import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { ENV } from "./config";
import type { AnalyticsRow } from "./analytics-server";

// ---------------------------------------------------------------------------
// Data model + pluggable async store.
//
// Two backends implement the same async `Store` interface:
//   * fileStore     — JSON file on local disk. Dev/test only; EPHEMERAL on
//                     serverless (Vercel) — do not use in production.
//   * supabaseStore — Supabase Postgres via PostgREST (fetch, no extra deps).
//                     Survives redeploys, restarts, and serverless cold starts.
//
// getStore() picks supabaseStore when SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY
// are set (ENV.hasSupabase), else falls back to fileStore. All call sites depend
// only on the async interface, so going live is a config change, not a code change.
// ---------------------------------------------------------------------------

export type Plan = "free" | "pro" | "team";
export type PlanStatus = "none" | "trialing" | "active" | "past_due" | "canceled" | "expired";
export type AccountStatus = "active" | "suspended";
export type Role = "user" | "admin";

export interface User {
  id: string;
  email: string;
  name?: string;
  passwordHash?: string; // legacy scrypt hash; null after Supabase Auth migration
  authUserId?: string | null;
  authMigratedAt?: string | null;
  legacyAuthDisabledAt?: string | null;
  updatedAt?: string | null;
  role: Role;
  status: AccountStatus;
  plan: Plan;
  planStatus: PlanStatus;
  trialEndsAt?: string | null;
  renewsAt?: string | null;
  paddleCustomerId?: string | null;
  paddleSubscriptionId?: string | null;
  createdAt: string;
  lastLoginAt?: string | null;
  downloads: number;
}

export type SafeUser = Omit<
  User,
  "passwordHash" | "authUserId" | "authMigratedAt" | "legacyAuthDisabledAt"
>;
export function toSafe(u: User): SafeUser {
  const rest: Partial<User> = { ...u };
  delete rest.passwordHash; // never expose the hash to the client
  delete rest.authUserId;
  delete rest.authMigratedAt;
  delete rest.legacyAuthDisabledAt;
  return rest as SafeUser;
}

export interface AuditEntry {
  id: string;
  at: string;
  actorId: string;
  actorEmail: string;
  action: string;
  targetId?: string;
  targetEmail?: string;
  meta?: Record<string, unknown>;
}

export interface WaitlistEntry {
  id: string;
  email: string;
  role?: string;
  source?: string;
  createdAt: string;
}

/** Server-authoritative authentication session. */
export interface Session {
  id: string;
  userId: string;
  createdAt: string;
  expiresAt: string;
  revokedAt?: string | null;
}

interface DBShape {
  users: User[];
  audit: AuditEntry[];
  resetTokens: { token: string; email: string; exp: number }[];
  waitlist: WaitlistEntry[];
  sessions: Session[];
}

export function newId(): string {
  return crypto.randomUUID();
}

export class DuplicateEmailError extends Error {
  constructor() {
    super("duplicate_email");
    this.name = "DuplicateEmailError";
  }
}

export function isDuplicateEmailError(error: unknown): boolean {
  return error instanceof DuplicateEmailError;
}

export interface Store {
  getByEmail(email: string): Promise<User | undefined>;
  getById(id: string): Promise<User | undefined>;
  create(u: User): Promise<User>;
  update(id: string, patch: Partial<User>): Promise<User | undefined>;
  remove(id: string): Promise<void>;
  deleteAccount(u: Pick<User, "id" | "email">): Promise<void>;
  list(): Promise<User[]>;
  audit(e: AuditEntry): Promise<void>;
  auditList(limit?: number): Promise<AuditEntry[]>;
  addResetToken(t: { token: string; email: string; exp: number }): Promise<void>;
  /** Returns duplicate:true if the email was already captured (idempotent). */
  addWaitlist(w: { email: string; role?: string; source?: string }): Promise<{ ok: boolean; duplicate: boolean }>;
  listWaitlist(limit?: number): Promise<WaitlistEntry[]>;
  createSession(session: Session): Promise<void>;
  getSession(id: string): Promise<Session | undefined>;
  revokeSession(id: string): Promise<void>;
  revokeSessionsForUser(userId: string): Promise<void>;
  linkAuthIdentity(userId: string, authUserId: string): Promise<boolean>;
  /** Identifies the active backend for health checks / diagnostics. */
  backend(): "supabase" | "file";
}

