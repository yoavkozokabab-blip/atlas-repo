import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

// Server-only configuration. Reads from environment; NEVER hardcodes secrets.
function csv(v: string | undefined): string[] {
  return (v || "").split(",").map((s) => s.trim().toLowerCase()).filter(Boolean);
}

// AUTH_SECRET must be set in production — a random per-process fallback would
// silently invalidate every session on each cold start (and differ across
// serverless instances), so we fail fast there instead. In dev/test the secret
// is persisted under the data dir: Next dev compiles each route into its own
// module graph, so a purely in-memory secret would differ between the register
// route and the session check and every sign-up would bounce back to /login.
let _ephemeral = "";
function ephemeralSecret(): string {
  if (process.env.NODE_ENV === "production") {
    throw new Error(
      "[atlas] AUTH_SECRET is not set. Set it in the host environment — sessions cannot work without a stable signing secret."
    );
  }
  if (!_ephemeral) {
    const dir = process.env.ATLAS_WEB_DATA_DIR || ".data";
    const file = path.join(dir, ".dev_auth_secret");
    try {
      _ephemeral = fs.readFileSync(file, "utf8").trim();
    } catch {
      /* first run — generate below */
    }
    if (!_ephemeral) {
      _ephemeral = crypto.randomBytes(32).toString("hex");
      try {
        fs.mkdirSync(dir, { recursive: true });
        fs.writeFileSync(file, _ephemeral, { mode: 0o600 });
      } catch {
        console.warn(
          "[atlas] AUTH_SECRET not set and the dev secret could not be persisted — sessions will reset on restart."
        );
      }
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
  // Legacy access-mode flags kept for compatibility. Normal self-serve access is open.
  get betaMode(): "open" | "invite" {
    return process.env.BETA_MODE === "invite" ? "invite" : "open";
  },
  get betaAllowlist(): string[] {
    return csv(process.env.BETA_ALLOWLIST);
  },
  get hasSupabase(): boolean {
    return !!(process.env.SUPABASE_URL && process.env.SUPABASE_SERVICE_ROLE_KEY);
  },
  get hasPaddle(): boolean {
    return !!process.env.PADDLE_API_KEY;
  },
  get paddleApiKey(): string {
    return process.env.PADDLE_API_KEY || "";
  },
  get paddleEnvironment(): "sandbox" | "production" {
    return process.env.PADDLE_ENVIRONMENT === "production" ? "production" : "sandbox";
  },
  get paddleProPriceId(): string {
    return process.env.PADDLE_PRO_PRICE_ID || "";
  },
  get paddleWebhookSecret(): string {
    return process.env.PADDLE_WEBHOOK_SECRET || "";
  },
  get appUrl(): string {
    const fallback = process.env.NODE_ENV === "production"
      ? "https://atlas-repo-wu76.vercel.app"
      : "http://localhost:3000";
    return (process.env.NEXT_PUBLIC_APP_URL || process.env.APP_URL || fallback).replace(/\/+$/, "");
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
    return process.env.NEXT_PUBLIC_ATLAS_VERSION || "1.0.1";
  },
};

/**`n * Live charges require live mode plus complete Paddle checkout configuration.`n * Stub/test deployments cannot create a paid checkout.`n */
export function liveChargesEnabled(): boolean {
  return ENV.paymentsMode === "live" && ENV.hasPaddle && !!ENV.paddleProPriceId;
}

export function paddleCheckoutConfigured(): boolean {
  return ENV.hasPaddle && !!ENV.paddleProPriceId;
}

export function paddleWebhookConfigured(): boolean {
  return !!ENV.paddleWebhookSecret;
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
