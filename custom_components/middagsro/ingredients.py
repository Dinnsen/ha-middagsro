"""What an ingredient is, and which of a shop's products can be it.

Two things decide whether a product is the ingredient a recipe asks for, before
any names are compared:

* **the kind of thing** - a vegetable, a spice, a canned good, minced meat - which
  the shop's own category says reliably ("Konserves & survarer" is a can, "Saucer
  & nem mad" is a ready sauce or an instant meal, "Krydderier" a spice). A product
  of another kind than the ingredient is out, however well its name fits: cup
  noodles are never the noodles for a dish, ground chili never a fresh one.
* **the catalogue** of common ingredients (:data:`CATALOG`): what a Danish recipe
  calls it, what the shop calls it, the kind, the usual form (fresh, canned,
  dried), what one piece weighs and how the thing is counted ("3 fed hvidløg" is
  one bulb). A fix for a wrongly matched ingredient is a line here, not code.

Everything here is pure: no Home Assistant, no network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from .words import _tokens, canned_tomatoes, ingredient_name, is_tap_water

# ------------------------------------------------------------------ kinds

# The kinds of thing a product can be. A line allows a set of them.
VEG = "veg"
FRUIT = "fruit"
HERB = "herb"  # fresh herbs (a pot or a bunch)
MEAT = "meat"  # beef, pork, lamb, veal, minced meat
POULTRY = "poultry"
FISH = "fish"  # fish and seafood, also canned tuna
SAUSAGE = "sausage"  # pølser, chorizo, salami as a cooking ingredient
BACON = "bacon"
COLD_CUTS = "cold_cuts"  # pålæg
DAIRY = "dairy"  # milk, cream, yoghurt, skyr, butter
CHEESE = "cheese"
EGG = "egg"
BREAD = "bread"
PASTA = "pasta"  # pasta, rice, noodles, couscous, bulgur
CANNED = "canned"  # cans and jars: tomatoes, beans, corn, coconut milk, olives
SAUCE = "sauce"  # ready sauces, soy, fish sauce, dressing, ketchup, mustard, mayo
STOCK = "stock"  # bouillon cubes and fond
SPICE = "spice"  # dried spices and herbs
BAKING = "baking"  # flour, sugar, yeast, dough
NUTS = "nuts"  # nuts, seeds, dried fruit
OIL = "oil"  # oil and vinegar
CEREAL = "cereal"  # oats, muesli
FROZEN = "frozen"  # frozen vegetables, fruit, berries
READY = "ready"  # ready meals, pizza, instant noodles, sandwiches, salads
SNACK = "snack"  # chips, bars, candy, ice cream
DRINK = "drink"
NONFOOD = "nonfood"  # household, personal care, pets, kitchen tools

# What an ingredient of a dish may be, unless the catalogue or the words say more.
FOOD_KINDS = frozenset(
    {
        VEG, FRUIT, HERB, MEAT, POULTRY, FISH, SAUSAGE, BACON, COLD_CUTS, DAIRY, CHEESE, EGG,
        BREAD, PASTA, CANNED, SAUCE, STOCK, SPICE, BAKING, NUTS, OIL, CEREAL, FROZEN,
    }
)  # fmt: skip
# Never an ingredient unless the line names such a thing itself.
NEVER_KINDS = frozenset({READY, SNACK, DRINK, NONFOOD})

# The AI's coarse category of a shopping line -> the kinds it may be.
LINE_CATEGORY_KINDS: dict[str, frozenset[str]] = {
    "frugt & grønt": frozenset({VEG, FRUIT, HERB}),
    "frugt og grønt": frozenset({VEG, FRUIT, HERB}),
    "kød": frozenset({MEAT, POULTRY, SAUSAGE, BACON}),
    "fisk": frozenset({FISH}),
    "mejeri": frozenset({DAIRY, CHEESE, EGG}),
    "brød": frozenset({BREAD}),
    "frost": frozenset({FROZEN, MEAT, POULTRY, FISH, BREAD}),
    "kolonial": frozenset({PASTA, CANNED, SAUCE, STOCK, SPICE, BAKING, NUTS, OIL, CEREAL}),
}

# ------------------------------------------------------------------ the shop's categories

# REMA 1000's departments and categories, matched by the words in them (their exact
# names change now and then). First match wins; a product's kinds come from the
# category when one matches, else from the department.
_CATEGORY_RULES: tuple[tuple[tuple[str, ...], frozenset[str]], ...] = (
    # ready and non-food first: they must never pass as an ingredient
    (("køkkenredskab", "husholdning", "rengøring", "vask", "toilet", "papir", "el", "cigaret", "tobak"), frozenset({NONFOOD})),
    (("brød", "rugbrød", "boller", "bavinchi", "bager"), frozenset({BREAD})),
    (("marmelade", "honning", "pålægschokolade"), frozenset({SAUCE, SNACK})),
    (("chips", "snack", "slik", "chokolade", "kiks", "kage", "dessert", "is"), frozenset({SNACK})),
    (("sodavand", "juice", "vand", "øl", "vin", "kaffe", "the", "drikke", "smoothie", "shots", "saft"), frozenset({DRINK})),
    (("færdigret", "pizza", "sandwich", "wrap", "burger", "salatbar", "måltidssalat", "pastasalat", "nudelsalat", "ready to cook", "suppe"), frozenset({READY})),
    # cold counter
    (("pålæg", "delikatesse", "postej", "pate", "paté"), frozenset({COLD_CUTS})),
    (("pølse",), frozenset({SAUSAGE})),
    (("bacon",), frozenset({BACON})),
    (("dej",), frozenset({BAKING})),
    (("dressing", "sauce", "saucer", "ketchup", "sennep", "mayonnaise", "remoulade"), frozenset({SAUCE})),
    (("fiskekonserves",), frozenset({FISH, CANNED})),
    (("fisk", "sild", "skaldyr", "laks", "rejer", "tun"), frozenset({FISH})),
    (("kylling", "kalkun", "and"), frozenset({POULTRY})),
    (("hakket", "fjerkræ"), frozenset({MEAT, POULTRY})),
    (("okse", "svin", "gris", "lam", "kalv", "kød", "bøf", "steg", "kotelet", "mørbrad", "fars"), frozenset({MEAT})),
    # dairy
    (("æg",), frozenset({EGG})),
    (("ost", "smøreost", "hytteost", "madlavningsost", "skæreost", "specialost", "skiveost", "skiveskåret"), frozenset({CHEESE})),
    (("mælk", "fløde", "yoghurt", "skyr", "smør", "margarine", "creme", "kvark", "mejeri", "syrnede"), frozenset({DAIRY})),
    # fruit & vegetables
    (("krydderurt", "smagsforstærker"), frozenset({HERB, VEG})),
    (("pære", "æble", "banan", "citrus", "frugt", "bær", "melon", "drue"), frozenset({FRUIT, VEG})),
    (("kartof", "løg", "kål", "agurk", "tomat", "peberfrugt", "grønt", "salat", "avocado", "svampe", "rodfrugt"), frozenset({VEG, HERB})),
    # frozen
    (("frost",), frozenset({FROZEN})),
    # dry goods
    (("konserves", "survarer", "dåse"), frozenset({CANNED})),
    (("ris", "pasta", "nudler"), frozenset({PASTA})),
    (("nem mad",), frozenset({SAUCE, STOCK, READY})),
    (("krydderi",), frozenset({SPICE, STOCK})),
    (("mel", "sukker", "bagning", "bage"), frozenset({BAKING})),
    (("nødder", "tørret frugt", "kerner", "frø"), frozenset({NUTS})),
    (("olie", "eddike"), frozenset({OIL})),
    (("morgenmad", "müsli", "gryn", "cornflakes"), frozenset({CEREAL})),
    (("asiatisk", "mexicansk", "verdens", "international", "tex mex", "texmex"), frozenset({SAUCE, CANNED, PASTA, SPICE, BREAD})),
)  # fmt: skip

_DEPARTMENT_RULES: tuple[tuple[tuple[str, ...], frozenset[str]], ...] = (
    (("husholdning", "personlig", "pleje", "baby", "kiosk", "dyr", "blomster", "tobak", "apotek"), frozenset({NONFOOD})),
    (("slik", "snack", "chips"), frozenset({SNACK})),
    (("drikke",), frozenset({DRINK})),
    (("frugt", "grønt"), frozenset({VEG, FRUIT, HERB})),
    (("kød", "fisk", "fjerkræ", "slagter"), frozenset({MEAT, POULTRY, FISH, SAUSAGE, BACON})),
    (("ost",), frozenset({CHEESE})),
    (("mejeri",), frozenset({DAIRY, CHEESE, EGG})),
    (("brød", "bavinchi"), frozenset({BREAD})),
    (("frost",), frozenset({FROZEN, MEAT, POULTRY, FISH, READY, SNACK, BREAD})),
    (("køl",), frozenset({COLD_CUTS, SAUSAGE, BACON, SAUCE, FISH, BAKING, READY, PASTA, MEAT})),
    (("nemt", "hurtigt"), frozenset({VEG, FRUIT, READY, COLD_CUTS})),
    (("kolonial",), frozenset({PASTA, CANNED, SAUCE, STOCK, SPICE, BAKING, NUTS, OIL, CEREAL, SNACK, DRINK})),
)  # fmt: skip


def _match_rules(
    text: str, rules: tuple[tuple[tuple[str, ...], frozenset[str]], ...]
) -> frozenset[str] | None:
    """The kinds of the first rule a word of which starts a word of the text.

    A short word must be the whole word ("is" is not "ris"); a longer one may start
    a longer word ("kartof" is "kartofler", "pålæg" is "pålægs").
    """
    low = text.lower()
    for words, kinds in rules:
        for w in words:
            pattern = rf"\b{re.escape(w)}" + (r"\b" if len(w) <= 3 else "")
            if re.search(pattern, low):
                return kinds
    return None


def product_kinds(
    department: str | None, category: str | None, name: str = "", underline: str | None = None
) -> frozenset[str] | None:
    """What a product is, from the shop's category (None when the shop says nothing).

    The category decides; the department only narrows or stands in for it. A few
    words in the name settle what a category leaves open (a "Saucer & nem mad"
    product called bouillon is stock, one called nudler is an instant meal), and in
    the freezer everything is frozen.
    """
    kinds = _match_rules(category, _CATEGORY_RULES) if category else None
    by_department = _match_rules(department, _DEPARTMENT_RULES) if department else None
    if by_department and NONFOOD in by_department:
        return frozenset({NONFOOD})
    if kinds is None and by_department and by_department <= NEVER_KINDS:
        kinds = by_department  # the sweets or drinks aisle says enough on its own
    if kinds is None:
        # No category: the department alone is too coarse to rule food out
        # (a shop's "Kolonial" holds both pasta and the odd fresh garlic).
        return None
    words = set(_tokens(f"{name} {underline or ''}"))
    if kinds & {SAUCE, STOCK, READY}:
        if any(w.endswith(("bouillon", "bouillonterninger", "fond")) for w in words):
            kinds = frozenset({STOCK})
        elif any(w.endswith("nudler") or w in {"cupnudler", "kopnudler", "instant"} for w in words):
            kinds = frozenset({READY})
    if by_department and FROZEN in by_department:
        kinds = _frozen_kinds(kinds, words)
    return kinds


_FROZEN_POULTRY = ("kylling", "kalkun", "hønse", "ande")
_FROZEN_FISH = (
    "laks",
    "torsk",
    "reje",
    "fisk",
    "sej",
    "rødspætte",
    "kuller",
    "hoki",
    "tun",
    "musling",
)
_FROZEN_MEAT = (
    "hakket",
    "okse",
    "svine",
    "grise",
    "frikadell",
    "bøf",
    "kødboll",
    "medister",
    "kalve",
    "lamme",
    "flæsk",
)


def _frozen_kinds(kinds: frozenset[str], words: set[str]) -> frozenset[str]:
    """What a product in the freezer is: meat and fish are that too, frozen."""
    if any(w.startswith(_FROZEN_POULTRY) for w in words):
        return frozenset({POULTRY, FROZEN})
    if any(w.startswith(_FROZEN_FISH) or w.endswith("fisk") for w in words):
        return frozenset({FISH, FROZEN})
    if any(w.startswith(_FROZEN_MEAT) for w in words):
        return frozenset({MEAT, FROZEN})
    if kinds & {READY, SNACK, BREAD}:
        return kinds
    return (kinds - {MEAT, POULTRY, FISH, SAUSAGE, BACON, COLD_CUTS}) | {FROZEN}


# ------------------------------------------------------------------ the catalogue


@dataclass(frozen=True)
class Entry:
    """A common ingredient: how it is written, and what the shop sells as it."""

    key: str  # the canonical name, as REMA would search it
    kinds: frozenset[str]
    aliases: tuple[str, ...] = ()
    query: str | None = None  # a better search term than the key
    piece_g: int | None = None  # what one piece weighs (for "2 stk" of a bagged thing)
    fresh: bool = False  # fruit & vegetables: fresh unless the line says frozen
    canned: bool = False  # always a can or a jar
    dried: bool = False  # a dried spice unless the line says fresh
    not_words: tuple[str, ...] = ()  # words in a product name that make it another thing
    ok_words: tuple[str, ...] = ()  # words that usually mean another thing, but not here


def _e(key: str, kinds: str | tuple[str, ...], *aliases: str, **extra: Any) -> Entry:
    kind_set = frozenset({kinds} if isinstance(kinds, str) else kinds)
    return Entry(key=key, kinds=kind_set, aliases=aliases, **extra)


# fmt: off
_ENTRIES: tuple[Entry, ...] = (
    # --- vegetables (fresh)
    _e("løg", VEG, "gule løg", "zittauerløg", "stort løg", "store løg", "små løg", piece_g=120, fresh=True,
       not_words=("skalotte", "forårs", "perle", "rød", "hvid", "syltede", "ristede", "stegte")),
    _e("rødløg", VEG, "rødt løg", "røde løg", piece_g=100, fresh=True),
    _e("skalotteløg", VEG, "skalotte", piece_g=30, fresh=True),
    _e("forårsløg", VEG, "springløg", piece_g=15, fresh=True),
    _e("hvidløg", VEG, "hvidløgsfed", piece_g=50, fresh=True, not_words=("pulver", "flager", "syltet", "marineret", "smør")),
    _e("porre", VEG, "porrer", piece_g=200, fresh=True),
    _e("gulerødder", VEG, "gulerod", "gulerødder", piece_g=90, fresh=True, not_words=("juice", "saft", "chips")),
    _e("kartofler", VEG, "kartoffel", "bagekartofler", "små kartofler", "nye kartofler", "skrællekartofler", piece_g=110, fresh=True,
       not_words=("chips", "mos", "pulver", "søde", "salat")),
    _e("søde kartofler", VEG, "sød kartoffel", "batat", piece_g=300, fresh=True),
    _e("broccoli", VEG, piece_g=400, fresh=True),
    _e("blomkål", VEG, piece_g=800, fresh=True),
    _e("spidskål", VEG, piece_g=700, fresh=True),
    _e("hvidkål", VEG, piece_g=1000, fresh=True),
    _e("rødkål", VEG, piece_g=1000, fresh=True, not_words=("glas", "konserves", "syltet")),
    _e("grønkål", VEG, piece_g=250, fresh=True),
    _e("spinat", VEG, "babyspinat", "baby spinat", "frisk spinat", fresh=True),
    _e("salat", VEG, "salathoved", "icebergsalat", "hjertesalat", "romainesalat", "grøn salat", piece_g=300, fresh=True,
       not_words=("pålæg", "karry", "kylling", "tun", "rejer", "pasta", "kartoffel", "dressing", "ost")),
    _e("agurk", VEG, "agurker", piece_g=350, fresh=True, not_words=("syltede", "asier", "drue")),
    _e("tomater", VEG, "tomat", "friske tomater", piece_g=100, fresh=True,
       not_words=("hakkede", "flåede", "puré", "pure", "ketchup", "suppe", "soltørrede", "passata", "sauce", "pesto", "chips")),
    _e("cherrytomater", VEG, "cherry tomater", "små tomater", "blommetomater", piece_g=15, fresh=True),
    _e("peberfrugt", VEG, "rød peberfrugt", "grøn peberfrugt", "gul peberfrugt", "peberfrugter", "peber frugt", query="peber", piece_g=180, fresh=True,
       not_words=("strimler", "grillede", "syltede", "pulver", "snack", "fyldte")),
    _e("squash", VEG, "zucchini", "courgette", piece_g=300, fresh=True),
    _e("aubergine", VEG, piece_g=350, fresh=True),
    _e("champignon", VEG, "champignoner", "svampe", piece_g=20, fresh=True, not_words=("dåse", "konserves", "suppe")),
    _e("majs", (VEG, CANNED), "majskolber", "sukkermajs", not_words=("chips", "popcorn", "mel", "baby")),
    _e("ærter", (VEG, FROZEN, CANNED), "grønne ærter", not_words=("gule", "suppe")),
    _e("grønne bønner", (VEG, FROZEN), "haricots verts", "bønner grønne", "bønner", "friske bønner", fresh=True,
       not_words=("kidney", "sorte", "hvide", "baked", "kaffe", "druer", "soja", "edamame", "brune")),
    _e("avocado", VEG, "avocadoer", piece_g=170, fresh=True),
    _e("selleri", VEG, "bladselleri", "knoldselleri", piece_g=500, fresh=True),
    _e("ingefær", VEG, "frisk ingefær", "ingefærrod", piece_g=60, fresh=True, not_words=("stødt", "pulver", "syltet", "øl", "the", "shot")),
    _e("chili", VEG, "rød chili", "frisk chili", "chilier", "grøn chili", piece_g=15, fresh=True,
       not_words=("stødt", "flager", "pulver", "sauce", "con", "olie", "mayo", "nødder", "chips", "ketchup", "pasta"), ok_words=("mix",)),
    _e("citrongræs", VEG, "lemongrass", piece_g=20, fresh=True),
    _e("fennikel", VEG, piece_g=300, fresh=True),
    _e("pastinak", VEG, "pastinakker", piece_g=120, fresh=True),
    _e("rødbeder", VEG, "rødbede", piece_g=150, fresh=True, not_words=("syltede", "glas", "konserves")),
    _e("asparges", VEG, "grønne asparges", piece_g=20, fresh=True, not_words=("hvide", "glas", "dåse")),
    _e("majroer", VEG, piece_g=150, fresh=True),
    # --- fruit
    _e("citron", FRUIT, "citroner", "økocitron", piece_g=100, fresh=True, not_words=("saft", "syre", "peber", "melisse")),
    _e("lime", FRUIT, "limefrugt", "øko lime", piece_g=70, fresh=True, not_words=("saft", "juice")),
    _e("æbler", FRUIT, "æble", piece_g=150, fresh=True, not_words=("most", "juice", "mos", "eddike", "chips", "kage")),
    _e("bananer", FRUIT, "banan", piece_g=120, fresh=True),
    _e("appelsin", FRUIT, "appelsiner", piece_g=200, fresh=True, not_words=("saft", "juice")),
    _e("pærer", FRUIT, "pære", piece_g=170, fresh=True),
    _e("mango", FRUIT, piece_g=400, fresh=True, not_words=("chutney", "dressing", "juice", "tørret")),
    _e("granatæble", FRUIT, "granatæblekerner", piece_g=300, fresh=True),
    # --- fresh herbs (a pot or a bunch)
    _e("persille", HERB, "bredbladet persille", "kruspersille", "frisk persille"),
    _e("basilikum", HERB, "frisk basilikum"),
    _e("koriander", HERB, "frisk koriander", not_words=("stødt", "frø")),
    _e("timian", HERB, "frisk timian"),
    _e("rosmarin", HERB, "frisk rosmarin"),
    _e("dild", HERB, "frisk dild"),
    _e("purløg", HERB, "frisk purløg"),
    _e("mynte", HERB, "frisk mynte", not_words=("the", "chokolade")),
    _e("oregano", (HERB, SPICE), "frisk oregano"),
    _e("salvie", HERB),
    _e("estragon", HERB),
    # --- meat
    _e("hakket oksekød", MEAT, "oksefars", "hakket okse", "oksekød hakket", "hakket oksekød 8-12%", "hakket oksekød 4-7%"),
    _e("hakket svinekød", MEAT, "svinefars", "grisefars", "hakket gris", "hakket svin", "hakket grisekød", query="hakket grisekød"),
    _e("hakket kalv og flæsk", MEAT, "kalv og flæsk", "hakket kalv & flæsk", "hakket gris og kalv", "hakket kalv"),
    _e("hakket kylling", POULTRY, "kyllingefars", "hakket kyllingekød"),
    _e("hakket kalkun", POULTRY, "kalkunfars"),
    _e("hakket lam", MEAT, "lammefars"),
    _e("oksekød", MEAT, "oksekød i strimler", "oksekød i tern", "oksekød til gryderet", "gullasch", "okse", "bøf", "oksebøf",
       not_words=("hakket", "fars", "nudler", "cup", "bouillon", "pålæg", "spegepølse", "suppe", "fond")),
    _e("entrecote", MEAT, "entrecotes", "entrecôte", "ribeye"),
    _e("oksemørbrad", MEAT),
    _e("svinemørbrad", MEAT, "mørbrad gris", "mørbrad af gris"),
    _e("svinekoteletter", MEAT, "svinekotelet", "koteletter", "kotelet"),
    _e("nakkekoteletter", MEAT, "nakkekotelet", "koteletter af nakke"),
    _e("nakkefilet", MEAT, "nakke", "svinenakke"),
    _e("flæskesteg", MEAT, "svinesteg", "kamsteg"),
    _e("svinekød", MEAT, "svinekød i strimler", "svinekød i tern", "skinkekød", "skinkeschnitzel", "svinefilet",
       not_words=("hakket", "fars", "pålæg", "pølse", "bacon")),
    _e("lammekød", MEAT, "lam", "lammekølle", "lammesteg"),
    _e("kalvekød", MEAT, "kalv"),
    _e("kødboller", (MEAT, READY), "frikadeller", "medister", "medisterpølse"),
    # --- poultry
    _e("kyllingebryst", POULTRY, "kyllingebrystfilet", "kyllingefilet", "kyllingebryster", "kyllingebryst i tern", "kyllingebryst i strimler",
       not_words=("pålæg", "nudler", "cup", "salat", "sandwich", "wrap", "bouillon", "pulver", "pølse", "suppe", "bbq", "marineret", "stegt", "honning")),
    _e("kyllingelår", POULTRY, "kyllingeoverlår", "kyllingeunderlår", "kyllinge lår", "hele kyllingelår", piece_g=250,
       not_words=("bbq", "marineret", "pålæg", "ovnklar", "krydret", "krydrede")),
    _e("hel kylling", POULTRY, "kylling hel", "kylling", piece_g=1200,
       not_words=("pålæg", "nudler", "cup", "salat", "sandwich", "wrap", "bouillon", "pulver", "pølse", "suppe", "bryst", "lår", "vinger", "ovnklar", "krydret", "krydrede", "marineret")),
    _e("kyllingevinger", POULTRY, "vinger"),
    _e("kalkun", POULTRY, "kalkunbryst", "kalkunkød", "kalkunfilet", "stegt kalkunkød", "kalkun i tern", not_words=("pålæg", "bacon", "pølse")),
    _e("and", POULTRY, "andebryst", "andelår"),
    # --- fish
    _e("laks", FISH, "laksefilet", "laksefileter", "laksestykker", "fersk laks", not_words=("røget", "pålæg", "gravad", "rogn", "salat", "indbagt", "kattefoder", "fars", "citron")),
    _e("torsk", FISH, "torskefilet", "torskeloin", "torskefileter", not_words=("fars", "rogn", "lever", "foder", "røget", "kattemad")),
    _e("rejer", FISH, "tigerrejer", "kæmperejer", "vannamei rejer", not_words=("salat", "chips", "lage", "kattemad", "oste", "paneret")),
    _e("tun", (FISH, CANNED), "tun på dåse", "dåsetun", "tunfisk", not_words=("salat", "pålæg")),
    _e("fiskefilet", FISH, "fiskefileter", "hvid fisk", "sej", "kuller", "rødspætte", "rødspættefilet"),
    _e("muslinger", FISH, "blåmuslinger"),
    _e("fiskefrikadeller", (FISH, READY)),
    # --- sausage, bacon, cold cuts
    _e("pølser", SAUSAGE, "pølse", "kyllingepølser", "kyllinge pølser", "frankfurter", "hotdogpølser", "grillpølser", "wienerpølser", "bratwurst"),
    _e("chorizo", (SAUSAGE, COLD_CUTS), "chorizopølse", "chorizo pølse"),
    _e("salami", (SAUSAGE, COLD_CUTS)),
    _e("bacon", BACON, "bacon i skiver", "bacon i tern", "baconstykker", "baconskiver"),
    _e("skinke", (COLD_CUTS, MEAT, BACON), "kogt skinke", "skinke i tern", "skinke i strimler", "serranoskinke", "parmaskinke"),
    # --- dairy
    _e("letmælk", DAIRY, "mælk", "letmælk 1,5%"),
    _e("sødmælk", DAIRY, "sødmælk 3,5%"),
    _e("skummetmælk", DAIRY, "minimælk"),
    _e("kærnemælk", DAIRY),
    _e("piskefløde", DAIRY, "fløde", "fløde 38%", "piskefløde 38%", "piskefløde 36%", "fløde 36%"),
    _e("madlavningsfløde", DAIRY, "fløde 18%", "madlavningsfløde 18%", "madlavningsfløde 15%", "fløde 15%", "fløde 13%", "fløde 9%"),
    _e("creme fraiche", DAIRY, "cremefraiche", "crème fraîche", "creme fraiche 18%", "creme fraiche 38%", "creme fraiche 9%"),
    _e("yoghurt", DAIRY, "yoghurt naturel", "græsk yoghurt", "tyrkisk yoghurt", "yoghurt 10%"),
    _e("skyr", DAIRY, "skyr naturel"),
    _e("kvark", DAIRY, "fromage frais"),
    _e("hytteost", (DAIRY, CHEESE)),
    _e("smør", DAIRY, "blødt smør", "smør til stegning", "usaltet smør", not_words=("jordnødde", "kærgården", "blandings", "hvidløg", "krydder")),
    _e("kokosmælk", CANNED, "kokosmelk", "kokosnøddemælk", not_words=("light", "drik")),
    # --- cheese
    _e("ost", CHEESE, "revet ost", "skiveost", "ost i skiver", "hård ost", "revet hård ost", "danbo", "skæreost",
       not_words=("blåhvid", "blå", "skimmel", "brie", "camembert", "gede", "feta", "mozzarella", "parmesan", "smøre", "fløde", "hytte", "snack", "kiks", "chips")),
    _e("parmesan", CHEESE, "parmesanost", "parmigiano", "grana padano", "revet parmesan"),
    _e("mozzarella", CHEESE, "mozzarellaost", "revet mozzarella", "mozzarella i tern"),
    _e("feta", CHEESE, "fetaost", "salatost", "feta i tern"),
    _e("cheddar", CHEESE, "revet cheddar"),
    _e("flødeost", CHEESE, "philadelphia"),
    _e("gedeost", CHEESE),
    _e("brie", CHEESE),
    # --- eggs
    _e("æg", EGG, "skrabeæg", "frilandsæg", "økologiske æg", "store æg", "æg str. m", not_words=("pasta", "nudler", "kage", "salat", "flødekage", "ægge", "sandwich")),
    # --- bread
    _e("rugbrød", BREAD, "rugbrødsskiver"),
    _e("brød", BREAD, "franskbrød", "flutes", "baguette", "toastbrød", "surdejsbrød"),
    _e("boller", BREAD, "burgerboller", "briocheboller", "grovboller", not_words=("kød", "fiske", "fars", "karry", "lakrids")),
    _e("pitabrød", BREAD, "pita", "fladbrød"),
    _e("tortilla", BREAD, "tortillas", "tortillabrød", "wraps", "madpandekager", not_words=("chips", "dip")),
    _e("tacoskaller", BREAD, "taco skaller", "tacos", not_words=("sauce", "krydderi", "mix")),
    _e("naanbrød", BREAD, "naan"),
    # --- pasta, rice, noodles
    _e("pasta", PASTA, "pastaskruer", "penne", "fusilli", "farfalle", "pastaskaller", "tagliatelle", "fettuccine", "linguine", "makaroni",
       not_words=("sauce", "salat", "pesto", "ret", "færdig", "karry", "sovs", "frisk", "fyldt")),
    _e("spaghetti", PASTA, "spaghettini", not_words=("sauce", "salat", "ret", "sovs", "dåse")),
    _e("lasagneplader", PASTA, "lasagne plader", "lasagneark", not_words=("færdig", "sauce", "sovs", "ret")),
    _e("ris", PASTA, "jasminris", "basmatiris", "grødris", "langkornede ris", "løse ris", "kogte ris", "parboiled ris",
       not_words=("riskager", "risengrød", "nudler", "papir", "chips", "mel", "kiks", "vin", "eddike", "drik", "budding")),
    _e("risnudler", PASTA, "glasnudler"),
    _e("nudler", PASTA, "ægnudler", "æggenudler", "fuldkornsnudler", "woknudler", "ramen nudler", "udon",
       not_words=("cup", "kop", "instant", "smag", "kylling", "oksesmag", "kyllingsmag", "ret")),
    _e("couscous", PASTA, "cous cous"),
    _e("bulgur", PASTA),
    _e("quinoa", PASTA),
    _e("risotto ris", PASTA, "risottoris", "arborio", "risotto"),
    # --- cans and jars
    _e("hakkede tomater", CANNED, "hakket tomat", "tomater hakkede", "dåsetomater", "tomater på dåse", "knuste tomater", canned=True,
       not_words=("suppe", "soltørrede", "frisk")),
    _e("flåede tomater", CANNED, "tomater flåede", "hele tomater", "flåede", canned=True, not_words=("suppe",)),
    _e("passata", (CANNED, SAUCE), "tomatpassata", "passata di pomodoro", "pureret tomat", canned=True),
    _e("tomatpuré", (CANNED, SAUCE), "tomatpure", "tomatkoncentrat", "koncentreret tomatpuré", canned=True),
    _e("soltørrede tomater", CANNED, "soltørret tomat", canned=True),
    _e("kidneybønner", CANNED, "kidney bønner", "røde bønner", "røde kidneybønner", canned=True),
    _e("sorte bønner", CANNED, canned=True),
    _e("hvide bønner", CANNED, "cannellini", "cannellinibønner", "butterbeans", canned=True),
    _e("kikærter", CANNED, "kikærter på dåse", canned=True, not_words=("mel", "snack", "ristede")),
    _e("linser", (CANNED, PASTA), "røde linser", "grønne linser", "brune linser", not_words=("suppe", "chips")),
    _e("oliven", CANNED, "sorte oliven", "grønne oliven", canned=True, not_words=("olie", "tapenade", "brød")),
    _e("kapers", CANNED, canned=True),
    _e("ananas", (FRUIT, CANNED), "ananas på dåse", "ananasringe", not_words=("juice", "saft", "brus")),
    _e("artiskok", CANNED, "artiskokker", "artiskokhjerter", canned=True),
    _e("baked beans", CANNED, canned=True),
    # --- sauces and condiments
    _e("sojasauce", SAUCE, "soja", "soya", "sojasovs", "soy sauce", "soja sauce", "tamari", not_words=("bønner", "mælk", "drik", "olie", "mel")),
    _e("fiskesauce", SAUCE, "fishsauce", "fish sauce", "fiskesovs", "nam pla", not_words=("bearnaise", "hollandaise", "pasta")),
    _e("østerssauce", SAUCE, "oyster sauce", "østers sauce"),
    _e("sweet chili sauce", SAUCE, "sød chilisauce", "sweet chilli", "chilisauce", "sriracha", "hot sauce", "chili sauce"),
    _e("ketchup", SAUCE, "tomatketchup"),
    _e("sennep", SAUCE, "dijonsennep", "grov sennep", "dijon"),
    _e("mayonnaise", SAUCE, "mayo"),
    _e("remoulade", SAUCE),
    _e("pesto", SAUCE, "grøn pesto", "rød pesto", "basilikumpesto"),
    _e("karrypasta", SAUCE, "rød karrypasta", "grøn karrypasta", "gul karrypasta", "curry paste", "karry pasta"),
    _e("pastasauce", SAUCE, "pastasovs", "tomatsauce", "tomatsovs", "dolmio", "pasta sauce"),
    _e("bearnaise", SAUCE, "bearnaisesauce", "bearnaise sauce"),
    _e("hoisin", SAUCE, "hoisinsauce"),
    _e("teriyaki", SAUCE, "teriyakisauce"),
    _e("tahin", SAUCE, "tahini", "sesampasta"),
    _e("peanutbutter", SAUCE, "peanut butter", "jordnøddesmør"),
    _e("honning", (SAUCE, SNACK), "flydende honning", not_words=("melon", "ristede", "mælkesnitte", "nødder", "mandler", "cashew")),
    _e("ahornsirup", SAUCE, "maple syrup", "sirup"),
    # --- stock
    _e("bouillon", STOCK, "bouillonterning", "bouillonterninger", "fond", "suppeterning"),
    _e("hønsebouillon", STOCK, "kyllingebouillon", "hønsefond", "kyllingefond", "hønsebouillon terninger"),
    _e("oksebouillon", STOCK, "oksefond", "oksebouillon terninger"),
    _e("grøntsagsbouillon", STOCK, "grønsagsbouillon", "grøntsagsfond", "grøntsagsbouillon terninger"),
    _e("fiskebouillon", STOCK, "fiskefond"),
    # --- dried spices
    _e("karry", SPICE, "karrypulver", "karry pulver", "curry", "madras karry", dried=True, not_words=("sild", "salat", "sauce", "pasta", "suppe", "dressing", "boller", "ret"), ok_words=("pulver",)),
    _e("paprika", SPICE, "paprikapulver", "røget paprika", "paprika pulver", dried=True, not_words=("chips", "frugt", "sauce", "pasta")),
    _e("spidskommen", SPICE, "kummin", "cumin", "stødt spidskommen", dried=True),
    _e("gurkemeje", SPICE, "stødt gurkemeje", "turmeric", dried=True),
    _e("kanel", SPICE, "stødt kanel", "kanelstang", "kanelstænger", dried=True, not_words=("snegle", "gifler", "kage")),
    _e("chiliflager", SPICE, "chili flager", "tørret chili", "chilipulver", "stødt chili", "cayenne", "cayennepeber", query="chili", dried=True,
       not_words=("sauce", "con", "olie", "mayo", "nødder", "chips", "ketchup", "pasta", "cheese", "mix")),
    _e("peber", SPICE, "sort peber", "friskkværnet peber", "peberkorn", "hvid peber", dried=True, not_words=("frugt", "rod", "mynte", "citron", "sild", "sauce", "nødder")),
    _e("salt", SPICE, "flagesalt", "havsalt", "groft salt", "fint salt", dried=True, not_words=("lakrids", "nødder", "kiks", "stænger", "peanuts", "kød")),
    _e("tørret oregano", SPICE, "oregano tørret", "oregano, tørret", query="oregano", dried=True),
    _e("tørret timian", SPICE, "timian tørret", query="timian", dried=True),
    _e("tørret basilikum", SPICE, "basilikum tørret", query="basilikum", dried=True),
    _e("tørret rosmarin", SPICE, "rosmarin tørret", query="rosmarin", dried=True),
    _e("tørret persille", SPICE, "persille tørret", query="persille", dried=True),
    _e("laurbærblade", SPICE, "laurbær", "laurbærblad", dried=True),
    _e("koriander frø", SPICE, "stødt koriander", "korianderfrø", query="koriander", dried=True),
    _e("ingefær pulver", SPICE, "stødt ingefær", "tørret ingefær", query="ingefær", dried=True, ok_words=("pulver",)),
    _e("hvidløgspulver", SPICE, "hvidløgs pulver", "tørret hvidløg", "granuleret hvidløg", query="hvidløg", dried=True, ok_words=("pulver", "granuleret")),
    _e("løgpulver", SPICE, dried=True, ok_words=("pulver",)),
    _e("garam masala", SPICE, dried=True),
    _e("tacokrydderi", SPICE, "taco krydderi", "taco mix", "tacomix", "fajita krydderi", dried=True),
    _e("muskatnød", SPICE, "muskat", "stødt muskat", dried=True),
    _e("kardemomme", SPICE, dried=True),
    _e("nelliker", SPICE, "stødt nellike", dried=True),
    _e("sesamfrø", (NUTS, SPICE), "sesam", "ristede sesamfrø", not_words=("olie", "knækbrød", "kiks")),
    _e("vaniljesukker", BAKING, "vanilje", "vaniljeekstrakt", "vanillesukker", dried=True),
    # --- baking
    _e("hvedemel", BAKING, "mel", "fuldkornshvedemel", not_words=("kikærte", "mandel", "kartoffel", "majs", "ris", "rug", "bage", "mix")),
    _e("rugmel", BAKING),
    _e("maizena", BAKING, "majsstivelse", "kartoffelmel"),
    _e("sukker", BAKING, "rørsukker", "brun farin", "farin", "hvidt sukker", "flormelis", not_words=("fri", "frit", "ærter", "nul", "erstatning", "kiks", "slik")),
    _e("gær", BAKING, "frisk gær", "tørgær"),
    _e("bagepulver", BAKING, "natron", ok_words=("pulver",)),
    _e("rasp", BAKING, "panko", "pankorasp", "brødkrummer"),
    _e("havregryn", CEREAL, "havre gryn", "grovvalsede havregryn", "finvalsede havregryn", not_words=("drik", "mælk", "kiks", "bar")),
    _e("tærtedej", BAKING, "butterdej", "mørdej", "pizzadej", "dej"),
    _e("chokolade", (BAKING, SNACK), "mørk chokolade", "kogechokolade", "bagechokolade", "chokoladeknapper"),
    _e("kakao", BAKING, "kakaopulver", ok_words=("pulver",)),
    # --- nuts and seeds
    _e("peanuts", (NUTS, SNACK), "saltede peanuts", "jordnødder", "ristede peanuts", not_words=("bar", "smør", "butter", "chokolade", "choco", "dadler", "daddelbar", "ketchup", "cookies", "rings", "ritter", "jalapeno")),
    _e("mandler", (NUTS, SNACK), "mandel", "smuttede mandler", "mandelflager", "hakkede mandler",
       not_words=("mælk", "drik", "mel", "chokolade", "choko", "bar", "kage", "marcipan", "oliven", "røgsmag", "is", "ritter", "saltede", "ristede", "røgede")),
    _e("cashewnødder", (NUTS, SNACK), "cashew", "cashews", not_words=("chokolade", "choko", "saltede", "ristede", "røgede")),
    _e("valnødder", NUTS, "valnød"),
    _e("hasselnødder", NUTS, "hasselnød"),
    _e("pinjekerner", NUTS, "pinjekerne"),
    _e("solsikkekerner", NUTS, "solsikkefrø"),
    _e("græskarkerner", NUTS, "græskarfrø"),
    _e("rosiner", NUTS, "rosin"),
    _e("dadler", NUTS, "daddel", not_words=("bar", "chokolade")),
    _e("kokosmel", (NUTS, BAKING), "kokos", "revet kokos", "kokosflager"),
    # --- oil and vinegar
    _e("olivenolie", OIL, "oliven olie", "ekstra jomfru olivenolie", "jomfruolie", not_words=("chili", "hvidløg", "trøffel", "spray")),
    _e("olie", OIL, "rapsolie", "solsikkeolie", "madolie", "stegeolie", "olie til stegning", "neutral olie", "vindruekerneolie", not_words=("oliven", "sesam", "kokos", "fiske", "trøffel", "chili", "hvidløg", "spray", "motor")),
    _e("sesamolie", OIL, "sesam olie", "ristet sesamolie"),
    _e("kokosolie", OIL, "kokos olie"),
    _e("eddike", OIL, "lagereddike", "hvidvinseddike", "æbleeddike", "æblecidereddike", "balsamico", "balsamicoeddike", "rødvinseddike", "hvidvins eddike", "riseddike"),
    # --- frozen
    _e("frosne ærter", FROZEN, "frost ærter", "dybfrosne ærter"),
    _e("frossen spinat", FROZEN, "frost spinat", "hakket spinat frost", "dybfrost spinat"),
    _e("frosne bær", FROZEN, "frosne hindbær", "frosne blåbær", "frosne jordbær", "bærmix"),
    _e("wokmix", FROZEN, "wokgrøntsager", "wok grøntsager", "frosne wokgrøntsager"),
    _e("frosne grøntsager", FROZEN, "grøntsagsblanding", "grøntsagsmix", "frost grøntsager", "dybfrosne grøntsager"),
    _e("pommes frites", FROZEN, "fritter", "pomfritter"),
    # --- ready food, snacks and drinks: only when the list asks for them by name
    _e("pizza", (READY, FROZEN), "frysepizza", "frossen pizza", "pizzaer", "frostpizza", "pizza margherita", piece_g=500),
    _e("vaniljeis", (SNACK, FROZEN), "vanilla is", "vaniglia is", "vanilleis", "vanilje is", "vanilla ice cream", query="is"),
    _e("is", (SNACK, FROZEN), "flødeis", "isdessert", "ispinde", "sorbet", "softice"),
    _e("chips", SNACK, "kartoffelchips", "franske kartofler"),
    _e("popcorn", SNACK, "popkorn"),
    _e("slik", SNACK, "vingummi", "lakrids", "blandet slik"),
    _e("kage", SNACK, "kager", "småkager", "cookies", "kiks"),
    _e("sodavand", DRINK, "cola", "læskedrik", "danskvand"),
    _e("saftevand", DRINK, "saft", "squash saft"),
    _e("kaffe", DRINK, "kaffebønner", "filterkaffe", "instant kaffe"),
    _e("te", DRINK, "the", "teposer", "grøn te"),
    # --- drinks used in cooking
    _e("hvidvin", DRINK, "tør hvidvin", "hvidvin til madlavning"),
    _e("rødvin", DRINK, "rødvin til madlavning"),
    _e("øl", DRINK, "mørk øl", "pilsner"),
    _e("appelsinjuice", DRINK, "appelsin juice", "juice"),
    _e("æblejuice", DRINK, "æble juice", "æblemost"),
    _e("kokosvand", DRINK),
)
# fmt: on

CATALOG: dict[str, Entry] = {entry.key: entry for entry in _ENTRIES}
_ALIASES: dict[str, Entry] = {}
for _entry in _ENTRIES:
    _ALIASES.setdefault(_entry.key, _entry)
    for _alias in _entry.aliases:
        _ALIASES.setdefault(_alias, _entry)
# Longest aliases first, so "frisk basilikum" is tried before "basilikum".
_ALIAS_ORDER = sorted(_ALIASES, key=len, reverse=True)


def _normal(text: str) -> str:
    return " ".join(_tokens(text))


def lookup(text: str) -> Entry | None:
    """The catalogue entry an ingredient is written as ("2 fed hvidløg, pressede" -> hvidløg).

    The whole cleaned name first, then the longest alias it contains as whole
    words; a word of the name that is an entry on its own (its head) last.
    """
    name = _normal(ingredient_name(text))
    if not name:
        return None
    if name in _ALIASES:
        return _ALIASES[name]
    padded = f" {name} "
    for alias in _ALIAS_ORDER:
        if " " in alias and f" {_normal(alias)} " in padded:
            return _ALIASES[alias]
    words = name.split()
    # The thing a Danish phrase is about comes last ("grønne bønner", "hakket oksekød").
    for word in reversed(words):
        # "hønsebouillonterninger": the cubes of a stock the catalogue knows.
        stem = re.sub(r"terning(?:er)?$", "", word)
        if len(word) >= 2 and (found := _ALIASES.get(word) or _ALIASES.get(stem)):
            return found
    return next(
        (entry for word in reversed(words) if (entry := _compound_of(word)) is not None), None
    )


def _compound_of(word: str) -> Entry | None:
    """The entry a compound word ends in ("laksefilet" is laks), if it is not another thing."""
    for key in _ALIAS_ORDER:
        if " " not in key and len(key) > 3 and word.endswith(key) and len(word) > len(key):
            entry = _ALIASES[key]
            if not any(word.startswith(n) for n in entry.not_words):
                return entry
    return None


# ------------------------------------------------------------------ an ingredient line's spec

# A line that is not a thing to buy: a recipe's section heading or its equipment.
_EQUIPMENT = {
    "tærteform", "form", "fad", "ovnfast", "gryde", "pande", "wok", "skål", "bageplade", "bagepapir",
    "folie", "stanniol", "film", "frysepose", "kødnål", "grillspyd", "spyd", "sigte", "si", "pensel",
    "mandolinjern", "mandolin", "blender", "stavblender", "foodprocessor", "røremaskine", "piskeris",
    "stegetermometer", "termometer", "springform", "muffinform", "bradepande", "kagerulle",
}  # fmt: skip
_HEADING = re.compile(r"^\s*[^:]{1,40}:\s*$")  # "Dej:", "Fyld:", "Til servering:"
# A recipe's remark among its ingredients ("Server med ris", "Tip: brug gerne …"): not bought.
_REMARK_STARTS = {
    "server", "serveres", "serveret", "servér", "tip", "tips", "pynt", "pyntes", "drys", "kog",
    "steg", "bland", "rør", "hæld", "tilsæt", "smag", "bemærk", "obs", "note", "brug", "bruges",
    "kan", "lad", "skær", "vend", "bag", "anret", "husk", "spis", "spises", "nyd", "velbekomme",
}  # fmt: skip
# "Evt. chili", "gerne frisk": the thing comes after the hedge.
_HEDGES = {"evt", "eventuelt", "gerne", "valgfri", "valgfrit", "ekstra"}
# How a recipe counts a thing that is sold whole or in a bunch: how many of them a
# package gives (3 fed hvidløg is one bulb, 2 stængler citrongræs one pack).
COUNT_WORDS: dict[str, int] = {
    "fed": 10, "stængel": 6, "stængler": 6, "kvist": 10, "kviste": 10, "blad": 10, "blade": 10,
    "håndfuld": 2, "håndfulde": 2, "nip": 50, "knivspids": 50, "dusk": 2, "duske": 2, "stilk": 6,
    "stilke": 6, "skive": 8, "skiver": 8, "bundt": 1, "bundter": 1, "pose": 1, "poser": 1,
    "pakke": 1, "pakker": 1, "dåse": 1, "dåser": 1, "glas": 1, "potte": 1, "potter": 1,
    "bakke": 1, "bakker": 1, "flaske": 1, "flasker": 1,
}  # fmt: skip
_FORM_FROZEN = {"frost", "frossen", "frosne", "frosset", "dybfrost", "dybfrossen", "dybfrosne"}
_FORM_FRESH = {"frisk", "friske", "fersk", "ferske"}
_FORM_DRIED = {"tørret", "tørrede", "stødt", "pulver", "krydderi"}
_FORM_CANNED = {"dåse", "dåser", "konserves", "glas", "hakkede", "flåede", "knuste"}
_BOUILLON = re.compile(r"bouil[li]on|fond\b")


@dataclass
class Spec:
    """What a shopping line asks for, read from its words and the catalogue."""

    key: str  # the canonical ingredient, to merge lines and remember choices
    kinds: frozenset[str]  # what the product may be
    form: str  # fresh | frozen | canned | dried | any
    entry: Entry | None = None
    query: str = ""  # the best search term
    skip: str | None = None  # why this is not a thing to buy (heading, equipment, water)
    piece_g: int | None = None
    count_word: str | None = None  # "fed", "stængler": the amount counts parts of a package
    per_package: int = 1
    explicit: frozenset[str] = field(default_factory=frozenset)  # kinds the words themselves say
    asked: frozenset[str] = field(default_factory=frozenset)  # the line's own words


def spec_for(name: str, search: str | None = None, category: str | None = None) -> Spec:
    """Read a line ("3 fed hvidløg, pressede", search "hvidløg", category "Frugt & grønt")."""
    raw = str(name or "")
    if _HEADING.match(raw):
        return Spec(key=_normal(raw), kinds=frozenset(), form="any", skip="heading")
    cleaned = ingredient_name(raw)
    if is_tap_water(cleaned):
        return Spec(key="vand", kinds=frozenset(), form="any", skip="water")
    words = _tokens(cleaned)
    while len(words) > 1 and words[0] in _HEDGES:
        words = words[1:]
        cleaned = " ".join(cleaned.split()[1:])
    if len(words) > 1 and words[0] in _REMARK_STARTS:
        return Spec(key=_normal(cleaned), kinds=frozenset(), form="any", skip="remark")
    search_words = _tokens(ingredient_name(search or ""))
    all_words = set(words) | set(search_words)
    if words and (words[0] in _EQUIPMENT or _head(cleaned) in _EQUIPMENT):
        return Spec(key=_normal(cleaned), kinds=frozenset(), form="any", skip="equipment")
    entry = lookup(cleaned) or (lookup(search) if search else None)
    # The form the words say, which beats the catalogue's usual form.
    explicit: set[str] = set()
    form = "any"
    if all_words & _FORM_FROZEN:
        form, explicit = "frozen", {FROZEN}
    elif all_words & _FORM_CANNED or canned_tomatoes(cleaned):
        form, explicit = "canned", {CANNED}
    elif all_words & _FORM_DRIED:
        form, explicit = "dried", {SPICE}
    elif all_words & _FORM_FRESH:
        form = "fresh"
    if _BOUILLON.search(cleaned.lower()):
        explicit = {STOCK}
    kinds: frozenset[str]
    if entry is not None:
        kinds = entry.kinds
        if form == "any":
            form = (
                "fresh"
                if entry.fresh
                else "canned"
                if entry.canned
                else "dried"
                if entry.dried
                else "any"
            )
        elif form == "frozen" and kinds & {VEG, FRUIT}:
            kinds = kinds | {FROZEN}
        elif form == "dried" and kinds & {HERB}:
            kinds = frozenset({SPICE})
        elif form == "fresh" and kinds & {SPICE} and HERB in kinds:
            kinds = frozenset({HERB})
    else:
        kinds = LINE_CATEGORY_KINDS.get(str(category or "").strip().lower(), FOOD_KINDS)
        if form == "frozen":
            kinds = kinds | {FROZEN}
    if explicit:
        kinds = (kinds & frozenset(explicit)) or frozenset(explicit)
    # "3 fed hvidløg": fed is how it is counted, hvidløg what is bought (read from
    # the words as written: the cleaned name has lost the counting word).
    raw_words = _tokens(raw)
    count_word = next((w for w in raw_words[:-1] if w in COUNT_WORDS), None)
    per_package = COUNT_WORDS.get(count_word or "", 1)
    key = entry.key if entry else _key_of(cleaned)
    if canned_tomatoes(cleaned) and entry is not None and entry.kinds == frozenset({VEG}):
        entry, key = CATALOG["hakkede tomater"], "hakkede tomater"
    query = (entry.query or entry.key) if entry else ingredient_name(search or cleaned)
    return Spec(
        key=key,
        kinds=kinds,
        form=form,
        entry=entry,
        query=query,
        piece_g=entry.piece_g if entry else None,
        count_word=count_word,
        per_package=per_package,
        explicit=frozenset(explicit),
        asked=frozenset(all_words),
    )


def _head(cleaned: str) -> str | None:
    from .mealplan import head_word  # noqa: PLC0415 - mealplan imports this module

    return head_word(cleaned)


def _key_of(cleaned: str) -> str:
    """A key for an ingredient the catalogue doesn't know: its words, the thing last."""
    head = _head(cleaned)
    words = [w for w in _tokens(cleaned) if w not in COUNT_WORDS]
    return head or (" ".join(words) if words else _normal(cleaned))


