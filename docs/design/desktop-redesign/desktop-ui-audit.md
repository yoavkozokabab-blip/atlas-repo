# Atlas desktop UI audit

Date: 2026-07-13  
Branch: `design/atlas-premium-experience`  
Scope: `atlas_desktop`, its launchers, packaged static payload, and loopback APIs. `websites/atlas-web` is excluded.

## Proven entry point and architecture

- Packaged entry: `atlas_desktop_entry.py`, collected as `Atlas.exe` by `atlas_desktop_entry.spec`.
- Developer entry: `py -3 run_atlas.py`; default address `http://127.0.0.1:8777/`.
- Shell: the default Windows browser. Atlas is not Electron, Tauri, or a native webview. `run_atlas.py` starts `atlas_desktop.server`, which serves `atlas_desktop/static/index.html` and JSON APIs on loopback.
- Backend: Python `ThreadingHTTPServer` by default; optional FastAPI/uvicorn is not route-equivalent and is not the redesign target.
- UI source: `atlas_desktop/static/index.html`, layered CSS, `app.js`, workflow/account/MCP scripts, and the bundled Three.js graph renderer.
- Package build: `powershell -File packaging/pyinstaller/build_atlas_exe.ps1`.
- Installer build: `powershell -File packaging/installer/installer_build.ps1`.

## Live baseline

The source app was run with isolated `ATLAS_DESKTOP_DATA` on port 8791. First launch, unsigned notice, auth, local mode, empty Home, Scan, progress, indexed Home, Ask, Debug, Impact, Plan, and Map were exercised at 900 x 650 through 1600 x 1000.

1. Splash, unsigned notice, and auth form a serial launch funnel styled like the public site.
2. Sign-in is visually dominant although local mode is a supported product mode.
3. Empty Home is a marketing hero with unused space and a three-step explainer.
4. Navigation changes after indexing, making location and breadth unstable.
5. At 900 x 650 the app bar wraps into three rows while repository, account, and detail controls compete for width.
6. Ask, Debug, Impact, and Plan have useful grounded outputs but underuse desktop width and lose persistent repository context.
7. Map is a dense three-column gaming-HUD surface with clipped panels, canvas-only interaction, blue/cyan glow, and metric-card overload.
8. Agent integrations exist on Home but have no stable Agents destination.
9. Diagnostics APIs and support tooling exist, but system health is buried in Map or separate support pages.
10. Memory, files, symbols, concepts, and evidence are product objects without first-class navigation.
11. Settings is fragmented across account menus, static pages, and implicit defaults.
12. Legacy neon CSS, Home tokens, `premium.css`, and report-specific CSS coexist. This layering is a regression risk.

## Accessibility baseline

- The graph has no accessible region contract and only Module mode gets a list fallback.
- Several actions are clickable `div`/`span` elements or incomplete ARIA pseudo-controls.
- Dialog semantics, focus containment/return, progressbar state, validation associations, live announcements, route state, and form labels are inconsistent.
- Required input/button boundaries use hairlines below 3:1 contrast in some states.
- Auth disables body scrolling, risking clipped actions in short windows and at zoom.

## Preservation boundary

Change hierarchy, markup, CSS, and client-side composition only. Preserve endpoint paths, payloads, stored data, account gates, scanning, persistence restore, MCP config behavior, support exports, installer packaging, loopback-only security, and script boot order unless replaced by an explicitly tested adapter. Never claim evidence absent from the response.

## Conclusion

The redesign target is a dense desktop workbench around the existing browser-hosted SPA. Replace the horizontal marketing header with a stable application rail and operational status bar, then migrate workflows without renaming their contracts.
