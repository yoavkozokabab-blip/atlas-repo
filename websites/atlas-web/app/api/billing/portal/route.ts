import { NextResponse } from "next/server";
import { currentUser } from "@/app/_lib/auth";
import { billingPortal } from "@/app/_lib/billing";

export const runtime = "nodejs";

export async function POST() {
  const user = await currentUser();
  if (!user) return NextResponse.json({ ok: false, error: "auth_required" }, { status: 401 });
  const r = billingPortal(user);
  return NextResponse.json({ ok: true, mode: r.mode, url: r.url });
}
