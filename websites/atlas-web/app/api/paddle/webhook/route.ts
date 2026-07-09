import { NextResponse } from "next/server";
import { handlePaddleEvent, verifyPaddleSignature } from "@/app/_lib/billing";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const rawBody = await req.text();
  if (!verifyPaddleSignature(rawBody, req.headers.get("paddle-signature"))) {
    return NextResponse.json({ ok: false, error: "invalid_signature" }, { status: 401 });
  }

  const event = JSON.parse(rawBody);
  const result = await handlePaddleEvent(event);
  return NextResponse.json(result);
}
