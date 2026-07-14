export const ANALYTICS_EVENTS = [
  "site_visit",
  "page_view",
  "download_clicked",
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
  "installer_download_started",
  "installer_download_completed",
  "desktop_installed",
  "desktop_launched",
  "repository_selected",
  "scan_started",
  "scan_completed",
  "agent_connected",
  "ask_submitted",
  "ask_completed",
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
      output[key] = raw;
      continue;
    }
    if (typeof raw !== "string") continue;
    const text = raw.trim().slice(0, 120);
    if (!text || LOCAL_PATH.test(text) || SECRET_VALUE.test(text)) continue;
    output[key] = text;
  }
  return output;
}

export function analyticsEnvironment(): "production" | "preview" | "development" | "test" | "unknown" {
  if (process.env.NODE_ENV === "test") return "test";
  const vercel = process.env.VERCEL_ENV;
  if (vercel === "production" || vercel === "preview" || vercel === "development") return vercel;
  if (process.env.NODE_ENV === "development") return "development";
  if (process.env.NODE_ENV === "production") return "unknown";
  return "unknown";
}
