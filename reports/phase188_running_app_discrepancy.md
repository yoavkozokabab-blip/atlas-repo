# Phase 188 — Running App Did Not Match Reports (Root Cause + Fix)

**Date:** 2026-06-08

## Symptom (reported from the live UI)

- Create Account showed only email / password / confirm — the beta profile
  onboarding form was missing.
- Pre-auth navigation (Home, Scan, Codebase Map, Change Plan, Debug, What Breaks,
  Account, repo chips) was still visible.
- A raw message appeared: *"Accounts service is not running. Start it with:
  python -m accounts_service.main"* — a Python command shown to a beta user.

## 1. Root cause

**The running application was a stale packaged build that predated Phase 188.**

- Phase 188 (commit `8441798c8`) only modified the **source** static files
  (`jarvis_desktop/static/*`). It never rebuilt the PyInstaller bundle.
- The packaged bundle (`dist/Atlas/…`) and the installer **staging** were last
  produced at Phase 187 (`b14334281`), **before** Phase 188 existed.
- The previous "installer rebuild" only recompiled the Inno `.iss` wrapper around
  that **same Phase-187 staging payload** — it never re-ran PyInstaller, so the
  installer also lacked Phase 188.
- The user was running the installed app
  `C:\Users\babi2\AppData\Local\Programs\Atlas\Atlas.exe` (port 8777), whose
  static bundle was pre-188 — hence no beta form, visible nav, and the raw error.

Evidence (Phase 188 markers — `1` = present):

| File | auth-layout | beta profile | verdict |
|---|---|---|---|
| `jarvis_desktop/static/index.html` (source) | 1 | 1 | Phase 188 present |
| `dist/Atlas/_internal/.../index.html` (packaged, before fix) | 0 | 0 | **stale (pre-188)** |
| `packaging/installer/staging/.../index.html` (installer, before fix) | 0 | 0 | **stale (pre-188)** |
| installed `…\Programs\Atlas\…\index.html` | 0 | 0 | **stale (pre-188)** |

A second, separate bug: `jarvis_desktop/accounts_routes.py` returned the literal
string `python -m accounts_service.main` on the offline path (register and a
similar login path) — a Python command that should never reach a beta user.

## 2. Exact files served by the running application

`C:\Users\babi2\AppData\Local\Programs\Atlas\_internal\jarvis_desktop\static\`
— `index.html`, `app.js`, `atlas_accounts.js`, `styles.css` (all pre-Phase-188),
served by `…\Programs\Atlas\Atlas.exe` on `127.0.0.1:8777`.

## 3. Was Phase 188 actually active?

- **In source:** yes — fully implemented and wired (verified; 188+189 tests pass).
- **In the running/installed app:** **no** — it served a pre-188 static bundle.

## 4. Did the installer contain Phase 188?

- **Before this fix:** **no** — the installer staging was the Phase-187 payload.
- **After this fix:** **yes** — see below.

## Fix

1. **Removed the Python command** from `jarvis_desktop/accounts_routes.py`
   (register + login offline paths) — now: *"The Atlas accounts service isn't
   available right now. Please restart Atlas, and contact support@useatlas.dev if
   this keeps happening."*
2. **Rebuilt the PyInstaller bundle** (`dist/Atlas`) from current source via
   `build_atlas_exe.ps1` → the package now contains Phase 188 + 189 + the fix.
3. **Rebuilt the installer** from the fresh `dist/` (`installer_build.ps1
   -SkipPackage`) → staging and `Atlas_Setup.exe` now contain Phase 188, while
   retaining the running-application update flow.

### Verification of the rebuilt **packaged** build

Ran the rebuilt `dist/Atlas/Atlas.exe` (`--no-browser --port 8810`) and captured:

| Screenshot | Proves |
|---|---|
| `reports/phase188_fix_verification/01_signed_out.png` | Signed out: only Atlas branding + centered auth card (Sign in, Create Account, Help/Support). App shell **hidden** (`#app-shell` computed `display: none`, `body.auth-mode`). No repo chips, scan controls, workflow tabs, or Python commands. |
| `reports/phase188_fix_verification/02_create_account_beta_profile.png` | Create Account: full **beta profile onboarding** form ("Apply for beta access" + developer status, intended use, company name/size, experience, primary role, repo size, languages, notes). 8/8 beta fields present. |

Rebuilt artifacts:

| Artifact | Value |
|---|---|
| `dist/Atlas/_internal/.../index.html` | auth-layout: 1, beta profile: 1 (Phase 188 present) |
| `packaging/installer/staging/.../index.html` | auth-layout: 1, beta profile: 1 (Phase 188 present) |
| Installer | `packaging/installer/output/Atlas_Setup.exe` (mirror `installer/output/Atlas_Setup.exe`) |
| Installer size | 12,244,928 bytes (11.68 MB) |
| Installer SHA256 | `863B33167E5245CA73CA23AA7091FCE08022E1144045A3349BEC59E1E012F038` |
| Tests | 29 passed (Phase 188 + 189 suites) |

## Operator note

The user's currently-installed copy under `…\Programs\Atlas` must be **updated by
re-running the rebuilt `Atlas_Setup.exe`** (the new installer detects the running
Atlas and closes it first, per the running-application update flow). After
reinstall, the signed-out screen and create-account beta profile form match the
Phase 188 implementation.

## Verdict

Root cause was a stale packaged/installer bundle (PyInstaller never rebuilt after
Phase 188). The bundle and installer have been rebuilt and now contain Phase 188
(+189), the Python-command leak is removed, and the rebuilt packaged build's
signed-out and create-account screens match the implemented design (screenshots
above).
