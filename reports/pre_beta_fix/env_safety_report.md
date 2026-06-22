# TASK 1 — Env Safety / Stale Supabase Prevention

**Date:** 2026-06-20. Code-only hardening (no auth/retrieval/billing logic touched).

## Search results (whole repo)
- `qfwmfllcqbngrowzbfpc` / `wggjguqcxmskhjznexum` in **tracked code**: **none** (only in this session's report docs). The stale id lives only in the gitignored `websites/jarvis-landing/.env.local` (operator-local, not deployed/committed).
- Hardcoded `supabase.co` URLs / fallbacks in source: **none**. The only `supabase.co` occurrences are the validator's host check (`_lib/config.ts:100`) and a docstring (`_lib/store.ts:227`).
- Env vars consumed: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (raw PostgREST + service role — `store.ts:231/237`, `ratelimit.ts:30/35`, `config.ts:40`). **`NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY` / `createClient` are NOT consumed anywhere.**

## State of the hardening (already in place + verified this pass)
- **No silent stale fallback:** the only URL fallback is `(process.env.SUPABASE_URL || "")` — empty string, which fails rather than pointing at another project. No `|| "https://…"` / `?? "https://…"` exists.
- **Fail-loud on prod misconfig:** `store.ts persist()` throws in production when Supabase is absent (`store.ts:118-129`); `getStore()` logs to Vercel and disables writes. `/api/health` returns **503** in prod when persistence isn't `ok`.
- **Exactly env-provided in prod:** the URL comes solely from `process.env.SUPABASE_URL`, read per-request (runtime), never hardcoded.
- **Dev-only file store:** file store is used only when Supabase env is absent; writes via it are blocked in production (the throw above), so it is effectively dev-only.
- **Format validator (no hardcoded project):** `validateSupabaseConfig()` (`_lib/config.ts`) checks URL present + parseable + `*.supabase.co` host, and exposes the hostname. `assertSupabaseConfigured()` throws a clear, secret-free message. No project id is hardcoded — drift is caught by surfacing the hostname.

## /api/health diagnostic (no secrets — booleans + hostname)
```json
"backend": "supabase|file",
"persistence": "ok|error|ephemeral",
"supabase": {
  "supabase_url_present": bool,
  "anon_key_present": bool,
  "service_role_present": bool,
  "hostname": "<project>.supabase.co",
  "validation_passed": bool
}
```
**Verified live:** against the stale `.env.local`, `/api/health` returns `persistence:"error"`, `detail:"fetch failed"`, `supabase.hostname:"qfwmfllcqbngrowzbfpc.supabase.co"` — the wrong project is now named explicitly instead of an opaque 500. Against a correct project it returns `persistence:"ok"`, the right hostname, `validation_passed:true`.

## What an operator does to catch drift
Hit `/api/health` after deploy → if `supabase.hostname` ≠ `wggjguqcxmskhjznexum.supabase.co` or `persistence:"error"`, the env is drifted. (Format validation can't detect a *valid-but-wrong* project — the hostname field is the human check; that's intentional, to avoid hardcoding the project in code.)

## Conclusion
No code change was needed to *remove* a stale fallback (none existed). The hardening (validator + health diagnostic + existing fail-loud persist) is in place and verified. The actual stale value is in Vercel env + local `.env.local` → **owner fix** (see `vercel_env_owner_guide.md`).
