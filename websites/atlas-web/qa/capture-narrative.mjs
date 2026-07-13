/** Captures each narrative act by scrolling to its progress position. */
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const OUT = process.argv[2] || "./qa/shots";
const BASE = process.argv[3] || "http://localhost:3011";
const W = Number(process.argv[4] || 1440);
const H = Number(process.argv[5] || 900);
const TAG = process.argv[6] || "narr";
mkdirSync(OUT, { recursive: true });

const steps = [
  { name: "enter", p: 0.12 },
  { name: "scan", p: 0.21 },
  { name: "memory", p: 0.46 },
  { name: "retrieval", p: 0.68 },
  { name: "converge", p: 0.93 },
];

const browser = await chromium.launch({
  args: ["--enable-unsafe-swiftshader", "--use-gl=angle", "--use-angle=swiftshader", "--ignore-gpu-blocklist"],
});
const ctx = await browser.newContext({ viewport: { width: W, height: H }, colorScheme: "dark" });
const page = await ctx.newPage();
const errs = [];
page.on("pageerror", (e) => errs.push(e.message));
await page.goto(BASE + "/", { waitUntil: "load" });
await page.waitForTimeout(3200); // intro

for (const s of steps) {
  await page.evaluate((p) => {
    const el = document.querySelector(".narrative");
    const top = el.offsetTop;
    const range = el.offsetHeight - window.innerHeight;
    const y = top + p * range;
    const lenis = window.__lenis;
    if (lenis) lenis.scrollTo(y, { immediate: true, force: true });
    else window.scrollTo(0, y);
  }, s.p);
  await page.waitForTimeout(750); // settle scene + act fade
  await page.evaluate(() => window.__atlasScene?.pause?.());
  await page.waitForTimeout(120);
  await page.screenshot({ path: `${OUT}/${TAG}-${s.name}.png` });
  await page.evaluate(() => window.__atlasScene?.resume?.());
  console.log(`OK ${TAG}-${s.name} p=${s.p}`);
}
console.log("errors=", errs.length, errs.slice(0, 3).join(" | "));
await browser.close();
