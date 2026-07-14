import { currentSafeUser } from "@/app/_lib/auth";
import { privateJson, unavailableJson } from "@/app/_lib/http";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const user = await currentSafeUser();
    return privateJson({ ok: true, user });
  } catch {
    return unavailableJson();
  }
}
