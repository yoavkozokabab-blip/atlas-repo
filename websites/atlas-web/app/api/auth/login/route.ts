import { loginUser, setSession } from "@/app/_lib/auth";
import { toSafe } from "@/app/_lib/store";
import { rateLimit, clientIp, readJson } from "@/app/_lib/ratelimit";
import { privateJson, unavailableJson } from "@/app/_lib/http";
import { csrfRejected, isTrustedBrowserWrite } from "@/app/_lib/request-security";

export const runtime = "nodejs";

export async function POST(req: Request) {
  try {
    if (!isTrustedBrowserWrite(req)) return csrfRejected();
    if (!(await rateLimit(`login:${clientIp(req)}`, 8, 900_000))) {
      return privateJson({ ok: false, error: "Too many login attempts. Please wait a few minutes." }, { status: 429 });
    }
    const body = await readJson(req);
    const r = await loginUser(String(body.email ?? ""), String(body.password ?? ""));
    if (!r.ok) return privateJson({ ok: false, error: r.error }, { status: 401 });
    await setSession(r.user.id);
    return privateJson({ ok: true, user: toSafe(r.user) });
  } catch {
    return unavailableJson();
  }
}
