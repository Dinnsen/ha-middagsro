"""Matching a shopping line to a shop's products by name: the words, the
avis offers, what the line is and the lines of a list."""

from __future__ import annotations

from datetime import UTC, date, datetime, time as clock_time, timedelta
import logging
import math
import re
from typing import Any

from homeassistant.util import dt as dt_util

from .amounts import add_amounts, package_size, pieces_per_package, to_base
from .api import Offer, Product
from .ingredients import FISH, MEAT, POULTRY, Spec, spec_for
from .words import (
    _DIFFERENT_PREFIXES,
    _DIFFERENT_WORDS,
    _DISH_CATEGORIES,
    _FRESH_WORDS,
    _FROZEN_WORDS,
    _NEUTRAL_WORDS,
    _name_words,
    _stem,
    _tokens,
    herb_form,
    ingredient_name,
    stock_cubes,
)

_LOGGER = logging.getLogger(__name__)


# Products REMA sells as "free from" an allergen.
# A milk allergy is to the protein: lactose-free dairy is no help, so only lactose maps.
FREE_FROM = {"gluten": "GLUTENFRI", "lactose": "LAKTOSEFRI"}


SEARCH_CONCURRENCY = 4


def prices_from(day: date) -> datetime:
    """When REMA has a day's products and prices: 00:00 UTC (02:00 danish), plus a margin."""
    return datetime.combine(day, clock_time(0, 5), UTC)


def noon(day: date) -> datetime | None:
    """Noon (danish time) on a day, in UTC, or None if that has passed: then prices are now."""
    moment = dt_util.start_of_local_day(day) + timedelta(hours=12)
    return dt_util.as_utc(moment) if moment > dt_util.now() else None


def _alternative(product: Product) -> dict[str, Any]:
    """A product the family may choose instead, as the panel shows it."""
    return {
        "id": product.id,
        "name": product.name,
        "underline": product.underline,
        "price": product.price,
        "is_organic": product.is_organic,
        "image": product.image,
    }


def avis_packages(
    amount: float | None, unit: str | None, offer: Offer, piece_g: int | None = None
) -> int:
    """How many of an avis offer's items cover an amount (by the avis's size).

    ``piece_g``: what one piece weighs, so "8 pølser" of a 330 g pack is two
    packs, not eight.
    """
    need = to_base(amount, unit) if amount and amount > 0 else None
    if need is None:
        return 1
    if need[0] == "pack":
        return max(1, min(20, math.ceil(need[1])))
    size = avis_size(offer, need[0])
    grams = avis_size(offer, "g") if need[0] == "stk" else None
    per = pieces_per_package(("g", grams[0]), piece_g) if grams else None
    if size and size[0] > 0:
        return max(1, min(20, math.ceil(need[1] / size[0] - 0.05)))
    if per and per >= 1:  # a pack of several pieces (not a part of one, like 120 g of pizza)
        return max(1, min(20, math.ceil(need[1] / per - 0.05)))
    if need[0] == "stk":
        return max(1, min(20, math.ceil(need[1])))
    return 1


# Words in REMA's underline that say where a product is from, not its brand.
_ORIGINS = {
    "danmark", "dansk", "danske", "land", "kl", "egypten", "spanien", "holland", "italien",
    "norge", "norsk", "tyskland", "frankrig", "sverige", "polen", "marokko", "peru", "chile",
    "portugal", "grækenland", "tyrkiet", "brasilien", "colombia", "ecuador", "costa", "israel",
    "sydafrika", "kenya", "new", "argentina", "mexico", "irland", "belgien", "udenlandsk",
}  # fmt: skip


# Words in an avis heading that describe rather than name a product or brand.
_AVIS_WORDS = _NEUTRAL_WORDS | {
    "eller", "pr", "partivare", "max", "frost", "dybfrost", "ca", "stk", "pak", "nyhed",
    "konventionelle", "økologiske", "udenlandske", "udenlandsk", "fersk", "ferske",
}  # fmt: skip


_PERCENT = re.compile(r"(\d+(?:[.,]\d+)?(?:\s*-\s*\d+(?:[.,]\d+)?)?)\s*%")


