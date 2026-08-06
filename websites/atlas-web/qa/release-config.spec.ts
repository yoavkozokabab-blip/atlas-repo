import { test, expect } from "playwright/test";
import fs from "node:fs";
import path from "node:path";
import {
  ASK_ENABLED,
  CURRENT_WINDOWS_RELEASE,
  DOWNLOAD_URL,
  GITHUB_RELEASE_URL,
  INSTALLER_SHA256,
  SECURITY_EMAIL,
  SUPPORT_EMAIL,
  HELLO_EMAIL,
  releaseSizeLabel,
} from "../app/_config";
import { ENV } from "../app/_lib/config";
import { facts } from "../app/lib/content/facts";

const APP_DIR = path.join(process.cwd(), "app");

/** Every .ts/.tsx under app/, so a claim cannot hide in a page I forgot. */
function appSources(): string[] {
  const out: string[] = [];
  const walk = (dir: string) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (/\.(ts|tsx)$/.test(entry.name)) out.push(full);
    }
  };
  walk(APP_DIR);
  return out;
}

const SOURCES = appSources().map((file) => ({ file, text: fs.readFileSync(file, "utf8") }));
const rel = (file: string) => path.relative(process.cwd(), file).replace(/\\/g, "/");

// ---------------------------------------------------------------------------
// The release object is the only place artifact facts may live.
// ---------------------------------------------------------------------------

test("release constant is filled in — a build must never ship the sentinel", () => {
  expect(
    CURRENT_WINDOWS_RELEASE.sha256,
    "sha256 is still the placeholder: paste the value installer_build.ps1 printed",
  ).not.toBe("PENDING_RELEASE_BUILD");
  expect(CURRENT_WINDOWS_RELEASE.sha256).toMatch(/^[A-F0-9]{64}$/);
  expect(
    CURRENT_WINDOWS_RELEASE.sizeBytes,
    "sizeBytes is still 0: paste the real byte count of the published installer",
  ).toBeGreaterThan(1_000_000);
});

test("version, tag, filename and download URL all describe one artifact", () => {
  const { version, tag, filename, downloadUrl, releaseUrl } = CURRENT_WINDOWS_RELEASE;
  expect(tag).toBe(`v${version}`);
  expect(filename).toBe(`Atlas-Setup-${version}.exe`);
  expect(downloadUrl).toContain(`/${tag}/`);
  expect(downloadUrl.endsWith(filename)).toBe(true);
  expect(releaseUrl.endsWith(tag)).toBe(true);
});

test("legacy exports and ENV.appVersion are derived, never independent", () => {
  expect(DOWNLOAD_URL).toBe(CURRENT_WINDOWS_RELEASE.downloadUrl);
  expect(INSTALLER_SHA256).toBe(CURRENT_WINDOWS_RELEASE.sha256);
  expect(GITHUB_RELEASE_URL).toBe(CURRENT_WINDOWS_RELEASE.releaseUrl);
  expect(ENV.appVersion).toBe(CURRENT_WINDOWS_RELEASE.version);
  expect(facts.version).toBe(CURRENT_WINDOWS_RELEASE.version);
  expect(facts.platform).toBe(CURRENT_WINDOWS_RELEASE.platform);
});

test("the displayed size is computed from bytes, not written by hand", () => {
  expect(releaseSizeLabel(41_943_040)).toBe("40.0 MB");
  expect(releaseSizeLabel()).toBe(`${(CURRENT_WINDOWS_RELEASE.sizeBytes / 1_048_576).toFixed(1)} MB`);

  const offenders = SOURCES.filter(({ text }) => /\b\d{1,3}(\.\d+)?\s?MB\b/.test(text)).map(({ file }) => rel(file));
  expect(offenders, "hardcoded size literal — render releaseSizeLabel() instead").toEqual([]);
});

test("no retired release version survives anywhere in the app", () => {
  const retired = ["1.0.4", "1.0.5"];
  const offenders: string[] = [];
  for (const { file, text } of SOURCES) {
    for (const version of retired) {
      // The changelog legitimately narrates release history.
      if (rel(file).includes("changelog")) continue;
      if (text.includes(version)) offenders.push(`${rel(file)} → ${version}`);
    }
  }
  expect(offenders, "retired version string still referenced").toEqual([]);
});

