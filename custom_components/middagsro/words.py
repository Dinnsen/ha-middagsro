"""The words of product and dish names, as REMA and the family write them."""

from __future__ import annotations

import re

_ABBREVIATIONS = {"hk": "hakket", "øko": "økologisk", "økologiske": "økologisk"}
# Extra words that make a product something else than what was asked for.
_DIFFERENT_WORDS = {
    "løse",
    "søde",
    "grønt",
    "grøntsager",
    "blanding",
    "mix",
    "pålæg",
    "marineret",
    "krydret",
    "kryddret",
    "paneret",
    "panerede",
    "røget",
    "gravad",
    "gravet",
    "gravede",
    "citronpeber",
    "chili",
    "sauce",
    "dressing",
    "salat",
    "suppe",
    "juice",
    "snack",
    "chips",
    # a dish made of it is not the ingredient (kebab pizza is no kebab)
    "pizza",
    "pizzaer",
    "sandwich",
    "wrap",
    "wraps",
    "lasagne",
    "tærte",
    "toast",
    "is",
    "sorbet",
    "dessert",
    "kage",
    "kager",
    "slik",
    "shake",
    "smoothie",
    "pulver",
    "bouillon",
    "fond",
}
# REMA's categories of ready-made food: not what an ingredient search is after.
_DISH_CATEGORIES = {
    "pizza", "pizzaer", "sandwich", "sandwiches", "wrap", "wraps", "færdigret", "færdigretter",
    "snack", "snacks", "kage", "kager", "slik", "is", "dessert", "desserter",
}  # fmt: skip
# The family asks for fresh or frozen; the other kind is not it.
_FRESH_WORDS = {"frisk", "friske", "fersk", "ferske"}
_FROZEN_WORDS = {"frost", "frossen", "frosne", "frosset", "dybfrost", "dybfrossen", "dybfrosne"}
# First parts of compound words that make it another product (hvidløg is not løg).
_DIFFERENT_PREFIXES = {
    "hvid", "perle", "hvidløgs", "rød", "forårs", "sukker",
    # kakaomælk, havremælk, kærnemælk … are not mælk
    "kakao", "chokolade", "kokos", "mandel", "havre", "soja", "kærne",
}  # fmt: skip
# Words in product names that say nothing about what the product is.
_NEUTRAL_WORDS = {
    "rema",
    "og",
    "med",
    "i",
    "af",
    "til",
    "en",
    "et",
    "dansk",
    "danske",
    "økologisk",
    "kl",
    "stk",
    "gr",
    "g",
    "kg",
    "ltr",
    "ml",
    "fedt",
    "frisk",
    "friske",
}

_ACCENTS = str.maketrans("éèêëáàâíìîïóòôúùûüç", "eeeeaaaiiiiooouuuuc")


def _tokens(text: str) -> list[str]:
    """Lower-case words of a product name, with REMA's abbreviations expanded."""
    words = re.findall(r"[a-zæøå]+", text.lower().translate(_ACCENTS))
    return [_ABBREVIATIONS.get(w, w) for w in words]


def _stem(word: str) -> str:
    """A word without its Danish plural/definite ending, to compare names."""
    for ending in ("erne", "ene", "er", "e", "r"):
        if word.endswith(ending) and len(word) - len(ending) >= 4:
            return word[: -len(ending)]
    return word


def _name_words(text: str) -> set[str]:
    return {_stem(w) for w in _tokens(text) if len(w) > 1 and w not in _NEUTRAL_WORDS}


def pantry_words(text: str) -> list[str]:
    """The family's basic items: 'salt, peber, olie og smør' -> salt, peber, olie, smør."""
    parts = re.split(r",|;|\n|\bog\b", text, flags=re.IGNORECASE)
    seen: list[str] = []
    for part in parts:
        word = part.strip().lower()
        if word and word not in seen:
            seen.append(word)
    return seen


def _uses_item(item: str, ingredient: str) -> bool:
    """Is a recipe ingredient this basic item? 'rapsolie' is olie; 'mælk' isn't mel."""
    wanted = _tokens(item)
    if not wanted:
        return False
    words = _tokens(ingredient)
    return all(
        any(
            w == want or (len(want) > 2 and w.endswith(want) and len(w) > len(want) + 2)
            for w in words
        )
        for want in wanted
    )
