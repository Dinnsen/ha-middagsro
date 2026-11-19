"""Varegrupper: which of eight groups a receipt line belongs to, from its name.

REMA 1000's receipts carry no category, so the name decides. The lists are tried
in order and the first word found wins (a "skinkeost" is cheese only if "ost"
comes before "skinke"; it does not, so it is meat, which is fine for a budget).
Whatever matches nothing is "hjem": the non-food, the toys and the odd things.
"""

from __future__ import annotations

import re

# The groups in the order they are drawn (and coloured) in the panel.
GROUPS: tuple[str, ...] = ("mejeri", "kolonial", "drikke", "brod", "snacks", "frugt", "hjem", "kod")

_WORDS: tuple[tuple[str, str], ...] = (
    (
        "hjem",
        r"bleer|pants|bleposer|vådserviet|nan pro|svømmeble|toiletpapir|køkkenrull|skumvask|opvask"
        r"|vaskemiddel|flydende vask|afspænding|pletfjern|håndsæbe|shampoo|hairspray|batteri"
        r"|affaldspose|lynlås|genluk|tandpasta|ansigtscreme|håndcreme|sollotion|lommeletter"
        r"|servietter|sprinklervæske|vejsalt|rodalon|hygiejnebind|gavepapir|sløjfe|amaryllis"
        r"|playset|politibil|pocket money",
    ),
    (
        "kolonial",
        r"pizza|lovemade|dinner kit|pommes|fritter|pomm's|dej|suppe|melboller|lasagne|nuggets"
        r"|ret nemt|karbonader|panerede|tærte|quiche",
    ),
    (
        "drikke",
        r"pepsi|faxe|fanta|cola|juice|smoothie|iskaffe|blanc|freixenet|chateau|château|grand cru"
        r"|prosecco|asti|barbera|reserva|mocktail|shots|kaffe|crema|espresso|qualita|x-mas"
        r"|chardonnay|rosé|ipa",
    ),
    (
        "snacks",
        r"slik|snack|chips|popcorn|haribo| mix|bars |chokolade|knas|marshmallow|toffifee|kiks"
        r"|kager|gummies|lakrids|ferrero|kinder|julekalender|isvaffel|sandwich is|ostepops"
        r"|spiraler|bugles|nødde|rosin|dipmix|grinebidder|halloween|snitter|kanelstang|trøfler"
        r"|kammerjunker|dippers|fruit stars|sour cream",
    ),
    (
        "kod",
        r"laks|kylling|okse|kalv|gris|hamburgerryg|postej|spegepølse|pølse|bacon|skinke"
        r"|frikadelle|fisk|makrel|tun |tun i|tunsalat|rejer|ørred|mørbrad|medister|flæskesteg"
        r"|ribbens|culotte|ribeye|kebab|döner|salami|rullepølse|burgerboost|pulled pork"
        r"|andebryst|steak|kalkun|hapser|sandwichsk|koteletter|carpaccio",
    ),
    (
        "brod",
        r"rugbrød|brød|boller|mysli|havregryn|guldkorn|coco pops|baguette|skagenslapper"
        r"|cafesandwich|pølsehorn|brioche|burgerb|rugfras|klemmer|tortilla|rug go|kohberg"
        r"|pandekager|æbleskiver|solsikke |focaccia|marmelade|gær",
    ),
    (
        "mejeri",
        r"mælk|yoghurt|fraiche|ost|mozzarella|smørbar|lurpak|kærgården|æg|fløde|cremefine"
        r"|koldskål|actimel|puck|havarti|parmigiano|grana|cheasy|vaniljesauce|45\+|30\+|burrata"
        r"|gouda|kakao|skiver ml",
    ),
    (
        "frugt",
        r"agurk|banan|avocado|blåbær|jordbær|druer|salat|broccoli|gulerød|tomat|citron|lime"
        r"|appelsin|clementin|kiwi|æble|vandmelon|kartof|kart\.|majs|ærter|sugar snaps|løg"
        r"|porre|squash|champignon|blomkål|hokkaido|ingefær|purløg|land/kl|danmark kl"
        r"|spanien kl|holland kl",
    ),
    (
        "kolonial",
        r"pasta|nudler|fusilli|fettuccine|ris |ris$|pesto|salsa|remoulade|dressing|mayo|sauce"
        r"|croutoner|bulgur|olie|mel |mel$|rasp|peanut|tex mex|hummus|vaniljestæng",
    ),
)
_COMPILED = tuple((group, re.compile(words)) for group, words in _WORDS)


def group_of(name: str | None) -> str:
    """The varegruppe of a receipt line, from its name."""
    text = f" {str(name or '').lower()} "
    for group, pattern in _COMPILED:
        if pattern.search(text):
            return group
    return "hjem"
