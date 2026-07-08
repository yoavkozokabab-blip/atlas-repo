import { NextResponse } from "next/server";
import { trackEvent } from "@/app/_lib/analytics";
import { currentUser } from "@/app/_lib/auth";
import { ENV } from "@/app/_lib/config";
import { rateLimit, clientIp, readJson } from "@/app/_lib/ratelimit";

export const runtime = "nodejs";

export async function POST(req: Request) {
  if (!(await rateLimit(`events:${clientIp(req)}`, 120, 3_600_000))) {
    return NextResponse.json({ ok: false, error: "rate_limited" }, { status: 429 });
  }
  const body = await readJson(req);
  const user = await currentUser();
  const result = await trackEvent({
    event_name: String(body.event_name ?? ""),
    anonymous_id: body.anonymous_id ? String(body.anonymous_id) : null,
    source: String(body.source ?? "website"),
    app_version: body.app_version ? String(body.app_version) : ENV.appVersion,
    platform: body.platform ? String(body.platform) : null,
    user_id: user?.id ?? null,
    metadata: (body.metadata as Record<string, unknown>) || {},
  });
  if (result.skipped) {
    return NextResponse.json({ ok: false, error: result.error || "invalid_event" }, { status: 400 });
  }
  return NextResponse.json({ ok: result.ok, persisted: result.ok });
}
