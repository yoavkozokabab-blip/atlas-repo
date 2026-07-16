import { currentUser, clearSession } from "@/app/_lib/auth";
import { store } from "@/app/_lib/store";
import { readJson } from "@/app/_lib/ratelimit";
import { privateJson, unavailableJson } from "@/app/_lib/http";
import { csrfRejected, isTrustedBrowserWrite } from "@/app/_lib/request-security";

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

  await store.deleteAccount(user);
  await clearSession();
    return privateJson({ ok: true });
  } catch {
    return unavailableJson();
  }
}
