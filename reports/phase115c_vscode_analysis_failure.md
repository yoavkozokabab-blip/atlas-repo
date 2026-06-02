# Phase 115C — VS Code Analysis Failure Investigation

**Repository:** `C:\J.A.R.V.I.S\vscode`  
**Symptom:** Scan completes with `files > 14000`, `modules = 0`, `edges = 0`, empty graph.  
**Mode:** Investigation only (no code changes).  
**Trace artifact:** `reports/phase115c_vscode_trace.json`

---

## Executive summary

VS Code is a **TypeScript-first** repository. JARVIS Desktop’s dependency graph is built exclusively from **Python** sources via `depgraph.build_graph` → `engine._collect_python_files`. The VS Code tree contains **73 Python files**, and **all 73** are classified as **`test`** by the RU-2 role classifier (paths under `test/`, `testdata/`, etc.). Production-scope graph building therefore keeps **0 files**, producing **0 modules** and **0 edges**.

The UI “files” count comes from the **light file index** (all scoped file types, ~14.8k entries), not from graph modules. **TypeScript is not rejected** by scope; it is **never fed to the graph engine**. Massive Repository Mode does **not** skip module extraction—it runs import-only graph build on an already-empty Python production set.

This is **not** a silent parser crash, **not** a serialization drop, and **not** a Phase 115B timeout/partial failure. It is an **expected empty graph** given current Python-only + production-scope semantics on this repo.

---

## Stage-by-stage trace

| Stage | Input count | Output count | Time | Failure / reason |
|---|---:|---:|---:|---|
| **1. Repository discovery** | path `vscode` | `total_files=15035`, `code_files=11159`, `ok=true` | 294 ms | None |
| **2. Language detection** (extension census) | 15035 files | `.ts=10563`, `.tsx=262`, `.py=73`, `.js=121`, … | — | None — TS/TSX dominate; only 73 `.py` |
| **3. Pre-scan estimate** | 15035 total | `code_files=11159`, `estimated_modules=7253`, `massive_mode_auto=true` | 1322 ms | **Misleading estimate:** `estimated_modules = code_files × 0.65` counts TS/JS as “modules” though graph is Python-only |
| **4. Module extraction** (`depgraph` candidates + production filter) | 73 Python candidates | **0 production kept** (73 excluded as `test`) | 300 ms | **`no_python_production_files`** — all `.py` under test paths |
| **5. Dependency extraction** (`build_graph`, imports detail) | 0 kept files | **0 modules**, **0 import edges** | 293 ms | Empty graph; `degraded=false`, `files_kept=0` in scope diagnostics |
| **6. Graph build policy** (`graph_build.py`) | `code_files=11159`, massive auto | tier=`massive`, `detail=imports`, `lazy_full=true` | — | Policy applied; **does not cause zero modules** |
| **7. Light index** (`_light_index`) | walk repo | **14871** indexed files | 1330 ms | Indexes TS/JS/CSS/etc.; `python_analysis=[]` |
| **8. Risk analysis** (`architectural_risk.rank_modules`) | graph with 0 modules | 0 ranked modules | 821 ms | No crash; ranks empty set |
| **9. Graph serialization** (`current_graph`) | empty graph state | `node_count=0`, `link_count=0`, `total_modules=0`, `ok=true` | &lt;1 ms | **Faithful empty payload** — not dropped in UI layer |
| **10. Full desktop scan** | end-to-end | `file_count=14871`, `module_count=0`, `dependency_edges=0` | 4637 ms | Scan `ok=true` despite empty graph |

---

## Investigation questions (requirements checklist)

### Where do modules become zero?

**Stage 4 — `depgraph._production_scope_filter`** in `builder_core/bug_intelligence/depgraph.py`, called from `build_graph()` with default `scope=production`, `include_tests=False`.

```
Python candidates: 73
Production kept:   0
Excluded by role:  { "test": 73 }
```

`scan_repository` sets `module_count = len([n for n in graph["nodes"] if n["type"] == "module"])` → **0**.

### Does language detection reject TypeScript?

**No.** `_CODE_EXTENSIONS` in `jarvis_desktop/api.py` includes `.ts`, `.tsx`, `.js`, etc. Pre-scan and validation **count** them as `code_files`. They are included in the light index walk.

**However**, module/dependency extraction uses **`engine._collect_python_files`** (`.py` only). TypeScript is never parsed for the dependency graph.

### Do scope filters exclude `.ts` / `.tsx`?

**Default scope `entire_repo`:** does **not** exclude TypeScript from file indexing.  
**`python_only` scope:** would exclude non-`.py` from `_light_index` / estimate, but graph would still be Python-only.

Graph emptiness is **not** caused by scope excluding TS; it is caused by **no production Python** after role filter.

### Does Massive Repository Mode skip module extraction?

**No.** For VS Code, `graph_build_plan` selects:

