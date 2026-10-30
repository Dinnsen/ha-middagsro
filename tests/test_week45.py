"""What a real week-45 plan got wrong, with REMA's real products (October 2026)."""

from __future__ import annotations

from dataclasses import replace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.middagsro import mealplan as mp
from custom_components.middagsro.api import Offer, Product
from custom_components.middagsro.bilka import BILKA_ID
from custom_components.middagsro.ingredients import lookup, variety_conflict, variety_missing
from custom_components.middagsro.words import ingredient_name
from homeassistant.core import HomeAssistant

from .conftest import make_product

FG = "Frugt & grønt"
PEPPERS = "Agurk, tomat & peberfrugt"
SALADS = "Salater, fint grønt & avocado"
BREAD = "Brød & Bavinchi"

SEARCH: dict[str, list[Product]] = {
    "peber": [
        make_product(306369, "SNACK PEBER", 22, underline="500 GR. / LAND/KL.: SE VAREN",
                     department=FG, category=PEPPERS),
        make_product(90930, "STØDT SORT PEBER", 7.5, underline="100 GR. / REMA 1000",
                     department="Kolonial", category="Krydderier"),
        make_product(306382, "ØKO. PEBER", 13, underline="1 STK. / LAND/KL.: SE VAREN",
                     department=FG, category=PEPPERS, is_organic=True),
        make_product(306351, "GUL/ORANGE PEBER", 9, underline="1 STK. / SPANIEN KL. 1",
                     department=FG, category=PEPPERS),
        make_product(100840, "PEBERFRUGT STRIMLER", 12.23, underline="180 GR. / REMA 1000",
                     department="Kolonial", category="Konserves & survarer"),
    ],
    "salat": [
        make_product(306446, "ØKO. HJERTESALAT", 15, underline="1 POSE / DANMARK KL. 1",
                     department=FG, category=SALADS, is_organic=True),
        make_product(306215, "ICEBERG SALAT", 12, underline="1 STK. / LAND/KL.: SE VAREN",
                     department=FG, category=SALADS),
        make_product(306447, "ØKO. RUCOLA", 10, underline="75 GR. / ITALIEN KL.1",
                     department=FG, category=SALADS, is_organic=True),
    ],
    "baguette": [
        make_product(360729, "MØRK BAGUETTE", 16, underline="300 GR. / BAVINCHI",
                     department=BREAD, category="Bavinchi bager"),
        make_product(60309, "FLUTES", 6.5, underline="300 GR. / REMA 1000",
                     department=BREAD, category="Baguette/flutes"),
    ],
}  # fmt: skip
SWEET_BREAD = make_product(62632, "SØDMÆLKSBRØD", 15, underline="600 GR. / SCHULSTAD",
                           department=BREAD, category="Brød")  # fmt: skip


async def _search(query: str, limit: int = 15, at: Any = None) -> list[Product]:
    return SEARCH.get(query.lower(), [])[:limit]


def _offer(heading: str, quantity: str | None = None, **kwargs: Any) -> Offer:
    return Offer(id=heading, heading=heading, description=None, price=kwargs.pop("price", 10),
                 pre_price=None, quantity=quantity, valid_from=None, valid_to=None, **kwargs)  # fmt: skip


def test_names_and_catalogue() -> None:
    """A recipe's instructions are not part of the thing; the catalogue knows the kinds."""
    assert ingredient_name("Kaffirblade, fjern stilken i midten og striml bladene fint") == (
        "Kaffirblade"
    )
    assert ingredient_name("galangarod, skrællet og skåret i tynde skiver") == "galangarod"
    assert lookup("Rød peber").key == lookup("Rød peberfrugt").key == "peberfrugt"  # type: ignore[union-attr]
    assert lookup("Mini-baguettes").key == "baguette"  # type: ignore[union-attr]
    assert lookup("Pølser (oste)").key == "pølser"  # type: ignore[union-attr]


def test_varieties() -> None:
    """A colour or a sort the line names must not be another on the product."""
    assert variety_conflict("Rød peberfrugt", "GUL/ORANGE PEBER")
    assert not variety_conflict("Rød peberfrugt", "ØKO. PEBER")
    assert variety_missing("Rød peberfrugt", "ØKO. PEBER")
    assert not variety_missing("Rød peber", "RØD PEBER")
    assert variety_conflict("Romainesalat", "ICEBERG SALAT")
    assert variety_conflict("Romainesalat", "ØKO. HJERTESALAT")
    assert not variety_conflict("Salat", "ICEBERG SALAT")
    assert not variety_conflict("Rødløg", "RØDLØG")
    assert not variety_conflict("Grønne bønner", "GRØNNE BØNNER")


def test_avis_pieces() -> None:
    """8 pølser are one 330 g avis pack (16 are two), not eight packs."""
    sausages = _offer("Langelænder pølser", "330 g", price=20)
    piece = lookup("pølser").piece_g  # type: ignore[union-attr]
    assert mp.avis_packages(8, "stk", sausages, piece) == 1
    assert mp.avis_packages(16, "stk", sausages, piece) == 2
    assert mp.avis_packages(8, "stk", sausages) == 8  # nothing known of a piece
    assert mp.avis_packages(660, "g", sausages, piece) == 2


