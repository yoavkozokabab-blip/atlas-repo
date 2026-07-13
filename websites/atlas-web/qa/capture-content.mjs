/** Captures the below-narrative home sections by scrolling to each. */
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const OUT = process.argv[2] || "./qa/shots";
const BASE = process.argv[3] || "http://localhost:3011";
const W = Number(process.argv[4] || 1440);
const H = Number(process.argv[5] || 900);
const TAG = process.argv[6] || "home";
mkdirSync(OUT, { recursive: true });

const sections = [
  ["cap", ".cap"],
  ["integrations", ".integ"],
  ["proof", ".proof-band"],
  ["localfirst", ".band"],
  ["faq", ".faq-sec"],
  ["download", ".dl-strip-sec"],
];

const browser = await chromium.launch({
  args: ["--enable-unsafe-swiftshader", "--use-gl=angle", "--use-angle=swiftshader", "--ignore-gpu-blocklist"],
});
const ctx = await browser.newContext({ viewport: { width: W, height: H }, colorScheme: "dark" });
const page = await ctx.newPage();
const errs = [];
page.on("pageerror", (e) => errs.push(e.message));
await page.goto(BASE + "/", { waitUntil: "load" });
await page.waitForTimeout(2500);

for (const [name, sel] of sections) {
  await page.evaluate((sel) => {
    const el = document.querySelector(sel);
    if (!el) return;
    const y = el.getBoundingClientRect().top + window.scrollY - 90;
    const lenis = window.__lenis;
    if (lenis) lenis.scrollTo(y, { immediate: true, force: true });
    else window.scrollTo(0, y);
  }, sel);
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${OUT}/${TAG}-${name}.png` });
  console.log(`OK ${TAG}-${name}`);
}
console.log("errors=", errs.length, errs.slice(0, 3).join(" | "));
await browser.close();
