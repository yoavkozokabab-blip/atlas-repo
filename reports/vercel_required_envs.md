# Vercel Required Environment Variables (Atlas website)

**Date:** 2026-06-20 · App root (Vercel **Root Directory**): `websites/jarvis-landing`.
Each var: why it exists · where consumed · failure mode if missing/wrong.

> **Correction to the requested list:** this codebase talks to Supabase via raw PostgREST + the **service-role** key, NOT `@supabase/supabase-js`/`createClient`. Therefore `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` are **NOT consumed anywhere** (`grep` in `app/` = 0). They are listed below as "not required / not used" so they are not mistaken for the fix.

## Required (auth/funnel will fail without these)
| Variable | Why it exists | Consumed at | Failure mode if missing/wrong |
|---|---|---|---|
| `SUPABASE_URL` | Base of the Supabase project (PostgREST origin). **This is the variable that was stale in prod.** | `_lib/store.ts:231`, `_lib/ratelimit.ts:30`, `_lib/config.ts:40` | Missing → file store → `persist()` throws in prod (`store.ts:118-129`), 500s. Wrong project → `ENOTFOUND`/`fetch failed` 500 on register/login (the observed bug). Set to `https://wggjguqcxmskhjznexum.supabase.co`. |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-side auth to PostgREST (bypasses RLS). **Use service_role, not anon.** | `_lib/store.ts:237`, `_lib/ratelimit.ts:35`, `_lib/config.ts:40` | Missing → file store → throws in prod. Anon key instead → RLS blocks all queries (no policies) → 401/empty → signup/login fail. Must match the **same** project as `SUPABASE_URL`. |
| `AUTH_SECRET` | HMAC key for the signed session cookie. | `_lib/config.ts:26`, `auth.ts` (sign/verify) | Missing in prod → per-process ephemeral secret → cookies invalidate on every cold start → users silently logged out. Set a stable 64-hex (`openssl rand -hex 32`). |

## Recommended
| Variable | Why | Consumed at | Failure mode |
|---|---|---|---|
| `ADMIN_EMAILS` | Grants admin role; invite-mode bypass. | `_lib/config.ts:29` | Missing → no admins; not an auth blocker. |
| `NEXT_PUBLIC_SUPPORT_EMAIL` | Support/contact display. | `_config.ts:5` | Missing → contact falls back to `/contact`. |

## Optional
| Variable | Why | Consumed at | Failure mode |
|---|---|---|---|
| `ATLAS_INSTALLER_URL` | `/download/atlas` 302 target (hosted installer). | `download/atlas/route.ts:51` | Missing → "No installer available" (download funnel only; not auth). |
| `PAYMENTS_MODE` | `stub`/`test`/`live` (default `stub`). | `_lib/config.ts:46` | Leave unset for free beta. |
| `BETA_MODE` / `BETA_ALLOWLIST` | Open vs invite-gated beta. | `_lib/config.ts:34,37` | `invite` without allowlist → only admins approved. |
| `NEXT_PUBLIC_ATLAS_VERSION` | Display version. | `_lib/config.ts:56` | Cosmetic. |

## NOT required / NOT used by this codebase (do not rely on these)
| Variable | Status |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | **Not consumed** in `app/` — setting/clearing it has no effect on the backend. |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` / `SUPABASE_ANON_KEY` | **Not consumed** — the app uses the service-role key server-side only. |
| `NODE_ENV` | Set automatically by Vercel; do not set manually. |
| `ATLAS_WEB_DATA_DIR` | File-store/dev only; irrelevant in prod. |

## Post-set verification
After setting `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` (new project) + `AUTH_SECRET` and redeploying, hit **`GET /api/health`** and confirm:
`persistence:"ok"`, `supabase.hostname:"wggjguqcxmskhjznexum.supabase.co"`, `supabase.validation_passed:true`, `supabase.service_role_present:true`. If `hostname` shows any other project, the env is still drifted.
