"""The week's dinners from the avis: ready recipes priced with the week's offers.

The recipes that are ready (every item that is bought has a product: the
family's own and REMA's) are priced at the plan's first day. An item whose
product is on offer counts at the offer's price; an item that may be another
of its kind (not marked *exact*) takes an offer of the same kind when that is
cheaper ("hakket oksekød" on offer for the bolognese's minced beef). The
family's rules filter them (allergies and foods they avoid, dishes they don't
like, dishes from the last weeks), and the rest are ranked: the cheapest per
person, or the most saved on offers.

A recipe is priced as one package of each item, as REMA's recipe cards are:
an estimate to compare dishes by, not the shopping list.
"""

from __future__ import annotations

from datetime import date, datetime
from functools import lru_cache
import re
from typing import TYPE_CHECKING, Any

from homeassistant.util import dt as dt_util

from .api import Offer, Product, RemaError
from .dishes import food_conflicts, matches_any
from .linking import is_bought, kind_of, links
from .recipes import disliked_names
from .rema_recipes import current_price
from .words import pantry_words

if TYPE_CHECKING:
    from .mealplan import MealPlanner

SHOWN = 30
SORTS = ("cheapest", "offers")


# The kinds an offer may stand in for: things sold as themselves, where one is
# as good as another for a dish (not "oksekød", which can be steaks or mince).
SWAPPABLE = frozenset(
    {
        "hakket oksekød", "hakket svinekød", "hakket kylling", "hakket kalkun", "hakket lam",
        "kyllingebryst", "kyllingelår", "kyllingeinderfilet", "kyllingeoverlår",
        "laks", "torsk", "mørksejfilet", "rødspættefileter", "fiskefilet", "sej", "rejer",
        "flæskesteg", "svinemørbrad", "svinekoteletter", "koteletter", "nakkekoteletter",
        "pølser", "bacon", "medister", "pasta", "spaghetti", "nudler", "ris", "kartofler",
        "peberfrugt", "broccoli", "gulerødder", "løg", "rødløg", "hvidkål", "rødkål",
        "spidskål", "blomkål", "porrer", "squash", "champignon", "tomater", "agurk",
        "piskefløde", "madlavningsfløde", "creme fraiche", "æg", "revet ost", "mozzarella",
        "feta", "tortilla", "pitabrød", "naan", "kokosmælk", "hakkede tomater",
    }
)  # fmt: skip
# An offer of something made from the kind, not the kind itself ("brunede kartofler").
_PROCESSED = re.compile(
    r"\b(?:brunede|glas|gratin|pulled|røget|varmrøget|confiteret|confiterede|salat|chips|snacks)\b",
    re.IGNORECASE,
)
_ORIGIN = re.compile(
    r"\b(?:dansk|danske|udenlandsk|udenlandske|fersk|friske?|økologisk|øko\.?|frilands|fritgående)\b",
    re.IGNORECASE,
)


@lru_cache(maxsize=4096)
def _kind(name: str) -> str | None:
    return kind_of(name)


def heading_kinds(heading: str) -> set[str]:
    """The kinds of thing an avis offer is ("REMA 1000 Laksefileter, rødspættefileter
    eller mørksejfilet": laks, rødspættefileter, mørksejfilet), of those it may stand
    in for; none for something made from them."""
    if _PROCESSED.search(heading):
        return set()
    text = _ORIGIN.sub(" ", heading)
    parts = re.split(r",|\beller\b", text)
    if re.search(r"\bi\b", parts[0]):
        parts = parts[:1]  # "Tun i vand, olie eller tomat": what it is in, not more kinds
    return {k for part in parts if part.strip() and (k := _kind(part)) in SWAPPABLE}


def offer_kinds(offers: list[Offer]) -> dict[str, Offer]:
    """The week's offers by the kind of thing each is (the cheapest offer of a kind)."""
    by_kind: dict[str, Offer] = {}
    for offer in offers:
        if offer.price is None:
            continue
        for kind in heading_kinds(offer.heading):
            best = by_kind.get(kind)
            if best is None or (best.price or 0) > offer.price:
                by_kind[kind] = offer
    return by_kind


def price_recipe(
    ingredients: list[dict[str, Any]],
    prices: dict[int, tuple[float | None, bool]],
    offers: dict[str, Offer],
    pantry: list[str],
) -> dict[str, Any]:
    """A recipe's price this week: {cost, saving, on_offer: [names], swaps: [{item, offer}]}.

    ``prices``: each product's (price, on offer) at the plan's first day.
    """
    cost = 0.0
    saving = 0.0
    on_offer: list[str] = []
    swaps: list[dict[str, Any]] = []
    for ingredient in ingredients:
        if not is_bought(ingredient, pantry):
            continue
        product = ingredient.get("product") or {}
        price, offer = prices.get(int(product.get("id") or 0), (None, False))
        name = str(ingredient["name"])
        if offer:
            on_offer.append(name)
        elif not ingredient.get("exact") and (kind := _kind(name)):
            cheaper = offers.get(kind)
            if (
                cheaper is not None
                and cheaper.price is not None
                and (price is None or cheaper.price < price)
            ):
                if price is not None:
                    saving += price - cheaper.price
                swaps.append({"item": name, "offer": cheaper.heading, "price": cheaper.price})
                on_offer.append(name)
                price = cheaper.price
        cost += price or 0
    return {
        "cost": round(cost, 2),
        "saving": round(saving, 2),
        "on_offer": on_offer,
        "swaps": swaps,
    }


