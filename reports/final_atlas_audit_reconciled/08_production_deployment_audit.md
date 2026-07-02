# 08 — Production Deployment Audit

**Date:** 2026-06-20 · **No code modified.** Supabase project: `https://wggjguqcxmskhjznexum.supabase.co`.
All claims cite file paths / line refs. App root: `websites/jarvis-landing` (set this as the Vercel **Root Directory**).

---

## PART 1 — Vercel environment variables

| Variable | Required? | Example value | Read in code |
|---|---|---|---|
| `SUPABASE_URL` | **REQUIRED (prod)** | `https://wggjguqcxmskhjznexum.supabase.co` | `_lib/config.ts:40` (hasSupabase); `_lib/store.ts:231` (restBase); `_lib/ratelimit.ts:30` |
| `SUPABASE_SERVICE_ROLE_KEY` | **REQUIRED (prod) · SECRET** | `eyJhbGciOiJIUzI1NiI...` (Supabase → Settings → API → **service_role** secret — NOT the anon key) | `_lib/config.ts:40`; `_lib/store.ts:237` (sb auth header); `_lib/ratelimit.ts:35` |
| `AUTH_SECRET` | **REQUIRED (prod) · SECRET** | 64-hex, e.g. `openssl rand -hex 32` | `_lib/config.ts:26` (authSecret); `api/health/route.ts:36` |
| `ATLAS_INSTALLER_URL` | **REQUIRED for `/download`** | `https://github.com/yoavkozokabab-blip/atlas-repo/releases/download/v0.1.0-beta/Atlas_Setup.exe` | `download/atlas/route.ts:51`; `api/health/route.ts:37` |
| `ADMIN_EMAILS` | Recommended | `yoavkozokabab@gmail.com` | `_lib/config.ts:29` (admin role; invite-mode bypass) |
| `BETA_MODE` | Optional (default `open`) | `invite` | `_lib/config.ts:34` |
| `BETA_ALLOWLIST` | **Required IF `BETA_MODE=invite`** | `a@x.com,b@y.com` | `_lib/config.ts:37` |
| `NEXT_PUBLIC_SUPPORT_EMAIL` | Recommended | `support@useatlas.dev` | `_config.ts:5` |
| `NEXT_PUBLIC_ATLAS_VERSION` | Optional (default `0.1.0-beta`) | `0.1.0-beta` | `_lib/config.ts:56` |
| `NEXT_PUBLIC_PAID_PLANS` | **MUST stay UNSET (free beta)** | _(do not set)_ | `_config.ts:13` |
| `PAYMENTS_MODE` | Optional (default `stub`) | _(leave unset)_ | `_lib/config.ts:46` |
| `STRIPE_SECRET_KEY` | Not set (free beta) | _(none)_ | `_lib/config.ts:43` |
| `ATLAS_INSTALLER_PATH` | Optional (local-file alt; NOT serverless-safe) | _(leave unset on Vercel)_ | `download/atlas/route.ts:23`; `account/downloads/page.tsx:10`; `api/health/route.ts:37` |
| `ATLAS_WEB_DATA_DIR` | Ignore (file-store/dev only) | _(unset)_ | `_lib/config.ts:50` |
| `NODE_ENV` | **Set automatically by Vercel** | `production` | `_lib/config.ts:15,53` (do not set manually) |

---

## PART 2 — Supabase migrations required

Only **two** migrations exist and they are **all the current code needs** (code touches tables `users`, `audit`, `reset_tokens`, `waitlist`, `rate_limits` + RPC `atlas_rate_limit_hit` — see `_lib/store.ts:69-180,264-357` and `_lib/ratelimit.ts:37`). `0003`/`0004` are **design-only, not in the repo, and NOT used by current code** (no `sessions`/`stripe_events` table is referenced).

