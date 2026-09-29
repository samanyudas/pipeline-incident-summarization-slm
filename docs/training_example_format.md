# Training-example draft format

Each local draft in `data/review/incident_<report_number>.json` represents one source report and one proposed seven-bullet answer.
Metadata includes report_number, operator_id, source_sha256, review_status, reviewer, reviewed_at, and review_notes.
The input object contains selected source fields, preserving explicit NO values, unknown values, dates, and narrative contradictions.
The target array contains seven objects in the requested order, each with heading, text, and source_fields.
Source-field references support human checking; they are not proof that the answer is correct.
Review metadata and evidence pointers are not model input.

## Input selection

Common fields identify the report, recorded incident and identified times, time zone, facility, segment, county, state, item, leak type, apparent cause, cause details, and narrative.
Additional fields depend on the failure category and must be checked against the PHMSA field guide.
The first batch includes internal-corrosion examination and treatment fields, pipe-joint examination and pressure-test fields, and operation-related details.
Do not apply the first batch's field list blindly to other cause categories.
Preserve absent information as absent; a blank analysis field does not mean no analysis occurred.
Strip only surrounding whitespace and enclosing export quotation marks, preserving internal punctuation and quantities.
Exclude preparer, authorizer, and contact details from model inputs.
Check narratives separately for unnecessary personal details before export.

## Review states

Every machine draft starts as draft with reviewer and reviewed_at unset.
A human may record needs_revision or rejected with reasons, or accepted with reviewer identity and date after checking the evidence.
Only accepted records are eligible for later export, and only after the separate rights and dataset checks pass.
No export or training is performed by creating a draft.

## First batch

`data/review/batch_01.md` presents reports 20220001, 20220002, and 20220004 with their selected source fields.
These are the first three report numbers in the eligible candidate manifest, not performance-selected examples.
The batch covers corrosion, pipe-joint failure, and incorrect operation.
Checks confirmed exact source values after permitted normalization, allowed operator membership, seven headings, valid source-field references, draft status, and exclusion of contact fields.
The cause-specific field meanings were checked against the local PHMSA field guide.
The first batch was accepted by Sam, then revised after the field-definition audit.
Sam accepted those revised records on September 28, 2026.

## Proposed revisions

`data/review/revisions/` contains separate proposed versions of all 33 targets.
Earlier originals are preserved under `data/review/history/pre_2026_09_28_acceptance/`.
Sam accepted 32 revised records, which now match the current records in `data/review/`.
Report 20250014 remains draft with its requested Evidence wording preserved and an inference qualification recorded.
Selecting that bullet wording has not been recorded as complete-report acceptance.
Every bullet includes supporting field references; the model input is restricted to cited fields plus report number.
`changes_for_review.md` shows only changed bullets; `revised_targets.md` includes full proposed answers and source evidence.
The validator checks source equality, references, schema, candidate coverage, and reserved-operator separation.
It does not certify semantic grounding or imply human acceptance.

## Accepted export

The September 28 export contains 32 accepted records and excludes draft 20250014.
Dataset version `phmsa-bcdb95566d0a` contains `train.jsonl` and `manifest.json` under `data/processed/`.
Each training line contains only a messages array with system, user, and assistant roles.
The user message serializes the selected source fields as JSON.
The assistant message preserves the seven accepted bullets exactly.
Review notes, evidence pointers, and approval metadata stay outside model messages.
The separate manifest records the system instruction, dataset version, source and output hashes, included report IDs, and hashes of the accepted records.

Run `python3 scripts/validate_review_revisions.py SOURCE_PATH --export-dir data/processed/phmsa-bcdb95566d0a` to reproduce this export from the same reviewed records.
The script validates all candidates before writing and refuses to overwrite a different existing export.
Run `python3 scripts/test_review_export.py SOURCE_PATH` to verify deterministic output, exact input/target preservation, and 12 rejection cases in temporary copies.
These checks record approval provenance but cannot authenticate the named reviewer or independently establish semantic correctness.
The system instruction and JSON input format must be matched in the next baseline comparison.
