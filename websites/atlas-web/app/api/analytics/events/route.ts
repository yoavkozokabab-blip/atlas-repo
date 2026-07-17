import { currentSafeUser } from "@/app/_lib/auth";
import { isAnalyticsEvent } from "@/app/_lib/analytics-contract";
import { acceptsAnalyticsRequest, analyticsBody, eventBatch, WEBSITE_ANALYTICS_EVENT_KEYS } from "@/app/_lib/analytics-ingestion";
import { buildAnalyticsRow } from "@/app/_lib/analytics-server";
import { recordAnalyticsEvents } from "@/app/_lib/store";
import { privateJson } from "@/app/_lib/http";
import { csrfRejected, isTrustedBrowserWrite } from "@/app/_lib/request-security";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  try {
    if (!isTrustedBrowserWrite(req)) return csrfRejected();
    if (!(await acceptsAnalyticsRequest(req, "website", 60))) {
      return privateJson({ ok: false, error: "rate_limited" }, { status: 429, headers: { "Retry-After": "60" } });
    }
    const body = await analyticsBody(req);
    const events = body && eventBatch(body, WEBSITE_ANALYTICS_EVENT_KEYS);
    if (!events || events.some((event) => !isAnalyticsEvent(event.eventName))) {
      return privateJson({ ok: false, error: "invalid_event" }, { status: 400 });
    }
    const user = await currentSafeUser().catch(() => null);
    const rows = events.map((event) => buildAnalyticsRow({
      eventName: event.eventName as Parameters<typeof buildAnalyticsRow>[0]["eventName"],
      source: "website", anonymousId: event.anonymousId, sessionId: event.sessionId,
      route: event.route, properties: event.properties, deduplicationKey: event.deduplicationKey,
      internal: event.internal === true, userId: user?.id || null, request: req,
    }));
    const result = await recordAnalyticsEvents(rows);
    return privateJson({ ok: true, accepted: rows.length, recorded: result.recorded }, { status: 202 });
  } catch {
    // Never block navigation, auth or download flows because analytics failed.
    return privateJson({ ok: true, recorded: false }, { status: 202 });
  }
}
