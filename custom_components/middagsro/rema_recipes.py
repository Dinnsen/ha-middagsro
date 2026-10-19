"""REMA 1000's own recipes: browse them, and put them in the collection or on the plan.

The recipes come from the same API as REMA's shop. Every ingredient there is
linked to one of REMA's products, so the shopping list gets the very item.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util

from .api import RemaError, parse_time
from .const import DOMAIN
from .recipes import clean_recipe

if TYPE_CHECKING:
    from .mealplan import MealPlanner

PER_PAGE = 20
CACHE_TTL = timedelta(hours=6)

# REMA's recipe categories (their ids are stable), the ones for dinner first.
TAGS: list[dict[str, str]] = [
    {"id": "5Q5t9rpmNk4jp1ygKZDEHx", "title": "Avisopskrifter"},
    {"id": "6mjo9YHow8fdXyG4LhmHoK", "title": "Aftensmad"},
    {"id": "13gnXZJQl6zEqH0Qnse3W5", "title": "Nem hverdagsmad"},
    {"id": "lw0hPueEJErVe4xopoDEy", "title": "Mad for børn"},
    {"id": "2rdeKY4498Ma5tPsizr0Er", "title": "Kødfri"},
    {"id": "jAeeKhT7mZYiNRwe9tIXf", "title": "Sundere alternativer"},
    {"id": "7yfezsL41ufC4kYdHXjN8d", "title": "Fisk & skaldyr"},
    {"id": "6jW3N23HdWFdUn67W1QyBa", "title": "Nemt & Grønt"},
    {"id": "1oTNXyZWW9ZmKVdmzu3JzJ", "title": "Udenlandsk"},
    {"id": "6nVXfMWIDj4pH5juLFlBBU", "title": "Sæsonmad"},
    {"id": "1RCnmZMsWBa1PRWB6fU54I", "title": "Glutenfri"},
    {"id": "SfE2R4iD9lKEhsmRhaboV", "title": "Tilbehør til aftensmad"},
    {"id": "7y7OZ6ygtgLHrjW6NedXdf", "title": "Frokost"},
]
TAG_IDS = {t["id"] for t in TAGS}
VEGETARIAN_TAG = "2rdeKY4498Ma5tPsizr0Er"
SORTS = {"popular": "-popularity", "newest": "-created_at"}
# "Denne opskrift indeholder udvalgte varer fra avis uge 42" is only true that week.
_STALE_INTRO = "denne opskrift indeholder udvalgte varer"


def _invalid(key: str, **placeholders: str) -> ServiceValidationError:
    return ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key=key,
        translation_placeholders=placeholders or None,
    )


def _number(value: Any) -> str:
    """250 -> '250', 0.75 -> '0,75' (Danish)."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if number <= 0:
        return ""
    text = f"{number:.2f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def amount_text(amount: Any, unit: Any) -> str:
    """'250 g', '1 fed', '' when REMA gives no amount."""
    number = _number(amount)
    return f"{number} {unit}".strip() if number and unit else number


def image_url(image: Any, width: int = 800) -> str | None:
    """A smaller webp of a recipe's photo."""
    url = image.get("url") if isinstance(image, dict) else None
    if not isinstance(url, str) or not url.startswith("https://"):
        return None
    return f"{url}?w={width}&fm=webp&q=80"


def current_price(product: dict[str, Any], now: datetime) -> tuple[float | None, bool]:
    """(price, on offer) of a REMA product right now."""
    for entry in product.get("prices") or []:
        if not isinstance(entry, dict):
            continue
        start, end = parse_time(entry.get("starting_at")), parse_time(entry.get("ending_at"))
        if (start is None or start <= now) and (end is None or now < end + timedelta(days=1)):
            price = entry.get("price")
            return (float(price) if isinstance(price, int | float) else None), bool(
                entry.get("is_advertised")
            )
    return None, False


def _ingredients(entity: dict[str, Any]) -> list[dict[str, Any]]:
    form = (entity.get("fields") or {}).get("customForm") or {}
    out = []
    for group in form.get("ingredientGroups") or []:
        for item in (group or {}).get("ingredients") or []:
            if isinstance(item, dict) and str(item.get("ingredient") or "").strip():
                out.append(item)
    return out