test("the pre-beta filename is never shown to a user", () => {
  // A local-dev filesystem fallback may still probe the historical name; it
  // must say so explicitly with the marker, and it must not be rendered.
  const offenders = SOURCES.filter(
    ({ text }) => text.includes("Atlas_Setup.exe") && !text.includes("dev-fallback-legacy-name"),
  ).map(({ file }) => rel(file));
  expect(offenders).toEqual([]);
});

// ---------------------------------------------------------------------------
// One support address, and no domain we do not own.
// ---------------------------------------------------------------------------

test("exactly one support address is used across every public surface", () => {
  const expected = "yoavkozokabab@gmail.com";
  expect(SUPPORT_EMAIL).toBe(expected);
  expect(HELLO_EMAIL).toBe(expected);
  expect(SECURITY_EMAIL).toBe(expected);

  const stale = ["yoavkozlovski@gmail.com", "atlas.repo.support@gmail.com", "support@useatlas.dev"];
  const offenders: string[] = [];
  for (const { file, text } of SOURCES) {
    for (const address of stale) if (text.includes(address)) offenders.push(`${rel(file)} → ${address}`);
  }
  expect(offenders, "stale support address still present").toEqual([]);
});

test("useatlas.dev is never referenced — the domain belongs to another product", () => {
  const offenders = SOURCES.filter(({ text }) => text.includes("useatlas.dev")).map(({ file }) => rel(file));
  expect(offenders).toEqual([]);
});

// ---------------------------------------------------------------------------
// The site may not advertise what the shipping binary does not do.
// ---------------------------------------------------------------------------

test("Ask is not advertised as available while the build ships it disabled", () => {
  expect(ASK_ENABLED).toBe(false);

  // Every mention of Ask must carry a disclaimer on the same line, so the
  // feature can be described without ever reading as shipping.
  const DISCLAIMED = /(under development|in development|not included|not available|planned|coming)/i;
  const offenders: string[] = [];
  for (const { file, text } of SOURCES) {
    text.split("\n").forEach((line, index) => {
      if (!/Ask Atlas/.test(line)) return;
      if (!DISCLAIMED.test(line)) offenders.push(`${rel(file)}:${index + 1}`);
    });
  }
  expect(offenders, "Ask mentioned without a not-in-this-beta disclaimer").toEqual([]);
});

test("impact precision/recall are never published without the direct-dependency qualifier", () => {
  expect(facts.impactQualifier).toBe("direct-dependency impact");
  const offenders: string[] = [];
  for (const { file, text } of SOURCES) {
    if (rel(file).endsWith("lib/content/facts.ts")) continue;
    if (/impactPrecision|impactRecall/.test(text) && !/impactQualifier/.test(text)) {
      offenders.push(rel(file));
    }
  }
  expect(offenders, "impact figures rendered without the qualifier").toEqual([]);
});

test("no unsupported token-savings claim is published", () => {
  const offenders: string[] = [];
  for (const { file, text } of SOURCES) {
    if (/\b\d+\s?%[^.\n]{0,40}(fewer|less|reduc)[^.\n]{0,20}token/i.test(text)) offenders.push(rel(file));
    if (/(saves?|reduc\w*)[^.\n]{0,30}\b\d+\s?%[^.\n]{0,20}token/i.test(text)) offenders.push(rel(file));
  }
  expect(offenders, "quantified token-savings claim — no measurement backs it").toEqual([]);
});

test("no macOS/Linux availability or code-signing claim", () => {
  expect(CURRENT_WINDOWS_RELEASE.signed).toBe(false);
  const offenders: string[] = [];
  for (const { file, text } of SOURCES) {
    if (/\b(macOS|Linux)\b[^.\n]{0,30}\b(available|supported|download)\b/i.test(text)
        && !/not (yet )?(available|supported)/i.test(text)) {
      offenders.push(`${rel(file)} → platform claim`);
    }
    if (/\bsigned installer\b/i.test(text) && !/unsigned/i.test(text)) {
      offenders.push(`${rel(file)} → signing claim`);
    }
  }
  expect(offenders).toEqual([]);
});
