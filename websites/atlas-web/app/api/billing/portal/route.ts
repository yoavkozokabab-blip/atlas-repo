import { currentUser } from "@/app/_lib/auth";
import { billingPortal } from "@/app/_lib/billing";
import { privateJson, unavailableJson } from "@/app/_lib/http";

export const runtime = "nodejs";

export async function POST() {
  try {
    const user = await currentUser();
    if (!user) return privateJson({ ok: false, error: "auth_required" }, { status: 401 });
    const r = billingPortal(user);
    return privateJson({ ok: true, mode: r.mode, url: r.url });
  } catch {
    return unavailableJson();
  }
}
