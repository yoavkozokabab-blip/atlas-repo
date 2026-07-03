import { NextResponse } from "next/server";
import { currentUser } from "@/app/_lib/auth";
import { cancelSubscription, renewSubscription } from "@/app/_lib/billing";
import { store, toSafe, newId } from "@/app/_lib/store";
import { readJson } from "@/app/_lib/ratelimit";

export const runtime = "nodejs";

export async function POST(req: Request) {
  const user = await currentUser();
  if (!user) return NextResponse.json({ ok: false, error: "auth_required" }, { status: 401 });
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
  return NextResponse.json({ ok: true, user: toSafe(fresh) });
}
