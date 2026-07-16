import { registerUser, issueSessionToken, entitlement } from "@/app/_lib/auth";
import { rateLimit, clientIp, readJson } from "@/app/_lib/ratelimit";
import { privateJson, unavailableJson } from "@/app/_lib/http";

export const runtime = "nodejs";

// Desktop registration (Phase 186A) — same user store as the website, returns a
// Bearer token instead of setting a cookie.
export async function POST(req: Request) {
  try {
    if (!(await rateLimit(`desktop-register:${clientIp(req)}`, 10, 3_600_000))) {
      return privateJson(
        { ok: false, error: "Too many attempts. Try again later." },
        { status: 429 }
      );
    }
    const body = await readJson(req);
    const r = await registerUser(
      String(body.email ?? ""),
      String(body.password ?? ""),
      body.name ? String(body.name) : undefined
    );
    if (!r.ok) return privateJson({ ok: false, error: r.error }, { status: 400 });
    return privateJson(
      { ok: true, token: await issueSessionToken(r.user.id), ...entitlement(r.user) },
      { status: 201 }
    );
  } catch {
    return unavailableJson();
  }
}
