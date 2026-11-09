# Temporary Render Free + existing Neon demo

One Docker web service serves React and FastAPI on the same HTTPS origin. No
Cloud Shell process is needed after deployment. No deployment or Neon changes
are performed by this preparation. Do not add a Render database.

## Access and persistence

The browser first prompts for HTTP Basic invitation credentials. Only then can
an operator select a mock customer, SUPPORT or ADMIN. Everyone who receives the
invitation is trusted to use every mock role. Share it only with demo reviewers,
not general visitors; use synthetic customer data. Application Logout clears the
mock session, not the browser's cached Basic credentials. Close the private
browser session to leave the invitation gate; rotate the password to revoke it.

Render Free sleeps after 15 idle minutes and wakes on a request (roughly one
minute). RAM-only unticketed chats disappear on sleep/restart/redeploy. Tickets
and linked transcripts persist in Neon. This follows the existing non-persistent
ordinary-chat requirement. Keep one worker; do not add keepalive automation.

## One-time database preparation — only after explicit authorization

1. Securely supply the existing Neon direct connection string as `DATABASE_URL`
   in a trusted terminal. Preserve its TLS parameters. Set
   `PYTHON_DOTENV_DISABLED=1` so no developer dotenv can select a different DB.
2. Inspect the database's current Alembic revision and schema before writing.
   Expected baseline: `0ca6d68be46d`, eight application tables plus
   `alembic_version`. Confirm whether any of the five new tables already exist.
3. Review `20261109_demo_chat_telemetry.py`. It only adds customer_assets,
   log_collectors, customer_logs, chat_rooms and room_messages plus their indexes.
   If these already exist from create_all, stop and reconcile their definitions;
   do not drop them or blindly stamp a revision. The revision intentionally has
   no destructive downgrade.
4. After approval, from `backend/`, run `.venv/bin/python -m alembic upgrade head`.
   Verify revision `20261109_demo` and 13 application tables plus alembic_version.
5. Verify the expected synthetic demo users exist. Only if missing, and separately
   authorized, run the existing `scripts/seed_phase1.py` with `PYTHONPATH=.` and
   then `scripts/seed_customer_data.py`. Never use legacy `seed.py` or the one-shot
   recovery script. No seeding or migration runs during container startup.

Render Free does not offer the paid pre-deploy command. Run this one-time
migration from a trusted local/Cloud Shell terminal; subsequent normal use needs
neither that terminal nor repeated setup.

## Render Dashboard settings — after source publication is approved

- New > Web Service > connect `thassanawalai/true`.
- Branch: `feature/ai-kb-phase-ab`, with the reviewed changes published first.
- Language/runtime: Docker; instance: Free.
- Root directory: blank (repository root).
- Dockerfile: `./Dockerfile`; Docker build context: repository root.
- Docker Command: blank (use image CMD, which binds `0.0.0.0:$PORT`).
- Health check path: `/healthz` (public generic DB connectivity check).
- Auto-deploy: disabled during demo preparation; use Manual Deploy after review.
- No persistent disk, second frontend service, Render PostgreSQL or cloud IAM.

Set these **runtime environment variables** in the Dashboard, never in Git:

| Variable | Value |
|---|---|
| APP_ENV | production |
| DATABASE_URL | Existing Neon PostgreSQL pooled URL with TLS parameters |
| DEMO_ACCESS_USER | Chosen invitation username (no colon) |
| DEMO_ACCESS_PASSWORD | Unique random secret, at least 24 characters |
| DEMO_SESSION_SECRET | Different random secret, at least 32 characters |
| GEMINI_ENABLED | false |

Render supplies PORT. No VITE API URL is needed. Leave GEMINI_API_KEY and
GEMINI_MODEL unset for fallback-only operation. Enable Gemini only after explicit
approval for external requests, using those two server-side settings. Do not put
secrets in Docker build arguments. The image excludes dotenv files and ships a
minimal runtime without the unused Torch/vector stack.

## Acceptance before sharing the URL

1. Wait for a successful deploy/health check; visit the onrender.com HTTPS URL.
2. In a fresh private browser, verify the invitation challenge appears before
   UI, demo-user list, login, docs or API access. Wrong credentials must fail.
3. After invitation authentication, verify A1/A2/B1 and SOC flows. The browser
   carries Basic authentication; the React client sends the mock session in
   X-Demo-Authorization. A mock token alone must not bypass the invitation gate.
4. Verify Thai fallback/citations, private rooms, SOC reply, explicit ticket
   creation and cross-company denials. Confirm linked tickets survive restart.
5. Open from a second device and verify the same URL/gate. Verify automatic wake
   after idle and explain that temporary chats expire. Never present live Gemini
   as verified when GEMINI_ENABLED is false.

References: https://render.com/docs/free, https://render.com/docs/docker,
https://render.com/docs/deploys, https://render.com/docs/health-checks.
