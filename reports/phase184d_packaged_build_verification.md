# Phase 184D — Packaged Build Verification Report

**Date:** 2026-06-07  
**Auditor:** Phase 184D automated verification  
**Scope:** `dist/Atlas/Atlas.exe`, `installer/output/Atlas_Setup.exe`, packaged static files  
**Method:** Static inspection only. No source code was modified. No features were implemented.

---

## Executive Summary

The packaged build **does not represent the current source revision**. It was produced on 2026-06-04 from commit `6c7e929c` (phase149), which is **54 commits behind HEAD** (`43654277`, phase184c). The build contains internal development labels, JARVIS branding visible to users, missing critical JavaScript files, and outdated workflow names throughout.

**Resolution:** A clean rebuild from current HEAD using `.\packaging\installer\installer_build.ps1` is required before any distribution. No source code changes are needed — the build pipeline is correct; only the build artifact is stale.

---

## 1. Packaging State

### Artifact locations

| Artifact | Path | Size | Modified |
|---|---|---|---|
| Executable | `dist/Atlas/Atlas.exe` | 2.87 MB | 2026-06-04 19:34 |
| Installer | `installer/output/Atlas_Setup.exe` | 11.2 MB | 2026-06-04 19:34 |
| Packaged `build_info.json` | `dist/Atlas/_internal/packaging/installer/build_info.json` | — | 2026-06-04 |

### Build identity

The `build_info.json` embedded inside the executable:

```json
{
  "build_date": "2026-06-04T19:34:09",
  "commit": "6c7e929c",
  "version": "phase146b-true-beta-blocker-fixes",
  "entry": "Atlas.exe",
  "product": "ATLAS"
}
```

**Evidence:**
- `version`: `"phase146b-true-beta-blocker-fixes"` — internal development label, not semver
- `commit`: `6c7e929c` resolves to `phase149: audit zero-friction startup packaging` (2026-06-04 15:54)
- Current HEAD: `43654277` `phase184c: ship readiness verification` (2026-06-07 13:17)
- **Gap: 54 commits, ~3 calendar days**

### Rebuild validation

A fresh rebuild via `packaging/installer/installer_build.ps1` would produce version `0.1.0-beta` because:
- `packaging/installer/installer_build.ps1` line 23: reads `PRODUCT_VERSION` from `jarvis_desktop/product_info.py`
- `jarvis_desktop/product_info.py` line 13: `PRODUCT_VERSION = "0.1.0-beta"`
- `packaging/installer/generated_version.iss` (last generated): `#define MyAppVersion "0.1.0-beta"`

The old version string `phase146b-true-beta-blocker-fixes` would not appear in a clean rebuild. It originated from a pre-packaging-refactor `build_info.json` that was baked into the June 4 build.

---

## 2. Missing Files in Packaged Build

The packaged `_internal/jarvis_desktop/static/` directory is missing **8 files** present in the current source. Four are `<script>` dependencies of `index.html`; two are 3D graph libraries; two are linked HTML pages.

### Critical missing JS files (referenced by `<script>` tags)

| File | Used In | Function | Impact if absent |
|---|---|---|---|
| `atlas_copy.js` | `index.html`, `support.html` | "Copy for Claude" clipboard export | Core workflow broken silently |
| `atlas_product.js` | `index.html`, `support.html`, `about.html`, `contact.html` | Product version display, feedback route, update check | Version panel blank; feedback link dead |
| `atlas_trust.js` | `index.html` | Trust indicator (context freshness) | Trust status silent failure |
| `atlas_zero_friction.js` | `index.html` | Onboarding flow, guided tooltips | First-user path degraded |

**Evidence — index.html lines 476–484 (source):**
```html
<script src="atlas_copy.js"></script>
…
<script src="atlas_zero_friction.js"></script>
<script src="atlas_trust.js"></script>
<script src="atlas_product.js"></script>
```
None of these files exist in `dist/Atlas/_internal/jarvis_desktop/static/`.

### Missing vendor directory (3D graph)

The current source `index.html` loads Three.js and 3d-force-graph from the bundled `vendor/` directory:
```html
<!-- 3D dependency graph (bundled locally for offline use). -->
<script src="vendor/three.min.js"></script>
<script src="vendor/3d-force-graph.min.js"></script>
```

