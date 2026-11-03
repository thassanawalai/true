# Phase 3: private live chat and ticket history

## Storage and privacy

Ordinary chat is not written to PostgreSQL, browser storage, files, or logs by
these chat handlers. To let SOC see active unticketed conversations, the demo
uses a bounded Python memory store (one active temporary room per customer).
It is explicitly a temporary transport, not an archive:

- Run **one Uvicorn worker** on one instance. No Redis or external services.
- TTL is 30 minutes since the last successful message; reading/polling does not
  extend it. A sweep removes expired content every 30 seconds and each temporary
  room access also purges expiry. Idle memory retention can exceed TTL by at most
  the sweep interval. Restart/shutdown loses all unticketed rooms.
- Maximum 1,000 active rooms and 200 messages per temporary room. A customer can
  discard a temporary room with DELETE and reopen, or explicitly create a ticket
  once the chatbot has answered. Capacity failure returns 409/503.
- Refresh/navigation/logout does not archive or delete a room: authenticated users
  can reconnect during its TTL. The UI keeps no transcript in sessionStorage or
  localStorage; only the existing demo bearer token is in sessionStorage.
- SOC sees only currently active temporary rooms plus ticket-linked rooms.
  This is polling (1.5 seconds per open conversation, 3 seconds for room lists),
  not guaranteed delivery or a scalable multi-instance messaging system.

Every room request authenticates with `current_user`. Customers are filtered by
BOTH owner and company, including direct room/message/ticket-history URLs.
ADMIN/SUPPORT may read/reply across customer companies and filter room lists by
company. A1 and A2 can share company ticket metadata but cannot read each other's
private transcript, including after ticket creation. No customer-supplied role,
sender, owner, transcript, or company is accepted on message/link requests.

Each customer message is followed by the rule-based chatbot, using authenticated
company-scoped telemetry. SOC replies are labelled with the authenticated agent.
The server blocks SOC replies and ticket linking before the first chatbot answer.
The default remains rule-based; optional AI Studio Gemini and its privacy limits
are documented in PHASE4_GEMINI.md. Staff can join the same conversation but cannot confirm a
customer's ticket creation.

## Durable promotion

`POST /api/chat-rooms/{room_id}/ticket` is the explicit customer confirmation.
A ticket, ChatRoom, and its existing customer/chatbot/SOC messages commit in ONE
transaction. Failure rolls back the ticket and history, leaving temporary chat
available. Retrying the same room returns its existing ticket. The temporary room
is removed only after commit; subsequent messages are stored in `room_messages`.
The default company-visible ticket description is generic, never the transcript.
The customer chooses a company-visible subject in the confirmation form.

`chat_rooms.ticket_id` is non-null and unique: durable rooms always link a ticket.
`room_messages` keeps sender, role, timestamp, and sequence. These are separate
from company-visible ticket comments. Ticket deletion cascades chat data at the
DB level. Demo startup creates the two additive tables using the existing
`Base.metadata.create_all` pattern; it does not drop or recreate existing tables.
No Alembic upgrade is needed for this demo startup path. Existing deployments
that exclusively use Alembic need to provision these tables before enabling the
new router; the repository's legacy migration chain is not the demo schema source.

## APIs

| Method | Path | Scope |
| --- | --- | --- |
| GET | `/api/chat-rooms?company_id=...` | Own rooms; SOC all or company filter |
| POST | `/api/chat-rooms` | Customer opens/reconnects temporary room |
| GET | `/api/chat-rooms/{id}` | Owner + company, or SOC |
| DELETE | `/api/chat-rooms/{id}` | Owner discards temporary room |
| POST | `/api/chat-rooms/{id}/messages` | Owner question + chatbot; SOC reply |
| POST | `/api/chat-rooms/{id}/ticket` | Owner explicit ticket confirmation |
| GET | `/api/chat-rooms/by-ticket/{ticket_id}` | Owner + company, or SOC |

The existing company Q&A, standalone explicit ticket form, login, company ticket
lists, status, and assignment APIs remain available. Standalone tickets have no
chat history and return 404 from by-ticket. A company colleague sees the same
unavailable response for another customer's private history.

## Verification

Backend (running localhost API, seeded demo users for the older portal suite):

```sh
cd backend
.venv/bin/python -m unittest discover -s tests -v
```

`test_chat_rooms.py` creates isolated test companies/users and removes them and
their chats/tickets. It checks live HTTP authorization/isolation, SOC messages,
explicit promotion, same-company transcript privacy, schema persistence,
idempotent linking, expired sessions, and forged payloads. Deterministic tests
call the same handlers with a controlled clock/commit failure to cover TTL,
process-memory loss, and atomic rollback without a test-only API endpoint.

Browser tests use isolated companies/users (including same-company customers),
real API calls through the Vite proxy, and separate browser contexts per role.
They clean up all fixture rooms/tickets/users after browser shutdown. Install the
optional test tool outside the repository; no package.json change is needed:

```sh
npm install --prefix /tmp/soc-chat-browser --no-save playwright
PLAYWRIGHT_BROWSERS_PATH=/tmp/soc-chat-browsers /tmp/soc-chat-browser/node_modules/.bin/playwright install chromium --only-shell
cd backend
PLAYWRIGHT_MODULE=/tmp/soc-chat-browser/node_modules/playwright/index.mjs \
PLAYWRIGHT_BROWSERS_PATH=/tmp/soc-chat-browsers \
.venv/bin/python scripts/test_phase3_browser.py
```

Node.js must be on PATH (or set `NODE_BINARY`). Vite must run on port 5173;
`PORTAL_URL` can override it. The runner supplies isolated fixtures and an expired
signed token without printing credentials or tokens. Do not run the browser file
directly without the fixture runner.

Verified in this workspace:

- 10 backend tests: 7 Phase 3 and 3 existing portal regressions.
- 12 browser flows: AI-first/no automatic ticket; A1/A2/B room isolation; temporary
  refresh/navigation and absence of browser transcript storage; ADMIN/SUPPORT
  company filtering/live replies; explicit ticket confirmation/full transcript;
  company ticket visibility versus private history; durable replies/follow-up
  after refresh; expired signed session during polling; unavailable temporary
  room recovery; explicit discard; loading/error/draft/retry; SOC ticket history
  and assignment/status controls.
- TTL expiry and process-memory loss were simulated deterministically. We did
  not wait 30 minutes or restart a production server as part of a browser test.
- Frontend lint/build, Python compile checks, and whitespace checks pass.

## Files changed for Phase 3

Backend: `main.py`, `models/chat.py`, `routers/chat_rooms.py`,
`services/temporary_chat.py`, `services/ticket_service.py`,
`tests/test_chat_rooms.py`, `scripts/test_phase3_browser.py`, `PHASE3_CHAT.md`.

Frontend: `src/App.jsx`, `src/components/PrivateChat.jsx`, `src/pages/Tickets.jsx`,
`src/services/api.js`, `tests/phase3.browser.mjs`, `README.md`.

Earlier uncommitted portal integration changes (including demo company listing,
ticket filtering/response schema, Vite config, and portal tests) are preserved.
