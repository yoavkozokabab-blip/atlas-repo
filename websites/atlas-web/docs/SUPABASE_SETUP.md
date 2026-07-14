# Atlas Website — Supabase Persistence Setup

The website funnel (email signups, accounts, login, billing state, admin) persists through a
single `Store` interface (`app/_lib/store.ts`). It selects a backend at runtime:

| Condition | Backend | Durability |
|---|---|---|
| `SUPABASE_URL` **and** `SUPABASE_SERVICE_ROLE_KEY` set | **Supabase** (PostgREST) | survives redeploys, restarts, serverless |
| otherwise | local JSON file | **ephemeral** — dev only, lost on Vercel |

No extra npm dependency is used — the adapter calls Supabase's PostgREST REST API with
`fetch` and the service-role key (server-side only; never exposed to the client).

## 1. Create the project & schema

1. Create a project at https://supabase.com (or use an existing one).
2. **SQL Editor → New query →** apply every file in `supabase/migrations/` in numeric order
   (`0001`, `0002`, then `0003`). (Or, with the Supabase CLI linked: `supabase db push`.)
   These migrations create the website, rate-limit, and analytics tables, enable RLS, and add
   **no** public policies — only the service role can read/write.

## 2. Configure environment variables

In **Vercel → Project → Settings → Environment Variables** (and `.env.local` for local):

| Var | Where to find it | Notes |
|---|---|---|
| `SUPABASE_URL` | Supabase → Project Settings → API → Project URL | e.g. `https://abc.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase → API → `service_role` secret | **server-only secret** — never client-exposed |
| `AUTH_SECRET` | `node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"` | stable sessions across redeploys |
| `ADMIN_EMAILS` | your admin email(s), comma-separated | grants admin dashboard + email signup export |

Redeploy after setting them (Vercel env changes need a new deployment).

## 3. Verify (do this after every deploy)

1. **Health probe** — `GET https://<your-domain>/api/health`:
   ```json
   { "ok": true, "backend": "supabase", "persistence": "ok", "config": { "hasSupabase": true, "hasAuthSecret": true } }
   ```
   `backend: "file"` or `persistence: "ephemeral"` in production = **NOT wired** — fix env vars.
   `persistence: "error"` = schema missing or bad key — re-run the migration / recheck the key.

2. **Email signup round-trip:** submit the Product updates form twice with the
   same test address. The first response must create a row and the second must
   report a duplicate. Confirm the row in Supabase. It must **survive a redeploy**.

3. **Account round-trip:** create an account at `/login`, redeploy, then log in again at `/login`.
   Success after a redeploy proves durable persistence (the old file backend would lose it).

4. **Admin export:** as an `ADMIN_EMAILS` user, download the email signup CSV.

## Rollback / dev

Unset `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` to fall back to the local file store
(dev only). Never run production on the file store — Vercel will silently lose data.

## Security posture

- Service-role key is read only on the server (`app/_lib/store.ts`); it is never imported
  into a client component and never returned by any route (including `/api/health`).
- RLS is enabled with no public policies, so a leaked anon key grants no data access.
- Passwords are scrypt-hashed (`app/_lib/auth.ts`); `password_hash` is never returned to
  the client (`toSafe()` strips it).
