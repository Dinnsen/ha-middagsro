"""Tests for the digital receipts (kvitteringer) client."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from yarl import URL

from custom_components.middagsro import api
from custom_components.middagsro.api import Receipt, ReceiptItem, RemaApiError, RemaAuthError
from custom_components.middagsro.receipts import aggregate_items, receipt_summary, spending_overview
from homeassistant.core import HomeAssistant

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


def test_store_nested_address() -> None:
    """The store's address can be a nested object, not just flat keys."""
    store = api.ReceiptStore.from_api(
        {
            "name": "Kolding",
            "storeNumber": "446",
            "address": {
                "address1": "Drejensvej 2",
                "address2": "v/ Rasmus Brødsgaard Christensen",
                "zip": "6000",
                "city": "Kolding",
            },
            "phone": "88526993",
            "cvr": "25519485",
        }
    )
    assert store is not None
    assert store.address == "Drejensvej 2"
    assert store.address2 == "v/ Rasmus Brødsgaard Christensen"
    assert store.zip == "6000"
    assert store.city == "Kolding"
    assert store.phone == "88526993"
    assert store.cvr == "25519485"


def test_store_flat_and_string_address() -> None:
    """Flat keys and a plain-string address both still work."""
    flat = api.ReceiptStore.from_api(
        {"storeName": "Valby", "address1": "Gl. Køge Landevej 1", "zip": "2500", "city": "Valby"}
    )
    assert flat is not None and flat.address == "Gl. Køge Landevej 1" and flat.city == "Valby"
    plain = api.ReceiptStore.from_api({"name": "X", "address": "Hovedgaden 3"})
    assert plain is not None and plain.address == "Hovedgaden 3" and plain.zip is None


def test_receipt_gross_computed_and_explicit() -> None:
    """Gross is the paid total plus discounts, or read straight when provided."""
    receipt = Receipt.from_api(
        _sample(totalPrice=16875, totalDiscount=3395, store={"name": "Kolding"})
    )
    assert receipt.total == 168.75
    assert receipt.gross == 202.70  # 168.75 + 33.95
    explicit = Receipt.from_api(_sample(grossSubtotal=20000))
    assert explicit.gross == 200.0


def test_receipt_from_dict_round_trip() -> None:
    """A persisted receipt rebuilds with its lines, store and amounts."""
    original = Receipt.from_api(
        _sample(
            grossSubtotal=16000,
            store={
                "name": "Kolding",
                "storeNumber": "446",
                "address": {"address1": "Drejensvej 2", "zip": "6000", "city": "Kolding"},
            },
        )
    )
    rebuilt = Receipt.from_dict(original.as_dict())
    assert rebuilt.id == original.id
    assert rebuilt.total == original.total
    assert rebuilt.gross == original.gross
    assert rebuilt.store is not None and rebuilt.store.city == "Kolding"
    assert rebuilt.store.address == "Drejensvej 2"
    assert [i.name for i in rebuilt.items] == [i.name for i in original.items]
    assert rebuilt.items[0].quantity == 2 and rebuilt.items[0].price == 10.95


def test_receipt_from_dict_requires_id() -> None:
    """A stored receipt without an id is rejected."""
    with pytest.raises(ValueError):
        Receipt.from_dict({"total": 10})


# --------------------------------------------------------------- aggregation


def _rc(date_ms: str, items: list[dict], rid: str) -> Receipt:
    return Receipt.from_api({"id": rid, "paymentDate": date_ms, "totalPrice": 1000, "items": items})


