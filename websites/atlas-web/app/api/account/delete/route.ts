import { currentUser, clearSession } from "@/app/_lib/auth";
import { store, newId } from "@/app/_lib/store";
import { readJson } from "@/app/_lib/ratelimit";
import { privateJson, unavailableJson } from "@/app/_lib/http";

export const runtime = "nodejs";

export async function POST(req: Request) {
  try {
    const user = await currentUser();
    if (!user) return privateJson({ ok: false, error: "auth_required" }, { status: 401 });

  // Destructive: require an explicit confirmation field from the client.
  const body = await readJson(req);
  if (String(body.confirm ?? "") !== "DELETE") {
    return privateJson({ ok: false, error: "confirmation_required" }, { status: 400 });
  }

  await store.audit({
    id: newId(),
    at: new Date().toISOString(),
    actorId: user.id,
    actorEmail: user.email,
    action: "account_self_delete",
    targetId: user.id,
    targetEmail: user.email,
  });
  await store.remove(user.id);
  await clearSession();
    return privateJson({ ok: true });
  } catch {
    return unavailableJson();
  }
}
