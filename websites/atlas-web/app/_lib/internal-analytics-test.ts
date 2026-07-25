import crypto from "node:crypto";

export const INTERNAL_ANALYTICS_TEST_HEADER = "x-atlas-internal-analytics-test";

function digest(value: string): Buffer {
  return crypto.createHash("sha256").update(value, "utf8").digest();
}

export function internalAnalyticsTestAuthorized(headers: Pick<Headers, "get">): boolean {
  const expected = process.env.ATLAS_INTERNAL_ANALYTICS_TEST_SECRET;
  const provided = headers.get(INTERNAL_ANALYTICS_TEST_HEADER);
  if (!expected || expected.length < 32 || !provided) return false;
  return crypto.timingSafeEqual(digest(expected), digest(provided));
}

export function isSyntheticUuid(value: unknown): value is string {
  return typeof value === "string" &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
}
