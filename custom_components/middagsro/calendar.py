"""The meal plan as a calendar of dinners."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import RemaConfigEntry
from .entity import device_info
from .mealplan import signal_plans_updated
from .storage import plan_period

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RemaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the calendar."""
    async_add_entities([RemaMealPlanCalendar(entry)])


def _event(day: dict[str, Any], plan: dict[str, Any]) -> CalendarEvent:
    start = date.fromisoformat(day["date"])
    details = []
    if day.get("total_minutes"):
        details.append(f"{day['total_minutes']} min.")
    if day.get("type") and day["type"] != "normal":
        details.append(day["type"])
    ingredients = ", ".join(
        f"{i['amount']} {i['name']}".strip() for i in day.get("ingredients", [])
    )
    description = " · ".join(details)
    if ingredients:
        description = f"{description}\n{ingredients}" if description else ingredients
    return CalendarEvent(
        start=start,
        end=start + timedelta(days=1),
        summary=day.get("dish") or "Aftensmad",
        description=description or None,
        uid=f"{plan['id']}-{day['date']}",
    )


class RemaMealPlanCalendar(CalendarEntity):
    """Dinners from the meal plans."""

    _attr_has_entity_name = True
    _attr_translation_key = "meal_plan"

    def __init__(self, entry: RemaConfigEntry) -> None:
        """Initialize the calendar."""
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}_meal_plan"
        self._attr_device_info = device_info(entry)

    def _events(self) -> list[CalendarEvent]:
        """One event per dinner; a newer plan replaces older ones for its whole period
        (also the days it skips), like in the panel."""
        by_day: dict[str, CalendarEvent] = {}
        for plan in reversed(self._entry.runtime_data.store.plans):
            start, end = plan_period(plan)
            for key in [k for k in by_day if start <= k <= end]:
                del by_day[key]
            for day in plan.get("days", []):
                by_day[day["date"]] = _event(day, plan)
        return sorted(by_day.values(), key=lambda e: e.start)

    @property
    def event(self) -> CalendarEvent | None:
        """Today's dinner, or the next one planned."""
        today = dt_util.now().date()
        return next((e for e in self._events() if e.start >= today), None)

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return dinners in a range."""
        start, end = start_date.date(), end_date.date()
        return [e for e in self._events() if e.end > start and e.start <= end]

    async def async_added_to_hass(self) -> None:
        """Update when plans change."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal_plans_updated(self._entry.entry_id), self._plans_updated
            )
        )

    @callback
    def _plans_updated(self) -> None:
        self.async_write_ha_state()
