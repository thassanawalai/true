# SOC demo portal

Requires Node.js 22.12+ and the FastAPI backend on `127.0.0.1:8000`.

```sh
npm ci
npm run dev
```

Open port 5173 (Cloud Shell Web Preview: port 5173). Vite proxies `/api` to
`http://127.0.0.1:8000`; override with `VITE_API_PROXY_TARGET` if needed.

- Pick a seeded demo identity. Sessions use a signed bearer token in
  `sessionStorage`; they are not production authentication.
- CUSTOMER: Q&A and tickets use the logged-in user's company, enforced by the
  backend. Ticket creation requires an explicit form submission.
- ADMIN/SUPPORT: choose a customer company before Q&A or viewing tickets.
  Switching companies clears the selected chat and ticket view. Customer company options
  come from the protected `/api/demo-auth/companies` endpoint.
- Q&A calls `/api/customer-data/ask` and displays `answer`. It is a rule-based
  telemetry demo with rule-based fallback. Optional AI Studio Gemini is documented
  in [Phase 4](../backend/PHASE4_GEMINI.md) and is disabled by default.
  Internal Company Q&A remains available.
- Customer Chat opens a private live room. SOC Customer Chats lists rooms across
  companies (or filters by company) and lets staff reply in the same conversation.
  Unticketed chat uses temporary server memory with a 30-minute idle TTL. It is
  lost on backend restart; refresh/navigation can reconnect while active.
- A customer explicitly confirms Create ticket from chat to save its transcript.
  The owner and SOC can reopen ticket-linked history from chat rooms or the ticket
  detail. A company colleague can see ticket metadata, never the private chat.
- Only demo tokens use browser sessionStorage. No transcript is stored there.
  See [Phase 3 architecture and tests](../backend/PHASE3_CHAT.md) for limitations.

Checks:

```sh
npm run lint
npm run build
cd ../backend
.venv/bin/python -m unittest discover -s tests -v
```

The live API tests require the backend running plus the demo users created by
`scripts/seed_phase1.py` and telemetry from `scripts/seed_customer_data.py`.
They create temporary tickets and remove only those tickets at teardown.
