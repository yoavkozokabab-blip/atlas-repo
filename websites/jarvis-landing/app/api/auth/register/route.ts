import { NextResponse } from "next/server";
import { registerUser, setSession } from "@/app/_lib/auth";
import { toSafe } from "@/app/_lib/store";
import { rateLimit, clientIp, readJson } from "@/app/_lib/ratelimit";

export const runtime = "nodejs";

export async function POST(req: Request) {
  if (!(await rateLimit(`register:${clientIp(req)}`, 10, 3_600_000))) {
    return NextResponse.json({ ok: false, error: "Too many attempts. Try again later." }, { status: 429 });
  }
  const body = await readJson(req);
  const r = await registerUser(
    String(body.email ?? ""),
    String(body.password ?? ""),
    body.name ? String(body.name) : undefined
  );
  if (!r.ok) return NextResponse.json({ ok: false, error: r.error }, { status: 400 });
  await setSession(r.user.id);
  return NextResponse.json({ ok: true, user: toSafe(r.user) }, { status: 201 });
}
