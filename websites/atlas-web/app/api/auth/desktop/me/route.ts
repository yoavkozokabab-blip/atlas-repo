import { userFromBearer, entitlement } from "@/app/_lib/auth";
import { privateJson, unavailableJson } from "@/app/_lib/http";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Desktop entitlement check (Phase 186A) — the desktop calls this with its Bearer
// token to learn the current account + plan/subscription state. Single source of
// truth for feature gating.
export async function GET(req: Request) {
  try {
    const u = await userFromBearer(req);
    if (!u) return privateJson({ ok: false, error: "auth_required" }, { status: 401 });
    return privateJson({ ok: true, ...entitlement(u) });
  } catch {
    return unavailableJson();
  }
}
