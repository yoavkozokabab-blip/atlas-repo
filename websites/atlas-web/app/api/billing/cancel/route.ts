import { currentUser } from "@/app/_lib/auth";
import { cancelSubscription, renewSubscription } from "@/app/_lib/billing";
import { store, toSafe, newId } from "@/app/_lib/store";
import { readJson } from "@/app/_lib/ratelimit";
import { privateJson, unavailableJson } from "@/app/_lib/http";

export const runtime = "nodejs";

export async function POST(req: Request) {
  try {
  const user = await currentUser();
  if (!user) return privateJson({ ok: false, error: "auth_required" }, { status: 401 });
  const body = await readJson(req);
  const action = String(body.action ?? "cancel");

  if (action === "renew") {
    await renewSubscription(user);
  } else {
    await cancelSubscription(user);
  }
  await store.audit({
    id: newId(),
    at: new Date().toISOString(),
    actorId: user.id,
    actorEmail: user.email,
    action: `subscription_${action}`,
  });
  const fresh = (await store.getById(user.id))!;
  return privateJson({ ok: true, user: toSafe(fresh) });
  } catch {
    return unavailableJson();
  }
}
