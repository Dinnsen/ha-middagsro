"""The family's recipe collection: liked, disliked and favourite dishes, and recipes from links.

A recipe in the collection:
    id, name, type ("normal"/"vegetar"), servings, active_minutes, total_minutes,
    ingredients [{name, amount}], steps [{text, minutes}], tip,
    rating ("like" / "dislike" / None), favorite (bool), source ("plan"/"link"/"manual"),
    created, updated, times_planned, last_planned

Links are only read when a recipe is added; the link itself is not kept.
"""

from __future__ import annotations

from datetime import datetime
import html
import ipaddress
import json
import logging
import re
import socket
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse
import uuid

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .dishes import matches_any, same_dish

if TYPE_CHECKING:
    from .mealplan import MealPlanner
    from .storage import RemaPlanStore

_LOGGER = logging.getLogger(__name__)

MAX_RECIPES = 500
PROMPT_RECIPES = 40
ACTIONS = ("like", "dislike", "favorite")
SORTS = ("name", "newest", "most_used", "quickest")
PAGE_LIMIT = 3_000_000
TIMEOUT = aiohttp.ClientTimeout(total=20)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Home Assistant; Middagsro) AppleWebKit/537.36 Chrome/130 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "da,en;q=0.8",
}
UNITS = (
    "kg|g|gram|mg|l|liter|dl|cl|ml|spsk|tsk|tskf|knsp|knivspids|stk|fed|dåse|dåser|bundt|"
    "pk|pakke|pakker|bakke|skive|skiver|håndfuld|kop|kopper|cup|cups|tbsp|tsp|oz|lb|stilk|stilke|"
    "blade|blad|nip|drys|glas|ds"
)
_AMOUNT = re.compile(
    rf"^\s*((?:ca\.?\s*)?[\d½¼¾⅓⅔⅛.,/]+(?:\s+[½¼¾⅓⅔⅛]|\s+\d+/\d+)?(?:\s*[-–]\s*[\d½¼¾.,/]+)?"
    rf"(?:\s*(?:{UNITS})\b\.?)?)\s+(.+)$",
    re.IGNORECASE,
)


def _invalid(key: str, **placeholders: str) -> ServiceValidationError:
    return ServiceValidationError(
        translation_domain=DOMAIN, translation_key=key, translation_placeholders=placeholders
    )


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _int(value: Any, high: int, default: int = 0) -> int:
    try:
        return max(0, min(high, int(float(value))))
    except (TypeError, ValueError):
        return default


def split_ingredient(text: str) -> dict[str, str]:
    """'2 dl fløde' -> {amount: '2 dl', name: 'fløde'}; 'salt' -> {amount: '', name: 'salt'}."""
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if match := _AMOUNT.match(text):
        return {"amount": match.group(1).strip()[:60], "name": match.group(2).strip()[:200]}
    return {"amount": "", "name": text[:200]}


def _product(value: Any) -> dict[str, Any] | None:
    """The REMA product a REMA recipe links an ingredient to."""
    if not isinstance(value, dict) or not isinstance(value.get("id"), int):
        return None
    return {
        "id": value["id"],
        "name": str(value.get("name") or "").strip()[:120],
        "underline": str(value.get("underline") or "").strip()[:120],
    }


def _ingredient(item: Any) -> dict[str, Any] | None:
    if isinstance(item, dict):
        name = str(item.get("name") or "").strip()[:200]
        amount = str(item.get("amount") or "").strip()[:60]
        if not name:
            return None
        out: dict[str, Any] = {"name": name, "amount": amount}
        if product := _product(item.get("product")):
            out["product"] = product
        if item.get("basic"):
            out["basic"] = True
        return out
    if isinstance(item, str) and item.strip():
        return split_ingredient(item)
    return None


def _step(item: Any) -> dict[str, Any] | None:
    if isinstance(item, dict):
        text = str(item.get("text") or "").strip()[:1000]
        return {"text": text, "minutes": _int(item.get("minutes"), 600)} if text else None
    if isinstance(item, str) and item.strip():
        return {"text": item.strip()[:1000], "minutes": 0}
    return None


