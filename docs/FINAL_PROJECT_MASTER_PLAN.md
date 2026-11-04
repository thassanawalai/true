# FINAL PROJECT MASTER PLAN

**Project:** SOC AI Support Assistant — AI-Assisted Cybersecurity Incident Analysis  
**Repository:** `thassanawalai/true`  
**Target location:** `docs/FINAL_PROJECT_MASTER_PLAN.md`  
**Document version:** `1.0.0`  
**Baseline date:** 4 November 2026  
**Presentation target:** 9 November 2026 (confirm with academic supervisor)  
**Status:** Scope frozen; implementation and research validation in progress  
**Document owner:** Project developer; changes require review and recorded justification

> **Purpose:** This document is the project's single source of truth for scope, architecture, implementation, research methods, evaluation, acceptance criteria, and presentation. It distinguishes **verified observations**, **developer/Codex reports**, **planned work**, and **limitations**. It is not evidence that untested features work.

---

## 1. Executive summary / บทสรุปโครงงาน

โครงงานนี้เป็นการวิจัยเชิงประยุกต์ AI เพื่อพัฒนาผู้ช่วยวิเคราะห์เหตุการณ์ด้านความมั่นคงปลอดภัยไซเบอร์สำหรับลูกค้าหลายบริษัท โดยใช้ระบบ ITSM เป็นช่องทางรับแจ้งปัญหา สนทนา และส่งต่อ Ticket ระบบจะค้นคืนหลักฐานที่ผู้ใช้มีสิทธิ์เข้าถึงจาก Asset Inventory, Security Logs และ Knowledge Base ก่อนสร้างคำตอบที่แยกข้อเท็จจริง สมมติฐาน ระดับความเสี่ยง คำแนะนำ และข้อมูลที่ยังขาด

**Research contribution to demonstrate:** เปรียบเทียบ Rule-Based Security Analysis (baseline) กับ Gemini-Assisted Analysis บนข้อมูลสังเคราะห์ชุดเดียวกัน โดยวัดความถูกต้อง ความสอดคล้องกับหลักฐาน ความปลอดภัยในการแยกข้อมูลลูกค้า และเวลาในการตอบสนอง ไม่อ้างว่า Gemini ดีกว่าจนกว่าจะมีผลทดลองจริง

### Proposed project title

- **Thai:** การพัฒนาระบบผู้ช่วยวิเคราะห์เหตุการณ์ความมั่นคงปลอดภัยไซเบอร์ด้วยปัญญาประดิษฐ์เชิงกำเนิดร่วมกับการสืบค้นหลักฐานแบบแยกข้อมูลลูกค้า
- **English:** Development of a Generative AI-Assisted Cybersecurity Incident Analysis System with Tenant-Isolated Evidence Retrieval

> The title is a proposal and should be checked against any previously approved university title. Gemini-Assisted functionality must be implemented and evaluated before making corresponding completion claims.

## 2. Problem statement and research questions

### Problem

SOC personnel receive cybersecurity incident reports with varying detail. Investigating relevant logs and assets, interpreting uncertain signals, and producing consistent advice can require manual effort. A generic chatbot may produce unsupported claims or mix data between customers. This project evaluates whether a controlled AI-assisted approach can help without sacrificing evidence traceability and tenant separation.

### Main research question (RQ1)

Does Gemini-assisted incident analysis improve analysis quality compared with the existing rule-based baseline when both methods receive the same authorized evidence?

### Supporting research questions

- **RQ2:** How accurately does each method classify incidents, extract entities, assess risk, and ground its claims in available evidence?
- **RQ3:** Can tenant isolation be maintained throughout evidence retrieval and AI response generation?
- **RQ4:** What trade-offs arise in latency, reliability, and uncertainty handling?

### Hypotheses (to test, not assert)

