"""Messages to the phone (the message centre, since 2.17.0).

Middagsro tells about offers on the watch list ("watch") and the food budget ("budget"). Each kind can be turned off,
go through the quiet hours or be held back, and has its own icon and colour. What is held back comes as one message when
the quiet hours end (or is dropped).
"""

from __future__ import annotations

from datetime import datetime
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from .mealplan import MealPlanner

_LOGGER = logging.getLogger(__name__)

KINDS = ("watch", "budget")
LOOK = {"watch": ("mdi:tag-heart", "#E4568C"), "budget": ("mdi:wallet-outline", "#0FA3A3")}
QUIET_DEFAULT = {"on": False, "from": "22:00", "to": "07:00", "after": "digest"}
DIGEST_MAX = 12


def _minutes(hhmm: str) -> int:
    hour, _, minute = str(hhmm).replace(".", ":").partition(":")
    return int(hour or 0) * 60 + int(minute or 0)


def in_quiet(settings: dict[str, Any], local: datetime) -> bool:
    """Whether the quiet hours are now."""
    quiet = {**QUIET_DEFAULT, **(settings.get("quiet") or {})}
    if not quiet["on"]:
        return False
    a, b, x = _minutes(quiet["from"]), _minutes(quiet["to"]), local.hour * 60 + local.minute
    return a <= x < b if a <= b else x >= a or x < b


def rule(settings: dict[str, Any], kind: str) -> dict[str, Any]:
    """A kind's choices: on, through the quiet hours, icon and colour."""
    icon, color = LOOK.get(kind, ("mdi:silverware-fork-knife", "#2F80ED"))
    return {
        "on": True,
        "through": False,
        "icon": icon,
        "color": color,
        **((settings.get("messages") or {}).get(kind) or {}),
    }


async def async_tell(
    planner: MealPlanner, kind: str, target: str, title: str, message: str, data: dict[str, Any]
) -> None:
    """Send a message to a notify service, or hold it back in the quiet hours."""
    settings = planner.store.settings
    own = rule(settings, kind)
    if not own["on"]:
        return
    if in_quiet(settings, dt_util.now()) and not own["through"]:
        if {**QUIET_DEFAULT, **(settings.get("quiet") or {})}["after"] == "digest":
            held: list[tuple[str, str, str]] = planner.__dict__.setdefault("phone_held", [])
            held.append((target, title, message))
        return
    await _async_send(
        planner,
        target,
        title,
        message,
        {**data, "notification_icon": own["icon"], "color": own["color"]},
    )


async def _async_send(
    planner: MealPlanner, target: str, title: str, message: str, data: dict[str, Any]
) -> None:
    await planner.hass.services.async_call(
        "notify",
        target.removeprefix("notify."),
        {"title": title, "message": message, "data": data},
        blocking=True,
    )


async def async_flush(planner: MealPlanner, now: datetime | None = None) -> None:
    """When the quiet hours are over: what was held back, as one message."""
    held: list[tuple[str, str, str]] = planner.__dict__.get("phone_held") or []
    if not held or in_quiet(planner.store.settings, dt_util.as_local(now or dt_util.now())):
        return
    planner.__dict__["phone_held"] = []
    for target in dict.fromkeys(t for t, _, _ in held):
        lines = [f"{title}: {message}" for t, title, message in held if t == target][-DIGEST_MAX:]
        try:
            await _async_send(
                planner,
                target,
                "Mens du sov",
                "\n".join(lines),
                {
                    "url": "/middagsro",
                    "clickAction": "/middagsro",
                    "notification_icon": "mdi:weather-night",
                    "color": "#5B5BD6",
                },
            )
        except (HomeAssistantError, ValueError) as err:
            _LOGGER.warning("Could not send the held messages: %s", err)
