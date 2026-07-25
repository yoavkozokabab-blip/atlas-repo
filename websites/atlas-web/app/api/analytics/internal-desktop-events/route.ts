import { hasForbiddenAnalyticsData, isDesktopAnalyticsEvent } from "@/app/_lib/analytics-contract";
import {
  acceptsAnalyticsRequest,
  analyticsBody,
  DESKTOP_ANALYTICS_EVENT_KEYS,
  eventBatch,
} from "@/app/_lib/analytics-ingestion";
import { buildAnalyticsRow } from "@/app/_lib/analytics-server";
import { privateJson } from "@/app/_lib/http";
import {
  internalAnalyticsTestAuthorized,
  isSyntheticUuid,
} from "@/app/_lib/internal-analytics-test";
import {
  analyticsStoreErrorInfo,
  recordAnalyticsEvents,
} from "@/app/_lib/store";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  try {
    if (!internalAnalyticsTestAuthorized(req.headers)) {
      return privateJson({ ok: false, error: "not_found" }, { status: 404 });
    }
    if (!(await acceptsAnalyticsRequest(req, "desktop-internal-test", 30))) {
      return privateJson(
        { ok: false, error: "rate_limited" },
        { status: 429, headers: { "Retry-After": "60" } },
      );
    }
    const body = await analyticsBody(req);
    if (req.headers.has("origin") || req.headers.has("referer")) {
      return privateJson({ ok: false, error: "native_client_required" }, { status: 403 });
    }
    const events = body && eventBatch(body, DESKTOP_ANALYTICS_EVENT_KEYS);
    if (!events || events.some((event) => {
      if (!isDesktopAnalyticsEvent(event.eventName)) return true;
      if (!isSyntheticUuid(event.installationId) || !isSyntheticUuid(event.sessionId)) return true;
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
    const rows = events.map((event) => buildAnalyticsRow({
      eventName: event.eventName as Parameters<typeof buildAnalyticsRow>[0]["eventName"],
      source: "desktop",
      installationId: event.installationId,
      sessionId: event.sessionId,
      route: "/desktop",
      properties: event.properties,
      deduplicationKey: event.eventId,
      appVersion: event.appVersion,
      buildCommit: event.buildCommit,
      internal: true,
      request: req,
    }));
    const result = await recordAnalyticsEvents(rows);
    return privateJson(
      { ok: true, accepted: rows.length, recorded: result.recorded },
      { status: 202 },
    );
  } catch (error) {
    const detail = analyticsStoreErrorInfo(error);
    console.error("[atlas] internal_analytics_test_delivery_failed", {
      status: detail.status,
      code: detail.code,
    });
    return privateJson(
      { ok: false, error: "analytics_temporarily_unavailable" },
      { status: 503 },
    );
  }
}
