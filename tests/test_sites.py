"""Tests for 2.6.0: recipes from the family's recipe sites (Valdemarsro, Madens Verden ...)."""

from __future__ import annotations

from datetime import date
import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.middagsro import mealplan as mp, planedit as pe, recipes as rc, sites
from custom_components.middagsro.storage import clean_settings
import homeassistant.components.ai_task as ai_task_component  # noqa: F401 - patched in the tests
from homeassistant.core import HomeAssistant

from .test_planedit import RECIPE
from .test_recipes import PAGE

VALDEMARSRO = "https://www.valdemarsro.dk"
MADENSVERDEN = "https://madensverden.dk"

ROBOTS = f"""User-agent: Googlebot
Disallow: /alt/
User-agent: *
Disallow: /wp-admin/  # admin
Disallow: /hemmelig-
Disallow: /*-print$
Sitemap: {VALDEMARSRO}/sitemap_index.xml
"""

INDEX = f"""<?xml version="1.0"?><sitemapindex>
<sitemap><loc>{VALDEMARSRO}/post-sitemap.xml</loc></sitemap>
<sitemap><loc>{VALDEMARSRO}/page-sitemap.xml</loc></sitemap>
<sitemap><loc>{VALDEMARSRO}/post-sitemap2.xml</loc></sitemap>
<sitemap><loc>{VALDEMARSRO}/post-sitemap.xml</loc></sitemap>
<sitemap><loc>https://example.com/post-sitemap.xml</loc></sitemap>
</sitemapindex>"""

POSTS = f"""<?xml version="1.0"?><urlset>
<url><loc>{VALDEMARSRO}/kylling-i-karry/</loc></url>
<url><loc><![CDATA[{VALDEMARSRO}/kylling-i-karry-med-ris-og-mango/]]></loc></url>
<url><loc>{VALDEMARSRO}/karrykylling/</loc></url>
<url><loc>{VALDEMARSRO}/madplan-uge-43/</loc></url>
<url><loc>{VALDEMARSRO}/hemmelig-kylling-karry/</loc></url>
<url><loc>{VALDEMARSRO}/kylling-karry-print</loc></url>
<url><loc>{VALDEMARSRO}/opskrifter/kylling/karry/</loc></url>
<url><loc>{VALDEMARSRO}/frikadeller-med-kartoffelsalat/</loc></url>
<url><loc>{VALDEMARSRO}/broendkarse-suppe/</loc></url>
<url><loc>https://example.com/kylling-karry/</loc></url>
</urlset>"""


def test_words_and_titles() -> None:
    """Addresses write æ, ø and å as ae, oe and aa; titles are guessed back."""
    assert sites.ascii_words("Brøndkarse-suppe & Æblekage") == ["broendkarse", "suppe", "aeblekage"]
    assert sites.title_from_slug("/kylling-i-hvidloegssauce/") == "Kylling i hvidløgssauce"
    assert sites.title_from_slug("") == ""
    assert sites.site_of("https://valdemarsro.dk/lasagne/") is sites.SITES["valdemarsro"]
    assert sites.site_of("https://www.madensverden.dk/x/") is sites.SITES["madensverden"]
    assert sites.site_of("https://example.com/lasagne/") is None


