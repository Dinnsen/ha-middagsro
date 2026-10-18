"""Tests for the REMA 1000 web client, against a fake HTTP session."""

from __future__ import annotations

import base64
from collections.abc import Callable
from datetime import UTC, datetime
import json
import time
from typing import Any

import aiohttp
import pytest
from yarl import URL

from custom_components.rema1000 import api
from custom_components.rema1000.api import (
    Catalog,
    Offer,
    Product,
    RemaApiError,
    RemaAuthError,
    RemaClient,
    RemaConnectionError,
    ShoppingList,
    ShoppingListItem,
    split_amount,
    week_end,
)

SHOP = "https://shop.rema1000.dk"
SITE = "https://rema1000.dk"
API = "https://api.digital.rema1000.dk/api"


def token(user_id: int = 4242, expires_in: int = 3600) -> str:
    """A JWT like REMA's (only the payload matters)."""
    payload = json.dumps({"sub": str(user_id), "exp": int(time.time()) + expires_in})
    body = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    return f"header.{body}.signature"


class FakeResponse:
    """Just enough of aiohttp's response."""

    def __init__(
        self,
        status: int = 200,
        data: Any = None,
        *,
        text: str | None = None,
        url: str = "https://example.dk/",
        cookies: dict[str, str] | None = None,
    ) -> None:
        self.status = status
        self._data = data
        self._text = text
        self.url = URL(url)
        self.cookies = cookies or {}

    async def json(self, content_type: str | None = None) -> Any:
        return self._data

    async def text(self) -> str:
        if self._text is not None:
            return self._text
        return "" if self._data is None else json.dumps(self._data)

    async def read(self) -> bytes:
        return (await self.text()).encode()

    async def __aenter__(self) -> FakeResponse:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None


type Handler = Callable[..., FakeResponse | Exception]


class FakeSession:
    """Routes requests to handlers; a handler may be a list answered in turn."""

    def __init__(self) -> None:
        self.cookie_jar = aiohttp.CookieJar()
        self.routes: dict[tuple[str, str], list[FakeResponse | Exception | Handler]] = {}
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def on(self, method: str, url: str, *answers: FakeResponse | Exception | Handler) -> None:
        self.routes[(method, url)] = list(answers)

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append((method, url, kwargs))
        answers = self.routes[(method, url)]
        answer = answers.pop(0) if len(answers) > 1 else answers[0]
        if callable(answer) and not isinstance(answer, FakeResponse):
            answer = answer(**kwargs)
        if isinstance(answer, Exception):
            raise answer
        if answer.cookies:  # set by the page the request ended on, like a browser
            self.cookie_jar.update_cookies(answer.cookies, answer.url)
        return answer

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        return self.request("POST", url, **kwargs)

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        return self.request("GET", url, **kwargs)


def login_routes(session: FakeSession, site: str = SHOP, access: str | None = None) -> None:
    """The three steps of REMA's web login."""
    session.on("GET", f"{site}/konto/auth", FakeResponse(url="https://login.rema1000.dk/?c=1"))
    session.on(
        "POST",
        api.LOGIN_API_URL,
        FakeResponse(data={"redirect_uri": "http://login.rema1000.dk/authorize?x=1"}),
    )
    session.on(
        "GET",
        "https://login.rema1000.dk/authorize?x=1",
        FakeResponse(url=f"{site}/konto", cookies={"access_token": access or token()}),
    )


async def logged_in() -> tuple[RemaClient, FakeSession]:
    session = FakeSession()
    login_routes(session)
    client = RemaClient(session, "family@example.com", "pw")  # type: ignore[arg-type]
    assert await client.async_login() == 4242
    return client, session


# ------------------------------------------------------------------ helpers


def test_helpers() -> None:
    """Small parsers."""
    assert api.parse_time(None) is None
    assert api.parse_time(5) is None
    assert api.parse_time("nope") is None
    assert api.parse_time("2026-10-18T00:00:00Z") == datetime(2026, 10, 18, tzinfo=UTC)
    assert api.parse_time("2026-10-18T00:00:00") == datetime(2026, 10, 18, tzinfo=UTC)
    assert api._float("") is None
    assert api._float("x") is None
    assert api._float("1.5") == 1.5
    assert api._name_of({"name": "Mejeri"}) == "Mejeri"
    assert api._name_of({"id": 1}) is None
    assert api._name_of("Kød") == "Kød"
    assert api._name_of(None) is None
    assert split_amount("3 x mælk") == (3, "mælk")
    assert split_amount("0 × æg") == (1, "æg")
    assert split_amount(" Opvasketabs ") == (1, "Opvasketabs")
    with pytest.raises(RemaApiError):
        api._jwt_claims("not-a-jwt")
    with pytest.raises(RemaApiError):
        api._jwt_claims("a." + base64.urlsafe_b64encode(b"[1]").decode() + ".c")


