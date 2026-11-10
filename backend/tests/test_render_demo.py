"""Offline deployment contracts. Never connect to Neon or a live provider."""
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, UUID, Numeric
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.autogenerate import compare_metadata
from core.database import Base
import test_gemini_offline as fixture

ROOT = Path(__file__).resolve().parents[1]


class AnswerLogIsolation(unittest.TestCase):
    setUp = fixture.GeminiOffline.setUp
    tearDown = fixture.GeminiOffline.tearDown
    req = fixture.GeminiOffline.req

    def test_inventory_filters_foreign_and_dangling_relations_before_limit(self):
        with patch.dict(os.environ, {'GEMINI_ENABLED': 'false'}):
            for own, other, user in [('A', 'B', 'a1'), ('B', 'A', 'b1')]:
                with self.Session() as db:
                    assets = {c: db.query(fixture.CustomerAsset).filter_by(company_id=self.companies[c]).first().id for c in ('A', 'B')}
                    collectors = {c: db.query(fixture.LogCollector).filter_by(company_id=self.companies[c]).first().id for c in ('A', 'B')}
                    refs = [(assets[other], collectors[own]), (assets[own], collectors[other]),
                            (assets[other], collectors[other]), (uuid4(), collectors[own]), (assets[own], uuid4())]
                    for i in range(25):
                        asset, collector = refs[i % len(refs)]
                        db.add(fixture.CustomerLog(company_id=self.companies[own], asset_id=asset,
                            collector_id=collector, event_type='INVALID', message='FOREIGN_CANARY', occurred_at=datetime(2099, 1, 1)))
                    db.commit()
                for question in ('logs', 'events'):
                    for caller, extra in [(user, {}), ('support', {'company_id': str(self.companies[own])})]:
                        result = self.req('/api/customer-data/ask', caller, {'message': question, **extra})
                        self.assertEqual(result.status_code, 200)
                        self.assertNotIn('FOREIGN_CANARY', result.text)
                        self.assertEqual(result.json()['counts']['logs'], 2)
                    legacy = self.req('/api/chat', user, {'message': question})
                    self.assertEqual(legacy.status_code, 200)
                    self.assertNotIn('FOREIGN_CANARY', legacy.text)
                room = self.req('/api/chat-rooms', user, {}).json()['id']
                result = self.req('/api/chat-rooms/' + room + '/messages', user, {'content': 'logs'})
                self.assertEqual(result.status_code, 200)
                self.assertNotIn('FOREIGN_CANARY', result.text)
            self.sdk.models.generate_content.assert_not_called()


class PublicDemoLogin(unittest.TestCase):
    setUp = fixture.GeminiOffline.setUp
    tearDown = fixture.GeminiOffline.tearDown
    req = fixture.GeminiOffline.req

    def test_login_shell_and_user_list_are_public_even_with_old_gate_settings(self):
        import main
        with tempfile.TemporaryDirectory() as directory:
            static = Path(directory)
            html = '<html><body><div id="root">Demo shell</div></body></html>'
            (static / 'index.html').write_text(html)
            with patch.object(main, 'STATIC_DIR', static), patch.dict(os.environ, {
                    'APP_ENV': 'production', 'RENDER': 'true',
                    'DEMO_ACCESS_USER': 'old-reviewer', 'DEMO_ACCESS_PASSWORD': 'obsolete'}):
                response = self.client.get('/')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.text, html)
                self.assertNotIn('www-authenticate', response.headers)
                users = self.client.get('/api/demo-auth/users')
                self.assertEqual(users.status_code, 200)
                self.assertEqual(len(users.json()), 5)
                self.assertNotIn('obsolete', users.text)
                self.assertNotIn('token', users.text)

    def test_mock_login_preserves_roles_and_session_headers(self):
        invalid = self.client.post('/api/demo-auth/login', json={'user_id': 'not-a-uuid'})
        self.assertEqual(invalid.status_code, 422)
        for name, role in [('a1', 'CUSTOMER'), ('support', 'SUPPORT'), ('admin', 'ADMIN')]:
            with patch.dict(os.environ, {'GEMINI_ENABLED': 'false', 'DEMO_AUTH_MODE': 'mock'}):
                login = self.client.post('/api/demo-auth/login', json={'user_id': str(self.users[name])})
                self.assertEqual(login.status_code, 200, login.text)
                response = login.json()
                me = self.client.get('/api/demo-auth/me', headers={'X-Demo-Authorization': 'Bearer ' + response['token']})
                self.assertEqual(me.status_code, 200)
            login = self.client.post('/api/demo-auth/login', json={
                'user_id': str(self.users[name]), 'password': 'mock-password-fixture-' + name,
            })
            self.assertEqual(login.status_code, 200, login.text)
            response = login.json()
            self.assertEqual(response['user']['role'], role)
            for header in ('Authorization', 'X-Demo-Authorization'):
                me = self.client.get('/api/demo-auth/me',
                    headers={header: 'Bearer ' + response['token']})
                self.assertEqual(me.status_code, 200)
                self.assertEqual(me.json()['id'], str(self.users[name]))
        self.assertEqual(self.req('/api/demo-auth/companies', 'a1').status_code, 403)

    def test_protected_apis_still_require_mock_session_without_basic_challenge(self):
        for path in ('/api/demo-auth/me', '/api/customer-data/assets',
                     '/api/customer-data/logs', '/api/chat-rooms', '/api/tickets'):
            for headers in ({}, {'Authorization': 'Basic b2xkOm9sZA=='},
                            {'X-Demo-Authorization': 'Bearer invalid'}):
                response = self.client.get(path, headers=headers)
                self.assertEqual(response.status_code, 401)
                self.assertNotIn('Basic', response.headers.get('www-authenticate', ''))
        self.sdk.models.generate_content.assert_not_called()


