"""Tests for the stored settings, favourites and plans."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from custom_components.middagsro.storage import (
    DEFAULT_SETTINGS,
    MAX_PLANS,
    RemaPlanStore,
    clean_settings,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .conftest import make_plan


def test_clean_settings_defaults() -> None:
    """Empty input gives the defaults."""
    assert clean_settings({}) == DEFAULT_SETTINGS


def test_clean_settings_limits_and_types() -> None:
    """Values are kept in range and wrong values fall back."""
    settings = clean_settings(
        {
            "start_weekday": 9,
            "days": "0",
            "budget": "abc",
            "organic": "sometimes",
            "organic_max_extra_pct": -5,
            "avoid": ["pork", "chocolate"],
            "allergies": ["nuts", "glitter"],
            "pantry": None,
            "wishes": "x" * 3000,
            "ai_task_entity": "",
            "auto_generate": 1,
            "egg_min": "golden",
            "milk_organic": "yes",
            "household": [
                {"role": "child", "age": 300, "sex": "female"},
                {"role": "pet", "age": "x", "sex": "?"},
                "not a member",
            ],
            "must_haves": [
                {"name": " Kaffe ", "product_id": "123", "amount": 200},
                {"name": " "},
                "x",
            ],
            "disliked_dishes": ["  Fiskefrikadeller ", "", None, "y" * 400] + ["a"] * 60,
            "fixed_days": [{"weekday": 3, "text": "Rugbrødsdag"}, {"weekday": 1, "text": " "}],
            "unknown_key": True,
        }
    )
    assert settings["start_weekday"] == 6
    assert settings["days"] == 1
    assert settings["budget"] == 500
    assert settings["organic"] == "prefer"
    assert settings["organic_max_extra_pct"] == 0
    assert settings["avoid"] == ["pork"]
    assert settings["allergies"] == ["nuts"]
    assert settings["pantry"] == ""
    assert len(settings["wishes"]) == 2000
    assert settings["ai_task_entity"] is None
    assert settings["auto_generate"] is True
    assert settings["egg_min"] == "caged"
    assert settings["milk_organic"] is True
    assert settings["household"] == [
        {"role": "child", "age": 120, "sex": "female"},
        {"role": "adult", "age": 30, "sex": "other"},
    ]
    assert settings["must_haves"] == [{"name": "Kaffe", "product_id": 123, "amount": 99}]
    assert settings["disliked_dishes"][0] == "Fiskefrikadeller"
    assert len(settings["disliked_dishes"][1]) == 300
    assert len(settings["disliked_dishes"]) == 50
    assert settings["fixed_days"] == [{"weekday": 3, "text": "Rugbrødsdag"}]
    assert "unknown_key" not in settings


async def test_store_round_trip(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Settings, favourites and plans survive a restart."""
    store = RemaPlanStore(hass, "entry")
    await store.async_load()
    assert store.latest_plan is None
    await store.async_set_settings({"budget": 700})
    fav = await store.async_save_favorite({"text": "Lasagne", "frequency": "weekly"})
    await store.async_add_plan(make_plan())

    again = RemaPlanStore(hass, "entry")
    await again.async_load()
    assert again.settings["budget"] == 700
    assert again.favorites[0]["id"] == fav["id"]
    assert again.latest_plan is not None
    assert again.latest_plan["id"] == "plan-1"


