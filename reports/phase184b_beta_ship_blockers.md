# Phase 184B — Final Beta Ship Blockers

Date: 2026-06-07

Scope: Fix only the four High blockers from [Phase 184A first-time user audit](phase184a_first_time_user_audit.md). No changes to graph engine, impact engine, persistence, trust integrity, billing, or operations.

## Summary

| Blocker | Root cause | Fix | Status |
| --- | --- | --- | --- |
| H1 Sample → Change Plan scan gate | `finishScanSession()` cleared `STATE.summary` after demo/scan loaders populated it | Stop nulling summary; workflow nav reads `summary.ok` correctly | Fixed |
| H2 Copy for Claude empty clipboard | Metadata-only server export stripped to empty string; weak `copyText` fallback reported success | Fallback to legacy prompt body; robust sync copy fallback; reject empty payloads | Fixed |
| H3 Internal phase version | Stale `generated_version.iss` / installer scripts read wrong file | Version sourced from `product_info.PRODUCT_VERSION` (`0.1.0-beta`) | Fixed |
| H4 External CDN for graph | `index.html` loaded Three.js from unpkg | Vendored under `jarvis_desktop/static/vendor/` | Fixed |

## 1. Sample Repository (H1)

**Reproduction (184A):** Load Sample → open Change Plan / Debug / What breaks? → panels still showed scan-first empty state even though backend could generate plans.

**Root cause:** In `app.js`, both `loadDemoMode()` and `executeScanFlow()` fetch `/api/repositories/current/summary` then call `finishScanSession()`, which executed `STATE.summary = null` before `updateWorkflowToolbars()`. Navigation gates (`go('build')`) check `STATE.summary?.ok` and rendered `renderWorkflowGate()`.

**Fix:** Removed the summary null assignment from `finishScanSession()`. Demo load and full scan now leave summary populated; toolbars unlock and workflow views show ready state.

**Verification:** `test_load_demo_mode_summary_ready_for_change_plan`, `test_finish_scan_session_does_not_clear_summary`.

## 2. Copy For Claude (H2)

**Reproduction (184A):** Load sample → Generate Change Plan → Copy Claude → clipboard empty; browser console showed `dispatchEvent` / `Unexpected end of input` (likely unrelated console noise from inline handlers / Three.js).

**Root cause:** `zfClipboardBody()` preferred server export text and ran `zfStripClipboardMetadata()`. When export contained only metadata header lines (`scan_id:`, `memory_ref:`, etc.), the stripped body was empty. `copyText()` still showed success; clipboard received an empty string.

**Fix:**

- `atlas_zero_friction.js`: if stripped server export is empty, fall back to `zfLegacyFullPromptBody()`.
- `app.js` `copyText()`: reject empty payloads; use off-screen textarea + `execCommand('copy')` fallback; return boolean success.
- `copyForAi()`: async, awaits `copyText`, surfaces error toast on failure.

**Verification:** `test_change_plan_export_has_copyable_body`, `test_copy_for_ai_falls_back_when_export_is_metadata_only`, `test_copy_text_rejects_empty_payload`.

## 3. Version String (H3)

**Audit surfaces:**

| Surface | Before (184A packaged run) | After |
| --- | --- | --- |
| `/api/health` `version` | `phase146b-true-beta-blocker-fixes` (stale build) | `0.1.0-beta` via `product_info.py` |
| Shipped static HTML/JS | Already clean | No `phase###` patterns |
| `about.html` / `changelog.html` | `0.1.0-beta` | Unchanged |
| `generated_version.iss` | Stale phase string | `0.1.0-beta` |
| Installer build scripts | Parsed `api.py` (no literal version) | Parse `product_info.py` |

**Note:** Existing `dist/Atlas/Atlas.exe` on disk may still report an old version until rebuilt with updated packaging scripts.

## 4. External CDN Audit (H4)

### Critical (bundled locally)

| Asset | Was | Now |
| --- | --- | --- |
| three.min.js @0.157.0 | unpkg.com | `static/vendor/three.min.js` |
| 3d-force-graph.min.js @1.73.4 | unpkg.com | `static/vendor/3d-force-graph.min.js` |

Updated: `index.html`, `graph_smoke.html`, `studio.html`.

### Non-blocking (removed from main app; system font fallback)

| Asset | Pages | Impact offline |
| --- | --- | --- |
| Google Fonts (Inter, Orbitron) | index.html (removed), marketing/support pages (unchanged) | Main app uses `Inter, system-ui` / `Orbitron` with system fallback |

Marketing pages (`landing.html`, `demo.html`, etc.) still reference Google Fonts for typography polish; core Atlas workflow (`index.html`) no longer requires network for JS or fonts.

## Files changed

- `jarvis_desktop/static/app.js`
- `jarvis_desktop/static/atlas_zero_friction.js`
- `jarvis_desktop/static/index.html`
- `jarvis_desktop/static/graph_smoke.html`
- `jarvis_desktop/static/studio.html`
- `jarvis_desktop/static/vendor/three.min.js` (new)
- `jarvis_desktop/static/vendor/3d-force-graph.min.js` (new)
- `packaging/installer/installer_build.ps1`
- `packaging/pyinstaller/build_atlas_exe.ps1`
- `packaging/installer/generated_version.iss`
- `packaging/installer/build_info.json`
- `jarvis_desktop/tests/test_phase184b_beta_ship_blockers.py` (new)

## Regression

```powershell
py -3 -m pytest jarvis_desktop/tests/test_phase184b_beta_ship_blockers.py -q
py -3 -m pytest jarvis_desktop/tests/test_phase184_ux_consistency.py jarvis_desktop/tests/test_phase179_beta_ship_blockers.py jarvis_desktop/tests/test_phase155_first_user_experience.py -q
```

## Beta gate

After rebuild, verify manually:

1. Load Sample → Change Plan opens without scan-first gate.
2. Generate plan → Copy for Claude → clipboard contains goal + files + steps.
3. `/api/health` → `"version": "0.1.0-beta"`.
4. Disconnect network → reload app → Codebase Map renders (local vendor JS).
