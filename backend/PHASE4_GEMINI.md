# Phase 4: optional Gemini through an AI Studio API key

**Current source uses plain-text generation.** The structured-output investigations
below are historical; their proposed fixes were not verified live. The plain-text
revision is tested offline only and awaits approval for one controlled live test.

## Integration and data boundaries

The existing google-genai==2.23.0 dependency is used with explicit
`vertexai=False`, `enterprise=False`, and the Gemini Developer API endpoint.
No IAM/ADC, Vertex AI, RAG, model tools, automatic ticket creation, Docker, or
new paid infrastructure is used. The legacy `/api/chat` now shares this same
safe path instead of its old RAG/tool loop and raw exception responses.

Flow: signed session -> room owner/company authorization where applicable ->
`authorized_company` -> company-filtered SQL -> local rule-based evidence ->
optional Gemini general advice. ADMIN/SUPPORT Q&A requires explicit company
selection. Customers cannot override the company in prompt text. Human SOC
messages never call Gemini. A room owner must explicitly confirm a ticket.

The provider is disabled by default, even if a key/model already exists.
`GEMINI_ENABLED=true` is the deliberate opt-in to live API usage. No model name
is assumed, no model discovery happens at startup/request time, and there are no
automatic retries or tool-call loops. We have NOT enabled live inference here.

### Only vetted demo values leave the server

The database schema has no trustworthy `is_mock` marker. Labelling arbitrary
rows as mock would be unsafe. `core/demo_telemetry.py` now holds the existing
seed fixtures, shared by the seed script and the outbound allowlist. Only rows
retrieved for the authorized company AND exactly matching that company's fixture
values can enter Gemini context. Unknown companies/records are omitted. Log
asset/collector references must also match the vetted scoped demo records.
No free-form database log bodies, tickets, user identities, company UUIDs,
credentials, tokens, or private transcript bodies enter the provider prompt.

To avoid fragile secret-pattern redaction, the raw user question is NOT sent.
It is projected locally to a fixed category and cybersecurity topic vocabulary
(e.g. assets, collectors, account security, malware, phishing, EDR, SIEM).
Up to six authorized room-history entries are inspected locally and only
customer topic enums leave the server. Caller-supplied legacy history is ignored.
This is intentionally a constrained demo assistant: nuanced questions outside
this vocabulary lose detail, and arbitrary conversation continuity is not sent
to Google. Extend the vetted projection only after reviewing the privacy impact.

Gemini produces plain-text Thai general guidance, not new evidence. The server
renders its rule-based company evidence separately and labels Gemini advice as
general guidance, not real system findings. The model is instructed not to
invent log events or claim actions. Invalid, blocked, truncated, empty,
non-Thai, or overlong output falls back without exposing SDK errors. Real model
compliance and Thai answer quality still need an explicitly approved live test.

### Bounds and fallback

- SQL samples: 20 assets, 10 collectors, 20 events; local evidence displays at
  most 10 events. Counts describe sampled rows, not full company inventory.
- Outbound context: at most 12 vetted demo records, six locally projected
  history entries, and 6,000 characters total. Questions: 1,000 characters.
- One generation call per request with default candidate behavior and at most
  512 output tokens. Accept only one STOP candidate and locally validated plain
  Thai text: at most 1,800 characters, six nonblank lines, 600 characters per line,
  and at least 12 characters. Local evidence caps at 3,000 characters.
- SDK HTTP timeout: 6,000 ms, retries: one attempt. Request wait deadline: seven
  seconds. At most two worker tasks, with no unbounded submission queue. A worker
  still finishing after a caller timeout holds its capacity until completion.
- Missing configuration/SDK, full capacity, invalid key, unavailable model,
  quota, network failure, deadline, or invalid output uses the existing rule-based
  response and `mode=rule_based_demo`; no provider exception/key is returned or logged.
- Success returns `mode=gemini_demo`, with the same existing `answer`, `source`,
  company/category/count fields. Chat history stores the visible assistant answer
  only under the existing temporary-or-ticket-linked Phase 3 policy.
- Network I/O happens outside the global chat store lock. Same-room duplicate
  customer sends return 409 while a bot response is pending; SOC replies and
  other rooms remain usable. Room access is checked again before appending.

## Secure configuration (do not paste keys into chat)

Use backend environment variables or the ignored **backend/.env** file (not
`,env`). Set file permissions to owner-only and enter the key in a local editor;
do not put it in shell commands/history, frontend VITE variables, Git, logs,
or screenshots. Existing .env values were not printed or modified by this task.