- `tier: massive`
- `detail: imports` (import-only fast path)
- `time_budget_sec: 60`
- `lazy_full: true`

Graph build completed in **0.38s** with **0 modules**. Massive mode changes **how** the graph is built, not **whether** Python production files exist.

### Are parser failures occurring silently?

**No Python production files reach `ast.parse`.** The 73 Python files are excluded before parsing. TypeScript is never submitted to a parser in this pipeline.

### Does `graph_build.py` return degraded/partial state?

**No.** Trace shows:

- `degraded: false`
- `jarvis_timed_out: false`
- `jarvis_partial: false`
- `scope_diagnostics.degraded: false`
- `files_kept: 0`

The scan reports success with an **empty but non-degraded** graph—a **semantic gap** (empty vs degraded) worth addressing in a future phase, not investigated as a bug fix here.

### Does graph payload generation drop results?

**No.** `current_graph("subsystem")` and `current_graph("module", force_module=True)` both return `ok: true` with zero nodes/links. Serialization reflects backend state accurately.

---

## Why Django / FastAPI work but VS Code does not

| Repo | Primary language | Python prod files (approx.) | Graph modules |
|---|---|---:|---:|
| Django | Python | 911 (production scope) | 911 |
| FastAPI | Python | hundreds+ | non-zero |
| VS Code | TypeScript | **0** (73 test-only `.py`) | **0** |

Django/FastAPI match the **Python production dependency graph** model. VS Code does not.

---

## Sample evidence: all Python paths are `test`

Every `.py` file under `vscode` is role-classified `test`, e.g.:

- `extensions/copilot/test/scenarios/.../*.py`
- `extensions/copilot/.../testdata/.../*.py`
- `extensions/copilot/.../fixtures/.../*.py`

Classifier rule (path segment in `_TEST_PARTS`): `repository_understanding.classify_file_role` → `test` when path contains test directories.

---

## Metric mismatch (UI confusion)

| Field | VS Code value | What it actually measures |
|---|---:|---|
| `file_count` | 14871 | All files in light index (multi-language) |
| `code_files` (validation/estimate) | 11159 | Files with extensions in `_CODE_EXTENSIONS` |
| `files_discovered` (scan) | 73 | Python files seen by depgraph (`scope_diagnostics.total_candidate_files`) |
| `module_count` | 0 | Python **module nodes** in dependency graph |
| `estimated_modules` (pre-scan) | 7253 | Heuristic `code_files × 0.65` — **includes TS, not graph-backed** |

Users see **large file counts** and **zero modules** because two different counting models are surfaced without explaining Python-only graph scope.

---

## Files / functions involved

| Concern | Location |
|---|---|
| Python-only collection | `builder_core/bug_intelligence/engine.py` → `_collect_python_files` |
| Production scope filter | `builder_core/bug_intelligence/depgraph.py` → `_production_scope_filter`, `build_graph` |
| Module count source | `jarvis_desktop/api.py` → `scan_repository` (`module_nodes` from graph) |
| Multi-language file index | `jarvis_desktop/api.py` → `_light_index`, `_count_code_files`, `pre_scan_estimate` |
| Role classification | `builder_core/repository_understanding.py` → `classify_file_role` |
| Graph tier policy | `jarvis_desktop/graph_build.py` → `graph_build_plan`, `build_scan_graph` |
| UI graph payload | `jarvis_desktop/api.py` → `current_graph`, `_subsystem_graph_payload` |

---

## Conclusion (root cause)

**Primary:** VS Code has **no Python production-scope sources** for `depgraph`; all Python is test-scoped. The dependency graph is **correctly empty** under current Builder Core semantics.

**Secondary:** **~11k TypeScript files** contribute to `code_files` and file index size but **do not participate** in module/edge extraction, creating a **false expectation** of thousands of modules.

**Not root cause:** Massive mode, import-cycle timeouts (115B), synthetic progress, graph serialization bugs, or silent parse failures.

---

## Recommended directions (documentation only — out of scope for 115C)

Future phases may consider (not implemented here):

1. **Language-aware graph** or explicit “Python graph only” UX when `files_kept == 0`.
2. **Mark scan as `degraded` or `unsupported_language_mix`** when production Python set is empty but `code_files` is large.
3. **Separate metrics:** `indexed_files` vs `graph_modules` vs `estimated_modules` with tooltips.
4. **`include_tests=True`** or TypeScript graph support if product scope expands.

---

## Verification command

Investigation trace was produced with an inline diagnostic (no production code changes). Reproduce:

```bash
cd local_jarvis
py -c "from jarvis_desktop import api; import json; r=api.scan_repository(r'C:\\J.A.R.V.I.S\\vscode'); print(json.dumps({k:r.get(k) for k in ['file_count','module_count','dependency_edges','files_discovered','graph_scope','massive_mode']}, indent=2))"
```

Expected: `module_count: 0`, `dependency_edges: 0`, `files_discovered: 73`, large `file_count`.