def test_aggregate_items_counts_prices_and_frequent() -> None:
    """Items roll up across receipts: quantities, unit price range, last buy, flag."""
    receipts = [
        _rc("2026-11-01T10:00:00Z", [{"shelfText1": "Mælk", "price": 1095, "quantity": 1}], "a"),
        _rc(
            "2026-11-10T10:00:00Z",
            [
                {"shelfText1": "Mælk", "price": 995, "quantity": 2},
                {"shelfText1": "Æg", "price": 2000},
            ],
            "b",
        ),
        _rc("2026-11-13T10:00:00Z", [{"shelfText1": "Mælk", "price": 1195, "quantity": 1}], "c"),
    ]
    agg = aggregate_items(receipts)
    assert agg[0]["name"] == "Mælk"  # most bought first
    milk = agg[0]
    assert milk["count"] == 4  # 1 + 2 + 1 quantities
    assert milk["times"] == 3  # three receipts
    assert milk["max_price"] == 11.95
    assert milk["last_date"] == "2026-11-13T10:00:00+00:00"
    assert milk["last_price"] == 11.95
    assert milk["frequent"] is False
    eggs = next(i for i in agg if i["name"] == "Æg")
    assert eggs["count"] == 1 and eggs["frequent"] is False


def test_aggregate_items_flags_frequent_over_five() -> None:
    """An item bought more than five times is flagged."""
    receipts = [
        _rc(f"2026-11-{d:02d}T10:00:00Z", [{"shelfText1": "Kaffe", "price": 3000}], f"r{d}")
        for d in range(1, 8)
    ]
    agg = aggregate_items(receipts)
    assert agg[0]["name"] == "Kaffe"
    assert agg[0]["count"] == 7
    assert agg[0]["frequent"] is True


def test_spending_overview_groups_and_summarises() -> None:
    """Receipts roll up by week/month/year with high, low, average and saved."""
    receipts = [
        Receipt.from_api(
            {
                "id": "s1",
                "paymentDate": "2026-09-10T10:00:00Z",
                "totalPrice": 5000,
                "totalDiscount": 500,
            }
        ),
        Receipt.from_api(
            {
                "id": "s2",
                "paymentDate": "2026-10-05T10:00:00Z",
                "totalPrice": 10000,
                "totalDiscount": 1000,
            }
        ),
        Receipt.from_api(
            {
                "id": "s3",
                "paymentDate": "2026-10-20T10:00:00Z",
                "totalPrice": 20000,
                "totalDiscount": 2000,
            }
        ),
    ]
    overview = spending_overview(receipts)
    assert set(overview) == {"week", "month", "year"}
    month = overview["month"]
    # Two months: sep (50) and oct (100 + 200 = 300).
    assert {b["key"]: b["spent"] for b in month["buckets"]} == {"2026-09": 50.0, "2026-10": 300.0}
    assert month["high"] == {"key": "2026-10", "spent": 300.0}
    assert month["low"] == {"key": "2026-09", "spent": 50.0}
    assert month["avg"] == 175.0  # (50 + 300) / 2
    assert month["saved_total"] == 35.0  # 5 + 10 + 20
    assert month["total"] == 350.0
    year = overview["year"]
    assert {b["key"]: b["spent"] for b in year["buckets"]} == {"2026": 350.0}
    assert year["saved_total"] == 35.0


def test_spending_overview_empty() -> None:
    """No receipts gives empty buckets and zeroed stats."""
    overview = spending_overview([])
    assert overview["week"]["buckets"] == []
    assert overview["week"]["high"] is None
    assert overview["week"]["avg"] == 0.0


def test_receipt_summary_is_compact() -> None:
    """The list summary carries the amounts and store but not the lines."""
    summary = receipt_summary(
        Receipt.from_api(
            _sample(
                totalPrice=16875, totalDiscount=3395, store={"name": "Kolding", "city": "Kolding"}
            )
        )
    )
    assert summary["total"] == 168.75
    assert summary["gross"] == 202.70
    assert summary["total_discount"] == 33.95
    assert summary["items"] == 2
    assert summary["store"] == "Kolding"
    assert summary["city"] == "Kolding"
    assert "items" in summary and isinstance(summary["items"], int)


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
    # It renewed; it did not run a full sign-in (no token/new exchange).
    assert all(c[1] != api.TOKEN_NEW_URL for c in session.calls)
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


# ------------------------------------------------- live wiring (coordinator, sensors, panel)


