"""Check heading normalization and refusal of malformed answers."""
from normalize_output import HEADINGS, normalize

for prefix, suffix in [('*   **', '**:'), ('**', ':**'), ('', ':'), ('1. ', ':'), ('- ', ':')]:
    answer = '\n'.join(f'{prefix}{h}{suffix} text about {h}' for h in HEADINGS)
    assert normalize(answer) == '\n'.join(f'- {h}: text about {h}' for h in HEADINGS), prefix
assert normalize('\n'.join(f'- {h}: x' for h in HEADINGS[:6])) is None
assert normalize('\n'.join(f'- {h}: x' for h in reversed(HEADINGS))) is None
assert normalize('\n'.join(f'- {h}: x' for h in HEADINGS) + '\nextra line') is None
print('normalize_output checks passed')
