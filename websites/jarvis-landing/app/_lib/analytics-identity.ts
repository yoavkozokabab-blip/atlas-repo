import fs from "node:fs";
import path from "node:path";
import { ENV } from "./config";
import { computeTtfvSeconds } from "./analytics-ttfv";
import type { AnalyticsInput } from "./analytics";

type IdentityRow = Record<string, unknown>;

const MILESTONE_BY_EVENT: Record<string, keyof IdentityRow> = {
  download_clicked: "installed_at",
  desktop_installed: "installed_at",
  desktop_opened: "opened_at",
  desktop_login_success: "login_success_at",
  api_desktop_login_success: "login_success_at",
  signup_success: "login_success_at",
  repo_connected: "repo_connected_at",
  first_context_generated: "first_context_at",
  cursor_connected: "cursor_connected_at",
  claude_connected: "claude_connected_at",
  codex_connected: "codex_connected_at",
};

const AGENT_CONNECT_BY_LEGACY: Record<string, keyof IdentityRow> = {
  cursor: "cursor_connected_at",
  claude: "claude_connected_at",
  codex: "codex_connected_at",
};

function restBase(): string {
  const raw = (process.env.SUPABASE_URL || "").trim().replace(/\/+$/, "");
  const origin = raw.replace(/\/rest\/v1$/i, "");
  return `${origin}/rest/v1`;
}

async function sb(pathAndQuery: string, init: RequestInit = {}): Promise<Response> {
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY!;
  return fetch(`${restBase()}/${pathAndQuery}`, {
    ...init,
    cache: "no-store",
    headers: {
      apikey: key,
      Authorization: `Bearer ${key}`,
      "Content-Type": "application/json",
      ...(init.headers || {}),
    },
  });
}

function identitiesFilePath(): string {
  return path.join(process.cwd(), ENV.dataDir, "analytics_identities.json");
}

function loadFileIdentities(): IdentityRow[] {
  try {
    return JSON.parse(fs.readFileSync(identitiesFilePath(), "utf8"));
  } catch {
    return [];
  }
}

function saveFileIdentities(rows: IdentityRow[]): void {
  fs.mkdirSync(path.dirname(identitiesFilePath()), { recursive: true });
  fs.writeFileSync(identitiesFilePath(), JSON.stringify(rows, null, 2), "utf8");
}

export function buildIdentityKey(input: AnalyticsInput): string {
  const meta = input.metadata || {};
  const installationId = meta.installation_id ? String(meta.installation_id) : "";
  if (input.user_id) return `user:${input.user_id}`;
  if (installationId) return `install:${installationId}`;
  if (input.anonymous_id) return `anon:${input.anonymous_id}`;
  return `ephemeral:${Date.now()}`;
}

function dayKey(iso: string): string {
  return iso.slice(0, 10);
}

function mergeEarliest(existing: unknown, incoming: string): string {
  const cur = existing ? String(existing) : "";
  if (!cur) return incoming;
  return new Date(incoming) < new Date(cur) ? incoming : cur;
}

function applyTtfv(row: IdentityRow): void {
  const ttfv = computeTtfvSeconds({
    installed_at: row.installed_at as string,
    opened_at: row.opened_at as string,
    login_success_at: row.login_success_at as string,
    repo_connected_at: row.repo_connected_at as string,
    first_context_at: row.first_context_at as string,
  });
  Object.assign(row, ttfv);
  if (ttfv.total_ttfv_sec != null) {
    row.ttfv_computed_at = new Date().toISOString();
  }
}

function bumpCounter(row: IdentityRow, key: string, delta = 1): void {
  row[key] = Number(row[key] || 0) + delta;
}

function applyEventToIdentity(row: IdentityRow, input: AnalyticsInput, now: string): void {
  const event = input.event_name;
  const meta = input.metadata || {};

  if (event === "desktop_opened") {
    bumpCounter(row, "sessions_count");
  }
  if (event === "atlas_tool_call") bumpCounter(row, "tool_calls_count");
  if (event === "agent_context_injected" || event.endsWith("_connected")) {
    bumpCounter(row, "context_injections_count");
  }
  if (event === "repo_connected" && meta.first === true) {
    bumpCounter(row, "repositories_count");
  }
  if (event === "cursor_used") bumpCounter(row, "cursor_used_count");
  if (event === "claude_used") bumpCounter(row, "claude_used_count");
  if (event === "codex_used") bumpCounter(row, "codex_used_count");

  const milestone = MILESTONE_BY_EVENT[event];
  if (milestone) {
    row[milestone] = mergeEarliest(row[milestone], now);
  }

  if (event === "agent_context_injected") {
    const agent = String(meta.agent || "").toLowerCase();
    const legacy = AGENT_CONNECT_BY_LEGACY[agent];
    if (legacy) row[legacy] = mergeEarliest(row[legacy], now);
  }

  applyTtfv(row);
  row.updated_at = now;
}

