"""Local keyword KB and mocked ASGI tests; no live network or PostgreSQL."""
import copy
import json
import unittest
from unittest.mock import patch
from uuid import uuid4
from services import knowledge_base as kb
import test_gemini_offline as fixture


class Retrieval(unittest.TestCase):
    def setUp(self):
        self.a, self.b = uuid4(), uuid4()

    def test_reviewed_catalog_shape_and_sources(self):
        docs = kb._catalog()
        self.assertEqual(len(docs), 10)
        self.assertEqual(len({d['id'] for d in docs}), 10)
        self.assertEqual(len(kb.public_context(docs)), 10)
        for d in docs:
            self.assertTrue(d['source']['url'].startswith('https://'))
            self.assertTrue(d['review']['method'])
            self.assertTrue(d['tags'])

    def test_relevance_in_thai_and_english(self):
        expected = [('suspicious login', 'KB-001'), ('อีเมลฟิชชิง', 'KB-003'),
                    ('SIEM alert', 'KB-004'), ('incident response', 'KB-005'),
                    ('ransomware', 'KB-006'), ('port scan', 'KB-007'),
                    ('log หาย', 'KB-008'), ('สำรองข้อมูล', 'KB-009')]
        for question, doc_id in expected:
            with self.subTest(question=question):
                self.assertEqual(kb.retrieve(question, self.a)[0]['id'], doc_id)

    def test_no_match_and_ascii_boundaries(self):
        self.assertEqual(kb.retrieve('ขอสูตรทำอาหาร', self.a), [])
        self.assertEqual(kb.retrieve('catalog collection tokenized scanning', self.a), [])
        self.assertIn('หลักฐานไม่เพียงพอ', kb.render([]))
        self.assertFalse(kb.matches('phishing', 'ip'))

    def test_scope_is_filtered_before_scoring_and_top_k(self):
        public = copy.deepcopy(kb._catalog()[0]); public['tags'] = ['login']
        a = dict(public, id='KB-901', scope='company', company_id=str(self.a), content='A_PRIVATE')
        b = dict(public, id='KB-902', scope='company', company_id=str(self.b), tags=['B_SECRET_TAG'], content='B_PRIVATE')
        unknown = dict(b, id='KB-903', scope='unknown', tags=['UNKNOWN_SCOPE'])
        with patch.object(kb, 'matches', wraps=kb.matches) as score:
            result = kb.retrieve('login B_SECRET_TAG UNKNOWN_SCOPE', self.a, documents=[b, unknown, a, public])
        self.assertEqual({d['id'] for d in result}, {'KB-001', 'KB-901'})
        self.assertNotIn('B_SECRET_TAG', [call.args[1] for call in score.call_args_list])
        self.assertNotIn('UNKNOWN_SCOPE', [call.args[1] for call in score.call_args_list])
        self.assertNotIn('A_PRIVATE', json.dumps(kb.retrieve('login', self.b, documents=[a, public])))
        with self.assertRaises(ValueError): kb.retrieve('login', None)

    def test_only_exact_reviewed_public_text_can_leave_backend(self):
        public = copy.deepcopy(kb._catalog()[0])
        private = dict(public, scope='company', company_id=str(self.a), content='PRIVATE_CANARY')
        tampered = dict(public, content='Injected unpublished content')
        self.assertEqual(kb.public_context([private, tampered]), [])
        self.assertEqual(kb.public_context([public])[0]['content'], public['content'])
        self.assertNotIn('source', kb.public_context([public])[0])

    def test_results_are_bounded_and_do_not_mutate_catalog(self):
        result = kb.retrieve('login mfa phishing incident ransomware siem backup', self.a)
        self.assertEqual(len(result), kb.MAX_RESULTS)
        result[0]['content'] = 'MUTATION'
        self.assertNotIn('MUTATION', json.dumps(kb._catalog()))


