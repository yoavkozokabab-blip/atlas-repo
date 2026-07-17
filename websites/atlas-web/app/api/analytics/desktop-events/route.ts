import { userFromBearer } from "@/app/_lib/auth";
import { isAnalyticsEvent } from "@/app/_lib/analytics-contract";
import { acceptsAnalyticsRequest, analyticsBody, DESKTOP_ANALYTICS_EVENT_KEYS, eventBatch } from "@/app/_lib/analytics-ingestion";
import { buildAnalyticsRow } from "@/app/_lib/analytics-server";
import { recordAnalyticsEvents } from "@/app/_lib/store";
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
    if (!events || events.some((event) => !isAnalyticsEvent(event.eventName))) {
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
  } catch {
    return privateJson({ ok: true, accepted: 0, recorded: 0 }, { status: 202 });
  }
}
