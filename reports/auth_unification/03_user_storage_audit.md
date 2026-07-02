# 03 — User Storage Audit ("why can't Yoav find the users?")

**Date:** 2026-06-20. Code-grounded.

## Where website users are stored
- `app/_lib/store.ts` → `getStore()`: returns **`supabaseStore`** when `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` are set (`ENV.hasSupabase`), else **`fileStore`** (`.data/atlas-web.json`).
- `registerUser` → `store.create` → inserts into Supabase **`public.users`** (columns: id, email, name, password_hash, role, status, plan, plan_status, …). 
- **Production safety:** `persist()` (store.ts:118-129) **throws** in production if Supabase is absent — so a prod register with no Supabase **500s** (no silent file write).

## Where desktop users are stored
- **Frozen/packaged desktop → website mode** (`accounts_client.auth_mode()` returns `website`): register/login go to `/api/auth/desktop/*` → the **same Supabase `public.users`**. So production desktop users ARE in Supabase.
- **Source/dev desktop → local mode**: register/login go to the **local `accounts_service` → SQLite** (`accounts_service` data dir, e.g. `atlas_accounts.db`). **These users are NOT in Supabase** — separate identity.

## Why users are not appearing in Supabase (the three real causes, by likelihood)
1. **Vercel `SUPABASE_URL` points at the wrong/stale project.** Earlier production pointed at the dead `qfwmfllcqbngrowzbfpc` project; the current project is `wggjguqcxmskhjznexum`. If Vercel still has the old value (or the wrong project), registrations land in the **old project** (or fail) and are invisible when you look at the **new** project. **Check:** `GET /api/health` → `supabase.hostname` must be `wggjguqcxmskhjznexum.supabase.co`. If it shows another host, that's where the users went.
2. **The migrations weren't applied** to the project being queried — earlier symptom was "Could not find the table public.waitlist". If `public.users` doesn't exist on the queried project, inserts failed / went elsewhere.
3. **The user registered through a desktop in local mode** (a source/dev build) → the account is in the **local SQLite**, not Supabase.

## How to find them (exact)
- Confirm the live project: `GET https://<site>/api/health` → check `supabase.hostname`.
- In that Supabase project's SQL Editor: `select email, status, created_at from public.users order by created_at desc;`
- If empty there, check the OLD project (`qfwmfllcqbngrowzbfpc`) and any local desktop SQLite (`accounts_service` data dir).

## After this change
The website is **open access** (no approval). New registrations on the live site write to `public.users` with `status:"active"` and are immediately usable. The remaining "can't find users" risk is purely the **env/project-targeting** (cause #1/#2 — owner verifies via `/api/health` hostname), not approval gating.