def test_models() -> None:
    """Products, list items, catalogues and offers from REMA's and Tjek's JSON."""
    now = datetime(2026, 10, 14, 12, tzinfo=UTC)
    product = Product.from_api(
        {
            "id": 20494,
            "name": "LETMÆLK 1,5% FEDT",
            "underline": "1 LTR. / REMA 1000",
            "department": {"name": "Mejeri"},
            "category": "Mælk",
            "labels": [{"name": "REMA1000"}, {"id": 2}],
            "images": [{"small": "s.webp"}],
            "prices": [
                {"price": 10.95, "starting_at": "2026-01-01T00:00:00Z", "compare_unit": "ltr",
                 "compare_unit_price": 10.95},
                {"price": 8.0, "is_advertised": True, "is_campaign": True,
                 "starting_at": "2026-10-11T00:00:00Z", "ending_at": "2026-10-17T22:00:00Z"},
                {"price": 7.5, "is_advertised": True, "starting_at": "2026-10-18T00:00:00Z"},
                {"price": 5.0, "starting_at": "2026-09-01T00:00:00Z",
                 "ending_at": "2026-09-07T00:00:00Z"},
            ],
        },
        now,
    )  # fmt: skip
    assert (product.price, product.normal_price) == (8.0, 10.95)
    assert product.is_advertised and product.is_campaign
    assert (product.upcoming_price, product.upcoming_is_advertised) == (7.5, True)
    assert product.department == "Mejeri"
    assert product.category == "Mælk"
    assert product.image == "s.webp"
    assert product.labels == ["REMA1000"]
    assert product.as_dict()["id"] == 20494

    favourite = Product.from_api(
        {"id": 1, "name": "ØKO. SMØR", "pricing": {"price": 20, "normal_price": 25,
         "is_on_discount": True, "price_changes_on": "2026-10-17"}},
        now,
    )  # fmt: skip
    assert (favourite.price, favourite.normal_price, favourite.is_campaign) == (20, 25, True)
    assert favourite.is_organic
    plain = Product.from_api({"id": 2, "name": "X", "underline": "ØKOLOGISK", "images": ["x"]})
    assert plain.price is None
    assert plain.is_organic
    assert plain.image is None

    item = ShoppingListItem.from_api(
        {"id": 1, "name": "RUGBRØD", "bought": True, "amount": 8, "store_item_id": 60033,
         "store_item": {"underline": "750 GR.", "pricing": {"price": 15, "max_quantity": 6,
                        "price_over_max": 22.5, "is_on_discount": True}}}
    )  # fmt: skip
    assert item.total_price == 6 * 15 + 2 * 22.5
    soda = ShoppingListItem.from_api(
        {
            "id": 2,
            "amount": 2,
            "store_item": {"name": "COLA", "pricing": {"price": 10, "deposit": 3}},
        }
    )
    assert soda.name == "COLA"
    assert soda.total_price == 26.0
    free = ShoppingListItem.from_api({"id": 3, "name": "Kage", "amount": None})
    assert free.total_price is None
    assert free.amount == 1
    lst = ShoppingList(1, "Indkøb", [item, soda, free])
    assert lst.unbought_total == 26.0
    assert lst.find(product_id=60033, name=None) is item
    assert lst.find(product_id=None, name=" kage ") is free
    assert lst.find(product_id=999, name="kage") is None

    catalog = Catalog.from_api(
        {"id": 7, "name": "Uge 43", "run_from": "2026-10-18T00:00:00+02:00", "offer_count": 3}
    )
    assert catalog.id == "7"
    assert catalog.label == "Uge 43"
    assert catalog.valid_to is None

    offer = Offer.from_api(
        {"id": 1, "heading": "Kaffe", "pricing": {"price": 30, "pre_price": 45},
         "quantity": {"size": {"from": 500}, "unit": {"symbol": "g"}, "pieces": {"from": 2}}}
    )  # fmt: skip
    assert offer.quantity == "2 stk. / 500 g"
    assert offer.as_dict()["pre_price"] == 45
    pieces = Offer.from_api(
        {"id": 2, "quantity": {"size": {"from": "1-2"}, "unit": {"symbol": "pcs"}}}
    )
    assert pieces.quantity == "1-2 stk."
    assert pieces.heading == ""
    assert Offer.from_api({"id": 3}).quantity is None