_RANGE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(?:-\s*(\d+(?:[.,]\d+)?))?\s*(KG|GR|G|LTR|LITER|L|ML|CL|DL|STK)\b",
    re.IGNORECASE,
)


def _brand(underline: str | None) -> str | None:
    """The brand in REMA's underline ('500 GR. / KAROLINES KØKKEN' -> karolines)."""
    if not underline or "/" not in underline:
        return None
    words = _tokens(underline.split("/", 1)[1])
    if not words or words[0] in _ORIGINS or words[0] == "økologisk":
        return None
    return words[0]


_LIMIT = re.compile(
    r"(?:max\.?|flere end|ved køb af(?: mindst)?)\s*\d+\s*(?:stk|pk|ks|pakker|poser)\.?",
    re.IGNORECASE,
)


_FRACTION_SIZE = re.compile(r"(\d+)\s*/\s*(\d+)\s*(kg|l|liter)\b", re.IGNORECASE)


def avis_size(offer: Offer, kind: str) -> tuple[float, float] | None:
    """The size range of one kind (g, ml or stk) an avis offer is for.

    "Max 6 stk." and "ved køb af flere end 6 stk." are limits, not sizes.
    """
    text = _LIMIT.sub(" ", f"{offer.description or ''} {offer.quantity or ''}")
    # "Pr. 1/2 kg" is half a kilo, not 2 kg.
    text = _FRACTION_SIZE.sub(lambda m: f"{int(m[1]) / int(m[2]):g} {m[3]}", text)
    found: list[tuple[float, float]] = []
    for low, high, unit in _RANGE.findall(text):
        a = to_base(float(low.replace(",", ".")), unit)
        b = to_base(float((high or low).replace(",", ".")), unit)
        if a and b and a[0] == kind:
            found.append((a[1], b[1]))
    if not found:
        return None
    return min(f[0] for f in found), max(f[1] for f in found)


# "Spar 30 %" and "op til 40 % rabat" are savings, not fat percentages.
_SAVINGS = re.compile(
    r"(?:spar|op til|ca\.?|cirka)\s*\d+(?:[.,]\d+)?\s*%|\d+(?:[.,]\d+)?\s*%\s*(?:rabat|billigere)",
    re.IGNORECASE,
)


def _percents(text: str) -> set[str]:
    text = _SAVINGS.sub(" ", text)
    return {re.sub(r"\s+", "", p).replace(",", ".") for p in _PERCENT.findall(text)}


def avis_match(name: str, underline: str | None, organic: bool, offer: Offer) -> bool:
    """Is a REMA product the very product an avis offer is for?

    Strict, because a wrong match puts a wrong price on the list:
    - every word of the product's name is in the offer's heading (a compound
      like "rugbrød" for "brød" only when the offer names the product's brand;
      any variety when the heading is just the product's name, "Kærgården"),
    - unless the heading names the product's brand, the product's part of it
      ("X, Y eller Z") names nothing the product isn't (another brand, another
      variety),
    - the size is within the offer's size or range,
    - fat percentages (8-12%) are the same,
    - organic matches organic.
    """
    return _avis_name_fits(name, underline, offer) and _avis_details_fit(
        name, underline, organic, offer
    )


def _avis_name_fits(name: str, underline: str | None, offer: Offer) -> bool:
    heading = _tokens(offer.heading)
    heading_words = {_stem(w) for w in heading if len(w) > 1}
    brand = _brand(underline)
    # REMA's underline has the brand after the size, but often a variety
    # instead ("200 GR. / LET"): only a brand the heading names counts.
    branded = bool(brand and brand != "rema" and brand in heading)
    words = _name_words(name)
    if not words:
        return False
    named = [w for w in heading if len(w) > 2 and w not in _AVIS_WORDS]
    first = _name_words(_tokens(name)[0]) if _tokens(name) else set()
    if len(named) == 1 and {_stem(named[0])} == first and _same_size(underline, offer):
        # "Kærgården" (200 g): the whole line of the product, any variety.
        # Only with the same kind of size: "Æbler" (1 stk.) is no apple juice.
        words = first
    for word in words:
        # "rugbrød" in "Schulstad Det Gode brød": the offer is for the brand's range.
        if word not in heading_words and not (
            branded and any(len(h) > 3 and word.endswith(h) for h in heading_words)
        ):
            return False
    if branded:
        return True
    parts = re.split(r",|\beller\b", offer.heading, flags=re.IGNORECASE)
    own = max(parts, key=lambda part: len(words & _name_words(part)))
    if heading and heading[0] != "rema":
        # "Lotus Premium Toiletpapir eller køkkenruller": the brand in front
        # is for every part, so not REMA's own køkkenruller.
        own = f"{' '.join(_tokens(parts[0])[:-1])} {own}"
    return not any(
        len(w) > 2 and w not in _AVIS_WORDS and _stem(w) not in words for w in _tokens(own)
    )


