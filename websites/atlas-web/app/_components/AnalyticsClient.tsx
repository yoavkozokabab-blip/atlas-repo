"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import type { AnalyticsEventName } from "../_lib/analytics-contract";

const ANON_KEY = "atlas_analytics_anonymous_id";
const SESSION_KEY = "atlas_analytics_session_id";
const SENT_PREFIX = "atlas_analytics_sent:";
const INTERACTION_GRACE_MS = 60_000;
const HEARTBEAT_MS = 15_000;

function identifier(storage: Storage, key: string): string {
  const existing = storage.getItem(key);
  if (existing) return existing;
  const value = crypto.randomUUID();
  storage.setItem(key, value);
  return value;
}

function campaignProperties(): Record<string, string> {
  const query = new URLSearchParams(window.location.search);
  const values: Record<string, string> = {};
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
    if (navigator.sendBeacon) {
      navigator.sendBeacon("/api/analytics/events", new Blob([payload], { type: "application/json" }));
    } else {
      void fetch("/api/analytics/events", { method: "POST", headers: { "Content-Type": "application/json" }, body: payload, keepalive: true });
    }
  } catch {
    // Analytics is strictly best-effort; product interaction always wins.
  }
}

function usePageActiveTime(pathname: string) {
  useEffect(() => {
    const sessionId = identifier(sessionStorage, SESSION_KEY);
    const startedAt = Date.now();
    let lastTick = performance.now();
    let activeSinceLastHeartbeat = 0;
    let totalActive = 0;
    let lastInteraction = 0;
    let focused = document.hasFocus();
    let closed = false;

    const activeNow = () => !document.hidden && focused && Date.now() - lastInteraction <= INTERACTION_GRACE_MS;
    const accrue = () => {
      const now = performance.now();
      if (activeNow()) {
        const delta = Math.max(0, Math.min(now - lastTick, HEARTBEAT_MS * 2));
        totalActive += delta;
        activeSinceLastHeartbeat += delta;
      }
      lastTick = now;
    };
    const markInteraction = () => { accrue(); lastInteraction = Date.now(); };
    const heartbeat = () => {
      accrue();
      if (activeSinceLastHeartbeat < 1) return;
      const duration = Math.round(activeSinceLastHeartbeat);
      activeSinceLastHeartbeat = 0;
      trackAnalyticsEvent("page_active_heartbeat", {
        route: pathname, properties: { duration_active_ms: duration }, deduplicationKey: crypto.randomUUID(),
      });
    };
    const finish = () => {
      if (closed) return;
      closed = true;
      accrue();
      trackAnalyticsEvent("page_active_ended", {
        route: pathname,
        properties: { duration_active_ms: Math.round(totalActive), duration_elapsed_ms: Math.max(0, Date.now() - startedAt) },
        deduplicationKey: `page_active_ended:${sessionId}:${pathname}:${startedAt}`,
      });
    };
    const onFocus = () => { accrue(); focused = true; };
    const onBlur = () => { accrue(); focused = false; };
    const onVisibility = () => { accrue(); };
    const interactions = ["pointerdown", "keydown", "scroll", "touchstart"] as const;
    interactions.forEach((type) => window.addEventListener(type, markInteraction, { passive: true }));
    window.addEventListener("focus", onFocus);
    window.addEventListener("blur", onBlur);
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("pagehide", finish);
    const timer = window.setInterval(heartbeat, HEARTBEAT_MS);
    return () => {
      window.clearInterval(timer);
      interactions.forEach((type) => window.removeEventListener(type, markInteraction));
      window.removeEventListener("focus", onFocus); window.removeEventListener("blur", onBlur);
      document.removeEventListener("visibilitychange", onVisibility); window.removeEventListener("pagehide", finish);
      finish();
    };
  }, [pathname]);
}

export default function AnalyticsClient() {
  const pathname = usePathname();
  usePageActiveTime(pathname);

  useEffect(() => {
    const sessionId = identifier(sessionStorage, SESSION_KEY);
    trackAnalyticsEvent("site_visit", { deduplicationKey: `site_visit:${sessionId}`, properties: campaignProperties() });
    trackAnalyticsEvent("page_view", { route: pathname, properties: campaignProperties() });
    if (pathname === "/pricing") trackAnalyticsEvent("pricing_viewed", { route: pathname });
    if (document.querySelector('[data-analytics-state="download-unavailable"]')) trackAnalyticsEvent("download_unavailable_seen", { route: pathname });
  }, [pathname]);

  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      const anchor = (event.target as Element | null)?.closest?.("a[href]") as HTMLAnchorElement | null;
      if (!anchor) return;
      const href = anchor.getAttribute("href") || "";
      if (/github\.com/i.test(href)) trackAnalyticsEvent("github_clicked", { properties: { href_kind: "github" }, deduplicationKey: crypto.randomUUID() });
      else if (href === "/docs" || href.startsWith("/docs?")) trackAnalyticsEvent("docs_clicked", { properties: { href_kind: "docs" }, deduplicationKey: crypto.randomUUID() });
      else if (href.startsWith("/download")) trackAnalyticsEvent("download_clicked", { properties: { surface: window.location.pathname }, deduplicationKey: crypto.randomUUID() });
    };
    document.addEventListener("click", onClick, true);
    return () => document.removeEventListener("click", onClick, true);
  }, []);

  return null;
}
