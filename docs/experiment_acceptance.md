# Feasibility experiment acceptance criteria

These criteria are fixed before adapter training.
The training pool contains 32 accepted examples from dataset `phmsa-bcdb95566d0a`.
Report 20250014 is excluded until complete-report acceptance is recorded.

## Comparison

Use the five development reports listed in `examples/evaluation_candidates.json`.
Use the six binary rules in `docs/scoring_rules.md` without changing them to favor an adapter.
Keep source inputs, instruction, chat template settings, generation limit, and backend the same for base and adapter.
Disable reasoning and use deterministic generation where supported.
If training uses MLX instead of llama-cli, establish a fresh unchanged-model baseline on MLX.
Do not treat cross-backend score differences as an adapter effect.
Retain raw outputs and exact model, dataset, prompt, package, and adapter hashes.

## Training smoke test

Before a longer run, verify complete target tokenization without truncation, finite loss, adapter save, adapter reload, and successful generation.
Exclude all development and final-test operators from gradient updates.
Use no final-test narratives for prompt changes, training selection, or debugging.

## Advancement gate

An adapter may advance to the final test only if it beats its matched unchanged-model total score, introduces no report-level score regression, passes factual integrity on every development case, and produces no critical errors.
It must also pass the exact seven-bullet format rule on all five development cases.
A critical error is a materially wrong cause, failure or safety condition, event date, quantity, or unsupported causal claim.
An improved total alone is insufficient.
These are experiment gates, not evidence of operational reliability.

## Final test

Freeze the adapter, prompt, generation settings, and scoring rules before preparing final references and evaluating the reserved five reports once.
Report all failures and the small sample size.
Do not revise the model using final-test results and then reuse that set as an unseen test.
No deployment is authorized by passing this feasibility gate.
