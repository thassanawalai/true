# Phase A recovery — synthetic PostgreSQL demo

Verified 3 November 2026, 22:26 Asia/Bangkok. Submission deadline: 9 November 2026.
Database recovery authorization was explicitly provided by the user. Phase C was not started.

## Preflight and preservation

Branch remained `feature/ai-kb-phase-ab`. All existing uncommitted files were preserved.
The configured DATABASE_URL was inspected in memory without printing credentials or the full URL.
The target is native local PostgreSQL 16/main on 5432, not a remote/production system.
Both the intended application role and database were confirmed absent immediately before creation.
Only the default non-template database `postgres` existed. The application .env was Git-ignored,
private to its owner, contained a password and a sufficiently long demo session secret; no process
DATABASE_URL override was present. Non-system target identifiers were validated.

Reviewed before execution: main.py, core/database.py, demo_auth, current ORM models,
seed_phase1.py, seed_customer_data.py, core/demo_telemetry.py and ticket_service.py.
The selected initialization/seed path uses SQLAlchemy create_all and inserts missing synthetic
fixtures. It has no drop/truncate/delete, Alembic migration or external-service call.
Legacy seed.py, Docker provisioning and vector ingestion were not run.

## Provisioning and credential handling

Created only the previously missing configured application role and database.
Role: LOGIN, NOSUPERUSER, NOCREATEDB, NOCREATEROLE, NOINHERIT, NOREPLICATION, NOBYPASSRLS.
Database: owned by the new role, UTF8, created from template0. PUBLIC access was revoked on
this new database only. Existing databases/roles/HBA configuration and superuser password were unchanged.

Used the existing backend .env credential without modifying the file. A SCRAM-SHA-256 verifier was
computed in memory (printable ASCII credential, unchanged by SASLprep) and submitted over psql stdin;
no plaintext password, verifier, session token or API key was printed or placed in command arguments.
The initial libpq encryption helper attempt required a connection and failed before issuing CREATE
statements; absence was checked again before the successful provisioning path. Configured credential
connectivity subsequently passed, confirming that the stored verifier authenticates correctly.

Imported the current application's models and used its existing Base.metadata.create_all process.
This created 13 tables with no migrations or schema changes to application code. Then ran the reviewed
Phase 1 and telemetry seed scripts. No existing data was deleted, overwritten or restored.

## Seed and final database state

| Entity | After seed | After smoke verification |
| --- | ---: | ---: |
| Companies | 3 | 3 |
| Demo users | 5 | 5 |
| Assets | 4 | 4 |
| Collectors | 2 | 2 |
| Logs | 4 | 4 |
| Tickets | 0 | 1 |
| Durable chat rooms | 0 | 1 |
| Room messages | 0 | 3 |
| Ticket categories | 0 | 1 |
| SLA policies | 0 | 1 |

Companies: Company A (Demo), Company B (Demo), Internal SOC (Demo).
Users: Customer A1, Customer A2, Customer B1, SOC Support and SOC Admin; all use @example.test.
A uses 192.0.2.10/20; B uses 198.51.100.10/20, with separate synthetic collectors and events.

One deliberately retained ticket is labelled `SYNTHETIC DEMO: Phase A recovery verification`,
status RESOLVED, with customer/assistant/SOC messages. The existing ticket service created the category
and SLA-policy dependency as needed. No SLA workflow or timer functionality was implemented.
[Final row counts](evidence/phase-a-recovery/database-counts.json).

## Exact verification results

| Verification | PASS | FAIL |
| --- | ---: | ---: |
| PostgreSQL + FastAPI TestClient, mocked Gemini SDK | 32 | 0 |
| Fresh Uvicorn process over HTTP + Vite/proxy | 9 | 0 |
| New recovery checks total | 41 | 0 |

All 41 checks executed, none skipped. These are named smoke checks; some contain multiple assertions,
not 41 separate unittest methods. The accepted 49/0 Phase B offline suite remains prior evidence and
was not rerun or added to this total. git diff --check passed.

The first verification launcher had an incorrect relative path and did not execute tests or write
application data; it was corrected before the recorded successful run.

[PostgreSQL/mock smoke log](evidence/phase-a-recovery/postgres-smoke.txt)
[Actual HTTP smoke log](evidence/phase-a-recovery/http-smoke.txt)

Coverage:
- Real PostgreSQL connection, current schema and limited role permissions.
- Startup lifespan and mock login for all five identities.
- Company A/B assets, collectors and logs; unauthorized and cross-company requests denied.
- KB retrieval and citation with Mock Gemini; raw canary and other-company telemetry absent from context.
- Thai fallback with AI disabled; no-match limitation.
- Private customer chat, same-company/cross-company room denial and SOC reply.
- Explicit ticket creation, company-visible metadata, customer status denial, support assignment/resolution.
- Citation persistence in PostgreSQL, owner-private ticket history.
- Fresh Uvicorn process reads the saved RESOLVED ticket and citation: durable data survives transition
  from the TestClient process to the real server process. This is not a PostgreSQL restart/restore test.
- Vite HTTP 200 and its /api proxy.

Mock provider verification replaces new_client with a fake SDK and fake key/model; it never calls
Google. The running Uvicorn process uses GEMINI_ENABLED=false, verified by HTTP response mode and
Thai fallback text. The retained transcript's Gemini-labelled advice came from the mock and must be
labelled as such in the university report. No live Gemini request, discovery call or evaluation score.

## Current service status and safe startup

At verification: PostgreSQL 16/main online on 5432; FastAPI on 127.0.0.1:8000 healthy;
Vite on 127.0.0.1:5173 healthy; API proxy working. Existing Vite was reused.
Services depend on this development session/VM; this is not a deployed or managed service.

First inspect ports; do not start duplicates or stop unidentified processes:

```sh
pg_lsclusters
ss -ltn '( sport = :5432 or sport = :8000 or sport = :5173 )'
curl -fsS http://127.0.0.1:8000/
```

Only if the relevant service is stopped, use separate terminals:

```sh
sudo pg_ctlcluster 16 main start
cd ~/true/backend
GEMINI_ENABLED=false .venv/bin/python -B -m uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1
```

```sh
cd ~/true/frontend
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Open Cloud Shell Web Preview port 5173 and choose a synthetic identity.
Keep the explicit GEMINI_ENABLED=false override: the existing .env was not edited and must not be
relied on to disable inference. Do not rerun provisioning or seeds for ordinary startup.
One backend worker preserves the existing temporary-room design.

The added `backend/scripts/verify_demo_recovery.py --synthetic-demo` is a one-shot, data-writing
smoke tool for a freshly seeded synthetic DB, not a general test runner. It now intentionally refuses
its synthetic/zero-ticket precondition because the retained demo ticket exists. Do not delete that
ticket merely to rerun the tool or run it against another configured DB without authorization.

## Remaining blockers and boundaries

The PostgreSQL authentication/missing-database blocker is resolved for the NEW synthetic demo.
Historical database/ticket/chat recovery was not attempted and is not claimed.

- Browser executable/screenshots and Thai visual acceptance still need a presentation browser.
- Live Gemini integration availability and answer quality remain unverified in this recovery run.
- Backup/restore and Cloud Shell VM-loss recovery remain untested; this local database is not a backup.
- Full Phase C validation requires separate approval; only the user's requested Phase A smoke scope ran.

New repository files in this recovery: the one-shot verification script, this report and the three
redacted evidence artifacts. No application source, dependency, .env, migration or existing test was
changed. No commit, push or deployment. Stopped after verification/reporting as requested.
