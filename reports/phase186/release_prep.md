# ATLAS — RELEASE PREPARATION (free invite beta)

**Date:** 2026-06-20 · Repo `yoavkozokabab-blip/atlas-repo` · Installer commit `f70a4975e`

---

## 1. Installer target URL — VERIFIED

Extracted from the **frozen `Atlas.exe`** (compiled `accounts_client`, not just source):

| Function | Baked value | Meaning |
|---|---|---|
| `web_base()` | **`https://useatlas.dev`** | The website auth authority the desktop uses (website mode = frozen default) |
| `<module>` `_SERVICE_BASE` | `http://127.0.0.1:8788` | **Dormant** local-service fallback; used only if `ATLAS_AUTH_MODE=local`/`ATLAS_DEV=1`. Not the frozen app's target. |

**Conclusion:** target = `https://useatlas.dev` (not localhost, not stale). **No rebuild required.**
**Gate:** do **not** publish/announce until `useatlas.dev` resolves to the Vercel production deployment.

---

## 2. GitHub Release payload (exact)

| Field | Value |
|---|---|
| Repo | `yoavkozokabab-blip/atlas-repo` |
| Tag | `v0.1.0-beta` |
| Title | `Atlas 0.1.0-beta` |
| Files to upload | `packaging/installer/output/Atlas_Setup.exe`<br>`packaging/installer/output/Atlas_Setup.exe.sha256` |
| SHA256 | `bc2a3e60113e74400d44d99c3548662e94739ec6074860482a116e6edb30cc6e` |
| Prerelease | yes (beta) |

**Command:**
```powershell
cd C:\J.A.R.V.I.S\local_jarvis
gh release create v0.1.0-beta `
  packaging\installer\output\Atlas_Setup.exe `
  packaging\installer\output\Atlas_Setup.exe.sha256 `
  --repo yoavkozokabab-blip/atlas-repo `
  --prerelease --title "Atlas 0.1.0-beta" --notes-file packaging\installer\RELEASE_NOTES.md
```

**Release notes (verbatim):**
```
Atlas 0.1.0-beta — free invite beta

Local-first repository intelligence for AI coding agents (Claude, Cursor, Codex).
Free during the invite beta — no payment, no card, nothing to buy.

Windows installer (64-bit). Self-contained — no Python required.

SHA256 (Atlas_Setup.exe):
bc2a3e60113e74400d44d99c3548662e94739ec6074860482a116e6edb30cc6e

Verify before installing (PowerShell):
  (Get-FileHash Atlas_Setup.exe -Algorithm SHA256).Hash

Note: this build is UNSIGNED, so Windows SmartScreen will show an
"unknown publisher" warning on first run — choose More info → Run anyway.
A code-signed build will follow.
```
> The `gh` command embeds the SHA256 in the notes anyway; the `--notes-file` above is optional — you can instead pass `--notes "<text>"`.

**Expected asset URL after publishing** (needed for §3 `ATLAS_INSTALLER_URL`):
`https://github.com/yoavkozokabab-blip/atlas-repo/releases/download/v0.1.0-beta/Atlas_Setup.exe`

---

## 3. Vercel environment variables (Production) — final list

| Variable | Value / source | Secret? | Notes |
|---|---|---|---|
| `SUPABASE_URL` | Supabase project URL | no | from your Supabase project |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase **service_role** key | **YES** | server-only; never expose |
| `AUTH_SECRET` | 32+ random bytes | **YES** | generate: `node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"` |
| `ADMIN_EMAILS` | your admin email(s), comma-separated | no | grants admin role |
| `ATLAS_INSTALLER_URL` | the §2 asset URL | no | set **after** the Release exists, then redeploy |
| `BETA_MODE` | `invite` (recommended) or `open` | no | `invite` = allowlist-gated; `open` = anyone who signs up |
| `BETA_ALLOWLIST` | comma-separated emails | no | **required only if** `BETA_MODE=invite` |
| `NEXT_PUBLIC_SUPPORT_EMAIL` | your support email | no | shown on contact/support |
| `NEXT_PUBLIC_ATLAS_VERSION` | `0.1.0-beta` | no | display only |
| `NEXT_PUBLIC_PAID_PLANS` | **DO NOT SET** | — | leaving it unset keeps paid CTAs hidden (free beta). Setting `1` re-enables paid UI — do not. |

```powershell
cd C:\J.A.R.V.I.S\local_jarvis\websites\jarvis-landing
vercel env add SUPABASE_URL production
vercel env add SUPABASE_SERVICE_ROLE_KEY production
vercel env add AUTH_SECRET production
vercel env add ADMIN_EMAILS production
vercel env add BETA_MODE production            # invite
vercel env add BETA_ALLOWLIST production       # only if BETA_MODE=invite
vercel env add NEXT_PUBLIC_SUPPORT_EMAIL production
vercel env add NEXT_PUBLIC_ATLAS_VERSION production
# ATLAS_INSTALLER_URL added in step 5 of the checklist (after the Release exists)
```

---

## 4. Owner checklist (owner actions only, in order)

1. **Connect domain** — in Vercel project → Settings → Domains, add `useatlas.dev`; set the DNS records Vercel shows (A/ALIAS or CNAME) at your registrar. Wait for "Valid Configuration".
2. **Provision Supabase** — run `supabase/migrations/0001_init.sql` then `0002_rate_limits.sql`; copy URL + service_role key.
3. **Set env** — add all §3 variables (except `ATLAS_INSTALLER_URL`).
4. **Deploy** — `vercel deploy --prod`. Confirm `https://useatlas.dev/api/health` → `backend: "supabase"`.
5. **Upload release** — run the §2 `gh release create`; copy the asset URL.
6. **Update installer URL** — `vercel env add ATLAS_INSTALLER_URL production` (the §2 URL) → `vercel deploy --prod`. Confirm `/download/atlas` → 302 to the asset.
7. **Production smoke test** — register + login on the live site; download installer; verify its SHA256 == `bc2a3e60…`; run `ATLAS_AUTH_MODE=website ATLAS_WEB_URL=https://useatlas.dev py -3 scripts\desktop_web_auth_smoke.py`.
8. **Clean-machine test** — fresh Windows VM: install, note SmartScreen, sign up on site → log in inside Atlas; connect Claude Desktop (`Atlas.exe --mcp`) and confirm a tool call; repeat for Cursor/Codex.

---

## 5. Launch-readiness gate (NOT to be claimed until all pass)

- [ ] `useatlas.dev` resolves to the deployed website
- [ ] `/api/health` passes in production (`backend: supabase`)
- [ ] website register / login / download works in production
- [ ] downloaded installer is the rebuilt one (SHA256 `bc2a3e60113e74400d44d99c3548662e94739ec6074860482a116e6edb30cc6e`)
- [ ] desktop login works against production
- [ ] Claude Desktop sees Atlas running
- [ ] Claude calls at least one Atlas tool

Until every box is checked, status = **NOT launch-ready**.
