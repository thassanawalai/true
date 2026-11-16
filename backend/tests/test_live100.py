"""Actual API and database, mocked Gemini; no external calls."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import test_gemini_offline as fixture
from evaluation.live100.cases import cases,seed,grade
from evaluation.live100.runner import Ledger
from services import gemini_support as provider
from core.rate_limits import FixedWindow

class Live100(unittest.TestCase):
    setUp=fixture.GeminiOffline.setUp
    tearDown=fixture.GeminiOffline.tearDown
    req=fixture.GeminiOffline.req
    def test_all_cases_and_idempotent_seed(self):
        from models.customer_data import CustomerLog
        with self.Session() as db:
            seed(db,self.companies);db.commit()
            count=db.query(CustomerLog).count()
            seed(db,self.companies);db.commit()
            self.assertEqual(count,db.query(CustomerLog).count())
        reports=[]
        for case in cases():
            provider._minute=FixedWindow(60)
            response=self.req('/api/customer-data/ask',payload={'action':'analyze_log','message':case['question']})
            self.assertEqual(response.status_code,200)
            payload=response.json();result=grade(case,payload)
            reports.append(dict(case_id=case['case_id'],**result))
            self.assertTrue(result['facts_passed'],(case['case_id'],result['checks'],payload['analysis']))
            self.assertTrue(result['gemini_passed'])
            self.assertTrue(payload['provider']['attempted'])
        self.assertEqual(self.sdk.models.generate_content.call_count,100)
        Path('/tmp/soc-live100-offline-results.json').write_text(json.dumps(reports,indent=2))
    def test_error_metadata_and_shared_incident_quota(self):
        from google.genai import errors
        self.sdk.models.generate_content.side_effect=errors.ClientError(429,{'error':{'message':'private-detail'}})
        result=self.req('/api/customer-data/ask',payload={'action':'analyze_log','message':'login'}).json()
        self.assertEqual(result['provider']['failure'],'provider_rate_limited')
        self.assertEqual(result['provider']['http_status'],429)
        self.assertNotIn('private-detail',json.dumps(result))
        with patch.dict('os.environ',{'GEMINI_MAX_CALLS_PER_DAY':'1'}):
            answer,reason=provider.incident_json({}, {})
            self.assertIsNone(answer);self.assertEqual(reason,'usage_limit')
        self.assertEqual(self.sdk.models.generate_content.call_count,1)
    def test_chat_response_has_evaluation_without_second_call(self):
        room=self.req('/api/chat-rooms',payload={}).json()['id']
        result=self.req('/api/chat-rooms/'+room+'/messages',payload={'content':'login','action':'analyze_log'}).json()
        self.assertTrue(result['evaluation']['provider']['succeeded'])
        self.sdk.models.generate_content.assert_called_once()

class LedgerTest(unittest.TestCase):
    def test_resume_budget_and_cooldown(self):
        with tempfile.TemporaryDirectory() as d:
            path=str(Path(d)/'state.sqlite');ledger=Ledger(path,budget=2,interval=60)
            with patch('evaluation.live100.runner.time.time',return_value=1000):
                self.assertTrue(ledger.reserve('one'));self.assertFalse(ledger.reserve('one'))
                with self.assertRaisesRegex(RuntimeError,'Cooldown'):ledger.reserve('two')
            ledger.db.close();ledger=Ledger(path,budget=2,interval=60)
            with patch('evaluation.live100.runner.time.time',return_value=1061):
                self.assertFalse(ledger.reserve('one'));self.assertTrue(ledger.reserve('two'))
            with patch('evaluation.live100.runner.time.time',return_value=1122):
                with self.assertRaisesRegex(RuntimeError,'Budget'):ledger.reserve('three')
            ledger.bind('version','one')
            with self.assertRaises(ValueError):ledger.bind('version','two')
            report=ledger.report(str(Path(d)/'report.json'))
            self.assertEqual(report['facts_passed'],0)
            self.assertEqual(report['attempts'][0]['status'],'in_flight')
            ledger.db.close()

class RunnerFlow(unittest.TestCase):
    def test_success_resume_and_fallback_stop(self):
        import os
        from evaluation.live100 import runner
        class Response:
            status_code=200
            def __init__(self,payload): self.payload=payload
            def json(self): return self.payload
            def raise_for_status(self): pass
        class Client:
            calls=[]
            fallback=False
            def __init__(self,**kwargs): pass
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def get(self,path): return Response({'id':'test-user','company_id':'company-a','role':'CUSTOMER','company':'Company A (Demo)'})
            def post(self,path,json):
                case=next(c for c in cases() if c['question']==json['message'])
                self.calls.append(case['case_id'])
                e=case['expected']
                text=f"ยังไม่ยืนยันการบุกรุก ล็อกอินล้มเหลว {e['failed_count']} ครั้ง และสำเร็จ {e['successful_count']} ครั้ง"
                text+=' '.join(f"บัญชี {r['account']} ล็อกอินล้มเหลว {r['count']} ครั้ง" for r in e['by_account'])
                text+=' '.join(f'IP ต้นทาง {ip} ล้มเหลว {n} ครั้ง' for ip,n in e['failures_by_ip'].items())
                return Response({'analysis':{'login_activity':e,'findings':[{'log_id':i} for i in case['expected_ids']]},'answer':text,
                    'mode':'rule_based_demo' if self.fallback else 'gemini_demo','provider':{'succeeded':not self.fallback}})
        with tempfile.TemporaryDirectory() as directory:
            state=str(Path(directory)/'state.sqlite');report=str(Path(directory)/'results.json')
            argv=['runner','--url','https://example.test','--state',state,'--report',report,'--limit','2']
            with patch.dict(os.environ,{'SOC_EVAL_TOKEN':'test-only-token'}),patch('sys.argv',argv),patch.object(runner.httpx,'Client',Client),patch.object(runner.Ledger,'remaining_wait',return_value=0),patch.object(runner.time,'time',side_effect=range(1000,100000,100)):
                runner.main()
                self.assertEqual(Client.calls,['EVAL-001','EVAL-002'])
                runner.main()
                self.assertEqual(Client.calls,['EVAL-001','EVAL-002','EVAL-003','EVAL-004'])
                Client.fallback=True
                runner.main()
                self.assertEqual(len(Client.calls),5)
                with self.assertRaises(SystemExit): runner.main()
            saved=json.loads(Path(report).read_text())
            self.assertEqual(saved['facts_passed'],5)
            self.assertEqual(saved['gemini_passed'],4)
            self.assertNotIn('test-only-token',Path(report).read_text())

class GradingTest(unittest.TestCase):
    def test_exact_rejects_boolean_count(self):
        from evaluation.live100.cases import exact
        self.assertFalse(exact(True,1))
        self.assertFalse(exact({'x':True},{'x':1}))
        self.assertFalse(exact([1,2],[1]))
        self.assertTrue(exact({'x':[1,False]},{'x':[1,False]}))