def _product(item: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """(digital product, REMA's product for sale) of an ingredient."""
    digital = item.get("digitalProduct")
    if not isinstance(digital, dict):
        digital = {}
    active = digital.get("active_product")
    if not isinstance(active, dict):
        active = {}
    return digital, active


def _tags(entity: dict[str, Any]) -> list[dict[str, Any]]:
    return [t for t in (entity.get("fields") or {}).get("tags") or [] if isinstance(t, dict)]


def summary(entity: dict[str, Any], now: datetime) -> dict[str, Any] | None:
    """What a recipe card shows."""
    fields = entity.get("fields") or {}
    slug, title = fields.get("slug"), str(fields.get("title") or "").strip()
    if not slug or not title:
        return None
    form = fields.get("customForm") or {}
    on_offer = 0
    cost = 0.0
    items = _ingredients(entity)
    for item in items:
        digital, active = _product(item)
        if (
            not active
            or digital.get("is_basic_ingredient")
            or item.get("isExcludedFromShoppingList")
        ):
            continue
        price, offer = current_price(active, now)
        on_offer += offer
        cost += price or 0
    tags = _tags(entity)
    return {
        "slug": str(slug),
        "title": title[:300],
        "image": image_url(fields.get("image"), 480),
        "servings": int((form.get("servings") or {}).get("amount") or 0) or None,
        "total_minutes": int(form.get("totalTime") or 0) or None,
        "tags": [str((t.get("fields") or {}).get("title") or "") for t in tags][:6],
        "vegetarian": any(t.get("id") == VEGETARIAN_TAG for t in tags),
        "ingredients": len(items),
        "on_offer": on_offer,
        "cost": round(cost, 2),
    }


def to_recipe(entity: dict[str, Any]) -> dict[str, Any]:
    """A REMA recipe in the collection's shape, not saved yet (id None)."""
    fields = entity.get("fields") or {}
    form = fields.get("customForm") or {}
    ingredients = []
    for item in _ingredients(entity):
        digital, active = _product(item)
        ingredient: dict[str, Any] = {
            "name": str(item["ingredient"]).strip(),
            "amount": amount_text(item.get("amountOfContent"), item.get("unitOfContent")),
        }
        if active.get("id") and not item.get("isExcludedFromShoppingList"):
            ingredient["product"] = {
                "id": active["id"],
                "name": str(active.get("name") or digital.get("title") or "")[:120],
                "underline": str(active.get("underline") or "")[:120],
            }
        if digital.get("is_basic_ingredient"):
            ingredient["basic"] = True
        ingredients.append(ingredient)
    steps = [
        str(step.get("step") or "").strip()
        for group in form.get("preparationGroups") or []
        for step in (group or {}).get("steps") or []
        if isinstance(step, dict)
    ]
    tips = [
        str(form.get(key) or "").strip()
        for key in ("preparationTextBefore", "preparationTextAfter")
    ]
    tip = " ".join(t for t in tips if t and not t.lower().startswith(_STALE_INTRO))
    recipe = clean_recipe(
        {
            "name": str(fields.get("title") or "").strip(),
            "type": "vegetar"
            if any(t.get("id") == VEGETARIAN_TAG for t in _tags(entity))
            else "normal",
            "servings": (form.get("servings") or {}).get("amount") or 4,
            "total_minutes": form.get("totalTime") or 0,
            "ingredients": ingredients,
            "steps": [s for s in steps if s],
            "tip": tip,
            "source": "rema",
            "rema_slug": fields.get("slug"),
            "image": image_url(fields.get("image")),
        }
    )
    recipe["id"] = None
    return recipe


class RemaRecipes:
    """REMA's recipe pages, cached for a while (they change once a week)."""

    def __init__(self, planner: MealPlanner) -> None:
        """Initialize."""
        self._planner = planner
        self._pages: dict[tuple[str, str, int], tuple[datetime, dict[str, Any]]] = {}

    async def async_list(
        self,
        tag: str | None = None,
        sort: str = "popular",
        page: int = 1,
        query: str | None = None,
    ) -> dict[str, Any]:
        """A page of recipe cards: {recipes, page, last_page, total}; a search if query."""
        query = " ".join(str(query or "").split())[:80] or None
        if query:
            tag = None  # REMA's search covers every category
        if tag and tag not in TAG_IDS:
            raise _invalid("rema_recipes_failed", error="ukendt kategori")
        order = SORTS.get(sort, SORTS["popular"])
        page = max(1, min(int(page or 1), 100))
        key = (f"?{query.lower()}" if query else tag or "", order, page)
        now = dt_util.utcnow()
        cached = self._pages.get(key)
        if cached and now - cached[0] < CACHE_TTL:
            return cached[1]
        try:
            data = await self._planner.client.async_get_recipes(
                tag=tag, page=page, per_page=PER_PAGE, sort=order, query=query
            )
        except RemaError as err:
            raise _invalid("rema_recipes_failed", error=str(err)) from err
        pagination = (data.get("meta") or {}).get("pagination") or {}
        recipes = [
            card
            for entity in data.get("data") or []
            if isinstance(entity, dict) and (card := summary(entity, now))
        ]
        result = {
            "recipes": recipes,
            "page": int(pagination.get("current_page") or page),
            "last_page": int(pagination.get("last_page") or page),
            "total": int(pagination.get("total") or len(recipes)),
        }
        if len(self._pages) > 60:
            self._pages.clear()
        self._pages[key] = (now, result)
        return result

    async def async_get(self, slug: str) -> dict[str, Any]:
        """One recipe in the collection's shape (not saved)."""
        slug = str(slug or "").strip()[:200]
        if not slug:
            raise _invalid("recipe_not_found")
        try:
            entity = await self._planner.client.async_get_recipe(slug)
        except RemaError as err:
            raise _invalid("rema_recipes_failed", error=str(err)) from err
        if entity is None:
            raise _invalid("recipe_not_found")
        return to_recipe(entity)
