import { NextResponse } from "next/server";
import { requireAdmin } from "@/app/_lib/auth";
import { store, toSafe } from "@/app/_lib/store";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const admin = await requireAdmin();
  if (!admin) return NextResponse.json({ ok: false, error: "forbidden" }, { status: 403 });

  const url = new URL(req.url);
  const q = (url.searchParams.get("q") || "").trim().toLowerCase();
  let users = (await store.list()).map(toSafe);
  if (q) users = users.filter((u) => u.email.includes(q) || (u.name || "").toLowerCase().includes(q));

  return NextResponse.json({
    ok: true,
    users, // SafeUser[] — never includes passwordHash
    audit: await store.auditList(100),
  });
}
