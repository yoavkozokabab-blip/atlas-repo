import { NextResponse } from "next/server";
import { loginUser, createToken, entitlement } from "@/app/_lib/auth";
import { rateLimit, clientIp, readJson } from "@/app/_lib/ratelimit";

export const runtime = "nodejs";

// Desktop login — same user store as the website. Keeps the generic
// anti-enumeration error from loginUser. Returns a Bearer token.
export async function POST(req: Request) {
  if (!(await rateLimit(`desktop-login:${clientIp(req)}`, 8, 900_000))) {
    return NextResponse.json({ ok: false, error: "Too many login attempts. Please wait a few minutes." }, { status: 429 });
  }
  const body = await readJson(req);
  const r = await loginUser(String(body.email ?? ""), String(body.password ?? ""));
  if (!r.ok) return NextResponse.json({ ok: false, error: r.error }, { status: 401 });
  return NextResponse.json({ ok: true, token: createToken(r.user.id), ...entitlement(r.user) });
}
