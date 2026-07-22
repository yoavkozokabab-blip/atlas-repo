export const WEBSITE_ANALYTICS_EVENTS = [
  "site_visit",
  "page_view",
  "download_clicked",
  "installer_download_started",
] as const;

export const DESKTOP_ANALYTICS_EVENTS = [
  "desktop_launched",
  "sample_scan_completed",
  "real_repo_scan_completed",
  "scan_failed",
  "graph_opened",
  "impact_completed",
  "mcp_connected",
  "analytics_opted_out",
] as const;

export const ANALYTICS_EVENTS = [...WEBSITE_ANALYTICS_EVENTS, ...DESKTOP_ANALYTICS_EVENTS] as const;

export type AnalyticsEventName = (typeof ANALYTICS_EVENTS)[number];
export type AnalyticsSource = "website" | "server" | "desktop";

const EVENT_SET = new Set<string>(ANALYTICS_EVENTS);
const WEBSITE_EVENT_SET = new Set<string>(WEBSITE_ANALYTICS_EVENTS);
const DESKTOP_EVENT_SET = new Set<string>(DESKTOP_ANALYTICS_EVENTS);
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
const EMAIL_VALUE = /\b[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)+\b/i;
const FORBIDDEN_MARKER = /(?:repo(?:sitory)?(?:[_\s-]*(?:path|name|folder))?|file(?:[_\s-]*(?:path|name))|source(?:[_\s-]*code)?|prompt|symbol(?:[_\s-]*name)?|graph(?:[_\s-]*(?:content|node|edge))|impact(?:[_\s-]*(?:path|result))|terminal(?:[_\s-]*output)?|windows(?:[_\s-]*user(?:name)?)|user(?:name)?|email|access[_-]?token|password|stack[_-]?trace)/i;

export function isAnalyticsEvent(value: unknown): value is AnalyticsEventName {
  return typeof value === "string" && EVENT_SET.has(value);
}

export function isWebsiteAnalyticsEvent(value: unknown): value is AnalyticsEventName {
  return typeof value === "string" && WEBSITE_EVENT_SET.has(value);
}

export function isDesktopAnalyticsEvent(value: unknown): value is AnalyticsEventName {
  return typeof value === "string" && DESKTOP_EVENT_SET.has(value);
}

export function hasForbiddenAnalyticsData(value: unknown): boolean {
  if (typeof value === "string") {
    return LOCAL_PATH.test(value) || SECRET_VALUE.test(value) || EMAIL_VALUE.test(value) || FORBIDDEN_MARKER.test(value);
  }
  if (!value || typeof value !== "object") return false;
  if (Array.isArray(value)) return value.some(hasForbiddenAnalyticsData);
  return Object.entries(value as Record<string, unknown>).some(
    ([key, child]) => SENSITIVE_KEY.test(key) || FORBIDDEN_MARKER.test(key) || hasForbiddenAnalyticsData(child),
  );
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
  if (hasForbiddenAnalyticsData(value)) return {};
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
