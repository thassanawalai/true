"""One-shot synthetic PostgreSQL smoke. Retains one ticket; never calls live Gemini."""
import os, sys, json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
assert sys.argv[1:]==['--synthetic-demo'], 'Explicit synthetic demo opt-in required'
os.environ['GEMINI_ENABLED']='false'
from main import app
from core.database import engine, SessionLocal
from sqlalchemy import text, inspect
from models.models import User, Ticket, Company
from fastapi.testclient import TestClient
from services import gemini_support as provider, temporary_chat
passed=0
def check(name,condition):
 global passed
 if not condition:
  print(f'FAIL: {name}; {passed} PASS, 1 FAIL; stopped without cleanup',flush=True); raise SystemExit(1)
 passed+=1; print('PASS:',name,flush=True)
with SessionLocal() as db:
 check('PostgreSQL connection',db.execute(text('SELECT 1')).scalar()==1)
 check('schema: 13 tables',len(inspect(engine).get_table_names())==13)
 check('synthetic-only preconditions', {u.email for u in db.query(User)}=={'customer.a1@example.test','customer.a2@example.test','customer.b1@example.test','support@example.test','admin@example.test'} and {c.name for c in db.query(Company)}=={'Company A (Demo)','Company B (Demo)','Internal SOC (Demo)'} and db.query(Ticket).count()==0)
 check('no administrative role privileges',not any(db.execute(text('SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=current_user')).one()))
sdk=MagicMock()
sdk.models.generate_content.return_value=SimpleNamespace(candidates=[SimpleNamespace(finish_reason='STOP')],text='ตรวจสอบข้อความน่าสงสัยผ่านช่องทางที่เชื่อถือได้ และแจ้ง SOC ตามขั้นตอนองค์กร')
with patch.dict(os.environ,{'GEMINI_ENABLED':'true','GEMINI_API_KEY':'synthetic-mock-key','GEMINI_MODEL':'synthetic-mock-model'}), patch.object(provider,'new_client',return_value=sdk), TestClient(app) as client:
 check('FastAPI lifespan health',client.get('/').status_code==200)
 users=client.get('/api/demo-auth/users').json(); check('five demo users',len(users)==5)
 users={u['name']:u for u in users}; tokens={}
 for name in users:
  r=client.post('/api/demo-auth/login',json={'user_id':users[name]['id']})
  check('mock login '+name,r.status_code==200 and r.json()['user']['name']==name); tokens[name]=r.json()['token']
 def req(method,path,user='Customer A1',**kw):
  return client.request(method,path,headers={'Authorization':'Bearer '+tokens[user]},**kw)
 check('unauthenticated denial',client.get('/api/customer-data/assets').status_code==401)
 for name,prefix in [('Customer A1','192.0.2.'),('Customer B1','198.51.100.')]:
  assets=req('GET','/api/customer-data/assets',name).json()
  check('synthetic telemetry '+name,len(assets)==2 and all(a['ip_address'].startswith(prefix) for a in assets) and len(req('GET','/api/customer-data/logs',name).json())==2 and len(req('GET','/api/customer-data/collectors',name).json())==1)
 b=users['Customer B1']['company_id']
 check('A cannot select B telemetry',req('GET','/api/customer-data/assets?company_id='+b).status_code==403)
 before=sdk.models.generate_content.call_count
 check('A cannot select B AI context',req('POST','/api/customer-data/ask',json={'message':'phishing','company_id':b}).status_code==403 and sdk.models.generate_content.call_count==before)
 result=req('POST','/api/customer-data/ask',json={'message':'phishing RAW_PRIVATE_CANARY'}).json()
 check('KB with Mock Gemini',result['mode']=='gemini_demo' and result['citations'][0]['id']=='KB-003')
 payload=sdk.models.generate_content.call_args.kwargs['contents']
 check('Gemini context privacy',all(x not in payload for x in ('RAW_PRIVATE_CANARY','b-web-01','198.51.100.10')) and json.loads(payload)['public_knowledge'][0]['id']=='KB-003')
 with patch.dict(os.environ,{'GEMINI_ENABLED':'false'}):
  fallback=req('POST','/api/customer-data/ask',json={'message':'phishing'}).json()
  missing=req('POST','/api/customer-data/ask',json={'message':'ขอสูตรทำอาหาร'}).json()
 check('Thai fallback and citations',fallback['mode']=='rule_based_demo' and 'ขณะนี้ไม่ได้ใช้ AI' in fallback['answer'] and '[KB-003]' in fallback['answer'])
 check('no-match limitation',missing['citations']==[] and 'หลักฐานไม่เพียงพอ' in missing['answer'])
 room=req('POST','/api/chat-rooms',json={}).json()['id']; path='/api/chat-rooms/'+room
 answer=req('POST',path+'/messages',json={'content':'phishing'}).json()['messages'][-1]['content']
 check('private customer chat citation','[KB-003]' in answer)
 check('same-company private denial',req('GET',path,'Customer A2').status_code==404)
 check('cross-company private denial',req('GET',path,'Customer B1').status_code==404)
 check('SOC human reply',req('POST',path+'/messages','SOC Support',json={'content':'Synthetic recovery smoke: SOC reviewed demo evidence.'}).status_code==200)
 linked=req('POST',path+'/ticket',json={'subject':'SYNTHETIC DEMO: Phase A recovery verification'}).json(); tid=linked['ticket_id']; ticket='/api/tickets/'+tid
 check('explicit ticket creation',bool(tid) and linked['temporary'] is False)
 check('company ticket metadata visible',req('GET',ticket,'Customer A2').status_code==200)
 check('other company ticket denied',req('GET',ticket,'Customer B1').status_code==404)
 check('customer status change denied',req('PATCH',ticket+'/status',json={'status':'RESOLVED'}).status_code==403)
 check('SOC assignment',req('PATCH',ticket+'/assign','SOC Support',json={'assignee_id':users['SOC Support']['id']}).status_code==200)
 check('SOC resolution',req('PATCH',ticket+'/status','SOC Support',json={'status':'RESOLVED'}).status_code==200)
 with temporary_chat.lock: temporary_chat.rooms.clear()
 history=req('GET','/api/chat-rooms/by-ticket/'+tid).json()
 check('PostgreSQL citation persistence',any(m['content']==answer for m in history['messages']))
 check('linked history stays private',all(req('GET','/api/chat-rooms/by-ticket/'+tid,n).status_code==404 for n in ('Customer A2','Customer B1')))
print(f'TOTAL: {passed} PASS, 0 FAIL. Mock Gemini only. One synthetic RESOLVED ticket retained.')
