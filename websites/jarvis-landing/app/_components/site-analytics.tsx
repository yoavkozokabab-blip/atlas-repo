"use client";

import { useEffect } from "react";
import { trackClientEvent } from "../_lib/analytics-client";

export function SiteAnalytics() {
  useEffect(() => {
    trackClientEvent("site_visit", { page: window.location.pathname });
    const onClick = (ev: MouseEvent) => {
      const el = ev.target as HTMLElement | null;
      const link = el?.closest("a[data-analytics-event]") as HTMLAnchorElement | null;
      if (!link) return;
      const eventName = link.getAttribute("data-analytics-event");
      if (eventName) {
        trackClientEvent(eventName, { page: window.location.pathname });
      }
    };
    document.addEventListener("click", onClick);
    return () => document.removeEventListener("click", onClick);
  }, []);
  return null;
}
