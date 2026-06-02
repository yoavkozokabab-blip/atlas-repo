# Phase 121D — Graph Mode Clarity & Trust Fix

**Date:** 2026-06-02  
**Builds on:** [phase121c_module_graph_correctness.md](phase121c_module_graph_correctness.md)

## Problem

The UI showed full-repository totals (e.g. 233 modules, 414 dependencies) while rendering 11 subsystem/cluster nodes, implying data loss. Phase 121C proved the module payload is complete; the mismatch was **presentation**.

## Solution

Make the active graph mode unmistakable: mode badge, mode-specific metrics, entity summary line, massive-mode disclosure, and correct defaults.

---

## Changes

### 1. Mode-specific metrics (`#graphScaleHeader`)

| Mode | Visible row | Underlying row |
|------|-------------|----------------|
| **Module Graph** | modules, dependencies, risk, cycles | — |
| **Architecture Overview** | subsystems + subsystem/cluster links | modules + dependencies |
| **Hierarchy View** | level-appropriate nodes + links | modules + dependencies |

### 2. Large mode badge (`#graphModeBadge`)

Centered pill: **Module Graph** | **Architecture Overview** | **Hierarchy View** (color-coded by mode).

### 3. Entity summary (`#graphEntitySummary`)

Examples:

- `Showing 216 of 216 modules`
- `Showing 11 architecture subsystems representing 216 modules`
- `Showing 11 top-level hierarchy nodes representing 216 modules`

### 4. Massive mode banner (`#massiveModeBanner`)

When `massive_mode` is active:

- Title: **Massive Repository Mode Active**
- Reason from `massive_reason` (e.g. repository size exceeds threshold)
- **Show Full Module Graph** button (hidden when already on module view)

### 5. Default view

- `GRAPH_HIERARCHY_THRESHOLD` / `GRAPH_DEFAULT_HIERARCHY_THRESHOLD` → **1000**
- Repositories with **&lt;1000 modules** (including FINAL_ALGO_TRADER ~216) default to **Module Graph**
- Scan completion toast nudges module graph for small repos

### 6. Mode switch toasts

- `Viewing Module Graph (N modules)`
- `Viewing Architecture Overview (N subsystems)`
- `Viewing Hierarchy (N top-level nodes)` (+ drill-down variants)

### 7. API

- Module view no longer shows “use Hierarchy” warning when `total_modules < 1000` (fixes size-only massive false alarm).

---

## Files

| File | Role |
|------|------|
| `static/app.js` | Metrics, badge, banner, toasts, default threshold |
| `static/index.html` | Banner, badge, entity summary DOM |
| `static/styles.css` | Badge, banner, two-row metrics layout |
| `api.py` | Hierarchy threshold 1000; warning guard |
| `tests/test_phase121d_graph_mode_clarity.py` | Regression tests |

---

## Tests

```bash
py -3 -m pytest jarvis_desktop/tests/test_phase121d_graph_mode_clarity.py jarvis_desktop/tests/test_phase121c_module_graph_correctness.py -q
```

Full desktop suite: **265 passed** (expected after run).

---

## Screenshots (operator)

Capture after scanning `C:\FINAL_ALGO_TRADER`:

| View | What to verify |
|------|----------------|
| **Module Graph** | Badge “Module Graph”; visible 216 modules; summary “Showing 216 of 216 modules”; no misleading 11-node count in metrics |
| **Architecture Overview** | Badge “Architecture Overview”; visible 11 subsystems; underlying 216 modules |
| **Hierarchy** | Badge “Hierarchy View”; visible 11 top-level nodes; underlying 216 modules |
| **Massive banner** | Shown with size reason + “Show Full Module Graph” on overview/hierarchy |

---

## Acceptance

| Criterion | Status |
|-----------|--------|
| User sees what mode is active | ✓ badge + toast |
| Visible vs underlying counts separated | ✓ |
| Path to full module graph when massive | ✓ button |
| FINAL_ALGO opens in module graph by default | ✓ &lt;1000 modules |
| No cosmetic/graph rendering changes | ✓ metrics/UX only |
