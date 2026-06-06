# Phase 174F — Build Gate Trace (A7_unsupported_repo_shallow_graph)

**Date:** 2026-06-05  
**Attack:** 174E A7 — Go repo with incidental `hack/boilerplate.py` helper  
**174E result:** Build `ok=true`, Investigation `ok=false` (`insufficient_evidence`)

## Repository state at attack time

| Variable | Value |
|----------|-------|
| `scan.file_count` | 3 |
| `scan.module_count` | 1 |
| `scan.dependency_edges` | 0 |
| `graph_health.label` | `healthy` (Go dominates; Python helper only) |
| `_shallow_unsupported_coverage()` | `True` → gate status `insufficient_evidence` |
| Helper file | `hack/boilerplate.py` with `def helper(): return 1` |

## Routes compared

| Route | Entry | Post-plan gate |
|-------|-------|----------------|
| Build | `POST /api/plan/change` → `api.plan_change()` | `gate_weak_graph_workflow(..., "build")` |
| Investigation | `POST /api/investigate` → `api.investigate_symptom()` | `gate_weak_graph_workflow(..., "investigate")` |

Both routes share the same planning → gate pipeline:

```
api.plan_change / api.investigate_symptom
  └─ planning_engine.plan_change / investigate_symptom
  └─ trust_integrity.gate_weak_graph_workflow
       └─ weak_graph_gate_applies → (True, "insufficient_evidence")
       └─ evidence check → DIVERGENCE WAS HERE (pre-174F)
```

## Where Investigation refused (174E)

**Call stack:**

```
api.investigate_symptom(symptom)
  planning_engine.investigate_symptom → {ok: True, plan: {...}}
  gate_weak_graph_workflow(state, result, "investigate")
    weak_graph_gate_applies → True, "insufficient_evidence"
    _has_exact_investigation_evidence(state, plan)  [pre-174F]
      → checked hypotheses/files + repository_evidence only
      → no symbol/import match on Go paths
    → return {ok: False, status: "insufficient_evidence", confidence: "low"}
```

**Condition:** Gate applied; investigation evidence path found no qualifying file/symbol proof.

## Where Build bypassed (174E — pre-fix)

**Call stack:**

```
api.plan_change(request)
  planning_engine.plan_change → {ok: True, plan: {files_to_inspect_first: ["hack/boilerplate.py"], ...}}
  gate_weak_graph_workflow(state, result, "build")
    weak_graph_gate_applies → True, "insufficient_evidence"
    _has_exact_file_evidence(state, plan)  [pre-174F]
      → _file_has_graph_symbol_evidence(state, "hack/boilerplate.py")
           symbols: ["helper"] present in evidence_store
           graph edges: repository→module, module→function (type "contains")
           OLD RULE: any resolved edge touching module counted as evidence
    → return result unchanged (ok=true)   ← BYPASS
```

**Bypass branch:** `_file_has_graph_symbol_evidence()` treated **`contains`** edges (repository→module, module→function) as resolved graph evidence when symbols existed on the incidental Python helper.

**Variable values at bypass:**

| Check | Value |
|-------|-------|
| `weak_graph_gate_applies` | `(True, "insufficient_evidence")` |
| `plan.files_to_inspect_first` | `["hack/boilerplate.py"]` |
| `symbols on helper` | `["helper"]` |
| `import edges (type=imports)` | 0 |
| `contains edges touching module` | 2 (resolved) |
| `_has_exact_file_evidence` (old) | `True` ← false positive |

## 174F fix

**File:** `jarvis_desktop/trust_integrity.py`

1. `_has_import_graph_evidence()` — only `type == "imports"` with `resolved=True` on the target **module** node counts.
2. `_weak_graph_evidence_allows()` — single strict rule used by both Build and Investigation.
3. `_file_has_graph_symbol_evidence()` — no longer counts `contains` edges; requires import graph evidence for weak-gate escape.

**Post-fix call stack (both routes):**

```
gate_weak_graph_workflow
  weak_graph_gate_applies → (True, "insufficient_evidence")
  _weak_graph_evidence_allows(state, plan, workflow)
    _has_import_graph_evidence("hack/boilerplate.py") → False (no import edges)
  → {ok: False, status: "insufficient_evidence", confidence: "low"}
```

## Requirement verification

| Requirement | Post-174F |
|-------------|-----------|
| Unsupported graph + insufficient evidence → never `ok=true` | ✅ Build and Investigation both refuse |
| Build and Investigation behave identically | ✅ Same `_weak_graph_evidence_allows()` |
| Real import evidence on weak label may still succeed | ✅ Only when `type=imports` resolved edges exist |
