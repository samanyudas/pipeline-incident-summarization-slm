# Development scoring rules

Use these rules to compare the unchanged Qwen3.5-0.8B model with prompt revisions on the same five reviewed cases.
Score each rule as 1 only when the complete rule passes, or 0 otherwise.
Inspect the report input and the reviewed answer before assigning a score.
The reviewed answer guides the check, but a faithful alternative wording can pass.

1. **Format and brevity.**
   The response has exactly seven top-level bullets in the requested order, each starting with `- Heading:`.
   It has no nested list, redundant claim, or extra text.
   A repeated fact is acceptable when it adds evidence attribution, uncertainty, or a necessary sequence connection.
   Repetition that adds no information fails this rule.
2. **Time and location.**
   Dates, times, time zones, facilities, segments, and locations match the input.
   The response distinguishes A4 reporting-criteria time, A13 failure-identification time, and physical event times in the narrative.
   It states genuine material inconsistencies without treating different event definitions as contradictions.
3. **Failed item and sequence.**
   The response identifies the failed component and describes the event sequence accurately.
   It does not name a functioning alarm or shutdown system as the failed item, and it does not turn a consequence into a cause.
4. **Cause and certainty.**
   The response includes the operator's reported apparent cause and the supported mechanism.
   It labels a suspected deeper cause as suspected and says when the underlying cause is unknown.
   It does not invent a mechanism to reconcile inconsistent fields.
5. **Contributing factors and evidence.**
   The response identifies materially relevant supported contributors, or says none are established.
   A concise list of observed conditions may exceed three when the reviewer requires their inclusion, but must distinguish them from established causes.
   It distinguishes observations from proven contributions and cites the actual inspection, analysis, alarm, or narrative evidence available.
   It does not treat absent shielding evidence, detection, repairs, or a planned investigation as a cause.
6. **Factual integrity.**
   The response does not reverse a `YES` or `NO` field, negate a stated normal condition, or invent a fact.
   It preserves numbers and units, including `MCF`, which means thousand cubic feet.
   A single material contradiction makes this rule fail.

Record each failed rule with the exact output phrase and the conflicting source field or narrative sentence.
Treat a wrong cause, safety condition, date, or quantity as a critical error even if the total score rises.
These five cases are development cases because their answers have been inspected and used to improve the prompt.
Do not use them or any report from their operators for training.
The reports in `examples/final_holdout.json` stay outside prompt development and training.

## Field-definition correction from batch 3 review

PHMSA form A4 defines LOCAL_DATETIME as the earliest local time a reporting criterion was met, not necessarily physical incident onset.
A13 is the time the operator identified failure.
A difference between these fields alone must not be scored as a contradiction.
Proximity to an NRC call does not prove a formal-filing explanation.
A11 concerns inpatient-hospitalization injuries; D3 and D4 separately count non-overnight medical treatment and EMT treatment.
IO_FOLLOW_PROCEDURE_IND=YES denotes failure to follow procedures.
E10 investigation-status fields concern controllers and control-room issues.
Historical prompt scores and earlier accepted targets have not yet been rescored against these clarified definitions.
