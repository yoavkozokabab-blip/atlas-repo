import crypto from "node:crypto";
import { cookies } from "next/headers";
import { ENV } from "./config";
import { store, User, SafeUser, toSafe, newId } from "./store";

const COOKIE = "atlas_session";
const SESSION_TTL_S = 60 * 60 * 24 * 7; // 7 days

// --- Passwords (scrypt; never plaintext, never returned to client) ---
export function hashPassword(pw: string): string {
  const salt = crypto.randomBytes(16);
  const derived = crypto.scryptSync(pw, salt, 64);
  return `scrypt$${salt.toString("hex")}$${derived.toString("hex")}`;
}
export function verifyPassword(pw: string, stored: string): boolean {
  const [scheme, saltHex, hashHex] = (stored || "").split("$");
  if (scheme !== "scrypt" || !saltHex || !hashHex) return false;
  const derived = crypto.scryptSync(pw, Buffer.from(saltHex, "hex"), 64);
  const a = Buffer.from(hashHex, "hex");
  return a.length === derived.length && crypto.timingSafeEqual(a, derived);
}

// --- Session token (HMAC-signed; httpOnly cookie) ---
function sign(data: string): string {
  return crypto.createHmac("sha256", ENV.authSecret).update(data).digest("base64url");
}
export function createToken(userId: string): string {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + SESSION_TTL_S })
  ).toString("base64url");
  return `${payload}.${sign(payload)}`;
}
export function verifyToken(token: string): string | null {
  const [payload, sig] = (token || "").split(".");
  if (!payload || !sig) return null;
  const expected = sign(payload);
  const a = Buffer.from(sig);
  const b = Buffer.from(expected);
  if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) return null;
  try {
    const { sub, exp } = JSON.parse(Buffer.from(payload, "base64url").toString());
    if (!sub || typeof exp !== "number" || exp < Math.floor(Date.now() / 1000)) return null;
    return sub as string;
  } catch {
    return null;
  }
}

export async function setSession(userId: string): Promise<void> {
  const c = await cookies();
  c.set(COOKIE, createToken(userId), {
    httpOnly: true,
    secure: ENV.isProd,
    sameSite: "lax",
    path: "/",
    maxAge: SESSION_TTL_S,
  });
}
export async function clearSession(): Promise<void> {
  const c = await cookies();
  c.set(COOKIE, "", { httpOnly: true, path: "/", maxAge: 0 });
}
export async function currentUser(): Promise<User | null> {
  const c = await cookies();
  const tok = c.get(COOKIE)?.value;
  if (!tok) return null;
  const uid = verifyToken(tok);
  if (!uid) return null;
  const u = await store.getById(uid);
  if (!u || u.status === "suspended") return null;
  return u;
}
export async function currentSafeUser(): Promise<SafeUser | null> {
  const u = await currentUser();
  return u ? toSafe(u) : null;
}

// --- Registration / login ---
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
export function validEmail(e: string): boolean {
  return EMAIL_RE.test(e || "");
}

type AuthResult = { ok: true; user: User } | { ok: false; error: string };

export async function registerUser(email: string, password: string, name?: string): Promise<AuthResult> {
  email = (email || "").trim().toLowerCase();
  if (!validEmail(email)) return { ok: false, error: "Enter a valid email address." };
  if ((password || "").length < 8) return { ok: false, error: "Password must be at least 8 characters." };
  if (await store.getByEmail(email)) return { ok: false, error: "An account with this email already exists." };
  const now = new Date().toISOString();
  const role = ENV.adminEmails.includes(email) ? "admin" : "user";
  const user: User = {
    id: newId(),
    email,
    name: name?.trim() || undefined,
    passwordHash: hashPassword(password),
    role,
    status: "active",
    plan: "free",
    planStatus: "none",
    createdAt: now,
    lastLoginAt: now,
    downloads: 0,
  };
  await store.create(user);
  return { ok: true, user };
}

// Dummy hash so unknown-email logins still run a KDF (reduces enumeration timing).
const DUMMY_HASH = `scrypt$${"00".repeat(16)}$${"00".repeat(64)}`;

export async function loginUser(email: string, password: string): Promise<AuthResult> {
  email = (email || "").trim().toLowerCase();
  const user = await store.getByEmail(email);
  const valid = verifyPassword(password, user?.passwordHash || DUMMY_HASH);
  // Generic message — never reveal whether the email exists (anti-enumeration).
  if (!user || !valid) return { ok: false, error: "Invalid email or password." };
  if (user.status === "suspended") return { ok: false, error: "This account is suspended. Contact support." };
  await store.update(user.id, { lastLoginAt: new Date().toISOString() });
  return { ok: true, user };
}

// --- Desktop (bearer-token) auth (Phase 186A) ---
// The desktop is a native client, not a browser, so it authenticates with a
// Bearer token instead of the httpOnly cookie. It hits the SAME Supabase-backed
// user store as the website — one account, one identity. The token is the same
// HMAC-signed payload used by the cookie (createToken/verifyToken).
export function bearerToken(req: Request): string | null {
  const m = /^Bearer\s+(.+)$/i.exec(req.headers.get("authorization") || "");
  return m ? m[1].trim() : null;
}
export async function userFromBearer(req: Request): Promise<User | null> {
  const tok = bearerToken(req);
  if (!tok) return null;
  const uid = verifyToken(tok);
  if (!uid) return null;
  const u = await store.getById(uid);
  if (!u || u.status === "suspended") return null;
  return u;
}
/**
 * Beta access rule (Phase 186A). Open beta → everyone active is approved.
 * Invite beta → only allow-listed emails (and admins). Minimal, env-driven,
 * no schema change. Unapproved users still get an account + a clear message.
 */
export function betaApproved(u: User): boolean {
  if (ENV.betaMode === "open") return true;
  if (u.role === "admin" || ENV.adminEmails.includes(u.email)) return true;
  return ENV.betaAllowlist.includes(u.email.toLowerCase());
}

/** Entitlement view returned to the desktop so it can gate features. */
export function entitlement(u: User) {
  const approved = betaApproved(u);
  return {
    user: toSafe(u),
    plan: u.plan,
    planStatus: u.planStatus,
    trialEndsAt: u.trialEndsAt ?? null,
    renewsAt: u.renewsAt ?? null,
    approved,
    betaMode: ENV.betaMode,
    message: approved
      ? null
      : "Your account isn't approved for the Atlas beta yet. Join the waitlist and we'll email your invite.",
  };
}

// --- Roles ---
export function isAdmin(u: User | null | undefined): boolean {
  if (!u) return false;
  return u.role === "admin" || ENV.adminEmails.includes(u.email);
}
export async function requireAdmin(): Promise<User | null> {
  const u = await currentUser();
  return isAdmin(u) ? u : null;
}
