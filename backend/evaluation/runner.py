"""Measurements for synthetic software verification or operator-enabled live runs."""
import csv
import hashlib
import json
import math
import statistics
import time
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from evaluation import catalog
from services import incident_experiment as experiment, gemini_support as provider


def mock_provider(context, schema):
    """Input-only fake, NOT an oracle or a simulated performance claim.

    Deliberately ignores question semantics; first recognized event determines its
    response. Four fixed failures verify accounting. Ground truth is never read.
    """
    p = context['evidence']
    failures = {'R16': (None, 'provider_timeout'), 'R24': (None, 'provider_unavailable'),
                'R30': ('not-json', None)}
    if p['case_id'] in failures: return failures[p['case_id']]
    mapping = {'SUSPICIOUS_LOGIN': 'suspicious_login', 'FAILED_LOGIN': 'suspicious_login',
        'BRUTE_FORCE': 'suspicious_login', 'PORT_SCAN': 'port_scan', 'MALWARE': 'malware',
        'MALWARE_DETECTED': 'malware', 'RANSOMWARE': 'ransomware'}
    row = next((r for r in p['logs'] if r['event_type'] in mapping), None)
    kind = mapping[row['event_type']] if row else 'unknown_security_issue'
    return json.dumps(dict(incident_type=kind, risk_level=('HIGH' if kind=='ransomware' else 'MEDIUM') if row else 'UNKNOWN',
        summary=('Compromise confirmed.' if p['case_id']=='R08' else
                 context['factual_summary_options'][row['id']] if row else context['no_evidence_summary']),
        evidence_ids=[row['id']] if row else [], recommended_actions=[context['action_options'][0]],
        uncertainty=[context['uncertainty_options'][0]])), None


def outcome(result):
    if result['status'] in ('success', 'skipped', 'execution_error'): return result['status']
    reasons = result.get('validation_failures', [])
    if 'provider_timeout' in reasons: return 'timeout'
    if any(r.startswith('provider_') or r == 'context_limit' for r in reasons): return 'fallback'
    return 'validation_failure'


def prediction(result):
    if result['status'] != 'success': return None
    a = result['analysis']
    if result['method'] == 'A':
        return dict(incident_type=a['issue_type'], risk_level=a['risk']['level'],
                    evidence_ids=[r['log_id'] for r in a['findings']])
    return a


def counts(predicted, expected):
    p, e = set(predicted), set(expected)
    return len(p & e), len(p-e), len(e-p)


def ratio(a,b): return a/b if b else None


def evidence_scores(tp,fp,fn):
    return dict(precision=ratio(tp,tp+fp), recall=ratio(tp,tp+fn), f1=ratio(2*tp,2*tp+fp+fn))


def claim_counts(output, package):
    """Automated structural factual grounding, NOT semantic/human claim scoring.

    One unit per cited log ID and one summary unit when evidence is cited.
    Actions, uncertainty, classification and risk are assessed separately/excluded.
    Invalid JSON/schema shapes are unscorable, not assigned zero unsupported claims.
    """
    if not isinstance(output, dict) or not isinstance(output.get('evidence_ids'), list) or not all(
            isinstance(i,str) for i in output['evidence_ids']) or not isinstance(output.get('summary'),str):
        return None
    ids = output['evidence_ids']; facts = experiment.facts(package)
    bad = sum(i not in facts for i in ids)
    expected = ' '.join(facts.get(i, '') for i in ids) if ids else experiment.NO_EVIDENCE
    # A nonempty invented summary without IDs still constitutes one claim unit.
    summary_unit = bool(ids) or output['summary'] != experiment.NO_EVIDENCE
    return dict(unsupported=bad + int(summary_unit and output['summary'] != expected),
                total=len(ids) + int(summary_unit))


