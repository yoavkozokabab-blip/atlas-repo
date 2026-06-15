import { NextResponse } from "next/server";
import crypto from "node:crypto";
import { store } from "@/app/_lib/store";
import { validEmail } from "@/app/_lib/auth";
import { rateLimit, clientIp, readJson } from "@/app/_lib/ratelimit";

export const runtime = "nodejs";

export async function POST(req: Request) {
  if (!rateLimit(`forgot:${clientIp(req)}`, 5, 900_000)) {
    return NextResponse.json({ ok: true }); // generic: never reveal rate state per-email
  }
  const body = await readJson(req);
  const email = String(body.email ?? "").trim().toLowerCase();

  // Always return the same generic response — never reveal whether the email exists.
  if (validEmail(email) && (await store.getByEmail(email))) {
    const token = crypto.randomBytes(24).toString("base64url");
    await store.addResetToken({ token, email, exp: Date.now() + 30 * 60_000 });
    // Stub mode: no email provider configured. Log the reset link for local testing.
    // Live: send via the configured transactional email provider instead.
    console.warn(`[atlas] password reset link (stub): /login?reset=${token}`);
  }
  return NextResponse.json({
    ok: true,
    message: "If an account exists for that email, a reset link has been sent.",
  });
}