The packaged `index.html` still uses the **pre-vendor-switchover CDN URLs**:
```html
<script src="https://unpkg.com/three@0.157.0/build/three.min.js"></script>
<script src="https://unpkg.com/3d-force-graph@1.73.4/dist/3d-force-graph.min.js"></script>
```

`vendor/` does not exist in the packaged build. The 3D dependency graph view:
- Works if unpkg.com is reachable (requires internet)
- Fails completely if offline

### Missing HTML pages

| File | Linked From | Impact |
|---|---|---|
| `quickstart.html` | `index.html` nav, `demo.html` CTA | Navigation link returns 404 |
| `startup-error.html` | `server.py` line 340 (fatal crash fallback) | Crash recovery page returns 404 instead of help |
| `latest.json` | `/api/version` update check | Update check endpoint silently broken |

**Evidence — server.py line 340:**
```python
start_path = "/startup-error.html"
_log_launcher(f"recovered on ephemeral port {bound_port} with startup-error page")
```
If Atlas.exe crashes on startup, the fallback opens a browser tab at `/startup-error.html` which returns 404.

---

## 3. Stale Content in Packaged Files

The packaged static files predate Phase 181–184 changes. The following user-visible strings appear in packaged files but have been replaced in current source.

### `app.js` — legacy workflow names and engineering labels

| Packaged string | Source replacement | Location |
|---|---|---|
| `"Build Plan needs a scan"` | `"Change Plan needs a scan"` | Empty state title |
| `"Impact analysis needs a scan"` | `"What Breaks needs a scan"` | Empty state title |
| `"Build Plan and Investigation may have fewer file anchors"` | `"Change Plan and Debug may have…"` | Scan warning tip |
| `"You can still run Build Plan"` | `"You can still run Change Plan"` | Partial graph tip |
| `"try Build Plan next"` | `"try Change Plan next"` | Scan success toast |
| `"Build plan"` (performance panel) | `"Change Plan"` | Performance stats row |
| `"Impact analysis"` (performance panel) | `"What Breaks"` | Performance stats row |
| `title="…not just fan-in"` | (attribute removed) | System health tooltip |
| `title="…high fan-in"` | (attribute removed) | System health tooltip |
| `"fan-in / fan-out"` | `"dependents / dependencies"` | Module inspector |
| `fan-in ${n.fan_in}` | (removed from label string) | Module detail panel |
| `"Impact could not be analyzed"` | `"Could not analyze what breaks"` | Error state heading |
| `setProductTourStep("Impact analysis", …)` | `"What breaks?"` | Product tour |
| `/* Build Plan */` (comment) | `/* Change Plan */` | Section header |

### `atlas_beta.js` — markdown export headers

| Packaged | Source |
|---|---|
| `"## Build Plan"` | `"## Change Plan"` |
| `"## Investigation"` | `"## Debug"` |
| `"## Impact"` | `"## What Breaks"` |

These are the headers of the Claude export bundle. A user copying their session to Claude receives headers with internal names.

### `billing.js` — usage dashboard labels

| Packaged | Source |
|---|---|
| `"Build plans"` | `"Change Plans"` |
| `"Investigations"` | `"Debug"` |
| `"Impact analyses"` | `"What Breaks"` |

Appears in both the user usage dashboard and admin metrics view.

### `universe.js` — 3D tooltip strings

| Packaged | Source |
|---|---|
| `fan-in ${n.fan_in} · risk` | `importers: ${n.fan_in} · risk` |

Visible in every 3D node tooltip on hover.

---

## 4. Branding Verification

### JARVIS references in packaged user-visible pages

The following files in the packaged build contain the brand name **JARVIS** in user-visible positions (titles, headings, body copy, navigation). None of these files contain JARVIS in the current source.

