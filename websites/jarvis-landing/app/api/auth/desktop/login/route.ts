import { NextResponse } from "next/server";
import { loginUser, createToken, entitlement } from "@/app/_lib/auth";
import { trackEvent } from "@/app/_lib/analytics";
import { rateLimit, clientIp, readJson } from "@/app/_lib/ratelimit";

export const runtime = "nodejs";

// Desktop login (Phase 186A) — same user store as the website. Keeps the generic
// anti-enumeration error from loginUser. Returns a Bearer token.
export async function POST(req: Request) {
  if (!(await rateLimit(`desktop-login:${clientIp(req)}`, 8, 900_000))) {
    return NextResponse.json({ ok: false, error: "Too many login attempts. Please wait a few minutes." }, { status: 429 });
  }
  const body = await readJson(req);
  await trackEvent({
    event_name: "api_desktop_login_started",
    source: "api",
    platform: String(body.platform ?? "desktop"),
    app_version: body.app_version ? String(body.app_version) : null,
    metadata: {},
  });
  const r = await loginUser(String(body.email ?? ""), String(body.password ?? ""));
  if (!r.ok) {
    await trackEvent({
      event_name: "api_desktop_login_failed",
      source: "api",
      platform: String(body.platform ?? "desktop"),
      metadata: { reason: "invalid_credentials" },
    });
    return NextResponse.json({ ok: false, error: r.error }, { status: 401 });
  }
  await trackEvent({
    event_name: "api_desktop_login_success",
    source: "api",
    user_id: r.user.id,
    platform: String(body.platform ?? "desktop"),
    app_version: body.app_version ? String(body.app_version) : null,
    metadata: {},
  });
  return NextResponse.json({ ok: true, token: createToken(r.user.id), ...entitlement(r.user) });
}
