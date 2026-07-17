import crypto from "node:crypto";
import { clientIp, rateLimit } from "./ratelimit";

export const MAX_ANALYTICS_EVENTS = 20;
export const MAX_ANALYTICS_BYTES = 32 * 1024;
export const MAX_ANALYTICS_DEPTH = 8;
export const WEBSITE_ANALYTICS_EVENT_KEYS = new Set([
  "eventName", "anonymousId", "sessionId", "route", "properties", "deduplicationKey", "internal",
]);
export const DESKTOP_ANALYTICS_EVENT_KEYS = new Set([
  "eventName", "installationId", "sessionId", "appVersion", "buildCommit", "properties", "eventId",
]);

function jsonDepth(value: unknown, depth = 0): number {
  if (!value || typeof value !== "object") return depth;
  const values = Array.isArray(value) ? value : Object.values(value as Record<string, unknown>);
  if (!values.length) return depth + 1;
  return Math.max(...values.map((item) => jsonDepth(item, depth + 1)));
}

export async function analyticsBody(req: Request): Promise<Record<string, unknown> | null> {
  const raw = await req.text();
  if (!raw || Buffer.byteLength(raw, "utf8") > MAX_ANALYTICS_BYTES) return null;
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) && jsonDepth(parsed) <= MAX_ANALYTICS_DEPTH
      ? parsed as Record<string, unknown>
      : null;
  } catch {
    return null;
  }
}

export function eventBatch(
  body: Record<string, unknown>,
  allowedKeys: ReadonlySet<string>,
): Record<string, unknown>[] | null {
  if ("events" in body && Object.keys(body).some((key) => key !== "events")) return null;
  const events = Array.isArray(body.events) ? body.events : [body];
  if (!events.length || events.length > MAX_ANALYTICS_EVENTS || events.some((item) => !item || typeof item !== "object" || Array.isArray(item))) return null;
  const records = events as Record<string, unknown>[];
  if (records.some((event) => Object.keys(event).some((key) => !allowedKeys.has(key)))) return null;
  return records;
}

export async function acceptsAnalyticsRequest(req: Request, namespace: string, limit: number): Promise<boolean> {
  // The raw address is never persisted. It only contributes to a one-way
  // rate-limit bucket kept by the server-side limiter.
  const key = crypto.createHash("sha256").update(`${namespace}:${clientIp(req)}`).digest("hex");
  return rateLimit(`analytics:${key}`, limit, 60_000);
}
