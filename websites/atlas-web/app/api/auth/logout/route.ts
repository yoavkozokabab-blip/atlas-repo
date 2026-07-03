import { NextResponse } from "next/server";
import { clearSession } from "@/app/_lib/auth";

export const runtime = "nodejs";

export async function POST() {
  await clearSession();
  return NextResponse.json({ ok: true });
}
