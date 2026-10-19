"""Diagnostics for REMA 1000."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .api import Catalog
from .coordinator import RemaConfigEntry

TO_REDACT = {CONF_EMAIL, CONF_PASSWORD, "title", "unique_id"}


def _catalog(catalog: Catalog | None) -> dict[str, Any] | None:
    if catalog is None:
        return None
    return {
        "id": catalog.id,
        "label": catalog.label,
        "valid_from": catalog.valid_from.isoformat() if catalog.valid_from else None,
        "valid_to": catalog.valid_to.isoformat() if catalog.valid_to else None,
        "offer_count": catalog.offer_count,
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: RemaConfigEntry
) -> dict[str, Any]:
    """Return what helps to find a problem, without personal details.

    Item names, dishes and the household are left out; only counts and
    settings that change how plans are made are included.
    """
    data = entry.runtime_data
    shopping = data.shopping_list.data
    offers = data.offers.data
    settings = data.store.settings
    latest = data.store.latest_plan
    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "shopping_list": {
            "last_update_success": data.shopping_list.last_update_success,
            "items": len(shopping.items) if shopping else None,
            "unbought_items": sum(1 for i in shopping.items if not i.bought) if shopping else None,
            "items_without_price": sum(1 for i in shopping.items if i.price is None)
            if shopping
            else None,
            "unbought_total": shopping.unbought_total if shopping else None,
        },
        "offers": {
            "last_update_success": data.offers.last_update_success,
            "current": _catalog(offers.current) if offers else None,
            "upcoming": _catalog(offers.upcoming) if offers else None,
            "catalogs": len(offers.catalogs) if offers else 0,
        },
        "settings": {
            key: settings[key]
            for key in (
                "ai_task_entity",
                "start_weekday",
                "days",
                "budget",
                "organic",
                "organic_max_extra_pct",
                "avoid",
                "allergies",
                "min_vegetarian",
                "max_vegetarian",
                "leftover_days",
                "max_cook_minutes_weekday",
                "no_repeat_weeks",
                "egg_min",
                "milk_organic",
                "produce_organic",
                "auto_generate",
                "auto_send",
            )
        }
        | {
            "household_members": len(settings["household"]),
            "fixed_days": len(settings["fixed_days"]),
            "must_haves": len(settings["must_haves"]),
            "disliked_dishes": len(settings["disliked_dishes"]),
        },
        "favorite_dishes": len(data.store.favorites),
        "plans": len(data.store.plans),
        "latest_plan": {
            "start_date": latest["start_date"],
            "end_date": latest["end_date"],
            "status": latest["status"],
            "days": len(latest["days"]),
            "shopping_lines": len(latest["shopping"]),
            "lines_without_product": sum(
                1 for line in latest["shopping"] if not line.get("product")
            ),
            "total": latest["total"],
            "budget": latest["budget"],
            "over_budget": latest.get("over_budget", False),
            "recipe_errors": sum(1 for day in latest["days"] if day.get("recipe_error")),
        }
        if latest
        else None,
        "planner": {
            "state": data.planner.status["state"],
            "ai_available": data.planner.ai_available(),
        },
    }
