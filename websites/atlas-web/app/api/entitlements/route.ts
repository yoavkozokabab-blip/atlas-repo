import { currentSafeUser } from "@/app/_lib/auth";
import { privateJson } from "@/app/_lib/http";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const user = await currentSafeUser();
  if (!user) return privateJson({ ok: false, error: "auth_required" }, { status: 401 });
  // Payments are disabled, so this endpoint never trusts a browser-provided
  // plan or a stale local claim.
  return privateJson({ ok: true, plan: "free", billingAvailable: false });
}
