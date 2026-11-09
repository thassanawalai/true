"""Knowledge-first chat and explicit tenant-scoped analysis, entirely offline."""
import os
import re
import unittest
from unittest.mock import patch
from sqlalchemy import event
from services import security_analysis
import test_gemini_offline as fixture


class ChatUX(unittest.TestCase):
    setUp = fixture.GeminiOffline.setUp
    tearDown = fixture.GeminiOffline.tearDown
    req = fixture.GeminiOffline.req
    ask = fixture.GeminiOffline.ask
    open_room = fixture.GeminiOffline.open_room

    def test_general_questions_never_query_telemetry_or_analyze(self):
        statements = []
        def record(conn, cursor, statement, parameters, context, many):
            statements.append(statement.lower())
        event.listen(self.engine, 'before_cursor_execute', record)
        with patch.dict(os.environ, {'GEMINI_ENABLED': 'false'}), patch.object(
                security_analysis, 'analyze', side_effect=AssertionError('Knowledge must not analyze logs')):
            path = '/api/chat-rooms/' + self.open_room() + '/messages'
            for question in ('phishing คืออะไร', 'MFA ช่วยอย่างไร', 'log หายควรทำอย่างไร', 'suspicious login', 'สวัสดี'):
                result = self.ask(question).json()
                self.assertNotIn('analysis', result)
                self.assertEqual(result['counts']['logs'], 0)
                self.assertNotIn('## Incident Summary', result['answer'])
                self.assertLess(len(result['answer']), 1200)
                self.assertEqual(self.req(path, payload={'content': question}).status_code, 200)
                self.assertEqual(self.req('/api/chat', payload={'message': question}).status_code, 200)
            # A details flag alone must not turn a knowledge question into analysis.
            self.assertNotIn('analysis', self.ask('login', details=True).json())
        for table in ('customer_logs', 'customer_assets', 'log_collectors'):
            self.assertFalse(any(table in statement for statement in statements), table)
        self.sdk.models.generate_content.assert_not_called()

    def test_action_uses_session_tenant_and_rejects_client_scope_and_foreign_rooms(self):
        path = '/api/chat-rooms/' + self.open_room() + '/messages'
        with patch.dict(os.environ, {'GEMINI_ENABLED': 'false'}), patch.object(
                security_analysis, 'analyze', wraps=security_analysis.analyze) as analyze:
            payload = {'content': 'suspicious login', 'action': 'analyze_log'}
            for name in ('a2', 'b1'):
                self.assertEqual(self.req(path, name, payload).status_code, 404)
            self.assertEqual(self.req(path, None, payload).status_code, 401)
            self.assertEqual(self.req(path, payload={**payload, 'company_id': str(self.companies['B'])}).status_code, 422)
            self.assertEqual(self.ask('login', action='analyze_log', company_id=str(self.companies['B'])).status_code, 403)
            analyze.assert_not_called()
            response = self.req(path, payload=payload)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(analyze.call_args.args[2], self.companies['A'])
            text = response.json()['messages'][-1]['content']
            self.assertIn('SUSPICIOUS', text)
            self.assertNotIn('b-web-01', text)
            self.assertNotIn('198.51.100.', text)
            self.assertIn('## สรุปการวิเคราะห์ Log', text)
            response = self.req(path, payload={**payload, 'content': 'port scan b-web-01 198.51.100.10'})
            text = response.json()['messages'][-1]['content']
            self.assertIn('UNKNOWN', text)
            self.assertNotIn('b-web-01', text)
            self.assertNotIn('198.51.100.', text)
            self.assertEqual(analyze.call_args.args[2], self.companies['A'])

    def test_brief_limits_evidence_and_actions_and_details_are_explicit(self):
        with self.Session() as db:
            log = db.query(fixture.CustomerLog).filter_by(company_id=self.companies['A']).first()
            for _ in range(8):
                db.add(fixture.CustomerLog(company_id=log.company_id, asset_id=log.asset_id,
                    collector_id=log.collector_id, event_type='SUSPICIOUS_LOGIN', message='Synthetic details canary'))
            db.commit()
        with patch.dict(os.environ, {'GEMINI_ENABLED': 'false'}):
            result = self.ask('suspicious login', action='analyze_log').json()
            text = result['answer']
            self.assertNotRegex(text, r'[0-9a-f]{8}-[0-9a-f]{4}-')
            self.assertNotRegex(text, r'\d{4}-\d{2}-\d{2}T')
            self.assertNotIn('Synthetic details canary', text)
            evidence = text.split('**หลักฐานที่พบในระบบ:**\n')[1].split('\n\n')[0]
            actions = text.split('**ขั้นตอนถัดไป:**\n')[1].split('\n\n')[0]
            self.assertEqual(len(re.findall(r'^- ', evidence, re.M)), 3)
            self.assertLessEqual(len(re.findall(r'^- ', actions, re.M)), 3)
            self.assertIn('ข้อสันนิษฐาน — ยังไม่ยืนยัน', text)
            detailed = self.ask('suspicious login', action='analyze_log', details=True).json()['answer']
            self.assertIn('Synthetic details canary', detailed)
            self.assertIn('## Missing Information', detailed)

    def test_analysis_survives_ticket_confirmation_and_owner_checks(self):
        path = '/api/chat-rooms/' + self.open_room()
        with patch.dict(os.environ, {'GEMINI_ENABLED': 'false'}):
            self.req(path + '/messages', payload={'content': 'login คืออะไร'})
            response = self.req(path + '/messages', payload={'content': 'suspicious login', 'action': 'analyze_log'})
        answer = response.json()['messages'][-1]['content']
        with self.Session() as db:
            self.assertEqual(db.query(fixture.Ticket).count(), 0)
        self.assertEqual(self.req(path + '/messages', 'support', {'content': 'SOC reviewed'}).status_code, 200)
        linked = self.req(path + '/ticket', payload={'subject': 'Explicit confirmation'}).json()
        history = self.req('/api/chat-rooms/by-ticket/' + linked['ticket_id']).json()
        self.assertIn(answer, [message['content'] for message in history['messages']])
        for user in ('a2', 'b1'):
            self.assertEqual(self.req('/api/chat-rooms/by-ticket/' + linked['ticket_id'], user).status_code, 404)
        self.assertEqual(self.req('/api/tickets/' + linked['ticket_id'], 'b1').status_code, 404)
