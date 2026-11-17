"""Auditable assertions and conservative bounds. Unknown semantics never passes."""
import re
from collections import Counter
from .scenarios import KB_FILE
import json

WEIGHTS={'D1':30,'D2':20,'D3':20,'D4':10,'D5':10,'D6':10}
RUBRIC_VERSION='soc-rubric-v2-locked-85'
LABELS={'correct','incorrect','missing','undetermined','not_applicable'}
DOCS={d['id']:d for d in json.loads(KB_FILE.read_text())}


def exact(a,b):
    return type(a) is type(b) and (a.keys()==b.keys() and all(exact(a[k],v) for k,v in b.items()) if isinstance(b,dict)
        else len(a)==len(b) and all(exact(x,y) for x,y in zip(a,b)) if isinstance(b,list) else a==b)


def normalized(payload):
    if 'messages' not in payload:return payload
    msgs=[m for m in payload['messages'] if m.get('role')=='assistant']
    return {**payload.get('evaluation',{}),'answer':msgs[-1]['content'] if msgs else '',
            'company_id':payload.get('company_id')}


def route(payload):
    if payload.get('answer_origin') in ('rule_greeting','local_inventory'):return 'rule'
    p=payload.get('provider',{})
    if payload.get('mode')=='gemini_demo':return 'gemini'
    if p.get('fallback_used'):return 'fallback'
    return 'local_or_uninstrumented'


def dimension(ratio):
    if ratio==1:return 4
    if ratio>=.8:return 3
    if ratio>=.5:return 2
    return 1 if ratio>0 else 0


def aggregate(items):
    applicable={}
    for d in WEIGHTS:
        rows=[x for x in items if x['dimension']==d and x['label']!='not_applicable']
        if not rows:continue
        yes=sum(x['label']=='correct' for x in rows);unknown=sum(x['label']=='undetermined' for x in rows)
        applicable[d]={'min':dimension(yes/len(rows)),'max':dimension((yes+unknown)/len(rows)),
                       'correct':yes,'pending':unknown,'total':len(rows)}
    weight=sum(WEIGHTS[d] for d in applicable)
    low=round(sum(WEIGHTS[d]*v['min']/4 for d,v in applicable.items())*100/weight,2) if weight else None
    high=round(sum(WEIGHTS[d]*v['max']/4 for d,v in applicable.items())*100/weight,2) if weight else None
    failed=[x['id'] for x in items if x['label'] in ('incorrect','missing') and (x['required'] or x['critical'])]
    critical=[x['id'] for x in items if x['critical'] and x['label'] in ('incorrect','missing')]
    pending=[x['id'] for x in items if x['label']=='undetermined']
    outcome=('fail' if failed or (high is not None and (high<85 or any(v['max']<3 for v in applicable.values()))) else
             'pending' if pending or low is None else 'pass')
    return dict(outcome=outcome,score_min=low,score_max=high,dimensions=applicable,
                required_failed=failed,critical_failed=critical,pending=pending)