# ------------------------------------------------------------------ login


async def test_login() -> None:
    """The web login gives a token and the user id."""
    client, session = await logged_in()
    assert client.user_id == 4242
    assert session.calls[1][2]["json"] == {"email": "family@example.com", "password": "pw"}


async def test_login_falls_back_to_second_site() -> None:
    """If the webshop flow fails, rema1000.dk is tried."""
    session = FakeSession()
    session.on("GET", f"{SHOP}/konto/auth", FakeResponse(url=f"{SHOP}/maintenance"))
    login_routes(session, SITE)
    client = RemaClient(session, "a", "b")  # type: ignore[arg-type]
    assert await client.async_login() == 4242
    assert client._site == SITE


@pytest.mark.parametrize(
    ("answer", "error"),
    [
        (FakeResponse(401), RemaAuthError),
        (FakeResponse(500), RemaApiError),
        (aiohttp.ClientError("reset"), RemaConnectionError),
        (FakeResponse(data={"no": "redirect"}), RemaApiError),
    ],
)
async def test_login_errors(answer: FakeResponse | Exception, error: type[Exception]) -> None:
    """Rejected logins, server errors and odd answers."""
    session = FakeSession()
    for site in (SHOP, SITE):
        login_routes(session, site)
    session.on("POST", api.LOGIN_API_URL, answer)
    client = RemaClient(session, "a", "b")  # type: ignore[arg-type]
    with pytest.raises(error):
        await client.async_login()


async def test_login_without_token_or_unreachable() -> None:
    """No token cookie, and a site that can't be reached."""
    session = FakeSession()
    session.on("GET", f"{SHOP}/konto/auth", aiohttp.ClientError("dns"))
    login_routes(session, SITE)
    session.on("GET", "https://login.rema1000.dk/authorize?x=1", FakeResponse(url=f"{SITE}/konto"))
    client = RemaClient(session, "a", "b")  # type: ignore[arg-type]
    with pytest.raises(RemaApiError, match="No access token"):
        await client.async_login()

    session.on("GET", f"{SITE}/konto/auth", FakeResponse(503))
    with pytest.raises(RemaApiError, match="HTTP 503"):
        await client.async_login()


# ------------------------------------------------------------------ tokens


async def test_token_refresh_and_relogin() -> None:
    """An old token is renewed; if that fails, the client logs in again."""
    client, session = await logged_in()
    session.on("GET", f"{API}/search/products", FakeResponse(data={"data": []}))

    client._expires_at = time.time() + 10
    session.on(
        "POST",
        f"{SHOP}/api/auth/refresh",
        FakeResponse(data={"tokens": {"access_token": token(4242, 7200)}}),
    )
    await client.async_search_products("x")
    assert client._expires_at > time.time() + 7000

    client._expires_at = 0
    session.on(
        "POST",
        f"{SHOP}/api/auth/refresh",
        FakeResponse(url=f"{SHOP}/", cookies={"access_token": token(4242, 5000)}),
    )
    await client.async_search_products("x")
    assert 4900 < client._expires_at - time.time() < 5100

    client._expires_at = 0
    session.on("POST", f"{SHOP}/api/auth/refresh", FakeResponse(401))
    logins = sum(1 for call in session.calls if call[1] == api.LOGIN_API_URL)
    await client.async_search_products("x")
    assert sum(1 for call in session.calls if call[1] == api.LOGIN_API_URL) == logins + 1

    client._expires_at = 0
    session.on("POST", f"{SHOP}/api/auth/refresh", aiohttp.ClientError("reset"))
    with pytest.raises(RemaConnectionError):
        await client.async_search_products("x")


async def test_refresh_edge_cases() -> None:
    """Refreshing needs a login and a token in the answer."""
    client = RemaClient(FakeSession(), "a", "b")  # type: ignore[arg-type]
    with pytest.raises(RemaAuthError):
        await client._async_refresh()

    client, session = await logged_in()
    session.cookie_jar.clear()
    session.on("POST", f"{SHOP}/api/auth/refresh", FakeResponse(data={"tokens": {}}))
    with pytest.raises(RemaAuthError):
        await client._async_refresh()