// ---------------------------------------------------------------------------
// File backend (dev/test only)
// ---------------------------------------------------------------------------

function dbPath(): string {
  return path.join(process.cwd(), ENV.dataDir, "atlas-web.json");
}
function load(): DBShape {
  try {
    const d = JSON.parse(fs.readFileSync(dbPath(), "utf8"));
    return {
      users: d.users || [],
      audit: d.audit || [],
      resetTokens: d.resetTokens || [],
      waitlist: d.waitlist || [],
      sessions: d.sessions || [],
    };
  } catch {
    return { users: [], audit: [], resetTokens: [], waitlist: [], sessions: [] };
  }
}
function persist(db: DBShape): void {
  // Safety: the file backend is ephemeral on serverless. Never let it silently
  // accept writes in production — that would lose data on the next redeploy.
  // Fail loudly so the bug is visible (and /api/health already reports not-ok).
  if (ENV.isProd && !ENV.hasSupabase) {
    throw new Error(
      "Refusing to persist to the local file store in production. Set SUPABASE_URL and " +
        "SUPABASE_SERVICE_ROLE_KEY (see docs/SUPABASE_SETUP.md)."
    );
  }
  const p = dbPath();
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, JSON.stringify(db, null, 2), "utf8");
}

const fileStore: Store = {
  backend: () => "file",
  getByEmail: async (email) => load().users.find((u) => u.email === email.toLowerCase()),
  getById: async (id) => load().users.find((u) => u.id === id),
  create: async (u) => {
    const db = load();
    if (db.users.some((existing) => existing.email.toLowerCase() === u.email.toLowerCase())) {
      throw new DuplicateEmailError();
    }
    db.users.push(u);
    persist(db);
    return u;
  },
  update: async (id, patch) => {
    const db = load();
    const i = db.users.findIndex((u) => u.id === id);
    if (i < 0) return undefined;
    db.users[i] = { ...db.users[i], ...patch };
    persist(db);
    return db.users[i];
  },
  remove: async (id) => {
    const db = load();
    db.users = db.users.filter((u) => u.id !== id);
    persist(db);
  },
  deleteAccount: async (u) => {
    const db = load();
    db.resetTokens = db.resetTokens.filter((t) => t.email.toLowerCase() !== u.email.toLowerCase());
    db.audit.push({
      id: newId(),
      at: new Date().toISOString(),
      actorId: u.id,
      actorEmail: u.email,
      action: "account_self_delete",
      targetId: u.id,
      targetEmail: u.email,
    });
    db.users = db.users.filter((existing) => existing.id !== u.id);
    persist(db);
  },
  list: async () => load().users,
  audit: async (e) => {
    const db = load();
    db.audit.push(e);
    persist(db);
  },
  auditList: async (limit = 200) => load().audit.slice(-limit).reverse(),
  addResetToken: async (t) => {
    const db = load();
    db.resetTokens.push(t);
    persist(db);
  },
  addWaitlist: async (w) => {
    const db = load();
    const email = w.email.toLowerCase();
    if (db.waitlist.some((e) => e.email === email)) return { ok: true, duplicate: true };
    db.waitlist.push({
      id: newId(),
      email,
      role: w.role,
      source: w.source,
      createdAt: new Date().toISOString(),
    });
    persist(db);
    return { ok: true, duplicate: false };
  },
  listWaitlist: async (limit = 1000) => load().waitlist.slice(-limit).reverse(),
  createSession: async (session) => {
    const db = load();
    db.sessions.push(session);
    persist(db);
  },
  getSession: async (id) => load().sessions.find((session) => session.id === id),
  revokeSession: async (id) => {
    const db = load();
    const session = db.sessions.find((entry) => entry.id === id);
    if (session && !session.revokedAt) session.revokedAt = new Date().toISOString();
    persist(db);
  },
  revokeSessionsForUser: async (userId) => {
    const db = load();
    const now = new Date().toISOString();
    for (const session of db.sessions) {
      if (session.userId === userId && !session.revokedAt) session.revokedAt = now;
    }
    persist(db);
  },
  linkAuthIdentity: async (userId, authUserId) => {
    const db = load();
    const user = db.users.find((entry) => entry.id === userId);
    if (!user || (user.authUserId && user.authUserId !== authUserId)) return false;
    const now = new Date().toISOString();
    user.authUserId = authUserId;
    user.authMigratedAt = user.authMigratedAt || now;
    user.legacyAuthDisabledAt = user.legacyAuthDisabledAt || now;
    user.updatedAt = now;
    delete user.passwordHash;
    db.audit.push({
      id: newId(),
      at: now,
      actorId: user.id,
      actorEmail: user.email,
      action: "legacy_auth_migrated",
      targetId: user.id,
      targetEmail: user.email,
      meta: { authority: "supabase_auth" },
    });
    persist(db);
    return true;
  },
};

