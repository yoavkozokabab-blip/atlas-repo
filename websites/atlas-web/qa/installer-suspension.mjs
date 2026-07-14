import { chromium, request as playwrightRequest } from "playwright";

const baseUrl = (process.env.ATLAS_WEB_BASE_URL || "http://localhost:3012").replace(/\/$/, "");
const label = "Windows build verification in progress";
const message =
  "The latest Atlas desktop build is undergoing final installed-app verification. Downloads will reopen when the verified installer is ready.";
const stalePattern = /atlas-beta|Atlas_Setup\.exe|23E882490013|30 MB|Verify release|Verify against the GitHub release/i;

function check(condition, messageText) {
  if (!condition) throw new Error(messageText);
}

async function verifyPage(browser, path, viewport, openMobileMenu = false) {
  const context = await browser.newContext({ viewport });
  const page = await context.newPage();
  const consoleErrors = [];
  const pageErrors = [];

  page.on("console", (entry) => {
    if (entry.type() === "error") consoleErrors.push(entry.text());
  });
  page.on("pageerror", (error) => pageErrors.push(error.message));

  const response = await page.goto(`${baseUrl}${path}`, { waitUntil: "networkidle" });
  check(response?.status() === 200, `${path} returned ${response?.status()}`);

  if (openMobileMenu) {
    await page.getByRole("button", { name: "Open menu" }).click();
    await page.getByRole("dialog", { name: "Menu" }).waitFor();
  }

  const body = await page.locator("body").innerText();
  const links = await page.locator("a").evaluateAll((items) =>
    items.map((item) => item.href)
  );
  const metrics = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));

  check(body.includes(label), `${path} is missing the verification label`);
  check(body.includes(message), `${path} is missing the verification message`);
  check(!stalePattern.test(body), `${path} still exposes stale installer metadata`);
  check(
    !links.some((href) => /atlas-beta|releases\/download|\/download\/atlas/i.test(href)),
    `${path} still contains an installer asset link`
  );
  check(metrics.scrollWidth <= metrics.clientWidth, `${path} has horizontal overflow`);
  check(consoleErrors.length === 0, `${path} console errors: ${consoleErrors.join(" | ")}`);
  check(pageErrors.length === 0, `${path} page errors: ${pageErrors.join(" | ")}`);

  await page.screenshot({ fullPage: true });
  await context.close();

  return {
    path,
    viewport,
    installerLinks: links.filter((href) =>
      /atlas-beta|releases\/download|\/download\/atlas/i.test(href)
    ),
    consoleErrors,
    pageErrors,
    horizontalOverflow: metrics.scrollWidth > metrics.clientWidth,
  };
}

const browser = await chromium.launch({ headless: true });

try {
  const results = [];
  results.push(await verifyPage(browser, "/", { width: 1440, height: 1000 }));
  results.push(await verifyPage(browser, "/", { width: 390, height: 844 }, true));
  results.push(await verifyPage(browser, "/download", { width: 1440, height: 1000 }));
  results.push(await verifyPage(browser, "/download", { width: 390, height: 844 }));

  const request = await playwrightRequest.newContext();
  const getResponse = await request.get(`${baseUrl}/download/atlas`, { maxRedirects: 0 });
  const getBody = await getResponse.json();
  const headResponse = await request.head(`${baseUrl}/download/atlas`, { maxRedirects: 0 });

  check(getResponse.status() === 503, `GET /download/atlas returned ${getResponse.status()}`);
  check(headResponse.status() === 503, `HEAD /download/atlas returned ${headResponse.status()}`);
  check(getResponse.headers()["cache-control"] === "no-store", "GET is missing Cache-Control: no-store");
  check(getResponse.headers()["retry-after"] === "3600", "GET is missing Retry-After: 3600");
  check(!getResponse.headers().location, "GET still redirects");
  check(!getResponse.headers()["content-disposition"], "GET still returns an attachment");
  check(getBody.error === "installer_temporarily_unavailable", "GET returned the wrong error code");
  check(getBody.message === message, "GET returned the wrong safety message");

  await request.dispose();
  console.log(JSON.stringify({
    ok: true,
    pages: results,
    downloadRoute: {
      getStatus: getResponse.status(),
      headStatus: headResponse.status(),
      cacheControl: getResponse.headers()["cache-control"],
      retryAfter: getResponse.headers()["retry-after"],
      body: getBody,
    },
  }, null, 2));
} finally {
  await browser.close();
}
