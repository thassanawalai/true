"""Synthetic A/B contracts, mocked SDK and network denial from existing fixture."""
import json
import os
import unittest
from unittest.mock import patch
from services import incident_experiment as experiment, gemini_support as provider
import test_gemini_offline as fixture


class IncidentExperiment(unittest.TestCase):
    setUp = fixture.GeminiOffline.setUp
    tearDown = fixture.GeminiOffline.tearDown
    req = fixture.GeminiOffline.req

    def output(self, case='a-login'):
        package = experiment.package_for(case)
        evidence = [package['logs'][0]['id']] if package['logs'] else []
        return dict(incident_type='port_scan' if case.startswith('b-') else 'suspicious_login',
            risk_level='MEDIUM' if evidence else 'UNKNOWN', evidence_ids=evidence,
            summary=experiment.facts(package)[evidence[0]] if evidence else experiment.NO_EVIDENCE,
            recommended_actions=[experiment.ACTION_OPTIONS[0]], uncertainty=[experiment.UNCERTAINTY[0]])

    def run_http(self, method='B', case='a-login', name='a1', **extra):
        return self.req('/api/customer-data/analyze-case', name,
                        dict(method=method, case_id=case, **extra))

    def test_a_and_b_share_input_and_b_success_does_not_call_baseline(self):
        a = self.run_http('A').json()
        self.sdk.models.generate_content.assert_not_called()
        self.sdk.models.generate_content.return_value.text = json.dumps(self.output())
        with patch.object(experiment, 'run_a', side_effect=AssertionError('B must be independent')):
            response = self.run_http()
        self.assertEqual(response.status_code, 200)
        b = response.json()
        self.assertEqual(a['input_sha256'], b['input_sha256'])
        self.assertEqual(b['status'], 'success')
        self.assertEqual(b['effective_method'], 'B')
        self.assertFalse(b['fallback'])
        self.assertEqual(b['analysis'], self.output())
        self.assertGreaterEqual(b['latency_ms'], 0)
        args = self.sdk.models.generate_content.call_args.kwargs
        self.assertEqual(args['config'].response_mime_type, 'application/json')
        self.assertIsNone(args['config'].tools)
        payload = json.loads(args['contents'])
        self.assertEqual(payload['evidence'], experiment.package_for('a-login'))
        self.assertNotIn('analysis', payload)
        self.sdk.close.assert_called_once()

    def test_company_b_and_empty_evidence_success(self):
        for case, user in [('b-scan', 'b1'), ('a-no-evidence', 'a1'), ('b-no-evidence', 'b1')]:
            self.sdk.models.generate_content.return_value.text = json.dumps(self.output(case))
            result = self.run_http(case=case, name=user).json()
            self.assertEqual(result['status'], 'success')
            self.assertEqual(result['analysis']['risk_level'], self.output(case)['risk_level'])
            self.assertNotIn('a-web-01' if user == 'b1' else 'b-web-01', json.dumps(result))

    def test_authorization_and_arbitrary_payloads_rejected_before_provider(self):
        self.assertEqual(self.run_http(name=None).status_code, 401)
        self.assertEqual(self.run_http(case='b-scan').status_code, 404)
        self.assertEqual(self.run_http(company_id=str(self.companies['B'])).status_code, 403)
        self.assertEqual(self.run_http(name='admin').status_code, 422)
        self.assertEqual(self.run_http(case='not-a-case').status_code, 404)
        for key in ('question', 'evidence', 'history', 'synthetic'):
            self.assertEqual(self.run_http(**{key: 'PRIVATE'}).status_code, 422)
        self.sdk.models.generate_content.assert_not_called()
        self.sdk.models.generate_content.return_value.text = json.dumps(self.output('b-scan'))
        self.assertEqual(self.run_http(case='b-scan', name='support',
            company_id=str(self.companies['B'])).json()['status'], 'success')

    def test_runtime_data_and_private_kb_never_leave(self):
        with self.Session() as db:
            db.query(fixture.CustomerLog).update({'message': 'PRIVATE_CUSTOMER_LOG'})
            db.query(fixture.CustomerAsset).update({'hostname': 'PRIVATE_HOST'})
            db.commit()
        self.sdk.models.generate_content.return_value.text = json.dumps(self.output())
        from services import knowledge_base as kb
        private = dict(kb._catalog()[0], scope='company', company_id=str(experiment.uid('Company A (Demo)')),
                       content='PRIVATE_KB')
        with patch.object(kb, '_catalog', return_value=[private]):
            self.assertEqual(self.run_http().json()['status'], 'success')
        payload = self.sdk.models.generate_content.call_args.kwargs['contents']
        for value in ('PRIVATE_CUSTOMER_LOG', 'PRIVATE_HOST', 'PRIVATE_KB', str(self.companies['A']), str(self.users['a1'])):
            self.assertNotIn(value, payload)

    def test_invalid_claims_ids_risk_and_schema_are_fallback_not_b_success(self):
        mutations = [dict(summary='Confirmed compromise and data theft.'),
            dict(evidence_ids=['foreign-evidence']), dict(risk_level='HIGH'),
            dict(recommended_actions=['MFA already bypassed by attacker']),
            dict(uncertainty=['Foreign host belongs to attacker']), dict(incident_type='ransomware'),
            dict(extra='not allowed'), dict(evidence_ids='wrong type')]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.sdk.models.generate_content.return_value.text = json.dumps({**self.output(), **mutation})
                result = self.run_http().json()
                self.assertEqual(result['method'], 'B')
                self.assertEqual(result['status'], 'fallback')
                self.assertEqual(result['effective_method'], 'A')
                self.assertIsNone(result['analysis'])
                self.assertTrue(result['validation_failures'])
                self.assertIn('fallback_analysis', result)
                self.assertNotIn('Confirmed compromise', json.dumps(result))
        self.sdk.models.generate_content.return_value.text = '{"risk_level":"HIGH","risk_level":"UNKNOWN"}'
        self.assertEqual(self.run_http().json()['validation_failures'], ['schema_invalid'])

    def test_disabled_unavailable_timeout_and_truncation_are_explicit(self):
        with patch.dict(os.environ, {'GEMINI_ENABLED': 'false'}):
            result = self.run_http().json()
        self.assertEqual(result['validation_failures'], ['provider_disabled'])
        self.sdk.models.generate_content.assert_not_called()
        for failure, code in [(TimeoutError('SECRET'), 'provider_timeout'), (RuntimeError('SECRET'), 'provider_unavailable')]:
            self.sdk.models.generate_content.side_effect = failure
            result = self.run_http().json()
            self.assertEqual(result['validation_failures'], [code])
            self.assertNotIn('SECRET', json.dumps(result))
        self.sdk.models.generate_content.side_effect = None
        self.sdk.models.generate_content.return_value.candidates[0].finish_reason = 'MAX_TOKENS'
        self.assertEqual(self.run_http().json()['validation_failures'], ['invalid_finish'])

    def test_deadline_pool_and_context_limits(self):
        from unittest.mock import MagicMock
        future = MagicMock()
        future.result.side_effect = TimeoutError()
        with patch.object(provider._pool, 'submit', return_value=future):
            self.assertEqual(self.run_http().json()['validation_failures'], ['provider_timeout'])
            future.result.assert_called_once_with(timeout=provider.DEADLINE_SECONDS)
            future.add_done_callback.call_args.args[0](future)
        with patch.object(provider._slots, 'acquire', return_value=False):
            self.assertEqual(self.run_http().json()['validation_failures'], ['provider_busy'])
        self.assertEqual(provider.incident_json({'oversized': 'x'*20001}, {})[1], 'context_limit')
