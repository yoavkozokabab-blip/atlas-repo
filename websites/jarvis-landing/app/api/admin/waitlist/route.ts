import { NextResponse } from "next/server";
import { requireAdmin } from "@/app/_lib/auth";
import { store } from "@/app/_lib/store";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * Admin: export the beta waitlist.
 *   GET /api/admin/waitlist            -> JSON
 *   GET /api/admin/waitlist?format=csv -> CSV download (for beta invites)
 */
export async function GET(req: Request) {
  const admin = await requireAdmin();
  if (!admin) return NextResponse.json({ ok: false, error: "forbidden" }, { status: 403 });

  const entries = await store.listWaitlist(5000);
  const format = new URL(req.url).searchParams.get("format");

  if (format === "csv") {
    const esc = (v: string) => `"${String(v).replace(/"/g, '""')}"`;
    const header = "email,role,source,createdAt";
    const rows = entries.map((e) =>
      [e.email, e.role || "", e.source || "", e.createdAt].map(esc).join(",")
    );
    const csv = [header, ...rows].join("\n");
    return new NextResponse(csv, {
      headers: {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": 'attachment; filename="atlas-waitlist.csv"',
        "Cache-Control": "no-store",
      },
    });
  }

  return NextResponse.json({ ok: true, count: entries.length, backend: store.backend(), entries });
}
