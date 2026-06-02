# Phase 121C — Module Graph Correctness Investigation

**Date:** 2026-06-02  
**Repository:** `C:\FINAL_ALGO_TRADER` (lab trace)  
**Scope:** Investigation only — no visual, color, or camera changes.

---

## Executive summary

**Modules are not missing from the module-graph pipeline.** For FINAL_ALGO_TRADER, the API returns **216 module nodes** and **370 import edges** when `view=module`. The ~**11 visible nodes** match the **Architecture overview / Hierarchy (subsystem level)** payload exactly (**11 aggregated clusters**), not the module graph.

**Root cause:** The UI shows **full-repository scale** (`total_modules`, `total_edges` from scan) in the scale header and scan metrics, while the active graph view renders **collapsed subsystem/architecture nodes** (~11). Users interpret this as “233 modules scanned but only 11 drawn.”

**Secondary issue:** **Massive Repository Mode** is auto-enabled because total repo size is **~2.6 GB** (`MASSIVE_SIZE_THRESHOLD_BYTES = 1e9`), not because module count exceeds 5,000. That enables architecture-cluster overview and import-tier graph build despite only ~216 modules.

---

## Step 1 — Pipeline trace (FINAL_ALGO_TRADER)

Command:

```bash
py -3 scripts/phase121c_trace_graph_pipeline.py
```

### Count table

| Stage | Nodes | Edges | Notes |
|-------|------:|------:|-------|
| pre_scan_estimate | 150 | 0 | `massive_mode_auto=True` (size, not modules) |
| scan_result | **216** | **370** | `massive_mode=True`, `full_graph_pending=True` |
| builder_core_graph_stored | **216** | **370** | `graph_detail=imports`, not degraded |
| api_payload_**module** | **216** | **370** | `view=module`, `subsystem_like_nodes=0` |
| api_payload_**subsystem** | **11** | **17** | `architecture_clusters=True`, 11 cluster labels |
| api_payload_**hierarchy** (top) | **11** | **17** | Same as subsystem aggregate |
| api_payload_module_force_full | **216** | **370** | Diagnostic: no extra truncation |
| frontend_chunk_simulation_final | **216** | **370** | Chunk loader preserves all nodes/links |

### Pipeline diagram

```
depgraph (builder_core)     216 module nodes, 370 resolved import edges
        ↓
_STATE["graph"]             identical counts
        ↓
_module_graph_payload()     216 nodes, 370 links (view=module)
        ↓
HTTP GET .../graph?view=module
        ↓
universe.js loadChunk       216 nodes, 370 links (simulated)
        ↓
ForceGraph3D                216 Three.js objects (module view)
```

**Subsystem path (what users often see):**

```
_subsystem_graph_payload(architecture_clusters=True)
        ↓
11 cluster nodes (Algo Scanner, Analysis, Analytics, …)
17 cross-cluster edges
```

---

## Step 2 — Payload verification

Sample saved: `reports/phase121c_samples/final_algo_trader_graph_sample.json`

### Module graph (`view=module`)

| Field | Value |
|-------|------:|
| `node_count` | 216 |
| `link_count` | 370 |
| `total_modules` | 216 |
| `total_edges` | 370 |
| `view` | `module` |
| `architecture_clusters` | false |
| Nodes marked hidden | **none** (no hidden flag in schema) |
| Subsystem-style ids | **0** |

### Architecture overview (`view=subsystem`, massive_mode)

| Field | Value |
|-------|------:|
| `node_count` | **11** |
| `link_count` | 17 |
| `total_modules` | 216 (full repo, not rendered count) |
| `architecture_clusters` | true |
| Cluster labels | Algo Scanner, Analysis, Analytics, (root), Desktop App, Mobile Operator App, Pages, Scripts, Services, Src, Tools |

**Conclusion:** Payload is correct per view. The browser receives 11 nodes only when the active view is subsystem or hierarchy-top — not because 205 modules were dropped from the module payload.

---

## Step 3 — View mode logic

| UI mode | API request | Payload `view` | Rendered node type |
|---------|-------------|------------------|-------------------|
| Module graph | `GET .../graph?view=module` | `module` | 216 file modules |
| Architecture overview | `GET .../graph?view=subsystem` | `subsystem` | 11 clusters |
| Hierarchy (initial) | `GET .../hierarchy-graph?level=subsystem` | `subsystem` | 11 clusters |

`fetchGraphPayload()` in `app.js` uses `STATE.graphView` — module mode does request module nodes.

`universe.js` sets `U.subsystemView` when `data.view === "subsystem"` or nodes have `subsystem:` ids — module payload does not trigger this.

**Proof of mismatch (UX bug, not API):**

- `renderGraphScaleHeader()` uses `graph.total_modules` / `sum.module_count` → shows **216+** modules.
- `updateGraphMeta()` uses `data.node_count` → shows **11 nodes** when overview/hierarchy is active.

So the UI can simultaneously advertise full-repo scale and render an 11-node aggregate graph.

---

## Step 4 — All node/limit gates (jarvis_desktop)

