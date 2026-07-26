import { userFromBearer } from "@/app/_lib/auth";
import {
  hasForbiddenAnalyticsData,
  hasOnlyPrimitiveAnalyticsProperties,
  isCanonicalAnalyticsUuid,
  isDesktopAnalyticsEvent,
} from "@/app/_lib/analytics-contract";
import { acceptsAnalyticsRequest, analyticsBody, DESKTOP_ANALYTICS_EVENT_KEYS, eventBatch } from "@/app/_lib/analytics-ingestion";
import { buildAnalyticsRow } from "@/app/_lib/analytics-server";
import { analyticsStoreErrorInfo, recordAnalyticsEvents } from "@/app/_lib/store";
import { privateJson } from "@/app/_lib/http";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  try {
    if (!(await acceptsAnalyticsRequest(req, "desktop", 30))) {
      return privateJson({ ok: false, error: "rate_limited" }, { status: 429, headers: { "Retry-After": "60" } });
    }
    const body = await analyticsBody(req);
    // Desktop delivery is a native client protocol. Browser-originated posts
    // are never accepted on this endpoint, even if the Origin is the Atlas
    // site; the browser uses /api/analytics/events instead.
    if (req.headers.has("origin") || req.headers.has("referer")) {
      return privateJson({ ok: false, error: "native_client_required" }, { status: 403 });
    }
    const events = body && eventBatch(body, DESKTOP_ANALYTICS_EVENT_KEYS);
    if (!events || events.some((event) => {
      if (!isDesktopAnalyticsEvent(event.eventName)) return true;
      if (!isCanonicalAnalyticsUuid(event.installationId)) return true;
      if (!hasOnlyPrimitiveAnalyticsProperties(event.properties)) return true;
      // Repository/privacy data must not enter through identity or build
      // fields either. Event names are checked separately because the
      // contract intentionally contains `real_repo_scan_completed`.
      return hasForbiddenAnalyticsData({
        installationId: event.installationId,
        sessionId: event.sessionId,
        appVersion: event.appVersion,
        buildCommit: event.buildCommit,
        properties: event.properties,
      });
    })) {
      return privateJson({ ok: false, error: "invalid_event" }, { status: 400 });
    }
    const user = await userFromBearer(req).catch(() => null);
    const rows = events.map((event) => buildAnalyticsRow({
      eventName: event.eventName as Parameters<typeof buildAnalyticsRow>[0]["eventName"],
      source: "desktop", installationId: event.installationId, sessionId: event.sessionId,
      route: "/desktop", properties: event.properties, deduplicationKey: event.eventId,
      appVersion: event.appVersion, buildCommit: event.buildCommit, userId: user?.id || null, request: req,
    }));
    const result = await recordAnalyticsEvents(rows);
    return privateJson({ ok: true, accepted: rows.length, recorded: result.recorded }, { status: 202 });
  } catch (error) {
    // Preserve operational evidence without returning a raw PostgREST error or
    // any request content to the desktop.  A 5xx lets the bounded native
    // outbox retry; falsely returning 202 used to discard real 400 failures.
    const detail = analyticsStoreErrorInfo(error);
    console.error("[atlas] desktop_analytics_delivery_failed", {
      status: detail.status,
      code: detail.code,
    });
    return privateJson({ ok: false, error: "analytics_temporarily_unavailable" }, { status: 503 });
  }
}
