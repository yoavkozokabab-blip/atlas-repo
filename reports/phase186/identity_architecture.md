# IDENTITY ARCHITECTURE (Phase 186A)

**Date:** 2026-06-20 · **Status of execution:** design = **PASS**, end-to-end demo = **BLOCKED** (needs a provisioned Supabase project + the desktop rewire below; I will not claim a demo I cannot run here).

## 1. Current state (audited, not assumed)

| Surface | Auth code | User store | Password hash | Sessions |
|---|---|---|---|---|
| **Website** (Next.js, Vercel) | `app/_lib/auth.ts` | `app/_lib/store.ts` → **Supabase** (PostgREST, service-role) + file fallback; schema `supabase/migrations/0001_init.sql` (`users`, `audit`, `reset_tokens`, `waitlist`) | **scrypt** (`auth.ts:10`) | Self-contained HMAC-signed httpOnly cookie, 7-day, **no server-side revocation** |
| **Desktop** (Python) | `jarvis_desktop/accounts_client.py` → `ATLAS_ACCOUNTS_URL` default `http://127.0.0.1:8788`; spawns local FastAPI via `accounts_service_runner.py` | `accounts_service/` SQLAlchemy (`User`/`License`/`Device`/`Session`) — local SQLite | **bcrypt** (`accounts_service/.lib/bcrypt`) | JWT access + **rotating refresh tokens**, device registry, `sessions` table |
| **Old serverless** (`~/jarvis_landing/api/`) | `_lib/auth.js` | `_lib/supabase.js` | n/a | n/a — **abandoned, must be deleted** |

**The problem, precisely:** a website account lives in Supabase with a *scrypt* hash; a desktop account lives in a *locally-spawned* SQLite service with a *bcrypt* hash. They are different databases, different hash schemes, and different session models. A web signup is invisible to the desktop and vice-versa. The hashes are **not interchangeable**, so you cannot simply copy rows between them.

## 2. Canonical decision

**Supabase is the single source of truth.** The **website (Next.js on Vercel) is the one auth authority**; the desktop becomes a *client* of it. Rationale:
- The website auth (`auth.ts`/`store.ts`) is already Supabase-backed, prod-guarded, and the funnel (signup → download → pay) lives there.
- The desktop must surface billing/subscription state that originates on the web. Making the web canonical means one place owns plan/entitlement.
- Avoids hosting and exposing the heavier FastAPI service publicly.

`accounts_service` (FastAPI) is **demoted to dev/offline only** and must stop being spawned in production builds. It is not deleted (it has 73 passing tests and useful device logic we may port), but it is no longer an identity authority.

## 3. Target architecture

```
        ┌─────────────────────────── Supabase (canonical) ───────────────────────────┐
        │  users (scrypt hash, plan, plan_status, stripe_customer_id) · sessions ·    │
        │  reset_tokens · audit · waitlist · rate_limits (186D)                        │
        └───────▲───────────────────────────────────────────────────────▲────────────┘
                │ PostgREST (service-role, server-side only)             │
        ┌───────┴────────┐                                       ┌───────┴───────────┐
        │  Website API   │  /api/auth/* (cookie, browser)        │  Desktop (Atlas)  │
        │  (Next.js)     │  /api/auth/desktop/* (Bearer token) ◄─┤  accounts_client  │
        └────────────────┘                                       └───────────────────┘
```

The desktop no longer runs a local accounts service in production; it calls the hosted website's **desktop auth endpoints** (bearer-token, not cookie).

## 4. Endpoints to add (website)

Token = the existing HMAC-signed token from `auth.ts` (`createToken`/`verifyToken`), returned in JSON instead of a cookie. New routes (thin wrappers over existing `loginUser`/`registerUser`):

