import { requireAdmin } from "@/app/_lib/auth";
import { store, toSafe } from "@/app/_lib/store";
import { privateJson, unavailableJson } from "@/app/_lib/http";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  try {
    const admin = await requireAdmin();
    if (!admin) return privateJson({ ok: false, error: "forbidden" }, { status: 403 });

  const url = new URL(req.url);
  const q = (url.searchParams.get("q") || "").trim().toLowerCase();
  let users = (await store.list()).map(toSafe);
  if (q) users = users.filter((u) => u.email.includes(q) || (u.name || "").toLowerCase().includes(q));

  return privateJson({
    ok: true,
    users, // SafeUser[] — never includes passwordHash
    audit: await store.auditList(100),
  });
  } catch {
    return unavailableJson();
  }
}