def _same_size(underline: str | None, offer: Offer) -> bool:
    """The product and the offer both have a size, of the same kind (g, ml, stk)."""
    size = package_size(underline)
    return bool(size and avis_size(offer, size[0]))


def _avis_details_fit(name: str, underline: str | None, organic: bool, offer: Offer) -> bool:
    text = f"{offer.heading}\n{offer.description or ''}"
    size = package_size(underline)
    sizes = avis_size(offer, size[0]) if size else None
    if size and sizes and not sizes[0] * 0.9 <= size[1] <= sizes[1] * 1.1:
        return False
    offer_percents = _percents(text)
    product_percents = _percents(name)
    if offer_percents and product_percents and not product_percents & offer_percents:
        return False
    words = _tokens(text)
    if "økologisk" in words:
        return organic or any(w.startswith("konventionel") for w in words)
    return not organic


def offer_covers(
    offer: Offer, product_id: int | None, name: str, underline: str | None, organic: bool
) -> bool:
    """Is the offer for this product? By REMA's product ids when Tjek has them.

    When Tjek also lists products without a REMA id ("Arla Skyr Airy"), or none
    at all, a product the ids don't cover can still be the offer by name.
    """
    if offer.product_ids is not None:
        if product_id in offer.product_ids:
            return True
        if not offer.unlinked:
            return False
        if unlinked_match(name, underline, organic, offer):
            return True
    return avis_match(name, underline, organic, offer)


def unlinked_match(name: str, underline: str | None, organic: bool, offer: Offer) -> bool:
    """Is a REMA product one Tjek lists for the offer without REMA's id?

    Every word of REMA's name is in Tjek's ("SKYR AIRY JORDBÆR" in "Arla Skyr
    Airy Jordbær"), and size, fat percentage and organic fit the offer.
    """
    words = _name_words(name)
    return bool(words) and any(
        words <= _name_words(tjek) and _avis_details_fit(name, underline, organic, offer)
        for tjek in offer.unlinked_names
    )


def offer_query(offer: Offer, name: str = "") -> str:
    """REMA search words for the part of an avis offer a line is about.

    'REMA 1000 salami, leverpostej eller Taga serrano' for 'leverpostej' ->
    'leverpostej'; 'REMA 1000 Laksefilet' -> 'Laksefilet'.
    """
    heading = re.sub(r"^REMA 1000\s+", "", offer.heading.strip(), flags=re.IGNORECASE)
    parts = [p.strip() for p in re.split(r",|\beller\b", heading, flags=re.IGNORECASE)]
    wanted = _name_words(name)
    best = max(parts, key=lambda part: len(wanted & _name_words(part)))
    return best or heading or offer.heading


_SPLIT_TAILS = ("dressing", "sauce", "sovs", "pasta", "creme", "pålæg", "pulver")