class DeploymentConfiguration(unittest.TestCase):
    def test_hosted_startup_validates_schema_without_create_all(self):
        import main
        with patch.dict(os.environ, {'APP_ENV': 'production', 'DEMO_ACCESS_USER': '',
                'DEMO_ACCESS_PASSWORD': '',
                'DEMO_SESSION_SECRET': 'synthetic-session-secret-at-least-32'}), \
                patch.object(main, 'STATIC_DIR', ROOT.parent / 'frontend/dist'), \
                patch('sqlalchemy.inspect') as inspector, \
                patch.object(Base.metadata, 'create_all', side_effect=AssertionError('No hosted DDL')):
            # StaticFiles startup is separately exercised in the built image.
            with patch.object(Path, 'is_file', return_value=True):
                inspector.return_value.get_table_names.return_value = list(Base.metadata.tables)
                with TestClient(main.app) as client:
                    self.assertEqual(client.get('/healthz').status_code, 200)
                    self.assertEqual(client.head('/healthz').status_code, 200)
                    self.assertEqual(client.get('/openapi.json').status_code, 200)
                inspector.return_value.get_table_names.return_value = []
                with self.assertRaisesRegex(RuntimeError, 'schema is incomplete'):
                    with TestClient(main.app): pass

    def test_health_failure_does_not_disclose_connection_details(self):
        import main
        with patch.object(main.engine, 'connect', side_effect=RuntimeError('PRIVATE_CONNECTION_DETAIL')):
            response = TestClient(main.app).get('/healthz')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('PRIVATE_CONNECTION_DETAIL', response.text)

    def test_hosted_missing_local_or_invalid_url_fails_without_dotenv(self):
        for url in ('', 'postgresql://localhost/demo', 'sqlite://', 'invalid-url'):
            env = {**os.environ, 'RENDER': 'true', 'DATABASE_URL': url, 'PYTHON_DOTENV_DISABLED': '0'}
            result = subprocess.run([sys.executable, '-B', '-c', 'import core.database'], cwd=ROOT,
                                    env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('DATABASE_URL', result.stderr)

    def test_remote_postgres_alias_is_accepted_without_connecting(self):
        for scheme in ('postgres', 'postgresql', 'postgresql+psycopg2'):
            env = {**os.environ, 'RENDER': 'true', 'DATABASE_URL': scheme + '://example.invalid/demo?sslmode=require'}
            result = subprocess.run([sys.executable, '-B', '-c',
                "from core.database import engine; assert engine.url.drivername == 'postgresql+psycopg2'; engine.dispose()",
                ], cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, 'PostgreSQL driver configuration failed')

    def test_additive_migration_matches_models_and_preserves_existing_data(self):
        files = list((ROOT / 'alembic/versions').glob('*.py'))
        modules = []
        for file in sorted(files):
            spec = importlib.util.spec_from_file_location(file.stem, file)
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            modules.append(module)
        engine = create_engine('sqlite://')
        try:
            with engine.begin() as connection:
                # SQLite reflects PostgreSQL's native UUID declaration as NUMERIC;
                # this dialect artifact is not a PostgreSQL schema difference.
                def compare_type(context, inspected, declared, inspected_type, declared_type):
                    if isinstance(declared_type, UUID) and isinstance(inspected_type, Numeric):
                        return False
                    return None
                context = MigrationContext.configure(connection, opts={'compare_type': compare_type})
                with Operations.context(context):
                    modules[0].upgrade()
                    connection.exec_driver_sql("INSERT INTO companies (id, name) VALUES ('00000000000000000000000000000001', 'Preserved synthetic company')")
                    for migration in modules[1:]:
                        migration.upgrade()
                self.assertEqual(len(inspect(connection).get_table_names()), 14)
                self.assertEqual(connection.exec_driver_sql('SELECT name FROM companies').scalar(), 'Preserved synthetic company')
                self.assertEqual(compare_metadata(context, Base.metadata), [])
        finally: engine.dispose()

    def test_postgresql_upgrade_sql_is_additive(self):
        from alembic.config import Config
        from alembic import command
        output = io.StringIO()
        config = Config(str(ROOT / 'alembic.ini'), output_buffer=output)
        # The application engine is intentionally already SQLite/offline. Override
        # only Alembic's URL source for PostgreSQL SQL generation, never connect.
        with patch('core.database.SQLALCHEMY_DATABASE_URL', 'postgresql://example.invalid/demo'):
            command.upgrade(config, '0ca6d68be46d:head', sql=True)
        sql = output.getvalue().upper()
        self.assertEqual(sql.count('CREATE TABLE '), 6)
        self.assertNotIn('DROP TABLE', sql)
        self.assertNotIn('DELETE FROM', sql)
