"""Select an installed shop and optionally carry a plan across accounts."""

from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
import copy
from typing import Any
import uuid

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .coordinator import RemaConfigEntry
from .matching import plan_total
from .storage import MAX_PLANS

SIGNAL = f"{DOMAIN}_selected_store_changed"
_KEY = f"{DOMAIN}_store_selection"
_FAMILY = (
    "household",
    "portion_percent",
    "allergies",
    "allergies_other",
    "avoid",
    "avoid_other",
    "wishes",
    "rules",
    "pantry",
)


class StoreSelection:
    """Household-wide default for the panel/cards, independent of credentials."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.store: Store[dict[str, Any]] = Store(hass, 1, f"{DOMAIN}.store_selection")
        self.data: dict[str, Any] = {}
        self.lock = asyncio.Lock()

    async def async_load(self) -> None:
        self.data = await self.store.async_load() or {}

    @property
    def preference(self) -> str:
        value = self.data.get("plan_action", "ask")
        return str(value) if value in ("copy", "new") else "ask"


def selection(hass: HomeAssistant) -> StoreSelection:
    """One selector shared by all configured shop accounts."""
    if _KEY not in hass.data:
        hass.data[_KEY] = StoreSelection(hass)
    result: StoreSelection = hass.data[_KEY]
    return result


def selected_entry(hass: HomeAssistant, entries: list[RemaConfigEntry]) -> RemaConfigEntry:
    """Fall back safely when the selected account was removed or is not loaded."""
    active = selection(hass).data.get("entry_id")
    return next((entry for entry in entries if entry.entry_id == active), entries[0])


async def _copy_plan(
    source: RemaConfigEntry, target: RemaConfigEntry, plan_id: str | None
) -> dict[str, Any] | None:
    old = (
        source.runtime_data.store.get_plan(plan_id)
        if plan_id
        else source.runtime_data.store.latest_plan
    )
    if old is None:
        if plan_id:
            raise ValueError("Madplanen findes ikke længere. Genindlæs siden og prøv igen.")
        return None
    plan = copy.deepcopy(old)
    # Keep plan/line identities across accounts. Existing receipts remain valid,
    # and returning to a shop must not forget items already sent there.
    existing = target.runtime_data.store.get_plan(plan["id"])
    sent = {line["id"]: line for line in (existing or {}).get("shopping", []) if line.get("sent")}
    for line in plan["shopping"]:
        was_sent = line.get("sent") or sent.get(line["id"], {}).get("sent")
        for key in (
            "product",
            "product_id",
            "offer",
            "offer_name",
            "avis_item",
            "price_source",
            "buy_at",
            "buy_from",
            "bilka_price_store",
            "on_list",
            "sent",
            "sent_amount",
            "recipe_product",
            "prefer",
        ):
            line.pop(key, None)
        if not line.get("have"):
            line.pop("skipped", None)
        if was_sent:
            line["sent"] = was_sent
        line["must_have"] = False  # resolve by ingredient/amount, never by another shop's SKU
        line["recipe"] = True
        line["offer"] = None
    for key in (
        "last_sent",
        "sent_at",
        "late_sent_at",
        "missing_products",
        "bilka_rematch",
        "refreshed_at",
    ):
        plan.pop(key, None)
    plan.update(status="draft", catalog=None, over_budget=False)
    # A saved recipe's identifier is account-local. Carry referenced recipes only;
    # never overwrite an independently edited recipe in the destination account.
    copied_recipes = []
    mapping: dict[str, str] = {}
    for day in plan.get("days", []):
        rid = day.get("recipe_id")
        if not rid:
            continue
        if rid not in mapping:
            recipe = next((r for r in source.runtime_data.store.recipes if r["id"] == rid), None)
            if recipe:
                recipe = copy.deepcopy(recipe)
                for ingredient in recipe.get("ingredients", []):
                    ingredient.pop("product", None)
                equivalent = next(
                    (
                        r
                        for r in target.runtime_data.store.recipes
                        if {k: v for k, v in r.items() if k != "id"}
                        == {k: v for k, v in recipe.items() if k != "id"}
                    ),
                    None,
                )
                recipe["id"] = equivalent["id"] if equivalent else uuid.uuid4().hex[:12]
                mapping[rid] = recipe["id"]
                if not equivalent:
                    copied_recipes.append(recipe)
        day["recipe_id"] = mapping.get(rid)
    await target.runtime_data.planner._async_price_lines(plan["shopping"], [])
    plan["total"] = plan_total(plan["shopping"])
    plan["over_budget"] = bool(plan.get("budget")) and plan["total"] > plan["budget"]
    return {"plan": plan, "recipes": copied_recipes}


async def async_switch(
    hass: HomeAssistant,
    source: RemaConfigEntry,
    target: RemaConfigEntry,
    action: str,
    remember: bool,
    plan_id: str | None,
) -> None:
    """Prepare completely before selecting the new shop. Never writes to a cart."""
    manager = selection(hass)
    async with manager.lock, AsyncExitStack() as stack:
        if source.entry_id == target.entry_id:
            return
        for entry in sorted((source, target), key=lambda entry: entry.entry_id):
            await stack.enter_async_context(entry.runtime_data.planner._send_lock)
            if entry.runtime_data.planner.generating:
                raise ValueError("Vent til madplanen er færdig, før du skifter butik.")
        store = target.runtime_data.store
        previous_settings = copy.deepcopy(store.settings)
        previous_plans, previous_freezer, previous_recipes = (
            store.plans[:],
            store.freezer_plans[:],
            store.recipes[:],
        )
        store.settings = {
            **store.settings,
            **{key: copy.deepcopy(source.runtime_data.store.settings[key]) for key in _FAMILY},
        }
        try:
            copied = await _copy_plan(source, target, plan_id) if action == "copy" else None
            if copied:
                plan = copied["plan"]
                plans = store.freezer_plans if plan.get("kind") == "freezer" else store.plans
                plans[:] = [p for p in plans if p["id"] != plan["id"]]
                plans.insert(0, plan)
                del plans[MAX_PLANS:]
                store.recipes.extend(copied["recipes"])
            await store.async_save()
        except BaseException:
            store.settings = previous_settings
            store.plans, store.freezer_plans, store.recipes = (
                previous_plans,
                previous_freezer,
                previous_recipes,
            )
            raise
        data = {
            **manager.data,
            "entry_id": target.entry_id,
            "plan_action": action if remember else "ask",
            "start_new": not copied,
            "previous_plan_id": (store.latest_plan or {}).get("id"),
            "copied_plan_id": copied["plan"]["id"] if copied else None,
        }
        await manager.store.async_save(data)
        manager.data = data
        target.runtime_data.planner._notify()
        async_dispatcher_send(hass, SIGNAL)