def search_queries(line: dict[str, Any]) -> list[str]:
    """What to search REMA for, best guess first.

    REMA names minced meat "HK. ...KØD", so "kyllingefars" is also tried as
    "hakket kylling", and the line's own name is tried last.
    """
    queries = [ingredient_name(line["search"])]
    for word in _tokens(queries[0]):
        if word.endswith("fars") and len(word) > 4:
            meat = word[:-4].rstrip("e")
            queries.append(f"hakket {meat}")
        # "Cæsardressing" is "CÆSAR DRESSING" on REMA's shelf: split a compound in two.
        for tail in _SPLIT_TAILS:
            if word.endswith(tail) and len(word) > len(tail) + 2:
                queries.append(f"{word[: -len(tail)]} {tail}")
    queries.append(ingredient_name(line["name"]))
    for query in list(queries):
        if herb_form(query):
            queries.append(
                re.sub(
                    r"\b(?:tørret|tørrede|tør|tørre|frisk|friske|fersk|ferske)\b",
                    "",
                    query,
                    flags=re.IGNORECASE,
                ).strip(" ,;")
            )
        if cubes := stock_cubes(query):
            queries.append(cubes.removesuffix(" terninger"))
        if "karrypulver" in _tokens(query):
            queries.append(re.sub(r"\bkarrypulver\b", "karry", query, flags=re.IGNORECASE))
        if "svinemørbrad" in _tokens(query):
            queries.append("mørbrad gris")
        if {"oksekød", "gryderet"} <= set(_tokens(query)):
            queries.extend(["oksekød tern", "gullasch"])
    unique: list[str] = []
    for query in queries:
        if query and query.lower() not in (q.lower() for q in unique):
            unique.append(query)
    return unique


def name_fit(
    search_words: list[str], product_name: str, neutral: tuple[str, ...] = ()
) -> tuple[int, float]:
    """How well a product name fits the searched words.

    Returns (number of searched words found, price penalty factor). Danish
    compound words count as a match ("skrabeæg" is æg, "laksefileter" is laks),
    but cost a little more than the plain word. Words that make it a different
    product ("søde kartofler", "oksekød 35% grønt", "broccoliblanding",
    "hvidløg" for løg) cost a lot, so they are only chosen if nothing else fits.
    """
    name = [t for t in _tokens(product_name) if len(t) > 1]
    matched = 0
    penalty = 1.0
    for word in search_words:
        if word in name:
            matched += 1
            continue
        compound = next(
            (
                t
                for t in name
                # A short word only at the end: skrabeæg is æg, æggestand isn't.
                if t.endswith(word) or (t.startswith(word) and len(word) > 3)
            ),
            None,
        )
        if compound is None:
            # "cæsardressing" written as one word, "CÆSAR DRESSING" as two.
            if any(name[i] + name[i + 1] == word for i in range(len(name) - 1)):
                matched += 1
                penalty += 0.15
            continue
        matched += 1
        rest = compound[len(word) :] if compound.startswith(word) else compound[: -len(word)]
        # Danish joins compounds with -e- or -s- (laks-e-pålæg, hvidløg-s-...).
        parts = {rest, rest.strip("es")}
        different = parts & (_DIFFERENT_WORDS | _DIFFERENT_PREFIXES)
        penalty += 5.0 if different else 0.15
    for token in name:
        if (
            token in _NEUTRAL_WORDS
            or token in neutral
            or any(word in token or token in word for word in search_words)
        ):
            continue
        is_other = token in _DIFFERENT_WORDS or any(
            token.endswith(d) for d in _DIFFERENT_WORDS if len(d) > 4
        )  # "varmrøget" is røget
        penalty += 5.0 if is_other else 0.15
    return matched, penalty


_PHRASE_BREAKS = {"med", "uden", "i", "til", "fra", "af", "på", "pa", "eller", "og"}


# Words that say how a thing is, not what it is: "tomater, hakkede" are tomatoes,
# "løg rødt" onions, "mælk let" milk. Skipped when they come after the thing.
_DESCRIBING = frozenset({
    "hakket", "hakkede", "revet", "revne", "skåret", "skårne", "kogt", "kogte", "stegt",
    "stegte", "røget", "røgede", "tørret", "tørrede", "frossen", "frosne", "frosset", "fersk",
    "ferske", "frisk", "friske", "hel", "hele", "halv", "halve", "ny", "nye", "små", "store",
    "stor", "lille", "mager", "magert", "magre", "let", "lette", "fed", "fede", "saltet",
    "usaltet", "rød", "rødt", "røde", "grøn", "grønt", "grønne", "gul", "gult", "gule",
    "hvid", "hvidt", "hvide", "sort", "sorte", "brun", "brune", "dansk", "danske", "øko",
    "økologisk", "økologiske", "skiver", "tern", "strimler", "stykker", "str", "stk", "pk",
    "dåse", "glas", "naturel", "neutral", "ekstra", "fin", "fint", "fine", "grov",
    "groft", "grove", "mellem", "skrællet", "skrællede", "flået", "flåede", "pillet",
    "pillede", "renset", "rensede", "marineret", "marinerede", "krydret", "krydrede",
    "terning", "terninger",
})  # fmt: skip


