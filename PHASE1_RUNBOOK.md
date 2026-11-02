# Phase 1 implementation and verification

## Implemented
- Demo user selection and signed, eight-hour bearer sessions (demo only)
- Server-derived user role and company
- Tenant-scoped ticket list/detail/create and support-only status/assignment
- Tenant-scoped AI ticket lookup/list; AI ticket creation disabled until user confirmation through ticket form
- React login/logout, role-aware ticket navigation, and authenticated API calls
- Demo fixture seeding script and Docker Vite proxy configuration

## Start locally
1. Copy `backend/.env.example` to `backend/.env`.
2. Set `DEMO_SESSION_SECRET` to a **unique random value of 32+ characters**. Set `GEMINI_API_KEY` to enable AI.
3. From repository root: `docker compose -f backend/docker-compose.yml up -d --build`
4. Seed demo users: `docker compose -f backend/docker-compose.yml exec backend python scripts/seed_phase1.py`
5. Open `http://localhost:5173`; API at `http://localhost:8000/docs`.

## Manual acceptance checks (not yet executed)
- Login as Customer A1 and create a ticket; Customer A2 sees it, Customer B1 does not.
- Attempt to GET/PATCH the Company A ticket ID as Customer B1: GET must be 404; PATCH must be 403.
- Customer A1 cannot assign or update status (403).
- Support/Admin can see tickets across companies, update status, and assign.
- Refresh page with demo token, then logout and verify protected requests return 401.
- Ask AI to list tickets as Customer B1; Company A ticket data must not appear.
- Verify Create Ticket works with no client-supplied company UUID.
- Test expired and forged tokens; both must return 401.

## Important limitations
- This is **not production authentication**: anyone with access to the demo login screen can choose any demo account. Do not expose it to the public internet.
- No browser/runtime tests were executed from this environment. No claim of completion until the checks above pass.
- Chat messages are local to the browser; persistent per-user conversations and Admin Inbox remain Phase 2.
- Existing schema and legacy seed.py were not migrated; use scripts/seed_phase1.py for this branch.
- Current session tokens are stateless: logout clears the browser token but does not revoke a copied token before expiration.
