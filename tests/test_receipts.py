"""Tests for the digital receipts (kvitteringer) client."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from custom_components.middagsro import api
from custom_components.middagsro.api import Receipt, ReceiptItem, RemaApiError

from .test_api import FakeResponse, logged_in, token

RECEIPTS_URL = api.RECEIPTS_URLS[0]  # the first candidate the client tries
RECEIPTS_URL_2 = api.RECEIPTS_URLS[1]


def _sample(**over: object) -> dict:
    """A receipt as the backend returns it (reverse-engineered field names)."""
    raw = {
        "id": "r-100",
        "displayId": "2026-0001",
        "paymentDate": 1_760_000_000_000,  # epoch milliseconds
        "totalPrice": 14995,  # øre -> 149.95 kr
        "totalPriceString": "149,95",
        "totalDiscount": 500,
        "totalVat": 2999,
        "paymentSource": "mobilepay",
        "paymentProvider": {"cardType": "VISA", "maskedPan": "**** 4417"},
        "store": {
            "storeNumber": "123",
            "name": "REMA 1000 Kolding",
            "zip": "6000",
            "city": "Kolding",
        },
        "items": [
            {
                "shelfText1": "LETMÆLK",
                "shelfText2": "1 LTR",
                "price": 1095,
                "quantity": 2,
                "vat": 100,
            },
            {"shelfText1": "RUGBRØD", "price": 2500},
        ],
    }
    raw.update(over)
    return raw


# --------------------------------------------------------------- parsing


def test_kroner_from_ore_and_strings() -> None:
    """Øre integers become kroner; decimal strings are read as kroner."""
    assert api._kroner(14995) == 149.95
    assert api._kroner(0) == 0.0
    assert api._kroner("1095") == 10.95  # a bare integer string is øre
    assert api._kroner("149,95") == 149.95
    assert api._kroner("149.95") == 149.95
    assert api._kroner(None) is None
    assert api._kroner("") is None
    assert api._kroner(True) is None


def test_receipt_time() -> None:
    """Receipt timestamps come as epoch millis, epoch seconds or ISO strings."""
    assert api._receipt_time(1_760_000_000_000) == datetime.fromtimestamp(1_760_000_000, UTC)
    assert api._receipt_time(1_760_000_000) == datetime.fromtimestamp(1_760_000_000, UTC)
    assert api._receipt_time("2026-01-02T03:04:05Z") == datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    assert api._receipt_time(None) is None
    assert api._receipt_time("nonsense") is None


def test_receipt_from_api() -> None:
    """A full receipt is read, with øre turned to kroner and lines parsed."""
    receipt = Receipt.from_api(_sample())
    assert receipt.id == "r-100"
    assert receipt.display_id == "2026-0001"
    assert receipt.date == datetime.fromtimestamp(1_760_000_000, UTC)
    assert receipt.total == 149.95
    assert receipt.total_string == "149,95"
    assert receipt.total_discount == 5.0
    assert receipt.card_type == "VISA"
    assert receipt.masked_pan == "**** 4417"
    assert receipt.store is not None
    assert receipt.store.name == "REMA 1000 Kolding"
    assert receipt.store.city == "Kolding"
    assert [item.name for item in receipt.items] == ["LETMÆLK 1 LTR", "RUGBRØD"]
    assert receipt.items[0].price == 10.95
    assert receipt.items[0].quantity == 2
    assert receipt.items[1].price == 25.0


def test_receipt_skips_bad_lines_but_keeps_receipt() -> None:
    """A line that cannot be read is dropped; the receipt is still returned."""
    receipt = Receipt.from_api(
        _sample(items=["not-an-object", {"shelfText1": "ÆG", "price": 2000}])
    )
    assert [item.name for item in receipt.items] == ["ÆG"]
    assert receipt.items[0].price == 20.0


def test_receipt_requires_an_id() -> None:
    """A receipt without any id is rejected (the caller skips it)."""
    with pytest.raises(ValueError):
        Receipt.from_api({"totalPrice": 100})


def test_receipt_as_dict_round_trips() -> None:
    """The service response shape is JSON-friendly."""
    data = Receipt.from_api(_sample()).as_dict()
    assert data["total"] == 149.95
    assert data["store"]["name"] == "REMA 1000 Kolding"
    assert data["items"][0] == {
        "name": "LETMÆLK 1 LTR",
        "quantity": 2,
        "price": 10.95,
        "deposit": None,
        "discount": None,
        "vat": 1.0,
    }
    assert data["date"] == datetime.fromtimestamp(1_760_000_000, UTC).isoformat()


def test_receipt_item_from_api_minimal() -> None:
    """A line with only a price still parses, with a fallback name."""
    item = ReceiptItem.from_api({"price": 999})
    assert item.name == "Vare"
    assert item.price == 9.99


# --------------------------------------------------------------- client


async def test_get_receipts_fetches_and_sorts() -> None:
    """The newest receipts come back first, within the limit, with a Bearer token."""
    client, session = await logged_in()
    older = _sample(id="old", paymentDate=1_700_000_000_000)
    newer = _sample(id="new", paymentDate=1_760_000_000_000)
    session.on("POST", RECEIPTS_URL, FakeResponse(data={"data": [older, newer]}))

    receipts = await client.async_get_receipts(limit=10)

    assert [r.id for r in receipts] == ["new", "old"]  # newest first
    _method, _url, kwargs = next(c for c in session.calls if c[1] == RECEIPTS_URL)
    assert kwargs["headers"]["Authorization"].startswith("Bearer ")


async def test_get_receipts_limit_and_since() -> None:
    """``limit`` trims the list and ``since`` is passed to the backend."""
    client, session = await logged_in()
    data = {"data": [_sample(id=f"r{i}", paymentDate=1_700_000_000_000 + i) for i in range(5)]}
    session.on("POST", RECEIPTS_URL, FakeResponse(data=data))

    receipts = await client.async_get_receipts(since=datetime(2026, 1, 1, tzinfo=UTC), limit=2)

    assert len(receipts) == 2
    _, _, kwargs = next(c for c in session.calls if c[1] == RECEIPTS_URL)
    assert kwargs["json"]["sinceDate"] == "2026-01-01T00:00:00Z"


async def test_get_receipts_handles_bare_list() -> None:
    """A backend that returns a plain list (no envelope) is accepted too."""
    client, session = await logged_in()
    session.on("POST", RECEIPTS_URL, FakeResponse(data=[_sample()]))
    receipts = await client.async_get_receipts()
    assert len(receipts) == 1


async def test_get_receipts_renews_a_rejected_token() -> None:
    """A 401 renews the access token once and then succeeds."""
    client, session = await logged_in()
    session.on(
        "POST",
        "https://shop.rema1000.dk/api/auth/refresh",
        FakeResponse(data={"tokens": {"access_token": token()}}),
    )
    session.on(
        "POST",
        RECEIPTS_URL,
        FakeResponse(status=401),
        FakeResponse(data={"data": [_sample()]}),
    )
    receipts = await client.async_get_receipts()
    assert len(receipts) == 1


async def test_get_receipts_falls_through_to_next_candidate() -> None:
    """A 404 on the first endpoint moves on to the next, which is remembered."""
    client, session = await logged_in()
    session.on("POST", RECEIPTS_URL, FakeResponse(status=404))
    session.on("POST", RECEIPTS_URL_2, FakeResponse(data={"data": [_sample()]}))

    receipts = await client.async_get_receipts()

    assert len(receipts) == 1
    assert client._receipts_url == RECEIPTS_URL_2  # the working one is remembered
    # Next call tries the remembered endpoint first (only it is routed here).
    session.on("POST", RECEIPTS_URL_2, FakeResponse(data={"data": []}))
    assert await client.async_get_receipts() == []


async def test_get_receipts_raises_when_no_endpoint_answers() -> None:
    """When every candidate fails, one error reports each status."""
    client, session = await logged_in()
    for url in api.RECEIPTS_URLS:
        session.on("POST", url, FakeResponse(status=404))
    with pytest.raises(RemaApiError):
        await client.async_get_receipts()
