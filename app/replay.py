from .models import DirectiveInterpretation, HourPlan, ScenarioInput

TOLERANCE = 0.02


def validate_plan(scenario: ScenarioInput, directives: list[DirectiveInterpretation], plan: list[HourPlan]) -> None:
    if len(plan) != 24 or [item.hour for item in plan] != list(range(24)):
        raise ValueError("plan must contain ordered hours 0 through 23")
    solar = [item.solar_kwh for item in scenario.hours]
    reserves = [scenario.battery.minimum_energy_kwh] * 24
    no_charge, no_discharge = set(), set()
    caps = {}
    for directive in directives:
        if not directive.applies:
            continue
        adjustment = directive.structured_adjustment or {}
        if directive.directive_type == "solar_reduction":
            for hour in adjustment["hours"]:
                solar[hour] *= adjustment["factor"]
        elif directive.directive_type == "minimum_battery_reserve":
            for hour in adjustment["hours"]:
                reserves[hour] = max(reserves[hour], adjustment["minimum_energy_kwh"])
        elif directive.directive_type == "no_charge_window":
            no_charge.update(adjustment["hours"])
        elif directive.directive_type == "no_discharge_window":
            no_discharge.update(adjustment["hours"])
        elif directive.directive_type == "max_grid_window":
            for hour in adjustment["hours"]:
                caps[hour] = min(caps.get(hour, float("inf")), adjustment["max_grid_kwh"])
    previous = scenario.battery.initial_energy_kwh
    for item, source in zip(plan, scenario.hours):
        amount = item.battery_kwh
        if item.solar_used_kwh > solar[item.hour] + TOLERANCE:
            raise ValueError("solar usage exceeds effective solar")
        if item.battery_action == "charge":
            if item.hour in no_charge or amount > scenario.battery.max_charge_kwh_per_hour + TOLERANCE or abs(item.battery_energy_after_kwh - previous - amount) > TOLERANCE:
                raise ValueError("invalid battery charge")
            discharge = 0
        elif item.battery_action == "discharge":
            if item.hour in no_discharge or amount > scenario.battery.max_discharge_kwh_per_hour + TOLERANCE or abs(item.battery_energy_after_kwh - previous + amount) > TOLERANCE:
                raise ValueError("invalid battery discharge")
            discharge = amount
        else:
            if amount > TOLERANCE or abs(item.battery_energy_after_kwh - previous) > TOLERANCE:
                raise ValueError("invalid idle battery state")
            discharge = 0
        if item.battery_energy_after_kwh < reserves[item.hour] - TOLERANCE or item.battery_energy_after_kwh > scenario.battery.capacity_kwh + TOLERANCE:
            raise ValueError("battery bounds violated")
        if item.hour in caps and item.grid_kwh > caps[item.hour] + TOLERANCE:
            raise ValueError("grid cap violated")
        if abs(item.grid_kwh + item.solar_used_kwh + discharge - source.demand_kwh - (amount if item.battery_action == "charge" else 0)) > TOLERANCE:
            raise ValueError("energy balance violated")
        previous = item.battery_energy_after_kwh
    if abs(previous - scenario.battery.initial_energy_kwh) > TOLERANCE:
        raise ValueError("battery neutrality violated")