| File | User-visible occurrence |
|---|---|
| `feedback.html` | `<title>JARVIS — Feedback</title>`, logo nav: "JARVIS" |
| `beta.html` | `<title>JARVIS — Beta Program</title>`, body: "We're inviting a small group of developers to use JARVIS on real codebases", card copy: "Paste a JARVIS context packet…", "does JARVIS earn a permanent tab…" |
| `demo.html` | `<title>JARVIS — Watch it in action</title>`, `<h1>Watch JARVIS in action</h1>`, chapter narration: "Point JARVIS at a local project" |
| `gallery.html` | `<title>JARVIS — Gallery</title>`, `<h1>A look inside JARVIS</h1>` |
| `studio.html` | `<title>JARVIS — Demo Studio</title>`, brand mark: "JARVIS Repository Intelligence" |
| `admin.html` | `<title>JARVIS — Admin Metrics</title>`, nav: "JARVIS" |
| `marketing.css` | CSS class names (`jarvis-*`) — not directly user-visible |
| `app.js` | JS identifier `LEGACY_RECENT_KEY = "jarvis_recent_repos"`, `JARVIS_UNIVERSE.*` — not directly visible |
| `universe.js` | `JARVIS_UNIVERSE` global — not directly visible |

**Source comparison:** `grep -rn "JARVIS" jarvis_desktop/static --include="*.html"` returns **zero results**. All user-visible HTML has been rebranded in source.

### Phase internal labels

| Location | String | Classification |
|---|---|---|
| `dist/Atlas/_internal/packaging/installer/build_info.json` | `"version": "phase146b-true-beta-blocker-fixes"` | Internal dev label — user-visible via version API |
| `atlas_beta.js` line 288 | `(function phase141Boot()` | Internal function name — not user-visible (JS code comment) |

### Installer metadata

The `Atlas.iss` uninstall section (line 55):
```
Type: filesandordirs; Name: "{userappdata}\.jarvis_desktop"
```
This is visible to users during uninstallation — the Windows installer will display that it is removing `.jarvis_desktop`. Minor; only appears on uninstall.

---

## 5. Offline Verification

| Component | Source behaviour | Packaged behaviour |
|---|---|---|
| 3D dependency graph | `vendor/three.min.js` (local, offline-safe) | CDN (unpkg.com) — requires internet |
| Fonts (index.html) | No CDN link — fallback to system font | Google Fonts CDN request on every load |
| Fonts (support.html) | Google Fonts CDN (unchanged in source) | Google Fonts CDN — identical |
| Scan, graph, plans | Local Python server — offline | Local Python server — offline |
| Repository analysis | Local file system — offline | Local file system — offline |
| Update check | Optional; fails silently | Same (configured via env var) |

**Summary:** The packaged build regresses offline behaviour relative to current source. The 3D graph view specifically requires internet in the packaged build; the current source is fully offline-capable for all primary workflows.

---

## 6. Workflow Verification (Packaged)

Because the packaged build is missing four script files that `index.html` depends on, the following workflows are broken or degraded in the packaged executable:

| Workflow | Status | Root Cause |
|---|---|---|
| Launch / startup screen | Likely functional | Core server/boot not affected by missing JS |
| Load Sample Repository | Likely functional | Server-side; unaffected |
| Scan | Likely functional | Server-side; unaffected |
| **Copy for Claude** | **Broken** | `atlas_copy.js` missing |
| Change Plan generate | Likely functional | `atlas_beta.js` present (old headers) |
| Debug | Likely functional | `atlas_beta.js` present |
| What Breaks | Likely functional | `atlas_beta.js` present (old label) |
| 3D graph (Dependency Universe) | **Requires internet** | CDN; `vendor/` missing |
| Trust indicator | **Silent failure** | `atlas_trust.js` missing |
| Onboarding / first-user path | **Degraded** | `atlas_zero_friction.js` missing |
| Feedback link | **Broken** | `atlas_product.js` missing; also JARVIS branding |
| Version display | **Shows wrong version** | `"phase146b-true-beta-blocker-fixes"` |
| Quickstart link | **404** | `quickstart.html` missing |
| Crash recovery page | **404** | `startup-error.html` missing |
| Support bundle | Likely functional | `support.js` present |
| Persistence restore | Likely functional | Server-side; unaffected |
| Export bundle headers | **Wrong names** | Old `atlas_beta.js` |

---

## 7. Blocker List

### Critical — prevents distribution