def clean_recipe(raw: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    """A recipe from the panel, a plan or a page, in the collection's shape."""
    old = existing or {}
    name = str(raw.get("name") if raw.get("name") is not None else old.get("name") or "").strip()
    if not name:
        raise _invalid("recipe_name_required")

    def pick(key: str, default: Any) -> Any:
        return raw[key] if key in raw else old.get(key, default)

    rating = pick("rating", None)
    favorite = bool(pick("favorite", False))
    if rating not in ("like", "dislike"):
        rating = None
    if favorite:
        rating = "like"
    kind = str(pick("type", "normal") or "normal").lower()
    return {
        "id": old.get("id") or uuid.uuid4().hex[:10],
        "name": name[:300],
        "type": "vegetar" if kind == "vegetar" else "normal",
        "servings": _int(pick("servings", 4), 50, 4) or 4,
        "active_minutes": _int(pick("active_minutes", 0), 600),
        "total_minutes": _int(pick("total_minutes", 0), 1440),
        "ingredients": [i for i in (_ingredient(x) for x in pick("ingredients", []) or []) if i][
            :80
        ],
        "steps": [s for s in (_step(x) for x in pick("steps", []) or []) if s][:60],
        "tip": str(pick("tip", "") or "").strip()[:1000],
        "rating": rating,
        "favorite": favorite,
        "source": str(old.get("source") or raw.get("source") or "manual")[:20],
        **_rema_fields(raw, old),
        "created": old.get("created") or _now(),
        "updated": _now(),
        "times_planned": _int(old.get("times_planned"), 100000),
        "last_planned": old.get("last_planned"),
    }


def _rema_fields(raw: dict[str, Any], old: dict[str, Any]) -> dict[str, Any]:
    """Where a recipe from REMA 1000 came from, and its photo."""
    out: dict[str, Any] = {}
    slug = raw.get("rema_slug") or old.get("rema_slug")
    if isinstance(slug, str) and slug.strip():
        out["rema_slug"] = slug.strip()[:200]
    image = raw.get("image") if "image" in raw else old.get("image")
    if isinstance(image, str) and image.startswith("https://") and len(image) <= 500:
        out["image"] = image
    return out


def find_recipe(store: RemaPlanStore, recipe_id: str | None) -> dict[str, Any] | None:
    """A recipe by id."""
    if not recipe_id:
        return None
    return next((r for r in store.recipes if r["id"] == recipe_id), None)


def find_by_name(store: RemaPlanStore, name: str) -> dict[str, Any] | None:
    """A recipe by its name (case and spacing don't matter)."""
    key = " ".join(str(name or "").lower().split())
    return next((r for r in store.recipes if " ".join(r["name"].lower().split()) == key), None)


async def async_save_recipe(store: RemaPlanStore, raw: dict[str, Any]) -> dict[str, Any]:
    """Create or update a recipe."""
    existing = find_recipe(store, raw.get("id"))
    if raw.get("id") and existing is None:
        raise _invalid("recipe_not_found")
    if existing is None and raw.get("rema_slug"):
        # A REMA recipe saved again is the same recipe (its ratings stay).
        existing = next((r for r in store.recipes if r.get("rema_slug") == raw["rema_slug"]), None)
        if existing is not None:
            raw = {k: v for k, v in raw.items() if k not in ("rating", "favorite") or v}
    recipe = clean_recipe(raw, existing)
    if existing is not None:
        existing.clear()
        existing.update(recipe)
        recipe = existing
    else:
        if len(store.recipes) >= MAX_RECIPES:
            raise _invalid("too_many_recipes", limit=str(MAX_RECIPES))
        store.recipes.insert(0, recipe)
    await store.async_save()
    return recipe


async def async_delete_recipe(store: RemaPlanStore, recipe_id: str) -> None:
    """Delete a recipe (plans that used it keep their own copy)."""
    if find_recipe(store, recipe_id) is None:
        raise _invalid("recipe_not_found")
    store.recipes = [r for r in store.recipes if r["id"] != recipe_id]
    await store.async_save()


def apply_rating(recipe: dict[str, Any], action: str) -> None:
    """👍, 👎 or ❤️: pressing the same again takes it back; the other one replaces it."""
    if action == "like":
        if recipe.get("rating") == "like":
            recipe.update(rating=None, favorite=False)
        else:
            recipe["rating"] = "like"
    elif action == "dislike":
        if recipe.get("rating") == "dislike":
            recipe["rating"] = None
        else:
            recipe.update(rating="dislike", favorite=False)
    elif action == "favorite":
        if recipe.get("favorite"):
            recipe["favorite"] = False
        else:
            recipe.update(favorite=True, rating="like")
    else:
        raise _invalid("recipe_bad_action")
    recipe["updated"] = _now()


async def async_rate(store: RemaPlanStore, recipe_id: str, action: str) -> dict[str, Any]:
    """Rate a recipe in the collection."""
    recipe = find_recipe(store, recipe_id)
    if recipe is None:
        raise _invalid("recipe_not_found")
    apply_rating(recipe, action)
    await store.async_save()
    return recipe


def recipe_from_day(day: dict[str, Any]) -> dict[str, Any]:
    """A plan's dinner as a recipe for the collection."""
    return {
        "name": day.get("dish") or "",
        "type": day.get("type") if day.get("type") == "vegetar" else "normal",
        "servings": day.get("servings") or 4,
        "active_minutes": day.get("active_minutes") or 0,
        "total_minutes": day.get("total_minutes") or 0,
        "ingredients": day.get("ingredients") or [],
        "steps": day.get("steps") or [],
        "tip": day.get("tip") or "",
        "source": "plan",
    }


def day_rating(store: RemaPlanStore, day: dict[str, Any]) -> dict[str, Any]:
    """The rating the collection has for a plan's dinner (for the panel's buttons)."""
    recipe = find_recipe(store, day.get("recipe_id")) or find_by_name(store, day.get("dish", ""))
    if recipe is None:
        return {"recipe_id": None, "rating": None, "favorite": False}
    return {"recipe_id": recipe["id"], "rating": recipe["rating"], "favorite": recipe["favorite"]}


async def async_rate_day(
    planner: MealPlanner, plan_id: str, day_date: str, action: str
) -> dict[str, Any]:
    """Rate a plan's dinner: it goes in the collection (with its recipe) if it isn't there."""
    from .planedit import cooked_day  # noqa: PLC0415

    store = planner.store
    plan = store.get_plan(plan_id)
    picked = next((d for d in plan["days"] if d["date"] == day_date), None) if plan else None
    if plan is None or picked is None:
        raise _invalid("day_not_found")
    day = cooked_day(plan, picked)
    if not day.get("dish") or day.get("type") == "tom":
        raise _invalid("recipe_name_required")
    recipe = find_recipe(store, day.get("recipe_id")) or find_by_name(store, day["dish"])
    if recipe is None:
        if action not in ACTIONS:
            raise _invalid("recipe_bad_action")
        recipe = clean_recipe(recipe_from_day(day))
        recipe["times_planned"] = 1
        recipe["last_planned"] = day["date"]
        store.recipes.insert(0, recipe)
        del store.recipes[MAX_RECIPES:]
    elif not recipe["ingredients"] and day.get("ingredients"):
        recipe.update(clean_recipe({**recipe_from_day(day), "id": recipe["id"]}, recipe))
    apply_rating(recipe, action)
    day["recipe_id"] = recipe["id"]
    await store.async_save()
    planner._notify()
    return recipe


def mark_planned(store: RemaPlanStore, plan: dict[str, Any]) -> None:
    """Count the collection's recipes a new plan uses."""
    for day in plan.get("days") or []:
        if recipe := find_recipe(store, day.get("recipe_id")):
            recipe["times_planned"] = recipe.get("times_planned", 0) + 1
            recipe["last_planned"] = day["date"]


def prompt_recipes(store: RemaPlanStore, avoid: list[str] | None = None) -> list[dict[str, Any]]:
    """Favourites first, then the dishes the family likes, for the AI (with ingredients).

    Not the ones the family had in the last weeks (``avoid``): they would be repeats.
    """
    chosen = [
        r
        for r in sorted(
            (r for r in store.recipes if r["rating"] == "like"),
            key=lambda r: (not r["favorite"], r.get("last_planned") or ""),
        )
        if matches_any(r["name"], avoid or []) is None
    ]
    return chosen[:PROMPT_RECIPES]


def favorite_recipe(store: RemaPlanStore, text: str) -> dict[str, Any] | None:
    """The collection's recipe for a favourite dish, if the family has one.

    The one they gave a ❤️ first, then one they like; never one they dislike.
    """
    found = [
        r
        for r in store.recipes
        if r.get("rating") != "dislike"
        and (r["ingredients"] or r["steps"])
        and same_dish(r["name"], text, strict=True)
    ]
    if not found:
        return None
    return min(found, key=lambda r: (not r.get("favorite"), r.get("rating") != "like"))


def disliked_names(store: RemaPlanStore) -> list[str]:
    """The dishes the family has given a thumbs down."""
    return [r["name"] for r in store.recipes if r["rating"] == "dislike"][:100]


def recipe_to_day(recipe: dict[str, Any], day: dict[str, Any]) -> None:
    """Put a recipe from the collection on a plan's day (its ingredients and steps)."""
    day["ingredients"] = [dict(i) for i in recipe["ingredients"]]
    day["steps"] = [dict(s) for s in recipe["steps"]]
    day["tip"] = recipe.get("tip") or ""
    day["nutrition"] = None
    day["active_minutes"] = recipe.get("active_minutes") or day.get("active_minutes", 0)
    day["total_minutes"] = recipe.get("total_minutes") or day.get("total_minutes", 0)


def ingredient_texts(recipe: dict[str, Any]) -> list[str]:
    """'600 g laksefilet', for prompts; with the REMA product a REMA recipe names."""
    out = []
    for item in recipe["ingredients"]:
        text = " ".join(p for p in (item["amount"], item["name"]) if p)
        if product := item.get("product"):
            text += (
                f" (REMA-vare: {' '.join(p for p in (product['name'], product['underline']) if p)})"
            )
        if item.get("basic"):
            text += " (basisvare)"
        out.append(text)
    return out


# ------------------------------------------------------------------ links


def _iso_minutes(value: Any) -> int:
    match = re.fullmatch(
        r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:\d+S)?", str(value or "").strip().upper()
    )
    if not match:
        return 0
    days, hours, minutes = (int(g or 0) for g in match.groups())
    return days * 1440 + hours * 60 + minutes


