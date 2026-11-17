"""Tests for the message centre: each kind on or off, the quiet hours, and what was held back sent as one."""

from __future__ import annotations

from datetime import timedelta

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.middagsro import phone
from custom_components.middagsro.storage import clean_settings
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.util import dt as dt_util


async def test_quiet_hours_and_the_summing_up(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    planner = init_integration.runtime_data.planner
    store = planner.store
    calls: list[ServiceCall] = []

    async def record(call: ServiceCall) -> None:
        calls.append(call)

    hass.services.async_register("notify", "mobile_app_telefon", record)
    now = dt_util.now()
    start, end = (
        (now - timedelta(hours=1)).strftime("%H:%M"),
        (now + timedelta(hours=1)).strftime("%H:%M"),
    )
    await store.async_set_settings(
        {
            **store.settings,
            "quiet": {"on": True, "from": start, "to": end, "after": "digest"},
            "messages": {
                "budget": {"through": True, "color": "#123456"},
                "watch": {"icon": "mdi:sale"},
            },
        }
    )
    # The budget goes through the quiet hours, in its own colour; the offer waits.
    await phone.async_tell(
        planner, "budget", "notify.mobile_app_telefon", "Budget", "80 %", {"url": "/middagsro"}
    )
    await phone.async_tell(
        planner, "watch", "notify.mobile_app_telefon", "Kaffe er på tilbud", "REMA", {}
    )
    assert [c.data["title"] for c in calls] == ["Budget"]
    assert calls[0].data["data"] == {
        "url": "/middagsro",
        "notification_icon": "mdi:wallet-outline",
        "color": "#123456",
    }
    await phone.async_flush(planner)
    assert len(calls) == 1  # still quiet

    # The quiet hours are over: the offer comes in one message.
    await phone.async_flush(planner, now + timedelta(hours=2))
    assert [(c.data["title"], c.data["message"]) for c in calls[1:]] == [
        ("Mens du sov", "Kaffe er på tilbud: REMA")
    ]

    # A kind turned off is not sent.
    await store.async_set_settings(
        {**store.settings, "quiet": {"on": False}, "messages": {"watch": {"on": False}}}
    )
    await phone.async_tell(planner, "watch", "notify.mobile_app_telefon", "Kaffe", "REMA", {})
    assert len(calls) == 2


def test_the_choices_are_cleaned() -> None:
    settings = clean_settings(
        {
            "messages": {
                "watch": {"on": "", "icon": "javascript:x", "color": "red"},
                "other": {"on": True},
            },
            "quiet": {"on": 1, "from": "25:00", "to": "06:30", "after": "never"},
        }
    )
    assert settings["messages"] == {"watch": {"on": False}}
    assert settings["quiet"] == {"on": True, "from": "22:00", "to": "06:30", "after": "digest"}
