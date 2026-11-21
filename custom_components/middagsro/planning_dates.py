"""Keep dinner dates separate from the day their shopping is bought."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any


def shopping_day(start: date, settings: dict[str, Any]) -> date:
    """The chosen weekday on or before the first dinner; unset means that same day."""
    weekday = settings.get("shopping_weekday")
    if weekday is None:
        return start
    return start - timedelta(days=(start.weekday() - int(weekday)) % 7)


def plan_shopping_day(plan: dict[str, Any]) -> date:
    """Use the date saved with this plan, including legacy plans without one."""
    return date.fromisoformat(plan.get("shopping_date") or plan["start_date"])
