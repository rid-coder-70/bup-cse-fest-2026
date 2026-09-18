# GridWise API Testing Guide

This guide tests the service through the public HTTP contract, not only by calling internal Python functions.

## 1. Start the service

```bash
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The service must expose:

- `GET /health`
- `POST /optimize-energy`

## 2. Health test

```bash
curl --fail-with-body http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok"}
```

## 3. Send a public sample

The following command sends the first supplied sample case and prints the important response fields:

```bash
curl --fail-with-body \
  -X POST http://127.0.0.1:8000/optimize-energy \
  -H 'content-type: application/json' \
  --data-binary "$(python -c 'import json; print(json.dumps(json.load(open("BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json"))["cases"][0]["input"]))')" \
| python -m json.tool
```

Expected response properties:

```text
scenario_id = SAMPLE-01
directive_interpretation has 2 entries
hourly_plan has 24 entries
total_cost_bdt is 38365 within tolerance
total_grid_kwh, total_cost_bdt, and peak_grid_kwh match the plan
```

## 4. FastAPI TestClient test

`TestClient` runs the FastAPI application in-process and is ideal for contract tests:

```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
response = client.get("/health")
assert response.status_code == 200
assert response.json() == {"status": "ok"}
```

For optimization tests, post a complete scenario dictionary:

```python
response = client.post("/optimize-energy", json=payload)
assert response.status_code == 200
body = response.json()
assert body["scenario_id"] == payload["scenario_id"]
assert len(body["directive_interpretation"]) == len(payload["operator_notes"])
assert len(body["hourly_plan"]) == 24
```

## 5. What every response test must verify

### Contract

- HTTP status is `200` for a valid scenario.
- `scenario_id` is echoed exactly.
- One interpretation entry exists per operator note.
- Interpretation entries are ordered by `note_index`.
- Every hourly plan entry exists exactly once for hours `0` through `23`.
- `battery_action` is `charge`, `discharge`, or `idle`.

### Directive semantics

- `no_op` means `applies=false` and `structured_adjustment=null`.
- Every active directive means `applies=true`.
- Directive hours are sorted, unique, and between `0` and `23`.
- Solar reduction uses remaining fraction, not reduction percentage.
- Time windows are start-inclusive and end-exclusive.

### Independent schedule replay

For every hour, recalculate:

```text
grid_kwh + solar_used_kwh + discharge_kwh
    == demand_kwh + charge_kwh
```

Then verify battery state, capacity, reserve, rate limits, solar limits, directive windows, grid caps, totals, and final battery neutrality. The production endpoint already performs this replay before returning; tests should still check the returned JSON externally.

## 6. Negative API tests

These requests must be rejected with `400` or `422`:

- Missing `hours` entries
- Duplicate hour numbers
- An hour outside `0..23`
- Empty operator notes
- More than three notes
- Negative demand, solar, tariff, or battery values
- Initial battery energy above capacity
- Minimum reserve above capacity
- Malformed JSON

A malformed model response must never produce a `500` containing a raw stack trace or secret.

## 7. Test layers

1. **Unit tests:** guardrail validation, time parsing, directive normalization, and replay arithmetic.
2. **Contract tests:** `/health`, request validation, response shape, status codes.
3. **Scenario tests:** the public samples and the hidden-style cases in `tests/data/hidden_style_cases.json`.
4. **Property tests:** randomized non-negative demand/solar/tariff values with feasible battery settings.
5. **Performance tests:** repeat valid requests and measure p95. The target is under 5 seconds.
6. **Deployment tests:** build Docker, start it on port 8000, and call `/health` from outside the container.

## 8. Commands

```bash
# All automated tests
pytest -q

# Only hidden-style API tests
pytest -q tests/test_hidden_style_cases.py

# Verbose failures
pytest -q -vv

# Basic latency sample while the server is running
for i in $(seq 1 20); do
  curl -s -o /dev/null -w '%{time_total}\n' http://127.0.0.1:8000/health
done
```

For a real p95 measurement, use a load tool such as `hey` or `wrk` against a representative `POST /optimize-energy` request. Do not benchmark with production secrets in shell history.

## 9. Test completion checklist

- All public and hidden-style scenarios return `200`.
- Every returned schedule passes independent replay.
- The expected directive type, hours, and numeric values match.
- Invalid requests are controlled failures.
- No response exposes model keys, prompts containing secrets, or stack traces.
- Docker startup and `/health` work from a clean environment.
- p95 stays within the competition target and repeated requests remain stable.
