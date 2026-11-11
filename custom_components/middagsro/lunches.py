"""Packed lunches (madpakker) and weekly items with a use, for the week's shopping list."""

from __future__ import annotations

from datetime import date, timedelta
import logging
import math
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

GROUP_LABELS = {
    "morgenmad": "Morgenmad",
    "madpakker": "Madpakker",
    "husholdning": "Husholdning",
}
MAX_IDEAS = 7


def _day(value: Any) -> date | None:
    """The day an event starts or ends; None for a time of day (not a whole day)."""
    if isinstance(value, dict):
        value = value.get("date") or value.get("dateTime")
    text = str(value or "")
    if len(text) != 10:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


async def async_days_off(hass: HomeAssistant, calendar: str, window: list[date]) -> set[date]:
    """The days in window covered by an all-day event in the calendar (holidays).

    Events with a time of day (a parents' meeting) are not days off. A calendar
    that can't be read gives no days off: packed lunches are bought as usual.
    """
    if not calendar or not window or hass.states.get(calendar) is None:
        return set()
    start = dt_util.start_of_local_day(min(window))
    end = dt_util.start_of_local_day(max(window) + timedelta(days=1))
    try:
        response = await hass.services.async_call(
            "calendar",
            "get_events",
            {"entity_id": calendar, "start_date_time": start, "end_date_time": end},
            blocking=True,
            return_response=True,
        )
    except (HomeAssistantError, ValueError) as err:
        _LOGGER.warning("The calendar %s of days off could not be read: %s", calendar, err)
        return set()
    found = (response or {}).get(calendar)
    events = found.get("events") if isinstance(found, dict) else None
    off: set[date] = set()
    for event in events if isinstance(events, list) else []:
        if not isinstance(event, dict):
            continue
        first, last = _day(event.get("start")), _day(event.get("end"))
        if first is None:
            continue
        last = last if last is not None and last > first else first + timedelta(days=1)
        off |= {d for d in window if first <= d < last}  # an all-day event's end is exclusive
    return off


async def async_lunches(
    hass: HomeAssistant, settings: dict[str, Any], window: list[date]
) -> dict[str, Any] | None:
    """The plan period's packed lunches; None when the family packs none."""
    count = int(settings.get("lunch_count") or 0)
    weekdays = settings.get("lunch_weekdays") or []
    if not count or not weekdays or not window:
        return None
    school = [d for d in window if str(d.weekday()) in weekdays]
    off = await async_days_off(hass, settings.get("lunch_calendar") or "", school)
    days = [d for d in school if d not in off]
    return {
        "count": count,
        "days": [d.isoformat() for d in days],
        "off": [d.isoformat() for d in school if d in off],
        "lunches": count * len(days),
        "usual_days": len(weekdays),
    }


def _number(value: float) -> str:
    return f"{value:g}".replace(".", ",")


def must_have_lines(
    items: list[dict[str, Any]], lunch: dict[str, Any] | None
) -> list[dict[str, Any]]:
    """The weekly items' shopping lines for one plan.

    A packed lunch item follows the week's packed lunches: none in a holiday
    week, fewer packages in a short school week, and an amount per packed lunch
    times how many. An item used by the week is its use (minus what is left,
    asked on the list).
    """
    lunches = int(lunch["lunches"]) if lunch else 0
    lines: list[dict[str, Any]] = []
    for item in items:
        group = item.get("group") or ""
        mode = item.get("mode") or "packs"
        use = float(item.get("use") or 0)
        unit = item.get("unit") or "stk"
        note = None
        if mode == "lunch":
            if not lunches:
                continue  # no packed lunches this week (or none set up)
            amount = round(use * lunches, 3)
            note = f"{lunches} madpakker × {_number(use)} {unit}"
        elif group == "madpakker" and lunch is not None and not lunches:
            continue  # a holiday week: no packed lunch items
        elif mode == "week":
            amount = use
            note = f"Bruger {_number(use)} {unit} om ugen"
        else:
            amount, unit = item.get("amount") or 1, "pk"
            usual = int(lunch["usual_days"]) if lunch else 0
            if group == "madpakker" and lunch is not None and len(lunch["days"]) < usual:
                amount = max(1, math.ceil(amount * len(lunch["days"]) / usual))
                note = f"{len(lunch['days'])} af {usual} skoledage"
        line: dict[str, Any] = {
            "name": item["name"],
            "amount": amount,
            "unit": unit,
            "search": item["name"],
            "category": GROUP_LABELS.get(group, "Faste varer"),
            "offer": None,
            "must_have": True,
            "product_id": item.get("product_id"),
        }
        if group:
            line["group"] = group
        if mode != "packs":
            line.update(use_mode=mode, use_total=amount)
        if note:
            line["use_note"] = note
        lines.append(line)
    return lines


def lunch_prompt(settings: dict[str, Any], lunch: dict[str, Any] | None) -> str:
    """What the AI is told about the week's packed lunches."""
    if not lunch or not lunch["lunches"]:
        return ""
    text = (
        f"\n- Familien smører {lunch['lunches']} madpakker i perioden "
        f"({lunch['count']} om dagen, {len(lunch['days'])} skoledage). "
        "Madpakkevarerne er faste varer og skal IKKE på indkøbslisten."
    )
    if settings.get("lunch_ideas"):
        text += (
            f" Skriv i lunch_ideas {min(MAX_IDEAS, len(lunch['days']))} korte, varierede "
            "madpakkeidéer til børn, gerne med ugens tilbud og rester fra aftensmaden "
            "(fx 'Rugbrød med frikadelle fra mandag og agurkestave'). Varer, som idéerne "
            "kræver ud over de faste madpakkevarer, må komme på indkøbslisten med "
            "kategorien 'Madpakker'."
        )
    return text


def clean_ideas(raw: Any) -> list[str]:
    """The AI's packed lunch ideas, short and few."""
    if not isinstance(raw, list):
        return []
    return [str(i).strip()[:200] for i in raw if str(i or "").strip()][:MAX_IDEAS]