- **H1:** Gemini assistance improves at least one measured aspect of analysis quality relative to the baseline.
- **H2:** Evidence validation reduces unsupported claims in displayed responses.
- **H3:** Tenant-safe retrieval and output checks prevent cross-tenant disclosure in defined test cases.

## 3. Research objectives and measurable outcomes

| Objective | Proposed measure | Target (not yet achieved) |
|---|---|---|
| Develop incident analysis from customer text and authorized evidence | Incident classification accuracy; entity extraction F1 | ≥85%; ≥90% |
| Compare baseline and Gemini-assisted methods | Evidence grounding; unsupported claim rate; risk agreement; latency | ≥90%; ≤5%; ≥80%; report actual latency |
| Enforce customer data separation | Tenant isolation test pass rate across defined API/chat/AI cases | 100% |

**Important:** Targets are project-proposed acceptance goals, not validated research results. Academic supervisor approval is required if objectives or targets have already been formally submitted.

## 4. Scope freeze / ขอบเขตที่ล็อก

### In scope

1. Existing React/Vite Customer and SOC portals, mock login, private chat, and ticket workflow.
2. Existing FastAPI, PostgreSQL, company/role access rules, customer assets/logs, and KB.
3. Existing rule-based incident analysis as an immutable comparison baseline (except verified bug fixes).
4. Gemini-assisted analysis through the backend, using only approved synthetic or explicitly authorized data.
5. Structured incident output, evidence validation, uncertainty handling, timeout/fallback.
6. Reproducible comparative evaluation and research reporting.

### Out of scope until after presentation

- New dashboard or UI redesign; production authentication; real SIEM ingestion; fine-tuning; new vector database; new ITSM modules; unnecessary database migrations; hosting migration; production certification.

### Scope-change rule

A change is permitted only to address (a) a demonstrated functional defect, (b) security/privacy risk, (c) an explicit supervisor requirement, or (d) a blocker to the agreed research evaluation. Record its reason, impact, test evidence, and approval in Section 15 before implementation. Ideas outside these categories go to **Future Work**.

## 5. Current implementation baseline (as of 4 Nov 2026)

| Component | Status | Evidence and qualification |
|---|---|---|
| React/Vite frontend | Implemented in existing project | Build PASS reported by Codex; independently verify on frozen commit |
| FastAPI backend + PostgreSQL | Running in Cloud Shell demo | API and local DB previously exercised; Cloud Shell persistence has been unreliable |
| Demo auth and CUSTOMER/AGENT/ADMIN roles | Implemented | Demo login and protected endpoints exercised; **not production authentication** |
| Customer private chat and tickets | Implemented | Automated tests PASS reported by Codex; cross-tenant populated-ticket cases still to verify |
| Customer asset/log retrieval | Implemented | Customer A/B test returned correct records; four cross-company asset/log requests returned HTTP 403 |
| Rule-based security analysis | Implemented | Manual Test 1 and Test 2 yielded grounded responses with cited log IDs |
| Knowledge Base citations | Implemented | Test responses cited KB-004 and KB-005; verify reference correctness separately |
| Gemini live inference | **Not yet demonstrated** | Both manual test responses explicitly stated Gemini was disabled |
| Comparative AI evaluation | **Not yet completed** | No validated benchmark or Method A/B comparison results yet |
| Production deployment/security | **Not claimed** | Mock auth and local demo environment are known limitations |

### Manual smoke-test evidence

**Test 1 — Company A suspicious login**
- Input: `SUSPICIOUS_LOGIN`, asset `a-web-01`, IP `192.0.2.10`.
- Observed: matched stored log ID `514af59d-abcb-4db1-a25c-ee14f3e38384`; returned MEDIUM with caution that login failures do not prove compromise; recommended investigating successful logins, MFA, and source IP.
- Qualification: risk severity is preliminary and not yet benchmark-validated.

