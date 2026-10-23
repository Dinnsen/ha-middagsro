"""Makes the README images in docs/images from the real panel with demo data.

Needs Python Playwright with Chromium:  python3 scripts/screenshots/shoot.py
"""

from __future__ import annotations

import asyncio
import functools
import http.server
import os
from pathlib import Path
import shutil
import threading

from PIL import Image
from playwright.async_api import Page, async_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "images"
TMP = Path(__file__).parent / ".phones"
PHONE = {"width": 390, "height": 844, "scale": 3}
CROP = {"width": 390, "height": 2400, "scale": 3}  # tall, so a whole card fits
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


async def js(page: Page, code: str) -> None:
    """Run code with p (the panel) and r (its shadow root)."""
    await page.evaluate(
        "async () => { const p = document.querySelector('middagsro-panel');"
        f" const r = p.shadowRoot; {code} }}"
    )
    await page.wait_for_timeout(300)


async def crop(
    page: Page, first: str, last: str | None = None, nth: int = 0, pad: int = 14
) -> Image.Image:
    """From one element's top to another's bottom (or the same one), as an image."""
    await js(page, "r.querySelector('.tabs').style.display = 'none';")  # the phone's tab bar
    top = await page.locator(f"middagsro-panel >> {first}").nth(nth).bounding_box()
    bottom = await page.locator(f"middagsro-panel >> {last or first}").nth(nth).bounding_box()
    assert top and bottom, first
    clip = {
        "x": top["x"] - pad,
        "y": top["y"] - pad,
        "width": top["width"] + pad * 2,
        "height": bottom["y"] + bottom["height"] - top["y"] + pad * 2,
    }
    path = TMP / "crop.png"
    await page.screenshot(path=str(path), clip=clip, full_page=True)
    return Image.open(path).convert("RGB")


def strip(images: list[Image.Image], file: str, background: tuple[int, ...] | None = None) -> None:
    """Phone-sized cut-outs side by side, top-aligned, on the panel's background."""
    gap = 36
    background = background or images[0].getpixel((2, 2))
    width = sum(i.width for i in images) + gap * (len(images) - 1)
    out = Image.new("RGB", (width, max(i.height for i in images)), background)
    x = 0
    for image in images:
        out.paste(image, (x, 0))
        x += image.width + gap
    out.save(OUT / file, optimize=True)


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    server = serve()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    async with async_playwright() as pw:
        # Danish dates in the date fields (dd.mm.åååå) need the browser's own language too.
        browser = await pw.chromium.launch(
            args=["--lang=da-DK"], env={**os.environ, "LANG": "da_DK.UTF-8", "LANGUAGE": "da"}
        )
        phones = [
            ("plan", "tab=plan&narrow=1&phone=1&theme=light"),
            (
                "recipe",
                "tab=recipes&narrow=1&phone=1&theme=light&day=0&tick=i0,i1,i2,s0,s1&timer=s3",
            ),
            ("budget", "tab=budget&narrow=1&phone=1&theme=dark"),
        ]
        for name, query in phones:
            page = await open_page(browser, base, query, PHONE)
            if name == "budget":  # the month's chart, under the week
                await page.evaluate("window.scrollTo(0, 330)")
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
        await card(page, ".card", "favorites.png", nth=1)
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

        # The food budget: the week on the front page, the month, the weeks and the year.
        chart = ".card:has(.budget-chart)"
        page = await open_page(browser, base, "tab=plan&narrow=1", CROP)
        week = await crop(page, ".budget-card")
        await page.close()
        page = await open_page(browser, base, "tab=budget&narrow=1", CROP)
        month = await crop(page, ".stats", chart)
        numbers = await crop(page, ".stats", nth=1)
        await js(page, "p._budgetSpan = 'weeks'; p._render();")
        weeks = await crop(page, chart, ".stats:last-of-type")
        await js(page, "p._budgetSpan = 'year'; p._render();")
        year = await crop(page, chart, ".stats:last-of-type")
        await js(page, "p._budgetSpan = 'purchases'; p._render();")
        purchases = await crop(page, ".card:has(ul.purchases)")
        await page.close()
        panel = week.getpixel((2, 2))
        strip([week, month, weeks], "budget.png")
        strip([numbers, year, purchases.crop((0, 0, purchases.width, 1500))], "budget-year.png")

        # The plan's tools: a day's menu, three other dishes, what the AI must remember.
        page = await open_page(browser, base, "tab=plan&narrow=1&ai=0.2", CROP)
        new_plan = await crop(page, ".card:has([data-action=surprise])")
        remember = await crop(page, ".card:has(textarea)")
        await js(page, "r.querySelectorAll('[data-action=day-menu]')[2].click();")
        menu = await crop(page, ".dialog", pad=0)
        await js(page, "r.querySelector('.dialog [data-action=swap-options]').click();")
        await page.wait_for_timeout(900)
        options = await crop(page, ".dialog", pad=0)
        await page.close()
        strip([menu, options, remember], "plan-tools.png", panel)
        strip([new_plan], "new-plan.png")

        page = await open_page(browser, base, "tab=favorites", DESK)
        await card(page, ".card", "watch.png")
        await page.close()

        page = await open_page(
            browser,
            base,
            "tab=plan",
            DESK,
            "const i = p.shadowRoot.querySelector('input[data-bind=everywhere]');"
            "i.value = 'mælk'; i.dispatchEvent(new Event('change', {bubbles: true}));"
            "await new Promise((r) => setTimeout(r, 900));",
        )
        await card(page, ".card:has(.chain-btn)", "search.png", 1000)
        await page.close()

        page = await open_page(
            browser,
            base,
            "tab=recipes",
            DESK,
            "p.shadowRoot.querySelector('[data-action=recipes-sub][data-arg=rema]').click();"
            "await new Promise((r) => setTimeout(r, 900));",
        )
        await card(page, ".card", "rema-recipes.png", 900)
        await page.close()

        page = await open_page(
            browser, base, "tab=health", DESK, "await new Promise((r) => setTimeout(r, 1200));"
        )
        await card(page, ".card", "health.png")
        await card(page, ".card", "health-advice.png", nth=1)
        await page.close()
        await browser.close()
    server.shutdown()
    shutil.rmtree(TMP, ignore_errors=True)
    print(
        "Images written to", OUT.relative_to(Path.cwd()) if OUT.is_relative_to(Path.cwd()) else OUT
    )


asyncio.run(main())
