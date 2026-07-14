import { currentSafeUser } from "@/app/_lib/auth";
import { isAnalyticsEvent } from "@/app/_lib/analytics-contract";
import { buildAnalyticsRow } from "@/app/_lib/analytics-server";
import { recordAnalyticsEvent } from "@/app/_lib/store";
import { privateJson } from "@/app/_lib/http";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  try {
    const body = await req.json().catch(() => ({}));
    if (!isAnalyticsEvent(body.eventName)) {
      return privateJson({ ok: false, error: "invalid_event" }, { status: 400 });
    }
    const user = await currentSafeUser().catch(() => null);
    const row = buildAnalyticsRow({
      eventName: body.eventName,
      source: "website",
      anonymousId: body.anonymousId,
      sessionId: body.sessionId,
      route: body.route,
      properties: body.properties,
      deduplicationKey: body.deduplicationKey,
      internal: body.internal === true,
      userId: user?.id || null,
    });
    const result = await recordAnalyticsEvent(row);
    return privateJson({ ok: true, recorded: result.recorded }, { status: 202 });
  } catch {
    // Never block navigation, auth or download flows because analytics failed.
    return privateJson({ ok: true, recorded: false }, { status: 202 });
  }
}