**Test 2 — Company B port scan**
- Input: `PORT_SCAN`, asset `b-web-01`, IP `198.51.100.10`.
- Observed: matched stored log ID `a0244239-cdb8-40e9-ada5-595527512887`; returned MEDIUM, described possible reconnaissance vs. authorized scanning, and recommended checking ports and scanner authorization.
- Qualification: underlying log lacks full network context; cannot conclude successful intrusion.

**Isolation observation:** Four cross-company asset/log API requests returned HTTP 403. This is **not** proof that chat, ticket, Gemini prompts, and AI responses are fully tenant-safe.

**Reported automated test evidence:** Codex reported 60 offline tests, 11 PostgreSQL analysis tests, and 10 PostgreSQL login/chat/ticket tests passing, plus frontend build and Python compilation. Re-run and archive outputs at the baseline commit; do not represent unverified reports as independent verification.

## 6. Locked system architecture

```text
Customer / SOC Portal (React + Vite)
              |
        FastAPI Backend
              |
    Demo Auth + Role/Tenant Checks
              |
  Authorized Evidence Retrieval
     |          |           |
   Assets      Logs         KB
              |
      +-------+--------+
      |                |
 Method A          Method B
 Rule-Based        Gemini-Assisted
 (baseline)       (backend only)
      |                |
      +-------+--------+
              |
 Evidence Validation + Risk Policy
              |
 Incident Summary / Evidence / Risk /
 Recommended Actions / Missing Information
              |
       Chat / Optional Ticket
```

### Design invariants

- Tenant ID comes from authenticated/authorized server context, never trusted solely from user input or model output.
- Only retrieved, permitted evidence may be represented as confirmed fact.
- Gemini can interpret/synthesize but cannot invent assets, log IDs, events, or confirmed compromise.
- Hypotheses must be explicitly labeled; insufficient evidence permits `UNKNOWN`.
- Risk labels must follow an explicit, testable policy; the model must not silently override risk.
- Never expose API keys to frontend, logs, GitHub, or evaluation artifacts.
- Only synthetic or approved non-sensitive material may be sent to external model services.
- On Gemini error, timeout, quota, or invalid response, fail safely and fall back to baseline with visible disclosure.

## 7. Technology stack and environment

| Layer | Locked choice |
|---|---|
| Frontend | React + Vite |
| Backend | Python + FastAPI + Uvicorn |
| Database | PostgreSQL + SQLAlchemy |
| AI model | Gemini Developer API, backend-only, subject to successful key/quota testing |
| Existing KB | Reuse current KB implementation |
| Development | Google Cloud Shell, GCP project `tdg-sec-soc-nonprod` |
| Repository | GitHub `thassanawalai/true` |
| Demo | Existing working Cloud Shell ports 8000 (API), 5173 (frontend) |

**Secrets:** `.env` stays local and ignored by Git. Relevant names: `DATABASE_URL`, `DEMO_SESSION_SECRET`, `GEMINI_ENABLED`, `GEMINI_API_KEY`, `GEMINI_MODEL`. Never paste secret values into reports or chat.

**Backup note:** A PostgreSQL custom-format backup was previously created at `~/true/backups/itsm_demo_20261104_122719.dump`; its archive listing was checked, but a full restore has not been validated. Keep backups out of Git and rehearse restore if time allows.

## 8. Final AI methodology

### Method A — Rule-Based Baseline

- Current tenant-safe retrieval, incident classification/entity extraction, rule-based risk reasoning, evidence/hypothesis separation, KB-backed guidance.
- Freeze baseline version and record Git commit SHA before changes.
- Do not modify baseline scoring during evaluation unless a documented critical bug requires it; rerun both methods if changed.

### Method B — Gemini-Assisted Analysis

- Feed Gemini the same authorized synthetic case evidence available to Method A.
- Request structured output: incident type, entities, cited evidence IDs, hypotheses, missing information, rationale, recommended actions.
- Validate references against an allowlist of retrieved IDs; reject/strip unsupported claims.
- Apply the same explicit risk policy to both methods, or clearly disclose any methodological difference.
- Store safe evaluation metadata: model name, prompt version, run ID, latency, validation outcome, fallback flag, without secrets or private data.
- Treat external-model responses as untrusted; no tool execution or automated remediation from model text.

