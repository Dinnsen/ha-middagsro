"""Tests for the digital receipts (kvitteringer) client."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from yarl import URL

from custom_components.middagsro import api
from custom_components.middagsro.api import Receipt, ReceiptItem, RemaApiError, RemaAuthError

from .test_api import FakeResponse, logged_in, token

RECEIPTS_URL = api.RECEIPTS_URL


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


# --------------------------------------------------------------- client (scan sign-in)

CALLBACK = "dk.rema1000.app://logincallback?code=THE-CODE"
LOGIN_PAGE = "https://login.rema1000.dk/login"
CONTINUE = "https://login.rema1000.dk/continue"


def _authorize_url() -> str:
    """The exact authorize URL the client builds (PKCE pinned by the test)."""
    return str(
        URL(api.AUTHORIZE_URL).with_query(
            {
                "client_id": api.SCAN_CLIENT_ID,
                "response_type": "code",
                "code_challenge_method": "S256",
                "code_challenge": "CHAL",
                "redirect_uri": api.SCAN_REDIRECT_URI,
                "screen": "login",
                "lang": "da",
            }
        )
    )


def _pin_pkce(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "_pkce_pair", lambda: ("VERIFIER", "CHAL"))


def _route_scan_login(session: object, *, tokens: dict | None = None) -> None:
    """Mock the authorize -> credentials -> code -> token-exchange happy path."""
    session.on("GET", _authorize_url(), FakeResponse(status=200, url=LOGIN_PAGE))
    session.on("POST", api.LOGIN_API_URL, FakeResponse(data={"redirect_uri": CONTINUE}))
    session.on("GET", CONTINUE, FakeResponse(status=302, headers={"Location": CALLBACK}))
    session.on(
        "POST",
        api.TOKEN_NEW_URL,
        FakeResponse(data=tokens or {"accessToken": token(), "refreshToken": "refresh-1"}),
    )


async def test_get_receipts_signs_in_and_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    """A full Scan Selv sign-in yields the receipts, newest first, with a Bearer."""
    _pin_pkce(monkeypatch)
    client, session = await logged_in()
    _route_scan_login(session)
    older = _sample(id="old", paymentDate=1_700_000_000_000)
    newer = _sample(id="new", paymentDate=1_760_000_000_000)
    session.on("GET", RECEIPTS_URL, FakeResponse(data={"data": [older, newer]}))

    receipts = await client.async_get_receipts(limit=10)

    assert [r.id for r in receipts] == ["new", "old"]
    # The code was exchanged with the matching PKCE verifier.
    _m, _u, kwargs = next(c for c in session.calls if c[1] == api.TOKEN_NEW_URL)
    assert kwargs["json"] == {
        "codeVerifier": "VERIFIER",
        "code": "THE-CODE",
        "redirectUri": api.SCAN_REDIRECT_URI,
    }
    # Receipts were read with the Scan Selv Bearer token.
    _m, _u, kwargs = next(c for c in session.calls if c[1] == RECEIPTS_URL)
    assert kwargs["headers"]["Authorization"].startswith("Bearer ")


async def test_get_receipts_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """``limit`` keeps only the newest few."""
    _pin_pkce(monkeypatch)
    client, session = await logged_in()
    _route_scan_login(session)
    data = {"data": [_sample(id=f"r{i}", paymentDate=1_700_000_000_000 + i) for i in range(5)]}
    session.on("GET", RECEIPTS_URL, FakeResponse(data=data))
    assert len(await client.async_get_receipts(limit=2)) == 2


async def test_get_receipts_handles_bare_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """A plain list (no envelope) is accepted too."""
    _pin_pkce(monkeypatch)
    client, session = await logged_in()
    _route_scan_login(session)
    session.on("GET", RECEIPTS_URL, FakeResponse(data=[_sample()]))
    assert len(await client.async_get_receipts()) == 1


async def test_get_receipts_renews_token() -> None:
    """With a refresh token held, it renews instead of signing in again."""
    client, session = await logged_in()
    client._scan_token = "old-token"
    client._scan_refresh = "refresh-1"
    client._scan_expires_at = 0  # expired
    session.on("POST", api.TOKEN_RENEW_URL, FakeResponse(data={"accessToken": token()}))
    session.on("GET", RECEIPTS_URL, FakeResponse(data=[_sample()]))

    receipts = await client.async_get_receipts()

    assert len(receipts) == 1
    # It renewed; it did not POST credentials.
    assert all(c[1] != api.LOGIN_API_URL for c in session.calls)
    _m, _u, kwargs = next(c for c in session.calls if c[1] == api.TOKEN_RENEW_URL)
    assert kwargs["json"] == {"refreshToken": "refresh-1"}


async def test_get_receipts_renews_on_401(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 401 from the backend forces a renew and one retry."""
    _pin_pkce(monkeypatch)
    client, session = await logged_in()
    _route_scan_login(session)
    client._scan_refresh = "refresh-1"
    session.on("POST", api.TOKEN_RENEW_URL, FakeResponse(data={"accessToken": token()}))
    session.on(
        "GET",
        RECEIPTS_URL,
        FakeResponse(status=401),
        FakeResponse(data=[_sample()]),
    )
    assert len(await client.async_get_receipts()) == 1


async def test_get_receipts_bad_password(monkeypatch: pytest.MonkeyPatch) -> None:
    """A rejected password surfaces as an auth error, not a soft failure."""
    _pin_pkce(monkeypatch)
    client, session = await logged_in()
    session.on("GET", _authorize_url(), FakeResponse(status=200, url=LOGIN_PAGE))
    session.on("POST", api.LOGIN_API_URL, FakeResponse(status=401))
    with pytest.raises(RemaAuthError):
        await client.async_get_receipts()


async def test_get_receipts_server_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A backend 500 surfaces as a RemaApiError."""
    _pin_pkce(monkeypatch)
    client, session = await logged_in()
    _route_scan_login(session)
    session.on("GET", RECEIPTS_URL, FakeResponse(status=500, text="boom"))
    with pytest.raises(RemaApiError):
        await client.async_get_receipts()
