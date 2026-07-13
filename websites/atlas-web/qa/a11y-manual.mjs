/** Manual a11y checks: skip link, keyboard scroll, mobile Escape, reduced motion. */
import { chromium } from "playwright";

const BASE = process.argv[2] || "http://localhost:3011";
const OUT = process.argv[3] || "./qa/shots";
const browser = await chromium.launch({
  args: ["--enable-unsafe-swiftshader", "--use-gl=angle", "--use-angle=swiftshader", "--ignore-gpu-blocklist"],
});
let failures = 0;

function watchErrors(page) {
  const errs = [];
  page.on("console", (m) => { if (m.type() === "error") errs.push(m.text()); });
  page.on("pageerror", (e) => errs.push("PAGEERROR: " + e.message));
  return errs;
}

function mark(label, ok, detail = "") {
  if (!ok) failures += 1;
  console.log(label, detail, ok ? "PASS" : "FAIL");
}

// 1) skip link + keyboard scroll (desktop)
{
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  const errs = watchErrors(page);
  await page.goto(BASE + "/", { waitUntil: "load" });
  await page.waitForTimeout(1500);
  await page.keyboard.press("Tab");
  const first = await page.evaluate(() => {
    const a = document.activeElement;
    return { text: a?.textContent?.trim(), cls: a?.className, visibleY: a?.getBoundingClientRect().top };
  });
  mark("Tab#1 focus:", first.text === "Skip to content", JSON.stringify(first));

  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(200);
  await page.keyboard.press("End");
  await page.waitForTimeout(1200);
  const scrolledY = await page.evaluate(() => window.scrollY);
  mark("keyboard End scrollY:", scrolledY > 500, String(Math.round(scrolledY)));
  mark("fresh desktop console errors:", errs.length === 0, String(errs.length));
  await ctx.close();
}

// 2) mobile menu: open, Escape closes
{
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await ctx.newPage();
  const errs = watchErrors(page);
  await page.goto(BASE + "/", { waitUntil: "load" });
  await page.waitForTimeout(1200);
  await page.click('button[aria-label="Open menu"]');
  await page.waitForTimeout(300);
  const openState = await page.evaluate(() => !!document.querySelector('[role="dialog"]'));
  await page.keyboard.press("Escape");
  await page.waitForTimeout(300);
  const state = await page.evaluate(() => ({
    closed: !document.querySelector('[role="dialog"]'),
    focusLabel: document.activeElement?.getAttribute("aria-label"),
  }));
  mark("mobile panel opened/Escape closed/focus returned:", openState && state.closed && state.focusLabel === "Open menu", JSON.stringify({ openState, ...state }));
  mark("fresh mobile console errors:", errs.length === 0, String(errs.length));
  await ctx.close();
}

// 3) reduced motion: stable scene + acts present
{
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" });
  const page = await ctx.newPage();
  const errs = watchErrors(page);
  await page.goto(BASE + "/", { waitUntil: "load" });
  await page.waitForTimeout(2500);
  const state = await page.evaluate(() => ({
    canvasOrStatic: !!document.querySelector(".scene-root canvas") || !!document.querySelector("svg.static-scene"),
    acts: document.querySelectorAll(".nact").length,
    lenis: !!window.__lenis,
  }));
  mark("reduced-motion:", state.acts === 4 && !state.lenis, JSON.stringify(state));
  // scroll into narrative and screenshot to eyeball stability
  await page.evaluate(() => {
    const el = document.querySelector(".narrative");
    if (el) window.scrollTo(0, el.offsetTop + 0.68 * (el.offsetHeight - window.innerHeight));
  });
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${OUT}/a11y-reducedmotion-retrieval.png` });
  console.log("reduced-motion screenshot saved");
  mark("fresh reduced-motion console errors:", errs.length === 0, String(errs.length));
  await ctx.close();
}

await browser.close();
if (failures) process.exit(1);