# ------------------------------------------------------------------ API calls


async def test_requests_and_retries() -> None:
    """401 renews the token once; other errors become RemaErrors."""
    client, session = await logged_in()
    url = f"{API}/search/products"
    session.on("POST", f"{SHOP}/api/auth/refresh", FakeResponse(data={"tokens": {
        "access_token": token()}}))  # fmt: skip

    session.on("GET", url, FakeResponse(401), FakeResponse(data={"data": [{"id": 1, "name": "A"}]}))
    assert [p.name for p in await client.async_search_products("a", 500)] == ["A"]
    assert session.calls[-1][2]["params"]["per_page"] == 100

    session.on("GET", url, FakeResponse(401))
    with pytest.raises(RemaAuthError):
        await client.async_search_products("a")

    session.on("GET", url, FakeResponse(500, text="Server error"))
    with pytest.raises(RemaApiError, match="HTTP 500: Server error"):
        await client.async_search_products("a")

    session.on("GET", url, TimeoutError())
    with pytest.raises(RemaConnectionError):
        await client.async_search_products("a")

    session.on("GET", url, FakeResponse(204))
    assert await client.async_search_products("a") == []
    session.on("GET", url, FakeResponse(200, text=""))
    assert await client.async_search_products("a") == []
    session.on("GET", url, FakeResponse(data={"data": [{"name": "no id"}, {"id": 2, "name": "B"}]}))
    assert [p.id for p in await client.async_search_products("a")] == [2]

    # Priced as of a later time: next week's avis price is the price then.
    prices = [
        {"price": 20, "starting_at": "2026-01-01T00:00:00Z", "ending_at": None},
        {"price": 15, "is_advertised": True, "starting_at": "2099-01-04T00:00:00Z",
         "ending_at": "2099-01-10T22:00:00Z"},
    ]  # fmt: skip
    session.on("GET", url, FakeResponse(data={"data": [{"id": 3, "name": "C", "prices": prices}]}))
    [now] = await client.async_search_products("c")
    assert (now.price, now.upcoming_price) == (20, 15)
    session.on("GET", url, FakeResponse(data={"data": [{"id": 3, "name": "C", "prices": prices}]}))
    [later] = await client.async_search_products("c", at=datetime(2099, 1, 5, tzinfo=UTC))
    assert (later.price, later.normal_price, later.is_advertised) == (15, 20, True)


def test_prices_through_the_week() -> None:
    """REMA's week prices end before the avis; they last until the week turns."""

    def at(prices: list[dict[str, Any]], now: str) -> Product:
        return Product.from_api({"id": 1, "name": "PISKEFLØDE", "prices": prices},
                                datetime.fromisoformat(now))  # fmt: skip

    cream = [
        {"price": 12, "is_advertised": True, "starting_at": "2026-10-11T00:00:00Z",
         "ending_at": "2026-10-17T00:00:00Z"},
        {"price": 12.95, "starting_at": "2026-08-01T00:00:00Z", "ending_at": "2026-10-17T00:00:00Z"},
        {"price": 12.95, "starting_at": "2026-10-18T00:00:00Z"},
    ]  # fmt: skip
    saturday = at(cream, "2026-10-17T10:00:00+00:00")  # no REMA price, avis still runs
    assert (saturday.price, saturday.normal_price, saturday.is_advertised) == (12, 12.95, True)
    sunday_night = at(cream, "2026-10-17T23:00:00+00:00")  # week turned, new prices not yet
    assert sunday_night.price == 12
    sunday = at(cream, "2026-10-18T10:00:00+00:00")
    assert (sunday.price, sunday.is_advertised) == (12.95, False)
    later = at(cream[:2], "2026-10-25T10:00:00+00:00")  # long gone
    assert later.price is None

    # The offer ended but the normal price runs on: the offer lasts to the week's end.
    running = [{"price": 20, "starting_at": "2026-01-01T00:00:00Z"}, cream[0]]
    assert at(running, "2026-10-17T10:00:00+00:00").price == 12
    assert at(running, "2026-10-18T10:00:00+00:00").price == 20

    # A price replaced in the middle of the week is not carried on.
    raised = [
        {"price": 10, "starting_at": "2026-01-01T00:00:00Z", "ending_at": "2026-10-14T00:00:00Z"},
        {"price": 11, "starting_at": "2026-10-14T00:00:00Z"},
    ]  # fmt: skip
    assert at(raised, "2026-10-15T10:00:00+00:00").price == 11
    # REMA's week turns sunday 00:00 UTC (02:00 danish time).
    assert week_end(datetime(2026, 10, 17, 22, tzinfo=UTC)) == datetime(2026, 10, 18, tzinfo=UTC)
    assert week_end(datetime(2026, 10, 18, tzinfo=UTC)) == datetime(2026, 10, 18, tzinfo=UTC)

    # During an offer REMA has no normal price; the one after (or before) it is used.
    offer_only = [cream[0], {"price": 12.95, "starting_at": "2026-10-18T00:00:00Z"}]
    assert at(offer_only, "2026-10-14T10:00:00+00:00").normal_price == 12.95
    before_only = [
        {"price": 13.5, "starting_at": "2026-08-01T00:00:00Z", "ending_at": "2026-10-11T00:00:00Z"},
        cream[0],
    ]  # fmt: skip
    assert at(before_only, "2026-10-14T10:00:00+00:00").normal_price == 13.5


