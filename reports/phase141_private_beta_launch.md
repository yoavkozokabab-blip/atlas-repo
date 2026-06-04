# Phase 141 — Private Beta Launch Preparation

**Date:** 2026-06-02  
**Goal:** First external developers can install Atlas and succeed without hand-holding.

## Launch readiness: **8.0 / 10**

| Capability | Status |
|------------|--------|
| Welcome screen | ✅ First-visit overlay with sample / walkthrough / own repo |
| Sample repository | ✅ Load Sample + demo packs (unchanged, surfaced on welcome) |
| Guided walkthrough | ✅ Step-by-step panel (`startGuidedWalkthrough`) |
| Report Issue | ✅ Top bar + `JarvisFeedback` with diagnostics context |
| Workflow thumbs | ✅ Build / Investigate / Impact → `atlas_workflow_feedback` localStorage |
| Markdown bundle export | ✅ `downloadWorkflowMarkdownBundle()` |
| About Atlas | ✅ In-app modal + expanded `about.html` |
| Beta diagnostics | ✅ `GET /api/system/diagnostics` + Copy Diagnostics button |

## New developer path (self-serve)

1. Open Atlas → **Welcome** screen.
2. **Load Sample Repository** or **Guided Walkthrough** (runs sample + Build / Investigate / Impact examples).
3. Explore **Repository Map**, run workflows, thumbs-up/down optional feedback.
4. **Export workflow markdown** or AI context from Export.
5. If stuck: **Report Issue** (includes diagnostics JSON) or **Diagnostics** copy for support.

## API

- `GET /api/system/diagnostics` — version, repository size, scan statistics, evidence coverage, workflow timings.
- `PRODUCT_VERSION` → `phase141-private-beta-launch`

## Files

| File | Role |
|------|------|
| `jarvis_desktop/api.py` | `beta_diagnostics()`, version bump |
| `jarvis_desktop/server.py` | diagnostics route |
| `jarvis_desktop/static/atlas_beta.js` | welcome, walkthrough, feedback, export, about, diagnostics UI |
| `jarvis_desktop/static/feedback.js` | `openReportIssue`, context in saved entries |
| `jarvis_desktop/static/index.html` | welcome, guided tour, about modal, toolbars |
| `jarvis_desktop/static/app.js` | workflow feedback hooks, toolbars |
| `jarvis_desktop/static/about.html` | does / does not do |
| `jarvis_desktop/static/styles.css` | phase 141 layout |
| `jarvis_desktop/tests/test_phase141_private_beta_launch.py` | automated checks |

## Remaining before wide launch

- Bundle Three.js offline (CDN dependency).
- Installer / signed build docs for external OS installs.
- Optional: email/upload path for feedback (today: local + manual export).
- Short video on welcome (marketing `demo.mp4` still optional).

## Support bundle format

Support can ask users to click **Diagnostics** and paste JSON containing:

- `version`, `generated_at`
- `repository.name`, `repository.size_mb`, `repository.demo_mode`
- `scan_statistics` (files, modules, edges, duration, graph quality)

## Tests

```bash
py -3 -m pytest jarvis_desktop/tests/test_phase141_private_beta_launch.py -q
```