async def test_favorites(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Favourites are due by their frequency."""
    store = RemaPlanStore(hass, "entry")
    weekly = await store.async_save_favorite({"text": "Tacos", "frequency": "weekly"})
    monthly = await store.async_save_favorite({"text": "Lasagne", "frequency": "monthly"})
    offer = await store.async_save_favorite({"text": "Laks", "frequency": "on_offer"})
    unknown = await store.async_save_favorite({"text": "Suppe", "frequency": "daily"})
    assert unknown["frequency"] == "inspiration"
    with pytest.raises(ServiceValidationError):
        await store.async_save_favorite({"text": "  "})

    monthly["last_used"] = "2026-10-01"
    due, optional = store.favorites_due(date(2026, 10, 18))
    assert [f["id"] for f in due] == [weekly["id"]]
    assert {f["id"] for f in optional} == {monthly["id"], offer["id"], unknown["id"]}

    due, _ = store.favorites_due(date(2026, 11, 1))
    assert monthly["id"] in [f["id"] for f in due]

    changed = await store.async_save_favorite({"id": weekly["id"], "text": "Fisketacos"})
    assert changed["text"] == "Fisketacos"
    await store.async_delete_favorite(weekly["id"])
    assert weekly["id"] not in [f["id"] for f in store.favorites]


async def test_plans(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Plans: newest first, at most MAX_PLANS, sent and deleted."""
    store = RemaPlanStore(hass, "entry")
    fav = await store.async_save_favorite({"text": "Spaghetti", "frequency": "weekly"})
    plan = make_plan("p0", start="2026-10-04")
    plan["days"][0]["favorite_id"] = fav["id"]
    await store.async_add_plan(plan)
    assert store.favorites[0]["last_used"] == "2026-10-04"

    for week in range(MAX_PLANS + 2):
        await store.async_add_plan(make_plan(f"p{week + 1}", start="2026-10-11"))
    assert len(store.plans) == MAX_PLANS
    assert store.latest_plan is not None
    assert store.latest_plan["id"] == f"p{MAX_PLANS + 2}"
    assert store.get_plan("p0") is None
    assert store.plan_for_start(date(2026, 10, 11)) is store.latest_plan
    assert store.plan_for_start(date(2026, 1, 1)) is None

    await store.async_mark_sent("p5")
    sent = store.get_plan("p5")
    assert sent is not None
    assert sent["status"] == "sent"
    assert sent["sent_at"]
    await store.async_mark_sent("missing")
    await store.async_delete_plan("p5")
    assert store.get_plan("p5") is None


async def test_recent_dishes(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Dishes from the weeks before a plan are not repeated."""
    store = RemaPlanStore(hass, "entry")
    await store.async_add_plan(make_plan("old", start="2026-09-01"))
    await store.async_add_plan(make_plan("last", start="2026-10-11"))
    recent = store.recent_dishes(date(2026, 10, 18), 3)
    assert recent == [
        "Spaghetti bolognese",
        "Rester af spaghetti bolognese",
        "Kyllingewok med broccoli",
    ]
    assert store.recent_dishes(date(2026, 10, 18), 0) == []


async def test_note_and_plan_covering(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """The wishes for the next plan are saved; the plan with a day's dinner is found."""
    store = RemaPlanStore(hass, "entry")
    note = await store.async_set_note("  Pizza fredag  " + "x" * 2000)
    assert note.startswith("Pizza fredag")
    assert len(note) == 1000
    other = RemaPlanStore(hass, "entry")
    await other.async_load()
    assert other.note == store.note
    assert await store.async_set_note("") == ""

    await store.async_add_plan(make_plan("week42", start="2026-10-15"))  # 15-17 Oct
    await store.async_add_plan(make_plan("week43", start="2026-10-18"))
    covering = store.plan_covering(date(2026, 10, 17))
    assert covering is not None
    assert covering["id"] == "week42"
    covering = store.plan_covering(date(2026, 10, 18))
    assert covering is not None
    assert covering["id"] == "week43"
    assert store.plan_covering(date(2026, 10, 1)) is None
    # Tonight skipped: the plan still counts, so the rest of its days are shown.
    week42 = store.get_plan("week42")
    assert week42 is not None
    week42["days"] = [d for d in week42["days"] if d["date"] != "2026-10-16"]
    covering = store.plan_covering(date(2026, 10, 16))
    assert covering is not None
    assert covering["id"] == "week42"


async def test_timeline(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """This week and the coming days as one plan: the newest plan covering a date decides."""
    store = RemaPlanStore(hass, "entry")
    assert store.timeline(date(2026, 10, 19), 6) == []
    await store.async_add_plan(make_plan("old", start="2026-10-18"))  # 18-20 Oct
    newer = make_plan("new", start="2026-10-19")  # 19-21 Oct, no dinner the 20th
    newer["days"] = [d for d in newer["days"] if d["date"] != "2026-10-20"]
    await store.async_add_plan(newer)
    timeline = store.timeline(date(2026, 10, 19), 6)  # a monday; the week starts sunday
    assert [(e["date"], e["plan_id"], e["skipped"]) for e in timeline] == [
        ("2026-10-18", "old", False),
        ("2026-10-19", "new", False),
        ("2026-10-20", "new", True),
        ("2026-10-21", "new", False),
    ]
    assert {e["week"] for e in timeline} == {43}
    plan, day = store.dinner(date(2026, 10, 20))
    assert plan is not None and plan["id"] == "new"
    assert day is None
    assert store.dinner(date(2026, 10, 30)) == (None, None)
    # A plan into next week: its days there are in the next week.
    await store.async_add_plan(make_plan("next", start="2026-10-24"))  # 24-26 Oct
    weeks = {e["date"]: e["week"] for e in store.timeline(date(2026, 10, 19), 6)}
    assert (weeks["2026-10-24"], weeks["2026-10-25"]) == (43, 44)
    # Everything has ended.
    assert store.timeline(date(2026, 11, 2), 6) == []