async def test_shopping_lists() -> None:
    """Find the primary list and change items."""
    client, session = await logged_in()
    lists = f"{API}/v3/users/4242/shopping-lists"
    session.on(
        "GET", lists, FakeResponse(data={"data": [{"id": 1}, {"id": 2, "is_primary": True}]})
    )
    session.on("GET", f"{API}/v2/shoppinglists/2", FakeResponse(data={
        "id": 2, "name": "Indkøb", "items": [{"id": 9, "name": "Mælk", "amount": 2,
                                               "store_item_id": 20494}]}))  # fmt: skip
    shopping = await client.async_get_primary_list()
    assert shopping.name == "Indkøb"
    assert shopping.items[0].amount == 2

    session.on("GET", lists, FakeResponse(data={"data": [{"id": 5}]}))
    assert await client.async_get_primary_list_id() == 5
    session.on("GET", lists, FakeResponse(data={"data": []}))
    with pytest.raises(RemaApiError):
        await client.async_get_primary_list_id()

    items = f"{API}/v2/shoppinglists/2/items"
    session.on("POST", items, lambda **kw: FakeResponse(data={"sent": kw["json"]}))
    assert (await client.async_create_item(2, product_id=20494, amount=2))["sent"] == {
        "amount": 2, "store_id": 1, "store_item_id": 20494}  # fmt: skip
    assert (await client.async_create_item(2, name="Kage"))["sent"]["name"] == "Kage"
    with pytest.raises(ValueError):
        await client.async_create_item(2)

    session.on("PATCH", f"{items}/9", lambda **kw: FakeResponse(data=kw["json"]))
    assert await client.async_update_item(2, 9, bought=True) == {"bought": True}

    session.on("PATCH", f"{API}/v2/shoppinglists/2", FakeResponse(204))
    await client.async_delete_items(2, [])
    await client.async_delete_items(2, [9, 10])
    assert session.calls[-1][2]["json"] == {
        "items": [{"id": 9, "delete": True}, {"id": 10, "delete": True}]
    }


async def test_add_to_list_merges_like_the_app() -> None:
    """Existing lines get more; bought lines start over."""
    client, session = await logged_in()
    shopping = ShoppingList(
        2,
        "Indkøb",
        [
            ShoppingListItem(1, "RUGBRØD", True, 8, 60033),
            ShoppingListItem(2, "kage", False, 1, None),
        ],
    )
    session.on("PATCH", f"{API}/v2/shoppinglists/2/items/1", FakeResponse(data={}))
    session.on("PATCH", f"{API}/v2/shoppinglists/2/items/2", FakeResponse(data={}))
    session.on("POST", f"{API}/v2/shoppinglists/2/items", FakeResponse(data={}))
    await client.async_add_to_list(shopping, product_id=60033, amount=2)
    assert session.calls[-1][2]["json"] == {"amount": 2, "bought": False}
    await client.async_add_to_list(shopping, product_id=60033, amount=1)
    assert session.calls[-1][2]["json"] == {"amount": 3, "bought": False}
    await client.async_add_to_list(shopping, name="Kage", amount=2)
    assert session.calls[-1][2]["json"] == {"amount": 3, "bought": False}
    await client.async_add_to_list(shopping, name="Opvasketabs")
    assert session.calls[-1][0] == "POST"


