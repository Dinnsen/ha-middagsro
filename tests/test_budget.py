"""Tests for the food budget: purchases, the week, the month and the year."""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.middagsro import budget as bg
from custom_components.middagsro.chains import REMA_ID
from custom_components.middagsro.const import DOMAIN
from custom_components.middagsro.storage import DEFAULT_SETTINGS, clean_settings
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError

TODAY = date(2026, 10, 14)  # a Wednesday; the week runs sunday 11/10 to saturday 17/10
NETTO = "9ba51"


class FakeStore:
    """Just what the budget reads of the plan store."""

    def __init__(self, purchases: list[dict[str, Any]] | None = None, **settings: Any) -> None:
        self.settings: dict[str, Any] = {
            **DEFAULT_SETTINGS,
            "monthly_budget": 3100,  # 100 kr. a day in October
            "budget_since": "2026-01-01",
            "household": [{"role": "adult", "age": 40}, {"role": "adult", "age": 40}],
            **settings,
        }
        self.purchases = purchases or []
        self.plans: list[dict[str, Any]] = []
        self.prices = True  # REMA 1000: every item has a price
        self.budget_told = ""
        self.saves = 0

    async def async_save(self) -> None:
        self.saves += 1

    def plan_covering(self, day: date) -> dict[str, Any] | None:
        iso = day.isoformat()
        return next((p for p in self.plans if p["start_date"] <= iso <= p["end_date"]), None)


def buy(day: str, amount: float, store: str = REMA_ID, pid: str | None = None) -> dict[str, Any]:
    return {
        "id": pid or f"{day}-{amount}",
        "date": day,
        "amount": amount,
        "store": store,
        "note": "",
        "source": "panel",
        "created": f"{day}T12:00:00",
    }


def the_store() -> FakeStore:
    """September's big shop, two shops before this week and two in it."""
    store = FakeStore(
        [
            buy("2026-09-20", 2000),
            buy("2026-10-04", 600),
            buy("2026-10-08", 300, NETTO),
            buy("2026-10-11", 500),
            buy("2026-10-13", 80),
        ]
    )
    store.plans = [
        {
            "id": "this",
            "start_date": "2026-10-11",
            "end_date": "2026-10-17",
            "shopping": [
                {"cost": 50, "buy_from": "2026-10-14"},
                {"cost": 30, "buy_from": "2026-10-16"},
                {
                    "cost": 40,
                    "sent": "2026-10-11T09:00:00+02:00",
                    "packages": 2,
                    "product": {"price": 20, "normal_price": 30},
                },
                {"cost": 500, "buy_from": "2026-10-16", "buy_at": NETTO},
            ],
        },
        {
            "id": "next",
            "start_date": "2026-10-18",
            "end_date": "2026-10-24",
            "shopping": [{"cost": 200}, {"cost": None}],
        },
    ]
    return store


def test_store_of() -> None:
    """A shop from an id, or a name as a card payment shows it."""
    assert bg.store_of(REMA_ID) == REMA_ID
    assert bg.store_of(NETTO) == NETTO
    assert bg.store_of("REMA 1000 VALBY") == REMA_ID
    assert bg.store_of("Netto Amager Strand") == NETTO
    assert bg.store_of("Lidl") == "71c90"
    assert bg.store_of("Bager Jensen") == bg.OTHER
    assert bg.store_of(None) == bg.OTHER


def test_parse_amount() -> None:
    """The amount as a phone's shortcut sends it, in Danish or English."""
    for text, value in (
        (600, 600),
        (12.5, 12.5),
        ("450,5", 450.5),
        ("600,00 kr.", 600),
        ("kr. 1.234,50", 1234.5),
        ("DKK 1,234.50", 1234.5),
        ("DKK 600.00", 600),
        ("1.234", 1234),
        ("12.345.678", 12345678),
        ("1,234,567", 1234567),
        ("-25,00", -25),
    ):
        assert bg.parse_amount(text) == value, text
    for bad in ("kr.", None, True):
        with pytest.raises(ValueError):
            bg.parse_amount(bad)