async def test_search(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """The sitemaps are read once a day, and the best matches come first."""
    aioclient_mock.get(f"{VALDEMARSRO}/robots.txt", text=ROBOTS)
    aioclient_mock.get(f"{VALDEMARSRO}/sitemap_index.xml", text=INDEX)
    aioclient_mock.get(f"{VALDEMARSRO}/post-sitemap.xml", text=POSTS)
    aioclient_mock.get(f"{VALDEMARSRO}/post-sitemap2.xml", status=500)
    # No robots.txt: the usual sitemap addresses.
    aioclient_mock.get(f"{MADENSVERDEN}/robots.txt", exc=aiohttp.ClientError("nede"))
    aioclient_mock.get(
        f"{MADENSVERDEN}/sitemap.xml",
        text=f"<urlset><url><loc>{MADENSVERDEN}/kylling-karry/</loc></url></urlset>",
    )
    aioclient_mock.get(f"{MADENSVERDEN}/sitemap_index.xml", exc=TimeoutError())
    finder = sites.RecipeSites(hass)
    finder._async_titles = AsyncMock()  # type: ignore[method-assign]

    found = await finder.async_search(["valdemarsro", "madensverden", "ukendt"], "Kylling karry")
    assert [hit["url"] for hit in found] == [
        f"{MADENSVERDEN}/kylling-karry/",
        f"{VALDEMARSRO}/kylling-i-karry/",
        f"{VALDEMARSRO}/kylling-i-karry-med-ris-og-mango/",
        f"{VALDEMARSRO}/karrykylling/",
    ]
    assert found[1] == {
        "site": "valdemarsro",
        "site_name": "Valdemarsro",
        "url": f"{VALDEMARSRO}/kylling-i-karry/",
        "title": "Kylling i karry",
    }
    assert [h["title"] for h in await finder.async_search(["valdemarsro"], "brøndkarse")] == [
        "Brøndkarse suppe"
    ]
    calls = aioclient_mock.call_count
    assert await finder.async_search(["valdemarsro"], "frikadeller") != []
    assert aioclient_mock.call_count == calls  # kept (half an hour, as a sitemap failed)
    assert await finder.async_search(["valdemarsro"], "i og") == []  # no real words
    assert await finder.async_search(["valdemarsro"], "madplan") == []  # not a recipe

    # A few from each site, so one big site doesn't fill the list.
    many = "".join(f"<url><loc>{VALDEMARSRO}/suppe-{i}/</loc></url>" for i in range(30))
    finder._indexes.clear()
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{VALDEMARSRO}/robots.txt", status=404)
    aioclient_mock.get(f"{VALDEMARSRO}/sitemap.xml", text=f"<urlset>{many}</urlset>")
    aioclient_mock.get(f"{VALDEMARSRO}/sitemap_index.xml", status=404)
    aioclient_mock.get(f"{MADENSVERDEN}/robots.txt", text=f"Sitemap: {MADENSVERDEN}/sitemap.xml")
    aioclient_mock.get(
        f"{MADENSVERDEN}/sitemap.xml",
        text=f"<urlset><url><loc>{MADENSVERDEN}/suppe/</loc></url></urlset>",
    )
    found = await finder.async_search(["valdemarsro", "madensverden"], "suppe", limit=6)
    assert len(found) == 5
    assert found[0]["url"] == f"{MADENSVERDEN}/suppe/"


async def test_search_keeps_the_last_index(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A site that is down keeps the recipes read before."""
    aioclient_mock.get(f"{VALDEMARSRO}/robots.txt", status=500)
    aioclient_mock.get(f"{VALDEMARSRO}/sitemap.xml", status=500)
    aioclient_mock.get(f"{VALDEMARSRO}/sitemap_index.xml", status=500)
    finder = sites.RecipeSites(hass)
    finder._async_titles = AsyncMock()  # type: ignore[method-assign]
    finder._indexes["valdemarsro"] = sites._Index(
        [(f"{VALDEMARSRO}/lasagne/", frozenset({"lasagne"}), "Lasagne")], [], -1e9
    )
    assert [h["title"] for h in await finder.async_search(["valdemarsro"], "lasagne")] == [
        "Lasagne"
    ]
    assert finder._indexes["valdemarsro"].failed == 1
    calls = aioclient_mock.call_count
    await finder.async_search(["valdemarsro"], "lasagne")
    assert aioclient_mock.call_count == calls  # tried again in half an hour
    finder._indexes["valdemarsro"].loaded -= sites.RETRY_SECONDS + 1
    assert not finder._indexes["valdemarsro"].fresh()
    finder._indexes["valdemarsro"].failed = 0
    assert finder._indexes["valdemarsro"].fresh()  # a day, when all was read


async def test_titles(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """The hits get the titles of their pages (addresses leave out æ, ø and å)."""
    finder = sites.RecipeSites(hass)
    urls = [f"{VALDEMARSRO}/{slug}/" for slug in ("aben-lasagne", "karry", "nede", "fejl")]
    aioclient_mock.get(urls[0], text="<html><h1>\n Åben <em>lasagne</em></h1></html>")
    aioclient_mock.get(
        urls[1],
        text='<meta property="og:title" content="Kylling i karry - Valdemarsro">',
    )
    aioclient_mock.get(urls[2], status=404)
    aioclient_mock.get(urls[3], exc=aiohttp.ClientError("nede"))
    hits = [{"url": url, "title": "Slug"} for url in urls]
    await finder._async_titles(hits)
    assert [h["title"] for h in hits] == ["Åben lasagne", "Kylling i karry", "Slug", "Slug"]
    calls = aioclient_mock.call_count
    await finder._async_titles([{"url": urls[0], "title": "Slug"}])
    assert aioclient_mock.call_count == calls  # kept


def test_page_title() -> None:
    """A page's heading, else og:title or <title> without the site's name."""
    assert sites.page_title("<h1> </h1><title>Lasagne | Arla</title>") == "Lasagne"
    assert sites.page_title("<title>Boller i karry – DK-kogebogen</title>") == "Boller i karry"
    assert sites.page_title("<p>Ingen titel</p>") == ""


async def test_recipe(hass: HomeAssistant) -> None:
    """A recipe is read from its page, in the collection's shape."""
    finder = sites.RecipeSites(hass)
    url = f"{VALDEMARSRO}/kylling-i-karry/"
    with patch.object(sites, "async_fetch_page", AsyncMock(return_value=PAGE)):
        recipe = await finder.async_recipe(url)
    assert recipe is not None
    assert recipe["name"] == "Kylling i karry & ris"
    assert recipe["source"] == "web"
    assert recipe["site"] == "Valdemarsro"
    assert recipe["url"] == url
    assert recipe["id"] is None
    assert recipe["ingredients"][0] == {"amount": "600 g", "name": "kyllingebryst"}
    with patch.object(sites, "async_fetch_page", AsyncMock(return_value=PAGE)):
        other = await finder.async_recipe("https://example.com/kylling/")
    assert other is not None
    assert other["site"] == "example.com"
    with patch.object(sites, "async_fetch_page", AsyncMock(return_value="<html></html>")):
        assert await finder.async_recipe(url) is None


async def test_candidates(hass: HomeAssistant) -> None:
    """A few recipes for each of the week's main items; a page that fails is left out."""
    finder = sites.RecipeSites(hass)
    hits = {
        "kylling": [{"url": "a"}, {"url": "b"}, {"url": "c"}, {"url": "d"}],
        "laks": [{"url": "b"}, {"url": "fejl"}],
    }

    async def search(
        site_ids: list[str], query: str, limit: int = 40, titles: bool = True
    ) -> list[dict[str, Any]]:
        assert not titles
        return hits[query]

    async def recipe(url: str) -> dict[str, Any] | None:
        if url == "fejl":
            raise aiohttp.ClientError("nede")
        return None if url == "c" else {"name": url}

    with (
        patch.object(finder, "async_search", side_effect=search),
        patch.object(finder, "async_recipe", side_effect=recipe),
    ):
        found = await finder.async_candidates(["valdemarsro"], ["kylling", "laks"])
    assert found == [{"name": "a"}, {"name": "b"}]


def test_settings() -> None:
    """Only known sites are kept."""
    settings = clean_settings({"recipe_sites": ["arla", "ukendt", 3], "recipe_sites_in_plan": 1})
    assert settings["recipe_sites"] == ["arla"]
    assert settings["recipe_sites_in_plan"] is True
    assert clean_settings({})["recipe_sites"] == []
    assert clean_settings({})["recipe_sites_in_plan"] is False


def test_prompt_has_the_sites_recipes() -> None:
    """The AI is offered the sites' recipes, except when it surprises the family."""
    web = [
        {
            "id": "web1",
            "name": "Kylling i karry",
            "site": "Valdemarsro",
            "ingredients": [{"amount": "600 g", "name": "kyllingebryst"}],
        }
    ]
    kwargs: dict[str, Any] = {
        "settings": clean_settings({}),
        "dates": [date(2026, 10, 25)],
        "catalog": None,
        "offers": [],
        "favorites_due": [],
        "favorites_optional": [],
        "recent_dishes": [],
        "web": web,
    }
    prompt = mp.build_prompt(**kwargs)
    assert "OPSKRIFTER FRA FAMILIENS MADSIDER" in prompt
    assert "web1 | Kylling i karry | Valdemarsro | 600 g kyllingebryst" in prompt
    assert "MADSIDER" not in mp.build_prompt(**kwargs, surprise=True)


async def test_plan_from_the_sites(
    hass: HomeAssistant, init_integration: MockConfigEntry, ai_task: str
) -> None:
    """A recipe from the sites that the AI chose is saved in the collection."""
    planner = init_integration.runtime_data.planner
    store = planner.store
    web_recipe = rc.clean_recipe(
        {
            "name": "Kylling i karry",
            "type": "normal",
            "source": "web",
            "ingredients": [{"amount": "600 g", "name": "kyllingebryst"}],
            "steps": [{"text": "Steg kyllingen.", "minutes": 10}],
        }
    ) | {"id": None, "site": "Valdemarsro", "url": f"{VALDEMARSRO}/kylling-i-karry/"}
    answer = {
        "days": [
            {"date": "2026-10-25", "dish": "Kylling i karry", "recipe_id": "web1"},
            {"date": "2026-10-26", "dish": "Kylling i karry igen", "recipe_id": "web1"},
        ],
        "shopping": [],
    }
    prompts: list[str] = []

    async def fake(hass: HomeAssistant, **kwargs: Any) -> SimpleNamespace:
        if kwargs["task_name"] == "REMA 1000 madplan":
            prompts.append(kwargs["instructions"])
            return SimpleNamespace(data=json.loads(json.dumps(answer)))
        return SimpleNamespace(data=RECIPE)

    await store.async_set_settings(
        {"days": 2, "recipe_sites": ["valdemarsro"], "recipe_sites_in_plan": True}
    )
    planner._get_catalogs = lambda: (None, None)
    candidates = AsyncMock(return_value=[web_recipe])
    with (
        patch("homeassistant.components.ai_task.async_generate_data", new=fake),
        patch.object(planner.sites, "async_candidates", candidates),
    ):
        plan = await planner.async_generate(date(2026, 10, 25))
    assert "web1 | Kylling i karry | Valdemarsro" in prompts[0]
    assert candidates.call_args.args[1] == ["aftensmad"]  # no offers known
    first, second = plan["days"]
    saved = rc.find_recipe(store, first["recipe_id"])
    assert saved is not None
    assert saved["source"] == "web"
    assert saved["url"] == f"{VALDEMARSRO}/kylling-i-karry/"
    assert saved["site"] == "Valdemarsro"
    assert second["recipe_id"] == first["recipe_id"]  # saved once
    assert first["steps"] == [{"text": "Steg kyllingen.", "minutes": 10}]
    assert sum(r.get("source") == "web" for r in store.recipes) == 1

    # Next time the family's own copy (with their changes) is used, not the site's.
    saved["name"] = "Mors kylling i karry"
    with (
        patch("homeassistant.components.ai_task.async_generate_data", new=fake),
        patch.object(planner.sites, "async_candidates", candidates),
    ):
        plan = await planner.async_generate(date(2026, 10, 25))
    assert plan["days"][0]["recipe_id"] == saved["id"]
    assert rc.find_recipe(store, saved["id"])["name"] == "Mors kylling i karry"  # type: ignore[index]


async def test_site_recipes_for_the_offers(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """The week's main offers decide what is looked for; a site that fails is skipped."""
    planner = init_integration.runtime_data.planner
    offers = [
        SimpleNamespace(heading="Hel kylling"),
        SimpleNamespace(heading="Laksefilet og kylling"),
        SimpleNamespace(heading="Bananer"),
    ]
    assert await planner._async_site_recipes([], offers) == []  # type: ignore[arg-type]
    candidates = AsyncMock(return_value=[{"name": "a"}, {"name": "b"}])
    with patch.object(planner.sites, "async_candidates", candidates):
        found = await planner._async_site_recipes(["arla"], offers)  # type: ignore[arg-type]
    assert found == [{"name": "a", "id": "web1"}, {"name": "b", "id": "web2"}]
    assert candidates.call_args.args == (["arla"], ["kylling", "laks"])
    with patch.object(planner.sites, "async_candidates", AsyncMock(side_effect=RuntimeError)):
        assert await planner._async_site_recipes(["arla"], offers) == []  # type: ignore[arg-type]


async def test_pick_from_the_sites(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """A dish chosen from the sites is saved and put on its day."""
    planner = init_integration.runtime_data.planner
    plan = planner.store.plans[0]
    recipe = rc.clean_recipe(
        {"name": "Boller i karry", "type": "normal", "source": "web", "ingredients": []}
    ) | {"id": None, "site": "Arla", "url": "https://www.arla.dk/opskrifter/boller-i-karry/"}
    swapped: list[dict[str, Any]] = []

    async def swap(planner: Any, plan_id: str, day: str, option: dict[str, Any]) -> dict[str, Any]:
        swapped.append(option)
        return plan

    with (
        patch.object(pe, "async_swap_dish", side_effect=swap),
        patch.object(planner.sites, "async_recipe", AsyncMock(side_effect=[recipe, None])),
    ):
        await planner._async_put_picks(
            plan,
            {
                "2026-10-18": {"dish": "Boller", "source": "web", "url": recipe["url"]},
                "2026-10-19": {"dish": "Væk", "source": "web", "url": "https://www.arla.dk/x/"},
            },
        )
    assert swapped[0]["dish"] == "Boller i karry"
    assert rc.find_recipe(planner.store, swapped[0]["recipe_id"])["url"] == recipe["url"]  # type: ignore[index]
    assert len(swapped) == 1  # the page without a recipe is skipped


async def test_websocket(
    hass: HomeAssistant, init_integration: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """The panel searches the chosen sites and opens a recipe from them."""
    client = await hass_ws_client(hass)
    planner = init_integration.runtime_data.planner

    async def ws(msg_id: int, **msg: Any) -> dict[str, Any]:
        await client.send_json({"id": msg_id, **msg})
        result: dict[str, Any] = await client.receive_json()
        return result

    msg = await ws(1, type="middagsro/state")
    assert {"id": "arla", "name": "Arla"} in msg["result"]["recipe_sites"]

    search = AsyncMock(return_value=[{"title": "Lasagne"}])
    with patch.object(planner.sites, "async_search", search):
        msg = await ws(2, type="middagsro/sites/search", query="lasagne")
        assert msg["result"] == {"results": []}  # no sites chosen
        await planner.store.async_set_settings({"recipe_sites": ["valdemarsro"]})
        msg = await ws(3, type="middagsro/sites/search", query="lasagne")
    assert msg["result"] == {"results": [{"title": "Lasagne"}]}
    assert search.call_args.args == (["valdemarsro"], "lasagne")
    with patch.object(planner.sites, "async_search", search):
        msg = await ws(4, type="middagsro/sites/search", query="lasagne", sites=["arla"])
    assert search.call_args.args == (["arla"], "lasagne")

    msg = await ws(5, type="middagsro/sites/recipe", url="https://example.com/lasagne/")
    assert not msg["success"]
    recipe = {"name": "Lasagne", "source": "web"}
    with patch.object(planner.sites, "async_recipe", AsyncMock(side_effect=[recipe, None])):
        msg = await ws(6, type="middagsro/sites/recipe", url=f"{VALDEMARSRO}/lasagne/")
        assert msg["result"] == recipe
        msg = await ws(7, type="middagsro/sites/recipe", url=f"{VALDEMARSRO}/lasagne/")
    assert not msg["success"]


@pytest.fixture
def storage_contents() -> dict[str, Any]:
    """A plan from sunday 18/10."""
    from .conftest import make_plan  # noqa: PLC0415

    return {"plans": [make_plan("p", start="2026-10-18")]}


MICRODATA = """<html><h1>Lasagne</h1><div itemscope itemtype="https://schema.org/Recipe">
<meta itemprop="totalTime" content="PT3H"><span itemprop="prepTime">PT40M</span>
<span itemprop="recipeYield">4 personer</span><span itemprop="recipeCategory">Aftensmad</span>
<h2 itemprop="name">Lasagne &amp; kødsovs</h2><img itemprop="image" src="x.jpg"/>
<ul><li itemprop="recipeIngredient">500 g hakket oksekød</li>
<li itemprop="ingredients"><span>2</span>
 løg</li><li itemprop="recipeIngredient"> </li></ul>
<div itemprop="recipeInstructions"><ol><li>Brun kødet.</li><li>Lag lasagnen.</li></ol></div>
<p itemprop="recipeInstructions">Bag den.<br>Server.</p>
<p itemprop="description">God og klassisk</p></div></html>"""


def test_microdata() -> None:
    """A page with the recipe as microdata (itemprop) instead of JSON-LD."""
    recipe = rc.parse_recipe_page(MICRODATA)
    assert recipe == {
        "name": "Lasagne",
        "servings": 4,
        "total_minutes": 180,
        "active_minutes": 40,
        "type": "normal",
        "ingredients": ["500 g hakket oksekød", "2 løg"],
        "steps": ["Brun kødet.", "Lag lasagnen.", "Bag den.", "Server."],
        "tip": "God og klassisk",
    }
    nameless = MICRODATA.replace('itemprop="name"', "")
    assert rc.parse_recipe_page(nameless)["name"] == "Lasagne"  # type: ignore[index]
    named = MICRODATA.replace("<h1>Lasagne</h1>", "<h1> </h1>")
    assert rc.parse_recipe_page(named)["name"] == "Lasagne & kødsovs"  # type: ignore[index]
    assert rc.parse_recipe_page(nameless.replace("<h1>Lasagne</h1>", "")) is None
    assert rc.parse_recipe_page(MICRODATA.replace("recipeIngredient", "x").replace(
        "ingredients", "x")) is None  # fmt: skip
    assert rc.parse_recipe_page("<p>Ingen opskrift</p>") is None
    # Line breaks inside the JSON-LD texts.
    page = '<script type="application/ld+json">{"@type": "Recipe", "name": "A",\n'
    page += '"recipeIngredient": ["1 løg\nhakket"]}</script>'
    assert rc.parse_recipe_page(page)["ingredients"] == ["1 løg\nhakket"]  # type: ignore[index]


async def test_page_session(hass: HomeAssistant) -> None:
    """One session for the recipe sites, with room for long headers."""
    session = rc.page_session(hass)
    assert rc.page_session(hass) is session


async def test_recipe_read_by_the_ai(hass: HomeAssistant) -> None:
    """A page without recipe data is read by the AI, when the panel asks for it."""
    finder = sites.RecipeSites(hass)
    url = f"{VALDEMARSRO}/lasagne/"
    extract = AsyncMock(return_value={"name": "Lasagne", "ingredients": ["500 g oksekød"]})
    with patch.object(sites, "async_fetch_page", AsyncMock(return_value="<p>Lasagne</p>")):
        recipe = await finder.async_recipe(url, extract)
        assert extract.call_args.args == ("<p>Lasagne</p>",)
        assert recipe is not None
        assert recipe["name"] == "Lasagne"
        assert recipe["site"] == "Valdemarsro"
        extract.return_value = {"name": "Intet"}
        assert await finder.async_recipe(url, extract) is None
