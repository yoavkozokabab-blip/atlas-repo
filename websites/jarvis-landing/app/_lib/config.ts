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