def _text(value: Any) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", str(value or ""))).strip()


def _walk(node: Any) -> list[dict[str, Any]]:
    """All objects in JSON-LD (lists, @graph)."""
    if isinstance(node, list):
        return [found for item in node for found in _walk(item)]
    if isinstance(node, dict):
        return [node, *_walk(node.get("@graph"))]
    return []


def _is_recipe(node: dict[str, Any]) -> bool:
    kind = node.get("@type")
    kinds = kind if isinstance(kind, list) else [kind]
    return "Recipe" in kinds


def _steps(value: Any) -> list[str]:
    if isinstance(value, str):
        return [s for s in (_text(p) for p in re.split(r"\n+", value)) if s]
    out: list[str] = []
    for item in value or []:
        if isinstance(item, str):
            out.append(_text(item))
        elif isinstance(item, dict):
            if item.get("itemListElement"):
                out += _steps(item["itemListElement"])
            elif item.get("text") or item.get("name"):
                out.append(_text(item.get("text") or item.get("name")))
    return [s for s in out if s]


def _servings(value: Any) -> int:
    for item in value if isinstance(value, list) else [value]:
        if match := re.search(r"\d+", str(item or "")):
            return _int(match.group(), 50, 4) or 4
    return 4


def parse_recipe_page(page: str) -> dict[str, Any] | None:
    """The recipe in a page's schema.org data (most recipe sites have it)."""
    for block in re.findall(
        r"<script[^>]+application/ld\+json[^>]*>(.*?)</script>", page, re.DOTALL | re.IGNORECASE
    ):
        try:
            data = json.loads(block.strip())
        except ValueError:
            continue
        for node in _walk(data):
            if not _is_recipe(node) or not node.get("name"):
                continue
            category = " ".join(
                str(c) for c in (node.get("recipeCategory"), node.get("suitableForDiet")) if c
            ).lower()
            return {
                "name": _text(node["name"]),
                "servings": _servings(node.get("recipeYield")),
                "total_minutes": _iso_minutes(node.get("totalTime")),
                "active_minutes": _iso_minutes(node.get("prepTime")),
                "type": "vegetar" if "veget" in category else "normal",
                "ingredients": [_text(i) for i in node.get("recipeIngredient") or [] if _text(i)],
                "steps": _steps(node.get("recipeInstructions")),
                "tip": _text(node.get("description"))[:500],
            }
    return None


