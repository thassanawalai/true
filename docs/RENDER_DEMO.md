# Temporary Render Free + existing Neon demo

One Docker web service serves React and FastAPI on the same HTTPS origin. No
Cloud Shell process is needed after deployment. No deployment or Neon changes
are performed by this preparation. Do not add a Render database.

## Gemini and login repair

For the Gemini build, use branch `feature/render-gemini-login`. The runtime
continues to serve FastAPI and the React bundle together and validates the DB
schema on startup. On the confirmed demo Neon database, inspect the current
revision before deploying. If the current revision is `20261109_demo`, the
reviewed upgrade to `20261110_ticket_assessment` adds only the ticket assessment
table. Run the upgrade separately after approval. Existing tickets remain readable.

The API validates login IDs as UUIDs and returns HTTP 422 for malformed IDs.
After deploying and confirming mock login, configure the following in the
Render service environment for Gemini:

| Variable | Value |
|---|---|
| GEMINI_ENABLED | true |
| GEMINI_API_KEY | Google AI Studio server-side key |
| GEMINI_MODEL | Model ID available to the key with structured generation |
| DEMO_AUTH_MODE | password |
| DEMO_LOGIN_PASSWORDS_JSON | JSON object keyed by seeded demo email, with a distinct random password of 16–256 characters for each enabled identity |

Enabling Gemini requires password sign-in for demo users. Use synthetic
incident descriptions and questions. Gemini receives only reviewed public KB
excerpts. Company-only documents remain local. New tickets show Gemini or
Fallback as the assessment source.

The remaining sections describe the existing Render baseline and mock rehearsal.

## Access and persistence

Visitors reach the existing SOC AI Support Demo Login page directly, without an
HTTP Basic prompt. The mock picker allows any visitor to select a demo customer,
SUPPORT or ADMIN. Use only synthetic demo data; this is not production identity
verification. API requests still require a signed mock session, with existing
role, company and private-room authorization. Application Logout clears that session.

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
| DEMO_SESSION_SECRET | Unique random secret, at least 32 characters |
| GEMINI_ENABLED | false |

DEMO_ACCESS_USER and DEMO_ACCESS_PASSWORD are no longer used; existing values have
no effect and can be removed from Render settings.

Render supplies PORT. No VITE API URL is needed. Leave GEMINI_API_KEY and
GEMINI_MODEL unset for fallback-only operation. Enable Gemini only after explicit
approval for external requests, using those two server-side settings. Do not put
secrets in Docker build arguments. The image excludes dotenv files and ships a
minimal runtime without the unused Torch/vector stack.

## Acceptance before sharing the URL

1. Wait for a successful deploy/health check; visit the onrender.com HTTPS URL.
2. In a fresh private browser, verify the Demo Login page and demo-user list load
   directly without an HTTP Basic challenge. Verify GET/HEAD /healthz succeeds.
3. Select A1/A2/B1 and SOC identities through the existing login page. The React
   client sends the signed mock session in X-Demo-Authorization. Protected APIs
   must still reject requests without a valid mock session.
4. Verify Thai fallback/citations, private rooms, SOC reply, explicit ticket
   creation and cross-company denials. Confirm linked tickets survive restart.
5. Open from a second device and verify the same URL/login page. Verify automatic wake
   after idle and explain that temporary chats expire. Never present live Gemini
   as verified when GEMINI_ENABLED is false.

## Chat behavior

General questions default to a concise Thai answer from the top authorized KB
match, without querying assets, collectors or customer logs. Existing explicit
inventory commands (`logs`, `events`, `assets`, `collectors`) remain available.
The วิเคราะห์ Log button sends `action: "analyze_log"` with the original question;
private chat accepts no company ID and resolves scope from the signed user.
Internal Q&A retains its existing authorized company selector. Summary replies
show at most three evidence items and three next steps. The technical-details
button explicitly sends `details: true`; a details flag alone does not analyze.
KB links are secondary, and creating a ticket still requires customer confirmation.
Gemini remains disabled in the Render configuration; the brief analysis uses
existing local rules. No database or migration change is needed for this UX.

References: https://render.com/docs/free, https://render.com/docs/docker,
https://render.com/docs/deploys, https://render.com/docs/health-checks.
