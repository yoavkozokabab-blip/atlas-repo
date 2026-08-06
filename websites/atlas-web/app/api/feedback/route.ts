import { analyticsEnvironment } from "@/app/_lib/analytics-contract";
import { redactFeedbackText } from "@/app/_lib/feedback-redaction";
import { privateJson } from "@/app/_lib/http";
import { clientIp, rateLimit } from "@/app/_lib/ratelimit";
import { analyticsStoreErrorInfo, store, type BetaFeedback } from "@/app/_lib/store";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** Hard cap on the whole request. Prose feedback needs far less than this. */
const MAX_BODY_BYTES = 16 * 1024;
const MAX_MESSAGE_CHARS = 4_000;
const MAX_EMAIL_CHARS = 200;
const MAX_DIAGNOSTIC_KEYS = 12;

const ALLOWED_KEYS = new Set([
  "feedback_id", "category", "message", "email", "page",
  "version", "build_commit", "installation_id", "diagnostics_summary", "timestamp", "product",
]);

const CATEGORIES = new Set(["general", "bug", "feature", "question", "performance", "accuracy"]);

function text(value: unknown, max: number): string {
  return typeof value === "string" ? redactFeedbackText(value.trim()).slice(0, max) : "";
}

function identifier(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return /^[A-Za-z0-9._:-]{4,80}$/.test(trimmed) ? trimmed : null;
}

/** Coarse counters only. Anything non-primitive or oversized is dropped. */
function diagnostics(value: unknown): Record<string, string | number | boolean> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  const out: Record<string, string | number | boolean> = {};
  for (const [key, raw] of Object.entries(value).slice(0, MAX_DIAGNOSTIC_KEYS)) {
    if (!/^[a-z][a-z0-9_]{0,40}$/i.test(key)) continue;
    if (typeof raw === "boolean") out[key] = raw;
    else if (typeof raw === "number" && Number.isFinite(raw)) out[key] = raw;
    else if (typeof raw === "string") {
      const cleaned = redactFeedbackText(raw.trim()).slice(0, 120);
      if (cleaned) out[key] = cleaned;
    }
  }
  return out;
}

export async function POST(req: Request) {
  try {
    // Rate limit before parsing, so a flood costs nothing to reject.
    if (!(await rateLimit(`feedback:${clientIp(req)}`, 10, 3_600_000))) {
      return privateJson(
        { ok: false, error: "rate_limited", message: "Too many reports from this network. Try again later." },
        { status: 429, headers: { "Retry-After": "600" } },
      );
    }

    const raw = await req.text();
    if (!raw || Buffer.byteLength(raw, "utf8") > MAX_BODY_BYTES) {
      return privateJson({ ok: false, error: "payload_too_large" }, { status: 413 });
    }

    let body: Record<string, unknown>;
    try {
      const parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("shape");
      body = parsed as Record<string, unknown>;
    } catch {
      return privateJson({ ok: false, error: "invalid_json" }, { status: 400 });
    }

    // Unknown top-level fields are rejected outright rather than ignored, so
    // a future client cannot quietly start sending something new.
    if (Object.keys(body).some((key) => !ALLOWED_KEYS.has(key))) {
      return privateJson({ ok: false, error: "invalid_field" }, { status: 400 });
    }

    const message = text(body.message, MAX_MESSAGE_CHARS);
    if (!message) {
      return privateJson({ ok: false, error: "empty_message" }, { status: 400 });
    }

    const feedbackId = identifier(body.feedback_id);
    if (!feedbackId) {
      return privateJson({ ok: false, error: "invalid_feedback_id" }, { status: 400 });
    }

    const category = typeof body.category === "string" && CATEGORIES.has(body.category)
      ? body.category
      : "general";

    const replyEmailRaw = text(body.email, MAX_EMAIL_CHARS);
    const replyEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(replyEmailRaw) ? replyEmailRaw : null;

    const record: BetaFeedback = {
      feedbackId,
      category,
      message,
      replyEmail,
      page: text(body.page, 120) || null,
      appVersion: identifier(body.version),
      buildCommit: identifier(body.build_commit)?.slice(0, 40) ?? null,
      installationId: identifier(body.installation_id),
      environment: analyticsEnvironment(),
      diagnostics: diagnostics(body.diagnostics_summary),
    };

    const result = await store.addFeedback(record);
    return privateJson(
      { ok: true, received: true, duplicate: result.duplicate },
      { status: result.duplicate ? 200 : 201 },
    );
  } catch (error) {
    // Never echo the request, the store error body, or a stack trace. A 503
    // tells the desktop the report was NOT delivered, so it keeps the local
    // copy and says so rather than claiming success.
    const detail = analyticsStoreErrorInfo(error);
    console.error("[atlas] feedback_delivery_failed", { status: detail.status, code: detail.code });
    return privateJson({ ok: false, error: "feedback_temporarily_unavailable" }, { status: 503 });
  }
}