def page_text(page: str) -> str:
    """A page's readable text, for the AI when it has no recipe data."""
    page = re.sub(r"<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", page, flags=re.DOTALL | re.I)
    return re.sub(r"\s+", " ", _text(page))[:15000]


def _check_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise _invalid("recipe_bad_link")
    return url.strip()


async def _check_public(hass: HomeAssistant, host: str) -> None:
    """Only pages on the internet: not Home Assistant itself or the home network."""
    try:
        infos = await hass.loop.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except OSError as err:
        raise _invalid("recipe_link_failed", error=str(err)) from err
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global:
            raise _invalid("recipe_bad_link")


async def async_fetch_page(hass: HomeAssistant, url: str) -> str:
    """Read a recipe page."""
    url = _check_url(url)
    await _check_public(hass, urlparse(url).hostname or "")
    session = async_get_clientsession(hass)
    try:
        async with session.get(
            url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True, max_redirects=5
        ) as resp:
            if resp.status >= 400:
                raise _invalid("recipe_link_failed", error=f"HTTP {resp.status}")
            raw = await resp.content.read(PAGE_LIMIT)
            return raw.decode(resp.charset or "utf-8", errors="replace")
    except (aiohttp.ClientError, TimeoutError) as err:
        raise _invalid("recipe_link_failed", error=str(err) or err.__class__.__name__) from err


