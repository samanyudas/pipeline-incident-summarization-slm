"""Exercise the real CLI on an isolated copy; never modify reviewed originals."""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('source', type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='phmsa-export-test-') as temp:
    isolated = Path(temp)
    for directory in ('scripts', 'examples', 'data/splits'):
        (isolated / directory).mkdir(parents=True)
    (isolated / 'data/review/revisions').mkdir(parents=True)
    shutil.copy(root / 'scripts/validate_review_revisions.py', isolated / 'scripts')
    for name in ('evaluation_candidates.json', 'final_holdout.json'):
        shutil.copy(root / 'examples' / name, isolated / 'examples')
    shutil.copy(root / 'data/splits/training_candidates.json', isolated / 'data/splits')
    for directory in ('data/review', 'data/review/revisions'):
        for path in (root / directory).glob('incident_*.json'):
            shutil.copy(path, isolated / directory)
    output = isolated / 'export'
    command = [sys.executable, str(isolated / 'scripts/validate_review_revisions.py'), str(args.source), '--export-dir', str(output)]
    def run(ok):
        result = subprocess.run(command, capture_output=True, text=True)
        assert (result.returncode == 0) == ok, result.stdout + result.stderr
        return result
    run(True)
    original = {path.name: path.read_bytes() for path in output.iterdir()}
    run(True)
    assert original == {path.name: path.read_bytes() for path in output.iterdir()}
    pairs = [json.loads(line) for line in original['train.jsonl'].splitlines()]
    manifest = json.loads(original['manifest.json'])
    assert len(pairs) == 32 and '20250014' not in manifest['report_numbers']
    assert hashlib.sha256(original['train.jsonl']).hexdigest() == manifest['training_sha256']
    for rid, pair in zip(manifest['report_numbers'], pairs):
        reviewed = json.loads((isolated / f'data/review/incident_{rid}.json').read_text())
        assert json.loads(pair['messages'][1]['content']) == reviewed['input']
        assert pair['messages'][2]['content'] == '\n'.join(f"- {b['heading']}: {b['text']}" for b in reviewed['target'])
        assert all(set(message) == {'role', 'content'} for message in pair['messages'])
        assert set(pair) == {'messages'}
        assert [message['role'] for message in pair['messages']] == ['system', 'user', 'assistant']
        assert len(pair['messages'][2]['content'].splitlines()) == 7
    print('PASS real CLI export, 32 messages-only pairs, draft excluded, manifest hash, repeat determinism')
    first = isolated / 'data/review/revisions/incident_20220001.json'
    canonical = isolated / 'data/review/incident_20220001.json'
    draft = isolated / 'data/review/revisions/incident_20250014.json'
    def negative(name, path, change, mirror=False):
        saved = path.read_bytes()
        canonical_saved = canonical.read_bytes()
        record = json.loads(saved)
        change(record)
        path.write_text(json.dumps(record))
        if mirror:
            canonical.write_text(json.dumps(record))
        fresh_output = isolated / ('bad-' + name)
        command[-1] = str(fresh_output)
        try:
            result = run(False)
            assert not fresh_output.exists(), name
            assert original == {p.name: p.read_bytes() for p in output.iterdir()}, name
            print('PASS', name, result.stderr.strip())
        finally:
            path.write_bytes(saved)
            canonical.write_bytes(canonical_saved)
            command[-1] = str(output)
    negative('source-value', first, lambda r: r['input'].__setitem__('REPORT_NUMBER', 'wrong'), True)
    negative('canonical-drift', first, lambda r: r['target'][0].__setitem__('text', 'Changed answer'))
    negative('missing-reviewer', first, lambda r: r.__setitem__('reviewer', ''), True)
    negative('invalid-date', first, lambda r: r.__setitem__('reviewed_at', '2026-99-28'), True)
    negative('grounding-flag', first, lambda r: r.__setitem__('grounding_flags', [{'status': 'reviewer_requested_inference'}]), True)
    negative('draft-metadata', draft, lambda r: r.__setitem__('reviewer', 'Sam'))
    negative('missing-reference', first, lambda r: r['target'][0]['source_fields'].append('ABSENT'), True)
    negative('uncited-input', first, lambda r: r['input'].__setitem__('UNCITED', 'x'), True)
    negative('source-mismatch', first, lambda r: r['input'].__setitem__('NARRATIVE', 'changed'), True)
    negative('reserved-operator', first, lambda r: r.__setitem__('operator_id', 'reserved'), True)
    negative('false-acceptance', draft, lambda r: r.__setitem__('review_status', 'accepted'))
    original_train = (output / 'train.jsonl').read_bytes()
    (output / 'train.jsonl').write_text('different export\n')
    result = run(False)
    assert (output / 'train.jsonl').read_text() == 'different export\n'
    assert (output / 'manifest.json').read_bytes() == original['manifest.json']
    print('PASS refuse different existing export', result.stderr.strip())
    (output / 'train.jsonl').write_bytes(original_train)
    print('ALL CHECKS PASSED')
