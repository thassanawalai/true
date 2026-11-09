# Phase A–B completion review — 3 November 2026 (Asia/Bangkok)

Phase B implementation and offline verification are complete for the agreed submission scope.
Phase A real database/application readiness is BLOCKED. Phase C has not started.
Deadline remains 9 November 2026.

## Work preserved and files

Branch remains `feature/ai-kb-phase-ab`; no switch, commit, push, deployment or live Gemini call
was made in this follow-up. Existing uncommitted files remain intact.

This follow-up extends only `backend/tests/test_knowledge_base.py` (five new test methods),
adds `docs/evidence/phase-ab/offline-tests-followup.txt` and this report.
No application logic, .env, database, PostgreSQL settings or credentials were changed.

Cumulative Phase A/B files:

- `backend/data/soc_knowledge.json`: 10 source-grounded public Thai articles.
- `backend/services/knowledge_base.py`: authorized keyword/tag ranking, source rendering and public digest allowlist.
- `backend/services/support_answers.py`: KB integration, Thai fallback, server citations.
- `backend/services/gemini_support.py`: instructions for the authorized public KB context.
- `backend/tests/test_knowledge_base.py`: now 19 test methods.
- `backend/scripts/test_phase_ab_offline.py`: isolated offline runner.
- `docs/PHASE_AB_EVIDENCE.md` and `docs/evidence/phase-ab/`: earlier architecture, evidence and this follow-up's log.

Pre-existing `AI_EVALUATION.md` and `backend/tests/test_ai_evaluation.py` are preserved without edits.
The latter is run as an existing regression suite, not claimed as newly authored work.

## Exact results

Command from `backend/`: `.venv/bin/python -B scripts/test_phase_ab_offline.py`

| Suite | PASS | FAIL | ERROR | SKIP |
| --- | ---: | ---: | ---: | ---: |
| Gemini offline | 14 | 0 | 0 | 0 |
| Request matrix | 3 | 0 | 0 | 0 |
| Timeout transport | 3 | 0 | 0 | 0 |
| Existing AI contract scenarios | 10 | 0 | 0 | 0 |
| KB retrieval/API/privacy/persistence | 19 | 0 | 0 | 0 |
| Total | 49 | 0 | 0 | 0 |

Actual unittest run: 49 tests in 6.069 seconds, OK. Parameterized subcases are not counted
as separate tests. [Full current log](evidence/phase-ab/offline-tests-followup.txt).
The prior 44-test log is preserved as historical evidence. `git diff --check` also passed.

The runner blocks outbound sockets, disables dotenv loading, supplies fake provider credentials,
uses in-memory SQLite fixtures and mocks the SDK. No production/demo PostgreSQL data is touched.
These are application contract results, not live AI quality scores or PostgreSQL integration results.

## KB architecture and evidence

Authenticated session → room ownership where applicable → `authorized_company` → filter JSON documents
by public scope or exact authorized company UUID → keyword/tag scoring → top two positive matches →
Thai evidence/KB text and deterministic source citations. This is not semantic search.

The Gemini branch receives existing fixed topic enums, bounded history topic projections,
whitelisted synthetic telemetry and exact reviewed public KB content verified by digest.
Company-private KB content and metadata are not sent to Gemini. Raw questions/transcripts are not forwarded.
No vector infrastructure, dependencies or database migrations were added.

| Priority | Evidence from passing tests |
| --- | --- |
| Public retrieval | Same expected public document and exact ID/title/source returned to A and B; Thai/English relevance cases |
| Company-private isolation | Filter before scoring/top-k; A/B private canaries separated; private titles/source URLs absent from B response |
| No match | Empty citations/context; Thai limitation with AI disabled and with mocked AI enabled |
| Thai fallback | Disabled provider and timeout retain Thai text and correct KB source |
| Citation correctness | Exact catalog metadata and source URL equality; fabricated provider KB IDs/URLs rejected |
| Ticket-linked citation persistence | Exact assistant text read from ORM RoomMessage in a new session; still retrieved after temporary RAM store is cleared |
| Gemini privacy | Public context retained while raw secret/question/history, other-company telemetry and identity IDs are absent |
| Supporting features | SOC reply, explicit ticket linking, company-visible ticket metadata and support status/assignment regression pass |

