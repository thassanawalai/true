"""Reviewed input allowlist. Changing data requires deliberate digest review."""
import copy
import hashlib
import json
from pathlib import Path

DATASET = Path(__file__).with_name('cases_v1.json')
APPROVED_SHA256 = '17df01f7758ba608a79c8295b0f7555cca1997451ff10792d5217d6f0957ea14'


def cases():
    raw = DATASET.read_bytes()
    if hashlib.sha256(raw).hexdigest() != APPROVED_SHA256:
        raise ValueError('Unapproved evaluation dataset; review before model export')
    records = json.loads(raw)
    if len(records) != 30 or len({c['case_id'] for c in records}) != 30:
        raise ValueError('Evaluation requires exactly 30 unique cases')
    return {c['case_id']: c for c in records}


def package(case_id):
    # Ground truth is intentionally not part of the model input or its hash.
    return copy.deepcopy(cases()[case_id]['package'])
