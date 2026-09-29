"""Check that readable rendering preserves every source value and glosses units."""
import re

from render_input import render

record = {'NARRATIVE': 'RELEASED 15 MCF AND 80 BBLS AT 900 PSIG.', 'ONSHORE_STATE_ABBREVIATION': 'WV',
          'REPORT_NUMBER': '1', 'ONE_CALL_NOTIFIED_IND': 'NO', 'LOCAL_DATETIME': '2/28/2025 19:29'}
text = render(record)
stripped = re.sub(r' \[[a-z ]+\]', '', text)
for value in record.values():
    assert value in stripped, value
assert '15 MCF [thousand cubic feet]' in text
assert '80 BBLS [barrels]' in text
assert '900 PSIG [pounds per square inch gauge]' in text
assert 'State: West Virginia (WV)' in text
assert 'One call notified?: NO' in text
assert text.splitlines()[0] == 'Report number: 1' and text.splitlines()[-1].startswith('Operator narrative:')
print('render_input checks passed')