// ---------------------------------------------------------------------------
// Supabase backend (production) — PostgREST over fetch, service-role key.
// ---------------------------------------------------------------------------

type Row = Record<string, unknown>;

class SupabaseStoreError extends Error {
  status: number;
  body: string;
  code?: string;

  constructor(ctx: string, status: number, body: string) {
    super(`supabase ${ctx} failed: ${status} ${body.slice(0, 300)}`);
    this.name = "SupabaseStoreError";
    this.status = status;
    this.body = body;
    try {
      const parsed = JSON.parse(body) as { code?: unknown };
      if (typeof parsed.code === "string") this.code = parsed.code;
    } catch {
      // Preserve the raw body for server logs; callers should use typed guards.
    }
  }
}

/**
 * Safe diagnostics for server-side delivery logs.  Never return the Supabase
 * body to native clients: it can include schema details that are not useful to
 * a user and must not become UI copy.
 */
export function analyticsStoreErrorInfo(error: unknown): { status: number | null; code: string | null } {
  if (error instanceof SupabaseStoreError) {
    return { status: error.status, code: error.code || null };
  }
  return { status: null, code: null };
}

function isUniqueEmailViolation(error: unknown): boolean {
  if (!(error instanceof SupabaseStoreError)) return false;
  const body = error.body.toLowerCase();
  return (
    error.code === "23505" &&
    (body.includes("users_email_key") || body.includes("users_email_idx") || body.includes("email"))
  );
}

