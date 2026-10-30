"""The shared product table (links.py) and saving a plan as test cases (record.py)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.middagsro import links
from custom_components.middagsro.api import RemaError
from custom_components.middagsro.links import family_links, link_name, merge, share_url
from custom_components.middagsro.record import answered
from homeassistant.core import HomeAssistant

from .conftest import make_plan, make_product

RED = make_product(306353, "RØD PEBER", 7.0, department="Frugt & grønt", underline="1 STK.")
ECO_RED = make_product(
    306355, "ØKO. RØD PEBER", 9.0, department="Frugt & grønt", underline="1 STK.", is_organic=True
)
YELLOW = make_product(306351, "GUL/ORANGE PEBER", 6.0, department="Frugt & grønt")
CAGED = make_product(10001, "SKRABEÆG M/L", 20.0, department="Mejeri", underline="10 STK.")
ORGANIC_EGGS = make_product(
    10002, "ØKOLOGISKE ÆG", 32.0, department="Mejeri", underline="10 STK.", is_organic=True
)
SHOP = {p.id: p for p in (RED, ECO_RED, YELLOW, CAGED, ORGANIC_EGGS)}


async def _products(ids: list[int], at: Any = None) -> list[Any]:
    return [SHOP[i] for i in ids if i in SHOP]


def _line(name: str, amount: float = 1, unit: str = "stk", **extra: Any) -> dict[str, Any]:
    return {"name": name, "amount": amount, "unit": unit, "search": name.lower(), **extra}


def test_link_names() -> None:
    """A name in the table: lower case, no preparation, counting words or organic."""
    assert link_name("Rød peberfrugt") == "rød peberfrugt"
    assert link_name("Økologisk rød peberfrugt, i strimler") == "rød peberfrugt"
    assert link_name("3 fed hvidløg") == link_name("Hvidløg") == "hvidløg"
    assert link_name("Ostepølser") != link_name("Pølser")


def test_merge_keeps_only_what_everyone_agrees_on() -> None:
    assert merge(
        [
            ("Rød peberfrugt", [306353, 306355]),
            ("rød peberfrugt", [306355]),
            ("Pølser", [1]),
            ("pølser", [2]),
            ("", [3]),
            ("Løg", []),
        ]
    ) == {"rød peberfrugt": [306355]}


def test_family_links_and_sharing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only lines the family kept or chose are shared, and only what the table lacks."""
    plan = make_plan("links")
    plan["shopping"] = [
        {"name": "Rød peberfrugt", "product": {"id": 306355}, "reviewed": True},
        {"name": "Agurk", "product": {"id": 306008}, "remembered": True},
        {"name": "Persille", "product": {"id": 1}, "reviewed": True, "skipped": True},
        {"name": "Kaffe", "product": {"id": 2}, "reviewed": True, "added": True},
        {"name": "Løg", "product": {"id": 3}},
    ]
    found = family_links([plan])
    assert found == {"agurk": [306008], "rød peberfrugt": [306355]}
    monkeypatch.setattr(links, "LINKS", {"rema": {"agurk": (306008,)}})
    url = share_url("REMA 1000", found)
    assert url is not None
    query = parse_qs(urlparse(url).query)
    assert query["title"] == ["Koblinger: 1 varer"]
    body = query["body"][0]
    shared = json.loads(body.split("```json\n")[1].split("\n```")[0])
    assert shared == {"shop": "rema", "links": {"rød peberfrugt": [306355]}}
    assert share_url("Netto", found) is None  # no table for that shop
    assert share_url("REMA 1000", {"agurk": [306008]}) is None  # nothing new
    many = {f"vare nummer {i}": [100000 + i] for i in range(400)}
    long = share_url("REMA 1000", many)
    assert long is not None
    assert len(long) <= 7500
    assert 0 < int(parse_qs(urlparse(long).query)["title"][0].split()[1]) < 400


def test_the_table_file() -> None:
    """The table that ships is read, and an unreadable one is no table."""
    assert links.LINKS["rema"]["agurk"]
    assert links.linked_ids("Netto", "Agurk") == ()
    assert links.linked_ids("REMA 1000", "Agurk") == links.LINKS["rema"]["agurk"]


