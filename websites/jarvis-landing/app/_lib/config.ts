import crypto from "node:crypto";

// Server-only configuration. Reads from environment; NEVER hardcodes secrets.
function csv(v: string | undefined): string[] {
  return (v || "").split(",").map((s) => s.trim().toLowerCase()).filter(Boolean);
}

// AUTH_SECRET must be set in production. When unset (test/dev), we use an
// ephemeral per-process secret (sessions reset on restart) and warn — we never
// fall back to a hardcoded constant.
let _ephemeral = "";
function ephemeralSecret(): string {
  if (!_ephemeral) {
    _ephemeral = crypto.randomBytes(32).toString("hex");
    if (process.env.NODE_ENV !== "production") {
      console.warn(
        "[atlas] AUTH_SECRET not set — using an ephemeral dev secret. Set AUTH_SECRET in .env.local for stable sessions."
      );
    }
  }
  return _ephemeral;
}

export const ENV = {
  get authSecret(): string {
    return process.env.AUTH_SECRET || ephemeralSecret();
  },
  get adminEmails(): string[] {
    return csv(process.env.ADMIN_EMAILS);
  },
  // Free-beta access model (Phase 186A). "open" = anyone who signs up is in;
  // "invite" = only emails on BETA_ALLOWLIST (and admins) are approved.
  get betaMode(): "open" | "invite" {
    return process.env.BETA_MODE === "invite" ? "invite" : "open";
  },
  get betaAllowlist(): string[] {
    return csv(process.env.BETA_ALLOWLIST);
  },
  get hasSupabase(): boolean {
    return !!(process.env.SUPABASE_URL && process.env.SUPABASE_SERVICE_ROLE_KEY);
  },
  get hasStripe(): boolean {
    return !!process.env.STRIPE_SECRET_KEY;
  },
  get paymentsMode(): "stub" | "test" | "live" {
    const m = process.env.PAYMENTS_MODE;
    return m === "live" || m === "test" ? m : "stub";
  },
  get dataDir(): string {
    return process.env.ATLAS_WEB_DATA_DIR || ".data";
  },
  get isProd(): boolean {
    return process.env.NODE_ENV === "production";
  },
  get appVersion(): string {
    return process.env.NEXT_PUBLIC_ATLAS_VERSION || "0.1.0-beta";
  },
};

/**
 * Live charges require BOTH live mode AND a Stripe key. This build never returns
 * true for a stub/test deployment, and the checkout code additionally falls
 * through to the stub path — so no real money can move without a deliberate,
 * reviewed change.
 */
export function liveChargesEnabled(): boolean {
  return ENV.paymentsMode === "live" && ENV.hasStripe;
}

// ---------------------------------------------------------------------------
// Supabase config validation (production env reconciliation).
// Validates ONLY the variables this codebase actually consumes — SUPABASE_URL
// and SUPABASE_SERVICE_ROLE_KEY (raw PostgREST + service role; see _lib/store.ts
// and _lib/ratelimit.ts). The app does NOT use createClient / anon key /
// NEXT_PUBLIC_SUPABASE_*, so those are not required and not validated here.
//
// No project id is hardcoded — drift is caught by surfacing the resolved
// hostname via /api/health so an operator can see a wrong/stale project.
// ---------------------------------------------------------------------------
export interface SupabaseConfigCheck {
  urlPresent: boolean;
  serviceRolePresent: boolean;
  validUrl: boolean;
  isSupabaseHost: boolean;
  hostname: string;
  ok: boolean;
}

export function validateSupabaseConfig(): SupabaseConfigCheck {
  const raw = (process.env.SUPABASE_URL || "").trim();
  const serviceRolePresent = !!process.env.SUPABASE_SERVICE_ROLE_KEY;
  let validUrl = false;
  let isSupabaseHost = false;
  let hostname = "";
  if (raw) {
    try {
      const u = new URL(raw);
      validUrl = true;
      hostname = u.hostname;
      isSupabaseHost = u.hostname.endsWith(".supabase.co") || u.hostname.endsWith(".supabase.in");
    } catch {
      validUrl = false;
    }
  }
  const urlPresent = !!raw;
  return {
    urlPresent,
    serviceRolePresent,
    validUrl,
    isSupabaseHost,
    hostname,
    ok: urlPresent && serviceRolePresent && validUrl && isSupabaseHost,
  };
}

/** Throws a clear, secret-free error when Supabase env is missing/malformed. */
export function assertSupabaseConfigured(): void {
  const c = validateSupabaseConfig();
  if (!c.ok) {
    throw new Error(
      `[atlas] Supabase env invalid: url_present=${c.urlPresent} service_role_present=${c.serviceRolePresent} ` +
        `valid_url=${c.validUrl} supabase_host=${c.isSupabaseHost} hostname=${c.hostname || "<none>"}. ` +
        `Set SUPABASE_URL=https://<project>.supabase.co and SUPABASE_SERVICE_ROLE_KEY to the CURRENT project.`
    );
  }
}
