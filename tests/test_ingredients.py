"""The ingredient catalogue: what a line is, and what the shop may sell as it."""

from __future__ import annotations

from typing import Any

from custom_components.middagsro import mealplan as mp
from custom_components.middagsro.ingredients import (
    CANNED,
    FISH,
    FROZEN,
    FRUIT,
    HERB,
    MEAT,
    NONFOOD,
    POULTRY,
    READY,
    SPICE,
    STOCK,
    VEG,
    allowed,
    lookup,
    other_thing,
    product_kinds,
    qualifier_only,
    spec_for,
)

from .conftest import make_product


def test_lookup_reads_the_thing_from_its_words() -> None:
    """The catalogue entry a line is written as."""
    assert lookup("2 fed hvidløg, pressede").key == "hvidløg"
    assert lookup("Stort løg, i både").key == "løg"
    assert lookup("Løg").key == "løg"
    assert lookup("Rødløg").key == "rødløg"  # not løg: its own entry
    assert lookup("Laksefilet med skind").key == "laks"
    assert lookup("Hønsebouillonterninger").key == "hønsebouillon"
    assert lookup("Oksebouillonterning").key == "oksebouillon"
    assert lookup("Grønne bønner").key == "grønne bønner"
    assert lookup("Soja").key == "sojasauce"
    assert lookup("Fishsauce").key == "fiskesauce"
    assert lookup("Æg").key == "æg"
    assert lookup("Hakkede tomater på dåse").key == "hakkede tomater"
    assert lookup("Skalotteløg") is not None and lookup("Skalotteløg").key == "skalotteløg"
    assert lookup("Noget helt ukendt") is None
    assert lookup("") is None
    # A compound that begins with a word the entry rules out is not the entry.
    assert lookup("Hvidløgssmør") is None or lookup("Hvidløgssmør").key != "hvidløg"


def test_spec_reads_headings_equipment_water_and_remarks() -> None:
    """What is not a thing to buy."""
    assert spec_for("Dej:").skip == "heading"
    assert spec_for("Til servering:").skip == "heading"
    assert spec_for("Tærteform").skip == "equipment"
    assert spec_for("1 ovnfast fad").skip == "equipment"
    assert spec_for("Vand").skip == "water"
    assert spec_for("2 dl kogende vand").skip == "water"
    assert spec_for("Server med ris").skip == "remark"
    assert spec_for("Tip: brug gerne frisk basilikum").skip == "remark"
    assert spec_for("Kan erstattes med skyr").skip == "remark"
    assert spec_for("Evt. chili").key == "chili"  # the hedge goes, the thing stays
    assert spec_for("Gerne frisk timian").key == "timian"
    assert spec_for("Kogte kartofler").key == "kartofler"
    assert spec_for("Stegt kalkunkød i tern").key == "kalkun"
    assert spec_for("Ris").skip is None


def test_spec_forms_and_counts() -> None:
    """Fresh, frozen, canned or dried; and how a recipe counts a thing."""
    chili = spec_for("Rød chili, hakket")
    assert (chili.key, chili.form, chili.kinds) == ("chili", "fresh", frozenset({VEG}))
    dried = spec_for("Stødt chili")
    assert (dried.key, dried.form, dried.kinds) == ("chiliflager", "dried", frozenset({SPICE}))
    assert spec_for("Frosne ærter").form == "frozen"
    assert FROZEN in spec_for("Frossen broccoli").kinds
    assert spec_for("Tørret timian").kinds == frozenset({SPICE})
    assert spec_for("Frisk oregano").kinds == frozenset({HERB})
    canned = spec_for("2 tomater, hakket")
    assert (canned.key, canned.form) == ("hakkede tomater", "canned")
    assert spec_for("Tun på dåse").kinds == frozenset({CANNED})
    assert spec_for("Grøntsagsbouillon").kinds == frozenset({STOCK})
    garlic = spec_for("3 fed hvidløg")
    assert (garlic.count_word, garlic.per_package, garlic.piece_g) == ("fed", 10, 50)
    assert spec_for("2 stængler citrongræs").per_package == 6
    assert spec_for("1 bundt persille").per_package == 1
    assert spec_for("Hvidløg").count_word is None
    unknown = spec_for("Koreansk gochujang", category="Kolonial")
    assert unknown.entry is None
    assert unknown.key == "gochujang"
    assert unknown.query == "Koreansk gochujang"
    assert "light" in spec_for("Kokosmælk light").asked


