# TASK 2 — Vercel Environment (owner-ready)

**Date:** 2026-06-20 · Vercel **Root Directory** = `websites/jarvis-landing`.

> ⚠️ **CRITICAL:** for the current **atlas-prod** project, set
> `SUPABASE_URL=https://wggjguqcxmskhjznexum.supabase.co` (and the service-role key from
> the **same** project). The previously-deployed value pointed at the dead project
> `qfwmfllcqbngrowzbfpc` → `ENOTFOUND` → register/login 500.

| Variable | Required? | Example shape | Consumed at | What breaks if wrong | Secret? | Must match Supabase project? |
|---|---|---|---|---|---|---|
| `SUPABASE_URL` | **YES** | `https://wggjguqcxmskhjznexum.supabase.co` | `store.ts:231`, `ratelimit.ts:30`, `config.ts:40` | wrong/dead → `ENOTFOUND` 500 on signup/login; missing → file store throws in prod | no (URL) | **YES** |
| `SUPABASE_SERVICE_ROLE_KEY` | **YES** | `eyJhbGci…` (service_role JWT) | `store.ts:237`, `ratelimit.ts:35`, `config.ts:40` | wrong/anon → RLS blocks all queries → auth fails; missing → file store throws | **YES** | **YES (same project as URL)** |
| `AUTH_SECRET` | **YES** | 64-hex (`openssl rand -hex 32`) | `config.ts:26`, `auth.ts` | missing in prod → ephemeral secret → users logged out on every cold start | **YES** | no |
| `ADMIN_EMAILS` | recommended | `yoavkozokabab@gmail.com` | `config.ts:29` | missing → no admins (not an auth blocker) | no | no |
| `BETA_MODE` | optional (`open` default) | `invite` | `config.ts:34` | `invite` w/o `BETA_ALLOWLIST` → only admins approved | no | no |
| `ATLAS_INSTALLER_URL` | for /download | GitHub release asset URL | `download/atlas/route.ts:51` | unset → "No installer available" (download funnel only) | no | no |
| `NEXT_PUBLIC_SUPPORT_EMAIL` | recommended | `support@useatlas.dev` | `_config.ts:5` | wrong → support mailto goes to a dead inbox | no | no |
| `NEXT_PUBLIC_SUPABASE_URL` | **NOT used by this app** | `https://wggjguqcxmskhjznexum.supabase.co` | — (no code reference) | nothing — **not consumed**. Set it to the same value for consistency if you wish, but it does **not** affect the backend. | no | (cosmetic) |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | **NOT used by this app** | `eyJhbGci…` (anon) | — | nothing — not consumed (app uses service-role server-side only) | no | (cosmetic) |

**Honest note (vs the requested list):** this codebase talks to Supabase via raw PostgREST + the **service-role** key, not `@supabase/supabase-js`/`createClient`. So `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` are listed but are **not** what fixes auth — the server `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` are. The prompt's "both `SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_URL` must be `…wggjguqcxmskhjznexum…`" is fine to follow (it's harmless and consistent), but only `SUPABASE_URL` is actually read.

**Do NOT set** `NEXT_PUBLIC_PAID_PLANS` (keeps paid hidden), `STRIPE_SECRET_KEY`, `PAYMENTS_MODE` (free beta). `NODE_ENV` is set by Vercel automatically.

**Verify after deploy:** `GET /api/health` → `persistence:"ok"`, `supabase.hostname:"wggjguqcxmskhjznexum.supabase.co"`, `supabase.validation_passed:true`, `supabase.service_role_present:true`.