async def test_favorites() -> None:
    """All pages are read, odd entries skipped, and the result cached."""
    client, session = await logged_in()
    url = f"{API}/v3/users/4242/favorites"
    pages = [
        FakeResponse(data={
            "data": [
                {"product": {"data": {"id": 1, "name": "MÆLK", "pricing": {"price": 10}}}},
                {"product": {"id": 2, "name": "SMØR"}},
                {"id": 3, "name": "ÆG"},
                {"product": {"id": 1, "name": "MÆLK"}},
                {"product": {"name": "no id"}},
                {"product": {"id": "x", "name": "bad"}},
                "odd",
            ],
            "meta": {"pagination": {"last_page": 2}},
        }),
        FakeResponse(data={"data": [{"product": {"id": 4, "name": "OST"}}]}),
    ]  # fmt: skip
    session.on("GET", url, *pages)
    favourites = await client.async_get_favorites()
    assert [p.id for p in favourites] == [1, 2, 3, 4]
    calls = len(session.calls)
    assert await client.async_get_favorites() is favourites
    assert len(session.calls) == calls
    session.on("GET", url, FakeResponse(data={"data": []}))
    assert await client.async_get_favorites(force=True) == []


# ------------------------------------------------------------------ offers


TJEK_HTML = 'x tjek:{api_key:"KEY",api_base_url:"https://tjek.example"} y'


async def test_catalogs_and_offers() -> None:
    """The Tjek key is read from the site, then catalogues and offers are fetched."""
    session = FakeSession()
    session.on("GET", f"{SHOP}/", aiohttp.ClientError("down"))
    session.on("GET", f"{SITE}/", FakeResponse(text=TJEK_HTML))
    session.on("GET", "https://tjek.example/v2/catalogs", FakeResponse(data=[
        {"id": "a", "label": "Uge 42", "run_from": "2026-10-11T00:00:00+02:00"},
        {"label": "no id"},
    ]))  # fmt: skip
    client = RemaClient(session, "a", "b")  # type: ignore[arg-type]
    catalogs = await client.async_get_catalogs()
    assert [c.id for c in catalogs] == ["a"]
    params = session.calls[-1][2]["params"]
    assert params["api_key"] == "KEY"
    assert params["dealer_ids"] == api.TJEK_DEALER_ID

    first = [{"id": i, "heading": f"Vare {i}"} for i in range(100)]
    session.on(
        "GET",
        "https://tjek.example/v2/offers",
        FakeResponse(data=first),
        FakeResponse(data=[{"id": 100, "heading": "Sidste"}]),
    )
    offers = await client.async_get_offers("a")
    assert len(offers) == 101
    assert offers[-1].heading == "Sidste"


async def test_offer_products() -> None:
    """Tjek says which REMA products an offer is for; they are fetched in one batch."""
    client, session = await logged_in()
    session.on("GET", f"{SHOP}/", FakeResponse(text=TJEK_HTML))
    rpc = "https://tjek.example/v4/rpc/get_offer_products"
    session.on(
        "POST",
        rpc,
        FakeResponse(data={"offer_products": [
            {"name": "KØDPØLSE", "external_id": "411655"},
            {"name": "PEBER SPEGEPØLSE", "external_id": "411652"},
            {"name": "IKKE I WEBSHOPPEN", "external_id": None},
            "x",
        ]}),
        FakeResponse(data={"offer_products": []}),
        aiohttp.ClientError("down"),
    )  # fmt: skip
    offers = [
        api.Offer("a", "Gøl spegepølse eller kødpølse", None, 10, None, None, None, None),
        api.Offer("b", "Partivare", None, 10, None, None, None, None),
        api.Offer("c", "Ukendt", None, 10, None, None, None, None),
    ]
    found = await client.async_get_offer_products(offers)
    assert [o.product_ids for o in found] == [(411655, 411652), (), None]
    # A product without REMA's id: the ids are not the whole offer.
    assert [o.unlinked for o in found] == [True, True, False]
    assert found[0].unlinked_names == ("IKKE I WEBSHOPPEN",)
    assert found[0].product_names == ("KØDPØLSE", "PEBER SPEGEPØLSE", "IKKE I WEBSHOPPEN")
    assert found[1].unlinked_names == ()  # Tjek lists nothing at all
    assert session.calls[-1][2]["json"] == {"id": "c"}
    calls = len(session.calls)
    await client.async_get_offer_products(offers[:2])  # cached
    assert len(session.calls) == calls

    product = {"id": 411655, "name": "KØDPØLSE", "underline": "110 GR. / GØL", "prices": [
        {"price": 10, "is_advertised": True, "starting_at": "2026-10-11T00:00:00+00:00",
         "ending_at": "2026-10-17T00:00:00+00:00"},
        {"price": 11.95, "starting_at": "2026-10-18T00:00:00+00:00",
         "ending_at": "2099-12-31T00:00:00+00:00"},
    ]}  # fmt: skip
    session.on("POST", f"{API}/v3/batch", FakeResponse(data=[
        {"status": 200, "body": {"data": product}},
        {"status": 404, "body": {"data": None}},
        {"status": 200, "body": {"data": {"id": "bad"}}},
        "x",
    ]))  # fmt: skip
    products = await client.async_get_products(
        [411655, 1, 2], datetime(2026, 10, 18, 10, tzinfo=UTC)
    )
    assert [(p.id, p.price) for p in products] == [(411655, 11.95)]
    assert session.calls[-1][2]["json"]["requests"][0] == {
        "uri": "/api/v3/products/411655",
        "method": "GET",
    }


