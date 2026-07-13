/** axe-core accessibility audit of the homepage (top + a scrolled narrative state). */
import { chromium } from "playwright";
import { AxeBuilder } from "@axe-core/playwright";

const BASE = process.argv[2] || "http://localhost:3011";
const browser = await chromium.launch({
  args: ["--enable-unsafe-swiftshader", "--use-gl=angle", "--use-angle=swiftshader", "--ignore-gpu-blocklist"],
});
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: "dark" });
const page = await ctx.newPage();
await page.goto(BASE + "/", { waitUntil: "load" });
await page.waitForTimeout(3000);

async function audit(label) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  console.log(`\n=== ${label}: ${results.violations.length} violations ===`);
  for (const v of results.violations) {
    console.log(`\n[${v.impact}] ${v.id} — ${v.help}`);
    console.log(`  ${v.helpUrl}`);
    v.nodes.slice(0, 4).forEach((n) => {
      console.log(`  · ${n.target.join(" ")}`);
      if (n.failureSummary) console.log(`    ${n.failureSummary.replace(/\n/g, "\n    ")}`);
    });
  }
}

await audit("home top");

// scroll into the narrative (retrieval act) and re-audit
await page.evaluate(() => {
  const el = document.querySelector(".narrative");
  if (!el) return;
  const y = el.offsetTop + 0.68 * (el.offsetHeight - window.innerHeight);
  (window.__lenis ? window.__lenis.scrollTo(y, { immediate: true, force: true }) : window.scrollTo(0, y));
});
await page.waitForTimeout(800);
await audit("narrative retrieval");

await browser.close();
