# Dataset preparation decision

## Scope

Use the 33 eligible final reports as a feasibility experiment, using the documented publisher public-domain designation and conditional on reviewing target answers.
This scope tests whether a small adapter can improve the specified summary task.
It does not establish reliability for safety decisions.
The candidate set spans 19 operators and eight apparent-cause categories.
Equipment failure accounts for ten reports, while other outside force damage has only one.
This uneven coverage limits category-level conclusions.

## Candidate selection

Run `python3 scripts/build_training_manifest.py /absolute/path/to/incident_type_r_reporting_regulated_gas_gathering_may2022_present.txt` from the project directory.
The script requires the source hash used by both evaluation manifests, rejects duplicate report numbers, validates reserved report/operator pairs, and excludes all reserved operators.
It selects records with FINAL as a complete word in REPORT_TYPE.
The output is `data/splits/training_candidates.json`.
This snapshot contains one row per report number, including supplemental final records; no duplicate report numbers were found.
The manifest is a candidate inventory, not a training approval or a target-quality assessment.
Near-duplicate narrative review remains part of training-pair preparation.
No final-test narrative is exposed by the script.

## Review and export

Keep raw source data, draft answers, reviewed targets, and model outputs local by default.
Publishable project material is limited for now to processing code, source links and hashes, split metadata, and documentation without report excerpts.
Nothing is published by this decision.
The rights review in `source_rights.md` records the publisher public-domain designation and its series-level scope.

Every proposed pair needs a report number, operator ID, source hash, selected input fields, seven answer bullets, and source-field support for each bullet.
Each pair starts with review_status set to draft and reviewer unset.
A named human reviewer must accept or reject it after comparing the draft with the evidence.
Only accepted pairs may enter training JSONL.
Automated format and split checks cannot substitute for this review.
Do not silently fill missing fields, resolve contradictory dates, convert suspicions into facts, or infer causal contribution from a recorded condition alone.

## Experiment boundaries

The five development cases guide prompt and adapter selection.
Their operators and the five final-test operators remain excluded from training.
Do not expand the source snapshot or change the reserves silently.
A changed source requires a new version and a split review.
Choose a fixed baseline and success criteria before training.
A feasibility result must report the number of reviewed training pairs actually used, not the candidate count.
A five-case final test cannot establish a general error rate with useful precision.

## Selector verification

The selector produced identical output in two consecutive runs against the pinned source.
A changed-source fixture was rejected without writing an output manifest.
Isolated fixtures also verified rejection of duplicate report IDs, overlapping development/test operators, and reserved report/operator mismatches.
All five checks passed on September 27, 2026.
These checks do not establish narrative uniqueness or target quality.
