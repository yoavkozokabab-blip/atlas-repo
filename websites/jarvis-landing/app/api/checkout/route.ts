import { NextResponse } from "next/server";
import { currentUser } from "@/app/_lib/auth";
import { startCheckout, isPlanId } from "@/app/_lib/billing";
import { readJson } from "@/app/_lib/ratelimit";

export const runtime = "nodejs";

export async function POST(req: Request) {
  const user = await currentUser();
  if (!user) return NextResponse.json({ ok: false, error: "auth_required" }, { status: 401 });
  const body = await readJson(req);
  const plan = String(body.plan ?? "");
  if (!isPlanId(plan)) return NextResponse.json({ ok: false, error: "invalid_plan" }, { status: 400 });
  // Stub mode: grants a local trial, never charges. See billing.ts.
  const r = await startCheckout(user, plan);
  return NextResponse.json({ ok: true, mode: r.mode, url: r.url });
}