def test_clean_purchase(freezer: Any) -> None:
    """Amounts with a comma, dates, shops and their names."""
    freezer.move_to("2026-10-14T10:00:00+00:00")
    p = bg.clean_purchase({"amount": "450,5", "store": "Netto"})
    assert (p["amount"], p["store"], p["date"], p["source"]) == (
        450.5,
        NETTO,
        "2026-10-14",
        "panel",
    )
    other = bg.clean_purchase({"amount": 35, "store": "Bager Jensen", "date": "2026-10-13"})
    assert (other["store"], other["note"]) == (bg.OTHER, "Bager Jensen")
    assert bg.clean_purchase({"amount": 10})["store"] == REMA_ID
    # Editing keeps the id and when it was made; only what is given changes.
    edited = bg.clean_purchase({"amount": 99}, p)
    assert (edited["id"], edited["created"], edited["store"]) == (p["id"], p["created"], NETTO)
    for raw, key in (
        ("600", "purchase_amount"),
        ({"amount": 0}, "purchase_amount"),
        ({"amount": "mange"}, "purchase_amount"),
        ({"amount": 200_000}, "purchase_amount"),
        ({"amount": "-25,00 kr."}, "purchase_amount"),
        ({"amount": 5, "date": "i går"}, "purchase_date"),
        ({"amount": 5, "date": "2026-10-20"}, "purchase_date"),
    ):
        with pytest.raises(ServiceValidationError) as err:
            bg.clean_purchase(raw)
        assert err.value.translation_key == key


async def test_add_edit_delete() -> None:
    """Purchases are kept sorted, the oldest dropped past the limit."""
    store = FakeStore()
    with patch.object(bg, "MAX_PURCHASES", 2):
        first = await bg.async_add(store, {"amount": 10, "date": "2026-10-01"})
        await bg.async_add(store, {"amount": 20, "date": "2026-09-01"})
        await bg.async_add(store, {"amount": 30, "date": "2026-10-05"})
    assert [p["amount"] for p in store.purchases] == [10, 30]
    await bg.async_edit(store, first["id"], {"date": "2026-10-09"})
    assert [p["amount"] for p in store.purchases] == [30, 10]
    await bg.async_delete(store, first["id"])
    assert [p["amount"] for p in store.purchases] == [30]
    with pytest.raises(ServiceValidationError):
        await bg.async_edit(store, "x", {})
    with pytest.raises(ServiceValidationError):
        await bg.async_delete(store, "x")
    assert store.saves == 5


def test_no_budget() -> None:
    """Without a monthly budget there is nothing to show, and plans keep their own."""
    store = FakeStore(monthly_budget=0)
    assert bg.summary(store, TODAY) is None
    assert bg.plan_budget(store, date(2026, 10, 18), TODAY) is None
    assert bg.crossed(store, TODAY) is None


def test_the_week() -> None:
    """What is left of the week, with what the month's earlier weeks left over."""
    week = bg.summary(the_store(), TODAY)["week"]
    assert week == {
        "start": "2026-10-11",
        "end": "2026-10-17",
        "week": 42,
        "budget": 700,
        "carry": 100,  # 1.000 kr. for 1-10 October, 900 spent
        "available": 800,
        "spent": 580,
        "remaining": 220,
        "pace": 457.14,
        "planned": 30,  # thursday's list; not today's, nor the one bought in Netto
        "after_planned": 190,
        "per_day": 55,
        "days_left": 4,
    }
    # A new month starts afresh: October's overspending is not taken from November.
    store = FakeStore([buy("2026-10-30", 2000)])
    week = bg.summary(store, date(2026, 11, 2))["week"]
    assert week["start"] == "2026-11-01"
    assert week["carry"] == 0
    assert week["budget"] == round(7 * 3100 / 30, 2)


