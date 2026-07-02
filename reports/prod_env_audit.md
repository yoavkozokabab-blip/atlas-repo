# Production Supabase Env Audit

**Date:** 2026-06-20 · App: `websites/jarvis-landing` · Actual project: `https://wggjguqcxmskhjznexum.supabase.co`
Production error: `POST /api/auth/register 500 → TypeError: fetch failed → getaddrinfo ENOTFOUND qfwmfllcqbngrowzbfpc.supabase.co`.

## Every Supabase URL found (whole repo)
| Location | Value | Status |
|---|---|---|
| `websites/jarvis-landing/.env.local:16` | `SUPABASE_URL=https://qfwmfllcqbngrowzbfpc.supabase.co/rest/v1/` | **STALE / wrong project** (gitignored, local-only) |
| `websites/jarvis-landing/.env.local:20` | `NEXT_PUBLIC_SUPABASE_URL=https://qfwmfllcqbngrowzbfpc.supabase.co/rest/v1/` | STALE **and UNUSED by code** |
| `websites/jarvis-landing/.env.example:23` | `SUPABASE_URL=` (empty) | Clean placeholder (tracked) |
| `app/_lib/store.ts:227` | `// https://x.supabase.co` (docstring example) | Comment only — not a URL/fallback |
| Anywhere else in tracked code/config | — | **none** (the stale id `qfwmfllcqbngrowzbfpc` exists ONLY in the gitignored `.env.local` and this session's transcript) |

## Every env variable consumed (by code, with file:line)
**Actually read by the running app:**
- `SUPABASE_URL` — `_lib/store.ts:231`, `_lib/ratelimit.ts:30`, `_lib/config.ts:40`
- `SUPABASE_SERVICE_ROLE_KEY` — `_lib/store.ts:237`, `_lib/ratelimit.ts:35`, `_lib/config.ts:40`
- `AUTH_SECRET` — `_lib/config.ts:26`; `ADMIN_EMAILS` — `_lib/config.ts:29`; `BETA_MODE`/`BETA_ALLOWLIST` — `:34,37`; `ATLAS_INSTALLER_URL` — `download/atlas/route.ts:51`; `NEXT_PUBLIC_*` (support email, version, paid) — `_config.ts`.

**Present in env files but consumed by NO code (dead vars):**
- `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `SUPABASE_ANON_KEY` — **zero references** in `app/`. The app uses raw PostgREST + service-role `fetch`; it does **not** use `@supabase/supabase-js`, `createClient`, or `createServerClient` (verified: none found). → These vars (and the prompt's Phase-5 "Required" anon/NEXT_PUBLIC list) are **not** part of this codebase's contract; a stale value in them is harmless and is **not** the culprit.

## Fallback values
- `_lib/store.ts:231` → `(process.env.SUPABASE_URL || "").trim()` — fallback is **empty string** (safe: an empty origin fails, it never silently points at another project).
- `_lib/ratelimit.ts:30` → same `|| ""`.
- `_lib/config.ts:26` → `process.env.AUTH_SECRET || ephemeralSecret()` (per-process random; not a URL).
- **No `|| "https://…"` or `?? "https://…"` fallbacks anywhere** (searched; none found).

## Hardcoded URLs
**None in code.** The only `supabase.co` literal in `app/` is the docstring comment at `store.ts:227`.

## Deprecated / stale URLs
The stale `qfwmfllcqbngrowzbfpc` project URL lives **only** in the gitignored `websites/jarvis-landing/.env.local` (lines 16 and 20). Not in any tracked file, not in `.env.example`, not in code.

## Production runtime path (how the URL is resolved at request time)
`POST /api/auth/register` → `registerUser()` → `store.create()` (`_lib/store.ts:273`) → `sb("users", …)` (`:236`) → `fetch(\`${restBase()}/users\`)` where `restBase()` (`:230-233`) reads **`process.env.SUPABASE_URL` at runtime**. The route is `runtime="nodejs"` + `dynamic="force-dynamic"` → the env is read **per request at runtime**, not captured at build time.

→ Therefore the host that's contacted is whatever `SUPABASE_URL` is in the **running environment** (Vercel's configured env var). See `prod_env_root_cause` below.

## Root cause (Phase 2 — proven, no guessing)
**Stale Vercel environment variable value — runtime env capture.** Ruling out each possibility:
- **Hardcoded fallback?** No — code fallback is `|| ""` (store.ts:231, ratelimit.ts:30); no URL default exists.
- **Stale `.env.example`?** No — `.env.example:23` is empty (`grep -c qfwmfllcqbngrowzbfpc .env.example` = 0).
- **Build-time capture?** No — `SUPABASE_URL` is read inside `restBase()` at request time on a dynamic Node route, not inlined at build.
- **Old branch / generated artifact?** No — code reads `process.env.SUPABASE_URL`; no generated config holds a URL.
- **Stale env value?** **YES.** The stale `qfwmfllcqbngrowzbfpc` URL is set as the deployment's `SUPABASE_URL`. It is mirrored in the local `.env.local:16` (the operator's local copy — the likely source that was pasted into Vercel). **Reproduced live:** running the app against `.env.local`, `GET /api/health` returns `hostname:"qfwmfllcqbngrowzbfpc.supabase.co"`, `persistence:"error"`, `detail:"fetch failed"` — the identical production symptom.

**Fix (owner, no code change):** set Vercel **`SUPABASE_URL=https://wggjguqcxmskhjznexum.supabase.co`** and **`SUPABASE_SERVICE_ROLE_KEY`=** the *new* project's service-role key, then redeploy. Also update local `.env.local:16-17` to the new project's URL **and** matching service-role key (changing only the URL would leave the old project's key → still broken). The unused `NEXT_PUBLIC_SUPABASE_*`/`SUPABASE_ANON_KEY` need not be touched.
