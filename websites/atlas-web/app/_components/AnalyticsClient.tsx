"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import type { AnalyticsEventName } from "../_lib/analytics-contract";

const ANON_KEY = "atlas_analytics_anonymous_id";
const SESSION_KEY = "atlas_analytics_session_id";
const SENT_PREFIX = "atlas_analytics_sent:";
const BACKOFF_KEY = "atlas_analytics_backoff_until";

function identifier(storage: Storage, key: string): string {
  const existing = storage.getItem(key);
  if (existing) return existing;
  const value = crypto.randomUUID();
  storage.setItem(key, value);
  return value;
}

const SOURCE_KEY = "atlas_analytics_acquisition_channel";

/**
 * Sticky, session-scoped acquisition source.
 *
 * The landing page is where `?ref=hn` and the HN referrer exist; by the time
 * the visitor clicks Download the referrer is our own site and the query
 * string is gone. Capturing it once per session and replaying it on every
 * later event is what makes the HN funnel measurable end to end.
 */
function acquisitionChannel(): string {
  try {
    const existing = sessionStorage.getItem(SOURCE_KEY);
    if (existing) return existing;
    const ref = (new URLSearchParams(window.location.search).get("ref") || "").trim().toLowerCase();
    let source = "unknown";
    if (ref === "hn" || ref === "hackernews" || ref === "hacker_news") {
      source = "hacker_news";
    } else if (document.referrer) {
      try {
        const host = new URL(document.referrer).hostname.toLowerCase();
        if (host === "news.ycombinator.com") source = "hacker_news";
        else if (host.endsWith(new URL(window.location.href).hostname)) source = existing || "unknown";
        else source = "referral";
      } catch { /* keep unknown */ }
    } else {
      source = "direct";
    }
    sessionStorage.setItem(SOURCE_KEY, source);
    return source;
  } catch {
    return "unknown";
  }
}

function campaignProperties(): Record<string, string> {
  const query = new URLSearchParams(window.location.search);
  const values: Record<string, string> = { acquisition_channel: acquisitionChannel() };
  const pairs: [string, string][] = [
    ["utm_source", "campaign_source"], ["utm_medium", "campaign_medium"], ["utm_campaign", "campaign_name"],
  ];
  for (const [source, target] of pairs) {
    const value = (query.get(source) || "").trim().slice(0, 80);
    if (/^[a-z0-9._-]+$/i.test(value)) values[target] = value;
  }
  return values;
}

export function trackAnalyticsEvent(
  eventName: AnalyticsEventName,
  options: {
    route?: string;
    properties?: Record<string, string | number | boolean>;
    deduplicationKey?: string;
    internal?: boolean;
  } = {}
) {
  if (typeof window === "undefined") return;
  try {
    const anonymousId = identifier(localStorage, ANON_KEY);
    const sessionId = identifier(sessionStorage, SESSION_KEY);
    const route = options.route || window.location.pathname;
    const clientKey = options.deduplicationKey || `${eventName}:${sessionId}:${route}`;
    const sentKey = `${SENT_PREFIX}${clientKey}`;
    if (sessionStorage.getItem(sentKey)) return;
    sessionStorage.setItem(sentKey, "1");
    const payload = JSON.stringify({
      eventName, anonymousId, sessionId, route,
      properties: options.properties || {}, deduplicationKey: clientKey, internal: options.internal === true,
    });
    // Honor server rate limiting: after a 429 we stop sending until the
    // Retry-After window passes instead of hammering the endpoint.
    const backoffUntil = Number(localStorage.getItem(BACKOFF_KEY) || 0);
    if (backoffUntil > Date.now()) return;
    // keepalive fetch survives page unload (sendBeacon cannot report 429s).
    void fetch("/api/analytics/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: payload,
      keepalive: true,
    })
      .then((res) => {
        if (res.status === 429) {
          const retry = Math.min(Number(res.headers.get("Retry-After")) || 60, 300);
          try { localStorage.setItem(BACKOFF_KEY, String(Date.now() + retry * 1000)); } catch { /* best-effort */ }
        }
      })
      .catch(() => { /* analytics never blocks the product */ });
  } catch {
    // Analytics is strictly best-effort; product interaction always wins.
  }
}

export default function AnalyticsClient() {
  const pathname = usePathname();

  useEffect(() => {
    const sessionId = identifier(sessionStorage, SESSION_KEY);
    trackAnalyticsEvent("site_visit", { deduplicationKey: `site_visit:${sessionId}`, properties: campaignProperties() });
    trackAnalyticsEvent("page_view", { route: pathname, properties: campaignProperties() });
  }, [pathname]);

  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      const anchor = (event.target as Element | null)?.closest?.("a[href]") as HTMLAnchorElement | null;
      if (!anchor) return;
      const href = anchor.getAttribute("href") || "";
      // The CTA must carry the session's acquisition source too, otherwise the
      // HN funnel breaks at exactly the step that matters most.
      if (href.startsWith("/download")) trackAnalyticsEvent("download_clicked", { properties: { surface: window.location.pathname, acquisition_channel: acquisitionChannel() }, deduplicationKey: crypto.randomUUID() });
    };
    document.addEventListener("click", onClick, true);
    return () => document.removeEventListener("click", onClick, true);
  }, []);

  return null;
}
