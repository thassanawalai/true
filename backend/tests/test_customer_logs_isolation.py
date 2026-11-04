"""Raw-log regressions using isolated synthetic SQLite; no live DB or AI."""
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import test_gemini_offline as fixture


class RawLogsIsolation(unittest.TestCase):
    setUp = fixture.GeminiOffline.setUp
    tearDown = fixture.GeminiOffline.tearDown
    req = fixture.GeminiOffline.req

    def test_valid_rows_keep_shape_order_limit_and_company_scope(self):
        with self.Session() as db:
            original = db.query(fixture.CustomerLog).filter(
                fixture.CustomerLog.company_id == self.companies['A']).first()
            asset, collector = original.asset_id, original.collector_id
            db.query(fixture.CustomerLog).filter(
                fixture.CustomerLog.company_id == self.companies['A']).delete()
            for i in range(105):
                db.add(fixture.CustomerLog(company_id=self.companies['A'], asset_id=asset,
                    collector_id=collector, event_type='VALID', message=f'synthetic-{i}',
                    occurred_at=datetime(2026, 1, 1) + timedelta(minutes=i)))
            db.commit()
        response = self.req('/api/customer-data/logs')
        self.assertEqual(response.status_code, 200)
        rows = response.json()
        self.assertEqual(len(rows), 100)
        self.assertEqual([r['message'] for r in rows], [f'synthetic-{i}' for i in range(104, 4, -1)])
        self.assertEqual(set(rows[0]), {'id', 'asset_id', 'collector_id', 'event_type', 'message', 'occurred_at'})
        self.assertTrue(all(r['asset_id'] == str(asset) and r['collector_id'] == str(collector) for r in rows))
        self.assertEqual(len(self.req('/api/customer-data/logs', 'b1').json()), 2)
        self.sdk.models.generate_content.assert_not_called()

    def test_malformed_foreign_and_missing_references_are_excluded_before_limit(self):
        for own, other, customer in [('A', 'B', 'a1'), ('B', 'A', 'b1')]:
            with self.subTest(company=own):
                with self.Session() as db:
                    assets = {c: db.query(fixture.CustomerAsset).filter(
                        fixture.CustomerAsset.company_id == self.companies[c]).first().id for c in ('A', 'B')}
                    collectors = {c: db.query(fixture.LogCollector).filter(
                        fixture.LogCollector.company_id == self.companies[c]).first().id for c in ('A', 'B')}
                    valid_ids = {str(r.id) for r in db.query(fixture.CustomerLog).filter(
                        fixture.CustomerLog.company_id == self.companies[own]).all()}
                    refs = [(assets[other], collectors[own]), (assets[own], collectors[other]),
                            (assets[other], collectors[other]), (uuid4(), collectors[own]),
                            (assets[own], uuid4())]
                    # More than 100 newer malformed rows must not hide valid ones.
                    for i in range(105):
                        asset, collector = refs[i % len(refs)]
                        db.add(fixture.CustomerLog(company_id=self.companies[own], asset_id=asset,
                            collector_id=collector, event_type='INVALID', message='FOREIGN_REFERENCE_CANARY',
                            occurred_at=datetime(2099, 1, 1)))
                    # The log's own tenant must also be checked, even when both refs match.
                    db.add(fixture.CustomerLog(company_id=self.companies[other], asset_id=assets[own],
                        collector_id=collectors[own], event_type='INVALID', message='FOREIGN_LOG_CANARY'))
                    db.commit()
                for name, suffix in [(customer, ''), ('admin', '?company_id=' + str(self.companies[own])),
                                     ('support', '?company_id=' + str(self.companies[own]))]:
                    response = self.req('/api/customer-data/logs' + suffix, name)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual({r['id'] for r in response.json()}, valid_ids)
                    self.assertNotIn('CANARY', response.text)
                    self.assertNotIn(str(assets[other]), response.text)
                    self.assertNotIn(str(collectors[other]), response.text)
                # Remove only this in-memory test's malformed records before reversing tenants.
                with self.Session() as db:
                    db.query(fixture.CustomerLog).filter(fixture.CustomerLog.event_type == 'INVALID').delete()
                    db.commit()

    def test_authorization_and_empty_results_unchanged(self):
        path = '/api/customer-data/logs'
        self.assertEqual(self.req(path, None).status_code, 401)
        self.assertEqual(self.req(path, 'admin').status_code, 422)
        for own, other in [('a1', 'B'), ('b1', 'A')]:
            self.assertEqual(self.req(path + '?company_id=' + str(self.companies[other]), own).status_code, 403)
        with self.Session() as db:
            db.query(fixture.CustomerLog).delete(); db.commit()
        response = self.req(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])
        self.sdk.models.generate_content.assert_not_called()


class ComposeCredentialConfiguration(unittest.TestCase):
    def test_password_and_backend_url_are_required_environment_references(self):
        compose = (Path(__file__).resolve().parents[1] / 'docker-compose.yml').read_text()
        settings = dict(line.strip().split(': ', 1) for line in compose.splitlines()
                        if line.strip().startswith(('POSTGRES_PASSWORD:', 'DATABASE_URL:')))
        self.assertEqual(set(settings), {'POSTGRES_PASSWORD', 'DATABASE_URL'})
        self.assertRegex(settings['POSTGRES_PASSWORD'], r'^\$\{POSTGRES_PASSWORD:\?[^}]+\}$')
        self.assertRegex(settings['DATABASE_URL'], r'^\$\{COMPOSE_DATABASE_URL:\?[^}]+\}$')
        self.assertNotRegex(compose, r'postgres(?:ql)?(?:\+\w+)?://[^\s:]+:[^\s@]+@')
