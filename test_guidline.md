# GridWise FastAPI Testing Guideline

This document explains how to test the GridWise API, how to send sample requests, how to inspect responses, and how to validate public and hidden-style cases.

## 1. API Contract

Base URL for local testing:

```text
http://127.0.0.1:8000
```

### Health endpoint

```http
GET /health
```

Expected response:

```json
{"status":"ok"}
```

### Optimization endpoint

```http
POST /optimize-energy
Content-Type: application/json
```

The request contains:

- `scenario_id`: string
- `operator_notes`: 1 to 3 natural-language notes
- `hours`: exactly 24 records for hours `0` through `23`
- `battery`: capacity, initial state, reserve, and charge/discharge limits

The response contains:

- `scenario_id`
- `directive_interpretation`: exactly one item per operator note
- `hourly_plan`: exactly 24 items
- `total_grid_kwh`
- `total_cost_bdt`
- `peak_grid_kwh`
- `plan_summary`

## 2. Start the Service

Use the project virtual environment:

```bash
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another terminal, verify readiness:

```bash
curl -i http://127.0.0.1:8000/health
```

Expected status and body:

```text
HTTP/1.1 200 OK
```

```json
{"status":"ok"}
```

Do not put a real model key in `.env.example`, tests, documentation, or Git. Use `.env`, which is ignored by Git. The local deterministic fallback is sufficient for the included tests.

## 3. Get a Public Sample Response

The public case file already contains request objects under `.cases[].input`. Send the first case directly:

```bash
curl -sS -X POST http://127.0.0.1:8000/optimize-energy \
  -H 'Content-Type: application/json' \
  --data-binary "$(.venv/bin/python -c 'import json; print(json.dumps(json.load(open("BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json"))["cases"][0]["input"]))')" \
  | .venv/bin/python -m json.tool
```

Print only the important response fields:

```bash
curl -sS -X POST http://127.0.0.1:8000/optimize-energy \
  -H 'Content-Type: application/json' \
  --data-binary "$(.venv/bin/python -c 'import json; print(json.dumps(json.load(open("BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json"))["cases"][0]["input"]))')" \
  | .venv/bin/python -c 'import json,sys; d=json.load(sys.stdin); print({k:d[k] for k in ("scenario_id","total_grid_kwh","total_cost_bdt","peak_grid_kwh")}); print("directives:", d["directive_interpretation"]); print("plan rows:", len(d["hourly_plan"]))'
```

A valid `SAMPLE-01` response must contain:

```json
{
  "scenario_id": "SAMPLE-01",
  "total_grid_kwh": 2692.5,
  "total_cost_bdt": 38365.0,
  "peak_grid_kwh": 175.0
}
```

The complete response also contains two directive entries and 24 hourly-plan entries. The action sequence does not have to equal the reference byte-for-byte. Any valid schedule with equivalent optimal cost is accepted.

## 4. Response Validation Rules

For every successful response, check:

```text
status code == 200
scenario_id equals the request scenario_id
len(directive_interpretation) == len(operator_notes)
note_index values are 0, 1, ..., N-1
len(hourly_plan) == 24
hour values are 0, 1, ..., 23
```

For every directive:

```text
no_op => applies is false and structured_adjustment is null
non-no_op => applies is true and structured_adjustment is not null
hours are unique, sorted, and between 0 and 23
```

For every hourly plan row:

```text
grid_kwh >= 0
solar_used_kwh >= 0
battery_kwh >= 0
battery state stays within reserve and capacity
battery action agrees with battery_kwh
```

Energy balance must hold within the official tolerance:

```text
grid_kwh + solar_used_kwh + battery_discharge_kwh
    == demand_kwh + battery_charge_kwh