| Method | Route | Body / Header | Returns |
|---|---|---|---|
| POST | `/api/auth/desktop/register` | `{email,password,name?,device_id}` | `{token, user(SafeUser), plan, planStatus}` |
| POST | `/api/auth/desktop/login` | `{email,password,device_id}` | `{token, user, plan, planStatus}` |
| GET | `/api/auth/desktop/me` | `Authorization: Bearer <token>` | `{user, plan, planStatus, trialEndsAt, renewsAt}` (entitlement) |
| POST | `/api/auth/desktop/logout` | `Authorization: Bearer <token>` | `204`; revokes the session row |

All reuse `loginUser`/`registerUser` and **must keep the generic anti-enumeration error** already in `auth.ts:118`.

## 5. Desktop changes

- `accounts_client.py:29`: default `ATLAS_ACCOUNTS_URL` → the hosted site (e.g. `https://useatlas.dev`); call `/api/auth/desktop/*` with a stored bearer token.
- `accounts_service_runner.py`: **do not auto-spawn** when a remote URL is configured / in packaged builds; keep local spawn only for `ATLAS_DEV=1`.
- Store the token in the OS-appropriate location already used for desktop state (`%USERPROFILE%\.jarvis_desktop`), file perms locked to the user.
- Feature gating reads `plan`/`planStatus` from `/me`.

## 6. Session handling (unified) — also fixes website V3

Add a **`sessions`** table to Supabase (migration `0003`) so logout/multi-device/revocation work for BOTH surfaces:

```
sessions(id uuid pk, user_id uuid, device_id text, token_hash text, created_at, expires_at, revoked_at)
```

| Concern | Design |
|---|---|
| Refresh tokens | Issue an opaque refresh token (hashed in `sessions`); short-lived access token (the signed payload). Rotate on refresh, revoke old (mirror `accounts_service` rotation logic — already proven). |
| Logout | Set `revoked_at`; `currentUser`/`/me` reject revoked. |
| Multi-device | One `sessions` row per device; optional `max_devices` per plan (port from `accounts_service`). |
| Expired sessions | `expires_at` check + access-token `exp`. |
| Suspension | `currentUser` already returns null when `status='suspended'` (`auth.ts:70`); `/me` returns 403. |

## 7. Billing / license / admin ownership

- **Billing & license** live on the `users` row (`plan`, `plan_status`, `trial_ends_at`, `renews_at`, `stripe_customer_id` — already in `0001_init.sql`). Stripe webhooks (186B) write here; the desktop reads via `/me`. One owner.
- **Admin**: `requireAdmin()` (`auth.ts:129`) gated by `role==='admin'` or `ADMIN_EMAILS`. Unchanged, single authority.

## 8. PASS / FAIL / BLOCKED

| Task | Status | Evidence |
|---|---|---|
| Audit all auth flows | **PASS** | This doc; file:line citations above. |
| Choose canonical source (Supabase) | **PASS** | §2. |
| Desktop authenticates against website store | **WEBSITE SIDE DONE (PASS, local) / DESKTOP REWIRE PENDING** | The 4 bearer-token endpoints (§4) are implemented and **demonstrated end-to-end on the dev file-store**: register → 128-char signed token; `GET /me` + Bearer returns the same identity + entitlement; tampered token → 401; login returns a working token; wrong password → generic error. Remaining: point `accounts_client.py` at these endpoints + provision Supabase. |
| Remove fragmentation | **PARTIAL** | One store now serves both browser (cookie) and desktop (bearer) auth in the website. Still to do: desktop client rewire + delete the old `~/jarvis_landing/api/`. |
| Session handling (refresh/logout/multi-device/expiry/suspension) | **PARTIAL** | Desktop side proven in `accounts_service` (73 tests); website side needs the `sessions` table (§6). |
| Migration path | **PASS (design)** | See `identity_migration_plan.md`. |
| **Website signup → Desktop login demo** | **BLOCKED** | Cannot run end-to-end without a provisioned Supabase + the desktop rewire. **Will not be claimed without a recorded run.** |
