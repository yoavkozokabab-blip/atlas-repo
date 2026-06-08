# Phase 192 — Frozen Accounts Service Packaging

**Date:** 2026-06-08
**Scope:** Remove the packaging blocker only. No feature or UX changes.

## Problem

Installed users (frozen build) could launch the Atlas desktop UI but the
**accounts service never started**, so register / login / beta onboarding / admin
review were all unreachable. Verdict was NO-GO.

## Investigation

### 1. How the accounts service is launched today

`jarvis_desktop/server.py` calls `accounts_service_runner.ensure_running_async()`
on boot. `accounts_service_runner.start_accounts_service()` spawned:

```python
subprocess.Popen([sys.executable, "-m", "accounts_service.main"], ...)
```

### 2. Why `sys.executable` fails in frozen mode

In a PyInstaller build, `sys.executable` is **`Atlas.exe`**, not a Python
interpreter. `Atlas.exe -m accounts_service.main` is meaningless — Atlas.exe
launches the desktop, it cannot run a module. There is also no Python on the
user's machine. So the subprocess either no-ops or relaunches the desktop, and
nothing ever binds `127.0.0.1:8788`.

### 3. Which dependencies were missing from the bundle

`packaging/pyinstaller/atlas.spec` **excluded** `fastapi`, `uvicorn`,
`starlette`, and never bundled `accounts_service` or its vendored deps
(`accounts_service/.lib`: pydantic, pydantic_core, sqlalchemy, greenlet, bcrypt,
passlib, jwt, email_validator, anyio, h11, click, …). The accounts service code
and its entire dependency tree were absent from the frozen app.

### 4. Architecture options considered

| Option | Verdict |
|---|---|
| Bundle accounts service **inside Atlas.exe** (uvicorn in a thread) | Pollutes the working desktop import graph with FastAPI; threads uvicorn into the desktop process; higher risk to a known-good build. |
| **Separate frozen executable** (`AtlasAccounts.exe`) launched by Atlas.exe | **Chosen.** Preserves the existing two-process HTTP architecture exactly (desktop ⇄ service over `:8788`); only the *spawn target* changes. Isolated, low-risk, easy to verify. |
| Background Windows service | Over-engineered for a local desktop beta; needs install-time service registration and elevation. |

## Chosen architecture

A dedicated **`AtlasAccounts.exe`** (its own PyInstaller one-folder bundle,
including FastAPI/uvicorn/starlette/pydantic/sqlalchemy/bcrypt from the vendored
`.lib`) is shipped inside the Atlas install folder under `accounts\`. On boot,
`Atlas.exe`'s runner detects frozen mode and spawns
`{app}\accounts\AtlasAccounts.exe` — no Python, no terminal, no manual setup.

The service writes its SQLite DB + JWT secret to a **per-user writable**
directory (`{desktop_data_dir}/accounts_service`) so it works even under a
read-only install location.

### Files bundled / added

- `packaging/pyinstaller/accounts_entry.py` — frozen entry (sets a writable data
  dir, runs `uvicorn accounts_service.main:app` on `:8788`).
- `packaging/pyinstaller/accounts.spec` — one-folder spec; `collect_all` for the
  FastAPI/uvicorn/pydantic/sqlalchemy/bcrypt stack from `.lib`.
- `jarvis_desktop/accounts_service_runner.py` — frozen branch spawns
  `accounts\AtlasAccounts.exe` with writable-data-dir env; source mode unchanged.
- `packaging/pyinstaller/build_atlas_exe.ps1` — builds the accounts exe and
  copies it into `dist\Atlas\accounts\`.
- `packaging/installer/installer_build.ps1` — self-test now fails the build if
  `accounts\AtlasAccounts.exe` is missing from staging.

### Startup sequence

1. User launches `Atlas.exe` (desktop UI, `:8777`).
2. `server.run()` → `accounts_service_runner.ensure_running_async()`.
3. Runner (frozen) spawns `accounts\AtlasAccounts.exe` with a writable data dir.
4. `AtlasAccounts.exe` runs uvicorn; `:8788/health` returns `{"status":"ok"}`.
5. Desktop register/login/onboarding call the service over HTTP as before.

## Standalone verification (pre-integration)

`AtlasAccounts.exe` run directly:

- `GET /health` → **200 `{"status":"ok","service":"atlas-accounts"}` in ~1.1 s**.
- `POST /auth/register` (full beta profile) → **HTTP 201** (account + profile
  persisted to the SQLite DB).

_Integration verification (fresh install → launch Atlas → /health within 15 s →
register/login/onboarding/admin) is recorded below._

### Fresh-install integration verification

`scripts/verify_frozen_accounts.ps1` — clean silent install to a temp dir, launch
**only** `Atlas.exe` (no manual commands):

| Check | Result |
|---|---|
| Installed `Atlas.exe` + `accounts\AtlasAccounts.exe` | **yes / yes** |
| `:8788/health` after launching only Atlas.exe | **OK in 8.2 s** (≤ 15 s) |
| `POST /auth/register` (full beta profile) via installed product | **201** |
| `POST /auth/login` | **200** |
| Desktop proxy `:8777/api/accounts/service-status` | **200** |

Screenshots from the installed product (`reports/phase192_polish/`):
`installed_01_sign_in.png`, `installed_02_create_account.png` — both render with
**no "accounts service unavailable" error** (the bundled service is running).

Unit tests: `jarvis_desktop/tests/test_phase192_frozen_accounts.py` — **5 passed**
(frozen branch spawns the bundled exe, writable data-dir env, source mode still
uses `python -m`).

## Overhead

| Metric | Value |
|---|---|
| Accounts bundle on disk (`dist\Atlas\accounts\`) | ~82 MB (second Python runtime + FastAPI/SQLAlchemy stack) |
| Installer size | 11.68 MB → **41.78 MB** (lzma2-compressed) |
| Accounts process RSS at runtime | ~84 MB |
| Startup-time impact | ~8 s to a healthy `:8788` after first launch (within the 15 s budget); desktop UI is unaffected (boots immediately, service starts in the background) |

> Note: the accounts bundle currently includes some non-runtime weight (e.g. a
> `mypy` plugin pulled transitively by pydantic, and vendored test folders). This
> is a size-only optimization opportunity and does not affect correctness; left
> out of scope per "remove the blocker only."

## Verdict

**GO for first 3–5 supervised beta users.** A fresh Windows machine with only
`Atlas_Setup.exe` installed now supports register / login / beta application /
pending approval with the accounts service starting automatically — no Python,
no terminal, no manual setup. The `/health` gate passes in 8.2 s (≤ 15 s) and a
complete registration succeeds from a clean install with no confusing errors.
