import { NextResponse } from "next/server";
import { store } from "@/app/_lib/store";
import { ENV, validateSupabaseConfig } from "@/app/_lib/config";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

async function probeAnalyticsTable(): Promise<{ ok: boolean; detail?: string }> {
  if (!ENV.hasSupabase) return { ok: true };
  const raw = (process.env.SUPABASE_URL || "").trim().replace(/\/+$/, "").replace(/\/rest\/v1$/i, "");
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!raw || !key) return { ok: false, detail: "analytics env missing" };
  const res = await fetch(`${raw}/rest/v1/analytics_events?select=id&limit=1`, {
    cache: "no-store",
    headers: { apikey: key, Authorization: `Bearer ${key}` },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    return {
      ok: false,
      detail: `analytics_events probe failed (${res.status}): ${body.slice(0, 120)}`,
    };
  }
  return { ok: true };
}

/**
 * Production health/readiness probe. No secrets returned — only booleans and the
 * active persistence backend. Use it after deploy to confirm the funnel is wired:
 *   GET /api/health  -> { ok, backend: "supabase"|"file", persistence: "ok"|... }
 */
export async function GET() {
  const backend = store.backend();
  let persistence: "ok" | "error" | "ephemeral" = backend === "file" ? "ephemeral" : "ok";
  let detail: string | undefined;

  if (backend === "supabase") {
    try {
      // Cheap round-trip that proves connectivity + schema presence.
      await store.listWaitlist(1);
      const analytics = await probeAnalyticsTable();
      if (!analytics.ok) {
        persistence = "error";
        detail = analytics.detail;
      }
    } catch (err) {
      persistence = "error";
      detail = err instanceof Error ? err.message.slice(0, 200) : "unknown";
    }
  }

  // Supabase env diagnostic — booleans + hostname only (no secrets). Surfacing
  // the resolved hostname lets an operator catch env drift (e.g. a stale/wrong
  // project) immediately instead of via an opaque ENOTFOUND 500.
  const sb = validateSupabaseConfig();
  const supabase = {
    supabase_url_present: sb.urlPresent,
    anon_key_present: !!(process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || process.env.SUPABASE_ANON_KEY),
    service_role_present: sb.serviceRolePresent,
    hostname: sb.hostname,
    validation_passed: sb.ok,
  };

  const body = {
    ok: persistence === "ok" || (persistence === "ephemeral" && !ENV.isProd),
    version: ENV.appVersion,
    env: ENV.isProd ? "production" : "development",
    backend,
    persistence,
    config: {
      hasSupabase: ENV.hasSupabase,
      hasAuthSecret: !!process.env.AUTH_SECRET,
      hasInstallerUrl: !!process.env.ATLAS_INSTALLER_URL || !!process.env.ATLAS_INSTALLER_PATH,
      paymentsMode: ENV.paymentsMode,
    },
    supabase,
    ...(detail ? { detail } : {}),
  };
  return NextResponse.json(body, { status: body.ok ? 200 : 503 });
}