function userToRow(u: Partial<User>): Row {
  const r: Row = {};
  if (u.id !== undefined) r.id = u.id;
  if (u.email !== undefined) r.email = u.email.toLowerCase();
  if (u.name !== undefined) r.name = u.name ?? null;
  if (u.passwordHash !== undefined) r.password_hash = u.passwordHash;
  if (u.authUserId !== undefined) r.auth_user_id = u.authUserId ?? null;
  if (u.authMigratedAt !== undefined) r.auth_migrated_at = u.authMigratedAt ?? null;
  if (u.legacyAuthDisabledAt !== undefined) r.legacy_auth_disabled_at = u.legacyAuthDisabledAt ?? null;
  if (u.updatedAt !== undefined) r.updated_at = u.updatedAt ?? null;
  if (u.role !== undefined) r.role = u.role;
  if (u.status !== undefined) r.status = u.status;
  if (u.plan !== undefined) r.plan = u.plan;
  if (u.planStatus !== undefined) r.plan_status = u.planStatus;
  if (u.trialEndsAt !== undefined) r.trial_ends_at = u.trialEndsAt ?? null;
  if (u.renewsAt !== undefined) r.renews_at = u.renewsAt ?? null;
  if (u.paddleCustomerId !== undefined) r.paddle_customer_id = u.paddleCustomerId ?? null;
  if (u.paddleSubscriptionId !== undefined) r.paddle_subscription_id = u.paddleSubscriptionId ?? null;
  if (u.createdAt !== undefined) r.created_at = u.createdAt;
  if (u.lastLoginAt !== undefined) r.last_login_at = u.lastLoginAt ?? null;
  if (u.downloads !== undefined) r.downloads = u.downloads;
  return r;
}
function rowToUser(r: Row): User {
  return {
    id: String(r.id),
    email: String(r.email),
    name: (r.name as string) ?? undefined,
    passwordHash: r.password_hash == null ? undefined : String(r.password_hash),
    authUserId: (r.auth_user_id as string) ?? null,
    authMigratedAt: (r.auth_migrated_at as string) ?? null,
    legacyAuthDisabledAt: (r.legacy_auth_disabled_at as string) ?? null,
    updatedAt: (r.updated_at as string) ?? null,
    role: (r.role as Role) ?? "user",
    status: (r.status as AccountStatus) ?? "active",
    plan: (r.plan as Plan) ?? "free",
    planStatus: (r.plan_status as PlanStatus) ?? "none",
    trialEndsAt: (r.trial_ends_at as string) ?? null,
    renewsAt: (r.renews_at as string) ?? null,
    paddleCustomerId: (r.paddle_customer_id as string) ?? null,
    paddleSubscriptionId: (r.paddle_subscription_id as string) ?? null,
    createdAt: String(r.created_at ?? new Date().toISOString()),
    lastLoginAt: (r.last_login_at as string) ?? null,
    downloads: Number(r.downloads ?? 0),
  };
}

// Normalize SUPABASE_URL to the PostgREST base. Accepts either the bare project
// URL (https://x.supabase.co) or one that already includes the REST path
// (…/rest/v1[/]). Trailing slashes and a trailing /rest/v1 are stripped so we
// never produce a doubled "/rest/v1/rest/v1/<table>" (PGRST125 "Invalid path").
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
async function sbRows(res: Response, ctx: string): Promise<Row[]> {
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new SupabaseStoreError(ctx, res.status, body);
  }
  const text = await res.text();
  if (!text) return [];
  return JSON.parse(text) as Row[];
}
async function sbValue<T>(res: Response, ctx: string): Promise<T> {
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new SupabaseStoreError(ctx, res.status, body);
  }
  const text = await res.text();
  if (!text) throw new Error(`supabase ${ctx} returned an empty response`);
  return JSON.parse(text) as T;
}
async function sbOk(res: Response, ctx: string): Promise<void> {
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new SupabaseStoreError(ctx, res.status, body);
  }
}
const enc = encodeURIComponent;

function rowToSession(row: Row): Session {
  return {
    id: String(row.id),
    userId: String(row.user_id),
    createdAt: String(row.created_at),
    expiresAt: String(row.expires_at),
    revokedAt: (row.revoked_at as string) ?? null,
  };
}

