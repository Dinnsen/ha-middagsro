/* Makes the README images in docs/images from the real panel with demo data.

   Needs Node and Playwright with Chromium:
     npm i -D playwright && npx playwright install chromium
     node scripts/screenshots/shoot.cjs
*/
const fs = require("fs");
const http = require("http");
const path = require("path");
const { chromium } = require("playwright");

const ROOT = path.resolve(__dirname, "../..");
const OUT = path.join(ROOT, "docs", "images");
const TMP = path.join(__dirname, ".phones");
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".png": "image/png", ".svg": "image/svg+xml", ".css": "text/css" };

function serve() {
  const server = http.createServer((req, res) => {
    const file = path.join(ROOT, decodeURIComponent(new URL(req.url, "http://x").pathname));
    if (!file.startsWith(ROOT) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
      res.writeHead(404).end();
      return;
    }
    res.writeHead(200, { "Content-Type": TYPES[path.extname(file)] || "application/octet-stream" });
    fs.createReadStream(file).pipe(res);
  });
  return new Promise((resolve) => server.listen(0, "127.0.0.1", () => resolve(server)));
}

async function open(browser, base, query, { width, height, scale = 2 }) {
  const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: scale, locale: "da-DK" });
  page.on("pageerror", (err) => console.error("page error:", err.message));
  await page.goto(`${base}/scripts/screenshots/demo.html?${query}`);
  await page.waitForSelector('body[data-ready="1"]');
  await page.waitForTimeout(300);
  return page;
}

/* A card, cut to at most `max` CSS pixels high. */
async function card(page, selector, file, max = 0, nth = 0) {
  const box = await page.locator(selector).nth(nth).boundingBox();
  const pad = 14;
  const clip = { x: box.x - pad, y: box.y - pad, width: box.width + pad * 2, height: (max ? Math.min(box.height, max) : box.height) + pad * 2 };
  await page.screenshot({ path: path.join(OUT, file), clip, fullPage: true });
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  fs.mkdirSync(TMP, { recursive: true });
  const server = await serve();
  const base = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch();
  const phone = { width: 390, height: 844, scale: 3 };
  const desk = { width: 1100, height: 1400, scale: 2 };

  // Phones for the top image.
  const phones = [
    ["plan", "tab=plan&narrow=1&phone=1&theme=light"],
    ["recipe", "tab=recipes&narrow=1&phone=1&theme=light&tick=i0,i1,i2,s0,s1&timer=s3"],
    ["shopping", "tab=shopping&narrow=1&phone=1&theme=dark"],
  ];
  for (const [name, query] of phones) {
    const page = await open(browser, base, query, phone);
    await page.screenshot({ path: path.join(TMP, `${name}.png`) });
    await page.close();
  }
  const hero = await browser.newPage({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1.5 });
  await hero.goto(`${base}/scripts/screenshots/hero.html`);
  await hero.waitForFunction(() => [...document.images].every((img) => img.complete && img.naturalWidth));
  await hero.screenshot({ path: path.join(OUT, "hero.png") });
  await hero.close();

  // Feature cut-outs on a computer screen.
  let page = await open(browser, base, "tab=plan", desk);
  await card(page, ".card", "plan.png");
  await page.close();

  page = await open(browser, base, "tab=recipes&tick=i0,i1,i2,s0,s1&timer=s3", desk);
  await card(page, ".card.recipe", "recipe.png");
  await page.close();

  page = await open(browser, base, "tab=shopping", desk);
  await card(page, ".card", "shopping.png", 760);
  await card(page, ".card", "rema-list.png", 0, 1);
  await page.close();

  page = await open(browser, base, "tab=favorites", desk);
  await card(page, ".card", "favorites.png");
  await page.close();

  page = await open(browser, base, "tab=history", desk);
  await card(page, ".card", "history.png");
  await page.close();

  page = await open(browser, base, "tab=settings", { ...desk, height: 4200 });
  await card(page, ".card", "settings.png", 838);
  await card(page, ".card", "family-favorites.png", 0, 1);
  await page.close();

  page = await open(browser, base, "tab=plan&theme=dark", desk);
  await card(page, ".card", "plan-dark.png");
  await page.close();

  await browser.close();
  server.close();
  fs.rmSync(TMP, { recursive: true, force: true });
  // Smaller files for the README, if sharp is installed.
  try {
    const sharp = require("sharp");
    for (const file of fs.readdirSync(OUT).filter((f) => f.endsWith(".png"))) {
      const full = path.join(OUT, file);
      const data = await sharp(full).png({ palette: true, quality: 90, effort: 10 }).toBuffer();
      fs.writeFileSync(full, data);
    }
  } catch (err) {
    if (err.code !== "MODULE_NOT_FOUND") throw err;
  }
  console.log("Images written to", path.relative(process.cwd(), OUT));
})();
