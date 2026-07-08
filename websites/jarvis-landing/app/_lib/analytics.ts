import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { ENV } from "./config";
import { newId } from "./store";
import { updateIdentityFromEvent } from "./analytics-identity";

export type AnalyticsInput = {
  event_name: string;
  source: string;
  user_id?: string | null;
  anonymous_id?: string | null;
  app_version?: string | null;
  platform?: string | null;
  metadata?: Record<string, unknown> | null;
};

const ALLOWED_EVENTS = new Set([
  "site_visit",
  "download_clicked",
  "github_clicked",
  "waitlist_joined",
  "signup_started",
  "signup_success",
  "signup_failed",
  "api_desktop_login_started",
  "api_desktop_login_success",
  "api_desktop_login_failed",
  "api_me_success",
  "api_me_failed",
  "desktop_opened",
  "desktop_login_started",
  "desktop_login_success",
  "desktop_login_failed",
  "desktop_me_success",
  "desktop_me_failed",
  "repo_connected",
  "first_context_generated",
  "agent_context_injected",
  "desktop_installed",
  "cursor_connected",
  "claude_connected",
  "codex_connected",
  "cursor_used",
  "claude_used",
  "codex_used",
  "atlas_session_started",
  "atlas_first_tool_call",
  "atlas_tool_call",
  "atlas_context_served",
  "atlas_context_used",
  "atlas_session_finished",
]);

const ALLOWED_METADATA_KEYS = new Set([
  "reason",
  "error_code",
  "page",
  "path",
  "target",
  "agent",
  "duplicate",
  "mode",
  "ok",
  "first",
  "http_status",
  "packet",
  "platform_hint",
  "signed_in",
  "installation_id",
  "tool",
  "session_sec",
  "source_kind",
]);

const BLOCKED_METADATA_KEYS = /password|token|prompt|secret|hash|api[_-]?key|authorization|repo_path|source_code|email/i;
const MAX_METADATA_BYTES = 2048;

function restBase(): string {
  const raw = (process.env.SUPABASE_URL || "").trim().replace(/\/+$/, "");
  const origin = raw.replace(/\/rest\/v1$/i, "");
  return `${origin}/rest/v1`;
}

async function sbInsert(row: Record<string, unknown>): Promise<void> {
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY!;
  const res = await fetch(`${restBase()}/analytics_events`, {
    method: "POST",
    headers: {
      apikey: key,
      Authorization: `Bearer ${key}`,
      "Content-Type": "application/json",
      Prefer: "return=minimal",
    },
    body: JSON.stringify(row),
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`analytics insert failed: ${res.status} ${body.slice(0, 200)}`);
  }
}

function analyticsFilePath(): string {
  return path.join(process.cwd(), ENV.dataDir, "analytics_events.jsonl");
}

function appendFile(row: Record<string, unknown>): void {
  const file = analyticsFilePath();
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.appendFileSync(file, `${JSON.stringify(row)}\n`, "utf8");
}

function scrubMetadata(raw: Record<string, unknown> | null | undefined): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(raw || {})) {
    if (!ALLOWED_METADATA_KEYS.has(key) || BLOCKED_METADATA_KEYS.test(key)) continue;
    if (value === null || value === undefined) continue;
    if (typeof value === "boolean" || typeof value === "number") {
      out[key] = value;
      continue;
    }
    const text = String(value).slice(0, 120);
    if (BLOCKED_METADATA_KEYS.test(text) || text.includes("```")) continue;
    out[key] = text;
  }
  if (JSON.stringify(out).length > MAX_METADATA_BYTES) {
    return { truncated: true };
  }
  return out;
}

export function normalizeEventName(name: string): string {
  return String(name || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, "_")
    .slice(0, 64);
}

/** Persist one analytics row. Never throws — failures are logged and swallowed. */
export async function trackEvent(input: AnalyticsInput): Promise<{ ok: boolean; skipped?: boolean; error?: string }> {
  const event_name = normalizeEventName(input.event_name);
  if (!event_name || !ALLOWED_EVENTS.has(event_name)) {
    return { ok: false, skipped: true, error: "event_not_allowed" };
  }
  const source = String(input.source || "unknown").slice(0, 64);
  const row = {
    id: newId(),
    created_at: new Date().toISOString(),
    user_id: input.user_id || null,
    anonymous_id: input.anonymous_id ? String(input.anonymous_id).slice(0, 64) : null,
    event_name,
    source,
    app_version: input.app_version ? String(input.app_version).slice(0, 32) : ENV.appVersion,
    platform: input.platform ? String(input.platform).slice(0, 32) : null,
    metadata: scrubMetadata(input.metadata),
  };
  try {
    if (ENV.hasSupabase) {
      await sbInsert(row);
    } else {
      appendFile(row);
    }
    await updateIdentityFromEvent({ ...input, event_name });
    return { ok: true };
  } catch (err) {
    console.error("[atlas] trackEvent failed:", event_name, err);
    return { ok: false, error: "persist_failed" };
  }
}

export function analyticsBackend(): "supabase" | "file" | "none" {
  if (ENV.hasSupabase) return "supabase";
  return "file";
}

export function hashAnonymousSeed(seed: string): string {
  return crypto.createHash("sha256").update(seed).digest("hex").slice(0, 24);
}