```dotenv
GEMINI_API_KEY=<your AI Studio API key, entered locally>
GEMINI_MODEL=<model ID available to this key; no default>
GEMINI_ENABLED=false
```

Choose an accessible text model supporting generateContent. JSON structured
output is not requested by the current provider. After configuring a candidate model, this OPTIONAL explicit command
makes exactly one model-metadata GET, with no inference or discovery loop:

```sh
cd backend
.venv/bin/python scripts/check_gemini_model.py --check
```

This command was tested with mocks only. A successful metadata check confirms
advertised generateContent access, not inference quota or JSON compatibility.
No live model/key check was performed in this task. Model availability remains
unverified until you run it. If unsupported, leave disabled and choose an
available model from your AI Studio account; the app does not guess another.

Only after approving live API use, change GEMINI_ENABLED to true and restart the
backend. Be aware that restarting loses temporary unticketed chats per Phase 3.
To disable Gemini, set the flag false and restart. Do not enable billing for
these tests. Normal authenticated usage when enabled can consume API quota.
The running backend for regression testing explicitly uses GEMINI_ENABLED=false.

Official references: [API keys](https://ai.google.dev/gemini-api/docs/api-key),
[model metadata and supported actions](https://ai.google.dev/api/models),
[Google Gen AI Python SDK](https://github.com/googleapis/python-genai).
SDK compatibility was checked against the locally installed pinned version.

## Offline verification

```sh
cd backend
.venv/bin/python -m unittest discover -s tests -p test_gemini_offline.py -v
```

This suite uses in-memory SQLite, real ASGI authentication/authorization, a
mocked Gemini client, and a guard against outbound socket connections. It never
connects to PostgreSQL, sends a real key, or makes a Google API/inference request.
The real SDK's config types and constructor options are checked offline.

It covers Thai success and bounds; timeout, invalid key, quota, unavailable model
fallback; missing config; adversarial tenant selection; unauthorized entrypoints;
secret/client-history/non-demo-record exclusion; same-company room privacy;
SOC replies and explicit ticket-linked history; blocked/malformed output;
deadline/capacity; SOC replies while inference is pending; and the optional
one-request metadata checker (mocked). Existing Phase 3 API/browser tests can
also run with GEMINI_ENABLED=false to verify fallback compatibility without
external inference.

Still unverified: actual key validity, model availability, live quota, schema
support for the selected model, live Thai answer quality, and live latency.

## Results for this implementation

- 12 offline/mock Gemini tests passed with outbound socket connections blocked.
- Full backend suite: 22 tests passed (12 new offline/mock + 10 existing).
- Existing Phase 3 browser suite: 12 flows passed against the updated backend,
  explicitly using GEMINI_ENABLED=false. This verifies fallback compatibility,
  not live Gemini behavior.
- Frontend lint/build, Python compilation, and git diff whitespace checks passed.
- The SDK already existed in requirements; version 2.23.0 was installed in the
  local venv. No new project dependency was added. The local FastAPI TestClient
  emits an httpx deprecation warning; tests pass with the SDK's existing httpx
  dependency, so no additional httpx2 dependency was introduced.
- backend/.env is ignored by Git and now has owner-only permissions. Its values
  were not changed or printed. The running backend stays on port 8000 with live
  Gemini disabled. No active temporary rooms existed before its restart.

Phase 4 files: `.env.example`, `core/demo_auth.py` (validate signed uid as UUID),
`core/demo_telemetry.py`, `core/llm_engine.py`, `main.py`,
`routers/customer_chat.py`, `routers/chat_rooms.py`,
`scripts/seed_customer_data.py`, `scripts/check_gemini_model.py`,
`services/gemini_support.py`, `services/support_answers.py`,
`services/temporary_chat.py`, `tests/test_gemini_offline.py`,
`PHASE3_CHAT.md`, `PHASE4_GEMINI.md`, plus frontend `README.md`,
`src/App.jsx`, and `src/components/PrivateChat.jsx` (provider-neutral wording).
Earlier uncommitted portal/Phase 3 changes are preserved.

## Offline diagnosis of the application HTTP 400

The earlier direct REST test succeeded without an output schema (256-token
limit). The application uses the same model/endpoint, a bounded JSON text input,
512-token limit, and JSON structured output. SDK serialization produces valid
user contents and text system instructions, and no tools are sent. No offline
issue was found with the model path, positive token bounds, or tenant context.

A confirmed request-contract mismatch is the output schema channel:

- Before: `response_schema=Advice` uses the legacy typed/OpenAPI
  `generationConfig.responseSchema`. The installed google-genai 2.23.0 emits
  `additional_properties: false` from Pydantic `extra='forbid'` into that object.
  The REST Schema contract does not define this field.
- After: `response_json_schema=Advice.model_json_schema()` uses
  `generationConfig.responseJsonSchema`, whose JSON Schema contract supports
  `additionalProperties: false` and `minItems`/`maxItems`. The existing Pydantic
  validation, Thai check, size bounds, timeout, no-retry behavior, and privacy
  boundaries remain intact. No SDK/dependency/key/model change was required.

References: [typed Schema and GenerationConfig](https://ai.google.dev/api/generate-content#Schema),
[official Python JSON Schema example](https://ai.google.dev/gemini-api/docs/generate-content/structured-output).

Historical audit contains HTTP 400, duration, attempt count, and scoped-demo
checks only; the Google error body was NOT retained. Therefore the incompatible
schema is confirmed offline and is a likely explanation, but we cannot prove
it was the sole cause of that historical response or claim live resolution.
A synthetic HTTP 400 in the regression is a contract-checking mock, not a
replayed Google error. Snake_case alone is not treated as the root cause: the
problem is a JSON Schema keyword in the legacy typed Schema channel.

The new test exercises the real SDK through httpx.MockTransport with an outbound
socket guard. It rejects the old incompatible field, accepts the new JSON Schema
request, and verifies the ASGI response uses gemini_demo while preserving the
constraints, system instruction, token limit, and absence of tools.

Verification: 23 backend tests passed (13 offline Gemini + 10 previous tests).
Frontend lint/build passed. API/browser regressions use isolated ports 8001/5174
and an SDK client mock; they never use the enabled real provider on port 8000.
The browser regression also obtains new room IDs from the create response to
avoid reading a dropdown before its option refresh completes.

No live Google API calls were made during diagnosis. To confirm real resolution,
we would need approval for ONE synthetic request through the fixed application,
without retries. If it still fails, capture only HTTP status, error.status and
redacted google.rpc.BadRequest field paths. Do not record raw headers, full
request/error bodies, credentials, or customer text.

Files changed for this diagnosis: `services/gemini_support.py`,
`tests/test_gemini_offline.py`, `../frontend/tests/phase3.browser.mjs`, and this
`PHASE4_GEMINI.md`. Existing tenant authorization and .env values are unchanged.

Browser regressions passed 12/12 with Gemini mocked. Temporary verification
servers on 8001/5174 were stopped. The local backend on 8000 was restarted to
load the fix after confirming zero temporary rooms; no inference was issued.
GEMINI_ENABLED remains true as previously approved; this task did not change it.

## Second offline investigation: configuration ablation (no live calls)

The updated application still received HTTP 400 INVALID_ARGUMENT in its ONE
approved post-schema-change test. The diagnostic retained status but no field
violations or useful provider message. That result disproves any claim that
switching schema channels alone fixed the integration.

### Exact known differences

The successful direct test was raw REST through httpx, not a google-genai SDK
call. Its known generation settings were temperature=0.2, candidateCount=1,
maxOutputTokens=256; no response MIME/schema. It used a short Thai synthetic
question and a short system instruction with no role field. The failing app
uses SDK 2.23.0, the same v1beta model endpoint, the same explicit API key source,
user-role JSON text containing vetted demo/topic enums, and a longer Thai system
instruction (SDK adds role=user to that instruction). It used temperature=0.2,
candidateCount=1, maxOutputTokens=512, responseMimeType=application/json, and
responseJsonSchema. AFC disable is local-only: it adds no toolConfig or tools to
the generated request. No prefilled model turn, thinking configuration, top-p,
top-k, or safety override is sent.

Thus temperature and candidateCount were present in BOTH historical tests;
they cannot by themselves explain the different historical result with certainty.
The structured-output block and input/system text are the main new body content.
Different HTTP client/library headers were not included in retained diagnostics.

### Installed SDK transformation

In google-genai 2.23.0, models.py's Developer API GenerateContentConfig converter
maps response_json_schema to responseJsonSchema via _transformers.t_json_schema.
That helper returns its input unchanged. The SDK accepts and serializes sampling
and candidate settings without validating model-specific capabilities. It is
not an offline server/model compatibility validator.

The current Advice schema is a plain object with guidance:string[] and optional
follow_up:string. It has additionalProperties=false, minItems=1, maxItems=3,
titles, and follow_up default="". It has NO $ref/$defs, nullable, null unions,
anyOf, or oneOf. The SDK preserves the schema unchanged. The structured-output
reference explicitly supports additionalProperties and minItems/maxItems;
model documentation explicitly lists structured outputs as supported. The default
annotation is not part of the listed supported-keyword subset, but that omission
alone is not evidence of rejection. It was NOT removed speculatively.

### Eight offline request stages

All stages are serialized by the REAL SDK with fake credentials into an
httpx.MockTransport under an outbound socket guard. Every mock response is 200;
this deliberately does NOT simulate a model rejection or imply live acceptance.

| Stage | Added setting | Generated body observation |
| --- | --- | --- |
| 1 | contents only | one user turn, no generation settings |
| 2 | system_instruction | text systemInstruction added |
| 3 | response_mime_type | responseMimeType=application/json |
| 4 | response_json_schema | unchanged JSON Schema in responseJsonSchema |
| 5 | temperature=0.2 (old config) | forwarded as temperature; no model validation |
| 6 | max_output_tokens=512 | forwarded as maxOutputTokens |
| 7 | candidate_count=1 (old config) | forwarded as candidateCount; no model validation |
| 8 | AFC disabled | wire body identical to stage 7; no tools |

A separate test reconstructs the known direct REST settings through SDK locally;
it does not recreate or replay the earlier live call. Schema-inventory and
incremental-shape assertions are in tests/test_gemini_request_matrix.py.

### Evidence-based smallest candidate change

[Developer API model page](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite)
links to [the model migration guidance](https://ai.google.dev/gemini-api/docs/whats-new-gemini-3.6).
Its migration checklist says candidate_count is unsupported on Gemini 3 and later,
and instructs Flash-Lite users to apply the same parameter rules. It describes
temperature/top-p/top-k as deprecated and ignored for these releases, with errors
on future generations. This is Developer API guidance, not a switch to Vertex.

The smallest safe candidate change is to OMIT explicit candidate_count and
temperature. They provide no necessary application behavior here. Keep
max_output_tokens=512, response MIME/schema, system instruction, AFC disabled,
Pydantic output validation, privacy projection, tenant checks, timeouts, bounded
workers, and fallback exactly as before. The request now has only three wire
settings: maxOutputTokens, responseMimeType, responseJsonSchema.

This removes documented compatibility risks but is NOT a confirmed fix. Given the
successful direct request also contained the removed settings, the historical
root cause remains unproven. Unsupported candidateCount is the strongest
model-specific configuration concern identified, while structured-output
compatibility remains the leading difference requiring a controlled server test.
No schema keywords, SDK version, API key, model, .env value, or live deployment
configuration were changed in this investigation. The live backend is NOT
restarted; source edits are for the next explicitly approved verification.

For conclusive diagnosis, a future separately approved single synthetic call must
retain a safely redacted provider message/code, not just INVALID_ARGUMENT. If it
still fails, field paths or a message template identifying the rejected setting
is needed before selecting another change. Do not retry or remove validation.

Verification results for this investigation: 26 backend tests passed (16 offline
Gemini/matrix and 10 prior regressions), 12 browser flows passed with Gemini
mocked, frontend lint/build and Python compilation/whitespace checks passed.
Isolated mock servers on 8001/5174 were stopped; live ports 8000/5173 and local
configuration were left unchanged. Test fixtures were cleaned by existing runners.
Changed files: services/gemini_support.py, tests/test_gemini_offline.py,
tests/test_gemini_request_matrix.py (new), and PHASE4_GEMINI.md.


## Plain-text simplification (current source, offline only)

Removed response_mime_type, response_schema, and response_json_schema entirely
from the production generation request. Removed the Advice/Pydantic output
schema and JSON parsing dependency from the provider. The SDK request now has
one user turn containing the SAME tenant-authorized sanitized demo context,
a short Thai system instruction, and generationConfig.maxOutputTokens=512 only.
Automatic function calling stays disabled locally; tools, sampling overrides,
and candidate-count overrides remain absent. API key/model/transport, timeout,
worker bounds, and retry settings are unchanged.

Local validate_text rejects empty/non-string/too-short/non-Thai/overlong text,
JSON-looking objects/arrays, code fences, HTML, invalid control/directional
characters and replacement characters, excessive lines/line length, or exact
configured credential echoes. The response must contain exactly one STOP
candidate without function calls. Blocked, truncated, malformed, timeout, quota,
permission, and transport failures retain the rule-based fallback. Validation
checks text structure and encoding, not factual correctness; live answer quality
still needs verification. No raw output or SDK exception is logged.

The system instruction asks for at most three concise Thai advice points and
one follow-up, without fabricated evidence, actions, tickets or requests for
credentials. The server continues to render database mock evidence separately
from general Gemini advice. There is no change to support_answers.py, tenant or
per-user authorization, outbound whitelist/topic projection, SOC human replies,
manual ticket confirmation, or temporary/ticket-linked storage semantics.

Offline tests replace schema expectations with plain-text success/rejection
cases. Real SDK MockTransport tests assert the ENTIRE generationConfig contains
only maxOutputTokens, with no MIME/schema/sampling/tools. Regression coverage
includes timeout, invalid key/model, quota, cross-tenant/adversarial company
selection, same-company private chat, human replies and ticket-linked history.
The request-matrix suite now exercises plain-text stages only; it no longer
constructs structured-output requests or assumes JSON decoding.

No live Gemini requests, configuration edits, billing changes, deployment, or
restart of the running application were performed. The source revision is not
active in the already-running backend process until it is reloaded for a future
approved test. Stop after offline verification and obtain explicit approval
before ONE controlled live test. Do not claim the HTTP 400 is resolved yet.

Files changed in this revision: services/gemini_support.py,
tests/test_gemini_offline.py, tests/test_gemini_request_matrix.py, PHASE4_GEMINI.md.

Plain-text verification results: 27 backend tests passed (14 Gemini offline,
3 plain-text wire/matrix, 10 prior regressions); 12 browser flows passed against
a mocked Gemini provider on isolated ports 8001/5174. Frontend lint/build,
Python compile and whitespace checks passed. Temporary mock servers stopped
and test fixtures cleaned. Existing live process/ports and .env were untouched.
This revision made ZERO live Gemini requests. Await explicit approval before
performing a single controlled live verification with the revised source.

## Separate client timeout and server deadline (offline verification only)

This revision changes ONLY timeout configuration in services/gemini_support.py:

```python
HTTP_TIMEOUT_MS = 15000
SERVER_DEADLINE_SECONDS = 12
DEADLINE_SECONDS = 16
# Existing HttpOptions, with all other options unchanged:
headers={'X-Server-Timeout': str(SERVER_DEADLINE_SECONDS)},
timeout=HTTP_TIMEOUT_MS,
```

Installed google-genai 2.23.0 has one HttpOptions.timeout in MILLISECONDS.
_api_client.get_timeout_in_seconds divides it by 1000 for the HTTP transport.
Without an explicit override, populate_server_timeout_header also derives a
server deadline in SECONDS using ceil(), so changing that one option alone does
NOT control client/server independently. The same function preserves an explicit
`X-Server-Timeout` header. HttpOptions.headers is supported public configuration;
this uses the exact spelling checked by the installed SDK, not an invented
server_timeout option, a patched SDK, or a weaker/unbounded timeout.

Real SDK offline transport tests confirm the configured header is "12" and all
HTTPX connect/read/write/pool timeout values are 15.0 seconds. Client timeout is
greater than server deadline. The application future.result guard is 16 seconds,
so it no longer returns fallback prematurely at the previous seven-second guard.
HTTPX timeouts apply per phase, not a guaranteed 15-second total wall-clock cap;
the separate 16-second application guard bounds caller waiting. A worker still
finishing after caller timeout retains its bounded worker slot as before.

A control test shows that 15001 ms without an explicit header derives a
16-second server deadline; supplying the explicit header retains 12 seconds
while HTTPX still receives 15.001 seconds. The normalized request bodies are
identical. An HTTPX ReadTimeout injected at the real SDK transport yields
fallback after exactly one attempt. Existing guard/quota/privacy tests remain.
No model, key, request body, output validation, tenant or user isolation,
telemetry projection, SOC replies, ticket confirmation or storage behavior changes.

The server-deadline hypothesis is supported by the installed SDK's confirmed
header behavior and external first-hand reports of minimum-deadline rejection;
our historical Google error message was not retained. This is NOT proof the
live HTTP 400 is resolved. No live Gemini call or metadata request is made here.
The running backend is not restarted and .env is not edited. This source change
awaits separately approved restart and controlled live verification.

Changed files: services/gemini_support.py,
tests/test_gemini_timeout_transport.py (new), PHASE4_GEMINI.md.

Deadline revision results: 30 backend tests passed, including three new real-SDK
transport timeout/header tests. Existing 12 browser flows passed with Gemini
mocked. Python compilation and whitespace checks passed. Temporary verification
servers stopped and their fixtures cleaned. Original backend PID 17042 on port
8000 was not restarted; no live Google API requests or billing/deployment changes.
