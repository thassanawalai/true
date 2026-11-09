"""Versioned synthetic-only A/B experiment. Never reads runtime telemetry/history.

Method A executes the frozen analyzer on an isolated in-memory snapshot. Method B
receives the same input snapshot, NOT Method A predictions. HTTP authorization is
performed before selecting a case. Catalog changes require source review.
"""
import hashlib
import json
import time
from datetime import datetime
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from core.database import Base
from core.demo_telemetry import FIXTURES
from models.customer_data import CustomerAsset, CustomerLog, LogCollector
from models.models import Company
from services import security_analysis as baseline, knowledge_base as kb, gemini_support

VERSION = 'synthetic-incident-v1'
CASES = {
    'a-login': ('Company A (Demo)', 'Suspicious login on a-web-01 192.0.2.10', False),
    'b-scan': ('Company B (Demo)', 'Port scan on b-web-01 198.51.100.10', False),
    'a-no-evidence': ('Company A (Demo)', 'Suspicious login on a-web-01', True),
    'b-no-evidence': ('Company B (Demo)', 'Port scan on b-web-01', True),
}
# Register reviewed research cases without changing the four Phase 2 smoke cases.
from evaluation import catalog as research_catalog
CASES.update({key: (row['tenant'], row['package']['question'], False)
              for key, row in research_catalog.cases().items()})

Incident = Literal['suspicious_login', 'port_scan', 'ransomware', 'malware', 'phishing',
                   'data_exfiltration', 'network_attack', 'unknown_security_issue']
UNCERTAINTY = ['Compromise is not confirmed.', 'Event volume and impact are unknown.',
               'The reported incident may not match the stored events.']
NO_EVIDENCE = 'No supporting log evidence was selected; the report is unconfirmed.'
ACTION_OPTIONS = list(dict.fromkeys(a for actions in baseline.ACTIONS.values() for a in actions)) + baseline.GENERIC_ACTIONS


class IncidentOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    incident_type: Incident
    risk_level: Literal['UNKNOWN', 'MEDIUM', 'HIGH']
    summary: str = Field(min_length=1, max_length=2400)
    evidence_ids: list[str] = Field(max_length=10)
    recommended_actions: list[str] = Field(min_length=1, max_length=5)
    uncertainty: list[str] = Field(min_length=1, max_length=3)


def uid(name):
    return uuid5(NAMESPACE_URL, VERSION + '/' + name)


def package_for(case_id):
    """Only source-controlled synthetic values; no arbitrary payload input seam."""
    if case_id in research_catalog.cases():
        return research_catalog.package(case_id)
    tenant, question, empty = CASES[case_id]
    collector, site, entries = FIXTURES[tenant]
    assets, logs = [], []
    for ip, host, kind, event, message in entries:
        asset_id = str(uid(host))
        assets.append(dict(id=asset_id, ip_address=ip, hostname=host, asset_type=kind))
        if not empty:
            logs.append(dict(id=str(uid(host + '/log')), asset_id=asset_id,
                collector_id=str(uid(collector)), event_type=event, message=message,
                occurred_at='2026-11-04T03:00:00'))
    documents = kb.public_context(kb.retrieve(question, uid(tenant)))
    return dict(version=VERSION, case_id=case_id, data_kind='approved_synthetic', question=question,
                assets=assets, logs=logs, collectors=[dict(id=str(uid(collector)), name=collector, site=site)],
                public_knowledge=documents)


def run_a(package):
    """Use baseline SQL correlation unchanged, against synthetic data only."""
    engine = create_engine('sqlite://')
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            cid = uid('snapshot-tenant')
            db.add(Company(id=cid, name='Synthetic experiment')); db.flush()
            for a in package['assets']:
                db.add(CustomerAsset(company_id=cid, **{**a, 'id': UUID(a['id'])}))
            for c in package['collectors']:
                db.add(LogCollector(company_id=cid, **{**c, 'id': UUID(c['id'])}))
            db.flush()
            for row in package['logs']:
                data = {**row, **{k: UUID(row[k]) for k in ('id', 'asset_id', 'collector_id')},
                        'occurred_at': datetime.fromisoformat(row['occurred_at'])}
                db.add(CustomerLog(company_id=cid, **data))
            db.flush()
            return baseline.analyze(package['question'], db, cid)
    finally:
        engine.dispose()