class KnowledgeAPI(unittest.TestCase):
    setUp = fixture.GeminiOffline.setUp
    tearDown = fixture.GeminiOffline.tearDown
    req = fixture.GeminiOffline.req
    ask = fixture.GeminiOffline.ask
    open_room = fixture.GeminiOffline.open_room

    def test_unauthorized_company_rejected_before_retrieval(self):
        with patch.object(kb, 'retrieve', wraps=kb.retrieve) as retrieval:
            self.assertEqual(self.ask('phishing', company_id=str(self.companies['B'])).status_code, 403)
            self.assertEqual(self.ask('phishing', name=None).status_code, 401)
            self.assertEqual(self.ask('phishing', name='admin').status_code, 422)
            retrieval.assert_not_called()
        self.sdk.models.generate_content.assert_not_called()

    def test_public_kb_context_and_server_citations(self):
        result = self.ask('phishing Bearer RAW_SECRET_CANARY').json()
        self.assertEqual(result['retrieval'], 'keyword_tag')
        self.assertEqual(result['kb_status'], 'matched')
        self.assertEqual(result['citations'][0]['id'], 'KB-003')
        self.assertIn('[KB-003]', result['answer'])
        self.assertIn(result['citations'][0]['source']['url'], result['answer'])
        context = json.loads(self.sdk.models.generate_content.call_args.kwargs['contents'])
        self.assertEqual(context['public_knowledge'][0]['id'], 'KB-003')
        self.assertNotIn('RAW_SECRET_CANARY', json.dumps(context))

    def test_private_kb_local_only_and_cross_tenant_hidden(self):
        public = copy.deepcopy(kb._catalog()[2])
        a = dict(public, id='KB-901', scope='company', company_id=str(self.companies['A']), content='A_PRIVATE_CANARY')
        b = dict(public, id='KB-902', scope='company', company_id=str(self.companies['B']), content='B_PRIVATE_CANARY')
        with patch.object(kb, '_catalog', return_value=[a, b]):
            for user, own, other in [('a1', 'A_PRIVATE_CANARY', 'B_PRIVATE_CANARY'), ('b1', 'B_PRIVATE_CANARY', 'A_PRIVATE_CANARY')]:
                result = self.ask('phishing', name=user).json()
                self.assertIn(own, result['answer']); self.assertNotIn(other, json.dumps(result))
                payload = self.sdk.models.generate_content.call_args.kwargs['contents']
                self.assertNotIn(own, payload); self.assertNotIn(other, payload)
                self.assertEqual(json.loads(payload)['public_knowledge'], [])
            result = self.ask('phishing', name='support', company_id=str(self.companies['B'])).json()
            self.assertIn('B_PRIVATE_CANARY', result['answer']); self.assertNotIn('A_PRIVATE_CANARY', json.dumps(result))

    def test_disabled_and_failed_ai_have_thai_fallback_and_citations(self):
        with patch.dict(fixture.os.environ, {'GEMINI_ENABLED': 'false'}):
            result = self.ask('phishing').json()
        self.assertEqual(result['mode'], 'rule_based_demo')
        self.assertIn('ขณะนี้ไม่ได้ใช้ AI', result['answer'])
        self.assertEqual(result['citations'][0]['id'], 'KB-003')
        self.sdk.models.generate_content.assert_not_called()
        self.sdk.models.generate_content.side_effect = TimeoutError('SENSITIVE_ERROR')
        result = self.ask('phishing').json()
        self.assertIn('AI ไม่พร้อมใช้งาน', result['answer']); self.assertIn('[KB-003]', result['answer'])
        self.assertNotIn('SENSITIVE_ERROR', result['answer'])

    def test_no_match_and_empty_telemetry_do_not_invent_citations(self):
        with self.Session() as db:
            db.query(fixture.CustomerLog).delete(); db.commit()
        with patch.dict(fixture.os.environ, {'GEMINI_ENABLED': 'false'}):
            result = self.ask('ขอสูตรทำอาหาร').json()
        self.assertEqual(result['citations'], []); self.assertEqual(result['kb_status'], 'no_match')
        self.assertIn('หลักฐานไม่เพียงพอ', result['answer'])
        self.assertIn('การไม่มีข้อมูลไม่ยืนยันว่าระบบปลอดภัย', result['answer'])

    def test_provider_cannot_invent_kb_ids_or_links(self):
        for text in ('ตรวจสอบตามเอกสาร KB-999 ซึ่งไม่ได้มีอยู่จริง', 'ตรวจสอบคำแนะนำที่ https://invented.invalid ก่อนดำเนินการ'):
            self.sdk.models.generate_content.return_value.text = text
            result = self.ask('phishing').json()
            self.assertEqual(result['mode'], 'rule_based_demo')
            self.assertNotIn('KB-999', result['answer']); self.assertNotIn('invented.invalid', result['answer'])

    def test_citations_survive_private_chat_ticket_and_soc_reply(self):
        room = self.open_room(); path = '/api/chat-rooms/' + room
        reply = self.req(path + '/messages', payload={'content': 'phishing'}).json()
        self.assertIn('[KB-003]', reply['messages'][-1]['content'])
        self.assertEqual(self.req(path + '/messages', 'support', {'content': 'SOC reviewed mock evidence'}).status_code, 200)
        linked = self.req(path + '/ticket', payload={'subject': 'Synthetic KB evidence'}).json()
        history = self.req('/api/chat-rooms/by-ticket/' + linked['ticket_id']).json()
        self.assertIn('[KB-003]', json.dumps(history))
        for user in ('a2', 'b1'):
            self.assertEqual(self.req('/api/chat-rooms/by-ticket/' + linked['ticket_id'], user).status_code, 404)

    def test_support_ticket_permissions_remain_unchanged(self):
        room = self.open_room()
        path = '/api/chat-rooms/' + room
        self.req(path + '/messages', payload={'content': 'SIEM alert'})
        linked = self.req(path + '/ticket', payload={'subject': 'Synthetic support regression'}).json()
        ticket = '/api/tickets/' + linked['ticket_id']
        self.assertEqual(self.req(ticket, 'a2').status_code, 200)
        self.assertEqual(self.req(ticket, 'b1').status_code, 404)
        self.assertEqual(self.req(ticket + '/status', 'a1', {'status': 'RESOLVED'}, 'PATCH').status_code, 403)
        assigned = self.req(ticket + '/assign', 'support', {'assignee_id': str(self.users['support'])}, 'PATCH')
        self.assertEqual(assigned.status_code, 200)
        self.assertEqual(assigned.json()['new_status'], 'IN_PROGRESS')
        resolved = self.req(ticket + '/status', 'support', {'status': 'RESOLVED'}, 'PATCH')
        self.assertEqual(resolved.status_code, 200)
        self.assertEqual(self.req(ticket, 'a2').json()['status'], 'RESOLVED')

    def test_public_retrieval_and_exact_citations_for_both_companies(self):
        document = next(d for d in kb._catalog() if d['id'] == 'KB-003')
        expected = [{'id': document['id'], 'title': document['title'], 'source': document['source']}]
        for user in ('a1', 'b1'):
            with self.subTest(user=user):
                result = self.ask('phishing', name=user).json()
                self.assertEqual(result['citations'], expected)
                self.assertIn(document['content'], result['answer'])
                self.assertIn(document['source']['url'], result['answer'])
                self.assertEqual(result['answer'].count('[KB-003]'), 1)

    def test_no_match_with_enabled_ai_keeps_empty_citations_and_context(self):
        result = self.ask('ขอสูตรทำอาหาร').json()
        self.assertEqual(result['kb_status'], 'no_match')
        self.assertEqual(result['citations'], [])
        self.assertIn('หลักฐานไม่เพียงพอ', result['answer'])
        context = json.loads(self.sdk.models.generate_content.call_args.kwargs['contents'])
        self.assertEqual(context['public_knowledge'], [])
        self.assertNotIn('ขอสูตรทำอาหาร', json.dumps(context, ensure_ascii=False))

    def test_private_chat_history_remains_projected_with_public_kb(self):
        path = '/api/chat-rooms/' + self.open_room() + '/messages'
        self.assertEqual(self.req(path, payload={'content': 'login TRANSCRIPT_CANARY'}).status_code, 200)
        self.assertEqual(self.req(path, payload={'content': 'phishing QUESTION_CANARY'}).status_code, 200)
        payload = self.sdk.models.generate_content.call_args.kwargs['contents']
        context = json.loads(payload)
        self.assertTrue(context['recent_topics'])
        self.assertEqual(context['public_knowledge'][0]['id'], 'KB-003')
        for forbidden in ('TRANSCRIPT_CANARY', 'QUESTION_CANARY', '198.51.100.10', 'b-web-01',
                          str(self.users['a1']), str(self.companies['A'])):
            self.assertNotIn(forbidden, payload)
        self.assertLessEqual(len(payload), fixture.provider.MAX_CONTEXT_CHARS)

    def test_citation_text_persisted_in_orm_after_temporary_store_cleared(self):
        from models.chat import RoomMessage
        path = '/api/chat-rooms/' + self.open_room()
        reply = self.req(path + '/messages', payload={'content': 'phishing'}).json()
        original = reply['messages'][-1]['content']
        linked = self.req(path + '/ticket', payload={'subject': 'Citation persistence fixture'}).json()
        with self.Session() as db:
            stored = db.query(RoomMessage).filter(RoomMessage.role == 'assistant').one()
            self.assertEqual(stored.content, original)
        with fixture.live.lock:
            fixture.live.rooms.clear()
        history = self.req('/api/chat-rooms/by-ticket/' + linked['ticket_id']).json()
        self.assertEqual(next(m['content'] for m in history['messages'] if m['role'] == 'assistant'), original)
        self.assertIn('https://www.ncsc.gov.uk/collection/phishing-scams/spot-scams', original)

    def test_private_citation_metadata_never_appears_for_other_company(self):
        private = dict(copy.deepcopy(kb._catalog()[2]), id='KB-901', scope='company',
                       company_id=str(self.companies['A']), title='PRIVATE_TITLE_CANARY',
                       source={'title': 'PRIVATE_SOURCE_CANARY', 'url': 'https://private-source.invalid/'})
        with patch.object(kb, '_catalog', return_value=[private]):
            owner = self.ask('phishing').json()
            other = self.ask('phishing', name='b1').json()
        self.assertEqual(owner['citations'][0]['source'], private['source'])
        self.assertEqual(other['citations'], [])
        for secret in ('KB-901', 'PRIVATE_TITLE_CANARY', 'PRIVATE_SOURCE_CANARY', 'private-source.invalid'):
            self.assertNotIn(secret, json.dumps(other))
