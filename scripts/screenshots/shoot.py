"""Makes the README images in docs/images from the real panel with demo data.

Needs Python Playwright with Chromium:  python3 scripts/screenshots/shoot.py
"""

from __future__ import annotations

import asyncio
import functools
import http.server
from pathlib import Path
import shutil
import threading

from playwright.async_api import Page, async_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "images"
TMP = Path(__file__).parent / ".phones"
PHONE = {"width": 390, "height": 844, "scale": 3}
DESK = {"width": 1100, "height": 1400, "scale": 2}


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass


def serve() -> http.server.ThreadingHTTPServer:
    handler = functools.partial(Quiet, directory=str(ROOT))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


async def open_page(browser, base: str, query: str, size: dict, js: str | None = None) -> Page:
    page = await browser.new_page(
        viewport={"width": size["width"], "height": size["height"]},
        device_scale_factor=size["scale"],
        locale="da-DK",
    )
    page.on("pageerror", lambda err: print("page error:", err))
    await page.goto(f"{base}/scripts/screenshots/demo.html?{query}")
    await page.wait_for_selector('body[data-ready="1"]')
    if js:
        await page.evaluate(
            f"async () => {{ const p = document.querySelector('middagsro-panel'); {js} }}"
        )
    await page.wait_for_timeout(400)
    return page


async def card(page: Page, selector: str, file: str, max_height: int = 0, nth: int = 0) -> None:
    """A card, cut to at most max_height CSS pixels high."""
    box = await page.locator(f"middagsro-panel >> {selector}").nth(nth).bounding_box()
    assert box, selector
    pad = 14
    height = min(box["height"], max_height) if max_height else box["height"]
    clip = {
        "x": box["x"] - pad,
        "y": box["y"] - pad,
        "width": box["width"] + pad * 2,
        "height": height + pad * 2,
    }
    await page.screenshot(path=str(OUT / file), clip=clip, full_page=True)


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    server = serve()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        phones = [
            ("plan", "tab=plan&narrow=1&phone=1&theme=light"),
            (
                "recipe",
                "tab=recipes&narrow=1&phone=1&theme=light&day=0&tick=i0,i1,i2,s0,s1&timer=s3",
            ),
            ("shopping", "tab=shopping&narrow=1&phone=1&theme=dark"),
        ]
        for name, query in phones:
            page = await open_page(browser, base, query, PHONE)
            await page.wait_for_timeout(300)
            await page.screenshot(path=str(TMP / f"{name}.png"))
            await page.close()
        hero = await browser.new_page(
            viewport={"width": 1600, "height": 900}, device_scale_factor=1.5
        )
        await hero.goto(f"{base}/scripts/screenshots/hero.html")
        await hero.wait_for_function(
            "[...document.images].every((img) => img.complete && img.naturalWidth)"
        )
        await hero.screenshot(path=str(OUT / "hero.png"))
        await hero.close()

        page = await open_page(browser, base, "tab=plan", DESK)
        await card(page, ".card", "plan.png", nth=1)
        await page.close()

        page = await open_page(
            browser, base, "tab=recipes&day=0&tick=i0,i1,i2,s0,s1&timer=s3", DESK
        )
        await card(page, ".card.recipe", "recipe.png")
        await page.close()

        page = await open_page(
            browser, base, "tab=recipes", DESK, "p._recipesSub = 'collection'; p._render();"
        )
        await card(page, ".card", "collection.png", nth=1)
        await page.close()

        page = await open_page(browser, base, "tab=shopping", DESK)
        await page.wait_for_timeout(300)
        await card(page, ".card", "shopping.png", 900)
        await card(page, ".card", "rema-list.png", nth=1)
        await page.close()

        page = await open_page(
            browser,
            base,
            "tab=shopping",
            DESK,
            "await new Promise((r) => setTimeout(r, 300));"
            "await p._ws('middagsro/chains/move', {plan_id: 'plan-43', line_id: 'l12', dealer_id: '9ba51', price: 22, heading: 'Danske frilandsæg'});"
            "await p._ws('middagsro/chains/move', {plan_id: 'plan-43', line_id: 'l11', dealer_id: '9ba51', price: 9.95, heading: 'Letmælk'});"
            "await p._load();",
        )
        await card(page, ".chain-list", "chains.png")
        await page.close()

        page = await open_page(browser, base, "tab=favorites", DESK)
        await card(page, ".card", "favorites.png")
        await page.close()

        page = await open_page(browser, base, "tab=history", DESK)
        await card(page, ".card", "history.png")
        await page.close()

        page = await open_page(browser, base, "tab=settings", DESK)
        await card(page, ".card", "settings.png")
        await page.close()

        page = await open_page(
            browser,
            base,
            "tab=settings",
            {**DESK, "height": 2400},
            "p._settingsSection = 'dishes'; p._render();",
        )
        await card(page, ".card", "family-favorites.png", nth=1)
        await page.close()

        page = await open_page(browser, base, "tab=plan&theme=dark", DESK)
        await card(page, ".card", "plan-dark.png", nth=1)
        await page.close()
        await browser.close()
    server.shutdown()
    shutil.rmtree(TMP, ignore_errors=True)
    print(
        "Images written to", OUT.relative_to(Path.cwd()) if OUT.is_relative_to(Path.cwd()) else OUT
    )


asyncio.run(main())
