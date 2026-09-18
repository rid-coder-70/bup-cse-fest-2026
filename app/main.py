from fastapi import FastAPI, HTTPException

from .interpreter import NoteInterpreter
from .models import OptimizationResponse, ScenarioInput
from .optimizer import optimize
from .replay import validate_plan

app = FastAPI(title="GridWise Energy Optimizer", version="1.0.0")
interpreter = NoteInterpreter()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/optimize-energy", response_model=OptimizationResponse)
async def optimize_energy(scenario: ScenarioInput):
    try:
        directives = await interpreter.interpret(scenario)
        plan = optimize(scenario, directives)
        validate_plan(scenario, directives, plan)
        total_grid = sum(item.grid_kwh for item in plan)
        total_cost = sum(item.grid_kwh * source.tariff_bdt_per_kwh for item, source in zip(plan, scenario.hours))
        return OptimizationResponse(
            scenario_id=scenario.scenario_id,
            directive_interpretation=directives,
            hourly_plan=plan,
            total_grid_kwh=round(total_grid, 6),
            total_cost_bdt=round(total_cost, 6),
            peak_grid_kwh=round(max(item.grid_kwh for item in plan), 6),
            plan_summary="The validated plan minimizes tariff-weighted grid import while satisfying all interpreted directives and battery rules.",
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail="optimization service unavailable") from error