```

The final battery state must equal the initial battery state.

Totals must be recalculated from `hourly_plan`:

```text
total_grid_kwh = sum(grid_kwh)
total_cost_bdt = sum(grid_kwh * tariff_bdt_per_kwh)
peak_grid_kwh = max(grid_kwh)
```

## 5. Run the Automated Tests

Run all tests:

```bash
.venv/bin/pytest -q
```

Run only the public cases:

```bash
.venv/bin/pytest -q tests/test_core.py
```

Run only hidden-style paraphrase cases:

```bash
.venv/bin/pytest -q tests/test_hidden_style_cases.py
```

The expected final result is currently:

```text
15 passed
```

The test suite includes:

- health endpoint validation
- all ten public cases
- ten hidden-style natural-language cases
- malformed request handling
- directive interpretation checks
- optimizer and replay validation
- 24-hour response shape checks

## 6. Public Test Cases and Correct Expected Results

The following values come from the supplied public reference file. Directive hours use start-inclusive/end-exclusive semantics.

| Case | Expected directive interpretation | Expected grid kWh | Expected cost BDT | Expected peak grid kWh |
|---|---|---:|---:|---:|
| SAMPLE-01 | solar reduction `[12,13]`, factor `0.25`; note 1 `no_op` | 2692.5 | 38365 | 175 |
| SAMPLE-02 | no charge `[2,3,4]` | 2915 | 42885 | 180 |
| SAMPLE-03 | minimum reserve `[18,19,20]`, 100 kWh | 2430 | 35480 | 205 |
| SAMPLE-04 | no discharge `[18,19]` | 2645 | 40495 | 225 |
| SAMPLE-05 | grid cap `[18,19,20]`, 155 kWh | 2430 | 33950 | 175 |
| SAMPLE-06 | solar reduction `[10,11]`, factor `0.5`; no charge `[14,15]`; note 2 `no_op` | 2395 | 34090 | 175 |
| SAMPLE-07 | reserve `[18,19,20,21]`, 90 kWh; grid cap `[19,20]`, 180 kWh | 2560 | 38550 | 185 |
| SAMPLE-08 | no charge `[11,12]`; no discharge `[17,18]` | 2490 | 37665 | 210 |
| SAMPLE-09 | solar reduction `[11,12,13]`, factor `0.2`; note 1 `no_op` | 2504 | 34873 | 170 |
| SAMPLE-10 | reserve `[18,19,20,21]`, 80 kWh; grid cap `[19,20,21]`, 190 kWh; note 2 `no_op` | 2715 | 41620 | 190 |

Important: the exact hourly plan can differ from the reference schedule. The judge accepts an equivalent valid optimum, not only one exact action sequence.

## 7. Print All Public Expected Output Summaries

Use this command to inspect every reference response summary:

```bash
.venv/bin/python - <<'PY'
import json

pack = json.load(open("BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json"))
for case in pack["cases"]:
    expected = case["expected_output"]
    print(case["id"])
    print("  directives:", expected["directive_interpretation"])
    print("  total_grid_kwh:", expected["total_grid_kwh"])
    print("  total_cost_bdt:", expected["total_cost_bdt"])
    print("  peak_grid_kwh:", expected["peak_grid_kwh"])
    print("  hourly_plan_rows:", len(expected["hourly_plan"]))
PY
```

To print the complete expected JSON for one case:

```bash
.venv/bin/python - <<'PY'
import json
pack = json.load(open("BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json"))
case = pack["cases"][0]
print(json.dumps(case["expected_output"], indent=2))
PY
```

## 8. Hidden-Style Test Cases

These are local hidden-style cases, not the organizer's private judge cases. They test paraphrase robustness and should not be hard-coded by case ID in the application.

| Case | Notes and expected interpretation |
|---|---|
| HIDDEN-01 | `The inverter will leave only 30% of forecast PV from 09:00 to 11:00.` -> `solar_reduction`, hours `[9,10]`, factor `0.3` |
| HIDDEN-02 | `Charging must remain unavailable between 03:00 and 06:00.` -> `no_charge_window`, hours `[3,4,5]` |
| HIDDEN-03 | `Keep a 180 kWh emergency reserve from 6 PM until 9 PM.` -> `minimum_battery_reserve`, hours `[18,19,20]`, reserve `180` |
| HIDDEN-04 | `During relay diagnostics, battery discharge is forbidden from 7 PM to 10 PM.` -> `no_discharge_window`, hours `[19,20,21]` |
| HIDDEN-05 | `Substation intake is limited to 140 kWh between 5 PM and 7 PM.` -> `max_grid_window`, hours `[17,18]`, cap `140` |
| HIDDEN-06 | `The campus newsletter is delayed until tomorrow.` -> `no_op` |
| HIDDEN-07 | `Heavy cloud means about half the expected solar from 1 PM to 3 PM.` and `The charging equipment is offline from 2 PM until 4 PM.` -> solar factor `0.5` at `[13,14]`; no charge `[14,15]` |
| HIDDEN-08 | `Maintain at least 60% battery state from 8 PM to 11 PM.` -> reserve `180` kWh, hours `[20,21,22]`, because capacity is 300 kWh |
| HIDDEN-09 | `An 80 percent solar reduction is expected from 10 AM through noon.`; `Do not use battery discharge from 6 PM until 8 PM.`; one distractor -> solar factor `0.2` at `[10,11]`; no discharge `[18,19]`; `no_op` |
| HIDDEN-10 | Grid cap 170 at `[18,19,20]`; reserve 100 at `[18,19,20,21]`; solar factor 0.25 at `[12,13]` |

The hidden-style request generator uses:

```json
{
  "demand_kwh": 100,
  "solar_kwh": 120,
  "tariff_bdt_per_kwh": 30,
  "battery": {
    "capacity_kwh": 300,
    "initial_energy_kwh": 100,
    "minimum_energy_kwh": 20,
    "max_charge_kwh_per_hour": 100,
    "max_discharge_kwh_per_hour": 100
  }
}
```

The actual reusable hidden-style data is stored in [tests/data/hidden_style_cases.json](tests/data/hidden_style_cases.json).

## 9. Manual Hidden-Style API Test

Send one hidden-style scenario through the real endpoint:

```bash
.venv/bin/python - <<'PY' > /tmp/gridwise-hidden-request.json
import json
from pathlib import Path
from tests.test_hidden_style_cases import scenario_for