| # | Finding | Evidence |
|---|---|---|
| C1 | **Build is 54 commits behind HEAD** — packaged from `6c7e929c` (phase149, June 4) vs `43654277` (phase184c, June 7) | `build_info.json commit = "6c7e929c"`; `git rev-list 6c7e929c..HEAD = 54` |
| C2 | **`version = "phase146b-true-beta-blocker-fixes"`** user-visible via version API and support page | `dist/Atlas/_internal/packaging/installer/build_info.json` |
| C3 | **`atlas_copy.js` missing** — "Copy for Claude" (primary value action) is non-functional | Source: 4 `<script>` references; packaged `static/`: file absent |
| C4 | **`atlas_product.js` missing** — product version, feedback form, update check broken | Source: 4 `<script>` references; packaged `static/`: file absent |
| C5 | **`atlas_trust.js` missing** — trust/freshness indicator broken | Source: 1 `<script>` reference; packaged `static/`: file absent |
| C6 | **`atlas_zero_friction.js` missing** — onboarding, guided first-user path broken | Source: 1 `<script>` reference; packaged `static/`: file absent |
| C7 | **JARVIS brand in user-visible pages** — feedback.html, beta.html, demo.html, gallery.html, studio.html show "JARVIS" in titles/headings/body | Source has zero JARVIS references in HTML |
| C8 | **`startup-error.html` missing** — crash recovery page is a 404 | `server.py` line 340 redirects to `/startup-error.html` on fatal error |

### High — significant user-visible degradation

| # | Finding |
|---|---|
| H1 | 3D dependency graph requires internet (unpkg.com CDN); `vendor/` missing; source is offline-safe |
| H2 | `app.js` contains 14 legacy strings: "Build Plan", "Impact analysis", "fan-in / fan-out", "Impact could not be analyzed" etc. |
| H3 | `atlas_beta.js` exports "## Build Plan", "## Investigation", "## Impact" to Claude — wrong canonical names |
| H4 | `billing.js` usage dashboard shows "Build plans", "Investigations", "Impact analyses" |
| H5 | `universe.js` 3D tooltips show `fan-in N · risk` not `importers: N · risk` |
| H6 | `quickstart.html` missing — nav link returns 404 |

### Medium — present but minor

| # | Finding |
|---|---|
| M1 | `latest.json` missing from packaged build |
| M2 | Google Fonts CDN loaded on every app page load (packaged index.html); source removed this |
| M3 | Installer uninstall mentions `.jarvis_desktop` user-visible path |

---

## 8. Root Cause

All findings have a single root cause: **the packaged artifacts have not been rebuilt since June 4, 2026 (commit `6c7e929c`, phase149)**. The source tree has since undergone 54 commits including:

- Phase 150–152: packaging refactor, PyInstaller spec, installer build pipeline  
- Phase 155: installer self-test  
- Phase 157: payload validation  
- Phase 175B: `product_info.py`, version `0.1.0-beta`  
- Phase 176–177: first-user polish, UX improvements  
- Phase 181: persistence foundation  
- Phase 182: beta operations, security hardening  
- Phase 184: UX consistency sweep (all workflow renames, JARVIS cleanup, vendor bundle, missing scripts added)

The build pipeline (`.\packaging\installer\installer_build.ps1`) is correct and will produce a clean `0.1.0-beta` build if run from current HEAD.

**No source code changes are required to resolve C1–C8.**

---

## GO / NO-GO

### 5 supervised beta users

> **NO-GO**

Blockers C1–C8 are present. "Copy for Claude" (the product's primary value action) is non-functional. The version string shown to users is `"phase146b-true-beta-blocker-fixes"`. JARVIS brand appears on reachable pages. The crash recovery page returns 404.

### 20 supervised beta users

> **NO-GO**

Same blockers. Distributing to a wider group while the core clipboard export is broken and the product version string is an internal label would harm user trust and generate support noise that masks signal.

---

## Required Action (not implementing — audit only)

Run from repo root:

```powershell
.\packaging\installer\installer_build.ps1
```

This will:
1. Read version `0.1.0-beta` from `product_info.py`
2. Record current HEAD commit hash in `build_info.json`
3. Run PyInstaller from `packaging/pyinstaller/atlas.spec` — which bundles all of `jarvis_desktop/static/` including the four previously-missing JS files and `vendor/`
4. Stage and compile `Atlas_Setup.exe` via Inno Setup

After rebuild, re-run this audit against the new artifacts to verify GO.