def _product_prices(products: list[Product]) -> dict[int, tuple[float | None, bool]]:
    return {p.id: (p.price, bool(p.is_advertised)) for p in products}


async def async_candidates(
    planner: MealPlanner, start: date, sort: str = "cheapest"
) -> dict[str, Any]:
    """The week's dinners from the avis, ranked; and how many the rules left out."""
    store = planner.store
    settings = store.settings
    pantry = pantry_words(str(settings.get("pantry") or ""))
    at: datetime | None = planner.price_time(start)
    catalog, offers = await planner._async_offers(start)
    by_kind = offer_kinds(offers)
    recent = store.recent_dishes(start, settings["no_repeat_weeks"])
    disliked = disliked_names(store)
    left_out = {"rules": 0, "recent": 0, "disliked": 0, "not_ready": 0}

    def allowed(name: str, ingredients: list[dict[str, Any]]) -> bool:
        if food_conflicts([str(i.get("name") or "") for i in ingredients], settings):
            left_out["rules"] += 1
            return False
        if matches_any(name, disliked):
            left_out["disliked"] += 1
            return False
        if matches_any(name, recent):
            left_out["recent"] += 1
            return False
        return True

    found: list[dict[str, Any]] = []
    # The family's own recipes, priced by REMA now.
    own = []
    for recipe in store.recipes:
        if not links(recipe, str(settings.get("pantry") or ""))["ready"]:
            left_out["not_ready"] += 1
            continue
        if recipe.get("rating") == "dislike" or not allowed(recipe["name"], recipe["ingredients"]):
            continue
        own.append(recipe)
    ids = sorted(
        {
            int(i["product"]["id"])
            for r in own
            for i in r["ingredients"]
            if isinstance(i.get("product"), dict)
        }
    )
    prices: dict[int, tuple[float | None, bool]] = {}
    if ids and planner.prices:
        try:
            prices = _product_prices(await planner.client.async_get_products(ids, at))
        except RemaError:
            prices = {}
    for recipe in own:
        price = price_recipe(recipe["ingredients"], prices, by_kind, pantry)
        found.append(
            {
                "source": "collection",
                "id": recipe["id"],
                "slug": recipe.get("rema_slug"),
                "name": recipe["name"],
                "image": recipe.get("image"),
                "servings": recipe.get("servings") or 4,
                "total_minutes": recipe.get("total_minutes") or None,
                "vegetarian": recipe.get("type") == "vegetar",
                "favorite": bool(recipe.get("favorite")),
                **price,
            }
        )
    # REMA's recipes, priced from what was read of them.
    mine = {r.get("rema_slug") for r in own if r.get("rema_slug")} | {
        r.get("rema_slug") for r in store.recipes if r.get("rema_slug")
    }
    moment = at or dt_util.utcnow()
    for entry in planner.rema_catalog.recipes.values():
        if entry["slug"] in mine:
            continue
        if not entry.get("ready"):
            left_out["not_ready"] += 1
            continue
        ingredients = entry["recipe"].get("ingredients") or []
        if not allowed(entry["title"], ingredients):
            continue
        entry_prices = {
            int(pid): current_price({"prices": p}, moment)
            for pid, p in (entry.get("prices") or {}).items()
        }
        price = price_recipe(ingredients, entry_prices, by_kind, pantry)
        found.append(
            {
                "source": "rema",
                "id": None,
                "slug": entry["slug"],
                "name": entry["title"],
                "image": entry.get("image"),
                "servings": entry.get("servings") or 4,
                "total_minutes": entry.get("total_minutes"),
                "vegetarian": bool(entry.get("vegetarian")),
                "favorite": False,
                **price,
            }
        )
    for item in found:
        item["per_person"] = round(item["cost"] / max(1, int(item["servings"])), 2)
    with_offers = [c for c in found if c["on_offer"]]
    if sort == "offers":
        with_offers.sort(key=lambda c: (-c["saving"], -len(c["on_offer"]), c["per_person"]))
    else:
        with_offers.sort(key=lambda c: (c["per_person"], -c["saving"]))
    return {
        "start": start.isoformat(),
        "avis": catalog.label if catalog else None,
        "offers": len(offers),
        "candidates": with_offers[:SHOWN],
        "total": len(with_offers),
        "without_offers": len(found) - len(with_offers),
        "left_out": left_out,
        "catalog": planner.rema_catalog.status(),
    }
