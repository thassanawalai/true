# AGENTS.md — SOC AI Support Assistant / ITSM

## Purpose and source of truth
This repository is a demo SOC AI Support Assistant and lightweight ITSM system for a customer-facing portal and an internal SOC portal. Treat the code, database schema, tests, and current user requirements as sources of truth. This file is working guidance, **not** proof that a feature has been implemented or tested. Inspect the repository before making changes.

**Current deadline:** Demo readiness by **2026-11-09**; target completion before **2026-11-10**. Prioritize a working, testable end-to-end demo over additional features.

## Repository and working branch
- GitHub repository: `thassanawalai/true`
- Active development branch: `feature/phase1-mock-login-multitenant`
- Backend: `backend/` — Python, FastAPI, SQLAlchemy, PostgreSQL, Uvicorn.
- Frontend: `frontend/` — React + Vite; inspect actual files and scripts before editing.
- Development environment: Google Cloud Shell / Cloud Shell Editor; GCP project `tdg-sec-soc-nonprod`.
- No Docker required for current development. Avoid adding paid services or unnecessary dependencies.
- Do not commit directly to a different branch or force-push. Preserve unrelated changes.

## Product scope — keep it small
- Mock login and mock users for the demo. **Not production authentication.**
- Roles: CUSTOMER, SUPPORT, ADMIN (check actual enums in code).
- Many customers may belong to the same company.
- Customer portal: own company's tickets; private per-user chat; AI responds first; customer explicitly creates a ticket when needed.
- Internal SOC portal: admin/support can view and respond to customer chats, view tickets across companies, and filter by company.
- Ticket workflow: NEW, IN_PROGRESS, PENDING, RESOLVED. PENDING pauses SLA; time-to-own and time-to-resolve are required concepts.
- Impact, urgency, and priority should be assessed by AI/engineer, not selected by customer.
- Do not persist an ordinary chat conversation unless it becomes a ticket, per current demo requirement; ticket-linked chat may be retained.
- Keep SIEM/cybersecurity examples and UI readable and concise. Avoid scope creep.

## Multi-tenant security — non-negotiable
- **All customer data access must be enforced server-side**, including API endpoints, AI retrieval, ticket queries, chat history, and admin operations. Never trust a company ID supplied by a customer or inferred by an LLM.
- CUSTOMER: scope reads/writes to the authenticated user's `company_id`. Customers in the same company may share company-level tickets/assets/logs, but individual chat rooms remain private to their owner unless accessed by authorized internal staff.
- SUPPORT/ADMIN: may access customer companies explicitly, subject to authorization; telemetry endpoints currently require an explicit `company_id`. Do not treat the internal SOC demo company as a customer company.
- Use `core.demo_auth.current_user` for demo-protected endpoints, **not** legacy dependencies that silently return an admin.
- Scope database queries by company *before* passing any records to an AI model. Prompt instructions alone are not isolation.
- Validate that asset/collector references belong to the same company before implementing telemetry write or ingestion endpoints.
- Do not log or expose credentials, tokens, private customer data, or `.env` values. Never commit secrets.
- Demo signed bearer sessions are **not production-grade identity**; do not represent them as such.

## Current implementation snapshot (2026-11-02)
- Mock login: `/api/demo-auth/users`, `/api/demo-auth/login`, `/api/demo-auth/me`. The user list exposes `name` (not `full_name`), `id`, `role`, `company_id`, `company`.
- Customer telemetry models: `backend/models/customer_data.py` — `customer_assets`, `log_collectors`, `customer_logs`.
- Tenant-scoped read APIs: `GET /api/customer-data/assets`, `/collectors`, `/logs`.
- Authorization helper: `backend/routers/customer_data.py:authorized_company`.
- Demo telemetry seed: `backend/scripts/seed_customer_data.py`.
- A manual integration test reported **24/24 passing** for customer A1/A2/B1 and admin across assets/collectors/logs, including cross-company denials. This is not a substitute for automated regression tests.
- New demo Q&A endpoint: `POST /api/customer-data/ask` in `backend/routers/customer_chat.py`, registered by `backend/main.py`. This is **deterministic rule-based mock-data Q&A, not an LLM**. It has been committed but **has not yet been verified running** in Cloud Shell.
- Existing `POST /api/chat` uses an optional AI provider and may return 503 if unavailable. Do not confuse it with the rule-based endpoint.
- Gemini via Vertex AI/IAM is planned, but IAM/provider availability is **unverified**. Do not block the demo on it; never claim the model works without a successful test.
- Jev AI / TypeSafe AI was discussed as an optional reviewer; no verified integration. Do not assume it is available.
- PostgreSQL previously had **11 tables** after seeding. A subsequent startup failed with `password authentication failed for user "itsm_user"`. Database connectivity must be fixed and re-tested; do not claim the backend is currently healthy.
- Never store a real password in this document. Read the local `backend/.env` securely and keep it out of Git.

## Next steps — in priority order
1. Restore PostgreSQL authentication, verify a DB connection, and start Uvicorn; inspect logs rather than repeatedly guessing.
2. Verify `/openapi.json` includes `/api/customer-data/ask`; test authenticated A/B/admin Q&A and cross-tenant denial.
3. Add repeatable automated tenant-isolation tests (including unauthorized and adversarial company-selection cases).
4. Integrate the tenant-safe chat/ticket flow into the existing frontend; keep mock login simple.
5. Test ticket creation only on customer confirmation, customer ticket visibility, internal access, and ticket-linked chat.
6. Verify end-to-end demo flows and fix bugs before the deadline. Add real Gemini only when access and time permit.

## Development and verification commands
In Google Cloud Shell, typical paths are `~/true` and `~/true/backend`. Check the actual environment before executing.

```bash
cd ~/true
git status --short
git branch --show-current
cd backend
source .venv/bin/activate
sudo pg_ctlcluster 16 main start
python -m compileall -q main.py routers
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

In another terminal:
```bash
curl -i http://127.0.0.1:8000/
curl -sS http://127.0.0.1:8000/openapi.json | python -m json.tool
```

If Uvicorn fails, inspect the **full relevant traceback**. If port 8000 is occupied, inspect the process before stopping anything. If the DB rejects a password, verify connection settings and authorized database credentials without printing secrets. Do not drop tables, recreate the database, or reset credentials without checking the impact and obtaining confirmation.

## Agent working rules
- Communicate in concise, clear Thai unless the user asks otherwise. Use standard English for code, identifiers, and UI terminology.
- Before changing code: inspect relevant files, identify dependencies, state a short plan, and keep changes focused.
- Prefer small, reversible commits on the active branch; do not overwrite local work or apply an old stash blindly.
- Run syntax checks and relevant tests where possible; clearly distinguish **implemented**, **tested**, **unverified**, and **blocked**.
- Do not fabricate test results, IAM permissions, external AI integrations, or completed features.
- Never invent endpoints or schema fields; inspect actual code. For example, demo users expose `name`, not `full_name`.
- If working in a new agent session, first read this file, inspect `git status`, and summarize current state and the next actionable step.
