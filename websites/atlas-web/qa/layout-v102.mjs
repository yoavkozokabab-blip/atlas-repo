/**
 * Atlas v1.0.2 layout QA — overflow, padding, button height, nav usability.
 * Usage: node qa/layout-v102.mjs http://localhost:3012 ./qa/shots/layout-v102
 */
import { chromium } from "playwright";
import { mkdirSync, writeFileSync } from "node:fs";

const BASE = process.argv[2] || "http://localhost:3012";
const OUT = process.argv[3] || "./qa/shots/layout-v102";
mkdirSync(OUT, { recursive: true });

const routes = [
  "/",
  "/hn",
  "/download",
  "/pricing",
  "/features",
  "/how-it-works",
  "/about",
  "/changelog",
  "/releases",
  "/docs",
  "/security",
  "/privacy",
  "/terms",
  "/refund",
  "/contact",
  "/login",
  "/register",
];

const viewports = [
  ["1920x1080", 1920, 1080],
  ["1440x900", 1440, 900],
  ["1366x768", 1366, 768],
  ["1280x720", 1280, 720],
  ["1024x768", 1024, 768],
  ["430x932", 430, 932],
  ["390x844", 390, 844],
  ["375x812", 375, 812],
  ["360x800", 360, 800],
  ["320x568", 320, 568],
];

const defects = [];
let checks = 0;
let failures = 0;

function routeName(route) {
  return route === "/" ? "home" : route.slice(1).replaceAll("/", "-");
}

async function auditPage(page, route, label) {
  const issues = await page.evaluate(() => {
    const out = [];
    const vw = window.innerWidth;
    const docW = document.documentElement.scrollWidth;
    if (docW > vw + 1) out.push({ type: "overflow", detail: `scrollWidth=${docW} vw=${vw}` });

    const buttons = Array.from(document.querySelectorAll("a.btn-mag, a.btn-line, a.btn-primary, button.btn-mag, .btn"));
    for (const btn of buttons.slice(0, 12)) {
      const r = btn.getBoundingClientRect();
      if (r.height > 0 && r.height < 30) out.push({ type: "button-height", detail: `${btn.textContent?.trim().slice(0, 30)} h=${Math.round(r.height)}` });
      if (r.width > 0 && (r.right > vw + 2 || r.left < -2)) out.push({ type: "button-clipped", detail: btn.textContent?.trim().slice(0, 30) });
    }

    const cards = Array.from(document.querySelectorAll(".card, .dl-card, .tier, .premium-list li"));
    for (const card of cards.slice(0, 8)) {
      const style = getComputedStyle(card);
      const pad = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom);
      if (pad > 0 && pad < 24 && vw >= 768) out.push({ type: "card-padding", detail: `padY=${pad}` });
      const text = card.querySelector("h2,h3,p,li");
      if (text) {
        const cr = card.getBoundingClientRect();
        const tr = text.getBoundingClientRect();
        if (tr.left - cr.left < 8 || cr.right - tr.right < 8) {
          out.push({ type: "text-near-border", detail: text.textContent?.trim().slice(0, 40) });
        }
      }
    }

    const sha = document.querySelector(".dl-meta code, .dl-meta");
    if (sha) {
      const r = sha.getBoundingClientRect();
      if (r.width > vw) out.push({ type: "sha-overflow", detail: "SHA block wider than viewport" });
    }

    return out;
  });
  return issues;
}

const browser = await chromium.launch({
  args: ["--enable-unsafe-swiftshader", "--use-gl=angle", "--use-angle=swiftshader"],
});

for (const route of routes) {
  for (const [label, width, height] of viewports) {
    checks += 1;
    const ctx = await browser.newContext({ viewport: { width, height }, colorScheme: "dark" });
    const page = await ctx.newPage();
    const errs = [];
    page.on("console", (m) => { if (m.type() === "error") errs.push(m.text()); });

    try {
      const response = await page.goto(BASE + route, { waitUntil: "load", timeout: 45000 });
      await page.waitForTimeout(route === "/" ? 2500 : 600);
      const status = response?.status() || 0;
      const issues = await auditPage(page, route, label);

      if (width <= 430 && ["/features", "/download", "/docs"].includes(route)) {
        const burger = page.locator(".site-nav-burger, .cnav-burger").first();
        if (await burger.count()) {
          await burger.click();
          await page.waitForTimeout(300);
          const panel = page.locator(".mobile-panel");
          const open = await panel.isVisible();
          if (!open) issues.push({ type: "mobile-menu", detail: "menu did not open" });
          await page.keyboard.press("Escape");
          await page.waitForTimeout(200);
          const closed = !(await panel.isVisible());
          if (!closed) issues.push({ type: "mobile-menu", detail: "Escape did not close menu" });
        }
      }

      await page.screenshot({ path: `${OUT}/${routeName(route)}-${label}.png`, fullPage: false });
      const ok = status < 400 && errs.length === 0 && issues.length === 0;
      if (!ok) failures += 1;
      if (issues.length) {
        for (const issue of issues) {
          defects.push({ route, viewport: label, ...issue });
        }
      }
      console.log(`${ok ? "OK" : "FAIL"} ${route} ${label} status=${status} issues=${issues.length} errors=${errs.length}`);
    } catch (e) {
      failures += 1;
      defects.push({ route, viewport: label, type: "error", detail: e.message });
      console.log(`FAIL ${route} ${label}: ${e.message}`);
    }
    await ctx.close();
  }
}

await browser.close();

writeFileSync(`${OUT}/defects.json`, JSON.stringify({ checks, failures, defects }, null, 2));
console.log(`LAYOUT_V102_DONE checks=${checks} failures=${failures} defects=${defects.length}`);
if (failures) process.exit(1);
