"""Real ASGI and SQLite; mocked Gemini. Never represents live-model accuracy."""
import argparse, json, sys, time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tests'))
from test_gemini_offline import GeminiOffline
from evaluation.live100.cases import seed, cases, grade as legacy_grade
from .scenarios import suite, manifest
from .scoring import evaluate, summarize

def mock_reply(**kwargs):
    context=json.loads(kwargs['contents']);config=kwargs['config']
    if getattr(config,'response_json_schema',None):
        docs=context.get('public_knowledge',[])
        text=json.dumps({'answer':docs[0]['content'],'citations':[docs[0]['id']]},ensure_ascii=False) if docs else '{}'
    else:text='ตรวจสอบบัญชีและการเข้าสู่ระบบ ให้ SOC ตรวจสอบหลักฐานและ MFA'
    return SimpleNamespace(candidates=[SimpleNamespace(finish_reason='STOP')],text=text)

def execute(f,case,fault=None):
    from services import gemini_support as provider
    from core.rate_limits import FixedWindow
    records=[];room_id=None
    if case['room']:room_id=f.req('/api/chat-rooms',case['actor'],{}).json()['id']
    for ti,turn in enumerate(case['turns']):
        provider._minute=FixedWindow(60);provider._day=FixedWindow(86400)
        payload=dict(turn);target=payload.pop('company_ref',None)
        if target:payload['company_id']=str(f.companies[target])
        path='/api/customer-data/ask'
        if room_id:payload['content']=payload.pop('message');path=f'/api/chat-rooms/{room_id}/messages'
        start=time.monotonic();response=f.req(path,None if case['actor']=='anonymous' else case['actor'],payload);raw=response.json()
        company=f.companies[target or ('B' if case['actor']=='b1' else 'A')]
        other='A' if str(company)==str(f.companies['B']) else 'B'
        scope={'company_id':str(company),'forbidden_identifiers':[c['host'] for c in cases() if c['company']==other]}
        records.append({'scenario_id':case['id'],'group':case['group'],'family':case['family'],'turn':ti,
            'http_status':response.status_code,'response':raw,'request':{'path':path,'payload':payload},
            'latency_ms':round((time.monotonic()-start)*1000),'run_kind':'offline_mocked_provider','fault_injected':bool(fault),
            'fault':fault,'grade':evaluate(case,ti,response.status_code,raw,scope)})
    return records

def run(output):
    from services import gemini_support as provider
    from core.rate_limits import FixedWindow
    from google.genai import errors
    import httpx
    root=Path(output);root.mkdir(parents=True,exist_ok=True)
    f=GeminiOffline();f.setUp();records=[];fault_records=[];legacy=[]
    try:
        with f.Session() as db:seed(db,f.companies);db.commit()
        f.sdk.models.generate_content.side_effect=mock_reply
        for case in suite():records.extend(execute(f,case))
        for c in cases():
            provider._minute=FixedWindow(60);provider._day=FixedWindow(86400)
            raw=f.req('/api/customer-data/ask',payload={'action':'analyze_log','message':c['question']}).json()
            legacy.append({'case_id':c['case_id'],**legacy_grade(c,raw),'response':raw})
        fault_templates={'timeout':(0,65),'503':(25,41),'429':(1,40),
                         'schema':(2,41),'advice_rejected':(3,40),'disabled':(26,66)}
        for fault, indices in fault_templates.items():
            for template in (suite()[i] for i in indices):
                c={**template,'id':f'FAULT-{fault}-{template["id"]}'}
                def invalid(**kwargs):return SimpleNamespace(candidates=[SimpleNamespace(finish_reason='STOP')],text='{}')
                def reject(**kwargs):return SimpleNamespace(candidates=[SimpleNamespace(finish_reason='STOP')],text='ข้อมูลนี้ยังต้องตรวจสอบเพิ่มเติมก่อนนำไปใช้งาน')
                f.sdk.models.generate_content.side_effect={'timeout':httpx.ReadTimeout('offline timeout'),
                    '503':errors.ServerError(503,{'error':{'message':'offline error'}}),
                    '429':errors.ClientError(429,{'error':{'message':'offline rate limit'}}),
                    'schema':invalid,'advice_rejected':reject,'disabled':mock_reply}[fault]
                with patch.dict('os.environ',{'GEMINI_ENABLED':'false' if fault=='disabled' else 'true'}):
                    fault_records.extend(execute(f,c,fault))
    finally:f.tearDown();f.doCleanups()
    for name,rows in [('responses',records),('faults',fault_records),('legacy',legacy)]:
        (root/(name+'.jsonl')).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
    (root/'manifest.json').write_text(json.dumps(manifest(),ensure_ascii=False,indent=2))
    result={'run_kind':'offline_mocked_provider','external_gemini_calls':0,'pilot':summarize(records,100),
        'fault_injection':summarize(fault_records,12),
        'legacy_regression':{'total':len(legacy),'facts_passed':sum(x['facts_passed'] for x in legacy)},
        'limitations':['No real Gemini quality measurement','Semantic judge not calibrated; pending is not pass',
        'SQLite is not Neon/PostgreSQL','Browser DOM not tested by ASGI']}
    (root/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2));return result
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);run(ap.parse_args().output)
