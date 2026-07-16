import { NextResponse } from "next/server";
import { bearerToken, verifySessionToken } from "@/app/_lib/auth";
import { store } from "@/app/_lib/store";

export const runtime = "nodejs";

// Desktop logout revokes the opaque server session, so a copied Bearer token
// cannot be reused after the client signs out.
export async function POST(req: Request) {
  const token = bearerToken(req);
  const claims = token ? verifySessionToken(token) : null;
  if (claims) await store.revokeSession(claims.sid);
  return new NextResponse(null, {
    status: 204,
    headers: {
      "Cache-Control": "private, no-store, max-age=0",
      Pragma: "no-cache",
      Vary: "Authorization",
    },
  });
}
