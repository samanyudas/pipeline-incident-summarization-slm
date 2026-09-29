# Results: local LoRA fine-tuning for PHMSA Type R incident summaries

## Conclusion

Local LoRA fine-tuning did not make Qwen3.5-0.8B or Qwen3.5-2B faithful enough to summarize PHMSA Type R incident reports.
No configuration passed the advancement gate in `docs/experiment_acceptance.md`, so the reserved five-report final test was never run.
The best total, 14 of 30 rule points, came from a 2B adapter trained at learning rate 1e-4 and decoded with a repetition penalty; 13 of 30 was reached by the first 0.8B adapter and by the untrained 2B model with readable input and heading normalization.
Every configuration made at least one critical factual error on the five development reports.
The experiment stops here by decision on 2026-09-28.
This is a feasibility result on five development cases, not a general accuracy estimate.

## Task and method

The model writes seven bullets per incident: When, Where, What failed, What happened, Root cause, Contributing factors, and Evidence / certainty.
Inputs are selected fields from the PHMSA gas gathering incident export, 111 reports in total.
Training used reference answers reviewed and accepted by Sam: 32 examples at first, then 39 in dataset `phmsa-3f501523f2f8`.
Reports from the ten operators behind the five development and five final-test cases were excluded from training to prevent leakage.
That exclusion removed 72 reports, so 39 is every eligible report in this source.

Each run was scored against six binary rules per report in `docs/scoring_rules.md`, for 30 points across five development reports.
The rules cover format, time and location, failed item and sequence, cause, contributing factors and evidence, and factual integrity.
Scoring was done by the assistant against source fields and reviewed references, not by an independent pipeline specialist.
Training and evaluation ran with MLX on an Apple M3 with 16 GiB of memory, using deterministic generation and reasoning disabled.

## Scores

All runs below use the MLX backend and the same five development prompts for their input format.

| Run | Model | Input | Training | Score |
|---|---|---|---|---:|
| MLX baseline | 0.8B | JSON | none | 4/30 |
| V1 | 0.8B | JSON | final-layer q/v, rank 4, 32 steps, 32 examples | 13/30 |
| V2 | 0.8B | JSON | as V1, learning rate 1e-4 | 7/30 |
| V3 | 0.8B | readable | as V1 | 12/30 |
| 2B baseline | 2B | readable | none | 10/30 |
| 2B baseline, normalized | 2B | readable | none, headings normalized | 13/30 |
| V4 | 2B | JSON | as V1 | 11/30 |
| V5 | 2B | JSON | final-layer attention and MLP, rank 8, 96 steps | 8/30 |
| V6 | 0.8B | JSON | as V1, 39 examples | 9/30 |
| V7 | 2B | readable | as V1, 39 examples, headings normalized | 12/30 |

The earlier llama-cli runs (`matched_v1`, `field_guide_v1`, 10/30 each) used a different backend and are not comparable with these.
The unchanged 0.8B model with readable input and the unchanged 2B model with JSON input were run as probes but not formally scored.

## What each change showed

### Training the 0.8B model

V1 raised the score from 4 to 13 mainly by learning the seven-bullet format and dropping filler.
It still invented facts: a fuel-line failure in place of the coolant-line leak on 20260017, 11 inches of cover turned into lost depth on 20260009, and 15 MCF turned into 15 cubic feet on 20250011.
A tenfold learning rate (V2) added reversals of alarm function, dates, and normal conditions.

### Readable input

`scripts/render_input.py` renders fields as labeled lines and appends unit meanings, such as `15 MCF [thousand cubic feet]`.
With that gloss directly beside the number, the unchanged 0.8B model still wrote 15 million cubic feet and reversed "not out of normal ranges".
The 0.8B errors come from the model overriding what the input states, not from missing knowledge of units.
Readable input did help both models keep the two recorded times apart.

### The 2B model

With readable input, the unchanged 2B model preserved units and negations and kept the coolant-line sequence on 20260017.
It replaced those errors with others of similar severity, such as turning 11 inches of cover into an excavation depth.
Its headings used `*   **When**:` markup, which fails the format rule; `scripts/normalize_output.py` rewrites only that markup and brought it to 13/30.
The trained 2B adapter on JSON input (V4) never learned the required heading format.

