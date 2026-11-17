import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from evaluation.v2.scenarios import suite, manifest
from evaluation.v2.scoring import aggregate,evaluate
from evaluation.v2.runner import Store,policy
from evaluation.v2.judge import calibration,confusion,validate

class EvaluationV2(unittest.TestCase):
    def test_manifest_and_family_split(self):
        from collections import Counter
        self.assertEqual(Counter(c['group'] for c in suite()),{'KB':25,'LIST':15,'ANALYSIS':25,'MULTITURN':15,'EDGE':10,'ACCESS':10})
        self.assertEqual(sum(len(c['turns']) for c in suite()),130)
        rows=calibration();self.assertEqual(len(rows),40)
        dev={r['family'] for r in rows if r['split']=='development'}
        hold={r['family'] for r in rows if r['split']=='holdout'}
        self.assertFalse(dev&hold)
    def test_pending_and_critical_never_pass(self):
        def item(label,critical=False):return dict(id='x',dimension='D1',label=label,required=True,critical=critical)
        self.assertEqual(aggregate([item('undetermined')])['outcome'],'pending')
        self.assertEqual(aggregate([item('incorrect',True)])['outcome'],'fail')
        self.assertEqual(aggregate([item('correct')])['outcome'],'pass')
    def test_wrong_extra_count_detected(self):
        c=suite()[40];e=c['oracle']['login']['expected'];ids=c['oracle']['login']['expected_ids']
        answer='ล็อกอินล้มเหลว 1 ครั้ง และสำเร็จ 0 ครั้ง\nล็อกอินล้มเหลว 9 ครั้ง และสำเร็จ 0 ครั้ง'
        result=evaluate(c,0,200,{'answer':answer,'analysis':{'login_activity':e,'findings':[{'log_id':i} for i in ids]}})
        self.assertIn('rendered_totals',result['critical_failed'])
    def test_fallback_and_quality_failure_continue(self):
        for reason in (None,'invalid_response','provider_unavailable','provider_timeout'):
            p={'provider':{'failure':reason,'fallback_used':True}}
            self.assertEqual(policy(200,p,{'outcome':'fail','critical_failed':[]})[0],'continue')
        self.assertEqual(policy(200,{'provider':{'failure':'provider_rate_limited'}},{})[0],'backoff')
        self.assertEqual(policy(200,{'provider':{'failure':'usage_limit'}},{})[0],'pause_quota')
        self.assertEqual(policy(200,{}, {'critical_failed':['tenant_canaries']})[0],'pause_security')
    def test_raw_saved_resume_and_budget(self):
        with tempfile.TemporaryDirectory() as d:
            store=Store(d);store.bind('manifest',manifest())
            self.assertTrue(store.reserve('V2-001:0',1));store.save('V2-001:0',{'response':{'answer':'fallback'}})
            store.db.close();store=Store(d)
            self.assertFalse(store.reserve('V2-001:0',1))
            self.assertEqual(store.records()[0]['response']['answer'],'fallback')
            with self.assertRaisesRegex(RuntimeError,'budget'):store.reserve('V2-002:0',1)
            with self.assertRaises(ValueError):store.bind('manifest',{'changed':True})
            store.set('not_before',1000)
            with patch('evaluation.v2.runner.time.time',return_value=950):self.assertEqual(store.wait_seconds(),50)
            store.db.close()
    def test_judge_rejects_fabricated_quotes_and_counts_missing_predictions(self):
        p={'answer':'real','evidence':{'KB-001':'source'},'assertions':[{'id':'x'}]}
        r={'assertions':[{'assertion_id':'x','label':'correct','answer_span':'invented','evidence_ids':['KB-001'],'reason':'test'}],'claims':[{'label':'correct','answer_span':'real','evidence_ids':['KB-001'],'reason':'test'}]}
        with self.assertRaises(ValueError):validate(r,p)
        result=confusion({'a':True,'b':True,'c':False},{'a':True,'b':False})
        self.assertEqual(result['error_recall'],.5);self.assertEqual(result['pending'],1)

import test_gemini_offline as fixture
class EvaluationProductFixes(unittest.TestCase):
    setUp=fixture.GeminiOffline.setUp
    tearDown=fixture.GeminiOffline.tearDown
    req=fixture.GeminiOffline.req
    def test_filtered_list_retains_scope_and_does_not_call_provider(self):
        from evaluation.live100.cases import seed,cases
        with self.Session() as db:seed(db,self.companies);db.commit()
        for index in (0,20,30,50,80,90):
            c=cases()[index]
            raw=self.req('/api/customer-data/ask',payload={'message':'ขอรายการ Log '+c['question']}).json()
            self.assertEqual({x['log_id'] for x in raw['analysis']['findings']},set(c['expected_ids']))
            self.assertFalse(raw['provider']['attempted']);self.assertFalse(raw['provider']['fallback_used'])
            self.assertEqual(raw['answer_origin'],'local_inventory')
        self.sdk.models.generate_content.assert_not_called()
    def test_specific_threat_beats_generic_alert(self):
        from services.knowledge_base import retrieve
        self.assertEqual(retrieve('malware จากชื่อ alert บอกชนิดได้แน่นอนไหม',self.companies['A'])[0]['id'],'KB-006')
    def test_transport_timeout_is_observable_and_fallback_retains_answer(self):
        import httpx
        self.sdk.models.generate_content.side_effect=httpx.ReadTimeout('private timeout detail')
        raw=self.req('/api/customer-data/ask',payload={'message':'login','action':'analyze_log'}).json()
        self.assertEqual(raw['provider']['failure'],'provider_timeout')
        self.assertTrue(raw['provider']['fallback_used']);self.assertTrue(raw['answer'])
        self.assertNotIn('private timeout detail',json.dumps(raw))