const supabaseStore: Store = {
  backend: () => "supabase",
  getByEmail: async (email) => {
    const rows = await sbRows(
      await sb(`users?email=eq.${enc(email.toLowerCase())}&limit=1`),
      "getByEmail"
    );
    return rows[0] ? rowToUser(rows[0]) : undefined;
  },
  getById: async (id) => {
    const rows = await sbRows(await sb(`users?id=eq.${enc(id)}&limit=1`), "getById");
    return rows[0] ? rowToUser(rows[0]) : undefined;
  },
  create: async (u) => {
    try {
      const rows = await sbRows(
        await sb("users", {
          method: "POST",
          headers: { Prefer: "return=representation" },
          body: JSON.stringify(userToRow(u)),
        }),
        "create"
      );
      return rows[0] ? rowToUser(rows[0]) : u;
    } catch (error) {
      if (isUniqueEmailViolation(error)) throw new DuplicateEmailError();
      throw error;
    }
  },
  update: async (id, patch) => {
    const rows = await sbRows(
      await sb(`users?id=eq.${enc(id)}`, {
        method: "PATCH",
        headers: { Prefer: "return=representation" },
        body: JSON.stringify(userToRow(patch)),
      }),
      "update"
    );
    return rows[0] ? rowToUser(rows[0]) : undefined;
  },
  remove: async (id) => {
    await sbRows(await sb(`users?id=eq.${enc(id)}`, { method: "DELETE" }), "remove");
  },
  deleteAccount: async (u) => {
    await sbOk(
      await sb("rpc/atlas_delete_account", {
        method: "POST",
        body: JSON.stringify({
          p_user_id: u.id,
          p_user_email: u.email.toLowerCase(),
        }),
      }),
      "deleteAccount"
    );
  },
  list: async () => {
    const rows = await sbRows(await sb("users?order=created_at.desc"), "list");
    return rows.map(rowToUser);
  },
  audit: async (e) => {
    await sbRows(
      await sb("audit", {
        method: "POST",
        body: JSON.stringify({
          id: e.id,
          at: e.at,
          actor_id: e.actorId,
          actor_email: e.actorEmail,
          action: e.action,
          target_id: e.targetId ?? null,
          target_email: e.targetEmail ?? null,
          meta: e.meta ?? null,
        }),
      }),
      "audit"
    );
  },
  auditList: async (limit = 200) => {
    const rows = await sbRows(await sb(`audit?order=at.desc&limit=${limit}`), "auditList");
    return rows.map((r) => ({
      id: String(r.id),
      at: String(r.at),
      actorId: String(r.actor_id ?? ""),
      actorEmail: String(r.actor_email ?? ""),
      action: String(r.action ?? ""),
      targetId: (r.target_id as string) ?? undefined,
      targetEmail: (r.target_email as string) ?? undefined,
      meta: (r.meta as Record<string, unknown>) ?? undefined,
    }));
  },
  addResetToken: async (t) => {
    await sbRows(
      await sb("reset_tokens", {
        method: "POST",
        body: JSON.stringify({ token: t.token, email: t.email.toLowerCase(), exp: t.exp }),
      }),
      "reset-token"
    );
  },
  addWaitlist: async (w) => {
    const email = w.email.toLowerCase();
    const existing = await sbRows(await sb(`waitlist?email=eq.${enc(email)}&limit=1`), "waitlist-check");
    if (existing[0]) return { ok: true, duplicate: true };
    await sbRows(
      await sb("waitlist", {
        method: "POST",
        headers: { Prefer: "resolution=ignore-duplicates" },
        body: JSON.stringify({
          id: newId(),
          email,
          role: w.role ?? null,
          source: w.source ?? null,
          created_at: new Date().toISOString(),
        }),
      }),
      "waitlist-insert"
    );
    return { ok: true, duplicate: false };
  },
  listWaitlist: async (limit = 1000) => {
    const rows = await sbRows(await sb(`waitlist?order=created_at.desc&limit=${limit}`), "listWaitlist");
    return rows.map((r) => ({
      id: String(r.id),
      email: String(r.email),
      role: (r.role as string) ?? undefined,
      source: (r.source as string) ?? undefined,
      createdAt: String(r.created_at ?? new Date().toISOString()),
    }));
  },
  createSession: async (session) => {
    await sbRows(
      await sb("atlas_sessions", {
        method: "POST",
        body: JSON.stringify({
          id: session.id,
          user_id: session.userId,
          created_at: session.createdAt,
          expires_at: session.expiresAt,
          revoked_at: session.revokedAt ?? null,
        }),
      }),
      "create-session"
    );
  },
  getSession: async (id) => {
    const rows = await sbRows(
      await sb(`atlas_sessions?id=eq.${enc(id)}&limit=1`),
      "get-session"
    );
    return rows[0] ? rowToSession(rows[0]) : undefined;
  },
  revokeSession: async (id) => {
    await sbRows(
      await sb(`atlas_sessions?id=eq.${enc(id)}&revoked_at=is.null`, {
        method: "PATCH",
        body: JSON.stringify({ revoked_at: new Date().toISOString() }),
      }),
      "revoke-session"
    );
  },
  revokeSessionsForUser: async (userId) => {
    await sbRows(
      await sb(`atlas_sessions?user_id=eq.${enc(userId)}&revoked_at=is.null`, {
        method: "PATCH",
        body: JSON.stringify({ revoked_at: new Date().toISOString() }),
      }),
      "revoke-user-sessions"
    );
  },
  linkAuthIdentity: async (userId, authUserId) => {
    return sbValue<boolean>(
      await sb("rpc/atlas_link_auth_identity", {
        method: "POST",
        body: JSON.stringify({ p_user_id: userId, p_auth_user_id: authUserId }),
      }),
      "link-auth-identity"
    );
  },
};

