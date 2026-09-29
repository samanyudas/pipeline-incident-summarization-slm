# Small-model fine-tuning for pipeline incident summaries

Can a small open model, fine-tuned locally with LoRA, turn a federal pipeline incident report into a faithful seven-bullet summary?
This project tests that with Qwen3.5-0.8B and Qwen3.5-2B on PHMSA Type R gas gathering incident reports, using MLX on an Apple M3 laptop with 16 GiB of memory.

**Short answer: not reliably.**
The best configuration scored 14 of 30 rule points on five development reports, and every configuration made at least one critical factual error.
No model passed the pre-registered advancement gate, so the reserved final-test set was never used.
The full write-up is in [docs/results.md](docs/results.md).

## Task

Each summary has seven bullets: When, Where, What failed, What happened, Root cause, Contributing factors, and Evidence / certainty.
Summaries must keep operator-reported causes, observed mechanisms, suspicions, and unknowns distinct, and must preserve quantities, units, and negative findings.

## Method

- **Data:** PHMSA Type R incident export (111 reports), a U.S. government public-domain dataset; provenance is in [docs/source_record.json](docs/source_record.json) and [docs/source_rights.md](docs/source_rights.md).
- **Leakage control:** reports from the ten operators behind the development and final-test cases are excluded from training, which leaves 39 eligible reports.
- **References:** every training target was human-reviewed, and each bullet cites the source fields that support it ([docs/training_example_format.md](docs/training_example_format.md)).
- **Scoring:** six binary rules per report, 30 points across five development reports ([docs/scoring_rules.md](docs/scoring_rules.md)).
- **Gate:** acceptance criteria were fixed before any training ([docs/experiment_acceptance.md](docs/experiment_acceptance.md)).
- **Experiments:** one change at a time, each compared with an untrained model under matched settings.

## Results

| Configuration | Score |
|---|---:|
| Untrained 0.8B, JSON input | 4/30 |
| 0.8B LoRA, final-layer q/v, learning rate 1e-5 | 13/30 |
| Untrained 2B, readable input, heading normalization | 13/30 |
| 2B LoRA rank 32 on the final layer, learning rate 1e-4, repetition penalty 1.1 | **14/30** |
| Untrained 2B with the same repetition penalty | 9/30 |

Findings:

- The 0.8B model overrides what the input states: it wrote "15 million cubic feet" with "[thousand cubic feet]" printed beside the number.
- Only the final full-attention layer of Qwen3.5 can be adapted in 16 GiB; backpropagation through any linear-attention layer runs out of memory, even with a 4-bit base (QLoRA).
- Learning rate 1e-5 barely changed the models; 1e-4 learned the target style but caused repetition loops, which a repetition penalty removed; 5e-4 diverged.
- More training passes lowered loss while adding invented details.
- With 39 examples, the dataset is the main limit; common guidance suggests 200 to 500.

Five development cases cannot separate differences of a few points from noise, and scoring was done by a single assistant reviewer.

## Repository layout

```text
scripts/
  build_training_manifest.py   select training candidates, excluding reserved operators
  validate_review_revisions.py validate reviewed references against the source and export JSONL
  render_input.py              render a record as labeled lines with unit glosses
  run_mlx_experiment.py        MLX baseline, training, and evaluation runner
  normalize_output.py          rewrite heading markup without touching bullet text
  run_baseline.py              earlier llama-cli baseline runner
  test_*.py                    tests using temporary synthetic data
data/splits/                   candidate manifest (report numbers and operators only)
examples/                      development and final-test split manifests
prompts/                       prompt variants tried before training
docs/                          method, rules, acceptance criteria, and results
```

Raw data, reviewed references, exported training files, model weights, and model outputs are kept out of the repository.
The scripts rebuild them from the public source file.

## Reproducing

1. Download the Type R dataset and field guide from the PHMSA page linked in `docs/source_record.json`.
2. Create a Python 3.12 environment and install `requirements-training.lock.txt`.
3. Download the Qwen3.5 checkpoints from Hugging Face into `models/`.
4. Run `python3 scripts/build_training_manifest.py --include-nonfinal <path-to-source.txt>`.
5. Write and review references under `data/review/`, then export with `python3 scripts/validate_review_revisions.py <path-to-source.txt> --export-dir data/processed/<version>`.
6. Train and evaluate with `scripts/run_mlx_experiment.py`; run it with `--help` for all options.

Tests: `python3 scripts/test_render_input.py`, `python3 scripts/test_normalize_output.py`, `python3 scripts/test_baseline_manifest.py`, and `python3 scripts/test_review_export.py <path-to-source.txt>`.

## Status

The experiment is concluded, and no configuration is recommended for use.
This is a feasibility study, not a validated safety-analysis tool.
