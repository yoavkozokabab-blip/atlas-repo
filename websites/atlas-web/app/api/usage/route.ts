import { currentSafeUser } from "@/app/_lib/auth";
import { freeFeatureGate } from "@/app/_lib/free-plan";
import { privateJson } from "@/app/_lib/http";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const user = await currentSafeUser();
  if (!user) return privateJson({ ok: false, error: "auth_required" }, { status: 401 });
  return privateJson({ ok: true, plan: "free", usage: freeFeatureGate().usage(user.id) });
}
