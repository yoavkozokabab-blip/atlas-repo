import { NextResponse } from "next/server";

export const runtime = "nodejs";

// Desktop logout (Phase 186A). The token is a stateless signed token, so the
// client discards it. TRUE server-side revocation requires the `sessions` table
// in identity_architecture.md §6 (deferred). Best-effort 204 for now.
export async function POST() {
  return new NextResponse(null, {
    status: 204,
    headers: {
      "Cache-Control": "private, no-store, max-age=0",
      Pragma: "no-cache",
      Vary: "Authorization",
    },
  });
}