async def test_week45_lines(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Red pepper, romaine and mini-baguettes get the right product, or a check."""
    mock_client.async_search_products.side_effect = _search
    mock_client.async_get_products.side_effect = None
    mock_client.async_get_products.return_value = [SWEET_BREAD]
    planner = init_integration.runtime_data.planner

    pepper = planner._clean_line(
        {"name": "Rød peberfrugt", "amount": 2, "unit": "stk", "search": "peber",
         "category": "Frugt & grønt"}
    )  # fmt: skip
    assert pepper is not None
    await planner._async_match(pepper)
    assert pepper["product"]["name"] == "ØKO. PEBER"  # never the yellow/orange one
    assert pepper["confidence"] == "medium"  # red isn't on the product: to be checked

    salad = planner._clean_line(
        {"name": "Romainesalat", "amount": 1, "unit": "stk", "search": "salat",
         "category": "Frugt & grønt"}
    )  # fmt: skip
    assert salad is not None
    await planner._async_match(salad)
    assert salad["product"] is None  # iceberg, hjertesalat and rucola are other salads
    assert salad["confidence"] == "low"

    bread = planner._clean_line(
        {"name": "Mini-baguettes", "amount": 1, "unit": "pk", "search": "brød",
         "category": "Brød"}
    )  # fmt: skip
    assert bread is not None
    schulstad = replace(_offer("Schulstad brød", "350 g", price=15), product_ids=(62632,))
    await planner._async_match(bread, None, schulstad)
    assert bread["product"]["name"] == "FLUTES"  # not the offer's sødmælksbrød


async def test_bilka_for_what_rema_has_no_sure_product(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Uncertain lines are looked for in Bilka ToGo: a sure match goes on Bilka's list."""
    store = init_integration.runtime_data.store
    await store.async_set_settings({"chains": [BILKA_ID]})
    planner = init_integration.runtime_data.planner
    romaine = make_product(5001, "ROMAINESALAT", 14.95, underline="1 STK.", department=FG,
                           category="Salat")  # fmt: skip

    async def bilka(query: str, limit: int = 12) -> list[Product]:
        return [romaine] if "romaine" in query.lower() else []

    planner.bilka = MagicMock(async_search=AsyncMock(side_effect=bilka))
    plan: dict[str, Any] = {
        "shopping": [
            {"id": "a", "name": "Romainesalat", "search": "salat", "amount": 1, "unit": "stk",
             "category": "Frugt & grønt", "product": None, "confidence": "low",
             "note": "Ingen sikker vare fundet – tilføjes som fritekst", "cost": None},
            {"id": "b", "name": "Galangarod", "search": "galangarod", "amount": 1, "unit": "stk",
             "category": "Frugt & grønt", "product": None, "confidence": "low",
             "note": "Ingen sikker vare fundet – tilføjes som fritekst", "cost": None},
            {"id": "c", "name": "Løg", "search": "løg", "amount": 1, "unit": "kg",
             "product": {"id": 1, "name": "LØG", "price": 8}, "confidence": "high", "cost": 8},
        ]
    }  # fmt: skip
    await planner._async_bilka_fallback(plan)
    lines = {line["id"]: line for line in plan["shopping"]}
    assert lines["a"]["buy_at"] == BILKA_ID
    assert lines["a"]["chain_price"] == 14.95
    assert lines["a"]["confidence"] == "high"
    assert not mp.needs_review(lines["a"])
    assert "buy_at" not in lines["b"]
    assert mp.needs_review(lines["b"])
    assert lines["b"]["note"] == "Ingen sikker vare i REMA eller Bilka – tilføjes som fritekst"
    assert "buy_at" not in lines["c"]  # a sure REMA line is not looked for elsewhere
    assert plan["total"] == round(14.95 + 8, 2)

    # Without Bilka among the shops, nothing is searched.
    await store.async_set_settings({"chains": []})
    planner.bilka.async_search.reset_mock()
    await planner._async_bilka_fallback({"shopping": [dict(lines["b"])]})
    assert not planner.bilka.async_search.called


async def test_find_items_again(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Find varer igen: unsent items are matched again; the family's own stay."""
    from .conftest import make_plan  # noqa: PLC0415

    mock_client.async_search_products.side_effect = _search
    store = init_integration.runtime_data.store
    planner = init_integration.runtime_data.planner
    plan = make_plan("w45", start="2026-11-01")
    yellow = {"id": 306351, "name": "GUL/ORANGE PEBER", "price": 9}
    plan["shopping"] = [
        {"id": "p1", "name": "Rød peber", "amount": 1, "unit": "stk", "search": "peber",
         "category": "Frugt & grønt", "key": "peber", "product": yellow, "packages": 1,
         "cost": 9, "confidence": "high"},
        {"id": "p2", "name": "Rød peberfrugt", "amount": 2, "unit": "stk", "search": "peber",
         "category": "Frugt & grønt", "key": "peberfrugt", "product": yellow, "packages": 2,
         "cost": 18, "confidence": "high"},
        {"id": "own", "name": "Kvark", "amount": 640, "unit": "g", "search": "kvark",
         "category": "Mejeri", "product_id": 21930, "confidence": "high", "packages": 2,
         "cost": 35.9, "product": {"id": 21930, "name": "FRAICHE 9%", "price": 17.95}},
        {"id": "sent", "name": "Salat", "amount": 1, "unit": "stk", "search": "salat",
         "category": "Frugt & grønt", "sent": "2026-10-31T10:00:00", "packages": 1,
         "cost": 12, "product": {"id": 306215, "name": "ICEBERG SALAT", "price": 12}},
    ]  # fmt: skip
    await store.async_add_plan(plan)
    result = await planner.async_rematch_all("w45")
    lines = {line["id"]: line for line in result["shopping"]}
    assert "p2" not in lines  # red pepper and red peberfrugt are one line now
    assert lines["p1"]["amount"] == 3
    assert lines["p1"]["product"]["name"] == "ØKO. PEBER"
    assert lines["p1"]["confidence"] == "medium"
    assert lines["own"]["product"]["name"] == "FRAICHE 9%"  # the family's choice stays
    assert lines["sent"]["product"]["name"] == "ICEBERG SALAT"  # in the app already
    assert result["total"] == round(lines["p1"]["cost"] + 35.9 + 12, 2)
