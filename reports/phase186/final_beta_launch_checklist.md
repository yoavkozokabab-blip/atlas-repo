# ATLAS — FINAL BETA-LAUNCH CHECKLIST

**Date:** 2026-06-20 · Branch `monetization-v1` · HEAD `e06b62bed` · Scope: **free invite beta**

---

## 0. What this session attempted, and the honest outcome

You asked me to build the installer, generate SHA256, create the GitHub Release, deploy to Vercel, and produce this checklist. I probed the environment first. **Four of the five are blocked on tooling/credentials that are not present here**, and shipping the *existing* installer would be misleading. I will not fabricate any of them. Real results:

| Task | Result | Why |
|---|---|---|
| Build latest installer | **DONE (2026-06-20)** | **Correction:** PyInstaller + Inno Setup are present in the workspace (`.phase152_packaging_lib`, `.phase150_inno`) — my first probe only checked global installs. Rebuilt from HEAD `f70a4975e`; ISCC "Successful compile". Frozen exe **proven** to contain the `/api/auth/desktop/*` rewire. |
| Generate SHA256 | **DONE (current build)** | New `Atlas_Setup.exe` = `bc2a3e60113e74400d44d99c3548662e94739ec6074860482a116e6edb30cc6e` (sidecar regenerated + verified). Supersedes the stale 06-18 `e5dad2…` build (do not ship that one). |
| Create GitHub Release | **BLOCKED** | `gh` CLI not installed and no API token available. (Remote exists: `github.com/yoavkozokabab-blip/atlas-repo`.) Also moot until a *current* installer exists. |
| Deploy website to Vercel | **BLOCKED (won't ship broken)** | Vercel CLI present and you are logged in (`yoavkozokabab-8018`), but the project is **not linked** and **no Supabase env is set** — a deploy would build yet return 500 on signup/login/waitlist (the prod data-loss guard). Deploying a broken-auth site is not a beta launch. |
| Final checklist | **DONE** | This document. |

**Bottom line:** the *code* for the free beta is complete and verified (identity unified, paid CTAs honest, security fixed — see `security_verification.md`, `identity_architecture.md`). The *release/deploy* is gated on owner tooling + provisioning below.

---

## 1. Critical ordering note (read before building)

There is a dependency loop: **the desktop's auth target is `web_base()` in `accounts_client.py`, which defaults to `https://useatlas.dev`.** A frozen exe reads no shell env, so that default (or a baked value) MUST equal the live site URL. Therefore the correct order is **provision → deploy → learn the URL → set it → build installer → release.**

If you launch on a `*.vercel.app` URL (no custom domain yet), either:
- point `useatlas.dev` DNS at Vercel (so the default is correct), **or**
- edit the `web_base()` default in `jarvis_desktop/accounts_client.py` to the live URL and rebuild.

---

## 2. Owner steps (exact commands, in order)

### Step A — Provision Supabase
1. Create a Supabase project.
2. SQL Editor → run `websites/jarvis-landing/supabase/migrations/0001_init.sql` then `0002_rate_limits.sql`.
3. Copy the project URL and the **service_role** key.

### Step B — Deploy the website to Vercel
```bash
cd C:/J.A.R.V.I.S/local_jarvis/websites/jarvis-landing
vercel link                       # link/create the project (interactive)
# Set env (Production). Do NOT set NEXT_PUBLIC_PAID_PLANS — free beta keeps paid OFF.
vercel env add AUTH_SECRET production              # 32+ random bytes
vercel env add SUPABASE_URL production             # from Step A
vercel env add SUPABASE_SERVICE_ROLE_KEY production
vercel env add NEXT_PUBLIC_SUPPORT_EMAIL production
vercel env add ADMIN_EMAILS production             # your admin email(s)
vercel env add NEXT_PUBLIC_ATLAS_VERSION production # 0.1.0-beta
# Optional invite gating (default is open beta):
#   vercel env add BETA_MODE production            # "invite"
#   vercel env add BETA_ALLOWLIST production        # comma-separated emails
vercel deploy --prod
```
Then verify: `GET https://<site>/api/health` must report `backend: "supabase"`. Test signup + waitlist persist.

### Step C — Build the installer (needs two installs)
```powershell
# 1. Install Inno Setup 6  → https://jrsoftware.org/isdl.php  (GUI installer)
# 2. Install PyInstaller:
py -3 -m pip install pyinstaller
# 3. Ensure the desktop auth target matches the live site (see §1), then build:
cd C:\J.A.R.V.I.S\local_jarvis
powershell -ExecutionPolicy Bypass -File packaging\installer\installer_build.ps1
```
**Verify the build is current:** `packaging/installer/build_info.json` `commit` must equal the HEAD you built (`e06b62bed` or later) — **not** `ce5f73805`. Confirm the bundled rewire is present:
```bash
grep -c "api/auth/desktop" packaging/installer/staging/_internal/jarvis_desktop/accounts_client.py   # must be > 0
```
SHA256 is written to `packaging/installer/output/Atlas_Setup.exe.sha256`.

### Step D — GitHub Release
```bash
# Install gh (https://cli.github.com), then:
gh auth login
cd C:/J.A.R.V.I.S/local_jarvis
gh release create v0.1.0-beta \
  packaging/installer/output/Atlas_Setup.exe \
  packaging/installer/output/Atlas_Setup.exe.sha256 \
  --repo yoavkozokabab-blip/atlas-repo \
  --title "Atlas 0.1.0-beta" --notes "Free invite beta. Unsigned build — SmartScreen will warn."
```
Copy the asset download URL.

### Step E — Wire the download + redeploy
```bash
cd C:/J.A.R.V.I.S/local_jarvis/websites/jarvis-landing
vercel env add ATLAS_INSTALLER_URL production     # the asset URL from Step D
vercel deploy --prod
```
Verify `GET /download/atlas` → 302 to the release asset.

---

## 3. Pre-flight verification (already PASS this session)

- Identity unified (desktop ↔ website, one Supabase store) — `desktop_web_auth_smoke.py` 13/13, dead-port independence proof.
- No fake billing in UI — home/pricing "Join the beta", `/checkout`→/pricing, `/api/checkout`→403, account/billing "Free beta".
- Security — enumeration leak fixed, rate limiting serverless-safe (`security_verification.md`).
- Tests — 152 desktop+accounts pass; website `tsc` + `build` clean; MCP smoke green.

## 4. Go / No-Go gates before inviting users

- [x] `build_info.json.commit` ≥ `e06b62bed` (installer contains phase186A) — **DONE**: `f70a4975e`, rewire proven inside the exe. See `owner_setup_guide.md`.
- [ ] `web_base()` default == live site URL (or DNS points there)
- [ ] `/api/health` reports `backend: "supabase"`
- [ ] Signup on the live site → desktop login works (repeat the smoke against the live URL)
- [ ] `/download/atlas` serves the released installer; SHA256 matches
- [ ] SmartScreen behavior documented for invitees (installer is **unsigned** — code-signing cert still outstanding)
- [ ] Clean-machine validation with Claude / Cursor / Codex — **your next step**

## 5. Known limitations carried into beta (non-blocking, be transparent)
- Installer **unsigned** → SmartScreen "unknown publisher" warning.
- Web session has no server-side revocation (7-day token) — acceptable for beta.
- No remote crash/error tracking — diagnosis via manual support bundle.
- Paid plans intentionally OFF (`PAID_PLANS_ENABLED` unset); Stripe not implemented (186B deferred).
