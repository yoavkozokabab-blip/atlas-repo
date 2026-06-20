import { NextResponse } from "next/server";
import { currentUser } from "@/app/_lib/auth";
import { startCheckout, isPlanId } from "@/app/_lib/billing";
import { readJson } from "@/app/_lib/ratelimit";
import { PAID_PLANS_ENABLED } from "@/app/_config";

export const runtime = "nodejs";

export async function POST(req: Request) {
  // Free-beta guard (Phase 186A): no checkout — not even the local stub trial —
  // while paid plans are disabled. Nothing here can grant a fake subscription.
  if (!PAID_PLANS_ENABLED) {
    return NextResponse.json(
      { ok: false, error: "Atlas is in free beta — there is nothing to purchase yet." },
      { status: 403 }
    );
  }
  const user = await currentUser();
  if (!user) return NextResponse.json({ ok: false, error: "auth_required" }, { status: 401 });
  const body = await readJson(req);
  const plan = String(body.plan ?? "");
  if (!isPlanId(plan)) return NextResponse.json({ ok: false, error: "invalid_plan" }, { status: 400 });
  // Stub mode: grants a local trial, never charges. See billing.ts.
  const r = await startCheckout(user, plan);
  return NextResponse.json({ ok: true, mode: r.mode, url: r.url });
}