def build_extract_prompt(text: str) -> str:
    """Ask the AI for the recipe on a page without recipe data."""
    return "\n".join(
        [
            "Herunder er teksten fra en hjemmeside med en opskrift. Find opskriften, og skriv "
            "den på dansk (oversæt, hvis den er på et andet sprog). Brug kun det, der står på "
            "siden. Er der ingen opskrift, så svar med name: null.",
            "",
            "SVARFORMAT: kun gyldig JSON, sådan:",
            json.dumps(
                {
                    "name": "Kylling i karry",
                    "type": "normal | vegetar",
                    "servings": 4,
                    "active_minutes": 20,
                    "total_minutes": 40,
                    "ingredients": [{"name": "kyllingebryst", "amount": "600 g"}],
                    "steps": [{"text": "Skær kyllingen i tern.", "minutes": 5}],
                    "tip": "",
                },
                ensure_ascii=False,
            ),
            "",
            "SIDENS TEKST:",
            text,
        ]
    )


async def async_import(planner: MealPlanner, url: str) -> dict[str, Any]:
    """Read the recipe behind a link (not saved: the panel shows it to be edited first)."""
    page = await async_fetch_page(planner.hass, url)
    found = parse_recipe_page(page)
    if found is None or not found.get("ingredients"):
        if not planner.ai_available():
            raise _invalid("recipe_not_on_page")
        try:
            found = await planner._async_ask_ai(
                build_extract_prompt(page_text(page)), "Middagsro opskrift fra link"
            )
        except HomeAssistantError as err:
            raise _invalid("recipe_link_failed", error=str(err)) from err
        if not isinstance(found, dict) or not found.get("name"):
            raise _invalid("recipe_not_on_page")
    recipe = clean_recipe({**found, "source": "link"})
    recipe["id"] = None  # not in the collection until saved
    return recipe
