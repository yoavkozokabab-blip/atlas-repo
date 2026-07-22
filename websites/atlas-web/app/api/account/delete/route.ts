import { currentUser, clearSession } from "@/app/_lib/auth";
import { store } from "@/app/_lib/store";
import { readJson } from "@/app/_lib/ratelimit";
import { privateJson, unavailableJson } from "@/app/_lib/http";
import { csrfRejected, isTrustedBrowserWrite } from "@/app/_lib/request-security";
import { ENV } from "@/app/_lib/config";

export const runtime = "nodejs";

export async function POST(req: Request) {
  try {
    if (!isTrustedBrowserWrite(req)) return csrfRejected();
    const user = await currentUser();
    if (!user) return privateJson({ ok: false, error: "auth_required" }, { status: 401 });

  // Destructive: require an explicit confirmation field from the client.
  const body = await readJson(req);
  if (String(body.confirm ?? "") !== "DELETE") {
    return privateJson({ ok: false, error: "confirmation_required" }, { status: 400 });
  }

  // Explicitly revoke every session before deleting the account. The database
  // migration also cascades sessions on deletion, but this keeps the invariant
  // true for the local/test backend and records fail closed on partial failure.
  await store.revokeSessionsForUser(user.id);
  await store.deleteAccount(user);
  if (ENV.authBridgeEnabled && ENV.hasSupabase && user.authUserId) {
    const { deleteAuthIdentity } = await import("@/app/_lib/supabase-auth");
    // The database trigger has already queued this Auth id. Successful Auth
    // deletion removes the queue row through its FK; failure leaves a durable,
    // server-only deletion request for an operator retry.
    await deleteAuthIdentity(user.authUserId);
  }
  await clearSession();
    return privateJson({ ok: true });
  } catch {
    return unavailableJson();
  }
}
