# ATLAS — OWNER-RUN BETA SETUP GUIDE

**Date:** 2026-06-20 · Branch `monetization-v1` · Scope: **free invite beta** (no Stripe).
Run everything from an **elevated PowerShell** on the build machine unless noted.

> **Status from this session:** the installer has already been **rebuilt from HEAD and verified** here (steps 3–4 below are DONE). PyInstaller and Inno Setup are present in the workspace. What remains is owner-only: install `gh`, provision Supabase + Vercel env, create the GitHub Release, set `ATLAS_INSTALLER_URL`, and run clean-machine validation.

---

## Current verified build (this session)

| Item | Value |
|---|---|
| Installer | `packaging/installer/output/Atlas_Setup.exe` (44 MB, **unsigned**) |
| Built from commit | `f70a4975e` (HEAD; `e06b62bed` rewire is an ancestor — **≥ requirement met**) |
| `build_info.json` | `{"commit":"f70a4975e","version":"0.1.0-beta","build_date":"2026-06-20T16:21:14"}` |
| **SHA256** | `bc2a3e60113e74400d44d99c3548662e94739ec6074860482a116e6edb30cc6e` |
| Rewire bundled? | **Proven** — frozen exe's compiled `accounts_client` contains `/api/auth/desktop/{login,logout,me,register}`, the `website` mode, and `auth_mode/web_base/verify_session` |
| Supersedes | stale 06-18 build `e5dad2121b31f9116ccc7e6046454b6cd7ad609b155b7331becf699bd8dee6a7` — **do not ship the old one** |

---

## ⚠️ Ordering (read first)
The desktop's auth target is `web_base()` in `jarvis_desktop/accounts_client.py`, default **`https://useatlas.dev`**. A frozen exe reads no shell env, so that default must equal the live site. Correct order: **Supabase → Vercel deploy → confirm live URL → make `web_base()` match it → (re)build installer → release → set `ATLAS_INSTALLER_URL`**. If you launch on `useatlas.dev`, the current build is already correct. If you launch on a `*.vercel.app` URL, edit the default and rebuild (step 3).

---

## 1. Tooling

PyInstaller and Inno Setup are **already in this workspace** (`.phase152_packaging_lib\PyInstaller`, `.phase150_inno\ISCC.exe`) — no install needed on *this* machine. For a fresh machine, or to install globally:

```powershell
# PyInstaller (workspace-local, the way the build script expects):
py -3 -m pip install --target .phase152_packaging_lib pyinstaller PyYAML

# Inno Setup 6 — GUI installer (no winget guarantee): https://jrsoftware.org/isdl.php
#   installs ISCC.exe to "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (build script finds it)

# GitHub CLI (NOT present here — required for the Release):
winget install --id GitHub.cli -e
#   or download: https://cli.github.com
gh --version
```

## 2. Supabase + Vercel env

**Supabase:** create a project → SQL Editor → run, in order:
`websites/jarvis-landing/supabase/migrations/0001_init.sql`, then `0002_rate_limits.sql`.
Copy the **project URL** and the **service_role** key.

**Vercel** (from `websites/jarvis-landing`):
```powershell
cd C:\J.A.R.V.I.S\local_jarvis\websites\jarvis-landing
vercel link                                   # link or create the project
vercel env add AUTH_SECRET production          # paste 32+ random bytes
vercel env add SUPABASE_URL production         # Supabase project URL
vercel env add SUPABASE_SERVICE_ROLE_KEY production
vercel env add NEXT_PUBLIC_SUPPORT_EMAIL production
vercel env add ADMIN_EMAILS production         # your admin email(s), comma-separated
vercel env add NEXT_PUBLIC_ATLAS_VERSION production   # 0.1.0-beta
# Leave NEXT_PUBLIC_PAID_PLANS UNSET → paid CTAs stay hidden (free beta).
# Optional invite gating (default = open beta):
#   vercel env add BETA_MODE production         # invite
#   vercel env add BETA_ALLOWLIST production     # comma-separated emails
vercel deploy --prod
```
**Verify:** `https://<site>/api/health` returns `backend: "supabase"`; signup + waitlist persist; `/pricing` shows "Join the beta" (no `$29`, no checkout).

## 3. Rebuild installer from HEAD  *(already done this session — rerun only if source/URL changed)*
```powershell
cd C:\J.A.R.V.I.S\local_jarvis
# If launching on a non-useatlas.dev URL, first set the desktop auth target:
#   edit jarvis_desktop/accounts_client.py → web_base() default = your live URL, commit.
git rev-parse --short HEAD                      # note the commit you're building
powershell -ExecutionPolicy Bypass -File packaging\installer\installer_build.ps1
```
This runs PyInstaller (builds `Atlas.exe` + `AtlasAccounts.exe`) and ISCC, producing `packaging\installer\output\Atlas_Setup.exe`.

