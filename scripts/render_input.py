"""Render a PHMSA record as labeled plain-language lines without altering any source value."""
import re

STATES = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas', 'CA': 'California', 'CO': 'Colorado',
    'CT': 'Connecticut', 'DE': 'Delaware', 'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho',
    'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana',
    'ME': 'Maine', 'MD': 'Maryland', 'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota',
    'MS': 'Mississippi', 'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada',
    'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York', 'NC': 'North Carolina',
    'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma', 'OR': 'Oregon', 'PA': 'Pennsylvania',
    'RI': 'Rhode Island', 'SC': 'South Carolina', 'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas',
    'UT': 'Utah', 'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia',
    'WI': 'Wisconsin', 'WY': 'Wyoming',
}

# Labels follow the PHMSA field guide; fields not listed fall back to their readable field name.
LABELS = {
    'REPORT_NUMBER': 'Report number',
    'LOCAL_DATETIME': 'Incident date and time recorded on the form (local)',
    'INCIDENT_IDENTIFIED_DATETIME': 'Date and time the operator identified the incident (local)',
    'TIME_ZONE': 'Time zone',
    'NRC_RPT_DATETIME': 'Date and time reported to the National Response Center',
    'SHUTDOWN_DATETIME': 'Pipeline shutdown date and time',
    'RESTART_DATETIME': 'Pipeline restart date and time',
    'PIPE_FAC_NAME': 'Pipeline or facility name',
    'SEGMENT_NAME': 'Segment name',
    'ONSHORE_COUNTY_NAME': 'County',
    'ONSHORE_CITY_NAME': 'City',
    'ONSHORE_STATE_ABBREVIATION': 'State',
    'ITEM_INVOLVED': 'Item involved in the failure',
    'CAUSE': 'Apparent cause selected by the operator',
    'CAUSE_DETAILS': 'Apparent cause subcategory',
    'ROOT_CAUSE_CATEGORY': 'Excavation damage root cause category',
    'ROOT_CAUSE_TYPE': 'Excavation damage root cause type',
    'ROOT_CAUSE_TYPE_OTHER': 'Excavation damage root cause comment',
    'DEPTH_OF_COVER': 'Depth of cover (inches)',
    'PIPE_DIAMETER': 'Pipe diameter (inches)',
    'RUPTURE_LENGTH': 'Rupture length (inches)',
    'RUPTURE_WIDTH': 'Rupture width (inches)',
    'INVESTIGATION_STATUS_DETAILS': 'Operator investigation details',
    'NARRATIVE': 'Operator narrative',
}

UNITS = [
    (r'MMCF', 'million cubic feet'),
    (r'MSCF', 'thousand standard cubic feet'),
    (r'MCF', 'thousand cubic feet'),
    (r'SCF', 'standard cubic feet'),
    (r'BBLS?', 'barrels'),
    (r'PSIG', 'pounds per square inch gauge'),
    (r'PSI', 'pounds per square inch'),
]
UNIT_PATTERN = re.compile(r'(\d[\d,.]*\s?)(' + '|'.join(u for u, _ in UNITS) + r')\b')
UNIT_NAMES = [(re.compile(u + r'\Z'), name) for u, name in UNITS]


def gloss_units(text):
    """Append the unit's meaning after each numeric quantity, leaving the original text intact."""
    def expand(match):
        name = next(name for pattern, name in UNIT_NAMES if pattern.match(match.group(2)))
        return f'{match.group(0)} [{name}]'
    return UNIT_PATTERN.sub(expand, text)


def label(field):
    if field in LABELS:
        return LABELS[field]
    words = field.lower().replace('_ind', '').replace('_', ' ')
    return words[0].upper() + words[1:] + ('?' if field.endswith('_IND') else '')


def render(record):
    closing = ['INVESTIGATION_STATUS_DETAILS', 'NARRATIVE']
    known = [f for f in LABELS if f in record and f not in closing]
    others = sorted(f for f in record if f not in LABELS)
    lines = []
    for field in known + others + [f for f in closing if f in record]:
        value = str(record[field])
        if field == 'ONSHORE_STATE_ABBREVIATION' and value in STATES:
            value = f'{STATES[value]} ({value})'
        lines.append(f'{label(field)}: {gloss_units(value)}')
    return '\n'.join(lines)
