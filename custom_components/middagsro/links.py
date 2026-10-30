"""The shared table of ingredients and the products they are, shop by shop.

``data/links.json`` maps a line's name, as :func:`link_name` writes it, to the
shop's product numbers it is: several where only the organic choice differs.
It is seeded from the test corpus and grows from families who share their
choices (product numbers and ingredient names, nothing about the family). A
name is only in it when everyone agrees what it is, so "pølser" and
"ostepølser" are each their own.
"""

from __future__ import annotations

import json
import logging
import pathlib
from typing import Any
from urllib.parse import quote

from .ingredients import COUNT_WORDS, _normal
from .words import ingredient_name

_LOGGER = logging.getLogger(__name__)

LINKS_FILE = pathlib.Path(__file__).parent / "data" / "links.json"
ISSUE_URL = "https://github.com/Dinnsen/ha-middagsro/issues/new"
# The shops the table knows, by the planner's shop name.
SHOP_KEYS = {"REMA 1000": "rema"}

# Words that don't change what a thing is in the table: the organic choice is
# the family's rule, not the ingredient.
_SAME = {"økologisk", "økologiske", "øko", "oeko", "eco", "frisk", "friske", "evt", "gerne"}


def _load() -> dict[str, dict[str, tuple[int, ...]]]:
    try:
        raw = json.loads(LINKS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        _LOGGER.warning("The shared product table could not be read: %s", err)
        return {}
    table: dict[str, dict[str, tuple[int, ...]]] = {}
    for shop, names in (raw.get("shops") or {}).items():
        table[shop] = {
            str(name): tuple(int(i) for i in ids if isinstance(i, int))
            for name, ids in names.items()
            if isinstance(ids, list) and ids
        }
    return table


LINKS: dict[str, dict[str, tuple[int, ...]]] = _load()


def link_name(name: str) -> str:
    """How a line's name is written in the table: its words, lower case, without
    home preparation, counting words or the organic choice."""
    words = [
        w for w in _normal(ingredient_name(name)).split() if w not in _SAME and w not in COUNT_WORDS
    ]
    return " ".join(words)


def linked_ids(shop: str, name: str) -> tuple[int, ...]:
    """The products the table says a line is, in a shop (empty: not known)."""
    key = SHOP_KEYS.get(shop)
    if key is None:
        return ()
    return LINKS.get(key, {}).get(link_name(name), ())


def merge(cases: list[tuple[str, list[int]]]) -> dict[str, list[int]]:
    """Names and the products they are, from many lines: one entry per name, only
    where every line agrees (the products all lines have in common)."""
    seen: dict[str, set[int]] = {}
    for name, ids in cases:
        key = link_name(name)
        if not key or not ids:
            continue
        if key in seen:
            seen[key] &= set(ids)
        else:
            seen[key] = set(ids)
    return {key: sorted(ids) for key, ids in sorted(seen.items()) if ids}


def family_links(plans: list[dict[str, Any]]) -> dict[str, list[int]]:
    """What the family has said products are: lines they kept or chose by hand."""
    cases: list[tuple[str, list[int]]] = []
    for plan in plans:
        for line in plan.get("shopping") or []:
            product = line.get("product") or {}
            if (
                product.get("id")
                and (line.get("reviewed") or line.get("remembered"))
                and not line.get("skipped")
                and not line.get("added")
                and not line.get("must_have")
                and not line.get("buy_at")
            ):
                cases.append((str(line.get("name") or ""), [int(product["id"])]))
    return merge(cases)


def share_url(shop: str, links: dict[str, list[int]]) -> str | None:
    """A prefilled GitHub issue with the family's links, for the shared table."""
    key = SHOP_KEYS.get(shop)
    if key is None or not links:
        return None
    known = LINKS.get(key, {})
    new = {name: ids for name, ids in links.items() if tuple(ids) != known.get(name)}
    url: str | None = None
    part: dict[str, list[int]] = {}
    # GitHub's links have a limit: as many as fit (the rest the next time).
    for name, ids in new.items():
        part[name] = ids
        body = (
            "Varer vi har valgt i Middagsro (kun ingrediens og varenummer):\n\n```json\n"
            + json.dumps({"shop": key, "links": part}, ensure_ascii=False, indent=1)
            + "\n```\n"
        )
        title = f"Koblinger: {len(part)} varer"
        candidate = f"{ISSUE_URL}?title={quote(title)}&labels=links&body={quote(body)}"
        if len(candidate) > 7500:
            break
        url = candidate
    return url
