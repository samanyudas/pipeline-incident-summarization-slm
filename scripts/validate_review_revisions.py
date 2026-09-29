"""Validate reviewed PHMSA records and optionally export accepted training pairs."""
import argparse
import csv
import hashlib
import json
from datetime import date
from difflib import SequenceMatcher
from itertools import combinations
from pathlib import Path

HEADINGS = ['When', 'Where', 'What failed', 'What happened', 'Root cause',
            'Contributing factors', 'Evidence / certainty']
SYSTEM_INSTRUCTION = (
    'Summarize the supplied PHMSA incident record using exactly seven bullets, '
    'in this order: When; Where; What failed; What happened; Root cause; '
    'Contributing factors; Evidence / certainty. Use only the supplied record. '
    'Preserve uncertainty, explicit negative findings, quantities, and units. '
    'Distinguish reported causes from confirmed mechanisms and recorded conditions '
    'from established causal contributions. Describe conflicting information without '
    'inventing a reconciliation. Do not invent missing facts.'
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


def validate(root, source):
    manifest = json.loads((root / 'data/splits/training_candidates.json').read_text())
    source_hash = digest(source.read_bytes())
    if source_hash != manifest['source_sha256']:
        raise ValueError('Source hash differs from the candidate manifest.')
    allowed = {r['report_number']: r['operator_id'] for r in manifest['selection']}
    if len(allowed) != len(manifest['selection']):
        raise ValueError('Repeated candidate manifest identity.')
    reserved = set()
    for name in ('evaluation_candidates.json', 'final_holdout.json'):
        split = json.loads((root / 'examples' / name).read_text())
        if split['source_sha256'] != source_hash:
            raise ValueError('Evaluation source hash mismatch.')
        reserved.update(r['operator_id'] for r in split['selection'])
    rows = {}
    with source.open(encoding='cp1252', newline='') as stream:
        for row in csv.DictReader(stream, delimiter='\t', quoting=csv.QUOTE_NONE):
            rid = row['REPORT_NUMBER']
            if rid in allowed:
                if rid in rows:
                    raise ValueError(f'Repeated source candidate: {rid}')
                if row['OPERATOR_ID'].strip() != allowed[rid]:
                    raise ValueError(f'Source operator identity mismatch: {rid}')
                rows[rid] = row
    if set(rows) != set(allowed):
        raise ValueError('Source candidate coverage is incomplete.')
    seen = set()
    accepted = []
    draft_ids = []
    for path in sorted((root / 'data/review/revisions').glob('incident_*.json')):
        record = json.loads(path.read_text())
        rid = record['report_number']
        if (rid not in allowed or rid in seen or record['operator_id'] != allowed[rid]
                or record['operator_id'] in reserved or path.name != f'incident_{rid}.json'):
            raise ValueError(f'Invalid or repeated candidate identity: {rid}')
        seen.add(rid)
        if record['schema_version'] != 1 or record['source_sha256'] != source_hash:
            raise ValueError(f'Invalid schema or source: {rid}')
        status = record['review_status']
        if status == 'accepted':
            reviewer = record['reviewer']
            reviewed_at = record['reviewed_at']
            if not isinstance(reviewer, str) or not reviewer.strip():
                raise ValueError(f'Missing reviewer: {rid}')
            if not isinstance(reviewed_at, str) or date.fromisoformat(reviewed_at).isoformat() != reviewed_at:
                raise ValueError(f'Invalid review date: {rid}')
            if any(flag.get('status') != 'resolved' for flag in record.get('grounding_flags', [])):
                raise ValueError(f'Unresolved grounding flag: {rid}')
            canonical_path = root / 'data/review' / path.name
            if json.loads(canonical_path.read_text()) != record:
                raise ValueError(f'Accepted revision differs from canonical reviewed record: {rid}')
            accepted.append((record, path, canonical_path))
        elif status == 'draft':
            if record['reviewer'] is not None or record['reviewed_at'] is not None:
                raise ValueError(f'Draft has acceptance metadata: {rid}')
            draft_ids.append(rid)
        else:
            raise ValueError(f'Unsupported review state: {rid}/{status}')
        if [b['heading'] for b in record['target']] != HEADINGS:
            raise ValueError(f'Invalid headings: {rid}')
        if record['input'].get('REPORT_NUMBER') != rid:
            raise ValueError(f'Input report identity mismatch: {rid}')
        cited = set()
        for bullet in record['target']:
            if (not isinstance(bullet['text'], str) or not bullet['text'].strip()
                    or '\n' in bullet['text'] or '\r' in bullet['text']
                    or not isinstance(bullet['source_fields'], list) or not bullet['source_fields']):
                raise ValueError(f'Empty or multiline bullet/evidence: {rid}')
            if any(key not in record['input'] for key in bullet['source_fields']):
                raise ValueError(f'Missing evidence reference: {rid}')
            cited.update(bullet['source_fields'])
        if set(record['input']) != cited | {'REPORT_NUMBER'}:
            raise ValueError(f'Uncited input fields: {rid}')
        for key, value in record['input'].items():
            if key not in rows[rid] or rows[rid][key].strip().removeprefix('"').removesuffix('"') != value:
                raise ValueError(f'Source value mismatch: {rid}/{key}')
            if key.startswith(('PREPARER_', 'AUTHORIZER_', 'LOCAL_CONTACT_', 'OPERATOR_')):
                raise ValueError(f'Unneeded administrative input: {rid}/{key}')
    if seen != set(allowed):
        raise ValueError('Candidate coverage is incomplete.')
    # Only candidate narratives are retained; final holdout narratives are not examined.
    narratives = {rid: ' '.join(row['NARRATIVE'].casefold().split()) for rid, row in rows.items()}
    exact, near = [], []
    for left, right in combinations(sorted(narratives), 2):
        if narratives[left] == narratives[right]:
            exact.append([left, right])
        ratio = SequenceMatcher(None, narratives[left], narratives[right], autojunk=False).ratio()
        if ratio >= 0.80:
            near.append({'reports': [left, right], 'character_similarity': round(ratio, 3)})
    result = {
        'status': 'structural_and_source_checks_passed',
        'records': len(seen), 'bullets': len(seen) * 7,
        'accepted_records': len(accepted), 'draft_records': len(draft_ids),
        'excluded_draft_report_numbers': draft_ids,
        'source_sha256': source_hash,
        'exact_narrative_duplicates': exact,
        'near_narrative_pairs_threshold_0_80': near,
        'limits': ['Reference existence and exact input equality do not prove semantic grounding.',
                   'Numeric meaning, unit interpretation, and causal statements require source-aware review.',
                   'Character similarity is a screening heuristic, not proof of incident independence.',
                   'Acceptance metadata and canonical equality record review; they do not authenticate the reviewer.']
    }
    return result, accepted


def export_payloads(result, accepted):
    if not accepted:
        raise ValueError('No accepted records to export.')
    lines = []
    reviews = []
    for record, path, canonical_path in accepted:
        example = {'messages': [
            {'role': 'system', 'content': SYSTEM_INSTRUCTION},
            {'role': 'user', 'content': json.dumps(record['input'], ensure_ascii=False, sort_keys=True)},
            {'role': 'assistant', 'content': '\n'.join(
                f"- {bullet['heading']}: {bullet['text']}" for bullet in record['target'])}
        ]}
        lines.append(json.dumps(example, ensure_ascii=False, sort_keys=True))
        reviews.append({'report_number': record['report_number'], 'operator_id': record['operator_id'],
                        'reviewer': record['reviewer'], 'reviewed_at': record['reviewed_at'],
                        'revision_sha256': digest(path.read_bytes()),
                        'canonical_sha256': digest(canonical_path.read_bytes())})
    training = ('\n'.join(lines) + '\n').encode()
    manifest = {'schema_version': 1, 'format': 'messages-only-jsonl',
                'dataset_version': 'phmsa-' + digest(training)[:12],
                'source_sha256': result['source_sha256'], 'training_file': 'train.jsonl',
                'training_sha256': digest(training), 'training_records': len(accepted),
                'report_numbers': [r['report_number'] for r, _, _ in accepted],
                'excluded_draft_report_numbers': result['excluded_draft_report_numbers'],
                'review_records': reviews, 'system_instruction': SYSTEM_INSTRUCTION}
    return training, encoded(manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--export-dir', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        result, accepted = validate(root, args.source)
        payloads = export_payloads(result, accepted) if args.export_dir else None
        # All source, review, and payload checks complete before any output is written.
        if payloads:
            for name, payload in zip(('train.jsonl', 'manifest.json'), payloads):
                existing = args.export_dir / name
                if existing.exists() and existing.read_bytes() != payload:
                    raise ValueError(f'Refusing to overwrite a different export: {existing}')
            args.export_dir.mkdir(parents=True, exist_ok=True)
            for name, payload in zip(('train.jsonl', 'manifest.json'), payloads):
                (args.export_dir / name).write_bytes(payload)
        (root / 'data/review/revisions/validation.json').write_bytes(encoded(result))
    except (ValueError, KeyError, TypeError, OSError) as error:
        raise SystemExit(f'Validation failed: {error}') from error
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
