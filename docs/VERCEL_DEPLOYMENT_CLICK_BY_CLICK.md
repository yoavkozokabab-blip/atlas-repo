# Vercel Deployment — Click-by-Click (for Yoav)

Deploy the Atlas landing on Vercel's **free** plan using the free `*.vercel.app` URL. No paid
domain required. ~10 minutes. Do this **after** Supabase setup (`docs/SUPABASE_CLICK_BY_CLICK.md`).

> Prereq: the repo is pushed to GitHub (the `local_atlas` repo, branch with this code).

---

## 1. Import the repo

1. Go to **https://vercel.com** → sign in with **GitHub**.
2. **Add New… → Project**.
3. Find your Atlas repo → **Import**. (If Vercel can't see it: **Adjust GitHub App
   Permissions** → grant access to the repo.)

## 2. Configure the project — THIS IS THE IMPORTANT PART

On the "Configure Project" screen:

| Setting | Value |
|---|---|
| **Root Directory** | **`websites/atlas-web`** ← click **Edit** and set this. Critical — the app is a subfolder. |
| **Framework Preset** | **Next.js** (auto-detected once Root Directory is set) |
| **Build Command** | leave default (`next build`) |
| **Output Directory** | leave default (Next.js managed — do **not** set `out`) |
| **Install Command** | leave default (`npm install`) |

> If you don't set **Root Directory** to `websites/atlas-web`, the build will fail or
> deploy the wrong thing — the repo has multiple folders and lockfiles.

## 3. Add environment variables

Still on the configure screen (or later under **Settings → Environment Variables**), add these
for the **Production** (and Preview) environment:

```
SUPABASE_URL               = https://<your>.supabase.co
SUPABASE_SERVICE_ROLE_KEY  = <service_role secret>     ← secret, server-only
SUPABASE_ANON_KEY          = <anon public>             ← optional
AUTH_SECRET                = <32-byte hex>             ← node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
ADMIN_EMAILS               = your-admin@example.com
NEXT_PUBLIC_ATLAS_VERSION  = 1.0.0
NEXT_PUBLIC_SUPPORT_EMAIL  = yoavkozokabab@gmail.com
ATLAS_INSTALLER_URL        = <leave empty for now; set after the GitHub Release>
```

`ATLAS_INSTALLER_URL` is added once you publish the installer
(`docs/GITHUB_RELEASE_CLICK_BY_CLICK.md`). Until then the download button returns a clear
"installer not available" message — not a crash.

## 4. Deploy

Click **Deploy**. Wait ~1–2 minutes. You'll get a URL like `https://atlas-web-xxxx.vercel.app`.

## 5. Redeploy after changing env vars

Env-var changes don't apply to existing deployments. After editing them:
**Deployments → latest → ⋯ → Redeploy** (uncheck "use existing build cache" if unsure).

## 6. Verify production

1. **Health:** open `https://<your-url>/api/health`. Want:
   ```json
   { "ok": true, "backend": "supabase", "persistence": "ok",
     "config": { "hasSupabase": true, "hasAuthSecret": true } }
   ```
   If `backend:"file"` → Root Directory or env vars wrong (and writes are now disabled in
   prod by design — see the readiness audit). Fix + redeploy.
2. **Account signup:** create a test account from the landing/download flow.
   Expect the success message; confirm the account row in **Supabase → Table Editor → users**.
   Resubmit the same email → duplicate-account message.
3. **Pages:** click through `/`, `/download`, `/pricing`, `/features`, `/faq`, `/login` — all
   should load.
4. **Download:** before the GitHub Release, the button shows the "create account / installer
   not available" path. After you set `ATLAS_INSTALLER_URL` + redeploy, a signed-in user's
   download 302-redirects to the GitHub asset.

## 7. Admin

Sign up with the email you put in `ADMIN_EMAILS`, then visit `/admin` (users + audit) and
`GET /api/admin/waitlist?format=csv` to export legacy email signups if needed.

---

### Notes
- The 42 MB installer is **never** deployed to Vercel or streamed through a function — it's
  hosted on GitHub Releases and the download route only redirects. The installer also lives
  outside `websites/atlas-web`, so it isn't part of the Vercel build.
- Free plan limits (bandwidth, function execution) are ample for the current launch.
