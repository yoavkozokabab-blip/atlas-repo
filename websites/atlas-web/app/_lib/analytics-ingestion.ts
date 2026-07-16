import crypto from "node:crypto";
import { clientIp, rateLimit } from "./ratelimit";

export const MAX_ANALYTICS_EVENTS = 20;
export const MAX_ANALYTICS_BYTES = 32 * 1024;

export async function analyticsBody(req: Request): Promise<Record<string, unknown> | null> {
  const raw = await req.text();
  if (!raw || Buffer.byteLength(raw, "utf8") > MAX_ANALYTICS_BYTES) return null;
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed as Record<string, unknown> : null;
  } catch {
    return null;
  }
}

export function eventBatch(body: Record<string, unknown>): Record<string, unknown>[] | null {
  const events = Array.isArray(body.events) ? body.events : [body];
  if (!events.length || events.length > MAX_ANALYTICS_EVENTS || events.some((item) => !item || typeof item !== "object" || Array.isArray(item))) return null;
  return events as Record<string, unknown>[];
}

export async function acceptsAnalyticsRequest(req: Request, namespace: string, limit: number): Promise<boolean> {
  // The raw address is never persisted. It only contributes to a one-way
  // rate-limit bucket kept by the server-side limiter.
  const key = crypto.createHash("sha256").update(`${namespace}:${clientIp(req)}`).digest("hex");
  return rateLimit(`analytics:${key}`, limit, 60_000);
}
