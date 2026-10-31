"""Finding the products for a plan's shopping lines: the family's choice, the
shared table, the avis offers and the shop's search, and pricing them."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import date, datetime
import logging
import math
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .amounts import line_packages, package_size, packages_needed, to_base
from .api import DANISH_TIME, TJEK_DEALER_ID, Offer, Product, RemaClient, RemaError, parse_time
from .bilka import BilkaSearch
from .errors import _invalid
from .ingredients import (
    Spec,
    allowed,
    other_thing,
    qualifier_only,
    variety_conflict,
    variety_missing,
)
from .links import linked_ids
from .matching import (
    _DESCRIBING,
    _EGG_LEVEL,
    FREE_FROM,
    SEARCH_CONCURRENCY,
    _alternative,
    _called,
    _percents,
    apply_spec,
    avis_packages,
    egg_level,
    head_word,
    kind_penalty,
    line_kind,
    line_spec,
    merge_lines,
    name_fit,
    needs_review,
    noon,
    offer_covers,
    offer_query,
    plan_total,
    prices_from,
    search_queries,
)
from .shops import OtherShop, async_search, next_shops
from .storage import RemaPlanStore
from .store_client import genitive, store_name
from .words import (
    _NEUTRAL_WORDS,
    _tokens,
    canned_tomato_product,
    canned_tomatoes,
    herb_form_matches,
    ingredient_name,
)

if TYPE_CHECKING:
    from .bilka import BilkaSearch

_LOGGER = logging.getLogger(__name__)


class ProductMatcher:
    """The planner's product matching (mealplan.MealPlanner is one)."""

    hass: HomeAssistant
    client: RemaClient
    store: RemaPlanStore
    bilka: BilkaSearch
    _search_cache: dict[tuple[str, str], list[Product]] | None
    _send_lock: asyncio.Lock

    if TYPE_CHECKING:

        def _notify(self) -> None: ...

        async def _async_ai_choices(self, plan: dict[str, Any]) -> None: ...

    @staticmethod
    def price_time(start: date) -> datetime | None:
        """When to read prices for a plan: noon on its first day, or now (None).

        A plan for next week is bought next week, so it gets next week's
        prices and offers, matching the avis it is built on.
        """
        return noon(start)

    @property
    def prices(self) -> bool:
        """Every item has a price (REMA 1000); with another shop only the offers have."""
        return bool(self.client.has_prices)

    @property
    def dealer_id(self) -> str:
        """The shop's id on Tjek: REMA 1000's, or the shop chosen instead."""
        return str(getattr(self.client, "dealer_id", TJEK_DEALER_ID))

    @property
    def shop(self) -> str:
        """Where the family shops: REMA 1000, Netto, føtex ..."""
        return "REMA 1000" if self.dealer_id == TJEK_DEALER_ID else store_name(self.dealer_id)

    async def _async_next_shops(self, plan: dict[str, Any]) -> None:
        """Look in the next shops (shops.py: Bilka ToGo) for what REMA has no sure
        product for (galangarod, romainesalat …). A sure match there goes on that
        shop's list at its price; a line no shop is sure of stays for the family's
        check."""
        shops = next_shops(self)
        if not shops:
            return
        lines = [
            line
            for line in plan["shopping"]
            if needs_review(line)
            and not line.get("buy_at")
            and not line.get("avis_item")
            and not line.get("product_id")
            and (not line.get("product") or line.get("confidence") == "low")
        ]
        if not lines:
            return
        semaphore = asyncio.Semaphore(4)
        here = self.shop.removesuffix(" 1000")
        names = " eller ".join(shop.name for shop in shops)

        async def look(line: dict[str, Any]) -> None:
            asked = False
            for shop in shops:
                # The line's own name first ("Romainesalat"), then the search ("salat").
                for query in dict.fromkeys((ingredient_name(line["name"]), line["search"])):
                    async with semaphore:
                        found = await async_search(shop, query, 15)
                    if found is None:
                        _LOGGER.debug("%s not searched for %s", shop.name, query)
                        break
                    asked = True
                    if (product := self._sure_elsewhere(line, found)) is not None:
                        self._buy_elsewhere(line, shop, product, here)
                        return
            if not asked:
                return  # no shop could be asked: the line stays as it was
            line["note"] = (
                f"{line['note']} (heller ikke sikker i {names})"
                if line.get("product") and line.get("note")
                else f"Ingen sikker vare i {here} eller {names} – tilføjes som fritekst"
                if not line.get("product")
                else f"Heller ikke sikker i {names} – tjek den"
            )

        await asyncio.gather(*(look(line) for line in lines))
        plan["total"] = plan_total(plan["shopping"])

    @staticmethod
    def _buy_elsewhere(line: dict[str, Any], shop: OtherShop, product: Product, here: str) -> None:
        """A line goes on another shop's list, with that shop's product and price."""
        spec = line_spec(line)
        packages = line_packages(line, product, spec.piece_g)
        line.update(
            buy_at=shop.dealer_id,
            chain_price=product.price,
            chain_heading=f"{product.name} ({product.underline})"
            if product.underline
            else product.name,
            bought=False,
            packages=packages,
            cost=round(packages * (product.price or 0), 2),
            confidence="high",
            note=f"Ikke sikkert i {here} – fundet i {shop.name}",
        )

    def _sure_elsewhere(self, line: dict[str, Any], products: list[Product]) -> Product | None:
        """The product of another shop that surely is the line (by REMA's own rules)."""
        candidates, penalty = self._candidates(line, products, line["search"], limit=15)
        spec = line_spec(line)
        sure = []
        for p in candidates:
            if not p.price or penalty.get(p.id, 1.0) >= 2:
                continue
            if variety_missing(line.get("name") or "", p.name):
                continue
            for query in (line["search"], line["name"]):
                words = [w for w in _tokens(query) if len(w) > 1 and w not in _NEUTRAL_WORDS]
                head = head_word(query)
                if words and (
                    name_fit(words, p.name)[0] == len(words)
                    or bool(head and head in _tokens(p.name))
                    or _called(spec, p.name)
                ):
                    sure.append(p)
                    break
        if not sure:
            return None

        def cost(p: Product) -> float:
            count = line_packages(line, p, spec.piece_g)
            return count * (p.price or 0) * penalty.get(p.id, 1.0)

        return min(sure, key=cost)

    async def _async_search(self, query: str, at: datetime | None) -> list[Product]:
        """Search REMA, priced now or (at) when the plan is bought."""
        key = (query.lower(), at.isoformat() if at else "")
        if self._search_cache is not None and key in self._search_cache:
            return self._search_cache[key]
        if at is None:
            products = await self.client.async_search_products(query, 15)
        else:
            products = await self.client.async_search_products(query, 15, at=at)
        if self._search_cache is not None:
            self._search_cache[key] = products
        return products

    async def _async_match(
        self, line: dict[str, Any], at: datetime | None = None, offer: Offer | None = None
    ) -> None:
        """Pick a REMA product for a shopping line and price it (now, or at a time).

        A product the family chose for this ingredient before is taken first,
        without a search; otherwise the best by name, kind and price, with how
        sure that is written on the line (``confidence``: high, medium or low,
        and ``alternatives`` to choose from when it isn't high).
        """
        line.update(product=None, avis_item=None, packages=1, cost=None, note=None)
        for key in ("price_source", "alternatives", "reviewed", "remembered", "linked"):
            line.pop(key, None)
        line["confidence"] = "high"
        if not line.get("product_id"):
            line["search"] = ingredient_name(line["search"])
            if "key" not in line:
                apply_spec(line)
        try:
            if (
                not line.get("product_id")
                and not line.get("must_have")
                and offer is None
                and self.prices
                and (
                    await self._async_match_remembered(line, at)
                    or await self._async_match_linked(line, at)
                )
            ):
                return
            products = await self._async_search(line["search"], at)
            if not line.get("product_id") and not line.get("must_have"):
                await self._async_match_by_name(line, products, at, offer)
                return
            if not products and line["search"] != line["name"]:
                products = await self._async_search(line["name"], at)
        except RemaError as err:
            line["note"] = f"Søgning fejlede: {err}"
            return

        if line.get("product_id"):
            chosen = next((p for p in products if p.id == line["product_id"]), None)
            if chosen is None:
                # A recipe's own REMA product: not always among the search results.
                try:
                    chosen = next(
                        iter(await self.client.async_get_products([line["product_id"]], at)), None
                    )
                except RemaError:
                    chosen = None
            if chosen:
                packages = (
                    packages_needed(line["amount"], line["unit"], chosen)
                    if line.get("recipe")
                    else int(line["amount"] or 1)
                )
                self._apply(line, chosen, packages)
                return
            if not line.get("must_have"):
                await self._async_match_by_name(line, products, at, offer)  # by its name, then
                return
        if line.get("must_have"):
            priced = [p for p in products if p.price]
            if priced:
                self._apply(line, priced[0], int(line["amount"] or 1))
            elif self.prices:
                line["note"] = "Ingen vare fundet – tilføjes som fritekst"
            return

    async def _async_match_remembered(self, line: dict[str, Any], at: datetime | None) -> bool:
        """The product the family chose for this ingredient before, if it is still sold."""
        choice = self.store.choice_for(str(line.get("key") or ""), self.shop)
        if not choice:
            return False
        try:
            products = await self.client.async_get_products([int(choice["product_id"])], at)
        except (RemaError, TypeError, ValueError):
            return False
        product = next((p for p in products if p.price), None)
        if product is None:
            return False
        spec = line_spec(line)
        self._apply(line, product, line_packages(line, product, spec.piece_g))
        line["confidence"] = "high"
        line["note"] = "Jeres valg fra en tidligere madplan"
        line["remembered"] = True
        return True

    async def _async_match_linked(self, line: dict[str, Any], at: datetime | None) -> bool:
        """The product the shared table says the line is (links.py), when it is sold
        and meets the family's rules; the family's organic rule picks among them."""
        ids = linked_ids(self.shop, str(line.get("name") or ""))
        if not ids:
            return False
        try:
            products = await self.client.async_get_products(list(ids), at)
        except RemaError:
            return False
        requirement = self._requirement(line)
        rejected = self.store.rejected_products(str(line.get("key") or ""), self.shop)
        name = str(line.get("name") or "")
        candidates = [
            p
            for p in products
            if p.id in ids
            and p.price
            and p.id not in rejected
            and (requirement is None or requirement[0](p))
            and not variety_conflict(name, p.name)
        ]
        if not candidates:
            return False
        chosen, _, _ = self._choose(line, candidates, {})
        spec = line_spec(line)
        self._apply(line, chosen, line_packages(line, chosen, spec.piece_g))
        line["confidence"] = "high"
        line["linked"] = True
        return True

    def _requirement(
        self, line: dict[str, Any]
    ) -> tuple[Callable[[Product], bool], str, list[str]] | None:
        """The family's rule for this kind of item: (test, label, extra searches)."""
        settings = self.store.settings
        kind = line_kind(line)
        if kind == "egg" and settings["egg_min"] != "caged":
            level = _EGG_LEVEL[settings["egg_min"]]
            if level == 1:
                return (
                    lambda p: egg_level(p) >= 1,
                    "frilandsæg eller økologiske æg",
                    ["frilandsæg", "økologiske æg"],
                )
            return lambda p: egg_level(p) >= 2, "økologiske æg", ["økologiske æg", "øko æg"]
        if (kind == "milk" and settings["milk_organic"]) or (
            kind == "produce" and settings["produce_organic"]
        ):
            label = "økologisk mælk" if kind == "milk" else "økologisk frugt og grønt"
            search = line["search"]
            return lambda p: p.is_organic, label, [f"økologisk {search}", f"øko {search}"]
        return None

    async def _async_search_candidates(
        self,
        line: dict[str, Any],
        first: list[Product],
        require: Callable[[Product], bool] | None,
        at: datetime | None = None,
        offer: Offer | None = None,
        offered: list[Product] | None = None,
    ) -> tuple[list[Product], dict[int, float]]:
        """Try the search terms in turn until a product matches by name.

        With an avis offer, first look for the product the offer is for
        (``offered``: those products as REMA has them, then searching for the
        offer's own name); only then for anything that fits.
        """
        queries = search_queries(line)
        found: dict[str, list[Product]] = {queries[0]: first}
        if offer is not None and offered:
            candidates, penalty = self._candidates(
                line, offered, line["search"], require, offer, limit=len(offered)
            )
            if candidates:
                return candidates, penalty
        passes: list[tuple[Offer | None, list[str]]] = []
        if offer is not None:
            passes.append((offer, [*queries, offer_query(offer, line["name"])]))
        passes.append((None, queries))
        poor: tuple[list[Product], dict[int, float]] | None = None
        for this_offer, terms in passes:
            for query in terms:
                if query not in found:
                    try:
                        found[query] = await self._async_search(query, at)
                    except RemaError:
                        found[query] = []
                candidates, penalty = self._candidates(
                    # With an offer, the products must still be what the line asks
                    # for, also when found by the offer's own name.
                    line,
                    found[query],
                    query if this_offer is None else line["search"],
                    require,
                    this_offer,
                )
                if not candidates:
                    continue
                if this_offer is not None or min(penalty.get(p.id, 1.0) for p in candidates) < 5:
                    return candidates, penalty
                # Only something else by that name ("laks": smoked salmon);
                # the line's own name ("Laksefilet") may find the real thing.
                poor = poor or (candidates, penalty)
        return poor or ([], {})

    async def _async_match_by_name(
        self,
        line: dict[str, Any],
        first: list[Product],
        at: datetime | None = None,
        offer: Offer | None = None,
    ) -> None:
        """Choose the best product by name, the family's rules and price."""
        if not self.prices:
            # Another shop: no products online. An offer the line is about is bought as
            # the avis has it, at its price; everything else is free text without one.
            line["note"] = None
            if offer is not None and self._store_only(line, offer):
                line["note"] = f"Tilbud i {genitive(self.shop)} avis"
            return
        offered = await self._async_offered(offer, at)
        if (
            offer is not None
            and offered == []
            and not offer.unlinked
            and self._store_only(line, offer)
        ):
            return
        requirement = self._requirement(line)
        require = requirement[0] if requirement else None
        note: str | None = None
        candidates, penalty = await self._async_search_candidates(
            line, first, require, at, offer, offered
        )
        if not candidates and requirement:
            # None of the usual results meet the rule: search for it directly.
            for query in requirement[2]:
                try:
                    products = await self._async_search(query, at)
                except RemaError:
                    continue
                for words in (line["search"], line["name"]):
                    candidates, penalty = self._candidates(line, products, words, require)
                    if candidates:
                        break
                if candidates:
                    break
            if not candidates:
                candidates, penalty = await self._async_search_candidates(line, first, None, at)
                note = f"Ingen vare opfylder kravet om {requirement[1]} – billigste valgt"
        if not candidates:
            # Better a free-text line than a wrong product.
            line["note"] = (
                "Ingen sikker vare fundet – vælg en vare"
                if getattr(self.client, "cart", None) is not None
                else "Ingen sikker vare fundet – tilføjes som fritekst"
            )
            line["confidence"] = "low"
            # What it could be: products of the right kind, even if not by that name.
            spec = line_spec(line)
            possible = [
                p
                for p in first
                if p.price
                and allowed(spec, p.department, p.category, p.name, p.underline) is not False
                and not other_thing(spec, p.name)
            ]
            line["alternatives"] = [_alternative(p) for p in possible[:4]]
            return
        spec = line_spec(line)
        chosen, fit, candidates = self._choose(line, candidates, penalty)
        self._apply(line, chosen, line_packages(line, chosen, spec.piece_g))
        if note:
            line["note"] = note
        # How sure the choice is, and what else it could have been.
        strong = False
        for query in (line["search"], line["name"]):
            words = [w for w in _tokens(query) if len(w) > 1 and w not in _NEUTRAL_WORDS]
            head = head_word(query)
            found, _ = name_fit(words, chosen.name) if words else (0, 1.0)
            if bool(words) and (
                found == len(words)
                or bool(head and head in _tokens(chosen.name))
                or _called(spec, chosen.name)
            ):
                strong = True
        known_kind = allowed(
            spec, chosen.department, chosen.category, chosen.name, chosen.underline
        )
        fit_penalty = penalty.get(chosen.id, 1.0)
        if "vej selv" in (chosen.underline or "").lower().replace('"', ""):
            fit_penalty -= 5.0  # the only way the shop sells it, then; not a doubt
        if fit_penalty >= 5 or note:
            line["confidence"] = "low"
        elif (
            not strong
            or (known_kind is None and spec.entry is None)
            or fit_penalty >= 2
            or variety_missing(line.get("name") or "", chosen.name)
            or bool(line.get("guessed"))
        ):
            line["confidence"] = "medium"
        else:
            line["confidence"] = "high"
        others = sorted((p for p in candidates if p.id != chosen.id), key=fit)[:4]
        if line["confidence"] != "high" or (others[:1] and penalty.get(others[0].id, 1.0) < 1.5):
            line["alternatives"] = [_alternative(p) for p in others]

    def _choose(
        self, line: dict[str, Any], candidates: list[Product], penalty: dict[int, float]
    ) -> tuple[Product, Callable[[Product], tuple[float, bool, float]], list[Product]]:
        """The best of the products that fit a line, by price for what it needs and
        the family's organic rule; how each one fits, to order the others; and the
        products still in the running (sizes that can be compared)."""
        spec = line_spec(line)
        need = to_base(line["amount"], line.get("unit")) if line.get("amount") else None
        size_penalty: dict[int, float] = {}
        if need and need[0] in ("g", "ml"):
            # 3 kg potatoes: only products whose size can be counted in kg,
            # not one sweet potato sold per piece.
            comparable = [
                p for p in candidates if (size := package_size(p.underline)) and size[0] == need[0]
            ]
            candidates = comparable or candidates
        elif need is None or need[0] == "pack" or not spec.piece_g:
            # "2 dåser kokosmælk": the usual size on the shelf, not a mini can
            # because it is the cheapest package.
            sizes = sorted(size for p in candidates if (size := package_size(p.underline)))
            if len(sizes) > 1 and len({size[0] for size in sizes}) == 1:
                usual = sizes[len(sizes) // 2][1]
                for p in candidates:
                    size = package_size(p.underline)
                    if size and size[1] < usual * 0.6:
                        size_penalty[p.id] = 5.0

        def package_cost(product: Product) -> float:
            return line_packages(line, product, spec.piece_g) * (product.price or 0)

        cost = package_cost

        def fit(product: Product) -> tuple[float, bool, float]:
            # Same cost: an offer beats the normal price, and more beats less.
            size = package_size(product.underline)
            return (
                cost(product) * (penalty.get(product.id, 1.0) + size_penalty.get(product.id, 0)),
                not product.is_advertised,
                -(size[1] if size else 0),
            )

        settings = self.store.settings
        if line.get("prefer") == "relevance":
            # Typed by a person ("letmælk"): only products named close to it,
            # then the lowest price per litre/kilo, so 1 L beats a 250 ml carton.
            best_fit = min(penalty.get(p.id, 1.0) for p in candidates)
            candidates = [p for p in candidates if penalty.get(p.id, 1.0) <= best_fit + 0.5]
            unit = next((p.compare_unit for p in candidates if p.compare_unit_price), None)

            def unit_cost(product: Product) -> float:
                if unit is None:
                    return product.price or 0
                if product.compare_unit == unit and product.compare_unit_price:
                    return product.compare_unit_price
                return math.inf  # cannot be compared per litre/kilo

            cost = unit_cost
            # min() keeps REMA's own order on ties.
            cheapest = min(candidates, key=lambda p: (cost(p), not p.is_advertised))
        else:
            cheapest = min(candidates, key=fit)
        # An organic alternative must be the same kind of product, not just organic.
        organic = [
            p
            for p in candidates
            if p.is_organic and penalty.get(p.id, 1.0) <= penalty.get(cheapest.id, 1.0) + 0.5
        ]
        best_organic = min(organic, key=fit) if organic else None
        chosen = cheapest
        if settings["organic"] == "only":
            if best_organic:
                chosen = best_organic
            else:
                line["note"] = "Ingen økologisk variant fundet"
        elif settings["organic"] == "prefer" and best_organic:
            limit = cost(cheapest) * (1 + settings["organic_max_extra_pct"] / 100)
            if cost(best_organic) <= limit + 0.001:
                chosen = best_organic
        return chosen, fit, candidates

    async def _async_offered(
        self, offer: Offer | None, at: datetime | None
    ) -> list[Product] | None:
        """The very products an offer is for, as REMA has them (None: unknown).

        An empty list means REMA's webshop has none of them: a *partivare*,
        sold only in the shops.
        """
        if offer is None or not offer.product_ids:
            return None
        try:
            return await self.client.async_get_products(list(offer.product_ids), at)
        except RemaError:
            return None

    @staticmethod
    def _store_only(line: dict[str, Any], offer: Offer) -> bool:
        """Put an offer REMA's webshop doesn't have on the list as the avis has it.

        Tjek's name for it ("REMA 1000 laksefilet 600g") at the avis's price.
        Before the offer starts, its product is often not in REMA yet: it is
        looked up again when the list is sent (from 02:00 on the shopping day
        it is there, if REMA sells it online). If REMA still doesn't have it,
        it goes on the list as free text, like the webshop does with a
        *partivare*. Only when it is what the line asks for (no meatballs for
        kebab when the AI picked the wrong offer).
        """
        label = (
            offer.product_names[0]
            if len(offer.product_names) == 1
            else f"{offer_query(offer, line['name'])} (tilbud)"
        )
        fits = False
        for text in (line["search"], line["name"]):
            words = [w for w in _tokens(text) if len(w) > 1 and w not in _NEUTRAL_WORDS]
            if words:
                matched, cost = name_fit(words, f"{label} {offer.heading}")
                fits = fits or (matched == len(words) and cost < 5)
        if not fits:
            return False
        packages = avis_packages(
            line.get("amount"), line.get("unit"), offer, line_spec(line).piece_g
        )
        start = parse_time(offer.valid_from)
        started = (
            start is None or prices_from(start.astimezone(DANISH_TIME).date()) <= dt_util.utcnow()
        )
        line["avis_item"] = {
            "name": label,
            "underline": offer.quantity,
            "price": offer.price,
            "is_advertised": True,
            "product_ids": list(offer.product_ids or ()),
        }
        line["packages"] = packages
        line["cost"] = round(packages * offer.price, 2) if offer.price else None
        line["price_source"] = "avis"
        line["note"] = (
            "Partivare – kun i butikken, tilføjes som fritekst"
            if started
            else "Avisvare – REMA har den først, når tilbuddet starter; vælges, når listen sendes"
        )
        return True

    def _candidates(
        self,
        line: dict[str, Any],
        products: list[Product],
        query: str,
        require: Callable[[Product], bool] | None = None,
        offer: Offer | None = None,
        limit: int = 12,
    ) -> tuple[list[Product], dict[int, float]]:
        """Products that really are what the line asks for, and a price penalty
        for each (extra words in the name make a product a worse fit).

        With an avis offer, only the products that offer is for.
        """
        priced = [p for p in products[:limit] if p.price and (require is None or require(p))]
        asked = f"{line.get('name') or ''} {line.get('search') or ''}"
        # The shop's own category first: a product of another kind than the line
        # asks for is out (cup noodles for noodles, a can of pepper strips for a
        # fresh pepper, ground chili for a fresh one), and so is a product the
        # family said no to for this ingredient, or one the catalogue knows is
        # another thing ("skalotteløg" for løg).
        spec = line_spec(line)
        rejected = self.store.rejected_products(spec.key, self.shop)
        trusted: set[int] = set()
        kept: list[Product] = []
        for p in priced:
            if p.id in rejected or other_thing(spec, p.name):
                continue
            if variety_conflict(line.get("name") or "", p.name):
                continue  # yellow pepper for "rød peberfrugt", iceberg for romaine
            fits_kind = allowed(spec, p.department, p.category, p.name, p.underline)
            if fits_kind is False:
                continue
            if fits_kind and spec.entry is not None:
                trusted.add(p.id)
            kept.append(p)
        priced = kept
        # Words the line itself uses are no mark against a product ("light" when
        # the line says light), nor are the words the catalogue allows for the thing.
        neutral = (*(spec.entry.ok_words if spec.entry is not None else ()), *spec.asked)
        priced = [p for p in priced if herb_form_matches(asked, p.name, p.department, p.category)]
        if canned_tomatoes(asked):
            priced = [
                p
                for p in priced
                if canned_tomato_product(p.name, p.underline, p.department, p.category)
            ]
        asked_words = set(_tokens(asked))
        if "svinemørbrad" in asked_words:
            priced = [
                p
                for p in priced
                if name_fit(["mørbrad"], p.name)[0]
                and (
                    "svinemørbrad" in _tokens(p.name)
                    or set(_tokens(f"{p.name} {p.category or ''}")) & {"gris", "svin", "svinekød"}
                )
            ]
        if {"oksekød", "gryderet"} <= asked_words and query.lower() == "gullasch":
            priced = [
                p
                for p in priced
                if "oksekød" in _tokens(p.category or "")
                and (p.department or "").lower() in ("kød", "kød og fisk", "frost")
                and not set(_tokens(p.name)) & {"hakket", "fars", "hakkebøffer"}
            ]
        if "karrypulver" in asked_words:
            priced = [
                p
                for p in priced
                if "karrypulver" in _tokens(p.name)
                or (
                    "karry" in _tokens(p.name)
                    and (
                        set(_tokens(p.category or "")) & {"krydderi", "krydderier"}
                        or set(_tokens(p.name)) <= {"karry", "mild", "stærk", "madras", "økologisk"}
                    )
                )
            ]
        if line.get("stock_cubes"):
            priced = [
                p
                for p in priced
                if not (
                    ((size := package_size(p.underline)) and size[0] == "ml")
                    or set(_tokens(f"{p.name} {p.underline or ''}"))
                    & {"pulver", "fond", "flydende", "drikkeklar"}
                )
            ]
        if not priced:
            return [], {}
        words = [w for w in _tokens(query) if len(w) > 1 and w not in _NEUTRAL_WORDS]
        if not words:
            return [], {}
        fits = {p.id: name_fit(words, p.name, neutral) for p in priced}
        # Called by another of the catalogue's names for the thing ("GRANA PADANO"
        # for parmesan, "RØDSPÆTTEFILETER" for fiskefilet): as good as the word itself.
        called = {p.id for p in priced if _called(spec, p.name)}
        penalty = {
            p.id: fits[p.id][1] + kind_penalty(line, p, words, p.id in trusted, spec)
            for p in priced
        }
        if wanted_pct := _percents(asked):
            # "Creme fraiche 18%": the fat content asked for, when the shelf states one.
            for p in priced:
                has = _percents(f"{p.name} {p.underline or ''}")
                if has and not has & wanted_pct:
                    penalty[p.id] += 5.0

        head = head_word(query)
        if head:
            # The thing itself beats a product that only has the word as a qualifier
            # ("DADDELBAR, PEANUTS" for peanuts, "BOLLER I KARRY" for karry).
            for p in priced:
                if qualifier_only(p.name, head):
                    penalty[p.id] += 5.0
        if offer is not None:
            # The AI built the dish on this avis offer: only the product it is
            # for, and only if that is also what the line asks for - the thing
            # itself, not just "hakket" (an offer on minced beef, pork and veal or
            # chicken is beef for "hakket oksekød").
            fitting = [
                p
                for p in priced
                if fits[p.id][0]
                and (fits[p.id][0] == len(words) or not head or name_fit([head], p.name)[0])
                and self._named_like(line, p, words, spec)
                and offer_covers(offer, p.id, p.name, p.underline, p.is_organic)
            ]
            return (self._free_from(fitting), penalty) if fitting else ([], penalty)

        best = max(fit[0] for fit in fits.values())
        relevant = [p for p in priced if (best and fits[p.id][0] == best) or p.id in called]
        if best < len(words) and head:
            # Only some of the words fit: the one the thing is (the last before
            # "med", "uden" ...) must be among them - "grønne bønner" is never
            # "grønne druer", but "laksefilet med skind" may be "LAKSEFILET".
            relevant = [p for p in relevant if p.id in called or name_fit([head], p.name)[0]]
        if not relevant or (line.get("prefer") == "relevance" and best < len(words)):
            # Nothing is called what we searched for. Typed by a person: every
            # word must fit, or "kage til Anna" could become anything with "ana"
            # in it. Free text is the safe answer.
            return [], penalty
        # "Laksefilet" searched as "laks": products that are what the line is
        # called (or what the catalogue calls it) beat the rest (salmon fillet,
        # not salmon in pastry; vanilla ice cream, not the cheapest ice).
        named = [
            w for w in _tokens(line.get("name") or "") if len(w) > 1 and w not in _NEUTRAL_WORDS
        ]
        full = {
            p.id
            for p in relevant
            if named and named != words and name_fit(named, p.name)[0] == len(named)
        }
        if not full:
            full = called or {p.id for p in relevant if fits[p.id][0] == len(words)}
        if full and len(full) < len(relevant):
            for p in relevant:
                if p.id not in full:
                    penalty[p.id] = penalty.get(p.id, 1.0) + 5.0
        # Stay in the department of the best-fitting product (fish, not cold
        # cuts), unless the catalogue vouches for the product's kind (the
        # freezer's chicken legs are chicken legs).
        anchor = min(relevant, key=lambda p: penalty.get(p.id, 1.0)).department
        relevant = [p for p in relevant if p.department == anchor or p.id in trusted] or relevant
        return self._free_from(relevant), penalty

    @staticmethod
    def _named_like(line: dict[str, Any], product: Product, words: list[str], spec: Spec) -> bool:
        """An offer's product must also be what the line is called: "Mini-baguettes"
        searched as "brød" is not the Schulstad offer's sødmælksbrød."""
        named = [
            w
            for w in _tokens(ingredient_name(str(line.get("name") or "")))
            if len(w) > 2 and w not in _NEUTRAL_WORDS and w not in _DESCRIBING
        ]
        if not named or set(named) <= set(words):
            return True
        return bool(name_fit(named, product.name)[0]) or _called(spec, product.name)

    def _free_from(self, relevant: list[Product]) -> list[Product]:
        """Prefer gluten-free / lactose-free products when the family needs them."""
        for allergy in self.store.settings["allergies"]:
            marker = FREE_FROM.get(allergy)
            if marker:
                free = [p for p in relevant if marker in f"{p.name} {p.underline or ''}".upper()]
                if free:
                    relevant = free
        return relevant

    async def _async_match_on_day(
        self, line: dict[str, Any], at: datetime | None, offer: Offer | None
    ) -> None:
        """Match a line on the day it is bought: a thursday offer's line on thursday."""
        day = line.get("buy_from")
        await self._async_match(line, noon(date.fromisoformat(day)) if day else at, offer)
        if day and offer is not None and not self._bought_on_offer(line, offer):
            # The dish was built on a thursday offer, but the product chosen isn't it
            # (the family's organic eggs, not the avis's skrabeæg): bought and
            # priced on the shopping day like the rest.
            line["buy_from"] = None
            await self._async_match(line, at, offer)
        self._avis_price(line, offer)

    async def async_rematch_all(self, plan_id: str) -> dict[str, Any]:
        """Find every unsent item of a plan again, with the matching as it is now.

        The dishes stay. What the family chose, kept, left out or moved to another
        shop stays too; the rest is read again from its words (one line per
        thing), matched, priced and, when still not sure, looked for in Bilka.
        """
        async with self._send_lock:
            plan = self.store.get_plan(plan_id)
            if plan is None:
                raise _invalid("plan_not_found")
            fixed = ("sent", "must_have", "added", "product_id", "buy_at", "reviewed", "skipped")
            todo = [
                line
                for line in plan["shopping"]
                if not any(line.get(key) for key in fixed) and not line.get("chain_only")
            ]
            for line in todo:
                line.pop("key", None)  # read again by today's catalogue
                line["search"] = ingredient_name(str(line.get("search") or line["name"]))
                apply_spec(line)
            kept = merge_lines(todo, plan.get("days") or [])
            gone = {id(line) for line in todo} - {id(line) for line in kept}
            plan["shopping"] = [line for line in plan["shopping"] if id(line) not in gone]
            offers = await self._async_plan_offers(plan, kept)
            at = self.price_time(date.fromisoformat(plan["start_date"]))
            semaphore = asyncio.Semaphore(SEARCH_CONCURRENCY)

            async def match(line: dict[str, Any]) -> None:
                async with semaphore:
                    offer = offers.get(str(line.get("offer_name") or ""))
                    await self._async_match_on_day(line, at, offer)

            await asyncio.gather(*(match(line) for line in kept))
            await self._async_ai_choices(plan)
            await self._async_next_shops(plan)
            plan["total"] = plan_total(plan["shopping"])
            plan["over_budget"] = bool(plan.get("budget")) and plan["total"] > plan["budget"]
            plan["rematched_at"] = dt_util.utcnow().isoformat()
            await self.store.async_save()
            self._notify()
            return plan

    async def _async_plan_offers(
        self, plan: dict[str, Any], lines: list[dict[str, Any]]
    ) -> dict[str, Offer]:
        """The avis offers the lines are built on, by heading, with their products."""
        catalog_id = (plan.get("catalog") or {}).get("id")
        wanted = {line["offer_name"] for line in lines if line.get("offer_name")}
        if not catalog_id or not wanted:
            return {}
        try:
            offers = await self.client.async_get_offers(catalog_id)
            found = await self.client.async_get_offer_products(
                [o for o in offers if o.heading in wanted]
            )
        except RemaError as err:
            _LOGGER.debug("The plan's offers could not be read: %s", err)
            return {}
        return {offer.heading: offer for offer in found}

    @staticmethod
    def _bought_on_offer(line: dict[str, Any], offer: Offer) -> bool:
        """Is what the line buys the offer's product (or the avis's own item)?"""
        if line.get("avis_item"):
            return True
        product = line.get("product")
        if not product:
            return True  # the offer itself, as free text: its day still holds
        return offer_covers(
            offer,
            product.get("id"),
            product.get("name") or "",
            product.get("underline"),
            bool(product.get("is_organic")),
        )

    @staticmethod
    def _avis_price(line: dict[str, Any], offer: Offer | None) -> None:
        """Use the avis's price for a line built on an offer REMA doesn't show yet.

        REMA only has an offer's price once it takes effect (02:00 on its first
        day), so a plan made before that would otherwise get the normal price.
        """
        product = line.get("product")
        if not offer or not offer.price or not product:
            return
        if product.get("price") and product["price"] <= offer.price:
            return  # REMA already has the offer, or its own price is lower anyway
        if not offer_covers(
            offer,
            product.get("id"),
            product.get("name") or "",
            product.get("underline"),
            bool(product.get("is_organic")),
        ):
            return  # another product than the one on offer
        product["normal_price"] = product.get("price")
        product["price"] = offer.price
        product["is_advertised"] = True
        line["cost"] = round(line["packages"] * offer.price, 2)
        line["price_source"] = "avis"

    @staticmethod
    def _apply(line: dict[str, Any], product: Product, packages: int) -> None:
        line["packages"] = packages
        line["cost"] = round(packages * (product.price or 0), 2)
        line["product"] = {
            "id": product.id,
            "name": product.name,
            "underline": product.underline,
            "price": product.price,
            "normal_price": product.normal_price,
            "is_advertised": product.is_advertised,
            "is_campaign": product.is_campaign,
            "is_organic": product.is_organic,
            "image": product.image,
            "department": product.department,
            "category": product.category,
            "labels": product.labels,
        }