The ORM persistence test proves the SQLite/ASGI path after ticket linking and a temporary-store clear.
It does not simulate a PostgreSQL restart or claim recovery across processes. Those remain deferred.
For the full Mermaid architecture, fields, source list and limitations see [Phase A/B evidence](PHASE_AB_EVIDENCE.md).

## PostgreSQL diagnosis — read-only

Observed in this follow-up:

1. `pg_lsclusters` reports only PostgreSQL 16/main, online on port 5432.
2. Active data directory: `/var/lib/postgresql/16/main`; configuration:
   `/etc/postgresql/16/main/postgresql.conf`; server version 16.15.
3. Application settings come from `backend/.env`, via `core/database.py`; no process
   DATABASE_URL override was present. The URL uses psycopg2, loopback host, port 5432,
   a populated password and no extra URL query options. No credential or full URL was printed.
4. The expected database name was compared in memory with `pg_database`: **absent**.
   The expected username was compared in memory with `pg_roles`: **absent**.
   Only `postgres` is a non-template database in this cluster.
5. The configured application connection returns password authentication failure.
   Because the role is absent, this error is not evidence that merely resetting its password
   would fix the system; the target database is also absent.
6. Local HBA rules use peer authentication on Unix sockets and scram-sha-256 on IPv4/IPv6 loopback.
   Read-only administrative queries succeeded through peer auth. No HBA edit was made.
7. Searches of `/etc/postgresql` and `/var/lib/postgresql` found only version 16/main.
   Ports 5432, 5433 were inspected: 5432 listening, no 5433 listener.
8. `docker ps -a` and `docker volume ls` returned empty lists on the current Docker daemon.
   Repository compose declares postgres:15-alpine and pgdata mounted at `/var/lib/postgresql/data`,
   but no such running container or volume was found. No Docker service was started.

**Conclusion:** the configured host/port reaches the current native cluster; the required demo
role and database are missing there. No alternate local registered cluster/container was found.
This is a confirmed configuration-versus-instance mismatch, not a confirmed password-only fault.
Whether the original DB was on an earlier Cloud Shell VM, another host or a removed volume remains
unproven. No previous cluster identifier or verified backup is available to establish that history.

### Backup and initialization inventory

No matching dump/backup/SQL/archive files were found in the searched home/tmp/workspace/mnt locations
(with dependency/cache/tool-history directories excluded), nor under `/var/backups` or local Docker
volume locations. No alternative PG_VERSION cluster root was found under `/var/lib/postgresql`.
This is a bounded local search, **not proof that no cloud/off-machine backup exists**.
No bucket, remote host, account or backup contents were accessed.

Available initialization sources, inspected only:

- `backend/scripts/seed_phase1.py`: company A/B/internal SOC and five mock users.
- `backend/scripts/seed_customer_data.py`: synthetic assets, collectors and logs.
- `backend/core/demo_telemetry.py`: A/B fixture definitions.
- `backend/main.py` startup: ORM `create_all` for current registered models.
- `backend/alembic/versions/0ca6d68be46d_initial_schema_with_multi_tenant.py`: legacy initial migration;
  not sufficient by itself for all current chat/telemetry tables.
- `backend/seed.py`: legacy seed, not chosen for recovery.
- `backend/docker-compose.yml`: alternate container setup, not an existing backup.

Seed scripts do not recreate historical tickets/private conversations. None was executed.

## Remaining blockers and exact next steps

1. User selects an authorized recovery source (backup/previous instance) or approves a fresh,
   explicitly synthetic demo database and role. Do not reset passwords or create/restore anything before approval.
2. If restoring: inspect backup metadata and destination first, then restore only the approved target.
   If starting fresh: provision the approved demo role/database, use current ORM registration and
   reviewed Phase 1/telemetry seeds; acknowledge that old tickets/chats are not recovered.
3. After separate database-write approval, validate PostgreSQL connectivity and expected fixture counts,
   start one FastAPI worker with process-level `GEMINI_ENABLED=false`, then check health/login/chat.
4. Browser executable and real UI screenshots remain unavailable from the earlier audit; collect actual
   Thai answer/citation/fallback screenshots after backend and browser prerequisites are available.
5. Obtain explicit approval for Phase C before the broader PostgreSQL cross-tenant/E2E matrix.
   Live Gemini, commit, push and deployment require separate approval.

Stopped after Phase A/B reporting. No Phase C work, PostgreSQL mutation or recovery action was performed.