### More adapter capacity

Adapting the last eight or four layers of the 2B model ran out of Metal memory on the first step.
Backpropagation through Qwen3.5 linear-attention layers does not fit in 16 GiB, so only the final full-attention layer can be adapted on this machine.
Widening that layer and training three passes (V5) cut training loss from 2.19 to 1.25 but lowered the score to 8/30.
The adapter memorized reference phrasing and copied one sentence into three bullets on 20240033.

### More training data

Sam reviewed and accepted the seven remaining eligible reports, including six non-final ORIGINAL reports, raising the dataset from 32 to 39 examples.
Retraining the V1 configuration (V6) scored 9/30 and repeated the V1 critical errors.
The 2B readable adapter (V7) scored 12/30 and was the first run to pass the cause rule on all five reports.
Neither result differs from its predecessor by more than five development cases can resolve.

### Learning rate, rank, and QLoRA (2026-09-29)

After a review of published LoRA practice, three untested levers were tried: adapting more layers with a 4-bit base (QLoRA), higher rank with alpha twice the rank, and learning rates of 1e-4 to 5e-4 with one or three passes and a cosine schedule.
QLoRA ran out of memory at step 2 with 4 layers and with 2 layers, so even one linear-attention layer cannot be adapted on this machine.
The sweep used rank 32, alpha 64 on all seven projections of the final layer; see `artifacts/v8_sweep_review.md`.
The best run (1e-4, one pass) scored 12/30; 5e-4 diverged; no run beat 13/30.
At 1e-4 the adapter produced the two best individual answers of the project, 5/6 each with correct A4 and A13 times, but two other answers fell into repetition loops that scored zero.
Three passes again lowered loss while adding invented details.
Higher learning rates are what let the adapter learn the target style, so the earlier 1e-5 runs understated what LoRA can do here; the remaining obstacles are generation instability and the 39-example dataset.

### Repetition penalty

A repetition penalty of 1.1 over a 64-token window removed every loop from the 1e-4 one-pass adapter, and all five answers passed the format rule.
It scored 14/30, the highest total of the project, against 9/30 for the untrained 2B model run with the same penalty; see `artifacts/v8_repetition_penalty_review.md`.
The one-point gain over the prior best is within what five cases can resolve.
Critical errors remain on four reports, including a reversed shielding field and a restart placed after repairs, so the adapter still fails the gate.

## Root cause of the low scores

The small models do not reliably copy stated facts from long structured records.
Training on 32 to 39 examples teaches format with little capacity, and memorized phrasing with more capacity, but not faithful extraction.
The persistent failure types across all runs are:

- merging or dropping the A4 reporting-criteria time;
- presenting recorded conditions, absent evidence, or post-incident corrective actions as contributing causes;
- naming a functioning shutdown system as the failed item;
- sequence reversals, such as a release placed after discovery or during excavation;
- invented locations and quantities.

## Limits of this evidence

Five development cases cannot distinguish a real change of a few points from run-to-run variation; all ten MLX configurations scored between 4 and 13.
The development cases were inspected repeatedly while choosing experiments, so they are not unseen data.
Scoring is by one assistant reviewer, and no pipeline specialist validated the reference answers' causal judgments.
The final-test set was preserved and never examined, so no held-out estimate exists.

## Recommendation

Do not deploy any configuration from this project for incident summarization.
If this work resumes, the most informative next steps are training hardware that can adapt more layers, and a larger development set so that score differences are measurable.
The strongest configuration without training is the unchanged 2B model with readable input and heading normalization.
Its outputs still require human review against the source record.

## Artifacts

Per-run outputs, `scores.json`, and `review.md` files are under `artifacts/`, named after the runs above.
The runner is `scripts/run_mlx_experiment.py`, with options `--input-format`, `--memory-limit-gib`, and `--adapter-profile`.
`HANDOFF.md` records the chronological run history and decisions.
