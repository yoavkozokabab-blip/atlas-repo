import { currentUser } from "@/app/_lib/auth";
import { BILLING_NOT_AVAILABLE, billingPortal } from "@/app/_lib/billing";
import { PAID_PLANS_ENABLED } from "@/app/_config";
import { privateJson, unavailableJson } from "@/app/_lib/http";
import { csrfRejected, isTrustedBrowserWrite } from "@/app/_lib/request-security";

export const runtime = "nodejs";

export async function POST(req: Request) {
  try {
    if (!isTrustedBrowserWrite(req)) return csrfRejected();
    const user = await currentUser();
    if (!user) return privateJson({ ok: false, error: "auth_required" }, { status: 401 });
    if (!PAID_PLANS_ENABLED) return privateJson({ ok: false, error: BILLING_NOT_AVAILABLE }, { status: 503 });
    const r = await billingPortal(user);
    return privateJson({ ok: true, mode: r.mode, url: r.url });
  } catch {
    return unavailableJson();
  }
}