### Risk assessment policy — to finalize before evaluation

Specify a deterministic matrix using available evidence (e.g., asset criticality, authentication outcome, scope/volume, corroborating signals, verified impact). Use `UNKNOWN` when insufficient. Freeze policy version, document decision rules and test examples. **Do not claim that current MEDIUM outputs are calibrated.**

## 9. Evaluation design / ระเบียบวิธีทดลอง

### Dataset

- **Target:** 30 synthetic cases (initial feasible research set, not a statistically representative real-world SOC sample).
- Categories: Suspicious Login (6), Brute Force (5), Port Scan (5), Phishing (5), Unknown IP/Asset (4), Insufficient Evidence (5).
- Include normal/ambiguous examples, missing logs, conflicting evidence, and adversarial cross-tenant references where appropriate.
- Each case includes question, tenant, authorized assets/logs, expected label/entities, evidence references, expected uncertainty and risk where justified.
- Ground truth must be written **before** running either method, not copied from baseline predictions. Have a supervisor/SOC reviewer check a subset if possible; disclose if not.

### Controlled comparison

1. Freeze dataset, ground truth, rubric, risk policy, and baseline commit.
2. Run Method A on all cases.
3. Run Method B on exactly the same authorized cases with fixed model/prompt settings and record failures/fallbacks.
4. Save predictions, evidence IDs, scores, and latency to versioned JSON/CSV (synthetic only).
5. Report aggregate metrics and per-category breakdown; show representative success and failure examples.
6. Repeat model runs if quota/time permits; disclose variance and small sample size.
7. Separate **raw Gemini quality**, **post-validation displayed quality**, and **fallback outcomes** to avoid inflated scores.

### Metric definitions (finalize scoring rubric before run)

| Metric | Calculation / interpretation | Proposed target |
|---|---|---|
| Incident classification accuracy | Correct incident labels / all labeled cases; define UNKNOWN handling | ≥85% |
| Entity extraction precision, recall, F1 | Micro-averaged exact-match entities by type; report missing and extra entities | F1 ≥90% |
| Evidence grounding rate | Supported factual claims / all checkable factual claims; report zero-claim cases separately | ≥90% |
| Unsupported claim rate | Unsupported factual claims / all checkable factual claims; disclose overlap with grounding | ≤5% |
| Risk agreement | Correct risk labels / cases with adjudicated risk ground truth; report UNKNOWN separately | ≥80% |
| Tenant isolation pass rate | Passed explicitly defined negative/positive isolation tests / total isolation tests | 100% |
| Response latency | Median and P95 end-to-end latency; report timeouts and failures | Report actual |
| Action suitability (optional) | Rubric-scored relevance, safety, and completeness of recommendations | Report actual |

**Caution:** Grounding and unsupported-claim rate may be complements under a binary rubric; define neutral/unverifiable claims explicitly to avoid double counting. Report denominators and confidence limits, especially with only 30 cases. Do not invent results or claim statistical significance without a justified test.

## 10. Security and privacy test plan

- Customer A cannot read Company B assets or logs; Customer B cannot read Company A.
- Customers cannot read another company's tickets, private chat rooms, or messages.
- Internal staff must select an authorized company context when retrieving tenant data.
- Prompt injection and user-provided company IDs must not override server-side tenant scoping.
- AI prompts and responses must not contain unauthorized tenant-specific identifiers or records.
- Model-generated evidence IDs must match the retrieved authorized evidence allowlist.
- Invalid Gemini output, errors, timeouts, and quota exhaustion must not leak data or break baseline.
- Tests must use synthetic data and must not mutate the live demo DB.

