import { NextResponse } from "next/server";
import { currentSafeUser } from "@/app/_lib/auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const user = await currentSafeUser();
  return NextResponse.json({ ok: true, user });
}