| Order | File | Tables | Indexes | Policies / RLS / Grants |
|---|---|---|---|---|
| 1 | `supabase/migrations/0001_init.sql` | `users` (email unique), `audit`, `reset_tokens`, `waitlist` (email unique); extension `pgcrypto` | `users_email_idx (lower(email))`, `audit_at_idx (at desc)`, `waitlist_created_idx (created_at desc)` | RLS **enabled, NO policies** on all 4 (service_role bypass). **Grants** `usage on schema public` + `select,insert,update,delete` on the 4 tables to `service_role` (required — without them PostgREST returns `42501 permission denied`, per the file's own comment) |
| 2 | `supabase/migrations/0002_rate_limits.sql` | `rate_limits` (bucket pk) | `rate_limits_expires_idx (expires_at)` | RLS **enabled, no policies**; RPC `atlas_rate_limit_hit(p_key,p_window_seconds,p_max)` is `SECURITY DEFINER` (runs as owner, so it works without an explicit `rate_limits` grant) |

Apply via Supabase Dashboard → SQL Editor → paste each file → Run (0001 first, then 0002). Idempotent (`create … if not exists`).

---

## PART 3 — Exact deployment sequence (empty Supabase + existing Vercel)

1. **Supabase schema** — SQL Editor → run `0001_init.sql`, then `0002_rate_limits.sql`. Verify: tables `users, audit, reset_tokens, waitlist, rate_limits` exist and function `atlas_rate_limit_hit` exists.
2. **Get secrets** — Supabase → Settings → API: copy the **service_role** key (secret). `SUPABASE_URL` is the project URL above.
3. **Generate** `AUTH_SECRET` = `openssl rand -hex 32` (or `node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"`).
4. **Vercel project** — import the repo; **Root Directory = `websites/jarvis-landing`**; framework auto-detect (Next.js).
5. **Set env (Production)** — all Part-1 REQUIRED + recommended vars. **Leave `NEXT_PUBLIC_PAID_PLANS` unset.** (`ATLAS_INSTALLER_URL` can be set now if the GitHub release exists, else in step 8.)
6. **Deploy** → `vercel deploy --prod` (or push to the connected branch).
7. **Custom domain** — add `useatlas.dev` to the Vercel project and point registrar DNS at Vercel (**required for desktop auth — see Blocker B4**).
8. **Installer URL** — after the GitHub release exists, set `ATLAS_INSTALLER_URL` to the asset URL → redeploy.
9. **Smoke test** (Part 4).

---

## PART 4 — Production smoke test (endpoints that must work)

Run against the live origin (use `https://useatlas.dev` once DNS is live):

| Method | Endpoint | Expected | Proves |
|---|---|---|---|
| GET | `/api/health` | 200 `{ok:true, backend:"supabase", persistence:"ok", config.hasSupabase:true, hasAuthSecret:true}` | Supabase wired + schema present (`health/route.ts:20` calls `store.listWaitlist(1)`) |
| GET | `/` , `/pricing` , `/download` , `/privacy` , `/terms` , `/contact` , `/login` | 200 | pages render |
| POST | `/api/auth/register` `{email,password}` | 201 `{ok:true}` + Set-Cookie | website signup writes `users` |
| POST | `/api/auth/login` `{email,password}` | 200 `{ok:true}` + cookie | website login |
| GET | `/api/auth/session` | 200 user when cookie present | session read |
| POST | `/api/auth/desktop/register` `{email,password}` | 201 `{ok:true, token}` | **desktop signup** |
| POST | `/api/auth/desktop/login` `{email,password}` | 200 `{ok:true, token}` | **desktop login** |
| GET | `/api/auth/desktop/me` (`Authorization: Bearer <token>`) | 200 `{ok:true, user, plan}` | **desktop session verify** |
| POST | `/api/auth/desktop/logout` (Bearer) | 204 | desktop logout |
| POST | `/api/waitlist` (form `email`) | 200 persists/dedups | waitlist |
| POST | `/api/checkout` `{plan:"pro"}` | **403** "nothing to purchase yet" | free-beta guard (must NOT charge — `checkout/route.ts:12`) |
| GET | `/download/atlas` (logged in) | 302 → `ATLAS_INSTALLER_URL` | gated download (`download/atlas/route.ts:47,54`) |

Recommended end-to-end: `ATLAS_AUTH_MODE=website ATLAS_WEB_URL=https://useatlas.dev py -3 scripts/desktop_web_auth_smoke.py` (drives register→token→/me→logout→bad-login against the live site).

---

## PART 5 — Production blockers (real, code-referenced)

### Signup + login (website AND desktop endpoints)
- **B1 — Supabase env REQUIRED, else writes hard-fail.** Without `SUPABASE_URL`+`SUPABASE_SERVICE_ROLE_KEY`, `getStore()` returns the file store and `persist()` **throws in production** → register/login/waitlist 500. Code: `_lib/store.ts:118-129` (throw), `_lib/store.ts:368-377` (getStore). **Use the service_role key, not anon** (RLS blocks anon: `0001_init.sql` enables RLS with no policies).
- **B2 — Migrations 0001 must be applied (incl. its grants).** Missing tables/grants → PostgREST errors (`42501 permission denied`, per `0001` comment) → register/login fail, `/api/health` `persistence:"error"`.
- **B3 — `AUTH_SECRET` must be set (login stability).** If unset in prod, `_lib/config.ts:11-27` falls back to a **per-process ephemeral secret** → session cookies are invalidated on every serverless cold start → users are silently logged out. Not a hard throw, but effectively breaks login.

### Desktop auth
- **B4 — CRITICAL: the production site must be served at `https://useatlas.dev`.** The frozen desktop's auth target is `web_base()` default `https://useatlas.dev` (`jarvis_desktop/accounts_client.py`, `web_base()`). A bare Vercel preview URL will NOT be reached by installed desktops; no user-side env can fix it. **Resolution (no code change): point `useatlas.dev` DNS at Vercel.** (The only alternative — rebuild the installer with the Vercel URL — is a code change, out of scope here.)

### MCP usage
- **B5 — NONE.** The MCP path is fully local and **login-free**: `jarvis_desktop/mcp_server/runtime.py` has no account/auth gate (only secret-redaction). MCP works regardless of Supabase/Vercel/domain. Connect-Claude → scan → use does not depend on this deployment at all.

### Degraded-but-not-blocking
- **Migration 0002 (rate limiting):** if not applied, `_lib/ratelimit.ts` fails **open** on RPC error (returns allow) → auth still works but is **unthrottled** (no brute-force protection). Apply 0002 to enable rate limiting; it is not required for auth to function.
- **`ATLAS_INSTALLER_URL` unset:** `/download/atlas` returns "No installer available" (`download/atlas/route.ts:64`). Blocks the website download funnel only — not signup/login/desktop-auth/MCP.

---

### Bottom line
For **signup + login + desktop auth**: apply 0001 (+0002), set `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` + `AUTH_SECRET`, and **serve at `useatlas.dev`** (B4). For **MCP usage**: nothing in this deployment is required. No code changes needed anywhere; every blocker is configuration/ops.