def test_product_kinds_from_the_shops_categories() -> None:
    """REMA's department and category say what a product is."""
    assert product_kinds("Kolonial", "Saucer & nem mad", "CUPNUDLER OKSEKØD") == frozenset({READY})
    assert product_kinds("Kolonial", "Saucer & nem mad", "GRØNTSAGSBOUILLON") == frozenset({STOCK})
    assert product_kinds("Kolonial", "Saucer & nem mad", "OKSE BOUILLON") == frozenset({STOCK})
    assert product_kinds("Kolonial", "Fiskekonserves", "TUN I VAND") == frozenset({FISH, CANNED})
    assert product_kinds("Husholdning", "Grill", "GRILLSPYD") == frozenset({NONFOOD})
    assert product_kinds("Frost", "Kød & fjerkræ", "HELE KYLLINGELÅR") == frozenset(
        {POULTRY, FROZEN}
    )
    assert product_kinds("Frost", "Fisk & skaldyr", "RØDSPÆTTEFILETER") == frozenset({FISH, FROZEN})
    assert product_kinds("Frost", "Færdigretter", "HK. OKSEKØD") == frozenset({MEAT, FROZEN})
    assert product_kinds("Frost", "Pizza", "PIZZA MARGHERITA") == frozenset({READY})
    assert product_kinds("Frost", "Grøntsager, frugt & bær", "ÆRTER") == frozenset(
        {VEG, FRUIT, FROZEN}
    )
    assert product_kinds("Kød, fisk & fjerkræ", "Kylling", "KYLLINGEBRYSTFILET") == frozenset(
        {POULTRY}
    )
    assert product_kinds(None, None, "X") is None
    assert product_kinds("Noget nyt", None, "X") is None
    assert product_kinds("Køl", None, "X") is not None


def test_allowed_gates_on_kind_and_form() -> None:
    """A product of another kind than the line can be is out; unknown categories pass."""
    noodles = spec_for("Nudler")
    assert allowed(noodles, "Kolonial", "Saucer & nem mad", "CUPNUDLER OKSEKØD") is False
    assert allowed(noodles, "Kolonial", "Ris & pasta, mv", "NUDLER") is True
    assert allowed(noodles, None, None, "NUDLER") is None
    pepper = spec_for("Rød peberfrugt")
    assert allowed(pepper, "Kolonial", "Konserves & survarer", "PEBERFRUGT STRIMLER") is False
    assert allowed(pepper, "Frugt & grønt", "Agurk, tomat & peberfrugt", "RØD PEBER") is True
    assert allowed(pepper, "Frost", "Grøntsager, frugt & bær", "PEBERFRUGT") is False  # fresh
    frozen = spec_for("Frosne ærter")
    assert allowed(frozen, "Frost", "Grøntsager, frugt & bær", "ÆRTER") is True
    anything = spec_for("Grillspyd", category="Andet")
    assert allowed(anything, "Husholdning", "Grill", "GRILLSPYD") is False
    pizza = spec_for("Frysepizza")
    assert allowed(pizza, "Frost", "Pizza", "PIZZA MARGHERITA") is True
    assert allowed(spec_for("Dej:"), "Køl", "Dej", "TÆRTEDEJ") is False


def test_other_thing_and_qualifiers() -> None:
    """The catalogue's words for what a product is not, unless the line said so."""
    onion = spec_for("Løg")
    assert other_thing(onion, "SKALOTTELØG")
    assert other_thing(onion, "RISTEDE LØG")
    assert not other_thing(onion, "ØKO. LØG GRAM SLOT")
    assert not other_thing(spec_for("Skalotteløg"), "SKALOTTELØG")
    coconut = spec_for("Kokosmælk")
    assert other_thing(coconut, "KOKOSMÆLK LIGHT")
    assert not other_thing(spec_for("Kokosmælk light"), "KOKOSMÆLK LIGHT")
    assert not other_thing(spec_for("Ukendt ting"), "HVAD SOM HELST")
    assert qualifier_only("DADDELBAR, PEANUTS", "peanuts")
    assert qualifier_only("BOLLER I KARRY", "karry")
    assert qualifier_only("HAKKEDE TOMATER M/CHILI", "chili")
    assert not qualifier_only("PEANUTS", "peanuts")
    assert not qualifier_only("KARRY PULVER", "karry")