def _live_receipts() -> list[Receipt]:
    """Two parsed receipts, newest last so sorting is exercised."""
    return [
        Receipt.from_api(
            {
                "id": "r-2",
                "paymentDate": "2026-10-10T09:00:00Z",
                "totalPrice": 7970,
                "store": {"name": "Kolding", "city": "Kolding"},
                "items": [{"shelfText1": "KAFFE", "price": 3000}],
            }
        ),
        Receipt.from_api(
            {
                "id": "r-1",
                "paymentDate": "2026-10-13T15:21:13Z",
                "totalPrice": 16875,
                "totalDiscount": 3395,
                "store": {
                    "name": "Kolding",
                    "storeNumber": "446",
                    "address": {"address1": "Drejensvej 2", "zip": "6000", "city": "Kolding"},
                },
                "items": [
                    {"shelfText1": "KAFFE", "price": 3000},
                    {"shelfText1": "CHOKOLADEKNAS", "price": 2000, "discount": 200},
                ],
            }
        ),
    ]


async def test_receipts_drive_coordinator_sensors_and_panel(
    hass: object,
    init_integration: object,
    mock_client: object,
    hass_ws_client: object,
) -> None:
    """Fetched receipts populate the store, the sensors, the item stats and the panel."""
    assert isinstance(hass, HomeAssistant)
    mock_client.async_get_receipts.return_value = _live_receipts()
    coordinator = init_integration.runtime_data.receipts
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Newest first, and the per-item stats are built.
    assert [r.id for r in coordinator.data] == ["r-1", "r-2"]
    kaffe = next(i for i in coordinator.items if i["name"] == "KAFFE")
    assert kaffe["count"] == 2 and kaffe["times"] == 2
    # The spend overview is built too.
    assert set(coordinator.overview) == {"week", "month", "year"}
    assert coordinator.overview["month"]["total"] == round(168.75 + 79.70, 2)

    # The latest-purchase sensors read the newest receipt.
    total = hass.states.get("sensor.middagsro_latest_purchase")
    gross = hass.states.get("sensor.middagsro_latest_purchase_before_discounts")
    assert total is not None and float(total.state) == 168.75
    assert gross is not None and float(gross.state) == 202.70
    assert total.attributes["discount"] == 33.95

    # The panel state carries the compact list + item stats.
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "middagsro/state"})
    state = (await client.receive_json())["result"]
    assert state["receipts"]["count"] == 2
    assert state["receipts"]["list"][0]["id"] == "r-1"
    assert state["receipts"]["list"][0]["gross"] == 202.70

    # One full receipt, with its lines, on demand.
    await client.send_json({"id": 2, "type": "middagsro/receipt", "receipt_id": "r-1"})
    full = await client.receive_json()
    assert full["success"]
    assert full["result"]["store"]["city"] == "Kolding"
    assert len(full["result"]["items"]) == 2

    # An unknown receipt id is a clean error.
    await client.send_json({"id": 3, "type": "middagsro/receipt", "receipt_id": "nope"})
    missing = await client.receive_json()
    assert not missing["success"]


async def test_receipts_booked_into_budget_on_refresh(
    hass: object,
    init_integration: object,
    mock_client: object,
) -> None:
    """With booking on, a refresh turns receipts into budget purchases."""
    store = init_integration.runtime_data.store
    await store.async_set_settings(
        {**store.settings, "monthly_budget": 3000, "book_receipts": True}
    )
    # Book from before the sample receipts so they are included.
    store.settings["book_receipts_since"] = "2026-01-01"
    mock_client.async_get_receipts.return_value = _live_receipts()
    await init_integration.runtime_data.receipts.async_request_refresh()
    await hass.async_block_till_done()
    booked = {p["id"] for p in store.purchases}
    assert {"rcpt_r-1", "rcpt_r-2"} <= booked
    amount = next(p["amount"] for p in store.purchases if p["id"] == "rcpt_r-1")
    assert amount == 168.75
