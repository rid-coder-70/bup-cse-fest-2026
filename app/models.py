from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

DirectiveType = Literal[
    "solar_reduction",
    "minimum_battery_reserve",
    "no_charge_window",
    "no_discharge_window",
    "max_grid_window",
    "no_op",
]
BatteryAction = Literal["charge", "discharge", "idle"]


class HourInput(BaseModel):
    hour: int
    demand_kwh: float = Field(ge=0)
    solar_kwh: float = Field(ge=0)
    tariff_bdt_per_kwh: float = Field(ge=0)


class BatteryInput(BaseModel):
    capacity_kwh: float = Field(gt=0)
    initial_energy_kwh: float = Field(ge=0)
    minimum_energy_kwh: float = Field(ge=0)
    max_charge_kwh_per_hour: float = Field(ge=0)
    max_discharge_kwh_per_hour: float = Field(ge=0)

    @model_validator(mode="after")
    def valid_bounds(self):
        if self.initial_energy_kwh > self.capacity_kwh:
            raise ValueError("initial energy exceeds capacity")
        if self.minimum_energy_kwh > self.capacity_kwh:
            raise ValueError("minimum energy exceeds capacity")
        return self


class ScenarioInput(BaseModel):
    scenario_id: str = Field(min_length=1)
    operator_notes: list[str] = Field(min_length=1, max_length=3)
    hours: list[HourInput]
    battery: BatteryInput

    @field_validator("operator_notes")
    @classmethod
    def notes_are_non_empty(cls, notes):
        if any(not note.strip() for note in notes):
            raise ValueError("operator notes must be non-empty")
        return notes

    @model_validator(mode="after")
    def has_all_hours(self):
        values = sorted(hour.hour for hour in self.hours)
        if values != list(range(24)):
            raise ValueError("hours must contain each integer from 0 through 23")
        return self


class DirectiveInterpretation(BaseModel):
    note_index: int
    applies: bool
    directive_type: DirectiveType
    structured_adjustment: dict | None
    explanation: str = ""


class HourPlan(BaseModel):
    hour: int
    grid_kwh: float = Field(ge=0)
    solar_used_kwh: float = Field(ge=0)
    battery_action: BatteryAction
    battery_kwh: float = Field(ge=0)
    battery_energy_after_kwh: float = Field(ge=0)


class OptimizationResponse(BaseModel):
    scenario_id: str
    directive_interpretation: list[DirectiveInterpretation]
    hourly_plan: list[HourPlan]
    total_grid_kwh: float
    total_cost_bdt: float
    peak_grid_kwh: float
    plan_summary: str
