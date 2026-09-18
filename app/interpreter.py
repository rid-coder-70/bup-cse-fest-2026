import json
import os
import re
from typing import Any

import httpx
from dotenv import load_dotenv

from .guardrails import validate_directives
from .models import DirectiveInterpretation, ScenarioInput

load_dotenv()

SYSTEM_PROMPT = """You interpret campus energy operator notes. Return JSON only with a directives array.
Return exactly one item per note, in note_index order. Allowed types are solar_reduction,
minimum_battery_reserve, no_charge_window, no_discharge_window, max_grid_window, no_op.
Use whole-hour arrays with start inclusive and end exclusive. For solar reduction, factor is
usable solar remaining, so an 80 percent reduction means factor 0.2. Irrelevant notes are
no_op with applies false and null adjustment. Never change demand, tariff, or battery data."""


def _hour_window(note: str) -> list[int]:
    note = re.sub(r"\bnoon\b", "12 PM", note, flags=re.I)
    note = re.sub(r"\bmidnight\b", "12 AM", note, flags=re.I)
    match = re.search(
        r"(?:from|between)\s+(\d{1,2})(?::\d{2})?\s*(AM|PM)?\s+"
        r"(?:until|to|and|through)\s+(\d{1,2})(?::\d{2})?\s*(AM|PM)?",
        note,
        re.I,
    )
    if not match:
        return []
    start, start_meridiem, end, end_meridiem = match.groups()
    start, end = int(start), int(end)
    if start_meridiem:
        start = (start % 12) + (12 if start_meridiem.upper() == "PM" else 0)
    if end_meridiem:
        end = (end % 12) + (12 if end_meridiem.upper() == "PM" else 0)
    return list(range(start, end)) if 0 <= start <= end <= 24 else []


def _offline_interpret(notes: list[str], capacity_kwh: float = 0.0) -> list[dict[str, Any]]:
    result = []
    for index, original in enumerate(notes):
        note = original.lower()
        hours = _hour_window(note)
        item: dict[str, Any] = {"note_index": index, "applies": False, "directive_type": "no_op", "structured_adjustment": None, "explanation": "This note does not affect the 24-hour energy schedule."}
        percentage = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|percent)", note)
        if any(word in note for word in ("solar", "panel", "inverter", "cloud")) and hours and (percentage or "half" in note):
            percent = float(percentage.group(1)) if percentage else 50.0
            factor = 1 - percent / 100 if "reduction" in note else percent / 100
            item.update(applies=True, directive_type="solar_reduction", structured_adjustment={"hours": hours, "factor": max(0.0, min(1.0, factor))}, explanation="Usable solar is reduced during the stated window.")
        elif any(word in note for word in ("do not charge", "charging is disabled", "charging must remain unavailable", "charging equipment is offline", "charger will be", "charging circuit")) and hours:
            item.update(applies=True, directive_type="no_charge_window", structured_adjustment={"hours": hours}, explanation="Battery charging is unavailable during the stated window.")
        elif any(
            word in note
            for word in (
                "do not discharge",
                "do not use battery discharge",
                "must not discharge",
                "battery discharge is forbidden",
                "discharging is unavailable",
            )
        ) and hours:
            item.update(applies=True, directive_type="no_discharge_window", structured_adjustment={"hours": hours}, explanation="Battery discharging is unavailable during the stated window.")
        elif any(word in note for word in ("grid import", "grid intake", "substation intake", "feeder", "transformer")) and hours:
            cap = re.search(r"(?:not exceed|at or below|limit is|limited to|no more than)\s+(\d+(?:\.\d+)?)", note)
            if cap:
                item.update(applies=True, directive_type="max_grid_window", structured_adjustment={"hours": hours, "max_grid_kwh": float(cap.group(1))}, explanation="Grid import is capped during the stated window.")
        elif any(
            word in note
            for word in (
                "reserve",
                "keep at least",
                "maintain at least",
                "battery state",
                "remain in the battery",
                "stored",
            )
        ) and hours:
            amount = re.search(r"(\d+(?:\.\d+)?)\s*kwh", note)
            percentage = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|percent)", note)
            if amount or percentage:
                item.update(applies=True, directive_type="minimum_battery_reserve", structured_adjustment={"hours": hours, "minimum_energy_kwh": float(amount.group(1)) if amount else 0.0}, explanation="Battery energy must remain above the stated reserve.")
                if percentage:
                    item["structured_adjustment"]["minimum_energy_kwh"] = capacity_kwh * float(percentage.group(1)) / 100
        result.append(item)
    return result


class NoteInterpreter:
    async def interpret(self, scenario: ScenarioInput) -> list[DirectiveInterpretation]:
        try:
            raw = await self._model_interpret(scenario)
        except Exception:
            raw = _offline_interpret(
                scenario.operator_notes,
                scenario.battery.capacity_kwh,
            )
        try:
            return validate_directives(raw, scenario)
        except ValueError:
            return validate_directives(
                _offline_interpret(
                    scenario.operator_notes,
                    scenario.battery.capacity_kwh,
                ),
                scenario,
            )

    async def _model_interpret(self, scenario: ScenarioInput) -> list[dict]:
        url = os.getenv("MODEL_API_URL")
        key = os.getenv("MODEL_API_KEY")
        placeholders = ("YOUR_", "your_", "CHANGE_ME", "changeme")
        if (
            not url
            or not key
            or any(value.startswith(placeholders) for value in (url, key))
        ):
            return _offline_interpret(scenario.operator_notes, scenario.battery.capacity_kwh)
        payload = {
            "model": os.getenv("MODEL_NAME", "gpt-4o-mini"),
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": json.dumps({"operator_notes": scenario.operator_notes, "battery_capacity_kwh": scenario.battery.capacity_kwh})}],
        }
        async with httpx.AsyncClient(timeout=float(os.getenv("MODEL_TIMEOUT_SECONDS", "12"))) as client:
            response = await client.post(url, headers={"Authorization": f"Bearer {key}"}, json=payload)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return parsed["directives"]
