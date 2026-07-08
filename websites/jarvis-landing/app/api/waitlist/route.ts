import { NextResponse } from "next/server";
import { store } from "@/app/_lib/store";
import { trackEvent } from "@/app/_lib/analytics";
import { rateLimit, clientIp } from "@/app/_lib/ratelimit";

export const runtime = "nodejs";

/**
 * Email update signup. Persists through the shared Store:
 *   - production (SUPABASE_* set): Supabase storage survives redeploys.
 *   - dev/test: local JSON file (ephemeral; never use on serverless).
 * Duplicate emails are idempotent (no error, no double row).
 */
export async function POST(request: Request) {
  if (!rateLimit(`updates:${clientIp(request)}`, 12, 3_600_000)) {
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
    await trackEvent({
      event_name: "waitlist_joined",
      source: "website",
      metadata: { duplicate: !!duplicate },
    });
    return NextResponse.json({
      ok: true,
      duplicate,
      message: duplicate
        ? "That email is already subscribed. We'll be in touch."
        : "Thanks. We'll be in touch.",
    });
  } catch (err) {
    console.error("[atlas] update signup persist failed:", err);
    return NextResponse.json(
      { ok: false, message: "Signup temporarily unavailable. Please try again." },
      { status: 503 }
    );
  }
}
