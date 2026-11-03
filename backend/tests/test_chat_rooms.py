"""Live HTTP security regressions plus deterministic TTL/rollback checks.
Uses isolated test companies/users; only these fixtures are removed.
"""
import base64
import hashlib
import hmac
import json
import os
import time
import unittest
from unittest.mock import patch
from uuid import uuid4
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from fastapi import HTTPException
from core.database import SessionLocal
from core.demo_auth import issue_token
from models.models import Company, User, RoleEnum, Ticket
from models.chat import ChatRoom, RoomMessage
from services import temporary_chat as live
from routers import chat_rooms


class ChatAPI(unittest.TestCase):
    @classmethod
    def request(cls, path='', token=None, data=None, method=None):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        request = Request('http://127.0.0.1:8000/api' + path, headers=headers,
                          data=json.dumps(data).encode() if data is not None else None, method=method)
        try:
            with urlopen(request, timeout=15) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)

    @classmethod
    def setUpClass(cls):
        cls.marker = 'phase3-' + uuid4().hex
        cls.users, cls.tokens = {}, {}
        with SessionLocal() as db:
            a, b = Company(name=cls.marker + '-A'), Company(name=cls.marker + '-B')
            db.add_all([a, b]); db.flush()
            cls.companies = [a.id, b.id]
            for name, company, role in [('a1', a, RoleEnum.CUSTOMER), ('a2', a, RoleEnum.CUSTOMER),
                                        ('b1', b, RoleEnum.CUSTOMER), ('admin', a, RoleEnum.ADMIN),
                                        ('support', a, RoleEnum.SUPPORT)]:
                user = User(company_id=company.id, full_name=cls.marker + name,
                            email=cls.marker + name + '@example.test', role=role)
                db.add(user); db.flush()
                cls.users[name] = {'id': user.id, 'company_id': company.id}
                cls.tokens[name] = issue_token(user)
            db.commit()

    def tearDown(self):
        for name in ('a1', 'a2', 'b1'):
            status, rooms = self.request('/chat-rooms', self.tokens[name])
            if status == 200:
                for room in rooms:
                    if room['temporary']:
                        self.request('/chat-rooms/' + room['id'], self.tokens[name], method='DELETE')
        with SessionLocal() as db:
            for room in db.query(ChatRoom).filter(ChatRoom.company_id.in_(self.companies)).all():
                db.delete(room)
            db.flush()
            for ticket in db.query(Ticket).filter(Ticket.company_id.in_(self.companies)).all():
                db.delete(ticket)
            db.commit()
        with live.lock:
            for key in list(live.rooms):
                if live.rooms[key]['company_id'] in self.companies:
                    del live.rooms[key]

    @classmethod
    def tearDownClass(cls):
        with SessionLocal() as db:
            db.query(User).filter(User.id.in_([u['id'] for u in cls.users.values()])).delete(synchronize_session=False)
            db.query(Company).filter(Company.id.in_(cls.companies)).delete(synchronize_session=False)
            db.commit()

    def open(self, name='a1'):
        status, room = self.request('/chat-rooms', self.tokens[name], {}, 'POST')
        self.assertEqual(status, 200)
        return room

    def send(self, room, name='a1', content='assets'):
        return self.request('/chat-rooms/' + room['id'] + '/messages', self.tokens[name], {'content': content})

    def test_live_private_isolation_soc_and_no_durable_history(self):
        a = self.open(); a2 = self.open('a2'); b = self.open('b1')
        self.assertNotEqual(a['id'], a2['id'])
        for role in ('admin', 'support'):
            self.assertEqual(self.send(a, role, 'early reply')[0], 409)
        status, a = self.send(a, content='private text ' + self.marker)
        self.assertEqual(status, 200)
        self.assertEqual([m['role'] for m in a['messages']], ['customer', 'assistant'])
        for name in ('a2', 'b1'):
            self.assertEqual(self.request('/chat-rooms/' + a['id'], self.tokens[name])[0], 404)
            self.assertEqual(self.send(a, name)[0], 404)
            self.assertEqual(self.request('/chat-rooms/' + a['id'] + '/ticket', self.tokens[name], {'subject': 'steal'})[0], 404)
            self.assertEqual(self.request('/chat-rooms/' + a['id'], self.tokens[name], method='DELETE')[0], 404)
            _, rooms = self.request('/chat-rooms', self.tokens[name])
            self.assertNotIn(a['id'], [r['id'] for r in rooms])
        self.assertEqual(self.request('/chat-rooms?company_id=' + str(self.users['b1']['company_id']), self.tokens['a1'])[0], 403)
        for role in ('admin', 'support'):
            status, rooms = self.request('/chat-rooms', self.tokens[role])
            self.assertEqual(status, 200)
            self.assertTrue({a['id'], a2['id'], b['id']} <= {r['id'] for r in rooms})
            _, rooms = self.request('/chat-rooms?company_id=' + str(self.users['a1']['company_id']), self.tokens[role])
            self.assertNotIn(b['id'], [r['id'] for r in rooms])
            status, replied = self.send(a, role, 'SOC reply ' + role)
            self.assertEqual(status, 200)
            self.assertEqual(replied['messages'][-1]['role'], 'support')
            self.assertEqual(replied['messages'][-1]['sender_id'], str(self.users[role]['id']))
        _, refreshed = self.request('/chat-rooms/' + a['id'], self.tokens['a1'])
        self.assertEqual(refreshed['messages'][-1]['content'], 'SOC reply support')
        self.assertEqual(self.open()['id'], a['id'])  # reconnect, including refresh
        with SessionLocal() as db:
            self.assertEqual(db.query(ChatRoom).filter(ChatRoom.company_id.in_(self.companies)).count(), 0)
            self.assertEqual(db.query(Ticket).filter(Ticket.company_id.in_(self.companies)).count(), 0)
            self.assertEqual(db.query(RoomMessage).filter(RoomMessage.content.like('%' + self.marker + '%')).count(), 0)

    def test_ticket_promotion_history_privacy_and_explicit_confirmation(self):
        a = self.open()
        self.assertEqual(self.request('/chat-rooms/' + a['id'] + '/ticket', self.tokens['a1'], {'subject': 'before AI'})[0], 409)
        _, a = self.send(a, content='secret assets ' + self.marker)
        self.send(a, 'support', 'SOC guidance')
        self.assertEqual(self.request('/chat-rooms/' + a['id'] + '/ticket', self.tokens['admin'], {'subject': 'staff cannot confirm'})[0], 403)
        status, linked = self.request('/chat-rooms/' + a['id'] + '/ticket', self.tokens['a1'], {'subject': self.marker})
        self.assertEqual(status, 200)
        self.assertFalse(linked['temporary'])
        self.assertEqual(len(linked['messages']), 3)
        _, retry = self.request('/chat-rooms/' + a['id'] + '/ticket', self.tokens['a1'], {'subject': 'retry'})
        self.assertEqual(retry['ticket_id'], linked['ticket_id'])
        for name in ('a1', 'admin', 'support'):
            status, history = self.request('/chat-rooms/by-ticket/' + linked['ticket_id'], self.tokens[name])
            self.assertEqual(status, 200)
            self.assertEqual(history['messages'], linked['messages'])
        for name in ('a2', 'b1'):
            self.assertEqual(self.request('/chat-rooms/' + a['id'], self.tokens[name])[0], 404)
            self.assertEqual(self.request('/chat-rooms/by-ticket/' + linked['ticket_id'], self.tokens[name])[0], 404)
            self.assertEqual(self.send(a, name)[0], 404)
        status, metadata = self.request('/tickets/' + linked['ticket_id'], self.tokens['a2'])
        self.assertEqual(status, 200)  # shared ticket metadata, private transcript
        self.assertNotIn('secret assets', metadata['description'])
        self.assertEqual(self.send(a, 'support', 'Saved reply')[0], 200)
        self.assertEqual(self.send(a, 'a1', 'collectors')[0], 200)
        _, refreshed = self.request('/chat-rooms/by-ticket/' + linked['ticket_id'], self.tokens['a1'])
        self.assertEqual(len(refreshed['messages']), 6)
        with SessionLocal() as db:
            self.assertEqual(db.query(ChatRoom).filter(ChatRoom.company_id.in_(self.companies)).count(), 1)
            self.assertEqual(db.query(Ticket).filter(Ticket.company_id.in_(self.companies)).count(), 1)
            self.assertEqual(len(db.get(ChatRoom, a['id']).messages), 6)
        self.assertNotEqual(self.open()['id'], a['id'])  # next conversation is independent

    def test_all_endpoints_reject_missing_and_expired_sessions(self):
        a = self.open()
        body = base64.urlsafe_b64encode(json.dumps({'uid': str(self.users['a1']['id']), 'exp': int(time.time()) - 5}).encode()).rstrip(b'=').decode()
        expired = body + '.' + hmac.new(os.environ['DEMO_SESSION_SECRET'].encode(), body.encode(), hashlib.sha256).hexdigest()
        for token in (None, expired):
            for path, data, method in [('/chat-rooms', None, 'GET'), ('/chat-rooms', {}, 'POST'),
                ('/chat-rooms/' + a['id'], None, 'GET'), ('/chat-rooms/' + a['id'], None, 'DELETE'),
                ('/chat-rooms/' + a['id'] + '/messages', {'content': 'test'}, 'POST'),
                ('/chat-rooms/' + a['id'] + '/ticket', {'subject': 'test'}, 'POST'),
                ('/chat-rooms/by-ticket/' + str(uuid4()), None, 'GET')]:
                self.assertEqual(self.request(path, token, data, method)[0], 401)

    def test_untrusted_message_fields_and_blank_content(self):
        a = self.open()
        for data in ({'content': 'x', 'role': 'assistant'}, {'content': 'x', 'company_id': str(self.users['b1']['company_id'])}, {'content': '   '}):
            self.assertEqual(self.request('/chat-rooms/' + a['id'] + '/messages', self.tokens['a1'], data)[0], 422)
        self.assertEqual(self.request('/chat-rooms', self.tokens['admin'], {})[0], 403)

    def test_ttl_and_backend_restart_are_non_durable(self):
        # Exercise the same handlers/store in this process to control time without
        # exposing test-only expiry controls over HTTP or waiting 30 minutes.
        with SessionLocal() as db:
            owner = db.get(User, self.users['a1']['id'])
            with patch.object(live, 'TTL_SECONDS', 10):
                with patch('services.temporary_chat.monotonic', return_value=100), patch('routers.chat_rooms.monotonic', return_value=100):
                    a = chat_rooms.open_room(db, owner)
                    chat_rooms.send_message(a['id'], chat_rooms.MessageInput(content='assets'), db, owner)
                with patch('services.temporary_chat.monotonic', return_value=109):
                    chat_rooms.read_room(a['id'], db, owner)  # reads do not extend TTL
                with patch('services.temporary_chat.monotonic', return_value=111):
                    with self.assertRaises(HTTPException) as error:
                        chat_rooms.read_room(a['id'], db, owner)
                    self.assertEqual(error.exception.status_code, 404)
            a = chat_rooms.open_room(db, owner)
            with live.lock:
                live.rooms.clear()  # process-memory loss on restart
            with self.assertRaises(HTTPException):
                chat_rooms.read_room(a['id'], db, owner)
            self.assertEqual(db.query(ChatRoom).filter(ChatRoom.company_id.in_(self.companies)).count(), 0)

    def test_failed_history_save_rolls_back_ticket_and_keeps_live_chat(self):
        with SessionLocal() as db:
            owner = db.get(User, self.users['a1']['id'])
            a = chat_rooms.open_room(db, owner)
            chat_rooms.send_message(a['id'], chat_rooms.MessageInput(content='assets'), db, owner)
            with patch.object(db, 'commit', side_effect=RuntimeError('simulate commit failure')):
                with self.assertRaises(HTTPException):
                    chat_rooms.link_ticket(a['id'], chat_rooms.LinkInput(subject=self.marker), db, owner)
            self.assertEqual(db.query(Ticket).filter(Ticket.company_id.in_(self.companies)).count(), 0)
            self.assertEqual(db.query(ChatRoom).filter(ChatRoom.company_id.in_(self.companies)).count(), 0)
            self.assertEqual(len(live.rooms[a['id']]['messages']), 2)

    def test_capacity_and_saved_history_after_memory_loss(self):
        with SessionLocal() as db:
            owner = db.get(User, self.users['a1']['id'])
            agent = db.get(User, self.users['support']['id'])
            with patch.object(live, 'MAX_ROOMS', 0):
                with self.assertRaises(HTTPException) as error:
                    chat_rooms.open_room(db, owner)
                self.assertEqual(error.exception.status_code, 503)
            room = chat_rooms.open_room(db, owner)
            with patch.object(live, 'MAX_MESSAGES', 2):
                chat_rooms.send_message(room['id'], chat_rooms.MessageInput(content='assets'), db, owner)
                with self.assertRaises(HTTPException) as error:
                    chat_rooms.send_message(room['id'], chat_rooms.MessageInput(content='SOC overflow'), db, agent)
                self.assertEqual(error.exception.status_code, 409)
                self.assertEqual(len(live.rooms[room['id']]['messages']), 2)
            saved = chat_rooms.link_ticket(room['id'], chat_rooms.LinkInput(subject=self.marker), db, owner)
            self.assertNotIn(room['id'], live.rooms)
            ticket_id = saved['ticket_id']
            with live.lock:
                live.rooms.clear()
        with SessionLocal() as db:
            owner = db.get(User, self.users['a1']['id'])
            saved = chat_rooms.ticket_history(ticket_id, db, owner)
            self.assertFalse(saved['temporary'])
            self.assertEqual(len(saved['messages']), 2)
