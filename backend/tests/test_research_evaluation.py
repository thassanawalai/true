import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evaluation import catalog, runner
from services import incident_experiment as experiment
import test_gemini_offline as fixture


class ResearchEvaluation(unittest.TestCase):
    def test_exact_dataset_and_independent_ground_truth(self):
        cases=catalog.cases()
        self.assertEqual(len(cases),30)
        self.assertEqual(len({c['case_id'] for c in cases.values()}),30)
        self.assertEqual({c['category'] for c in cases.values()}, {'login','scan','malware','benign','uncertain'})
        with patch.object(experiment,'run_a',side_effect=AssertionError('Do not derive truth from A')):
            for key,case in cases.items():
                package=experiment.package_for(key)
                self.assertEqual(package,case['package'])
                self.assertNotIn('ground_truth',json.dumps(package))
                self.assertTrue(set(case['ground_truth']['evidence_ids']) <= {r['id'] for r in package['logs']})
        with patch.object(Path,'read_bytes',return_value=b'changed-private-input'):
            with self.assertRaises(ValueError):catalog.cases()

    def test_metrics_empty_denominators_fallback_and_claims(self):
        self.assertEqual(runner.counts(['a','b'],['a','c']),(1,1,1))
        self.assertEqual(runner.evidence_scores(1,1,1),dict(precision=.5,recall=.5,f1=.5))
        self.assertIsNone(runner.evidence_scores(0,0,0)['f1'])
        self.assertIsNone(runner.prediction(dict(status='fallback',analysis={'incident_type':'malware'})))
        package=experiment.package_for('R01')
        self.assertEqual(runner.claim_counts({'evidence_ids':['foreign'], 'summary':'Compromise confirmed'},package),
                         dict(unsupported=2,total=2))
        self.assertIsNone(runner.claim_counts({'broken':True},package))

    def test_full_mock_run_exports_and_failure_accounting(self):
        with patch.object(runner.provider,'new_client',side_effect=AssertionError('No live provider')):
            report=runner.evaluate('mock')
        self.assertEqual(len(report['rows']),60)
        self.assertEqual(report['metrics']['A']['scored'],30)
        self.assertEqual(report['metrics']['B']['scored'],26)
        self.assertGreater(report['metrics']['B']['raw_claims']['unsupported'],0)
        self.assertEqual(report['metrics']['B']['displayed_claims']['unsupported'],0)
        self.assertEqual(report['metrics']['B']['outcomes'],dict(success=26,validation_failure=2,timeout=1,fallback=1))
        for i in range(0,60,2):
            self.assertEqual(report['rows'][i]['input_sha256'],report['rows'][i+1]['input_sha256'])
        for row in report['rows']:
            if row['outcome']!='success':
                self.assertIsNone(row['prediction']);self.assertIsNone(row['classification_correct'])
        with tempfile.TemporaryDirectory() as root:
            target=Path(root)/'run';runner.export(report,target)
            self.assertEqual({p.name for p in target.iterdir()},{'results.json','results.csv','summary.md'})
            self.assertIn('SOFTWARE VERIFICATION ONLY',(target/'summary.md').read_text())
            self.assertEqual(len(json.loads((target/'results.json').read_text())['rows']),60)
            with self.assertRaises(FileExistsError):runner.export(report,target)

    def test_hash_mismatch_aborts_and_baseline_marks_b_skipped(self):
        with patch.object(experiment,'run_case',return_value=dict(input_sha256='wrong')):
            with self.assertRaisesRegex(ValueError,'hash mismatch'):runner.evaluate('mock')
        report=runner.evaluate('baseline')
        self.assertEqual(report['metrics']['B']['outcomes'],{'skipped':30})
        self.assertEqual(report['metrics']['B']['attempted'],0)
        self.assertIsNone(report['metrics']['B']['classification_accuracy'])

    def test_live_requires_operator_flag_and_configuration(self):
        from scripts.evaluate_research import main
        with tempfile.TemporaryDirectory() as root, patch.object(runner.provider,'incident_json') as provider:
            with self.assertRaises(SystemExit):main(['--mode','live','--output',root+'/new'])
            with patch.object(runner.provider,'configured',return_value=False):
                with self.assertRaises(SystemExit):main(['--mode','live','--enable-live','--output',root+'/new'])
            provider.assert_not_called()


class ResearchTenantAccess(unittest.TestCase):
    setUp=fixture.GeminiOffline.setUp
    tearDown=fixture.GeminiOffline.tearDown
    req=fixture.GeminiOffline.req

    def test_research_case_authorization_and_canary_detection(self):
        path='/api/customer-data/analyze-case'
        for case,user in [('R01','b1'),('R02','a1')]:
            self.assertEqual(self.req(path,user,{'case_id':case,'method':'B'}).status_code,404)
        self.assertEqual(self.req(path,None,{'case_id':'R01','method':'A'}).status_code,401)
        self.assertEqual(self.req(path,'admin',{'case_id':'R01','method':'A'}).status_code,422)
        self.assertEqual(self.req(path,'a1',{'case_id':'R01','method':'A','company_id':str(self.companies['B'])}).status_code,403)
        for case,user in [('R01','a1'),('R02','b1')]:
            response=self.req(path,user,{'case_id':case,'method':'A'})
            self.assertEqual(response.status_code,200)
            self.assertFalse(runner.tenant_leak(response.text,catalog.cases()[case]))
        self.sdk.models.generate_content.assert_not_called()
        self.assertTrue(runner.tenant_leak('eval-b-web-01',catalog.cases()['R01']))