def _called(spec: Spec, product_name: str) -> bool:
    """Is the product called by one of the catalogue's names for the thing
    ("GRANA PADANO" for parmesan, "RØDSPÆTTEFILETER" for fiskefilet)?"""
    if spec.entry is None:
        return False
    tokens = _tokens(product_name)
    for name in (spec.entry.key, *spec.entry.aliases):
        words = [w for w in _tokens(name) if len(w) > 1 and w not in _NEUTRAL_WORDS]
        if len(name) > 3 and words and all(_is_word(w, tokens) for w in words):
            return True
    return False


def _is_word(word: str, tokens: list[str]) -> bool:
    """Is the word one of the tokens, allowing a plural ending ("rødspættefileter")?"""
    return any(t == word or (t.startswith(word) and len(t) - len(word) <= 2) for t in tokens)


def head_word(query: str) -> str | None:
    """The word a search is about: the last one before "med", "uden", "til" …

    Danish puts the thing last: "grønne bønner" are beans, "hakket oksekød" beef,
    "laksefilet med skind" a salmon fillet. A list's way of writing it ("tomater,
    hakkede", "oksekød hakket 8-12%") puts how it is last: that is skipped.
    """
    words: list[str] = []
    for token in _tokens(query):
        if token in _PHRASE_BREAKS and words:
            break
        if len(token) > 1 and token not in _NEUTRAL_WORDS and not token.isdigit():
            words.append(token)
    # "Tomater, hakkede": a describing word after the thing is not the thing.
    things = [w for w in words if w not in _DESCRIBING]
    if things:
        return things[-1]
    return words[-1] if words else None


def kind_penalty(
    line: dict[str, Any],
    product: Product,
    words: list[str],
    trusted: bool = False,
    spec: Spec | None = None,
) -> float:
    """Extra cost for a product that is another kind of thing than the line asks for.

    A dish made of it (kebab pizza, a chicken wrap) is not the ingredient, frozen
    is not fresh (and the other way round), and fruit and vegetables are fresh
    unless the line says frozen. ``trusted``: the catalogue already allowed the
    product's category (peanuts are on the snack shelf), so that is no mark against it.
    """
    asked = set(_tokens(f"{line.get('search') or ''} {line.get('name') or ''}"))
    category = set(_tokens(product.category or ""))
    penalty = 0.0
    if "vej selv" in (product.underline or "").lower().replace('"', ""):
        penalty += 5.0  # loose, weighed by the customer: a bag is what a list means
    if (
        not trusted
        and category & _DISH_CATEGORIES
        and not any(w in category or any(c.startswith(w) for c in category) for w in words)
    ):
        penalty += 5.0
    name = set(_tokens(product.name))
    frozen = (product.department or "").lower() == "frost" or bool(name & _FROZEN_WORDS)
    wants_frozen = bool(asked & _FROZEN_WORDS)
    wants_fresh = bool(asked & _FRESH_WORDS) or (line_kind(line) == "produce" and not wants_frozen)
    if (frozen and wants_fresh) or (not frozen and wants_frozen):
        penalty += 5.0
    elif frozen and not wants_frozen and spec is not None and spec.kinds & _FRESH_FIRST:
        penalty += 0.5  # frozen meat or fish only when it is clearly cheaper
    return penalty


_FRESH_FIRST = frozenset({MEAT, POULTRY, FISH})


_EGG_LEVEL = {"caged": 0, "free_range": 1, "organic": 2}


_NOT_EGGS = {"pålæg", "indlæg", "tillæg", "oplæg", "pålægs"}


_NOT_DAIRY_MILK = ("kokos", "mandel", "havre", "soja", "ris", "kakao", "kærne")


