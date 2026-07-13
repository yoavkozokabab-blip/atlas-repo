// Rate limiting (Phase 186D).
//
// Serverless reality: a per-process Map does NOT rate-limit on Vercel, because
// each instance/invocation has its own memory. So in production we use a SHARED,
// atomic counter in Supabase via a Postgres RPC (`atlas_rate_limit_hit`,
// migration 0002). In dev/test (no Supabase) we fall back to an in-process Map,
// which is correct for a single instance.
//
// `rateLimit` is async. Backend errors FAIL OPEN (allow) and log — a transient
// limiter outage must not lock every user out (self-DoS). The window is a fixed
// window of `windowMs`.
import { ENV } from "./config";

// --- dev/test fallback: in-process sliding window (single instance only) ---
const hits = new Map<string, number[]>();
function memoryHit(key: string, max: number, windowMs: number): boolean {
  const now = Date.now();
  const arr = (hits.get(key) || []).filter((t) => t > now - windowMs);
  if (arr.length >= max) {
    hits.set(key, arr);
    return false;
  }
  arr.push(now);
  hits.set(key, arr);
  return true;
}

// --- production: shared atomic counter in Supabase ---
function restBase(): string {
  const raw = (process.env.SUPABASE_URL || "").trim().replace(/\/+$/, "");
  const origin = raw.replace(/\/rest\/v1$/i, "");
  return `${origin}/rest/v1`;
}
async function supabaseHit(key: string, max: number, windowMs: number): Promise<boolean> {
  const apiKey = process.env.SUPABASE_SERVICE_ROLE_KEY!;
  try {
    const res = await fetch(`${restBase()}/rpc/atlas_rate_limit_hit`, {
      method: "POST",
      cache: "no-store",
      headers: {
        apikey: apiKey,
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        p_key: key,
        p_window_seconds: Math.max(1, Math.ceil(windowMs / 1000)),
        p_max: max,
      }),
    });
    if (!res.ok) {
      console.error(`[atlas] rate-limit RPC failed (${res.status}); failing open for "${key}"`);
      return true; // fail open
    }
    // The RPC returns a bare boolean: true = under the limit (allow).
    return (await res.json()) === true;
  } catch (e) {
    console.error(`[atlas] rate-limit RPC threw; failing open for "${key}":`, e);
    return true; // fail open
  }
}

/** Returns true if the request is ALLOWED (under the limit), false if throttled. */
export async function rateLimit(key: string, max: number, windowMs: number): Promise<boolean> {
  return ENV.hasSupabase ? supabaseHit(key, max, windowMs) : memoryHit(key, max, windowMs);
}

export function clientIp(req: Request): string {
  return req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || "local";
}

export async function readJson(req: Request): Promise<Record<string, unknown>> {
  try {
    const v = await req.json();
    return v && typeof v === "object" ? (v as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}
