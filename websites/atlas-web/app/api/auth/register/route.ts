import { registerUser, setSession } from "@/app/_lib/auth";
import { toSafe } from "@/app/_lib/store";
import { rateLimit, clientIp, readJson } from "@/app/_lib/ratelimit";
import { privateJson, unavailableJson } from "@/app/_lib/http";
import { csrfRejected, isTrustedBrowserWrite } from "@/app/_lib/request-security";

export const runtime = "nodejs";

export async function POST(req: Request) {
  try {
    if (!isTrustedBrowserWrite(req)) return csrfRejected();
    if (!(await rateLimit(`register:${clientIp(req)}`, 10, 3_600_000))) {
      return privateJson({ ok: false, error: "Too many attempts. Try again later." }, { status: 429 });
    }
    const body = await readJson(req);
    const r = await registerUser(
      String(body.email ?? ""),
      String(body.password ?? ""),
      body.name ? String(body.name) : undefined
    );
    if (!r.ok) return privateJson({ ok: false, error: r.error }, { status: 400 });
    await setSession(r.user.id);
    return privateJson({ ok: true, user: toSafe(r.user) }, { status: 201 });
  } catch {
    return unavailableJson();
  }
}