def test_apply_spec_writes_key_search_and_package_count() -> None:
    """A line gets its key and search term; counted parts become packages."""
    line: dict[str, Any] = {"name": "3 fed hvidløg", "search": "hvidløg", "amount": 3,
                            "unit": "stk", "category": "Frugt & grønt"}  # fmt: skip
    assert mp.apply_spec(line)
    assert (line["key"], line["search"], line["amount"], line["unit"]) == (
        "hvidløg",
        "hvidløg",
        1,
        "pk",
    )
    line = {"name": "Rød peberfrugt", "search": "rød peberfrugt", "amount": 2, "unit": "stk"}
    assert mp.apply_spec(line)
    assert (line["key"], line["search"]) == ("peberfrugt", "peber")
    # A product chosen by hand, or a must-have, keeps its own search term.
    line = {"name": "Rød peberfrugt", "search": "min peber", "product_id": 7}
    mp.apply_spec(line)
    assert line["search"] == "min peber"
    assert not mp.apply_spec({"name": "Dej:", "search": "dej"})
    assert not mp.apply_spec({"name": "Tærteform", "search": "tærteform"})
    assert mp.recipe_line({"name": "Fyld:", "amount": ""}) is None
    assert mp.recipe_line({"name": "Server med ris", "amount": ""}) is None
    pieces = mp.recipe_line({"name": "2 stængler forårsløg", "amount": "3 stk"})
    assert pieces is not None
    assert (pieces["name"], pieces["amount"], pieces["unit"]) == ("Forårsløg", 1, "pk")


def test_merge_lines_adds_up_the_same_thing() -> None:
    """Three onion lines are one line; the dishes' uses follow the name."""
    raw = [
        {"name": "Løg", "amount": 2, "unit": "stk", "search": "løg", "category": "Frugt & grønt"},
        {"name": "Løg, i både", "amount": 1, "unit": "stk", "search": "løg", "category": "Frugt & grønt"},
        {"name": "Stort løg", "amount": 200, "unit": "g", "search": "løg", "category": "Frugt & grønt", "offer": "o1"},
        {"name": "Rødløg", "amount": 1, "unit": "stk", "search": "rødløg", "category": "Frugt & grønt"},
        {"name": "Hakkede tomater", "amount": 2, "unit": "dåse", "search": "hakkede tomater", "category": "Kolonial"},
        {"name": "Tomater, hakkede", "amount": 1, "unit": "dåse", "search": "hakkede tomater", "category": "Kolonial"},
        {"name": "Lime", "amount": 1, "unit": "stk", "search": "lime", "category": "Frugt & grønt"},
        {"name": "Lime, saften herfra", "amount": None, "unit": None, "search": "lime", "category": "Frugt & grønt"},
        {"name": "Kaffe", "amount": 1, "unit": "pk", "search": "kaffe", "category": "Faste varer", "must_have": True},
        {"name": "Kaffe", "amount": 1, "unit": "pk", "search": "kaffe", "category": "Faste varer", "must_have": True},
    ]  # fmt: skip
    cleaned = [(item, mp.MealPlanner._clean_line(item)) for item in raw]
    for item, line in cleaned:
        assert line is not None
        line["must_have"] = bool(item.get("must_have"))
    days = [{"uses": ["Løg, i både", "Stort løg", "Lime"]}, {"uses": ["Tomater, hakkede", "Løg"]}]
    merged = mp.merge_lines(
        [line for _item, line in cleaned if line],
        days,
        {item["name"].lower(): line["name"] for item, line in cleaned if line},
    )
    by_name = {line["name"]: line for line in merged}
    assert list(by_name) == ["Løg", "Rødløg", "Hakkede tomater", "Lime", "Kaffe"]
    assert len(merged) == 6  # the two must-haves stay apart
    assert (by_name["Løg"]["amount"], by_name["Løg"]["unit"], by_name["Løg"]["offer"]) == (
        560,
        "g",
        "o1",
    )
    assert (by_name["Hakkede tomater"]["amount"], by_name["Hakkede tomater"]["unit"]) == (3, "pk")
    assert by_name["Lime"]["amount"] == 1
    assert days == [{"uses": ["Løg", "Lime"]}, {"uses": ["Hakkede tomater", "Løg"]}]


