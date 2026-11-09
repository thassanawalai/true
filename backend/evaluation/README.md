# Minimal research evaluation v1

This is a synthetic experiment harness, not a completed empirical Gemini study.
`cases_v1.json` contains **exactly 30 evaluation cases**, separate from the four
unchanged Phase 2 smoke cases. There are 6 login, 6 scan, 6 malware-related,
6 benign/adjudicated and 6 uncertain cases; 15 belong to each synthetic tenant.
This distribution supersedes the proposed distribution in the plan for this
minimal run, per the Phase 3 request to include malware and benign cases.

## Dataset and independent annotations

Each case includes the approved input package and **separate** ground truth:
incident type, expected risk, expected log evidence IDs and rationale. Annotations
were authored from the scenario descriptions before running A or B, not copied
from baseline/model predictions. They have NOT been independently reviewed by a
human SOC analyst. “Independent” here means independent of method execution, not
independent expert adjudication. The small, deliberately authored sample is not
representative of SOC traffic; no statistical significance/generalization claim.

The input file has a pinned SHA-256 in `catalog.py`. Any edit fails closed until
review and explicit digest update. The runner never accepts arbitrary customer
files, never reads the demo DB, and never exports annotations to Gemini. Input
packages contain only deterministic synthetic IDs, reserved documentation IPs,
synthetic timestamps/assets/events. KB is empty in this corpus to control inputs;
existing approved-KB behavior remains tested by the original suite.

Label mapping:

- Failed login and brute force map to `suspicious_login` (existing shared ontology).
- Port scanning maps to `port_scan`; malware detections to `malware`; ransomware
  to `ransomware`; phishing reports to `phishing`.
- Routine health/maintenance/backup and unspecified/unknown-IP reports map to
  `unknown_security_issue`. There is no separate BENIGN output label.
- Known-benign/false-positive login/scan/malware scenarios retain the reported
  incident category but expect no unresolved supporting incident evidence and
  UNKNOWN risk. Expected evidence means **relevant unresolved incident support**,
  not merely any stored alert or evidence that an activity was benign.

Risk annotation: UNKNOWN for missing/mismatched/explicitly benign or resolved
false-positive evidence; MEDIUM for unresolved login/scan/malware alerts; HIGH for
ransomware alerts. None implies confirmed compromise. These are provisional
scenario-level labels, not calibrated severity. Existing A/B policy uses event
labels/findings and cannot express LOW, account for volume/criticality, or reliably
interpret benign qualifiers. R16 intentionally contains competing login/ransomware
terms. These limitations are exposed by scoring, not corrected in either method.

## Execution

From repository root (Python dependencies already installed):

```bash
PYTHONWARNINGS=ignore backend/.venv/bin/python -B backend/scripts/test_phase_ab_offline.py
PYTHONWARNINGS=ignore backend/.venv/bin/python -B backend/scripts/evaluate_research.py --mode mock --output /tmp/soc-eval-mock-run1
PYTHONWARNINGS=ignore backend/.venv/bin/python -B backend/scripts/evaluate_research.py --mode baseline --output /tmp/soc-eval-baseline-run1
```

Each output path must be new. The runner exports `results.json`, `results.csv`
and `summary.md`. The JSON contains per-case metadata/predictions, aggregate and
category metrics, ground truth and A/B input hashes. CSV nested values are JSON
strings. Failed B output is never replaced by A for B scoring; the original
experiment's labeled fallback remains available in its result object.

Live is **never automatic**. The operator must export the existing provider's
`GEMINI_ENABLED=true`, `GEMINI_API_KEY`, and `GEMINI_MODEL` securely, then explicitly run:

```bash
PYTHONWARNINGS=ignore backend/.venv/bin/python -B backend/scripts/evaluate_research.py --mode live --enable-live --output /tmp/soc-eval-live-run1
```

No `.env` is loaded. Do not paste credentials in command arguments or artifacts.
Live may make up to 30 provider attempts and consume quota. No retry loop is added.
Without both the flag and valid provider configuration the CLI refuses to run.
Mock/baseline disable Gemini and block outbound sockets. Baseline mode records B
as skipped. No application database connection or migration is performed.

Both methods use existing `run_case` and `input_sha256`. A executes its unchanged
analyzer on an in-memory snapshot; B receives the identical raw package, not A's
answers. A/B input mismatch aborts evaluation rather than reporting comparison.
The catalog registration is the only change to the experiment service: existing
A and B logic, validation, risk policy and smoke cases are preserved.

## Metrics and denominators

- **Classification accuracy / risk agreement:** correct / successfully returned
  predictions, with scored/total and outcome counts alongside. B fallback,
  timeout, validation failure, skipped and execution errors are excluded from the
  successful-B denominator. Correct classification / all cases is also reported
  as coverage-aware yield, not mislabeled prediction accuracy.
- **Evidence precision/recall/F1:** micro TP/FP/FN using selected vs expected log-ID
  sets across successful predictions. Also report exact evidence-set accuracy.
  Empty denominators are JSON null / empty CSV, never automatically perfect scores.
- **Unsupported-claim rate:** explicitly limited automated structural proxy: one
  unit per log reference plus one factual-summary unit per response with claims.
  A's structured finding fields are compared with input records; B's summary is
  checked against the approved extractive factual strings. A nonempty invented
  summary without evidence still counts as a claim unit. Unsupported units / total
  units; zero-claim cases give null rate. This does not measure human semantic
  entailment, action suitability, or free-form reasoning. Incident class and risk
  are measured separately. Irrelevant but authentic evidence hurts retrieval
  precision, not factual-grounding rate.
- **Raw vs displayed B:** raw structurally scorable output has separate counters,
  including rejected claims; malformed/missing output is unscorable, not “0% wrong”.
  Invalid raw text is never persisted; only counters and failure codes are saved.
  Displayed successful B grounding is constrained by validation and therefore must
  not be presented as raw model accuracy or proof of absence of hallucination.
- **Tenant isolation:** count cases containing the other synthetic tenant's host,
  IP, asset/collector/log IDs in provider context or displayed result; raw provider
  leakage is counted separately. These are finite canary checks, not a universal
  privacy guarantee. Endpoint auth regressions separately test foreign case IDs,
  forged company selection and missing/internal auth context with synthetic users.
- **Latency:** median and nearest-rank P95 of all attempted wrapper executions,
  including failures/fallback; skipped rows have null latency. Includes A's SQLite
  construction and fallback work. Mock latency is not live model latency.

Mock B deliberately chooses the first recognized event, ignores question semantics,
and injects an unsupported summary (R08), timeout (R16), provider failure (R24), and
malformed JSON (R30). It never reads ground truth. Its scores demonstrate plumbing
and failure accounting only; they provide **no empirical evidence of Gemini quality**.

Repeated runs retain stable dataset/input hashes and deterministic mock predictions;
run IDs/latencies vary. Freeze data, annotations and rubric before live runs. Preserve
failures and do not tune validation or ground truth against observed scores.
