"""Run a matched development baseline or a two-iteration local LoRA smoke test."""
import argparse
import hashlib
import json
import math
import time
from pathlib import Path
from types import SimpleNamespace

from render_input import render



def model_revision(model_dir):
    quantized = model_dir / 'quantization_source.json'
    if quantized.is_file():
        source = json.loads(quantized.read_text())
        return f"{source['hf_revision']}+q{source['q_bits']}g{source['q_group_size']}"
    revisions = {path.read_text().splitlines()[0] for path in (model_dir / '.cache/huggingface/download').glob('*.metadata')}
    if len(revisions) != 1:
        raise ValueError('Model directory must come from exactly one Hugging Face revision')
    return revisions.pop()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def read_training(manifest_path):
    manifest = json.loads(manifest_path.read_text())
    if manifest['schema_version'] != 1 or manifest['format'] != 'messages-only-jsonl':
        raise ValueError('Unsupported dataset manifest')
    name = manifest['training_file']
    if Path(name).name != name:
        raise ValueError('Training file must be a sibling filename')
    path = manifest_path.parent / name
    if path.resolve().parent != manifest_path.parent.resolve():
        raise ValueError('Training file escapes dataset directory')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest['training_sha256']:
        raise ValueError('Training hash mismatch')
    records = [json.loads(line) for line in raw.decode().splitlines()]
    if len(records) != manifest['training_records'] or not records:
        raise ValueError('Training count mismatch')
    for record in records:
        messages = record['messages']
        if [m['role'] for m in messages] != ['system', 'user', 'assistant']:
            raise ValueError('Unexpected training roles')
        if messages[0]['content'] != manifest['system_instruction']:
            raise ValueError('Training system instruction mismatch')
    return manifest, records