export function getStore(): Store {
  if (ENV.isProd && !ENV.hasSupabase) {
    // Visible in Vercel logs. Writes will throw (see persist); /api/health reports not-ok.
    console.error(
      "[atlas] PRODUCTION without Supabase — file store is ephemeral. Set SUPABASE_URL + " +
        "SUPABASE_SERVICE_ROLE_KEY. Writes are disabled until then."
    );
  }
  return ENV.hasSupabase ? supabaseStore : fileStore;
}

export const store = getStore();

export async function recordAnalyticsEvent(
  row: AnalyticsRow
): Promise<{ recorded: boolean }> {
  const result = await recordAnalyticsEvents([row]);
  return { recorded: result.recorded === 1 };
}

export async function recordAnalyticsEvents(
  rowsToRecord: AnalyticsRow[]
): Promise<{ recorded: number }> {
  if (!ENV.hasSupabase) return { recorded: 0 };
  const rows = await sbRows(
    await sb("analytics_events?on_conflict=deduplication_key", {
      method: "POST",
      headers: { Prefer: "resolution=ignore-duplicates,return=representation" },
      body: JSON.stringify(rowsToRecord),
    }),
    "analytics-event"
  );
  return { recorded: rows.length };
}

export type AnalyticsSummary = {
  since: string;
  timezone: "UTC";
  environment: string | null;
  build_commit: string | null;
  include_internal: boolean;
  unique_visitors: number;
  sessions: number;
  page_views: number;
  downloads_attempted: number;
  successful_installs: number;
  first_launches: number;
  scans_completed: number;
  graphs_opened: number;
  impact_completed: number;
  agents_connected: number;
  signup_success: number;
  signup_failed: number;
  active_users: number;
  returning_users: number;
  top_routes: { route: string; views: number }[];
};

export async function analyticsSummary(input: {
  since: string;
  until?: string | null;
  environment?: string | null;
  buildCommit?: string | null;
  includeInternal?: boolean;
}): Promise<AnalyticsSummary> {
  if (!ENV.hasSupabase) throw new Error("analytics backend unavailable");
  return sbValue<AnalyticsSummary>(
    await sb("rpc/atlas_analytics_summary", {
      method: "POST",
      body: JSON.stringify({
          p_since: input.since,
          p_until: input.until || null,
        p_environment: input.environment || null,
        p_build_commit: input.buildCommit || null,
        p_include_internal: input.includeInternal === true,
      }),
    }),
    "analytics-summary"
  );
}
