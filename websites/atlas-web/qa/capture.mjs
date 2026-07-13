/**
 * Playwright visual-QA capture for the Atlas site.
 * Usage: node qa/capture.mjs [outDir] [baseUrl]
 * Forces SwiftShader so the WebGL constellation renders headless.
 */
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const OUT = process.argv[2] || "./qa/shots";
const BASE = process.argv[3] || "http://localhost:3011";
mkdirSync(OUT, { recursive: true });

const shots = [
  { name: "home-desktop-hero", path: "/", w: 1440, h: 900, wait: 3400 },
  { name: "home-desktop-scroll40", path: "/", w: 1440, h: 900, wait: 3400, scroll: 0.4 },
  { name: "home-desktop-scroll75", path: "/", w: 1440, h: 900, wait: 3400, scroll: 0.75 },
  { name: "home-1920-hero", path: "/", w: 1920, h: 1080, wait: 3400 },
  { name: "home-mobile-hero", path: "/", w: 390, h: 844, wait: 3400 },
  { name: "howitworks-desktop", path: "/how-it-works", w: 1440, h: 900, wait: 1000 },
  { name: "integrations-desktop", path: "/integrations", w: 1440, h: 900, wait: 1000 },
];

const browser = await chromium.launch({
  args: [
    "--enable-unsafe-swiftshader",
    "--use-gl=angle",
    "--use-angle=swiftshader",
    "--ignore-gpu-blocklist",
    "--enable-webgl",
  ],
});

for (const s of shots) {
  const ctx = await browser.newContext({
    viewport: { width: s.w, height: s.h },
    deviceScaleFactor: 1,
    colorScheme: "dark",
  });
  const page = await ctx.newPage();
  const errs = [];
  page.on("console", (m) => { if (m.type() === "error") errs.push(m.text()); });
  page.on("pageerror", (e) => errs.push("PAGEERROR: " + e.message));
  try {
    await page.goto(BASE + s.path, { waitUntil: "load", timeout: 30000 });
    await page.waitForTimeout(s.wait);
    if (s.scroll) {
      await page.evaluate((f) => window.scrollTo(0, document.body.scrollHeight * f), s.scroll);
      await page.waitForTimeout(900);
    }
    await page.evaluate(() => { const w = window; if (w.__atlasScene?.pause) w.__atlasScene.pause(); });
    await page.waitForTimeout(150);
    await page.screenshot({ path: `${OUT}/${s.name}.png`, fullPage: false });
    console.log(`OK  ${s.name} @ ${s.w}x${s.h}  errors=${errs.length}${errs.length ? " :: " + errs.slice(0, 3).join(" | ") : ""}`);
  } catch (e) {
    console.log(`FAIL ${s.name}: ${e.message}`);
  }
  await ctx.close();
}

await browser.close();
console.log("CAPTURE_DONE ->", OUT);
