import { NextResponse } from "next/server";
import { store } from "@/app/_lib/store";
import { rateLimit, clientIp } from "@/app/_lib/ratelimit";

export const runtime = "nodejs";

/**
 * Waitlist signup. Persists through the shared Store:
 *   - production (SUPABASE_* set): Supabase `waitlist` table — survives redeploys.
 *   - dev/test: local JSON file (ephemeral; never use on serverless).
 * Duplicate emails are idempotent (no error, no double row).
 */
export async function POST(request: Request) {
  if (!rateLimit(`waitlist:${clientIp(request)}`, 12, 3_600_000)) {
    return NextResponse.json(
      { ok: false, message: "Too many attempts. Please try again later." },
      { status: 429 }
    );
  }

  const form = await request.formData();
  const email = String(form.get("email") || "").trim().toLowerCase();
  const role = String(form.get("role") || "").trim().slice(0, 80);

  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return NextResponse.json(
      { ok: false, message: "Enter a valid email address." },
      { status: 400 }
    );
  }

  try {
    const { duplicate } = await store.addWaitlist({ email, role, source: "jarvis-landing" });
    return NextResponse.json({
      ok: true,
      duplicate,
      message: duplicate
        ? "You're already on the list — we'll be in touch."
        : "You're on the list. We'll email your beta invite soon.",
    });
  } catch (err) {
    console.error("[atlas] waitlist persist failed:", err);
    return NextResponse.json(
      { ok: false, message: "Waitlist temporarily unavailable. Please try again." },
      { status: 503 }
    );
  }
}
