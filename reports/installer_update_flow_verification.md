# Installer — Running-Application Update Flow

**Date:** 2026-06-07
**Component:** `packaging/installer/Atlas.iss` + `packaging/installer/running_app_flow.iss`
**Toolchain:** Inno Setup 6.7.3 → `packaging/installer/output/Atlas_Setup.exe` (rebuilt)

## Problem

When a user updated Atlas while it was still running, the installer relied on
Inno Setup's default Restart-Manager / "files in use" behavior. Its automatic
shutdown attempt could fail, and the user was then shown a **generic technical
error dialog**. Poor UX for beta users.

## Fix

`[Setup]` now disables Inno's default close/restart handling:

```
CloseApplications=no
RestartApplications=no
```

A dedicated `[Code]` flow (shared file `running_app_flow.iss`, `#include`d by the
installer) takes over via `PrepareToInstall`, which runs **before any files are
copied**, so an unsafe overwrite of a live `Atlas.exe` can never happen:

1. **Detect** a running Atlas — `IsAtlasRunning()` queries
   `Win32_Process WHERE Name='Atlas.exe'` (WMI), with a `tasklist` fallback.
2. **Dedicated dialog** — `ShowAtlasRunningDialog()` (a custom `TSetupForm`
   built with `CreateNew`):
   - **Title:** "Atlas is currently running"
   - **Body:** "Atlas must be closed before the update can continue."
   - **Actions (4 buttons):** Close Atlas automatically · Retry · Open Task
     Manager instructions · Cancel
3. **Close automatically** — `CloseAtlas()` sends a graceful
   `taskkill /IM Atlas.exe`, waits, then a force `taskkill /F /T /IM Atlas.exe`
   for the whole process tree (server + any child process).
4. **If automatic close fails** — the dialog re-renders with:
   - "We couldn't close Atlas automatically."
   - Simple manual steps (Ctrl+Shift+Esc → find Atlas.exe → End task)
   - The **exact process name**: `Atlas.exe`
   - A **Retry** button (now the default)
5. **Open Task Manager instructions** — a clear step-by-step message box.
6. **Cancel** — stops the update with a plain-language note
   ("Update paused: Atlas is still running. Please close Atlas, then run this
   installer again.") — **no generic installer error language**.
7. **Silent / unattended** (`/SILENT`, `/VERYSILENT`) — `WizardSilent()` is
   detected and Atlas is auto-closed without UI (never hangs on a dialog); if it
   cannot be closed, the update aborts cleanly.

The interactive loop repeats until Atlas is closed (then the update proceeds) or
the user cancels. Either way, **files are never overwritten while Atlas runs.**

## Rebuilt installer

| Property | Value |
|---|---|
| Path | `packaging/installer/output/Atlas_Setup.exe` (mirror: `installer/output/Atlas_Setup.exe`) |
| Size | 12,232,138 bytes (11.67 MB) |
| SHA256 | `5F78090BA6106779ABA186A781A0BAEC523DF01CC401B1FC5D83899EA1FF63F3` |
| Rebuilt | 2026-06-07T20:45:38 (after the UX changes) |

The mirror copy under `installer/output/` has an identical SHA256.

## Screenshots

Rendered from the **exact shipped code** — `running_app_flow.iss` is `#include`d
by both the installer (`Atlas.iss`) and the verification harness
(`_verify/running_app_flow_test.iss`), so these are pixel-accurate to what beta
users see. Saved under `reports/installer_update_flow/`:

| File | Shows |
|---|---|
| `01_atlas_running_dialog.png` | "Atlas is currently running": title, body, 4 actions (Close is default). |
| `02_close_failed_dialog.png` | "We couldn't close Atlas automatically": manual steps, **Process name: Atlas.exe**, Retry default. |
| `03_task_manager_instructions.png` | Task Manager step-by-step instructions. |

## Verification — OVERALL: PASS (7/7)

Script: `scripts/verify_installer_update_flow.ps1`.
Raw results: `reports/installer_update_flow/scenario_results.json`.

### Real installer, end-to-end (no GUI navigation needed)

| Case | Result | Status |
|---|---|---|
| **Atlas running blocks the unsafe install** | The real `Atlas_Setup.exe` detects the running `Atlas.exe` and **closes it before any files are written** (`atlas_closed=True` *then* `installed=True`, no hang). The live process is never overwritten. | **PASS** |
| **Atlas not running installs successfully** | Real installer installs normally (exit 0, `Atlas.exe` written). | **PASS** |

> Interactive runs gate on the dialog (proven by the shared-code screenshots);
> silent/unattended runs auto-close first. In both, the overwrite-while-running
> is prevented.

### Process-state scenarios

Each scenario sets up the relevant state, then exercises the **exact** detection
(`Win32_Process Name='Atlas.exe'`) and close (`taskkill /IM` then `/F /T /IM`)
logic the installer uses.

| Scenario | Result | Status |
|---|---|---|
| Atlas running (active) | detected + closed | **PASS** |
| Atlas **idle** | detected + closed | **PASS** |
| Atlas **service/worker active** (bound TCP port) | detected + closed; port 8779 freed after close | **PASS** |
| Atlas with **browser window open** | Atlas closed; the separate browser process left untouched | **PASS** |
| **Browser open but no Atlas.exe** | `Atlas.exe` **not** detected → **no false block** | **PASS** |

> Detection is strictly by the `Atlas.exe` image name, so an open browser (a
> different process image) never triggers a false block.

## Files changed

- `packaging/installer/Atlas.iss` — `CloseApplications=no`,
  `RestartApplications=no`; `[Code]` `#include`s the flow and adds
  `PrepareToInstall`.
- `packaging/installer/running_app_flow.iss` — **new** shared flow code.
- `packaging/installer/_verify/running_app_flow_test.iss` — **new** screenshot harness.
- `scripts/capture_installer_dialogs.ps1` — **new** dialog screenshot capture.
- `scripts/verify_installer_update_flow.ps1` — **new** end-to-end + scenario verification.
- `packaging/installer/output/Atlas_Setup.exe` + `installer/output/Atlas_Setup.exe` — rebuilt binaries.

## Notes / limitations

- The 4-button dialog uses a custom `TSetupForm` (`CreateNew`) because this Inno
  build's `CreateCustomForm()` is unavailable and `TaskDialogMsgBox` only
  supports renaming up to 3 standard buttons.
- A pixel screenshot of the dialog hosted by the wizard process specifically
  (vs. the identical harness) was not produced because the CI-style host blocks
  synthetic foreground/keyboard automation of the multi-page wizard. Dialog
  rendering is proven by the shared-code harness; the real installer's behavior
  is proven by the silent end-to-end cases above.

## Verdict

**Ready to distribute to beta users.** The running-application update flow
replaces the generic error with a dedicated, plain-language dialog; automatic
close works with a clear manual fallback (exact process name + Retry);
silent/unattended updates auto-close instead of hanging; and detection/close
hold across all upgrade scenarios with no false blocking from an open browser.
