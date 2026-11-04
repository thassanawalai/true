# AI Security Problem Analysis — Phase 1

The shared `answer_question` service now performs local evidence-based triage for
`POST /api/customer-data/ask`, `/api/chat`, and private chat messages. Greeting and
basic inventory queries retain their existing behavior. No schema migration,
additional service, or dependency is required. Existing uncommitted UI/KB work
was preserved.

## Behavior and security boundaries

- Resolve tenant using authenticated `current_user` and `authorized_company`
  before any retrieval. Customer-supplied company IDs cannot change scope;
  internal users must explicitly select an authorized customer company.
- Classify reported login, scan, malware, ransomware, phishing, network, and
  exfiltration issues using deterministic English/Thai rules. Unknown issues
  explicitly remain unknown.
- Extract IPs (IPv4/IPv6), common hostnames, labeled usernames, recognized event
  types and ISO dates/timestamps locally. User-reported identifiers are not
  evidence of ownership. `analysis.entities` is untrusted reported information.
- Query tenant-scoped assets/logs, requiring both asset and collector to belong
  to the same tenant as each log. Event/entity/time filters precede the result
  limit. Source IP matches in messages do not imply asset ownership.
- Distinguish stored evidence, unconfirmed hypotheses and missing information.
  No matching logs gives UNKNOWN risk, never a claim of safety. Matching alerts
  give provisional MEDIUM risk (HIGH for ransomware/exfiltration), with reasons;
  the event label alone never confirms compromise.
- Render five sections: Incident Summary, Evidence & Findings, Risk Assessment,
  Recommended Actions, Missing Information. KB citations retain server-owned
  provenance. The existing Markdown component displays these sections in full.
- Gemini still uses the existing opt-in, bounded provider. It receives only
  fixed topic enums, exact verified synthetic fixture values, and digest-approved
  public KB. Raw customer prompts, extracted entities, real telemetry, private
  KB and chat transcripts are never sent. No real-data approval switch is added.
- Gemini output is mapped to reviewed defensive recommendations. Arbitrary
  model-authored evidence, identifiers, URLs and citations are not displayed.
  Local findings/risk remain authoritative if Gemini is disabled or unavailable.
- Existing room ownership, SOC access and explicit ticket promotion remain in
  place. No ordinary chat is made durable by this change. Legacy client-supplied
  `/api/chat` history continues to be ignored.

## Limits

This is explainable rule-based triage with optional Gemini recommendation
selection, not autonomous investigation or unrestricted LLM analysis. Rules and
aliases are intentionally small; ambiguous/free-form phrases can remain unknown.
Only the first matching issue class is analyzed. Plain inventory questions remain
inventory answers. There is no external IP reputation/ownership lookup.

Search examines at most 100 candidate logs after SQL filtering and validates
unstructured IP/username token boundaries locally. A truncation flag and warning
expose incomplete searches; narrow the time range to investigate further.
At most 20 matching assets are returned and 10 log records are rendered. Raw log
excerpts are limited to 300 characters; full logs remain in existing telemetry.
No timestamp means latest matching records across retained history, which may
not belong to the reported incident. Date-only input searches that UTC day;
precise timestamps use a 15-minute margin (two timestamps bound a range).
Timezone-naive input is interpreted as UTC and flagged for confirmation. Relative
phrases such as “yesterday” are not parsed. No new conversation-memory inference
is introduced. Risk scores do not alter ticket priority or workflow.

## Environment and verification

Existing runtime settings:

- `DATABASE_URL`: PostgreSQL connection for the application.
- `DEMO_SESSION_SECRET`: at least 32 characters for demo signed sessions.
- Optional Gemini: `GEMINI_ENABLED=true`, `GEMINI_API_KEY`, `GEMINI_MODEL`.
  Leave disabled for fully local operation. There are no new runtime variables.

Repeat safe synthetic tests from `backend/`:

```bash
PYTHONWARNINGS=ignore .venv/bin/python scripts/test_phase_ab_offline.py
PYTHONWARNINGS=ignore .venv/bin/python scripts/test_security_postgres.py
```

The offline runner disables dotenv, supplies fake settings, mocks the SDK and
blocks outbound sockets. The PostgreSQL runner requires local PostgreSQL server
binaries via `pg_config`; it creates its own temporary Unix-socket cluster and
HTTP port, disables Gemini for live HTTP tests, and stops/removes its own resources.
It does not use the configured application database or running demo server.

Frontend build: `cd frontend && npm run build` from the repository root.

Verification on 2026-11-04:

- Offline suite: **PASS, 60 tests** (11 new analysis regressions plus 49 existing).
- Isolated PostgreSQL analysis: **PASS, 11 tests**, mocked Gemini.
- Isolated PostgreSQL live chat/login/ticket suites: **PASS, 10 tests**, Gemini disabled.
- Frontend production build: **PASS**.
- Python compilation and whitespace checks: **PASS**.

No live Gemini inference or browser interaction was performed. Existing database
and demo server health are not inferred from these isolated results. Initial
format-related test failures were resolved before the final passing runs.

## Files changed for this task

- `backend/services/security_analysis.py` — extraction, scoped correlation, risk,
  actions and five-section rendering.
- `backend/services/support_answers.py` — shared pipeline integration and safe
  recommendation mapping.
- `frontend/src/components/ChatAnswer.jsx` — keep incident sections visible.
- `backend/tests/test_security_analysis.py` — synthetic analysis/security regressions.
- `backend/tests/test_ai_evaluation.py` — expect evidence sections for analyzed replies.
- `backend/scripts/test_phase_ab_offline.py` — include the new analysis suite.
- `backend/scripts/test_security_postgres.py` — disposable PostgreSQL verification.
- `docs/AI_SECURITY_ANALYSIS_PHASE1.md` — behavior, limitations and verification.