function newIdentityRow(input: AnalyticsInput, identityKey: string, now: string): IdentityRow {
  const meta = input.metadata || {};
  return {
    identity_key: identityKey,
    user_id: input.user_id || null,
    anonymous_id: input.anonymous_id || null,
    installation_id: meta.installation_id ? String(meta.installation_id) : null,
    first_seen: now,
    last_seen: now,
    days_active: 1,
    sessions_count: 0,
    cursor_used_count: 0,
    claude_used_count: 0,
    codex_used_count: 0,
    tool_calls_count: 0,
    context_injections_count: 0,
    repositories_count: 0,
  };
}

async function upsertSupabase(row: IdentityRow): Promise<void> {
  const key = encodeURIComponent(String(row.identity_key));
  const existingRes = await sb(`analytics_identities?identity_key=eq.${key}&limit=1`);
  const existing = existingRes.ok ? ((await existingRes.json()) as IdentityRow[]) : [];
  if (existing[0]) {
    const merged = { ...existing[0], ...row, identity_key: row.identity_key };
    await sb(`analytics_identities?identity_key=eq.${key}`, {
      method: "PATCH",
      headers: { Prefer: "return=minimal" },
      body: JSON.stringify(merged),
    });
    return;
  }
  await sb("analytics_identities", {
    method: "POST",
    headers: { Prefer: "return=minimal" },
    body: JSON.stringify(row),
  });
}

function upsertFile(row: IdentityRow): void {
  const rows = loadFileIdentities();
  const idx = rows.findIndex((r) => r.identity_key === row.identity_key);
  if (idx >= 0) rows[idx] = { ...rows[idx], ...row };
  else rows.push(row);
  saveFileIdentities(rows);
}

/** Update identity rollups + TTFV after an event is accepted. Never throws. */
export async function updateIdentityFromEvent(input: AnalyticsInput): Promise<void> {
  try {
    const now = new Date().toISOString();
    const identityKey = buildIdentityKey(input);
    let row: IdentityRow;

    if (ENV.hasSupabase) {
      const key = encodeURIComponent(identityKey);
      const res = await sb(`analytics_identities?identity_key=eq.${key}&limit=1`);
      const existing = res.ok ? ((await res.json()) as IdentityRow[]) : [];
      row = existing[0] ? { ...existing[0] } : newIdentityRow(input, identityKey, now);
    } else {
      const existing = loadFileIdentities().find((r) => r.identity_key === identityKey);
      row = existing ? { ...existing } : newIdentityRow(input, identityKey, now);
    }

    const prevDay = dayKey(String(row.last_seen || row.first_seen || now));
    row.last_seen = now;
    if (dayKey(now) !== prevDay) {
      row.days_active = Number(row.days_active || 1) + 1;
    }
    if (input.user_id && !row.user_id) row.user_id = input.user_id;

    applyEventToIdentity(row, input, now);

    if (ENV.hasSupabase) await upsertSupabase(row);
    else upsertFile(row);
  } catch (err) {
    console.error("[atlas] updateIdentityFromEvent failed:", err);
  }
}

export async function loadAllIdentities(limit = 5000): Promise<{ data: IdentityRow[]; error?: string }> {
  if (ENV.hasSupabase) {
    const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
    if (!key) {
      return { data: [], error: "Analytics backend is not configured." };
    }
    const res = await sb(
      `analytics_identities?order=last_seen.desc&limit=${Math.min(limit, 10000)}`
    );
    if (!res.ok) {
      const body = await res.text().catch(() => "");
      const hint = res.status === 404 || body.includes("analytics_identities")
        ? " Run Supabase migrations 0003–0005 on the production project."
        : "";
      return {
        data: [],
        error: `Analytics backend error: analytics_identities query failed (${res.status}).${hint}`,
      };
    }
    return { data: (await res.json()) as IdentityRow[] };
  }
  return { data: loadFileIdentities().slice(0, limit) };
}

export function retentionRates(identities: IdentityRow[]): { d1: number; d7: number; d30: number } {
  const cohorts = identities.filter((r) => r.first_seen);
  if (!cohorts.length) return { d1: 0, d7: 0, d30: 0 };

  function rate(days: number): number {
    let eligible = 0;
    let retained = 0;
    const now = Date.now();
    for (const row of cohorts) {
      const first = new Date(String(row.first_seen)).getTime();
      const ageDays = (now - first) / 86400000;
      if (ageDays < days) continue;
      eligible += 1;
      const last = new Date(String(row.last_seen)).getTime();
      if ((last - first) / 86400000 >= days) retained += 1;
    }
    return eligible ? Math.round((retained / eligible) * 1000) / 10 : 0;
  }

  return { d1: rate(1), d7: rate(7), d30: rate(30) };
}