case = json.loads(Path("tests/data/hidden_style_cases.json").read_text())[0]
print(json.dumps(scenario_for(case)))
PY

curl -sS -X POST http://127.0.0.1:8000/optimize-energy \
  -H 'Content-Type: application/json' \
  --data-binary @/tmp/gridwise-hidden-request.json \
  | .venv/bin/python -m json.tool
```

Expected key interpretation for HIDDEN-01:

```json
{
  "scenario_id": "HIDDEN-01",
  "directive_interpretation": [
    {
      "note_index": 0,
      "applies": true,
      "directive_type": "solar_reduction",
      "structured_adjustment": {
        "hours": [9, 10],
        "factor": 0.3
      }
    }
  ]
}
```

The response also contains a valid 24-row `hourly_plan`. Its exact values may differ from another optimal solution, so validate constraints and totals instead of comparing the entire response as a raw string.

## 10. Negative API Tests

### Missing required fields

```bash
curl -i -X POST http://127.0.0.1:8000/optimize-energy \
  -H 'Content-Type: application/json' \
  -d '{"scenario_id":"BAD"}'
```

Expected status: `400` or `422`.

### Wrong number of hours

```bash
curl -i -X POST http://127.0.0.1:8000/optimize-energy \
  -H 'Content-Type: application/json' \
  -d '{"scenario_id":"BAD","operator_notes":["hello"],"hours":[],"battery":{"capacity_kwh":1,"initial_energy_kwh":0,"minimum_energy_kwh":0,"max_charge_kwh_per_hour":1,"max_discharge_kwh_per_hour":1}}'
```

Expected status: `422` and no traceback in the response.

### Malformed JSON

```bash
curl -i -X POST http://127.0.0.1:8000/optimize-energy \
  -H 'Content-Type: application/json' \
  -d '{not-json}'
```

Expected status: `400` or `422`.

## 11. External LLM Testing

For local tests, leave the model key unset or use placeholder values. The service then uses the deterministic fallback and tests remain repeatable.

For an external OpenAI-compatible provider, use a private `.env` file:

```env
MODEL_API_URL=https://provider.example/v1/chat/completions
MODEL_API_KEY=real_key_only_in_local_env
MODEL_NAME=provider-model-name
MODEL_TIMEOUT_SECONDS=12
```

Test provider behavior separately from API correctness. A provider timeout, 404, invalid JSON response, or rate limit must not produce a schedule based on unvalidated model output. The service should fall back safely or return a controlled error.

Never print the key when debugging. Never commit `.env`.

## 12. Testing Checklist

Before submission:

- [ ] `/health` returns HTTP 200 and `{"status":"ok"}`.
- [ ] Valid requests return HTTP 200.
- [ ] Invalid requests return controlled `400` or `422` responses.
- [ ] Every note has exactly one interpretation entry.
- [ ] All supported directive types are tested.
- [ ] Distractor notes become `no_op`.
- [ ] Time windows use start-inclusive/end-exclusive hours.
- [ ] Solar factors represent solar remaining, not percentage reduction.
- [ ] Battery reserves are applied before optimization.
- [ ] Charge and discharge windows are enforced.
- [ ] Grid caps are enforced.
- [ ] Energy balance passes for all 24 hours.
- [ ] Battery remains within bounds.
- [ ] Final battery equals initial battery.
- [ ] Totals are recalculated from the hourly plan.
- [ ] All public and hidden-style tests pass.
- [ ] Provider failures do not crash the API.
- [ ] No API key appears in source, tests, logs, or documentation.
- [ ] Docker startup and `/health` work from a clean environment.
