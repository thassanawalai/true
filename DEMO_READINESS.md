# SOC demo readiness — 2026-11-02 (UTC), demo 2026-11-09

**Verdict: core workflow PASS with mocks; environment/recovery NEEDS FIX before
calling the demo fully ready. No live Gemini request was made in this audit.**

| Status | Area | Evidence / action |
| --- | --- | --- |
| PASS | Complete workflow | Customer A1 login → Thai Gemini mock → SUPPORT reply in same room → customer confirms ticket → SUPPORT assigns and RESOLVED → customer sees status. |
| PASS | Role isolation | A1/A2 share company ticket metadata, never private chat/history; B excluded; ADMIN/SUPPORT list/filter/reply and manage tickets. Existing API/browser regressions plus restart check. |
| PASS | Error/empty/loading/session | Existing browser suite covers loading, readable errors, draft/retry, empty lists, unavailable rooms, explicit discard and signed-session expiry. Offline tests cover timeout/quota/key failure and fallback. |
| PASS | Thai text handling | Plain-text validator and mock Thai response render through the real UI/Markdown path with separate mock evidence. No JSON response exposed. |
| NEEDS FIX | Thai visual acceptance | Screenshot in this headless environment shows missing Thai glyphs; `fc-list :lang=th family` returns no fonts. Check the actual presentation browser/OS, and supply a Thai font there if missing. DOM text assertions alone do not prove readability. |
| PASS, limited | Restart recovery | A NEW test process on the same isolated SQLite file recovers the RESOLVED ticket and linked customer/bot/SOC messages; unticketed room returns 404. All five role permissions remain enforced. |
| BLOCKED | Cloud Shell VM-loss recovery | Real PostgreSQL is under `/var/lib/postgresql/16/main`, outside persistent home. Local Cloud Shell notice says VM/system changes are ephemeral. No backup/restore or fresh-VM recovery was tested/authorized. Need a verified backup/recovery plan before relying on the machine through Nov 9. |
| NEEDS FIX | Startup/runtime | Earlier checks returned HTTP 200, but final recheck found BOTH 8000 and 5173 stopped (connection refused). Start them using the runbook and recheck health before rehearsal. Node/npm are not on normal PATH; current Node 22.23.4 is under `/tmp`, so a VM reset loses it. Prepare a reliable Node 22.12+ startup environment. |
| NEEDS FIX | Space | Home has ~130 MB free (98% used). Review space before npm installs/backups. Nothing was deleted. |
| NEEDS FIX | SLA presentation | UI says RESOLVED “Stop SLA Timer”, but status/assign code does not update TicketSLA ownership/resolution or pause tracking. Remove that claim or exclude SLA timer claims from the demo; do not add a new SLA feature in this readiness pass. |
| NEEDS FIX | Reproducible source | Branch `feature/phase1-mock-login-multitenant`: 15 modified tracked files + 17 untracked files BEFORE this report. Core chat/Gemini/tests are untracked. Review and obtain approval to commit/back up; nothing was committed/pushed. |

## Exact verification performed

Tests deliberately used **isolated `/tmp/soc-readiness-isolated.sqlite3`**, NOT the
configured PostgreSQL database. Existing suites create/delete fixtures, so they
were redirected to that disposable test DB to respect the restriction on existing
data. Test-only SQLite UUID binding accepts string parameters like PostgreSQL;
application code/schema was not changed. This run therefore does NOT replace a
new PostgreSQL write/integration or PostgreSQL restore test.

- Backend: **30 tests passed**, command:
  `./.venv/bin/python -W ignore::DeprecationWarning /tmp/readiness_runner.py`.
  Runner redirects existing HTTP tests to the mocked app on 8001. Gemini offline
  tests use fake credentials/network guards; transport tests use mocked HTTP.
- Existing browser: **12 flows passed**, command:
  `NODE_BINARY=/tmp/true-node/node-v22.23.4-linux-x64/bin/node PLAYWRIGHT_MODULE=/home/ext_thassanawalai_man/.npm/_npx/420ff84f11983ee5/node_modules/playwright/index.mjs PLAYWRIGHT_BROWSERS_PATH=/tmp/true-playwright PORTAL_URL=http://127.0.0.1:5174 ./.venv/bin/python /tmp/readiness_runner.py browser`.
