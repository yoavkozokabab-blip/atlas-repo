import { currentUser } from "@/app/_lib/auth";
import { BILLING_NOT_AVAILABLE, startCheckout, isPlanId } from "@/app/_lib/billing";
import { readJson } from "@/app/_lib/ratelimit";
import { PAID_PLANS_ENABLED } from "@/app/_config";
import { privateJson, unavailableJson } from "@/app/_lib/http";
import { csrfRejected, isTrustedBrowserWrite } from "@/app/_lib/request-security";

export const runtime = "nodejs";

export async function POST(req: Request) {
  if (!isTrustedBrowserWrite(req)) return csrfRejected();
  // Guard for deployments that intentionally hide paid-plan actions.
  if (!PAID_PLANS_ENABLED) {
    return privateJson(
      { ok: false, error: BILLING_NOT_AVAILABLE },
      { status: 503 }
    );
  }
  try {
    const user = await currentUser();
    if (!user) return privateJson({ ok: false, error: "auth_required" }, { status: 401 });
    const body = await readJson(req);
    const plan = String(body.plan ?? "");
    if (!isPlanId(plan)) return privateJson({ ok: false, error: "invalid_plan" }, { status: 400 });
    const r = await startCheckout(user, plan);
    return privateJson({ ok: true, mode: r.mode, url: r.url });
  } catch (err) {
    const code = typeof err === "object" && err && "code" in err ? String((err as { code: unknown }).code) : "checkout_failed";
    const message = err instanceof Error ? err.message : "Checkout failed.";
    const status = code === BILLING_NOT_AVAILABLE || code === "team_not_billed" ? 503 : 500;
    if (code === "checkout_failed") return unavailableJson();
    return privateJson({ ok: false, error: code, message }, { status });
  }
}
