import { NextResponse } from "next/server";
import { loginUser, setSession } from "@/app/_lib/auth";
import { toSafe } from "@/app/_lib/store";
import { rateLimit, clientIp, readJson } from "@/app/_lib/ratelimit";

export const runtime = "nodejs";

export async function POST(req: Request) {
  if (!(await rateLimit(`login:${clientIp(req)}`, 8, 900_000))) {
    return NextResponse.json({ ok: false, error: "Too many login attempts. Please wait a few minutes." }, { status: 429 });
  }
  const body = await readJson(req);
  const r = await loginUser(String(body.email ?? ""), String(body.password ?? ""));
  if (!r.ok) return NextResponse.json({ ok: false, error: r.error }, { status: 401 });
  await setSession(r.user.id);
  return NextResponse.json({ ok: true, user: toSafe(r.user) });
}
