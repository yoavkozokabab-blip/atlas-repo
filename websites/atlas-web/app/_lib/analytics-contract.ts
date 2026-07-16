export const ANALYTICS_EVENTS = [
  "site_visit",
  "page_view",
  "page_active_heartbeat",
  "page_active_ended",
  "screen_view",
  "screen_active_heartbeat",
  "screen_active_ended",
  "app_session_ended",
  "session_ended",
  "download_clicked",
  "installer_download_response_started",
  "download_unavailable_seen",
  "github_clicked",
  "docs_clicked",
  "pricing_viewed",
  "signup_started",
  "signup_success",
  "signup_failed",
  "login_started",
  "login_success",
  "login_failed",
  "guest_mode_started",
  "contact_submitted",
  "app_first_run",
  "app_launch",
  "repository_loaded",
  "scan_started",
  "scan_completed",
  "scan_failed",
  "impact_started",
  "impact_completed",
  "impact_failed",
  "ask_started",
  "ask_completed",
  "ask_failed",
  "debug_started",
  "debug_completed",
  "debug_failed",
  "plan_started",
  "plan_completed",
  "plan_failed",
  "mcp_configured",
  "mcp_connected",
  "mcp_disconnected",
] as const;

export type AnalyticsEventName = (typeof ANALYTICS_EVENTS)[number];
export type AnalyticsSource = "website" | "server" | "desktop";

const EVENT_SET = new Set<string>(ANALYTICS_EVENTS);
const PROPERTY_KEYS = new Set([
  "agent",
  "href_kind",
  "http_status",
  "outcome",
  "plan",
  "reason_code",
  "status",
  "surface",
  "screen",
  "workflow",
  "duration_active_ms",
  "duration_elapsed_ms",
  "referrer_category",
  "campaign_source",
  "campaign_medium",
  "campaign_name",
  "device_category",
  "browser_category",
]);
const SENSITIVE_KEY = /(authorization|cookie|email|password|prompt|repo|path|secret|token)/i;
const LOCAL_PATH = /(?:[a-z]:\\|\\\\|\/(?:Users|home|var|etc|private|tmp)\/)/i;
const SECRET_VALUE = /(?:bearer\s+[a-z0-9._-]+|sb_secret_|service[_-]?role|eyJ[a-z0-9_-]{10,}\.)/i;

export function isAnalyticsEvent(value: unknown): value is AnalyticsEventName {
  return typeof value === "string" && EVENT_SET.has(value);
}

export function sanitizeRoute(value: unknown): string | null {
  if (typeof value !== "string" || !value.startsWith("/")) return null;
  const route = value.split(/[?#]/, 1)[0].slice(0, 256);
  return LOCAL_PATH.test(route) ? null : route;
}

export function sanitizeIdentifier(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const result = value.trim();
  return /^[a-zA-Z0-9._:-]{8,160}$/.test(result) ? result : null;
}

export function sanitizeProperties(value: unknown): Record<string, string | number | boolean> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  const output: Record<string, string | number | boolean> = {};
  for (const [key, raw] of Object.entries(value).slice(0, 16)) {
    if (!PROPERTY_KEYS.has(key) || SENSITIVE_KEY.test(key)) continue;
    if (typeof raw === "boolean" || (typeof raw === "number" && Number.isFinite(raw))) {
      output[key] = typeof raw === "number" && key.startsWith("duration_")
        ? Math.max(0, Math.min(Math.floor(raw), 86_400_000))
        : raw;
      continue;
    }
    if (typeof raw !== "string") continue;
    const text = raw.trim().slice(0, 120);
    if (!text || LOCAL_PATH.test(text) || SECRET_VALUE.test(text)) continue;
    output[key] = text;
  }
  return output;
}

export function classifyReferrer(value: string | null): string {
  if (!value) return "direct";
  try {
    const host = new URL(value).hostname.toLowerCase();
    if (/google\.|bing\.|duckduckgo\.|search\.yahoo\./.test(host)) return "search";
    if (/github\.com|twitter\.com|x\.com|linkedin\.com|reddit\.com|news\.ycombinator\.com/.test(host)) return "social";
    return "referral";
  } catch {
    return "unknown";
  }
}

export function classifyDevice(userAgent: string | null): "mobile" | "desktop" | "unknown" {
  if (!userAgent) return "unknown";
  return /mobile|android|iphone|ipad/i.test(userAgent) ? "mobile" : "desktop";
}

export function classifyBrowser(userAgent: string | null): "edge" | "chrome" | "firefox" | "safari" | "other" {
  const value = userAgent || "";
  if (/edg\//i.test(value)) return "edge";
  if (/firefox\//i.test(value)) return "firefox";
  if (/chrome\//i.test(value)) return "chrome";
  if (/safari\//i.test(value)) return "safari";
  return "other";
}

export function analyticsEnvironment(): "production" | "preview" | "development" | "test" | "unknown" {
  if (process.env.NODE_ENV === "test") return "test";
  const vercel = process.env.VERCEL_ENV;
  if (vercel === "production" || vercel === "preview" || vercel === "development") return vercel;
  if (process.env.NODE_ENV === "development") return "development";
  if (process.env.NODE_ENV === "production") return "unknown";
  return "unknown";
}
