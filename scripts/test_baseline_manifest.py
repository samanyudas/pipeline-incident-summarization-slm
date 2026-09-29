"""Check baseline manifest mode with a mocked model process, never running inference."""
import contextlib
import hashlib
import io
import json
import runpy
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

runner_source = Path(__file__).resolve().with_name('run_baseline.py')
with tempfile.TemporaryDirectory(prefix='baseline-manifest-test-') as temp:
    root = Path(temp)
    (root / 'scripts').mkdir()
    (root / 'models').mkdir()
    (root / 'examples').mkdir()
    folder = root / 'data/processed/synthetic'
    folder.mkdir(parents=True)
    script = root / 'scripts/run_baseline.py'
    script.write_bytes(runner_source.read_bytes())
    (root / 'models/Qwen3.5-0.8B-BF16.gguf').touch()
    # All data and model placeholders are synthetic and confined to the temporary root.
    rid = '20260017'
    source_hash = 'synthetic-source-hash'
    dev = {'source_sha256': source_hash, 'selection': [{'report_number': rid}]}
    (root / 'examples/evaluation_candidates.json').write_text(json.dumps(dev))
    case = {'source_report_number': rid, 'input': {'z': 'é', 'REPORT_NUMBER': rid, 'a': 'NO'}, 'system_instruction': 'historical'}
    (root / f'examples/incident_{rid}.json').write_text(json.dumps(case))
    instruction = 'Synthetic exact system instruction. '
    training = (json.dumps({'messages': [{'role': 'system', 'content': instruction}, {'role': 'user', 'content': '{}'}, {'role': 'assistant', 'content': 'synthetic'}]}) + '\n').encode()
    (folder / 'train.jsonl').write_bytes(training)
    base = {'schema_version': 1, 'format': 'messages-only-jsonl', 'training_file': 'train.jsonl', 'training_sha256': hashlib.sha256(training).hexdigest(), 'source_sha256': source_hash, 'system_instruction': instruction, 'training_records': 1}
    selected = folder / 'manifest.json'
    selected.write_text(json.dumps(base))
    def execute(arguments, success, check=None):
        answer = '\n'.join('- ' + heading + ': value' for heading in ['When','Where','What failed','What happened','Root cause','Contributing factors','Evidence / certainty'])
        fake = subprocess.CompletedProcess([], 0, answer + '\n[ Prompt:', '')
        with patch.object(sys, 'argv', [str(script)] + arguments), patch('subprocess.run', return_value=fake) as model, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            try:
                runpy.run_path(str(script), run_name='__main__')
                assert success
            except SystemExit:
                assert not success
            if success:
                assert model.call_count == 1
                if check:
                    check(model.call_args.args[0])
            else:
                model.assert_not_called()
    def matched(command):
        assert command[command.index('-sys') + 1] == base['system_instruction']
        assert Path(command[command.index('-f') + 1]).read_text() == json.dumps(case['input'], ensure_ascii=False, sort_keys=True)
    execute(['--dataset-manifest',str(selected),'--label','matched',rid], True, matched)
    execute(['--dataset-manifest',str(selected),rid], False)
    execute(['--dataset-manifest',str(selected),'--instruction-file',str(selected),'--label','matched',rid], False)
    execute(['--dataset-manifest',str(selected),'--label','matched',rid,'20230005'], False)
    for key,value in [('schema_version',2),('format','wrong'),('training_sha256','wrong'),('training_file','../train.jsonl'),('source_sha256','wrong'),('system_instruction',''),('system_instruction','different prompt')]:
        selected.write_text(json.dumps(base | {key:value}))
        execute(['--dataset-manifest',str(selected),'--label','matched',rid], False)
    def legacy(command):
        assert command[command.index('-sys')+1] == 'historical'
        assert Path(command[command.index('-f')+1]).read_text().startswith('Incident report fields:\n')
    execute([rid], True, legacy)
    custom = folder/'instruction.txt'; custom.write_text(' custom historical instruction\n')
    execute(['--instruction-file',str(custom),'--label','custom',rid],True,lambda command: (_ for _ in ()).throw(AssertionError()) if command[command.index('-sys')+1] != 'custom historical instruction' else None)
    for prefix in ('*   **', '1. **'):
        formatted = '\n'.join(prefix + heading + ':** value' for heading in ['When','Where','What failed','What happened','Root cause','Contributing factors','Evidence / certainty'])
        captured = io.StringIO()
        with patch.object(sys, 'argv', [str(script), rid]), patch('subprocess.run', return_value=subprocess.CompletedProcess([], 0, 'runtime preamble\n' + formatted + '\n[ Prompt:', '')), contextlib.redirect_stdout(captured):
            runpy.run_path(str(script), run_name='__main__')
        assert (root / f'examples/incident_{rid}_baseline.txt').read_text() == formatted + '\n'
        assert 'missing headings: []' in captured.getvalue()
    raw = 'Unknown response formatting\n[ Prompt:'
    diagnostics = 'test diagnostic'
    with patch.object(sys, 'argv', [str(script), rid]), patch('subprocess.run', return_value=subprocess.CompletedProcess([], 0, raw, diagnostics)):
        try:
            runpy.run_path(str(script), run_name='__main__')
            raise AssertionError('Malformed answer unexpectedly parsed')
        except SystemExit as error:
            assert 'raw output saved' in str(error)
    assert (root / f'examples/incident_{rid}_baseline_stdout.txt').read_text() == raw
    assert (root / f'examples/incident_{rid}_baseline_stderr.txt').read_text() == diagnostics
print('PASS bold-star and numbered headings extracted without formatting changes')
print('PASS raw stdout/stderr preserved exactly on extraction failure')
print('PASS 13 mocked CLI cases: exact matched serialization/system, 10 rejection gates, both historical modes; no inference executed')
