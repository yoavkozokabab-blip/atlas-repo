import { NextResponse } from "next/server";
import { isAdmin, userFromBearer } from "@/app/_lib/auth";
import { buildAnalyticsDashboardPayload } from "@/app/_lib/analytics-dashboard-api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** Desktop Admin Workspace — bearer auth (same admin gate as website dashboard). */
export async function GET(req: Request) {
  const user = await userFromBearer(req);
  if (!user || !isAdmin(user)) {
    return NextResponse.json({ ok: false, error: "forbidden" }, { status: 403 });
  }
  return NextResponse.json(await buildAnalyticsDashboardPayload());
}