def tenant_leak(text, case):
    other = 'b' if case['tenant']=='Company A (Demo)' else 'a'
    foreign_ip = '198.51.100.110' if other=='b' else '192.0.2.110'
    # Package assets/collector IDs are stable across cases of one tenant.
    foreign = next(c for c in catalog.cases().values() if c['tenant'] != case['tenant'])
    tokens = [f'eval-{other}-web-01', foreign_ip, foreign['package']['assets'][0]['id'],
              foreign['package']['collectors'][0]['id']]
    tokens += [r['id'] for c in catalog.cases().values() if c['tenant'] != case['tenant'] for r in c['package']['logs']]
    return any(t in text for t in tokens)


def aggregate(rows, method):
    group = [r for r in rows if r['method']==method]
    scored = [r for r in group if r['outcome']=='success']
    tp=sum(r['tp'] for r in scored); fp=sum(r['fp'] for r in scored); fn=sum(r['fn'] for r in scored)
    latencies=sorted(r['latency_ms'] for r in group if r['latency_ms'] is not None)
    claims=[r['displayed_claims'] for r in scored if r['displayed_claims'] is not None]
    raw=[r['raw_claims'] for r in group if r['raw_claims'] is not None]
    return dict(attempted=sum(r['outcome']!='skipped' for r in group), total=len(group), scored=len(scored),
        outcomes=dict(Counter(r['outcome'] for r in group)),
        classification_accuracy=ratio(sum(r['classification_correct'] for r in scored),len(scored)),
        risk_agreement=ratio(sum(r['risk_correct'] for r in scored),len(scored)),
        evidence_set_accuracy=ratio(sum(r['fp']==0 and r['fn']==0 for r in scored),len(scored)),
        correct_classification_over_all_cases=ratio(sum(r['classification_correct'] for r in scored),len(group)),
        evidence=dict(tp=tp,fp=fp,fn=fn,**evidence_scores(tp,fp,fn)),
        displayed_claims=dict(unsupported=sum(c['unsupported'] for c in claims),total=sum(c['total'] for c in claims),
            rate=ratio(sum(c['unsupported'] for c in claims),sum(c['total'] for c in claims))),
        raw_claims=dict(scorable_cases=len(raw),unsupported=sum(c['unsupported'] for c in raw),total=sum(c['total'] for c in raw),
            rate=ratio(sum(c['unsupported'] for c in raw),sum(c['total'] for c in raw))),
        tenant_isolation_failures=sum(r['tenant_failure'] for r in group),
        raw_tenant_failures=sum(r['raw_tenant_failure'] for r in group),
        latency_ms=dict(median=statistics.median(latencies) if latencies else None,
                        p95=latencies[math.ceil(.95*len(latencies))-1] if latencies else None))