- Supplemental browser: **5 checks passed** with `/tmp/readiness_workflow.mjs`:
  Thai Gemini mock display; SOC reply; complete manual-ticket/assignment/status
  sequence; refresh restores linked history; next unticketed room uses fallback.
- Recovery: **3 checks passed** with `/tmp/readiness_recovery_check.py` after
  restarting ONLY the test backend: durable history/status retained, temporary
  room lost, all five roles retain correct visibility.
- Frontend: `npm run lint` and `npm run build` passed, using the existing temporary
  Node PATH. `git diff --check` passed. Thai screenshot inspected visually.
- No new live Gemini/metadata call. Prior separately approved actual-UI test
  succeeded with Gemini HTTP 200, 1.693 s provider latency, 261 input + 193 output
  tokens (454 total), text accepted and displayed. This is historical evidence,
  not a new quota/availability guarantee for demo day.

## Read-only real-environment checks

PostgreSQL connection PASS; cluster 16/main online. Counts before audit:
3 companies, 5 demo users (CUSTOMER 3, ADMIN 1, SUPPORT 1), 4 assets, 2 collectors,
4 logs, 0 tickets, 0 durable chat rooms/messages. Env is Git-ignored and mode 0600;
session secret is configured; values were not printed. Model remains
`gemini-3.5-flash-lite`, GEMINI_ENABLED remains true; timeout code is 15 s client,
12 s server, 16 s application wait. Current local services were not restarted by this audit; final port checks found
8000/5173 no longer listening. The isolated test backend was stopped after tests; no existing PostgreSQL data was altered or removed.

## Rehearsal/startup runbook (existing machine)

Do not start duplicates: inspect occupied ports/processes first. Restarting the
backend loses unticketed rooms; linked history remains in the database.

Backend terminal:

```sh
cd ~/true/backend
sudo pg_ctlcluster 16 main start
.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1
```

Frontend terminal (CURRENT temporary runtime; fix durability before demo):

```sh
export PATH=/tmp/true-node/node-v22.23.4-linux-x64/bin:$PATH
cd ~/true/frontend
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Open Cloud Shell Web Preview port 5173. Verify health without triggering Gemini:
`curl -fsS http://127.0.0.1:8000/`. Keep one backend worker for the volatile live
room store. Do not enable billing. Each customer send while Gemini is enabled
may call the API; use mocks/offline mode for rehearsals unless separately approved.

If data is missing on a recovered EMPTY demo DB, inspect/restore first. The
existing idempotent seed commands are:

```sh
cd ~/true/backend
PYTHONPATH=. .venv/bin/python scripts/seed_phase1.py
PYTHONPATH=. .venv/bin/python scripts/seed_customer_data.py
```

They do not restore tickets/private histories. Do not reset DB credentials,
drop/recreate a DB, or seed a different/live DB without reviewing scope. No
cold-VM/PostgreSQL restore is claimed to pass. Do not run the normal fixture-
cleaning regression suite against existing demo/customer data without approval.

## Minimum remaining work, priority order

1. Start backend 8000/frontend 5173 and verify health; verify Thai glyphs on the actual presentation device; fix its font if necessary.
2. Make Node startup and disk headroom reliable; authorize a backup and rehearse
   PostgreSQL recovery (or explicitly plan a fresh seeded demo with no retained
   tickets). No paid service/Docker is required.
3. Review/save the uncommitted change set with approval, and refresh stale guidance
   that still describes Gemini/DB as unverified.
4. Rehearse the exact sequence above with mocks; check customer status by opening
   tickets after SOC update or reloading (ticket lists do not continuously poll).
   Do not promise SLA timer tracking or unrestricted free-form AI context.

No new feature, paid dependency, architecture change, commit, push, deployment,
existing-data deletion, or live API call was performed. Only this readiness report
was added to the repository. Temporary test artifacts are retained under /tmp;
they are not backups and do not survive VM loss.
