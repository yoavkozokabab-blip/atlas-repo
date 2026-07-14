import { clearSession } from "@/app/_lib/auth";
import { privateJson } from "@/app/_lib/http";

export const runtime = "nodejs";

export async function POST() {
  await clearSession();
  return privateJson({ ok: true });
}
