import { loginUser, createToken, entitlement } from "@/app/_lib/auth";
import { rateLimit, clientIp, readJson } from "@/app/_lib/ratelimit";
import { privateJson, unavailableJson } from "@/app/_lib/http";

export const runtime = "nodejs";

// Desktop login (Phase 186A) — same user store as the website. Keeps the generic
// anti-enumeration error from loginUser. Returns a Bearer token.
export async function POST(req: Request) {
  try {
    if (!(await rateLimit(`desktop-login:${clientIp(req)}`, 8, 900_000))) {
      return privateJson(
        { ok: false, error: "Too many login attempts. Please wait a few minutes." },
        { status: 429 }
      );
    }
    const body = await readJson(req);
    const r = await loginUser(String(body.email ?? ""), String(body.password ?? ""));
    if (!r.ok) return privateJson({ ok: false, error: r.error }, { status: 401 });
    return privateJson({ ok: true, token: createToken(r.user.id), ...entitlement(r.user) });
  } catch {
    return unavailableJson();
  }
}
