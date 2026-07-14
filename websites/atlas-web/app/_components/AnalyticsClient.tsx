"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import type { AnalyticsEventName } from "../_lib/analytics-contract";

const ANON_KEY = "atlas_analytics_anonymous_id";
const SESSION_KEY = "atlas_analytics_session_id";
const SENT_PREFIX = "atlas_analytics_sent:";

function identifier(storage: Storage, key: string): string {
  const existing = storage.getItem(key);
  if (existing) return existing;
  const value = crypto.randomUUID();
  storage.setItem(key, value);
  return value;
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
      eventName,
      anonymousId,
      sessionId,
      route,
      properties: options.properties || {},
      deduplicationKey: clientKey,
      internal: options.internal === true,
    });
    if (navigator.sendBeacon) {
      navigator.sendBeacon("/api/analytics/events", new Blob([payload], { type: "application/json" }));
    } else {
      void fetch("/api/analytics/events", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: payload,
        keepalive: true,
      });
    }
  } catch {
    // Analytics must never block or break product behavior.
  }
}

export default function AnalyticsClient() {
  const pathname = usePathname();

  useEffect(() => {
    const sessionId = identifier(sessionStorage, SESSION_KEY);
    trackAnalyticsEvent("site_visit", { deduplicationKey: `site_visit:${sessionId}` });
    trackAnalyticsEvent("page_view", { route: pathname });
    if (pathname === "/pricing") trackAnalyticsEvent("pricing_viewed", { route: pathname });
    if (document.querySelector('[data-analytics-state="download-unavailable"]')) {
      trackAnalyticsEvent("download_unavailable_seen", { route: pathname });
    }
  }, [pathname]);

  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      const anchor = (event.target as Element | null)?.closest?.("a[href]") as HTMLAnchorElement | null;
      if (!anchor) return;
      const href = anchor.getAttribute("href") || "";
      if (/github\.com/i.test(href)) {
        trackAnalyticsEvent("github_clicked", { properties: { href_kind: "github" }, deduplicationKey: crypto.randomUUID() });
      } else if (href === "/docs" || href.startsWith("/docs?")) {
        trackAnalyticsEvent("docs_clicked", { properties: { href_kind: "docs" }, deduplicationKey: crypto.randomUUID() });
      } else if (href.startsWith("/download")) {
        trackAnalyticsEvent("download_clicked", { properties: { surface: window.location.pathname }, deduplicationKey: crypto.randomUUID() });
      }
    };
    document.addEventListener("click", onClick, true);
    return () => document.removeEventListener("click", onClick, true);
  }, []);

  return null;
}
