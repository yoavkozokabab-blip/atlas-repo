import { NextResponse } from "next/server";
import { userFromBearer, entitlement } from "@/app/_lib/auth";
import { trackEvent } from "@/app/_lib/analytics";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Desktop entitlement check (Phase 186A) — the desktop calls this with its Bearer
// token to learn the current account + plan/subscription state. Single source of
// truth for feature gating.
export async function GET(req: Request) {
  const u = await userFromBearer(req);
  if (!u) {
    await trackEvent({
      event_name: "api_me_failed",
      source: "api",
      metadata: { reason: "auth_required" },
    });
    return NextResponse.json({ ok: false, error: "auth_required" }, { status: 401 });
  }
  await trackEvent({
    event_name: "api_me_success",
    source: "api",
    user_id: u.id,
    metadata: {},
  });
  return NextResponse.json({ ok: true, ...entitlement(u) });
}
