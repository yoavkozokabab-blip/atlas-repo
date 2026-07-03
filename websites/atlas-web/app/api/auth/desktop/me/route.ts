import { NextResponse } from "next/server";
import { userFromBearer, entitlement } from "@/app/_lib/auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Desktop entitlement check (Phase 186A) — the desktop calls this with its Bearer
// token to learn the current account + plan/subscription state. Single source of
// truth for feature gating.
export async function GET(req: Request) {
  const u = await userFromBearer(req);
  if (!u) return NextResponse.json({ ok: false, error: "auth_required" }, { status: 401 });
  return NextResponse.json({ ok: true, ...entitlement(u) });
}