## 11. Delivery phases and exit criteria

| Phase | Work | Exit criteria | State |
|---|---|---|---|
| 1 — Freeze & Verify | Record commit, backup, run backend/frontend tests, smoke-test A/B | Reproducible baseline, test log, rollback path | Pending independent verification |
| 2 — Gemini Integration | Backend-only Gemini, structured output, validator, fallback | Real inference verified on synthetic cases; regression passes | Not started/verified |
| 3 — Research Evaluation | Freeze dataset/rubric; run both methods | Machine-readable results, comparison, limitations | Not completed |
| 4 — Report & Defense | Align report, figures, demo, Q&A with measured findings | Demo and report make only supported claims | In progress |

### Working timeline (subject to confirmation)

- **4 Nov:** baseline freeze, backup, regression evidence.
- **5 Nov:** Gemini integration.
- **6 Nov:** validation, security tests, synthetic dataset/rubric.
- **7 Nov:** comparative evaluation and analysis.
- **8 Nov:** report, slides, demo rehearsal.
- **9 Nov:** target presentation.

**Priority when time is insufficient:** preserve working baseline → ensure no privacy leak → produce honest measured results → complete report. Defer optional features. Never conceal a failed test.

## 12. Definition of Done / เกณฑ์ส่งมอบ

- [ ] Frozen baseline commit SHA and rollback instructions recorded.
- [ ] Backend, frontend, and relevant PostgreSQL tests rerun with saved output.
- [ ] Two existing manual cases reproducibly pass with authorized evidence.
- [ ] Gemini real inference confirmed, with model/version and prompt settings recorded.
- [ ] Evidence validation, tenant isolation, fallback, and regression tests pass.
- [ ] Dataset and ground truth are independently defined and versioned.
- [ ] Method A/B comparison completed with actual scores and denominators.
- [ ] Findings, limitations, failures, and threats to validity documented.
- [ ] Demo runs from customer report to evidence-based answer and optional ticket.
- [ ] Academic report and presentation match verified implementation and experiments.

## 13. Research report mapping / โครงร่างรายงานสหกิจ

| Report section | Reuse from this document | Additional evidence required |
|---|---|---|
| Chapter 1 — Introduction | Problem, objectives, scope, expected contribution | Organization context, approved objectives, citations |
| Chapter 2 — Theory and related work | Multi-tenant systems, incident analysis, LLM grounding, evaluation | Properly verified academic references and related research |
| Chapter 3 — Methodology | Architecture, data flow, methods A/B, dataset, metrics, safety | Final diagrams, schemas, exact test procedure |
| Chapter 4 — Results | Test cases, metrics, comparison, security tests | Actual run logs, charts, tables, screenshots |
| Chapter 5 — Conclusion | Findings, limitations, future work | Discussion based strictly on measured results |

**Writing rule:** distinguish planned design from implemented functionality and experimentally demonstrated outcomes. Cite external sources accurately; do not invent references or experimental data.

## 14. Presentation outline (suggested 10–12 slides)

1. Project title and motivation.
2. SOC workflow pain point and research gap.
3. Research questions, objectives, measurable KPIs.
4. Scope and system architecture.
5. Tenant-safe evidence retrieval and privacy model.
6. Rule-based baseline (Method A).
7. Gemini-assisted approach (Method B) and evidence validation.
8. Dataset, ground truth, evaluation design.
9. Quantitative comparison and latency (real results only).
10. Security/tenant isolation test results.
11. Live demo: Customer A/B → analysis → optional ticket.
12. Limitations, contribution, conclusion, future work.

**Likely defense questions:** Why Gemini vs rules? How do you detect hallucinations? Why is risk MEDIUM? How do you prevent cross-tenant leakage? How are ground truths established? What did the developer design and verify when using Codex? What fails when Gemini is unavailable?

## 15. Change control and decision log

### Change request template

