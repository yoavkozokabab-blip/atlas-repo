import { clearSession } from "@/app/_lib/auth";
import { privateJson } from "@/app/_lib/http";
import { csrfRejected, isTrustedBrowserWrite } from "@/app/_lib/request-security";

export const runtime = "nodejs";

export async function POST(req: Request) {
  if (!isTrustedBrowserWrite(req)) return csrfRejected();
  await clearSession();
  return privateJson({ ok: true });
}
