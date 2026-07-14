import { NextResponse } from "next/server";
import { registerUser, createToken, entitlement } from "@/app/_lib/auth";
import { rateLimit, clientIp, readJson } from "@/app/_lib/ratelimit";

export const runtime = "nodejs";

// Desktop registration — same user store as the website, returns a
// Bearer token instead of setting a cookie.
export async function POST(req: Request) {
  if (!(await rateLimit(`desktop-register:${clientIp(req)}`, 10, 3_600_000))) {
    return NextResponse.json({ ok: false, error: "Too many attempts. Try again later." }, { status: 429 });
  }
  const body = await readJson(req);
  const r = await registerUser(
    String(body.email ?? ""),
    String(body.password ?? ""),
    body.name ? String(body.name) : undefined
  );
  if (!r.ok) return NextResponse.json({ ok: false, error: r.error }, { status: 400 });
  return NextResponse.json({ ok: true, token: createToken(r.user.id), ...entitlement(r.user) }, { status: 201 });
}
