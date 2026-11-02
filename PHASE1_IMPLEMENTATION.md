# Phase 1 — Mock Login & Multi-Tenant Foundation

Status: In progress. Branch: `feature/phase1-mock-login-multitenant`.
Target: 2–8 November 2026.

## Findings in main
- `backend/main.py` explicitly omits authentication and migrations.
- `GET /api/tickets/` returns all tickets without caller authorization.
- `GET /api/tickets/{id}`, status update, and assignment lack authorization checks.
- `backend/core/llm_engine.py` ticket lookup and list tools do not enforce company ownership.
- `frontend/src/App.jsx` has no login, and hard-codes a company.
- `frontend/src/pages/Tickets.jsx` uses an all-zero company UUID and lets customers choose impact/urgency.
- `backend/api/chat_router.py` is empty and not registered; admin chat belongs to Phase 2.

## Implementation order
1. Define demo users/companies and role contract (CUSTOMER, SUPPORT, ADMIN).
2. Implement a server-issued, short-lived demo session tied to a known seeded user. Do not trust client-provided role/company. Clearly mark demo auth as non-production.
3. Add `get_current_user` dependency and role/company access checks to ticket list/detail/create/status/assign endpoints.
4. Enforce identical tenant scoping for AI ticket lookup/list/create tools. Require explicit confirmation for ticket creation.
5. Add frontend mock-login user picker, session handling, logout, and role-specific navigation.
6. Replace hard-coded company IDs with server-side user context. Remove customer impact/urgency controls.
7. Add integration tests for cross-tenant read/write denial, customer/admin role permissions, invalid/expired sessions, and logout.
8. Run frontend build, backend tests, and Docker smoke test before PR.

## Acceptance criteria
- Customers A1/A2 see only company A tickets; B1 sees only company B tickets.
- Support and Admin can see tickets across companies.
- Customer cannot change ticket status or assignment.
- Direct API requests and AI tools cannot bypass tenant authorization.
- Login/logout and page refresh work for demo sessions.
- No real credentials or secrets committed.
- No production deployment or claim of production-grade authentication.

## Out of scope
Admin inbox, persistent private chat, SLA calculation, advanced RAG, real SSO/authentication, production deployment.

## Review gates
All access-control tests pass; manual checks use two companies and three roles; no default-branch changes until reviewed.
