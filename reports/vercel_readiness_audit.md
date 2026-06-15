# Atlas Website — Vercel Readiness Audit (Ops Phase / Step 4)

**Date:** 2026-06-16
**Target:** Vercel free plan, `*.vercel.app` URL (no paid domain).

## Checks

| Check | Status | Evidence / Notes |
|---|---|---|
| Next.js config production-safe | **PASS** | `next.config.mjs`: `compress`, `poweredByHeader:false`, `reactStrictMode`, `optimizePackageImports`. No risky settings. |
| Production build succeeds | **PASS** | `next build` → 25/25 pages, exit 0 |
| No hardcoded localhost in user-facing pages | **PASS** | grep for `localhost`/`127.0.0.1`/`http://` in `app/` → no matches |
| Download flow uses env var | **PASS** | `download/atlas/route.ts` 302-redirects to `ATLAS_INSTALLER_URL`; local file only as dev fallback |
| Waitlist uses Supabase when env present | **PASS** | `getStore()` returns `supabaseStore` when `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` set |
| File fallback can't silently run in prod | **FIXED** | `persist()` now **throws** when `NODE_ENV=production` && no Supabase; `getStore()` logs a loud error; `/api/health` returns `ok:false`. No silent data loss. |
| Secrets not exposed to client | **PASS** | service-role key read only server-side in `store.ts`; never imported by a client component; `/api/health` returns booleans only |
| 42 MB installer not deployed/streamed | **PASS** | redirect-only; installer lives outside `websites/jarvis-landing` so it's not in the Vercel build |
| Multiple lockfiles / workspace root | **WARN** | `local_jarvis/package-lock.json` + the app's lockfile make Next infer the wrong root. **Mitigation:** set Vercel **Root Directory = `websites/jarvis-landing`** (in the deploy guide). |
| `vercel.json` present | **N/A** | not needed — Next.js auto-detected once Root Directory is set |

## Production safety behavior (verified by code + build)

- **With Supabase env:** `backend:"supabase"`, writes go to Postgres, `/api/health` → `ok:true`.
- **Without Supabase in production:** writes **throw** (register/waitlist fail with a clear
  error instead of writing to ephemeral disk), `getStore()` logs to Vercel, `/api/health` →
  `ok:false, persistence:"ephemeral"`. This makes a misconfiguration **loud, not silent.**
- **Local dev (NODE_ENV≠production):** file store works normally for testing.

## Required human action before go-live

1. Set Vercel **Root Directory = `websites/jarvis-landing`**.
2. Add env vars (Supabase keys, `AUTH_SECRET`, `ADMIN_EMAILS`, `NEXT_PUBLIC_*`); redeploy.
3. After the GitHub Release, set `ATLAS_INSTALLER_URL`; redeploy.
4. Verify `/api/health` → `backend:"supabase"` and a waitlist round-trip persists.

## Verdict: **VERCEL_READY (pending env configuration)**

Code and config are production-safe for Vercel free-tier. The only blockers are the four
human ops steps above — no code changes remain.