def facts(package):
    assets = {a['id']: a for a in package['assets']}
    return {r['id']: f"Stored event {r['event_type']} on {assets[r['asset_id']]['hostname']} "
            f"({assets[r['asset_id']]['ip_address']}) at {r['occurred_at']} UTC: {r['message']}."
            for r in package['logs']}


def validate_output(raw, package):
    """Extractive factual language is enforced, not a heuristic hallucination detector."""
    try:
        # Reject duplicate JSON keys rather than silently accepting last-value wins.
        def unique(pairs):
            result = {}
            for k, v in pairs:
                if k in result: raise ValueError('duplicate_key')
                result[k] = v
            return result
        decoded = json.loads(raw, object_pairs_hook=unique)
        output = IncidentOutput.model_validate(decoded)
    except (ValueError, TypeError, ValidationError):
        return None, ['schema_invalid']
    errors = []
    allowed = facts(package)
    ids = output.evidence_ids
    if len(set(ids)) != len(ids) or any(i not in allowed for i in ids):
        errors.append('unknown_or_duplicate_evidence')
    else:
        expected = ' '.join(allowed[i] for i in ids) if ids else NO_EVIDENCE
        if output.summary != expected: errors.append('unsupported_summary_claim')
    if any(a not in ACTION_OPTIONS for a in output.recommended_actions):
        errors.append('unsupported_action_claim')
    if any(u not in UNCERTAINTY for u in output.uncertainty):
        errors.append('unsupported_uncertainty_claim')
    # A selected event must support the proposed incident class. Classification
    # without logs is tentative; risk must be UNKNOWN. No silent score override.
    event_types = next((events for kind, _, events in baseline.RULES if kind == output.incident_type), ())
    selected = [r for r in package['logs'] if r['id'] in ids]
    if any(r['event_type'] not in event_types for r in selected): errors.append('unsupported_incident_type')
    risk = 'UNKNOWN' if not ids else ('HIGH' if output.incident_type in ('ransomware', 'data_exfiltration') else 'MEDIUM')
    if output.risk_level != risk: errors.append('risk_policy_violation')
    return (None, errors) if errors else (output.model_dump(), [])


def run_case(case_id, method):
    """Independent entry point for trusted offline evaluation of catalog cases only."""
    if method not in ('A', 'B'): raise ValueError('Unknown method')
    started = time.perf_counter()
    package = package_for(case_id)
    digest = hashlib.sha256(json.dumps(package, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    result = dict(run_id=str(uuid4()), case_id=case_id, method=method, baseline_commit='cd6a5e9',
                  input_sha256=digest, prompt_version=gemini_support.INCIDENT_PROMPT_VERSION,
                  status='success', fallback=False, validation_failures=[], analysis=None)
    if method == 'A':
        result['analysis'] = run_a(package)
        result['effective_method'] = 'A'
        result['model'] = None
    else:
        context = dict(evidence=package, factual_summary_options=facts(package),
                       no_evidence_summary=NO_EVIDENCE, action_options=ACTION_OPTIONS,
                       uncertainty_options=UNCERTAINTY)
        raw, failure = gemini_support.incident_json(context, IncidentOutput.model_json_schema())
        parsed, errors = validate_output(raw, package) if not failure else (None, [failure])
        result.update(model=gemini_support.configured_model(), effective_method='B', analysis=parsed)
        if errors:
            result.update(status='fallback', fallback=True, effective_method='A',
                          validation_failures=errors, analysis=None, fallback_analysis=run_a(package))
    result['latency_ms'] = round((time.perf_counter() - started) * 1000, 3)
    return result
