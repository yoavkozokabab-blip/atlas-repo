# Phase 112 — Installer + First Public Demo

**Status:** Complete  
**Product version:** `phase112-installer-demo`  
**Scope:** Productization only — no new analysis engines, benchmarks, or token optimization.

## Goal

A developer with zero JARVIS knowledge can install, run a demo, reach a wow moment in ~3 minutes, and understand the value proposition without assistance.

## Delivered

| # | Feature | Implementation |
|---|---------|----------------|
| 1 | Windows installer | `installer/jarvis.iss` (Inno Setup), `installer_build.ps1`, `installer/README.md` → `JARVIS_Setup.exe` |
| 2 | Demo pack | `small_repo`, `medium_repo`, `large_repo` + `GET /api/demo/packs`, `POST /api/demo/load` `{pack}` |
| 3 | Screenshot mode | Enhanced presentation layout, watermark badge, hides debug chrome |
| 4 | Product tour | **Start Product Tour** — auto demo scan → graph tour → copilot → impact → export |
| 5 | Landing assets | `jarvis_desktop/assets/landing/checklists.md` + bundle copy |
| 6 | Local analytics | `jarvis_desktop/analytics.py`, JSONL in `%USERPROFILE%\.jarvis_desktop` |
| 7 | Export bundle | `POST /api/demo/export-bundle` → zip with summary, report, SVG, context |
| 8 | Polish | Demo pack picker, empty states, panel scrolling, responsive grid |
| 9 | Tests | `test_phase112_installer_and_demo_pack.py` (59 total desktop tests pass) |

## 3-minute stranger path

1. Run `installer/output/JARVIS_Setup.exe` (or `py run_jarvis_desktop.py`)
2. Click **Try Demo** or **Start Product Tour**
3. Explore galaxy graph → ask Copilot → export Claude context / Demo Bundle

## Installer build

```powershell
cd local_jarvis
.\installer_build.ps1          # requires Inno Setup 6 for .exe
.\installer_build.ps1 -SkipCompile   # staging only
```

Output: `installer/output/JARVIS_Setup.exe`

Installer creates Desktop + Start Menu shortcuts, registers icon, uninstalls cleanly.

## Demo pack module counts (typical)

| Pack | Modules | Use case |
|------|---------|----------|
| small | ~6 | Fast wow / product tour |
| medium | ~18 | Multi-subsystem demo |
| large | ~40 | Galaxy-scale graph |

## Local analytics events

`scan_completed`, `demo_loaded`, `graph_opened`, `copilot_question`, `export_created`, `bundle_exported`, `product_tour_started`

Query: `GET /api/analytics/summary` — local file only, no cloud.

## Constraints honored

- Builder Core analysis logic unchanged (same `depgraph`, `architectural_risk`, `repository_understanding` imports)
- No benchmark / compact_packets / token work in this phase

## Verification

```powershell
py -m pytest jarvis_desktop/tests/ -q
```

## Screenshots

Capture from running desktop app using **Screenshot mode** + **Export Demo Bundle** (see `assets/landing/checklists.md`).