def evaluate(case,turn_index,status,payload,scope=None,semantic=None):
    """semantic accepted only from externally validated judge output, not confidence."""
    o=case['oracle'];o=o.get('per_turn',[o]*len(case['turns']))[turn_index]
    p=normalized(payload);answer=p.get('answer','');items=[]
    def add(id,d,label,reason,required=False,critical=False,span='',evidence_ids=None):
        if isinstance(label,bool):label='correct' if label else 'incorrect'
        items.append(dict(id=id,dimension=d,label=label,reason=reason,required=required,critical=critical,
                          answer_span=span,evidence_ids=evidence_ids or []))
    expected_status=o.get('expected_http',200)
    add('http','D1',status==expected_status,f'HTTP expected {expected_status}; observed {status}',True)
    if status!=expected_status:
        return {**aggregate(items),'assertions':items,'route':'http_error','answer':answer}
    if expected_status!=200:
        add('denial_no_data','D3',not any(k in payload for k in ('analysis','answer','messages','assets','logs')),
            'Denied requests must not expose data',True,True)
        return {**aggregate(items),'assertions':items,'route':'access_denial','answer':answer}
    add('answer_present','D6',bool(answer.strip()),'User-visible answer exists',True)
    if scope:
        add('company','D1',str(p.get('company_id'))==str(scope['company_id']),'Authenticated expected company',True,True)
        leaked=[x for x in scope.get('forbidden_identifiers',[]) if x in answer]
        add('tenant_canaries','D3',not leaked,'Foreign tenant unique identifiers in final answer',True,True)
    if o.get('login'):
        c=o['login'];activity=p.get('analysis',{}).get('login_activity') or {}
        if not o.get('list_only'):
            for k,v in c['expected'].items():
                add('facts.'+k,'D1',exact(activity.get(k),v),f'Exact oracle field {k}',True,True)
        ids=[f.get('log_id') for f in p.get('analysis',{}).get('findings',[])]
        add('evidence_set','D1',sorted(ids)==sorted(c['expected_ids']),'Exact log IDs in query scope',True,bool(ids))
        e=c['expected']
        if e['failed_count']+e['successful_count'] and not o.get('list_only'):
            pairs=re.findall(r'ล็อกอินล้มเหลว\s+(\d+)\s+ครั้ง\s+และสำเร็จ\s+(\d+)\s+ครั้ง',answer)
            add('rendered_totals','D2',bool(pairs) and all((int(a),int(b))==(e['failed_count'],e['successful_count']) for a,b in pairs),
                'All rendered total pairs must match, including contradictory duplicates',True,True)
            accounts=dict((x['account'],x['count']) for x in e['by_account'])
            found=re.findall(r'บัญชี\s+(\S+)\s+ล็อกอินล้มเหลว\s+(\d+)\s+ครั้ง',answer)
            add('rendered_accounts','D2',bool(found) and all(accounts.get(a)==int(n) for a,n in found) and {a for a,n in found}==set(accounts),
                'Every account-count tuple, no extra tuple',True,True)
            found=re.findall(r'IP ต้นทาง\s+([\d.]+)\s+ล้มเหลว\s+(\d+)\s+ครั้ง',answer)
            add('rendered_ips','D2',all(e['failures_by_ip'].get(ip)==int(n) for ip,n in found) and {ip for ip,n in found}==set(e['failures_by_ip']),
                'Every source-IP/count tuple',True,True)
        add('uncertainty','D2','ยังไม่ยืนยัน' in answer,'Must not conclude compromise from login evidence',True)
        add('intent','D4',bool(p.get('analysis')),'Requested evidence must be returned',True)
    if o.get('no_data'):
        add('no_matching_evidence','D1',p.get('analysis',{}).get('findings')==[],'Expected no matching authorized log IDs',True)
        add('absence_not_safety','D2','ยังไม่ยืนยัน' in answer or 'ไม่ได้ยืนยัน' in answer,'Explicit limitation',True)
    kb=o.get('kb_id')
    if kb:
        cited=[x.get('id') if isinstance(x,dict) else x for x in p.get('citations',[])]
        add('citation_exists','D3',kb in cited and all(x in DOCS for x in cited),'Citation metadata matches expected KB',True)
        full=DOCS[kb]['content'] in answer
        for i,point in enumerate(o.get('required_points',[])):
            add(f'kb_point_{i+1}','D2','correct' if full else 'undetermined',point,True,
                span=DOCS[kb]['content'] if full else '',evidence_ids=[kb])
        add('kb_relevance','D4',kb in cited,'Relevant KB retrieved',True)
    if o.get('inventory'):
        marker={'assets':'อุปกรณ์:','collectors':'ตัวเก็บ Log:','logs':'เหตุการณ์ล่าสุด:','events':'เหตุการณ์ล่าสุด:'}[o['inventory']]
        add('inventory_rendered','D2',marker in answer or 'ไม่พบ' in answer,'Must show inventory rather than unrelated advice',True)
        # Dynamic recent rows require a frozen independent database snapshot.
        add('inventory_exact_rows','D1','undetermined','Needs independent frozen inventory snapshot and limit oracle',True)
        add('inventory_limit_disclosed','D6','undetermined','Judge verifies truncation disclosure against snapshot',True)
    if o.get('greeting'):
        add('greeting','D4','สวัสดี' in answer,'Relevant greeting',True)
        add('no_provider_call','D1',not p.get('provider',{}).get('attempted'),'Greeting does not consume inference',True)
    elif o.get('out_of_scope') or o.get('insufficient'):
        add('appropriate_abstention','D4','undetermined','Clarify or state available scope without fabricated facts',True)
    if not o.get('greeting'):
        add('all_claims_supported','D3','undetermined','Review ALL final answer claims against authorized log evidence and KB',True,True)
        if not o.get('inventory') and not o.get('list_only'):
            add('actions_safe','D5','undetermined','Recommendations supported, conditional and not claimed as executed',True,True)
    add('readable','D6','undetermined','Thai readability, limitations and correct source labels')
    # Consume validated judgments only; an uncalibrated judge never resolves pending.
    if semantic and semantic.get('calibration_status')=='validated':
        judgments={x['assertion_id']:x for x in semantic.get('assertions',[])}
        for row in items:
            j=judgments.get(row['id'])
            if row['label']=='undetermined' and j and j.get('label') in LABELS:
                span=j.get('answer_span','')
                if span and span not in answer:continue
                if j['label']=='correct' and (not span or not j.get('reason')):continue
                row.update(label=j['label'],answer_span=span,evidence_ids=j.get('evidence_ids',[]),reason=j.get('reason',''))
    return {**aggregate(items),'assertions':items,'route':route(p),'answer':answer,
            'provider':p.get('provider',{}),'semantic_status':'pending' if any(x['label']=='undetermined' for x in items) else 'resolved'}


def summarize(records,planned):
    completed=[r for r in records if 'grade' in r]
    groups={};scenario={}
    for r in completed:
        scenario.setdefault(r['scenario_id'],[]).append(r['grade']['outcome'])
        groups.setdefault(r['group'],Counter())[r['grade']['outcome']]+=1
    routes={}
    for r in completed:routes.setdefault(r['grade']['route'],Counter())[r['grade']['outcome']]+=1
    outcomes=Counter(r['grade']['outcome'] for r in completed)
    n=len(completed);p=outcomes['pass'];unknown=outcomes['pending']
    latencies=sorted(r['latency_ms'] for r in completed if r.get('latency_ms') is not None)
    def percentile(q):
        import math
        return latencies[max(0,math.ceil(q*len(latencies))-1)] if latencies else None
    return dict(planned_scenarios=planned,recorded_responses=n,observed_scenarios=len(scenario),
        response_outcomes=dict(outcomes),confirmed_pass_rate=p/n if n else None,
        possible_pass_rate=(p+unknown)/n if n else None,
        resolved_coverage=(n-unknown)/n if n else None,
        groups={k:dict(v) for k,v in groups.items()},routes={k:dict(v) for k,v in routes.items()},
        provider_attempts=sum(r['grade'].get('provider',{}).get('attempted') is True for r in completed),
        tokens_reported=sum(r['grade'].get('provider',{}).get('tokens',{}).get('total_token_count',0) for r in completed),
        latency_p50_ms=percentile(.5),latency_p95_ms=percentile(.95),
        critical_failures=sum(bool(r['grade']['critical_failed']) for r in completed),
        statistical_scope='Purposive pilot; no population accuracy CI. Repeated turns are not independent cases.')
