import { requireAdmin } from "@/app/_lib/auth";
import { store, toSafe, newId, type User } from "@/app/_lib/store";
import { readJson } from "@/app/_lib/ratelimit";
import { privateJson, unavailableJson } from "@/app/_lib/http";

export const runtime = "nodejs";

const ALLOWED = new Set(["suspend", "restore", "revoke_license", "grant_pro"]);

export async function POST(req: Request) {
  try {
  const admin = await requireAdmin();
  if (!admin) return privateJson({ ok: false, error: "forbidden" }, { status: 403 });

  const body = await readJson(req);
  const action = String(body.action ?? "");
  const targetId = String(body.targetId ?? "");
  if (!ALLOWED.has(action)) return privateJson({ ok: false, error: "invalid_action" }, { status: 400 });

  const target = await store.getById(targetId);
  if (!target) return privateJson({ ok: false, error: "user_not_found" }, { status: 404 });

  let patch: Partial<User> = {};
  if (action === "suspend") patch = { status: "suspended" };
  else if (action === "restore") patch = { status: "active" };
  else if (action === "revoke_license") patch = { plan: "free", planStatus: "none", trialEndsAt: null, renewsAt: null };
  else if (action === "grant_pro") patch = { plan: "pro", planStatus: "active", renewsAt: new Date(Date.now() + 30 * 86_400_000).toISOString() };

  const updated = await store.update(target.id, patch);

  // Every admin action is audited.
  await store.audit({
    id: newId(),
    at: new Date().toISOString(),
    actorId: admin.id,
    actorEmail: admin.email,
    action: `admin_${action}`,
    targetId: target.id,
    targetEmail: target.email,
    meta: patch as Record<string, unknown>,
  });

  return privateJson({ ok: true, user: updated ? toSafe(updated) : null });
  } catch {
    return unavailableJson();
  }
}
