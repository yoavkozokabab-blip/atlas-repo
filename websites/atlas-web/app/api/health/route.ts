import { NextResponse } from "next/server";
import { store } from "@/app/_lib/store";
import { ENV, paddleCheckoutConfigured, validateSupabaseConfig } from "@/app/_lib/config";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

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
      await store.listAnalytics(1);
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
      hasInstallerUrl: !!process.env.NEXT_PUBLIC_DOWNLOAD_URL || !!process.env.ATLAS_INSTALLER_URL || !!process.env.ATLAS_INSTALLER_PATH,
      analyticsCollector: true,
      paymentsMode: ENV.paymentsMode,
      paddleCheckoutConfigured: paddleCheckoutConfigured(),
      paddleWebhookConfigured: !!ENV.paddleWebhookSecret,
    },
    supabase,
    ...(detail ? { detail } : {}),
  };
  return NextResponse.json(body, { status: body.ok ? 200 : 503 });
}
