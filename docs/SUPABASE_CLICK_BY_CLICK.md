# Supabase — Click-by-Click Setup (for Yoav)

Goal: a free Supabase project that stores Atlas accounts + waitlist durably, so nothing is
lost when Vercel redeploys. ~10 minutes. **Never paste secrets into chat, git, or client code.**

---

## 1. Create the project

1. Go to **https://supabase.com** → **Sign in** (GitHub login is easiest).
2. Click **New project**.
3. **Organization:** pick or create one (free).
4. **Name:** `atlas` (anything).
5. **Database Password:** click **Generate a password**, then **copy it to your password
   manager**. (You won't need it for Atlas, but Supabase requires one.)
6. **Region:** choose the one closest to your users. If unsure, **East US (North Virginia)** —
   it's also closest to Vercel's default region, which keeps API latency low.
7. **Plan:** **Free**.
8. Click **Create new project** and wait ~2 minutes for it to provision.

## 2. Apply the database schema

1. In the left sidebar click **SQL Editor**.
2. Click **+ New query**.
3. Open the repo file **`websites/jarvis-landing/supabase/migrations/0001_init.sql`**, copy
   its **entire** contents, and paste into the editor.
4. Click **Run** (or Ctrl+Enter). You should see "Success. No rows returned."
5. Verify: left sidebar → **Table Editor** → you should now see 4 tables:
   **users, audit, reset_tokens, waitlist**.

This script also enables Row Level Security with **no public policies**, so only the secret
service-role key (used server-side) can read/write. That's intentional and secure.

## 3. Get your keys

Left sidebar → **Project Settings** (gear icon) → **API**. You'll need three values:

| Field on the page | Env var to set later | Secret? |
|---|---|---|
| **Project URL** (e.g. `https://abcd.supabase.co`) | `SUPABASE_URL` | no (but don't post it around) |
| **Project API keys → `anon` `public`** | `SUPABASE_ANON_KEY` | low-sensitivity |
| **Project API keys → `service_role` `secret`** | `SUPABASE_SERVICE_ROLE_KEY` | **YES — keep secret** |

> ⚠️ The **service_role** key bypasses all security rules. Only ever put it in Vercel's
> **Environment Variables** (server-side) or your local `.env.local` (gitignored). Never in
> client code, never in git, never in chat.

## 4. Where these go (set in Vercel — see the Vercel guide)

In **Vercel → your project → Settings → Environment Variables**, add:

```
SUPABASE_URL               = <Project URL>
SUPABASE_SERVICE_ROLE_KEY  = <service_role secret key>
SUPABASE_ANON_KEY          = <anon public key>          # optional, not used server-side yet
AUTH_SECRET                = <run the command below>
ADMIN_EMAILS               = yoavkozokabab@gmail.com    # your admin email(s), comma-separated
NEXT_PUBLIC_ATLAS_VERSION  = 0.1.0-beta
```

Generate `AUTH_SECRET` (stable login sessions across redeploys) — run locally:

```bash
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
```

Copy the long hex string it prints into `AUTH_SECRET`.

## 5. Test it works (`/api/health`)

After deploying with the vars set (Vercel guide), open in a browser:

```
https://<your-vercel-url>/api/health
```

You want to see:

```json
{ "ok": true, "backend": "supabase", "persistence": "ok",
  "config": { "hasSupabase": true, "hasAuthSecret": true } }
```

- `backend: "file"` or `persistence: "ephemeral"` → env vars not set / not redeployed. Fix and
  redeploy.
- `persistence: "error"` → the migration didn't run, or the service-role key is wrong. Re-run
  step 2 / re-copy the key.

Then submit the waitlist form on the site once, and confirm a row appears in
**Table Editor → waitlist**. It must still be there after a redeploy — that proves durability.

## Local testing (optional)

Create `websites/jarvis-landing/.env.local` (gitignored) with the same vars to run the
production backend locally: `npm run dev`, then open `http://localhost:3000/api/health`.

---

### Repo state (verified 2026-06-16)
- `supabase/migrations/0001_init.sql` ✅ exists, 4 tables (users, audit, reset_tokens, waitlist) + RLS.
- `.env.example` ✅ documents all required vars (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY,
  SUPABASE_ANON_KEY, AUTH_SECRET, ADMIN_EMAILS, ATLAS_INSTALLER_URL, NEXT_PUBLIC_*).
