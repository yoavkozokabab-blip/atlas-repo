import { NextResponse } from "next/server";

export function privateJson(body: unknown, init: ResponseInit = {}) {
  const headers = new Headers(init.headers);
  headers.set("Cache-Control", "private, no-store, max-age=0");
  headers.set("Pragma", "no-cache");
  headers.set("Vary", "Cookie, Authorization");
  return NextResponse.json(body, { ...init, headers });
}

export function unavailableJson() {
  return privateJson(
    { ok: false, error: "account_service_unavailable" },
    { status: 503, headers: { "Retry-After": "60" } }
  );
}