def test_budget_since() -> None:
    """Days before the budget was kept have none, and their weeks aren't shown."""
    store = FakeStore([buy("2026-10-02", 400)], budget_since="2026-10-14")
    data = bg.summary(store, TODAY)
    assert data is not None
    assert data["week"]["budget"] == 400  # wednesday to saturday
    assert data["week"]["carry"] == 0
    assert data["month"]["budget"] == 1800
    assert [w["week"] for w in data["weeks"]] == [42]
    assert [m["budget"] for m in data["year"]["months"]][8:11] == [None, 1800, 3100]
    store.settings["budget_since"] = "ikke en dato"
    assert bg.since(store) == date.min


def test_month_year_and_stats() -> None:
    """The month's forecast from the family's own pace, the year, and the averages."""
    data = bg.summary(the_store(), TODAY)
    assert data is not None
    assert data["monthly"] == 3100
    assert data["daily"] == 100
    month = data["month"]
    assert (month["first"], month["days"], month["budget"]) == ("2026-10-01", 31, 3100)
    assert (month["spent"], month["remaining"]) == (1480, 1620)
    assert len(month["series"]) == 14
    assert month["series"][3] == 600
    assert month["series"][-1] == 1480
    # 3.480 kr. in the 25 days since 20 September: 139,20 a day for the 17 days left.
    assert month["forecast"] == 3846.4
    assert month["planned"] == 230

    weeks = data["weeks"]
    assert len(weeks) == bg.WEEKS_SHOWN
    assert weeks[-1] == {
        "start": "2026-10-11",
        "week": 42,
        "budget": 700,
        "spent": 580,
        "current": True,
    }
    assert weeks[-2]["spent"] == 900

    year = data["year"]
    assert year["year"] == 2026
    assert year["months"][8] == {"month": 9, "spent": 2000, "budget": 3100}
    assert year["months"][9]["spent"] == 1480
    assert year["months"][10] == {"month": 11, "spent": None, "budget": 3100}
    assert year["spent"] == 3480
    assert year["average"] == round(2000 / 9, 2)

    stats = data["stats"]
    assert stats["trips"][0] == {"weekday": "søndag", "average": 1033.33, "count": 3}
    assert (stats["extra_trips"], stats["extra_average"]) == (2, 190)
    assert stats["per_portion_day"] == round(1480 / 14 / 2, 2)
    assert stats["stores"] == [{"store": REMA_ID, "amount": 3180}, {"store": NETTO, "amount": 300}]
    assert stats["saved_on_offers"] == 20
    assert stats["outside_lists"] == 1440

    assert [p["date"] for p in data["purchases"]][:2] == ["2026-10-13", "2026-10-11"]

    # Few days known: the budget's own rate; nothing booked: no averages.
    fresh = bg.summary(FakeStore([buy("2026-10-12", 300)]), TODAY)
    assert fresh is not None
    assert fresh["month"]["forecast"] == 300 + 17 * 100
    # Lists sent before the budget was kept don't count; nor while less is booked than sent.
    late = the_store()
    late.settings["budget_since"] = "2026-10-12"
    stats = bg.summary(late, TODAY)["stats"]  # type: ignore[index]
    assert (stats["saved_on_offers"], stats["outside_lists"]) == (0, None)
    late.settings["budget_since"] = "2026-10-01"
    late.purchases = [buy("2026-10-11", 30)]
    assert bg.summary(late, TODAY)["stats"]["outside_lists"] is None  # type: ignore[index]

    empty = bg.summary(FakeStore(), TODAY)
    assert empty is not None
    assert empty["stats"]["extra_trips"] is None
    assert empty["stats"]["per_portion_day"] is None
    assert empty["stats"]["outside_lists"] is None
    assert empty["year"]["average"] == 0