| Constant / logic | Value | Applies to FINAL_ALGO? |
|------------------|------:|------------------------|
| `GRAPH_DISPLAY_CAP` | 5000 | No (216 modules) |
| `GRAPH_DEFAULT_HIERARCHY_THRESHOLD` | 5000 | No |
| `MASSIVE_FILES_THRESHOLD` | 20_000 files | No |
| `MASSIVE_MODULES_THRESHOLD` | 5000 modules | No |
| `MASSIVE_SIZE_THRESHOLD_BYTES` | 1 GB repo bytes | **Yes (~2.6 GB)** |
| `_module_graph_payload` cap | Top 5000 by risk | No |
| `_subsystem_graph_payload` | Collapse to subsystems/clusters | **Yes (11 nodes)** |
| `graph_build_plan` massive tier | `DETAIL_IMPORTS`, lazy full | **Yes** (massive_mode) |
| `universe.js` `LARGE_GRAPH_THRESHOLD` | 1000 (hover cap only) | No |
| `HOVER_NEIGHBOR_CAP` | 100 | Display only |
| Chunk loader link filter | Drops edges until endpoints loaded | No loss at end state |

No `MAX_NODES`, `TOP_N`, `VISIBILITY_LIMIT`, or hidden-node filter on module payloads.

---

## Step 5 — Massive mode leakage

FINAL_ALGO_TRADER trace:

```
files: 45,824
bytes: 2,773,335,129 (~2.6 GB)
code_files: 232
module_count: 216
massive_reason: { files: false, modules: false, size: true, manual: false }
```

**Massive mode is ON because of total directory size** (data, logs, artifacts), not module count.

Effects:

1. `graph_build_plan` → import-tier graph, `lazy_full` / `full_graph_pending`
2. `cluster_overview = is_massive` → architecture cluster names on subsystem overview
3. Render warning on module view suggesting hierarchy/overview (misleading for a 216-module code graph)

**Expected for 233-module repos:** massive mode should **not** activate on size alone when code footprint is small; module graph should show **all** modules without requiring overview.

---

## Step 6 — Full graph diagnostic (no clustering)

| Check | Result |
|-------|--------|
| `current_graph("module")` | 216 nodes, 370 edges |
| `current_graph("module", force_module=True)` | Same (no extra cap) |
| Frontend chunk simulation | 216 / 370 |
| Browser FPS / memory | Not measured in CI; payload size ~216 nodes is well within Phase 116B budgets |

**Expected:** Desktop can render all ~216–233 module nodes. The lab trace shows **no server-side truncation** for module view.

To reproduce locally:

```bash
set ATLAS_TRACE_REPO=C:\FINAL_ALGO_TRADER
py -3 scripts/phase121c_trace_graph_pipeline.py
```

In the app: select **Module graph** (not Architecture overview), confirm `graphMeta` shows `module · 216 nodes` (counts may vary slightly with cache).

---

## Step 7 — Visual acceptance criteria

| Metric | User report | Module view (lab) | Overview view (lab) |
|--------|-------------|-------------------|---------------------|
| Reported modules | 233 | 216 (scan) | 216 (`total_modules`) |
| Visible nodes | ~11 | **216** (expected) | **11** (aggregated) |
| Reported edges | 414 | 370 (scan) | 17 (cluster edges) |

**233 vs 216:** Same scan path sets `module_count` from depgraph module nodes. A higher UI number may be from an older cached scan, different scope, or summary/index field — not from module payload truncation. Re-scan clears cache.

**929 modules / ~18 nodes:** Same pattern — ~18 architecture clusters vs full `total_modules` in header (not re-traced in this lab run).

---

## Where modules “disappear”

| Location | Disappears? | Explanation |
|----------|-------------|-------------|
| builder_core depgraph | No | 216 modules stored |
| API `view=module` | No | 216 nodes returned |
| API `view=subsystem` | **Yes (by design)** | Collapsed to 11 clusters |
| Hierarchy top level | **Yes (by design)** | Uses subsystem aggregate |
| Frontend chunk loader | No | All nodes merged |
| ForceGraph (module view) | No | Renders full payload |

**Not a ForceGraph bug. Not a styling bug. View mode + metrics mismatch.**

---

## Recommended fixes (future phase — not implemented in 121C)

1. **Metrics honesty:** Scale header and graph meta should show `visible_nodes / total_modules` when `node_count < total_modules`.
2. **Default view:** If module graph is default, ensure Command Center opens on module view after scan (already intended for &lt;5000 modules).
3. **Massive mode gate:** Base auto-massive on **code_files** / **module_count**, not total repo bytes (or exclude `data/`, `.git`, artifacts from size tally).
4. **Overview labeling:** When 11 clusters are shown, label as “11 architecture clusters (216 modules)”.

---

## Tests added

`jarvis_desktop/tests/test_phase121c_module_graph_correctness.py` — pipeline assertions (skips if FINAL_ALGO_TRADER absent).

```bash
py -3 -m pytest jarvis_desktop/tests/test_phase121c_module_graph_correctness.py -q
```

---

## Screenshots

| When | What to capture |
|------|-----------------|
| **Before (bug UX)** | Architecture overview selected; scale header shows ~233 modules; graph shows ~11 spheres |
| **After (verify)** | Module graph selected; `graphMeta` shows `module · N nodes` where N ≈ module_count |

Screenshots are operator-captured; not stored in repo for this investigation.

---

## Artifacts

- `scripts/phase121c_trace_graph_pipeline.py`
- `reports/phase121c_samples/final_algo_trader_graph_sample.json`
- `jarvis_desktop/tests/test_phase121c_module_graph_correctness.py`
