import { test, expect } from "playwright/test";
import fs from "node:fs";
import path from "node:path";
import {
  analyticsBody,
  DESKTOP_ANALYTICS_EVENT_KEYS,
  eventBatch,
  MAX_ANALYTICS_BYTES,
} from "../app/_lib/analytics-ingestion";
import { hasForbiddenAnalyticsData } from "../app/_lib/analytics-contract";
import { buildAnalyticsRow } from "../app/_lib/analytics-server";
import {
  INTERNAL_ANALYTICS_TEST_HEADER,
  internalAnalyticsTestAuthorized,
  isSyntheticUuid,
} from "../app/_lib/internal-analytics-test";

const TEST_SECRET = "q".repeat(48);

test.beforeEach(() => {
  delete process.env.ATLAS_INTERNAL_ANALYTICS_TEST_SECRET;
  process.env.NODE_ENV = "test";
});

test("missing and wrong secrets fail while the exact server secret passes", () => {
  expect(internalAnalyticsTestAuthorized(new Headers())).toBe(false);
  process.env.ATLAS_INTERNAL_ANALYTICS_TEST_SECRET = TEST_SECRET;
  expect(internalAnalyticsTestAuthorized(new Headers({
    [INTERNAL_ANALYTICS_TEST_HEADER]: "w".repeat(48),
  }))).toBe(false);
  expect(internalAnalyticsTestAuthorized(new Headers({
    [INTERNAL_ANALYTICS_TEST_HEADER]: TEST_SECRET,
  }))).toBe(true);
});

test("weak configured secrets fail closed", () => {
  process.env.ATLAS_INTERNAL_ANALYTICS_TEST_SECRET = "too-short";
  expect(internalAnalyticsTestAuthorized(new Headers({
    [INTERNAL_ANALYTICS_TEST_HEADER]: "too-short",
  }))).toBe(false);
});

test("only canonical synthetic UUIDs are accepted", () => {
  expect(isSyntheticUuid("5a1f769f-702f-4d51-98fc-5bf389f3785f")).toBe(true);
  expect(isSyntheticUuid("not-a-uuid")).toBe(false);
  expect(isSyntheticUuid("00000000-0000-0000-0000-000000000000")).toBe(false);
});

test("client-controlled internal is not in either desktop envelope", () => {
  expect(DESKTOP_ANALYTICS_EVENT_KEYS.has("internal")).toBe(false);
  expect(eventBatch({
    eventName: "desktop_launched",
    installationId: "5a1f769f-702f-4d51-98fc-5bf389f3785f",
    sessionId: "c22b5304-a8dc-43ee-b1fb-0f0c0ceaaed5",
    eventId: "18977393-a37c-45e1-94b8-66a4fb755a46",
    internal: true,
  }, DESKTOP_ANALYTICS_EVENT_KEYS)).toBeNull();
});

test("authorized server construction forces an internal row", () => {
  const row = buildAnalyticsRow({
    eventName: "desktop_launched",
    source: "desktop",
    installationId: "5a1f769f-702f-4d51-98fc-5bf389f3785f",
    sessionId: "c22b5304-a8dc-43ee-b1fb-0f0c0ceaaed5",
    deduplicationKey: "18977393-a37c-45e1-94b8-66a4fb755a46",
    internal: true,
  });
  expect(row.is_internal).toBe(true);
});

test("internal route retains the production ingestion controls", () => {
  const route = fs.readFileSync(
    path.join(process.cwd(), "app", "api", "analytics", "internal-desktop-events", "route.ts"),
    "utf8",
  );
  const publicRoute = fs.readFileSync(
    path.join(process.cwd(), "app", "api", "analytics", "desktop-events", "route.ts"),
    "utf8",
  );
  expect(route).toContain("internalAnalyticsTestAuthorized(req.headers)");
  expect(route).toContain('acceptsAnalyticsRequest(req, "desktop-internal-test", 30)');
  expect(route).toContain("analyticsBody(req)");
  expect(route).toContain("eventBatch(body, DESKTOP_ANALYTICS_EVENT_KEYS)");
  expect(route).toContain("hasForbiddenAnalyticsData");
  expect(route).toContain("isSyntheticUuid");
  expect(route).toContain("internal: true");
  expect(route).toContain('error: "not_found"');
  expect(publicRoute).not.toContain("ATLAS_INTERNAL_ANALYTICS_TEST_SECRET");
  expect(publicRoute).not.toContain("internal: true");
});

test("forbidden nested fields and oversized bodies remain blocked", async () => {
  expect(hasForbiddenAnalyticsData({
    safe: { source_code: "ATLAS_PRIVACY_TEST_SOURCE_20260724" },
  })).toBe(true);
  const oversized = new Request("http://localhost/internal", {
    method: "POST",
    body: JSON.stringify({ value: "x".repeat(MAX_ANALYTICS_BYTES + 1) }),
  });
  expect(await analyticsBody(oversized)).toBeNull();
});
