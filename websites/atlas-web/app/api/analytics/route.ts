import { NextResponse } from "next/server";
import { store } from "@/app/_lib/store";
import { clientIp, rateLimit, readJson } from "@/app/_lib/ratelimit";

export const runtime = "nodejs";

const ALLOWED_EVENTS = new Set([
  "page_view",
  "hn_page_view",
  "pricing_view",
  "download_click",
  "pro_cta_click",
  "docs_click",
]);

function safePath(value: unknown): string {
  const path = String(value || "").slice(0, 160);
  return /^\/[A-Za-z0-9_/-]*$/.test(path) ? path : "/";
}

export async function POST(request: Request) {
  if (!(await rateLimit(`analytics:${clientIp(request)}`, 180, 60_000))) {
    return new NextResponse(null, { status: 429 });
  }
  const body = await readJson(request);
  const event = String(body.event || "");
  if (!ALLOWED_EVENTS.has(event)) {
    return NextResponse.json({ ok: false, error: "invalid_event" }, { status: 400 });
  }
  try {
    await store.recordAnalytics({ event, path: safePath(body.path) });
    return new NextResponse(null, { status: 202 });
  } catch (err) {
    console.error("[atlas] analytics persist failed:", err);
    return new NextResponse(null, { status: 503 });
  }
}
