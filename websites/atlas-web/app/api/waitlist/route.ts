import { store } from "@/app/_lib/store";
import { rateLimit, clientIp } from "@/app/_lib/ratelimit";
import { privateJson, unavailableJson } from "@/app/_lib/http";
import { csrfRejected, isTrustedBrowserWrite } from "@/app/_lib/request-security";
import { MAX_WAITLIST_BODY_BYTES, parseWaitlistForm } from "@/app/_lib/waitlist-form";

export const runtime = "nodejs";

/**
 * Email update signup. Persists through the shared Store:
 *   - production (SUPABASE_* set): Supabase storage survives redeploys.
 *   - dev/test: local JSON file (ephemeral; never use on serverless).
 * Duplicate emails are idempotent (no error, no double row).
 */
export async function POST(request: Request) {
  if (!isTrustedBrowserWrite(request)) return csrfRejected();
  const contentLength = Number(request.headers.get("content-length") || 0);
  if (!Number.isFinite(contentLength) || contentLength < 0 || contentLength > MAX_WAITLIST_BODY_BYTES) {
    return privateJson({ ok: false, message: "Request is too large." }, { status: 413 });
  }
  if (!(await rateLimit(`updates:${clientIp(request)}`, 12, 3_600_000))) {
    return privateJson(
      { ok: false, message: "Too many attempts. Please try again later." },
      { status: 429 }
    );
  }

  const form = await request.formData();
  const parsed = parseWaitlistForm(form);
  if (!parsed) {
    return privateJson(
      { ok: false, message: "Enter a valid email address." },
      { status: 400 }
    );
  }

  try {
    const { duplicate } = await store.addWaitlist({ ...parsed, source: "atlas-web" });
    return privateJson({
      ok: true,
      duplicate,
      message: duplicate
        ? "That email is already subscribed. We'll be in touch."
        : "Thanks. We'll be in touch.",
    });
  } catch {
    return unavailableJson();
  }
}
