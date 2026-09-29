"""Validate the pinned source and reserve operators, then list training candidates."""
import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('source', type=Path)
parser.add_argument('--include-nonfinal', action='store_true',
                    help='Also select ORIGINAL and SUPPLEMENTAL reports that have no FINAL filing.')
parser.add_argument('--output', type=Path, default=Path('data/splits/training_candidates.json'))
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
source_hash = hashlib.sha256(args.source.read_bytes()).hexdigest()
manifests = [json.loads((root / 'examples' / name).read_text()) for name in
             ('evaluation_candidates.json', 'final_holdout.json')]
if any(m['source_sha256'] != source_hash for m in manifests):
    raise SystemExit('Source hash differs from the frozen evaluation snapshot.')
reserved = [m['selection'] for m in manifests]
operator_sets = [{r['operator_id'] for r in group} for group in reserved]
if operator_sets[0] & operator_sets[1]:
    raise SystemExit('Development and final-test operators overlap.')
excluded = operator_sets[0] | operator_sets[1]
with args.source.open(encoding='cp1252', newline='') as stream:
    reader = csv.DictReader(stream, delimiter='\t', quoting=csv.QUOTE_NONE)
    rows = [{key: row[key].strip().strip('"') for key in
             ('REPORT_NUMBER', 'OPERATOR_ID', 'REPORT_TYPE', 'CAUSE')} for row in reader]
counts = Counter(r['REPORT_NUMBER'] for r in rows)
if any(n != 1 for n in counts.values()):
    raise SystemExit('Duplicate report numbers require report-version review.')
by_id = {r['REPORT_NUMBER']: r for r in rows}
for group in reserved:
    for record in group:
        row = by_id.get(record['report_number'])
        if row is None or row['OPERATOR_ID'] != record['operator_id']:
            raise SystemExit('Reserved report/operator does not match the source.')
allowed = [r for r in rows if r['OPERATOR_ID'] not in excluded]
final = sorted((r for r in allowed if args.include_nonfinal or 'FINAL' in r['REPORT_TYPE'].split()),
               key=lambda r: r['REPORT_NUMBER'])
result = {
    'schema_version': 1,
    'status': 'candidates_only_not_reviewed_training_data',
    'source_sha256': source_hash,
    'excluded_operator_ids': sorted(excluded),
    'source_report_count': len(rows),
    'eligible_report_count': len(allowed),
    'eligible_final_report_count': sum('FINAL' in r['REPORT_TYPE'].split() for r in allowed),
    'includes_nonfinal_reports': args.include_nonfinal,
    'candidate_operator_count': len({r['OPERATOR_ID'] for r in final}),
    'cause_counts': dict(sorted(Counter(r['CAUSE'] for r in final).items())),
    'selection': [dict(report_number=r['REPORT_NUMBER'], operator_id=r['OPERATOR_ID'],
                       report_type=r['REPORT_TYPE'], apparent_cause=r['CAUSE']) for r in final],
    'excluded_nonfinal_report_numbers': sorted(r['REPORT_NUMBER'] for r in allowed if r not in final),
}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k: v for k, v in result.items() if k not in ('selection', 'excluded_operator_ids')}, indent=2))