def test_plan_budget() -> None:
    """A plan may cost what is left of its week, never below 40 % of the week's budget."""
    store = the_store()
    # Next week: its 700 kr. and the 220 kr. October has left by then.
    assert bg.plan_budget(store, date(2026, 10, 18), TODAY) == 920
    # From tomorrow: 220 left, today's list (50 kr.) is still to be bought: the floor.
    assert bg.plan_budget(store, date(2026, 10, 15), TODAY) == 280
    store.purchases = store.purchases[:3]
    assert bg.plan_budget(store, date(2026, 10, 15), TODAY) == 750


def test_crossed_and_message() -> None:
    """Told once a week, when 80 % is used, and only if the family wants it."""
    store = the_store()
    store.settings["budget_notify"] = True
    assert bg.crossed(store, TODAY) is None  # 580 of 800
    store.purchases.append(buy("2026-10-14", 100))
    week = bg.crossed(store, TODAY)
    assert week is not None
    assert store.budget_told == "2026-10-11"
    assert bg.crossed(store, TODAY) is None  # told already
    assert bg.week_message(week) == (
        "💰 120 kr. tilbage af ugens madbudget",
        "Brugt 680 kr. af 800 kr. – resten af ugens lister er anslået til 30 kr.",
    )
    over = {**week, "remaining": -1127.4, "planned": 0}
    assert bg.week_message(over) == (
        "💸 Ugens madbudget er overskredet med 1.127 kr.",
        "Brugt 680 kr. af 800 kr.",
    )
    store.budget_told = ""
    store.settings["budget_notify"] = False
    assert bg.crossed(store, TODAY) is None


def test_settings_clean() -> None:
    """The monthly budget is clamped; the day it began must be a date."""
    settings = clean_settings({"monthly_budget": "-5", "budget_since": "nej", "budget_notify": 1})
    assert (settings["monthly_budget"], settings["budget_since"], settings["budget_notify"]) == (
        0,
        None,
        True,
    )
    assert clean_settings({"monthly_budget": 9e9})["monthly_budget"] == 1_000_000
    assert clean_settings({"budget_since": "2026-10-01"})["budget_since"] == "2026-10-01"


# ------------------------------------------------------------------ in Home Assistant


async def _ws(client: Any, msg_id: int, **msg: Any) -> dict[str, Any]:
    await client.send_json({"id": msg_id, **msg})
    result: dict[str, Any] = await client.receive_json()
    return result


