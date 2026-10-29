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
    "cupnudler",
    "kopnudler",
    "instant",
    "cup",
}
# REMA's categories of ready-made food: not what an ingredient search is after.
_DISH_CATEGORIES = {
    "pizza", "pizzaer", "sandwich", "sandwiches", "wrap", "wraps", "færdigret", "færdigretter",
    "snack", "snacks", "kage", "kager", "slik", "is", "dessert", "desserter",
}  # fmt: skip
# The family asks for fresh or frozen; the other kind is not it.
_FRESH_WORDS = {"frisk", "friske", "fersk", "ferske"}
_FROZEN_WORDS = {"frost", "frossen", "frosne", "frosset", "dybfrost", "dybfrossen", "dybfrosne"}
_DRIED_WORDS = {"tørret", "tørrede", "tør", "tørre"}
_HERBS = {
    "oregano",
    "timian",
    "rosmarin",
    "basilikum",
    "persille",
    "purløg",
    "dild",
    "koriander",
    "mynte",
    "estragon",
    "salvie",
    "merian",
}
# First parts of compound words that make it another product (hvidløg is not løg).
_DIFFERENT_PREFIXES = {
    "hvid", "perle", "hvidløgs", "rød", "forårs", "sukker",
    # cupnudler and kopnudler are an instant meal, not the noodles for a dish
    "cup", "kop", "instant",
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

# These raw ingredients are prepared at home; meat, cheese and canned tomatoes
# retain descriptors that identify the product to buy.
_PREPARE_AT_HOME = {
    "løg", "hvidløg", "rødløg", "forårsløg", "skalotteløg", "porre", "porrer",
    "gulerod", "gulerødder", "kartoffel", "kartofler", "agurk", "squash", "peberfrugt",
    "broccoli", "blomkål", "kål", "hvidkål", "spidskål", "rødkål", "ingefær",
    "persille", "purløg", "dild", "koriander", "basilikum", "mynte",
    "knoldselleri", "selleri",
}  # fmt: skip
_CUT_AT_HOME = {
    "svinemørbrad", "mørbrad", "kyllingebryst", "kyllingebrystfilet", "kyllingefilet",
    "kalkunbryst", "oksebov", "okseklump",
}  # fmt: skip
_KEEP_PREPARATION = {
    "kød", "oksekød", "svinekød", "flæsk", "kylling", "kalkun", "lam", "lammekød",
    "ost", "parmesan", "mozzarella", "tomat", "tomater",
}  # fmt: skip
_TAP_WATER_WORDS = {
    "vand", "postevand", "koldt", "kold", "varmt", "varm", "lunkent", "kogende", "kogt",
    "afkølet", "iskoldt", "iskold", "fra", "hanen", "almindeligt", "rent", "lidt", "til",
    "kogning", "pensling", "pasta", "af", "efter", "behov", "ca", "dl", "ml", "l", "liter",
}  # fmt: skip


# A recipe's way of writing what to do with it, after a comma: "lime, saften herfra",
# "chili, hakket", "citrongræs, banket på langs". Not what to buy.
_PREPARATION_TAIL = {
    "hakket", "hakkede", "snittet", "snittede", "revet", "revne", "skåret", "skårne", "banket",
    "strimlet", "fintstrimlet", "strimlede", "presset", "pressede", "pillet", "pillede",
    "skrællet", "skrællede", "renset", "rensede", "saften", "saft", "skallen", "skal", "smag",
    "servering", "pynt", "delt", "halveret", "halverede", "udkernet", "udkernede", "kogt",
    "kogte", "stegt", "ristet", "ristede", "knust", "knuste", "fjernet", "valgfri", "valgfrit",
    "evt", "eventuelt", "gerne", "frisk", "friske", "tørret", "tørrede", "herfra", "heraf",
    "tern", "skiver", "strimler", "stykker", "både", "plus", "ekstra", "mere",
}  # fmt: skip
# "2 stængler citrongræs", "3 fed hvidløg", "1 bundt persille": the thing comes after.
_COUNT_WORDS = {
    "stængel", "stængler", "fed", "kvist", "kviste", "bundt", "bundter", "håndfuld", "håndfulde",
    "skive", "skiver", "blad", "blade", "nip", "knivspids", "dusk", "duske", "stilk", "stilke",
}  # fmt: skip
_FRESH_JUICE = {"citronsaft": "citron", "limesaft": "lime", "appelsinsaft": "appelsin"}
# Words in a bracket note that make it a note, not part of the name.
_NOTE_WORDS = {
    "eller",
    "efter",
    "ca",
    "cirka",
    "mængde",
    "kan",
    "undlades",
    "som",
    "fx",
    "f",
    "eks",
}


def _strip_recipe_notes(text: str) -> str:
    """'Lime, saften herfra (eller citron)' -> 'Lime'; '2 stængler citrongræs' -> 'citrongræs'."""
    name = text
    # Freshly pressed juice: the fruit is bought.
    if re.search(r"\bfriskpresse\w*\b", name, flags=re.IGNORECASE):
        name = re.sub(r"\bfriskpresse\w*\b", "", name, flags=re.IGNORECASE)
        for juice, fruit in _FRESH_JUICE.items():
            name = re.sub(rf"\b{juice}\b", fruit, name, flags=re.IGNORECASE)

    def note(match: re.Match[str]) -> str:
        # "(M)" says the size of the eggs; "(mængde efter smag)" says nothing to buy.
        words = set(_tokens(match.group(1)))
        return "" if words & (_PREPARATION_TAIL | _NOTE_WORDS) else match.group(0)

    name = re.sub(r"\s*\(([^)]*)\)", note, name)
    head, _sep, tail = name.partition(",")
    tail_words = set(_tokens(tail))
    if tail_words and not set(_tokens(head)) & _KEEP_PREPARATION and tail_words & _PREPARATION_TAIL:
        name = head  # "chili, hakket"; "tomater, hakkede" is a can and is kept
    words = name.split()
    # "2 stængler citrongræs": the counting word before the thing.
    while len(words) > 1 and (
        words[0].rstrip(".").replace(",", ".").replace("½", "").isdigit()
        or (_tokens(words[0]) and _tokens(words[0])[0] in _COUNT_WORDS)
    ):
        if not _tokens(words[0]) and not (
            len(words) > 2 and _tokens(words[1]) and _tokens(words[1])[0] in _COUNT_WORDS
        ):
            break  # "2 tomater": the number stays with the thing
        words = words[1:]
    name = " ".join(words)
    return " ".join(name.split()).strip(" ,;:")


def ingredient_name(text: str) -> str:
    """Remove home preparation, preserving the actual kind of product."""
    # A recipe's suggested pasta brand must not exclude equivalent products.
    text = re.sub(r"\brummo(?:[’']s)?\b", "", text, flags=re.IGNORECASE)
    text = _strip_recipe_notes(text) or text
    name = re.sub(
        r"\b(?:fint?|groft?)(hakket|hakkede|snittet|snittede|revet|revne)\b",
        r"\1",
        text,
        flags=re.IGNORECASE,
    )
    name = re.sub(
        r"\b(?:fint|groft)\s+(hakket|hakkede|snittet|snittede)\b", r"\1", name, flags=re.IGNORECASE
    )
    name = re.sub(
        r"\b(?:presset|pressede|pillet|pillede|skrællet|skrællede|renset|rensede)\b",
        "",
        name,
        flags=re.IGNORECASE,
    )
    words = set(_tokens(name))
    if (
        (words & _PREPARE_AT_HOME and not words & _KEEP_PREPARATION)
        or words & _CUT_AT_HOME
        or {"oksekød", "gryderet"} <= words
    ):
        name = re.sub(
            r"\b(?:skåret\s+)?(?:i\s+(?:(?:små|fine|tynde|grove)\s+)?(?:tern|skiver|strimler|stykker)|tern)\b",
            "",
            name,
            flags=re.IGNORECASE,
        )
    if words & _PREPARE_AT_HOME and not words & _KEEP_PREPARATION:
        name = re.sub(
            r"\b(?:hakket|hakkede|knust|knuste|revet|revne|snittet|snittede|skåret|skårne)\b",
            "",
            name,
            flags=re.IGNORECASE,
        )
    name = re.sub(r"\(\s*\)", "", name)
    return " ".join(name.split()).strip(" ,;")


def herb_form(text: str) -> str | None:
    """An explicit fresh/dried herb choice, independent of word order."""
    words = set(_tokens(text))
    if not words & _HERBS:
        return None
    if words & _DRIED_WORDS:
        return "dried"
    if words & _FRESH_WORDS:
        return "fresh"
    return None


def herb_form_matches(text: str, name: str, department: str | None, category: str | None) -> bool:
    """Plain 'Oregano' can be dried spice or a fresh pot; use shelf metadata."""
    wanted = herb_form(text)
    if wanted is None:
        return True
    words = set(_tokens(name))
    shelf = set(_tokens(f"{department or ''} {category or ''}"))
    if words & _DRIED_WORDS:
        actual = "dried"
    elif words & _FROZEN_WORDS or "frost" in shelf:
        actual = "frozen"
    elif words & _FRESH_WORDS or "grønt" in shelf or "grøntsager" in shelf:
        actual = "fresh"
    elif shelf & {"krydderi", "krydderier"}:
        actual = "dried"
    else:
        return False  # no evidence for the explicit form: let the user choose
    return actual == wanted


def stock_cubes(text: str) -> str | None:
    """Recognize stock without confusing the diluted volume with the product."""
    text = ingredient_name(text).lower()
    match = re.search(
        r"\b((?:grøntsags|grønsags|okse|hønse|kyllinge|svine)?bouil[li]on)(?:terning(?:er)?)?\b",
        text,
    )
    if not match:
        return None
    base = match.group(1).replace("bouilion", "bouillon")
    return f"{base} terninger"


def is_tap_water(text: str) -> bool:
    """Plain recipe water is available at home; bottled/flavoured water is not."""
    words = set(_tokens(text))
    return bool(words & {"vand", "postevand"}) and words <= _TAP_WATER_WORDS


# Chopped, peeled ("flåede") and crushed tomatoes are always the canned kind, never fresh.
_TOMATO_WORDS = {"tomat", "tomater"}
_CANNED_TOMATO_WORDS = {"hakket", "hakkede", "flået", "flåede", "knust", "knuste"}
_CANNED_WORDS = {"dåse", "dåser", "karton", "tetra", "konserves"}
_FRESH_SHELF = {"frugt", "grønt", "grøntsager"}
_NOT_CANNED_TOMATOES = {
    "soltørrede", "soltørret", "ketchup", "pure", "tomatpure", "passata", "suppe",
    "sauce", "pesto", "juice", "cherry", "cherrytomater", "snacktomater", "chips",
}  # fmt: skip


def canned_tomatoes(text: str) -> bool:
    """'Hakkede tomater', '2 tomater, hakket', 'flåede tomater': canned tomatoes."""
    words = set(_tokens(text))
    return bool(words & _TOMATO_WORDS) and bool(words & _CANNED_TOMATO_WORDS)


def canned_tomato_product(
    name: str, underline: str | None, department: str | None, category: str | None
) -> bool:
    """A can (or carton) of chopped or peeled tomatoes, not fresh ones from the shelf."""
    words = set(_tokens(f"{name} {underline or ''}"))
    shelf = set(_tokens(f"{department or ''} {category or ''}"))
    if not words & _TOMATO_WORDS or words & _NOT_CANNED_TOMATOES or shelf & _FRESH_SHELF:
        return False
    return bool(words & (_CANNED_TOMATO_WORDS | _CANNED_WORDS) or shelf & _CANNED_WORDS)


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