class NonThinkingTokenizer:
    def __init__(self, tokenizer):
        self.tokenizer = tokenizer

    def apply_chat_template(self, *args, **kwargs):
        kwargs['enable_thinking'] = False
        return self.tokenizer.apply_chat_template(*args, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['baseline', 'smoke', 'reload', 'train', 'evaluate'])
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--dataset-manifest', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--adapter-path', type=Path)
    parser.add_argument('--minimal-smoke', action='store_true')
    parser.add_argument('--learning-rate', type=float, default=1e-5)
    parser.add_argument('--lora-layers', type=int, choices=[2, 4], default=4, help='Final layers adapted by qlora4_r32')
    parser.add_argument('--repetition-penalty', type=float)
    parser.add_argument('--epochs', type=int, choices=[1, 2, 3])
    parser.add_argument('--lr-schedule', choices=['constant', 'cosine'], default='constant')
    parser.add_argument('--input-format', choices=['json', 'readable'], default='json')
    parser.add_argument('--memory-limit-gib', type=int, default=6)
    parser.add_argument('--adapter-profile', choices=['final_qv', 'wide', 'final_all_r32', 'qlora4_r32'], default='final_qv')
    args = parser.parse_args()
    if not math.isfinite(args.learning_rate) or not 0 < args.learning_rate <= 1e-3:
        parser.error('--learning-rate must be finite, positive, and at most 1e-3')
    if args.mode != 'train' and args.learning_rate != 1e-5:
        parser.error('A nondefault --learning-rate is permitted only for train mode')
    if args.input_format != 'json' and args.mode not in ('baseline', 'evaluate', 'train'):
        parser.error('--input-format readable is available only for baseline, evaluate, or train mode')
    if args.mode != 'train' and args.memory_limit_gib != 6:
        parser.error('A nondefault --memory-limit-gib is permitted only for train mode')
    if args.mode != 'train' and args.adapter_profile != 'final_qv':
        parser.error('A nondefault --adapter-profile is permitted only for train mode')
    if args.mode != 'train' and (args.epochs is not None or args.lr_schedule != 'constant'):
        parser.error('--epochs and --lr-schedule are permitted only for train mode')
    if args.repetition_penalty is not None and (args.mode not in ('baseline', 'evaluate') or not 1 < args.repetition_penalty <= 1.5):
        parser.error('--repetition-penalty must be in (1, 1.5] and is permitted only for baseline or evaluate mode')
    if not 1 <= args.memory_limit_gib <= 12:
        parser.error('--memory-limit-gib must be between 1 and 12')
    if args.minimal_smoke and args.mode != 'smoke':
        parser.error('--minimal-smoke is available only for smoke mode')
    if (args.mode in ('reload', 'evaluate')) != (args.adapter_path is not None):
        parser.error('--adapter-path is required only for reload or evaluate mode')
    if args.adapter_path and not all((args.adapter_path / name).is_file() for name in ('adapters.safetensors', 'adapter_config.json')):
        parser.error('Adapter weights or configuration missing')
    root = Path(__file__).resolve().parents[1]
    manifest, records = read_training(args.dataset_manifest)
    development = json.loads((root / 'examples/evaluation_candidates.json').read_text())
    if development['source_sha256'] != manifest['source_sha256']:
        raise ValueError('Development source hash mismatch')
    dev_ids = [r['report_number'] for r in development['selection']]
    if len(dev_ids) != 5 or len(set(dev_ids)) != 5:
        raise ValueError('Expected five distinct development cases')
    if set(dev_ids) & set(manifest['report_numbers']):
        raise ValueError('Development report appears in training')
    holdout = json.loads((root / 'examples/final_holdout.json').read_text())
    if holdout['source_sha256'] != manifest['source_sha256']:
        raise ValueError('Final reserve source hash mismatch')
    reserved = development['selection'] + holdout['selection']
    reserved_ids = {record['report_number'] for record in reserved}
    reserved_operators = {record['operator_id'] for record in reserved}
    review_records = manifest['review_records']
    if len(review_records) != len(records) or len(set(manifest['report_numbers'])) != len(records):
        raise ValueError('Training review identity coverage mismatch')
    for pair, reviewed, rid in zip(records, review_records, manifest['report_numbers']):
        if json.loads(pair['messages'][1]['content'])['REPORT_NUMBER'] != rid or reviewed['report_number'] != rid:
            raise ValueError('Training input/review identity mismatch')
        if rid in reserved_ids or reviewed['operator_id'] in reserved_operators:
            raise ValueError('Reserved report or operator appears in training')
    if args.output_dir.exists():
        raise ValueError('Output directory already exists; choose a new run name')
    if not args.model.is_dir():
        raise ValueError('Local model directory missing')
    revision = model_revision(args.model)
    # MLX imports initialize Metal; validate files and arguments first.
    import mlx.core as mx
    import numpy as np
    from mlx_lm import load, generate
    from mlx_lm.sample_utils import make_logits_processors, make_sampler
    if args.minimal_smoke or args.mode == 'train':
        mx.set_memory_limit(args.memory_limit_gib * 1024**3)
        mx.set_cache_limit(256 * 1024**2)
    mx.random.seed(0)
    np.random.seed(0)
    model, tokenizer = load(str(args.model), adapter_path=str(args.adapter_path) if args.adapter_path else None)
    template = NonThinkingTokenizer(tokenizer)
    args.output_dir.mkdir(parents=True)
    metadata = {'mode': args.mode, 'model_path': str(args.model.resolve()),
                'hf_revision': revision, 'dataset_version': manifest['dataset_version'],
                'training_sha256': manifest['training_sha256'], 'seed': 0,
                'enable_thinking': False, 'input_format': args.input_format, 'status': 'started'}
    write_json(args.output_dir / 'run.json', metadata)
    if args.mode in ('baseline', 'reload', 'evaluate'):
        max_tokens = 64 if args.mode == 'reload' else 700
        if args.adapter_path:
            metadata.update(adapter_path=str(args.adapter_path.resolve()), adapter_sha256=hashlib.sha256((args.adapter_path / 'adapters.safetensors').read_bytes()).hexdigest(), purpose='Five-case development evaluation' if args.mode == 'evaluate' else 'Reload compatibility check only, not a scored evaluation')
        results = []
        for rid in (dev_ids[:1] if args.mode == 'reload' else dev_ids):
            case = json.loads((root / f'examples/incident_{rid}.json').read_text())
            if case['source_report_number'] != rid:
                raise ValueError('Development case identity mismatch')
            messages = [{'role': 'system', 'content': manifest['system_instruction']},
                        {'role': 'user', 'content': render(case['input']) if args.input_format == 'readable' else json.dumps(case['input'], ensure_ascii=False, sort_keys=True)}]
            prompt = template.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            (args.output_dir / f'incident_{rid}_prompt.txt').write_text(prompt)
            start = time.monotonic()
            processors = make_logits_processors(repetition_penalty=args.repetition_penalty, repetition_context_size=64) if args.repetition_penalty else None
            answer = generate(model, tokenizer, prompt=prompt, max_tokens=max_tokens,
                              sampler=make_sampler(temp=0), logits_processors=processors, verbose=False)
            (args.output_dir / f'incident_{rid}.txt').write_text(answer)
            results.append({'report_number': rid, 'elapsed_seconds': time.monotonic() - start,
                            'answer_sha256': hashlib.sha256(answer.encode()).hexdigest()})
            write_json(args.output_dir / 'results.json', results)
            print(f'{rid}: saved complete unmodified model response', flush=True)
        metadata.update(status='complete', max_tokens=max_tokens, temperature=0, results=results,
                        repetition_penalty=args.repetition_penalty, repetition_context_size=64 if args.repetition_penalty else None)
    else:
        from mlx_lm.lora import CONFIG_DEFAULTS, train_model
        from mlx_lm.tuner.datasets import ChatDataset
        source_records = records
        if args.input_format == 'readable':
            records = [{'messages': [m if m['role'] != 'user' else {'role': 'user', 'content': render(json.loads(m['content']))} for m in r['messages']]} for r in records]
        dataset = ChatDataset(records, template, mask_prompt=True)
        lengths = []
        offsets = []
        for record in records:
            tokens, offset = dataset.process(record)
            prefix = template.apply_chat_template(record['messages'][:-1], add_generation_prompt=True, return_dict=False)
            if tokens[:offset] != prefix or offset <= 0 or offset >= len(tokens):
                raise ValueError('Assistant mask offset does not match exact token prefix')
            lengths.append(len(tokens))
            offsets.append(offset)
        max_length = 2560
        if max(lengths) > max_length:
            raise ValueError(f'Training sequence exceeds {max_length}; truncation forbidden')
        config = dict(CONFIG_DEFAULTS)
        config.update(model=str(args.model), train=True, fine_tune_type='lora',
                      adapter_path=str(args.output_dir / 'adapter'), seed=0, num_layers=4,
                      batch_size=1, iters=2, learning_rate=1e-5, steps_per_report=1,
                      steps_per_eval=100, save_every=2, max_seq_length=max_length,
                      grad_checkpoint=True, mask_prompt=True,
                      lora_parameters={'rank': 8, 'dropout': 0.0, 'scale': 20.0})
        if args.minimal_smoke or args.mode == 'train':
            keys = ['self_attn.q_proj', 'self_attn.v_proj']
            final_modules = dict(model.layers[-1].named_modules())
            if any(key not in final_modules for key in keys):
                raise ValueError('Final layer lacks the required full-attention projections')
            selected = list(range(len(records))) if args.mode == 'train' else sorted(range(len(records)), key=lambda index: (lengths[index], manifest['report_numbers'][index]))[:2]
            if args.mode != 'train' and len(selected) != 2:
                raise ValueError('Minimal smoke requires two complete training examples')
            selected_ids = []
            for index in selected:
                report_id = json.loads(source_records[index]['messages'][1]['content'])['REPORT_NUMBER']
                if report_id != manifest['report_numbers'][index]:
                    raise ValueError('Training row and manifest report identity differ')
                selected_ids.append(report_id)
            dataset = ChatDataset([records[index] for index in selected], template, mask_prompt=True)
            config.update(num_layers=1, lora_parameters={'rank': 4, 'dropout': 0.0, 'scale': 20.0, 'keys': keys})
            metadata.update(smoke_profile='full_dataset' if args.mode == 'train' else 'minimal', memory_limit_bytes=args.memory_limit_gib * 1024**3,
                            cache_limit_bytes=256 * 1024**2, selected_report_numbers=selected_ids,
                            selected_token_lengths=[lengths[index] for index in selected],
                            selection=f'All {len(records)} complete accepted examples' if args.mode == 'train' else 'Two shortest complete accepted examples; all records mask-checked first',
                            purpose='One epoch feasibility training' if args.mode == 'train' else 'Technical smoke only, not quality training')
        if args.mode == 'train':
            epoch = len(records)
            config.update(iters=epoch, save_every=epoch, learning_rate=args.learning_rate)
            metadata['epoch_coverage'] = f'Batch size 1; trainer permutes all {epoch} batches once; {epoch} iterations'
            if args.adapter_profile in ('wide', 'final_all_r32', 'qlora4_r32'):
                # Backpropagating through several linear-attention layers exhausts 16 GB; see the qlora4_r32 OOM record.
                wide_keys = ['self_attn.q_proj', 'self_attn.k_proj', 'self_attn.v_proj', 'self_attn.o_proj',
                             'mlp.gate_proj', 'mlp.up_proj', 'mlp.down_proj']
                # final_all_r32 uses rank 32 with alpha 64 (MLX scale = alpha / rank = 2).
                lora = {'rank': 8, 'scale': 20.0} if args.adapter_profile == 'wide' else {'rank': 32, 'scale': 2.0}
                layers = 1
                if args.adapter_profile == 'qlora4_r32':
                    # Four final layers span linear-attention blocks, so their projections are adapted too.
                    wide_keys = wide_keys + ['linear_attn.in_proj_qkv', 'linear_attn.out_proj']
                    layers = args.lora_layers
                config.update(num_layers=layers, lora_parameters={**lora, 'dropout': 0.0, 'keys': wide_keys})
            passes = args.epochs or (3 if args.adapter_profile in ('wide', 'final_all_r32') else 1)
            config.update(iters=passes * epoch, save_every=passes * epoch)
            metadata['epoch_coverage'] = f'Batch size 1; {passes * epoch} iterations cover all {epoch} examples {passes} time(s)'
            if args.lr_schedule == 'cosine':
                config['lr_schedule'] = {'name': 'cosine_decay', 'arguments': [args.learning_rate, passes * epoch]}
            metadata.update(adapter_profile=args.adapter_profile, epochs=passes, lr_schedule=args.lr_schedule)
        metadata.update(training_config=config, token_lengths=lengths, mask_offsets=offsets,
                        validation='No validation loss; no development or final reserve targets used')
        write_json(args.output_dir / 'run.json', metadata)
        # train_model freezes base weights before adding LoRA; empty validation set avoids held-out training.
        from mlx_lm.tuner.callbacks import TrainingCallback
        losses = []
        class LossRecorder(TrainingCallback):
            def on_train_loss_report(self, train_info):
                if not math.isfinite(train_info['train_loss']):
                    raise ValueError('Nonfinite training loss')
                losses.append(train_info)
                write_json(args.output_dir / 'training_losses.json', losses)
        train_model(SimpleNamespace(**config), model, dataset, [], LossRecorder())
        if len(losses) != config['iters']:
            raise ValueError('Expected one finite loss report per iteration')
        from mlx.utils import tree_flatten
        trainable = [name for name, _ in tree_flatten(model.trainable_parameters())]
        if not trainable or any('lora_' not in name for name in trainable):
            raise ValueError('Unexpected non-adapter trainable parameters')
        adapter = args.output_dir / 'adapter/adapters.safetensors'
        if not adapter.is_file():
            raise ValueError('Training did not save adapter')
        weights = mx.load(str(adapter))
        if not weights or not all(bool(mx.all(mx.isfinite(value)).item()) for value in weights.values()):
            raise ValueError('Adapter contains nonfinite weights')
        metadata.update(status='complete', trainable_parameters=trainable, training_losses=losses, adapter_weights_finite=True,
                        adapter_sha256=hashlib.sha256(adapter.read_bytes()).hexdigest())
    write_json(args.output_dir / 'run.json', metadata)


if __name__ == '__main__':
    main()