def test_add_amounts() -> None:
    """Grams to grams, pieces to pieces, pieces to grams by weight, else the bigger."""
    line: dict[str, Any] = {"amount": 200, "unit": "g"}
    mp.add_amounts(line, {"amount": 3, "unit": "dl"})
    assert (line["amount"], line["unit"]) == (200, "g")  # unlike: the weight stands
    line = {"amount": 2, "unit": "pk"}
    mp.add_amounts(line, {"amount": 300, "unit": "ml"})
    assert (line["amount"], line["unit"]) == (300, "ml")
    line = {"amount": 2, "unit": "stk"}
    mp.add_amounts(line, {"amount": 3, "unit": "pk"})
    assert line["amount"] == 3
    line = {"amount": 1.5, "unit": "stk"}
    mp.add_amounts(line, {"amount": 1, "unit": "stk"}, piece_g=100)
    assert (line["amount"], line["unit"]) == (3, "stk")
    line = {"amount": 155, "unit": "g"}
    mp.add_amounts(line, {"amount": 1, "unit": "stk"}, piece_g=100)
    assert (line["amount"], line["unit"]) == (260, "g")
    line = {"amount": None, "unit": None}
    mp.add_amounts(line, {"amount": 2, "unit": "stk"})
    assert line["amount"] == 2


def test_pieces_per_package() -> None:
    """Eight onions in a kilo bag, one chicken in a lighter chicken, a sixth of a lettuce."""
    assert mp.pieces_per_package(("g", 1000), 120) == 8
    assert mp.pieces_per_package(("g", 1000), 1200) == 1
    assert mp.pieces_per_package(("g", 1250), 250) == 5
    assert mp.pieces_per_package(("g", 50), 300) == 50 / 300
    assert mp.pieces_per_package(("ml", 1000), 120) is None
    assert mp.pieces_per_package(None, 120) is None
    assert mp.pieces_per_package(("g", 1000), None) is None
    bag = make_product(1, "LØG", 12.0, underline="1 KG. / DANMARK")
    assert mp.packages_needed(2, "stk", bag, 120) == 1
    assert mp.packages_needed(20, "stk", bag, 120) == 3
    shoots = make_product(2, "ÆRTESKUD", 10.0, underline="50 GR.")
    assert mp.packages_needed(1, "stk", shoots, 300) == 6
    chicken = make_product(3, "HEL KYLLING", 50.0, underline="1000 GR.")
    assert mp.packages_needed(2, "stk", chicken, 1200) == 2


def test_fit_amounts_counts_pieces_by_weight() -> None:
    """Two onions from a kilo bag is one bag, not two."""
    plan = {
        "days": [
            {"date": "2026-10-25", "dish": "Suppe", "type": "normal", "ingredients": [
                {"name": "2 løg", "amount": "2 stk"}, {"name": "Gulerødder", "amount": "3 stk"},
            ]},
            {"date": "2026-10-26", "dish": "Gryde", "type": "normal", "ingredients": [
                {"name": "Stort løg", "amount": "1"}, {"name": "Gulerod", "amount": "500 g"},
            ]},
        ],
        "shopping": [
            {"name": "Løg", "key": "løg", "amount": 2, "unit": "stk", "packages": 1, "cost": 12.0,
             "product": {"id": 1, "name": "LØG", "underline": "1 KG. / DANMARK", "price": 12.0}},
            {"name": "Gulerødder", "key": "gulerødder", "amount": 3, "unit": "stk", "packages": 1, "cost": 12.0,
             "product": {"id": 2, "name": "GULERØDDER", "underline": "1 KG.", "price": 12.0}},
        ],
    }  # fmt: skip
    assert mp.fit_amounts(plan) == []
    assert [line["packages"] for line in plan["shopping"]] == [1, 1]
    plan["days"][1]["ingredients"][1]["amount"] = "1200 g"
    assert mp.fit_amounts(plan) == ["Gulerødder"]
    assert plan["shopping"][1]["packages"] == 2


def test_called_by_another_name() -> None:
    """ "GRANA PADANO" is parmesan to the catalogue; "KYLLINGEBRYSTFILET" is not kylling."""
    assert mp._called(spec_for("Parmesan"), "GRANA PADANO")
    assert mp._called(spec_for("Fiskefilet"), "RØDSPÆTTEFILETER")
    assert mp._called(spec_for("Vaniljeis"), "VANILLA  IS")
    assert not mp._called(spec_for("Hel kylling"), "KYLLINGEBRYSTFILET")
    assert not mp._called(spec_for("Ukendt ting"), "UKENDT TING")
