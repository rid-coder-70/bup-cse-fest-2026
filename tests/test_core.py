import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import ScenarioInput
from app.interpreter import NoteInterpreter
from app.optimizer import optimize
from app.replay import validate_plan

client = TestClient(app)
SAMPLES = Path(__file__).parents[1] / "BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json"


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("case", json.loads(SAMPLES.read_text())["cases"], ids=lambda case: case["id"])
def test_public_case_is_valid(case):
    scenario = ScenarioInput.model_validate(case["input"])
    import asyncio
    directives = asyncio.run(NoteInterpreter().interpret(scenario))
    plan = optimize(scenario, directives)
    validate_plan(scenario, directives, plan)
    assert len(directives) == len(scenario.operator_notes)
    assert len(plan) == 24


def test_invalid_hour_shape_is_rejected():
    payload = {"scenario_id": "bad", "operator_notes": ["hello"], "hours": [], "battery": {"capacity_kwh": 1, "initial_energy_kwh": 0, "minimum_energy_kwh": 0, "max_charge_kwh_per_hour": 1, "max_discharge_kwh_per_hour": 1}}
    assert client.post("/optimize-energy", json=payload).status_code == 422