def test_unreadable_table(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    monkeypatch.setattr(links, "LINKS_FILE", tmp_path / "missing.json")
    assert links._load() == {}
    broken = tmp_path / "links.json"
    broken.write_text(json.dumps({"shops": {"rema": {"a": [1, "x"], "b": [], "c": "no"}}}))
    monkeypatch.setattr(links, "LINKS_FILE", broken)
    assert links._load() == {"rema": {"a": (1,)}}


async def test_matched_by_the_table(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A name the table knows is that product, without a search; the family's rules
    still decide among the table's products, and a product they said no to is out."""
    monkeypatch.setattr(
        links,
        "LINKS",
        {"rema": {"rød peberfrugt": (306353, 306355, 306351), "æg": (10001, 10002)}},
    )
    mock_client.async_get_products.side_effect = _products
    store = init_integration.runtime_data.store
    planner = init_integration.runtime_data.planner

    await store.async_set_settings({"organic": "none"})
    line = planner._clean_line(_line("Rød peberfrugt", 2))
    await planner._async_match(line)
    assert line["product"]["id"] == 306353  # the cheapest; yellow is another colour
    assert line["confidence"] == "high"
    assert line["linked"] is True
    assert line["packages"] == 2
    assert not mock_client.async_search_products.called
    assert planner._clean_line(_line("Gul peberfrugt")) is not None

    await store.async_set_settings({"organic": "only"})
    await planner._async_match(line)
    assert line["product"]["id"] == 306355

    # Organic eggs at least: the caged ones in the table are not taken.
    await store.async_set_settings({"organic": "none", "egg_min": "organic"})
    eggs = planner._clean_line(_line("Æg", 10))
    await planner._async_match(eggs)
    assert eggs["product"]["id"] == 10002

    await store.async_reject_product(eggs["key"], planner.shop, 10002)
    mock_client.async_search_products.side_effect = None
    mock_client.async_search_products.return_value = []
    await planner._async_match(eggs)
    assert not eggs.get("linked")  # nothing left in the table: searched by name

    # Not sold any more, or REMA doesn't answer: by name, as before.
    monkeypatch.setattr(links, "LINKS", {"rema": {"rød peberfrugt": (999,)}})
    await planner._async_match(line)
    assert not line.get("linked")
    monkeypatch.setattr(links, "LINKS", {"rema": {"rød peberfrugt": (306353,)}})
    mock_client.async_get_products.side_effect = RemaError("nede")
    await planner._async_match(line)
    assert not line.get("linked")


def test_answered() -> None:
    """What the family said a line is."""
    product = {"id": 5}
    assert answered({"product": product, "reviewed": True}) == [5]
    assert answered({"product": product, "remembered": True}) == [5]
    assert answered({"product": product, "reviewed": True, "skipped": True}) == "unknown"
    assert answered({"reviewed": True, "skipped": True}) is None
    assert answered({"product": product}) is None
    assert answered({"product": product, "reviewed": True, "added": True}) is None
    assert answered({"product": product, "reviewed": True, "buy_at": "93f13"}) is None


async def test_record_and_share_over_websocket(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    hass_ws_client: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gem som testsag: the answered lines with REMA's answers, replayable by name;
    Del jeres valg: a GitHub link with them."""
    monkeypatch.setattr(links, "LINKS", {"rema": {}})

    async def search(query: str, limit: int = 15, **kwargs: Any) -> list[Any]:
        return [RED, ECO_RED, YELLOW] if "peber" in query else []

    mock_client.async_search_products.side_effect = search
    mock_client.async_get_products.side_effect = _products
    store = init_integration.runtime_data.store
    plan = make_plan("rec")
    plan["shopping"] = [
        {**_line("Rød peberfrugt", 2), "id": "a", "key": "peberfrugt",
         "product": {"id": 306355, "name": "ØKO. RØD PEBER"}, "reviewed": True},
        {**_line("Gul peberfrugt"), "id": "b", "key": "peberfrugt",
         "product": {"id": 306353, "name": "RØD PEBER"}, "reviewed": True, "skipped": True},
        {**_line("Persille"), "id": "c", "key": "persille", "product": {"id": 7}},
    ]  # fmt: skip
    await store.async_add_plan(plan)
    await store.async_remember_choice("peberfrugt", "REMA 1000", 306355, "ØKO. RØD PEBER")
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "middagsro/plan/record", "plan_id": "rec"})
    answer = await client.receive_json()
    assert answer["success"], answer
    record = answer["result"]
    assert [c["expect"] for c in record["cases"]] == [[306355], "unknown"]
    assert record["cases"][1]["not"] == [306353]
    assert any("peber" in query for query in record["searches"])
    assert {p["id"] for p in record["products"]} >= {306355, 306353}
    assert record["shop"] == "REMA 1000"

    await client.send_json({"id": 2, "type": "middagsro/plan/record", "plan_id": "nope"})
    answer = await client.receive_json()
    assert not answer["success"]

    await client.send_json({"id": 3, "type": "middagsro/links/share"})
    answer = await client.receive_json()
    assert answer["success"], answer
    assert answer["result"]["count"] == 1
    assert "github.com" in answer["result"]["url"]


async def test_record_survives_rema_errors(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    from custom_components.middagsro.record import async_record_plan  # noqa: PLC0415

    mock_client.async_search_products.side_effect = RemaError("nede")
    mock_client.async_get_products.side_effect = RemaError("nede")
    plan = make_plan("err")
    plan["shopping"] = [
        {**_line("Rød peberfrugt"), "product": {"id": 306355}, "reviewed": True},
        {"name": "", "product": {"id": 1}, "reviewed": True},
    ]
    record = await async_record_plan(init_integration.runtime_data.planner, plan)
    assert len(record["cases"]) == 1  # a line that is no line is no case
    assert record["searches"] == {}
