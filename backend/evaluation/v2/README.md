# SOC evaluation v2 — implementation and current limits

This is a **pilot coverage suite**, not a claim of 100% accuracy or a complete acceptance run.
It assesses the delivered answer including fallback. A successful Gemini HTTP call is not an answer-quality pass.

## What is implemented

- 100 scenarios / 130 responses: KB 25, LIST 15, ANALYSIS 25, MULTITURN 15 × 3 turns, EDGE 10, ACCESS 10.
- Reuses existing `soc-live100-v1` fixtures. Does not delete or reinsert Neon data.
- Separate 100-case legacy regression and 12 injected-failure scenarios / 16 responses.
- Independent field/type/evidence-set checks and rendered account/IP/count tuple checks, including contradictory extra tuples.
- Six rubric dimensions, required/critical assertions, score bounds, and `pass / fail / pending` outcomes.
- Raw response is committed to SQLite before grading. Resume never repeats a reserved POST.
- One active runner, HTTPS, 60-second post-response delay, 300-second pause every 10 requests.
- All fallback and ordinary content failures continue. Confirmed tenant leaks pause. Provider 429 backs off; local quota, auth and configuration faults pause.
- Chat-room response metadata includes citations, scope, origin and provider status from that same call.
- Judge packets, strict result validation, 40 synthetic calibration examples split by KB family, confusion-matrix utility.

## Not yet completed

- Authenticated Render/Neon/Gemini execution requires test account sessions. No credentials are bundled.
- Judge inference/calibration and a trusted reference review have not run. `judge.py` prepares packets; `judge_runner.py` can run bounded calibration on synthetic answers only. Live-answer judge inference is not implemented.
- Inventory exact-row oracle needs an independent frozen database snapshot. Basic inventory-format checks cannot prove exact completeness.
- Browser E2E has not run. ASGI TestClient results are API results, not DOM verification.
- A separate frozen acceptance set is still needed. Pilot cases used to fix bugs are development evidence.
- No automatic retries are currently implemented; uncertain requests are preserved and skipped after operator review.
- Run budget is conservative app-request accounting; other production users and external judge calls must fit within the same project quota.
- Existing temporary chat rooms may contain earlier context. The runner does not delete rooms or force a clean conversation. Persisted room IDs are retained; an expired context is a failure, not silently recreated.
- The 12 fault scenarios cover all requested routes, but not every route × failure combination.

## Run offline

From `backend/`, using the repository virtual environment:

```bash
PYTHON_DOTENV_DISABLED=1 DATABASE_URL=sqlite:////tmp/soc-eval-unused.sqlite \
python -m evaluation.v2.offline --output ./evaluation-output/offline-v2
python -m unittest discover -s tests -p 'test_evaluation_v2.py' -v
```

Offline uses an isolated SQLite database, the actual API routes and a mocked SDK. External sockets are disabled by the fixture. All generated IDs and passwords are synthetic. Production data is never modified.

## Live pilot then remaining cases

After deploying the instrumentation/fixes, from `~/true/backend`:

```bash
python -m evaluation.v2.runner \
  --url https://soc-itsm-ai-demo.onrender.com \
  --output ./evaluation-output/live-v2 \
  --actors a1 --limit 5
```

Passwords are requested with `getpass`, never command-line arguments or output files.
Use the same output directory to resume. `--limit` is the number of **new response requests**, not scenarios. The old `evaluation-state.sqlite` is a different format and must not be reused for v2.

After inspecting the pilot, include all roles and collect the remaining responses:

```bash
python -m evaluation.v2.runner \
  --url https://soc-itsm-ai-demo.onrender.com \
  --output ./evaluation-output/live-v2 \
  --actors a1,a2,b1,support,admin --limit 130 --budget 150
```

Do not run alongside the v1 runner or other evaluation jobs. Credentials can also be supplied securely as `SOC_EVAL_TOKEN_A1`, `SOC_EVAL_TOKEN_A2`, `SOC_EVAL_TOKEN_B1`, `SOC_EVAL_TOKEN_SUPPORT`, `SOC_EVAL_TOKEN_ADMIN`; never paste them in chat. Only a missing-session case is blocked; it is not counted as passed. The runner revalidates `/api/demo-auth/me`.

`Ctrl+C`: restart with the same directory. If interrupted during POST, review the saved `in_flight` entry; `--resume-reviewed` skips that uncertain attempt permanently rather than silently retrying it. Reports retain this gap.

## Score semantics later without new application calls

```bash
python -m evaluation.v2.judge \
  --responses ./evaluation-output/live-v2/responses.jsonl \
  --output ./evaluation-output/live-v2/judge
```

This only produces evaluation packets and synthetic calibration references; it consumes zero API calls. Free text remains pending until a judge has been calibrated and its evidence-bound output validated. An arbitrary `calibration_status=validated` string is not a calibration certificate; do not directly call the scorer with untrusted judge results.

## Evidence and interpretation

`state.sqlite` is the durable live source of truth; `responses.jsonl`, `assertions.csv` and `report.json` are exports.
Offline output has separate `responses.jsonl`, `faults.jsonl`, `legacy.jsonl`, frozen manifest and report.
Never add regression test-method counts to scenario counts. Never combine injected failures with natural fallback frequency. Never infer production latency from mocked SDK latency. `pending` does not mean wrong or right, and is never a pass.

## Optional synthetic judge calibration

Use `python -m evaluation.v2.judge_runner --output ./evaluation-output/judge-calibration --limit 5` after securely configuring `SOC_JUDGE_API_KEY` and `SOC_JUDGE_MODEL` in the runtime. It only transmits authored synthetic answers and public KB excerpts; never live transcripts. Use the same directory to resume, with at most 40 total calibration answers and at most 50 requests per rolling day. A missing/uncertain result stays pending. It reports development/holdout confusion matrices, but never automatically certifies the judge because the reference labels have not been reviewed independently. Do not run it concurrently with application tests.
