# Login pilot API evaluation

Run from repository root with backend dependencies and httpx installed:

```sh
python3 backend/evaluation/login_pilot/run_api.py /tmp/new-pilot-results
```

The runner creates a temporary SQLite database, seeds ten isolated synthetic tenants,
logs in through the actual FastAPI endpoint, and calls /api/customer-data/ask.
Gemini is disabled. Output includes raw requests, raw responses, item scores and CSV.
Counts are scored from login_activity; conclusion and advice checks recognize the
current deterministic renderer's phrases. These are regression checks for a synthetic
pilot, not an independent LLM judge or a representative production accuracy estimate.

LOG-006 transports the source event ID explicitly as event_id=E01 in the stored
message. Database UUIDs represent storage rows. Unique events are counted per
collector, asset and explicit source event ID. Missing source IDs yield unknown,
rather than assuming each storage row is a unique source event.
The other input fields remain separate from ground truth.

The explicit Thai time range in LOG-005 has one calendar date and timezone +07:00.
“ถึงก่อน” excludes the end boundary; “ถึง” includes it. Existing timestamp-only
queries retain their surrounding search window.