def egg_level(product: Product) -> int:
    """0 = skrabeæg (or unknown), 1 = frilandsæg, 2 = økologiske æg."""
    text = f"{product.name} {product.underline or ''}".upper()
    if product.is_organic or re.search(r"(^|[^A-ZÆØÅ])ØKO", text):
        return 2
    if "FRILAND" in text:
        return 1
    return 0


def line_kind(line: dict[str, Any]) -> str | None:
    """Is a shopping line eggs, (dairy) milk or fruit & vegetables?"""
    tokens = _tokens(f"{line.get('search') or ''} {line.get('name') or ''}")
    if any(t == "æg" or (t.endswith("æg") and t not in _NOT_EGGS) for t in tokens):
        return "egg"
    if any(
        "mælk" in t and "chokolade" not in t and not t.startswith(_NOT_DAIRY_MILK) for t in tokens
    ):
        return "milk"
    category = str(line.get("category") or "").lower()
    if "frugt" in category or "grønt" in category:
        return "produce"
    return None


def line_spec(line: dict[str, Any]) -> Spec:
    """What a shopping line asks for (the catalogue's view of its words)."""
    return spec_for(
        str(line.get("name") or ""), line.get("search"), line.get("category"), line.get("catalog")
    )


def apply_spec(line: dict[str, Any], spec: Spec | None = None) -> bool:
    """Read what a line is and write it on the line: its key (to merge lines and
    remember choices), the search term the shop knows, and parts of a package
    counted as one ("3 fed hvidløg" is one bulb). False: not a thing to buy (a
    recipe's heading, its equipment, water). ``spec``: read from the words as
    first written, when the line's name has been cleaned since."""
    if spec is None:
        spec = line_spec(line)
    if spec.skip:
        return False
    line["key"] = spec.key
    if (
        spec.entry is not None
        and not line.get("product_id")
        and not line.get("must_have")
        and not line.get("stock_cubes")
    ):
        line["search"] = spec.query
    if spec.count_word and line.get("amount") and (line.get("unit") or "stk") in ("stk", "pk"):
        line["amount"] = max(1, math.ceil(float(line["amount"]) / spec.per_package))
        line["unit"] = "pk"
    return True


def merge_lines(
    shopping: list[dict[str, Any]],
    days: list[dict[str, Any]],
    original: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """One line per thing: the overview's "Løg" and "Løg, i både" are bought together.

    Lines the catalogue reads as the same thing (the same key) are added up on
    the first of them, which keeps an offer any of them had; the dishes' lists
    of what they use are renamed to it (``original``: the names the AI wrote,
    lower-cased, to the cleaned names the lines got). Basic items the family
    keeps and lines bought as a particular product stay as they are.
    """
    first: dict[str, dict[str, Any]] = {}
    renamed: dict[str, str] = dict(original or {})
    merged: list[dict[str, Any]] = []
    for line in shopping:
        key = str(line.get("key") or "")
        if not key or line.get("must_have") or line.get("product_id") or line.get("stock_cubes"):
            merged.append(line)
            continue
        kept = first.get(key)
        if kept is None:
            first[key] = line
            merged.append(line)
            continue
        add_amounts(kept, line, line_spec(kept).piece_g)
        if line.get("offer") and not kept.get("offer"):
            kept["offer"] = line["offer"]
        if line["name"] != kept["name"]:
            for raw, clean in list(renamed.items()):
                if clean == line["name"]:
                    renamed[raw] = kept["name"]
            renamed[line["name"].lower()] = kept["name"]
    if renamed:
        for day in days:
            uses: list[str] = []
            for name in day.get("uses") or []:
                new = renamed.get(str(name).lower(), name)
                if new not in uses:
                    uses.append(new)
            day["uses"] = uses
    return merged


def needs_review(line: dict[str, Any]) -> bool:
    """Should the family look at this line before it is sent: the match is not
    sure, and nobody has confirmed, changed or left it out yet."""
    return (
        line.get("confidence") in ("medium", "low")
        and not line.get("reviewed")
        and not line.get("must_have")
        and not line.get("added")
        and not line.get("sent")
        and not line.get("skipped")
    )


def plan_total(shopping: list[dict[str, Any]]) -> float:
    """What the list costs: every line with a price, except those the family left out."""
    return round(sum(line.get("cost") or 0 for line in shopping if not line.get("skipped")), 2)