def allowed(
    spec: Spec,
    department: str | None,
    category: str | None,
    name: str,
    underline: str | None = None,
) -> bool | None:
    """May a product be what the line asks for? None when the shop's category is unknown.

    A product of a kind the line can't be is out: an instant meal for noodles, a can
    of pepper strips for a fresh pepper, ground chili for a fresh one, grill skewers
    for anything to eat.
    """
    kinds = product_kinds(department, category, name, underline)
    if kinds is None:
        return None
    if not spec.kinds:
        return False
    if kinds & NEVER_KINDS and not spec.kinds & kinds:
        return False
    if FROZEN in kinds and FROZEN not in spec.kinds and spec.form in ("fresh", "canned", "dried"):
        return False
    return bool(kinds & spec.kinds)


def other_thing(spec: Spec, product_name: str) -> bool:
    """Is a product, by the catalogue's words, another thing than the line asks for?

    "SKALOTTELØG" for løg, "STØDT CHILI" for chili, "CUPNUDLER" for nudler.
    """
    if spec.entry is None:
        return False
    words = _tokens(product_name)
    for word in spec.entry.not_words:
        if any(w == word or w.startswith(word) or w.endswith(word) for w in words):
            # Unless the line asked for it ("stødt chili" is a spice line, not fresh,
            # "kokosmælk light" is the light one, "løg rødt" the red ones).
            if (
                word in _tokens(spec.key)
                or word in spec.query.lower()
                or any(asked.startswith(word) for asked in spec.asked)
            ):
                continue
            return True
    return False


_QUALIFIER = re.compile(r",| m/| med | i | u/| uden | på | til ", re.IGNORECASE)


def qualifier_only(product_name: str, word: str) -> bool:
    """Is the asked word only a qualifier in the product's name, not the thing itself?

    "DADDELBAR, PEANUTS" is not peanuts, "BOLLER I KARRY" not karry, "NUDLER
    M/KYLLINGSMAG" not kylling; "KARRY PULVER" and "BACON I SKIVER" are what they say.
    """
    parts = _QUALIFIER.split(f" {product_name} ", maxsplit=1)
    if len(parts) < 2:
        return False
    before, after = (set(_tokens(part)) for part in parts)

    def has(words: set[str]) -> bool:
        return any(
            w == word or (len(word) > 3 and (w.endswith(word) or w.startswith(word))) for w in words
        )

    return has(after) and not has(before)
