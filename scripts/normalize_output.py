"""Rewrite heading markup of a seven-bullet answer to `- Heading: text` without touching bullet text."""
import argparse
import re
from pathlib import Path

HEADINGS = ('When', 'Where', 'What failed', 'What happened', 'Root cause',
            'Contributing factors', 'Evidence / certainty')
# Accepts plain, dashed, starred, numbered, and bold forms such as `*   **When**:` or `1. **When:**`.
LINE = re.compile(r'^\s*(?:[-*]|\d+[.)])?\s*(?:\*\*)?(' + '|'.join(map(re.escape, HEADINGS)) +
                  r')(?:\*\*)?\s*:\s*(?:\*\*)?\s*(.*\S)\s*$')


def normalize(answer):
    """Return the normalized answer, or None when it is not exactly seven headed bullets in order."""
    lines = [line for line in answer.strip().splitlines() if line.strip()]
    matches = [LINE.match(line) for line in lines]
    if len(lines) != len(HEADINGS) or not all(matches):
        return None
    if tuple(m.group(1) for m in matches) != HEADINGS:
        return None
    return '\n'.join(f'- {m.group(1)}: {m.group(2)}' for m in matches)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_dir', type=Path)
    parser.add_argument('output_dir', type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    for path in sorted(args.source_dir.glob('incident_*[0-9].txt')):
        result = normalize(path.read_text())
        if result is None:
            print(f'{path.name}: not normalized, structure differs from seven headed bullets')
            result = path.read_text()
        (args.output_dir / path.name).write_text(result + '\n')


if __name__ == '__main__':
    main()
