import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { ENV } from "./config";

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
  passwordHash: string; // scrypt "scrypt$salt$hash" — never plaintext, never sent to client
  role: Role;
  status: AccountStatus;
  plan: Plan;
  planStatus: PlanStatus;
  trialEndsAt?: string | null;
  renewsAt?: string | null;
  stripeCustomerId?: string | null;
  createdAt: string;
  lastLoginAt?: string | null;
  downloads: number;
}

export type SafeUser = Omit<User, "passwordHash">;
export function toSafe(u: User): SafeUser {
  const rest: Partial<User> = { ...u };
  delete rest.passwordHash; // never expose the hash to the client
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

interface DBShape {
  users: User[];
  audit: AuditEntry[];
  resetTokens: { token: string; email: string; exp: number }[];
  waitlist: WaitlistEntry[];
}

export function newId(): string {
  return crypto.randomUUID();
}

export interface Store {
  getByEmail(email: string): Promise<User | undefined>;
  getById(id: string): Promise<User | undefined>;
  create(u: User): Promise<User>;
  update(id: string, patch: Partial<User>): Promise<User | undefined>;
  remove(id: string): Promise<void>;
  list(): Promise<User[]>;
  audit(e: AuditEntry): Promise<void>;
  auditList(limit?: number): Promise<AuditEntry[]>;
  addResetToken(t: { token: string; email: string; exp: number }): Promise<void>;
  /** Returns duplicate:true if the email was already on the waitlist (idempotent). */
  addWaitlist(w: { email: string; role?: string; source?: string }): Promise<{ ok: boolean; duplicate: boolean }>;
  listWaitlist(limit?: number): Promise<WaitlistEntry[]>;
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
    };
  } catch {
    return { users: [], audit: [], resetTokens: [], waitlist: [] };
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
};

// ---------------------------------------------------------------------------
// Supabase backend (production) — PostgREST over fetch, service-role key.
// ---------------------------------------------------------------------------

type Row = Record<string, unknown>;

function userToRow(u: Partial<User>): Row {
  const r: Row = {};
  if (u.id !== undefined) r.id = u.id;
  if (u.email !== undefined) r.email = u.email.toLowerCase();
  if (u.name !== undefined) r.name = u.name ?? null;
  if (u.passwordHash !== undefined) r.password_hash = u.passwordHash;
  if (u.role !== undefined) r.role = u.role;
  if (u.status !== undefined) r.status = u.status;
  if (u.plan !== undefined) r.plan = u.plan;
  if (u.planStatus !== undefined) r.plan_status = u.planStatus;
  if (u.trialEndsAt !== undefined) r.trial_ends_at = u.trialEndsAt ?? null;
  if (u.renewsAt !== undefined) r.renews_at = u.renewsAt ?? null;
  if (u.stripeCustomerId !== undefined) r.stripe_customer_id = u.stripeCustomerId ?? null;
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
    passwordHash: String(r.password_hash ?? ""),
    role: (r.role as Role) ?? "user",
    status: (r.status as AccountStatus) ?? "active",
    plan: (r.plan as Plan) ?? "free",
    planStatus: (r.plan_status as PlanStatus) ?? "none",
    trialEndsAt: (r.trial_ends_at as string) ?? null,
    renewsAt: (r.renews_at as string) ?? null,
    stripeCustomerId: (r.stripe_customer_id as string) ?? null,
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
    throw new Error(`supabase ${ctx} failed: ${res.status} ${body.slice(0, 300)}`);
  }
  const text = await res.text();
  if (!text) return [];
  return JSON.parse(text) as Row[];
}
const enc = encodeURIComponent;

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
    const rows = await sbRows(
      await sb("users", {
        method: "POST",
        headers: { Prefer: "return=representation" },
        body: JSON.stringify(userToRow(u)),
      }),
      "create"
    );
    return rows[0] ? rowToUser(rows[0]) : u;
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
  list: async () => {
    const rows = await sbRows(await sb("users?order=created_at.desc"), "list");
    return rows.map(rowToUser);
  },
  audit: async (e) => {
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
    });
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
    await sb("reset_tokens", {
      method: "POST",
      body: JSON.stringify({ token: t.token, email: t.email.toLowerCase(), exp: t.exp }),
    });
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
