import math

from .models import DirectiveInterpretation, ScenarioInput

SUPPORTED = {
    "solar_reduction",
    "minimum_battery_reserve",
    "no_charge_window",
    "no_discharge_window",
    "max_grid_window",
    "no_op",
}


def _hours(value, note_index):
    if not isinstance(value, list) or any(isinstance(item, bool) or not isinstance(item, int) for item in value):
        raise ValueError(f"note {note_index}: hours must be integer list")
    if value != sorted(set(value)) or any(item < 0 or item > 23 for item in value):
        raise ValueError(f"note {note_index}: hours must be unique sorted values from 0 to 23")
    return value


def validate_directives(raw: list[dict], scenario: ScenarioInput) -> list[DirectiveInterpretation]:
    if len(raw) != len(scenario.operator_notes):
        raise ValueError("the model must return one directive per note")
    result = []
    for expected_index, item in enumerate(raw):
        if not isinstance(item, dict) or item.get("note_index") != expected_index:
            raise ValueError("directive entries must be ordered by note_index")
        directive_type = item.get("directive_type")
        applies = item.get("applies")
        adjustment = item.get("structured_adjustment")
        if directive_type not in SUPPORTED:
            raise ValueError("unsupported directive type")
        if directive_type == "no_op":
            if applies is not False or adjustment is not None:
                raise ValueError("no_op requires applies=false and null adjustment")
        else:
            if applies is not True or not isinstance(adjustment, dict):
                raise ValueError("active directives require applies=true and an adjustment")
            hours = _hours(adjustment.get("hours"), expected_index)
            if directive_type == "solar_reduction":
                factor = adjustment.get("factor")
                if not isinstance(factor, (int, float)) or isinstance(factor, bool) or not math.isfinite(factor) or not 0 <= factor <= 1:
                    raise ValueError("solar factor must be between 0 and 1")
                adjustment = {"hours": hours, "factor": float(factor)}
            elif directive_type == "minimum_battery_reserve":
                reserve = adjustment.get("minimum_energy_kwh")
                if not isinstance(reserve, (int, float)) or isinstance(reserve, bool) or not math.isfinite(reserve) or not 0 <= reserve <= scenario.battery.capacity_kwh:
                    raise ValueError("invalid battery reserve")
                adjustment = {"hours": hours, "minimum_energy_kwh": float(reserve)}
            elif directive_type == "max_grid_window":
                cap = adjustment.get("max_grid_kwh")
                if not isinstance(cap, (int, float)) or isinstance(cap, bool) or not math.isfinite(cap) or cap < 0:
                    raise ValueError("invalid grid cap")
                adjustment = {"hours": hours, "max_grid_kwh": float(cap)}
            else:
                adjustment = {"hours": hours}
        result.append(DirectiveInterpretation(note_index=expected_index, applies=applies, directive_type=directive_type, structured_adjustment=adjustment, explanation=str(item.get("explanation", ""))))
    return result
