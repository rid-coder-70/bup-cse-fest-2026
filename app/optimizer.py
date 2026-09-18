import numpy as np
from scipy.optimize import linprog

from .models import DirectiveInterpretation, HourPlan, ScenarioInput

HOURS = 24


def optimize(scenario: ScenarioInput, directives: list[DirectiveInterpretation]) -> list[HourPlan]:
    # Variable groups: grid, solar use, charge, discharge, battery-after.
    offset = {name: index * HOURS for index, name in enumerate(("grid", "solar", "charge", "discharge", "energy"))}
    size = 5 * HOURS
    objective = np.zeros(size)
    for hour in scenario.hours:
        objective[offset["grid"] + hour.hour] = hour.tariff_bdt_per_kwh
    effective_solar = [hour.solar_kwh for hour in scenario.hours]
    energy_lower = [scenario.battery.minimum_energy_kwh] * HOURS
    charge_upper = [scenario.battery.max_charge_kwh_per_hour] * HOURS
    discharge_upper = [scenario.battery.max_discharge_kwh_per_hour] * HOURS
    grid_upper = [np.inf] * HOURS
    for directive in directives:
        if not directive.applies:
            continue
        adjustment = directive.structured_adjustment or {}
        for hour in adjustment["hours"]:
            if directive.directive_type == "solar_reduction":
                effective_solar[hour] *= adjustment["factor"]
            elif directive.directive_type == "minimum_battery_reserve":
                energy_lower[hour] = max(energy_lower[hour], adjustment["minimum_energy_kwh"])
            elif directive.directive_type == "no_charge_window":
                charge_upper[hour] = 0
            elif directive.directive_type == "no_discharge_window":
                discharge_upper[hour] = 0
            elif directive.directive_type == "max_grid_window":
                grid_upper[hour] = min(grid_upper[hour], adjustment["max_grid_kwh"])
    bounds = []
    for name in ("grid", "solar", "charge", "discharge"):
        for hour in range(HOURS):
            upper = {"grid": grid_upper, "solar": effective_solar, "charge": charge_upper, "discharge": discharge_upper}[name][hour]
            bounds.append((0, upper))
    bounds.extend((energy_lower[hour], scenario.battery.capacity_kwh) for hour in range(HOURS))
    equality = []
    rhs = []
    for hour in range(HOURS):
        row = np.zeros(size)
        row[offset["grid"] + hour] = 1
        row[offset["solar"] + hour] = 1
        row[offset["discharge"] + hour] = 1
        row[offset["charge"] + hour] = -1
        equality.append(row)
        rhs.append(scenario.hours[hour].demand_kwh)
        state = np.zeros(size)
        state[offset["energy"] + hour] = 1
        state[offset["charge"] + hour] = -1
        state[offset["discharge"] + hour] = 1
        if hour == 0:
            rhs.append(scenario.battery.initial_energy_kwh)
        else:
            state[offset["energy"] + hour - 1] = -1
            rhs.append(0)
        equality.append(state)
    final = np.zeros(size)
    final[offset["energy"] + 23] = 1
    equality.append(final)
    rhs.append(scenario.battery.initial_energy_kwh)
    result = linprog(objective, A_eq=np.array(equality), b_eq=np.array(rhs), bounds=bounds, method="highs")
    if not result.success:
        raise ValueError(f"scenario is infeasible: {result.message}")
    values = result.x
    plan = []
    for hour in range(HOURS):
        charge, discharge = values[offset["charge"] + hour], values[offset["discharge"] + hour]
        if charge > 1e-7:
            action, amount = "charge", charge
        elif discharge > 1e-7:
            action, amount = "discharge", discharge
        else:
            action, amount = "idle", 0.0
        plan.append(HourPlan(hour=hour, grid_kwh=max(0.0, values[offset["grid"] + hour]), solar_used_kwh=max(0.0, values[offset["solar"] + hour]), battery_action=action, battery_kwh=max(0.0, amount), battery_energy_after_kwh=values[offset["energy"] + hour]))
    return plan
