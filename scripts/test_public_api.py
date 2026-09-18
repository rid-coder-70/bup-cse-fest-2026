import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json"
BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"


def adjustment_matches(actual, expected) -> bool:
    if actual is None or expected is None:
        return actual == expected
    if actual.get("hours") != expected.get("hours"):
        return False
    numeric_fields = ("factor", "minimum_energy_kwh", "max_grid_kwh")
    return all(
        field not in expected
        or abs(actual.get(field, float("nan")) - expected[field]) <= 0.01
        for field in numeric_fields
    )


def main() -> int:
    pack = json.loads(SAMPLES.read_text())
    failures = []

    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        health = client.get("/health")
        if health.status_code != 200 or health.json() != {"status": "ok"}:
            print(f"HEALTH FAIL: {health.status_code} {health.text}")
            return 1
        print("HEALTH OK")

        for case in pack["cases"]:
            expected = case["expected_output"]
            response = client.post("/optimize-energy", json=case["input"])
            if response.status_code != 200:
                failures.append(f"{case['id']}: HTTP {response.status_code} {response.text}")
                continue

            body = response.json()
            problems = []
            for field in ("scenario_id", "total_grid_kwh", "total_cost_bdt", "peak_grid_kwh"):
                if field == "scenario_id":
                    if body.get(field) != expected[field]:
                        problems.append(f"{field}={body.get(field)!r}")
                elif abs(body.get(field, float("nan")) - expected[field]) > 0.01:
                    problems.append(f"{field}={body.get(field)!r}, expected={expected[field]!r}")

            actual_directives = body.get("directive_interpretation", [])
            expected_directives = expected["directive_interpretation"]
            if len(actual_directives) != len(expected_directives):
                problems.append("directive count mismatch")
            else:
                for actual, reference in zip(actual_directives, expected_directives):
                    if actual.get("directive_type") != reference["directive_type"]:
                        problems.append(
                            f"note {reference['note_index']} type={actual.get('directive_type')!r}"
                        )
                    if not adjustment_matches(
                        actual.get("structured_adjustment"),
                        reference.get("structured_adjustment"),
                    ):
                        problems.append(f"note {reference['note_index']} adjustment mismatch")

            if len(body.get("hourly_plan", [])) != 24:
                problems.append("hourly_plan must contain 24 rows")

            if problems:
                failures.append(f"{case['id']}: " + "; ".join(problems))
                print(f"FAIL {case['id']}")
            else:
                print(
                    f"PASS {case['id']} "
                    f"cost={body['total_cost_bdt']} "
                    f"grid={body['total_grid_kwh']} "
                    f"peak={body['peak_grid_kwh']}"
                )

    if failures:
        print("\nFailures:")
        print("\n".join(failures))
        return 1
    print(f"\nAll {len(pack['cases'])} public API cases passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