```markdown
### CR-YYYYMMDD-NN — Short title
- Requested by:
- Date:
- Reason: [verified bug / security / supervisor requirement / evaluation blocker]
- Evidence:
- Files/modules affected:
- Impact on scope, schedule, research validity:
- Alternatives considered:
- Decision: [approve / reject / defer]
- Approved by:
- Tests required:
- Result and commit SHA:
- Document version updated:
```

### Initial decisions

| Date | Decision | Reason |
|---|---|---|
| 2026-11-04 | Freeze React/FastAPI/PostgreSQL and existing ITSM workflow | Preserve 4 months of work and minimize regression |
| 2026-11-04 | Use Gemini pretrained model; no fine-tuning | Allowed by supervisor; fits time and infrastructure |
| 2026-11-04 | Compare Method A vs Method B on synthetic evidence | Required to substantiate Applied AI Research contribution |
| 2026-11-04 | Require tenant-safe retrieval and evidence validation | Protect data separation and prevent unsupported conclusions |
| 2026-11-04 | Defer UI redesign, new SIEM integration, and production auth | Out of research scope and high schedule risk |

## 16. Known risks and mitigation

| Risk | Mitigation |
|---|---|
| Gemini key, quota, timeout, or permission unavailable | Baseline fallback; record blocked AI evaluation honestly |
| Model invents facts/log IDs | Evidence allowlist, claim validation, structured outputs, failure tests |
| Tenant data leakage | Server-side tenant authorization, adversarial API/chat/AI tests |
| Small synthetic dataset overstates performance | Report sample size, category breakdown, limits on generalization |
| Risk scores appear arbitrary | Publish deterministic risk policy and examples; UNKNOWN when insufficient |
| Cloud Shell DB resets or service stops | Backups outside Git, smoke-test script, verify restore if possible |
| Codex changes working code unexpectedly | Freeze commit, small PR/commit changes, regression tests, rollback |
| Deadline pressure | No new features; prioritize research evidence and working demo |

## 17. Future work (not part of current scope)

- Production-grade authentication, MFA, audit hardening and secret management.
- Live SIEM/SOAR integration and richer event correlation.
- Larger expert-reviewed datasets and multi-run statistical evaluation.
- Real-world deployment hardening, availability monitoring and tested disaster recovery.
- Extended risk calibration and human-in-the-loop SOC feedback.

## 18. Verification register / หลักฐานที่ต้องแนบภายหลัง

| Evidence ID | Required artifact | Status |
|---|---|---|
| EV-01 | Baseline Git commit SHA, branch, clean status | Pending |
| EV-02 | Backend/frontend/PostgreSQL test logs | Pending rerun |
| EV-03 | Test 1/2 response captures | User provided text; archive securely |
| EV-04 | Cross-tenant API test output | Previously observed; archive reproducible script |
| EV-05 | Gemini live inference and fallback traces | Pending |
| EV-06 | Dataset, ground truth, scoring rubric | Pending |
| EV-07 | Method A/B raw and validated results | Pending |
| EV-08 | Results tables and research discussion | Pending |
| EV-09 | Demo rehearsal checklist and screenshots | Pending |
| EV-10 | Supervisor confirmation of title/objectives/date | Pending |

---

## 19. Document maintenance policy

- This file is the authoritative **plan**, not a substitute for source code or test artifacts.
- Keep status and results current after every completed phase.
- Update version, date, change log, and evidence references in the same commit as any approved material scope change.
- Use semantic versions: patch for wording/evidence links; minor for approved method/schedule changes; major only for supervisor-approved scope reset.
- Never silently rewrite historical results. Append corrected observations with date and reason.
- Keep secrets, real customer logs, personal data, and database dumps out of GitHub.
- Any claims used in the report or slides must trace to a test result, code artifact, or cited source.

**Final principle:** Preserve the working system. Demonstrate what the AI contributes. Measure honestly. Finish with a defensible, reproducible Applied AI Research result.