def evaluate(mode='mock'):
    if mode not in ('mock','live','baseline'): raise ValueError('Unknown mode')
    if mode=='live' and not provider.configured(): raise ValueError('Live provider not explicitly configured')
    rows=[]
    for key, case in catalog.cases().items():
        package=experiment.package_for(key)
        digest=hashlib.sha256(json.dumps(package,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        captured={}
        real_provider=provider.incident_json
        def capture(context,schema):
            captured['prompt_leak']=tenant_leak(json.dumps(context,ensure_ascii=False),case)
            raw,failure=(mock_provider if mode=='mock' else real_provider)(context,schema)
            captured['raw_leak']=tenant_leak(raw or '',case)
            try: captured['claims']=claim_counts(json.loads(raw),package) if raw else None
            except (ValueError,TypeError): captured['claims']=None
            return raw,failure
        for method in ('A','B'):
            if method=='B' and mode=='baseline':
                result=dict(method='B',status='skipped',input_sha256=digest,latency_ms=None,analysis=None)
            else:
                start=time.perf_counter()
                try:
                    with patch.object(provider,'incident_json',side_effect=capture):
                        result=experiment.run_case(key,method)
                except Exception:
                    result=dict(method=method,status='execution_error',input_sha256=digest,latency_ms=(time.perf_counter()-start)*1000,
                                analysis=None,validation_failures=['execution_error'])
            if result['input_sha256'] != digest: raise ValueError('A/B input hash mismatch; evaluation aborted')
            pred=prediction(result); truth=case['ground_truth']
            tp,fp,fn=counts(pred['evidence_ids'],truth['evidence_ids']) if pred else (0,0,0)
            claims=None
            if pred and method=='B': claims=claim_counts(pred,package)
            elif pred:
                allowed={r['id']:r for r in package['logs']}
                findings=result['analysis']['findings']
                bad=sum(f['log_id'] not in allowed or any(f[k]!=allowed[f['log_id']][k]
                    for k in ('asset_id','event_type','message','occurred_at')) for f in findings)
                claims=dict(unsupported=sum(f['log_id'] not in allowed for f in findings)+int(bool(bad)),
                            total=len(findings)+int(bool(findings)))
            rows.append(dict(case_id=key,category=case['category'],method=method,mode=mode,
                outcome=outcome(result),input_sha256=digest,latency_ms=result['latency_ms'],
                classification_correct=pred['incident_type']==truth['incident_type'] if pred else None,
                risk_correct=pred['risk_level']==truth['risk_level'] if pred else None,
                tp=tp,fp=fp,fn=fn,**evidence_scores(tp,fp,fn),
                displayed_claims=claims,raw_claims=captured.get('claims') if method=='B' else None,
                tenant_failure=tenant_leak(json.dumps(result,ensure_ascii=False),case) or (captured.get('prompt_leak',False) if method=='B' else False),
                raw_tenant_failure=captured.get('raw_leak',False) if method=='B' else False,
                ground_truth=truth,prediction=pred,result=result))
    return dict(dataset_sha256=catalog.APPROVED_SHA256,mode=mode,
        implementation_sha256={name:hashlib.sha256((Path(__file__).resolve().parents[1]/name).read_bytes()).hexdigest()
            for name in ('services/security_analysis.py','services/incident_experiment.py',
                         'services/gemini_support.py','evaluation/runner.py')},
        warning='MOCKED GEMINI: SOFTWARE VERIFICATION ONLY; NOT REAL GEMINI PERFORMANCE' if mode=='mock' else 'Synthetic small-sample evaluation; see methodology limitations.',
        metrics={m:aggregate(rows,m) for m in ('A','B')},
        by_category={category:{m:aggregate([r for r in rows if r['category']==category],m) for m in ('A','B')}
                     for category in sorted({r['category'] for r in rows})},rows=rows)


def export(report, directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
    (directory/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    fields=list(report['rows'][0])
    with (directory/'results.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for row in report['rows']:
            writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items()})
    lines=['# Minimal synthetic evaluation', '', report['warning'], '',
           'Dataset SHA-256: `'+report['dataset_sha256']+'`', '',
           'Metrics exclude unsuccessful B predictions; fallback is never counted as Gemini success.', '',
           '| Method | Successful / total | Classification | Risk agreement | Evidence F1 | Outcomes |',
           '|---|---:|---:|---:|---:|---|']
    for method,m in report['metrics'].items():
        lines.append(f"| {method} | {m['scored']} / {m['total']} | {m['classification_accuracy']} | {m['risk_agreement']} | {m['evidence']['f1']} | {m['outcomes']} |")
    for method,m in report['metrics'].items():
        lines += ['', f"{method}: grounding counts/rates={m['displayed_claims']}; raw structural counts={m['raw_claims']}; "
                  f"tenant failures={m['tenant_isolation_failures']}, raw={m['raw_tenant_failures']}; latency={m['latency_ms']}", '']
    lines += ['Grounding is a structural evidence check, not human semantic assessment. Zero denominators are null.',
              'Latency includes wrapper/SQLite setup and fallback; mock latency is not model latency.',
              'Tenant checks use synthetic canaries, not a complete authorization audit. See evaluation/README.md.']
    (directory/'summary.md').write_text('\n'.join(lines)+'\n')
