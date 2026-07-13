/** Web-Vitals + scene-chunk timing on the production build. */
import { chromium } from "playwright";

const BASE = process.argv[2] || "http://localhost:3012";
const browser = await chromium.launch({
  args: ["--enable-unsafe-swiftshader", "--use-gl=angle", "--use-angle=swiftshader", "--ignore-gpu-blocklist"],
});
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: "dark" });
const page = await ctx.newPage();

const reqs = [];
page.on("response", async (r) => {
  const url = r.url();
  if (url.endsWith(".js")) {
    let len = Number(r.headers()["content-length"] || 0);
    reqs.push({ url: url.split("/").pop(), len, t: Date.now() });
  }
});

const t0 = Date.now();
await page.goto(BASE + "/", { waitUntil: "load" });
// collect paint + LCP + CLS
await page.waitForTimeout(3500);
const vitals = await page.evaluate(() => new Promise((resolve) => {
  const out = { fcp: 0, lcp: 0, cls: 0, ttfb: 0 };
  const nav = performance.getEntriesByType("navigation")[0];
  if (nav) out.ttfb = Math.round(nav.responseStart);
  const fcp = performance.getEntriesByName("first-contentful-paint")[0];
  if (fcp) out.fcp = Math.round(fcp.startTime);
  new PerformanceObserver((l) => {
    const e = l.getEntries();
    out.lcp = Math.round(e[e.length - 1].startTime);
  }).observe({ type: "largest-contentful-paint", buffered: true });
  let cls = 0;
  new PerformanceObserver((l) => {
    for (const e of l.getEntries()) if (!e.hadRecentInput) cls += e.value;
  }).observe({ type: "layout-shift", buffered: true });
  setTimeout(() => { out.cls = Math.round(cls * 1000) / 1000; resolve(out); }, 400);
}));

// find the biggest js chunk (likely three) and when it loaded relative to nav
const big = reqs.slice().sort((a, b) => b.len - a.len).slice(0, 6);
console.log("VITALS", JSON.stringify(vitals));
console.log("JS chunks (top 6 by content-length):");
for (const r of big) console.log(`  ${r.len ? (r.len / 1024).toFixed(1) + "kB" : "?"}  ${r.url}  +${r.t - t0}ms`);
console.log("total js requests:", reqs.length);
await browser.close();