**Regenerate the checksum sidecar** (the build script does not):
```powershell
cd packaging\installer\output
(Get-FileHash Atlas_Setup.exe -Algorithm SHA256).Hash.ToLower() + "  Atlas_Setup.exe" | Out-File -Encoding ascii Atlas_Setup.exe.sha256
```

## 4. Verify the build is current (commit ≥ e06b62bed)
```powershell
cd C:\J.A.R.V.I.S\local_jarvis
Get-Content packaging\installer\build_info.json          # "commit" must be your HEAD, NOT ce5f73805
git merge-base --is-ancestor e06b62bed HEAD; "ancestor_ok=$($LASTEXITCODE -eq 0)"
```
Optional definitive proof the rewire is inside the frozen exe:
```powershell
$env:PYTHONIOENCODING="utf-8"; $env:PYTHONPATH=".phase152_packaging_lib"
py -3 -c "import marshal,os,tempfile;from PyInstaller.archive.readers import CArchiveReader,ZlibArchiveReader;c=CArchiveReader('dist/Atlas/Atlas.exe');d=c.extract('PYZ.pyz')[1];p=os.path.join(tempfile.gettempdir(),'p.pyz');open(p,'wb').write(d);a=ZlibArchiveReader(p);co=marshal.loads(a.extract('jarvis_desktop.accounts_client')[1]);s=[];[s.append(k) if isinstance(k,str) else None for k in co.co_consts];print('has desktop auth:', any('/api/auth/desktop' in x for x in s))"
```
Current session result: `commit = f70a4975e`, `ancestor_ok=True`, `has desktop auth: True`. ✅

## 5. Create the GitHub Release
```powershell
gh auth login                                   # one-time
cd C:\J.A.R.V.I.S\local_jarvis
gh release create v0.1.0-beta `
  packaging\installer\output\Atlas_Setup.exe `
  packaging\installer\output\Atlas_Setup.exe.sha256 `
  --repo yoavkozokabab-blip/atlas-repo `
  --title "Atlas 0.1.0-beta" `
  --notes "Free invite beta. Unsigned build — Windows SmartScreen will warn on first run. SHA256: bc2a3e60113e74400d44d99c3548662e94739ec6074860482a116e6edb30cc6e"
```
Copy the asset download URL from the release page.

## 6. Update ATLAS_INSTALLER_URL + redeploy
```powershell
cd C:\J.A.R.V.I.S\local_jarvis\websites\jarvis-landing
vercel env add ATLAS_INSTALLER_URL production   # paste the release asset URL
vercel deploy --prod
```
**Verify:** `https://<site>/download/atlas` → 302 to the release asset; downloaded file's SHA256 matches step 4.

## 7. Clean-machine validation (your final gate)
On a fresh Windows 11 VM (snapshot first; no Python, no Node, no repo):
1. Download `Atlas_Setup.exe` from the live `/download/atlas`; **record SmartScreen** (expected: unsigned warning). Verify SHA256 matches.
2. Install (lowest-privilege); confirm shortcuts + launch; run in-app: scan, context generation, export.
3. **Identity:** sign up on the live website → log in *inside Atlas* with the same account → confirm it works (this is the unified-identity proof on real Supabase). Optionally run from a dev box pointed at prod: `ATLAS_AUTH_MODE=website ATLAS_WEB_URL=https://<site> py -3 scripts\desktop_web_auth_smoke.py`.
4. **Claude Desktop:** add Atlas (`Atlas.exe --mcp`) per `docs/MCP_CLIENT_SETUP.md`; confirm tools visible + callable + analysis returns results.
5. **Cursor / Codex:** configure Atlas MCP; confirm exports + a task workflow.
6. **Failure cases:** corrupt MCP config, kill network, corrupt auth token → expect graceful messages, no crash.

---

## Go / No-Go gates before inviting users
- [x] Installer built from HEAD (`f70a4975e` ≥ `e06b62bed`), rewire proven inside the exe
- [x] SHA256 generated + sidecar matches (`bc2a3e60…`)
- [ ] Supabase provisioned; `/api/health` → `backend: supabase`
- [ ] Vercel deployed; paid CTAs hidden; signup/waitlist persist
- [ ] `web_base()` default == live URL (or `useatlas.dev` DNS → Vercel)
- [ ] GitHub Release published; `/download/atlas` serves it; checksum matches
- [ ] Clean-machine: signup→desktop login, Claude/Cursor/Codex MCP all pass
- [ ] Invitees warned about SmartScreen (installer unsigned — code-signing cert still outstanding)

**Do not claim launch readiness until the rebuilt installer is downloaded from the live site AND the live Vercel/Supabase signup→desktop-login flow passes on a clean machine.**