async def test_tjek_errors() -> None:
    """A rejected key is read again next time; errors become RemaErrors."""
    session = FakeSession()
    session.on("GET", f"{SHOP}/", FakeResponse(text="no key here"))
    session.on("GET", f"{SITE}/", FakeResponse(500))
    client = RemaClient(session, "a", "b")  # type: ignore[arg-type]
    with pytest.raises(RemaApiError, match="Tjek"):
        await client.async_get_catalogs()

    session.on("GET", f"{SHOP}/", FakeResponse(text='tjek:{api_key:"K2"}'))
    session.on("GET", f"{api.TJEK_DEFAULT_BASE}/v2/catalogs", FakeResponse(403, text="no"))
    with pytest.raises(RemaApiError, match="HTTP 403"):
        await client.async_get_catalogs()
    assert client._tjek is None

    session.on("GET", f"{api.TJEK_DEFAULT_BASE}/v2/catalogs", aiohttp.ClientError("reset"))
    with pytest.raises(RemaConnectionError):
        await client.async_get_catalogs()
    session.on("GET", f"{api.TJEK_DEFAULT_BASE}/v2/catalogs", FakeResponse(data=None))
    assert await client.async_get_catalogs() == []


def test_parse_nutrition() -> None:
    """REMA's nutrition table per 100 g, as the app shows it."""
    table = [
        {"name": "Energi", "value": "932 KJ / 224 kcal"},
        {"name": "Fedt", "value": "16"},
        {"name": "Heraf mættede fedtsyrer", "value": "2,3"},
        {"name": "Kulhydrat", "value": "< 0,5"},
        {"name": "Kostfibre", "value": ""},
        {"name": "Protein", "value": "20"},
        {"name": "Salt", "value": "0,11"},
        "x",
    ]
    assert api.parse_nutrition(table) == {
        "kcal": 224.0, "fat_g": 16.0, "carbs_g": 0.0, "protein_g": 20.0, "salt_g": 0.11,
    }  # fmt: skip
    assert api.parse_nutrition([{"name": "Energi", "value": "932 KJ"}]) == {}
    assert api.parse_nutrition(None) == {}


async def test_get_nutrition() -> None:
    """Nutrition per product, fetched once."""
    client, session = await logged_in()
    salmon = {"data": {"id": 440095, "nutrition_info": [{"name": "Energi", "value": "224 kcal"}]}}
    session.on("GET", f"{API}/v3/products/440095", FakeResponse(data=salmon))
    session.on("GET", f"{API}/v3/products/1", FakeResponse(data={"data": {"id": 1}}))
    session.on("GET", f"{API}/v3/products/2", FakeResponse(404))
    found = await client.async_get_nutrition([440095, 1, 2, 440095])
    assert found == {440095: {"kcal": 224.0}}
    calls = len(session.calls)
    assert await client.async_get_nutrition([440095, 1]) == {440095: {"kcal": 224.0}}
    assert len(session.calls) == calls  # cached
