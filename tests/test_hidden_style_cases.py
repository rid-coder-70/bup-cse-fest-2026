import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

CASES = json.loads((Path(__file__).parent / "data/hidden_style_cases.json").read_text())
client = TestClient(app)


def scenario_for(case):
    hours = []
    for hour in range(24):
        solar = 120.0 if 8 <= hour <= 16 else 0.0
        tariff = 30.0 if 17 <= hour <= 21 else 6.0
        hours.append({
            "hour": hour,
            "demand_kwh": 100.0,
            "solar_kwh": solar,
            "tariff_bdt_per_kwh": tariff,
        })
    return {
        "scenario_id": case["id"],
        "operator_notes": case["notes"],
        "hours": hours,
        "battery": {
            "capacity_kwh": 300.0,
            "initial_energy_kwh": 100.0,
            "minimum_energy_kwh": 20.0,
            "max_charge_kwh_per_hour": 100.0,
            "max_discharge_kwh_per_hour": 100.0,
        },
    }


def test_hidden_style_cases_through_http_contract():
    for case in CASES:
        response = client.post("/optimize-energy", json=scenario_for(case))
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["scenario_id"] == case["id"]
        assert len(body["directive_interpretation"]) == len(case["notes"])
        assert len(body["hourly_plan"]) == 24
        for actual, expected in zip(body["directive_interpretation"], case["expected"]):
            assert actual["directive_type"] == expected["type"]
            if expected["type"] == "no_op":
                assert actual["applies"] is False
                assert actual["structured_adjustment"] is None
                continue
            assert actual["applies"] is True
            adjustment = actual["structured_adjustment"]
            assert adjustment["hours"] == expected["hours"]
            for key in ("factor", "minimum_energy_kwh", "max_grid_kwh"):
                if key in expected:
                    assert abs(adjustment[key] - expected[key]) <= 0.01


def test_malformed_and_semantically_invalid_requests_are_controlled():
    response = client.post("/optimize-energy", json={"scenario_id": "bad"})
    assert response.status_code in (400, 422)
    assert "Traceback" not in response.text


def test_health_contract():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