async def test_websocket(
    hass: HomeAssistant, init_integration: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """Setting the budget, and booking, changing and deleting purchases from the panel."""
    store = init_integration.runtime_data.store
    client = await hass_ws_client(hass)
    msg = await _ws(client, 1, type="middagsro/state")
    assert msg["result"]["budget"] is None
    msg = await _ws(client, 2, type="middagsro/purchases/add", amount=100)
    assert not msg["success"]

    msg = await _ws(
        client, 3, type="middagsro/settings", settings={**store.settings, "monthly_budget": 3100}
    )
    assert msg["result"]["budget_since"] == "2026-10-14"
    msg = await _ws(client, 4, type="middagsro/budget")
    assert msg["result"]["week"]["available"] == 400

    msg = await _ws(client, 5, type="middagsro/purchases/add", amount="250,5", store="Netto Amager")
    assert msg["success"]
    week = msg["result"]["week"]
    assert (week["spent"], week["remaining"]) == (250.5, 149.5)
    purchase = msg["result"]["purchases"][0]
    assert purchase["store"] == NETTO
    msg = await _ws(
        client,
        6,
        type="middagsro/purchases/edit",
        purchase_id=purchase["id"],
        amount=300,
        note=None,
    )
    assert msg["result"]["week"]["spent"] == 300
    assert msg["result"]["purchases"][0]["store"] == NETTO
    msg = await _ws(client, 7, type="middagsro/purchases/edit", purchase_id="x", amount=1)
    assert not msg["success"]
    msg = await _ws(client, 8, type="middagsro/purchases/delete", purchase_id=purchase["id"])
    assert msg["result"]["week"]["spent"] == 0
    msg = await _ws(client, 9, type="middagsro/purchases/delete", purchase_id=purchase["id"])
    assert not msg["success"]

    # Keeping the budget from the day it began, also when it is changed; off again clears it.
    await store.async_set_settings({**store.settings, "monthly_budget": 4000})
    assert store.settings["budget_since"] == "2026-10-14"
    await store.async_set_settings({**store.settings, "monthly_budget": 0})
    assert store.settings["budget_since"] is None


async def test_action_sensors_and_notification(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """The action books a purchase and answers; the sensors follow; the family is told."""
    store = init_integration.runtime_data.store
    left = "sensor.middagsro_food_budget_left_this_week"
    state = hass.states.get(left)
    assert state is not None
    assert state.state == "unavailable"
    calls: list[ServiceCall] = []

    async def record(call: ServiceCall) -> None:
        calls.append(call)

    hass.services.async_register("notify", "mobile_app_telefon", record)
    await store.async_set_settings(
        {
            **store.settings,
            "monthly_budget": 3100,
            "budget_notify": True,
            "watch_notify": "notify.mobile_app_telefon",
        }
    )
    init_integration.runtime_data.planner._notify()
    await hass.async_block_till_done()
    state = hass.states.get(left)
    assert state is not None
    assert float(state.state) == 400

    answer = await hass.services.async_call(
        DOMAIN,
        "register_purchase",
        {"amount": 350, "store": "REMA 1000 Valby"},
        blocking=True,
        return_response=True,
    )
    assert answer == {
        "week_left": 50,
        "week_spent": 350,
        "week_available": 400,
        "week_planned": 0,
        "month_spent": 350,
        "month_forecast": 350 + 17 * 100,
    }
    assert store.purchases[0]["source"] == "action"
    assert store.purchases[0]["store"] == REMA_ID
    await hass.async_block_till_done()
    state = hass.states.get(left)
    assert state is not None
    assert float(state.state) == 50
    assert state.attributes["spent"] == 350
    spent = hass.states.get("sensor.middagsro_food_budget_spent_this_month")
    assert spent is not None
    assert float(spent.state) == 350
    assert spent.attributes["budget"] == 1800
    forecast = hass.states.get("sensor.middagsro_food_budget_forecast_for_the_month")
    assert forecast is not None
    assert float(forecast.state) == 2050

    assert len(calls) == 1
    assert calls[0].data["title"] == "💰 50 kr. tilbage af ugens madbudget"
    assert calls[0].data["data"]["url"] == "/middagsro"

    # Told once a week; in Home Assistant itself; a notify service that is gone is no error.
    store.budget_told = ""
    await store.async_set_settings({**store.settings, "watch_notify": "persistent_notification"})
    with patch.object(bg.persistent_notification, "async_create") as create:
        await hass.services.async_call(DOMAIN, "register_purchase", {"amount": 10}, blocking=True)
    assert create.call_args.kwargs["notification_id"] == "middagsro_budget"
    # The amount as the card payment shows it.
    await hass.services.async_call(
        DOMAIN, "register_purchase", {"amount": "12,50 kr."}, blocking=True
    )
    assert 12.5 in [p["amount"] for p in store.purchases]
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "register_purchase", {"amount": "kr."}, blocking=True
        )
    store.budget_told = ""
    await store.async_set_settings({**store.settings, "watch_notify": "notify.findes_ikke"})
    await hass.services.async_call(
        DOMAIN,
        "register_purchase",
        {"amount": 10, "date": "2026-10-13", "note": "Kaffe"},
        blocking=True,
    )
    assert store.purchases[0]["note"] == "Kaffe"
    assert len(calls) == 1

    await store.async_set_settings({**store.settings, "monthly_budget": 0})
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "register_purchase", {"amount": 10}, blocking=True)
