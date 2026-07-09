import { NextResponse } from "next/server";
import { currentUser } from "@/app/_lib/auth";
import { startCheckout, isPlanId } from "@/app/_lib/billing";
import { readJson } from "@/app/_lib/ratelimit";
import { PAID_PLANS_ENABLED } from "@/app/_config";

export const runtime = "nodejs";

export async function POST(req: Request) {
  // Guard for deployments that intentionally hide paid-plan actions.
  if (!PAID_PLANS_ENABLED) {
    return NextResponse.json(
      { ok: false, error: "Pro trial checkout is not available in this build." },
      { status: 403 }
    );
  }
  const user = await currentUser();
  if (!user) return NextResponse.json({ ok: false, error: "auth_required" }, { status: 401 });
  const body = await readJson(req);
  const plan = String(body.plan ?? "");
  if (!isPlanId(plan)) return NextResponse.json({ ok: false, error: "invalid_plan" }, { status: 400 });
  try {
    const r = await startCheckout(user, plan);
    return NextResponse.json({ ok: true, mode: r.mode, url: r.url });
  } catch (err) {
    const code = typeof err === "object" && err && "code" in err ? String((err as { code: unknown }).code) : "checkout_failed";
    const message = err instanceof Error ? err.message : "Checkout failed.";
    const status = code === "billing_not_configured" || code === "team_not_billed" ? 503 : 500;
    return NextResponse.json({ ok: false, error: code, message }, { status });
  }
}
