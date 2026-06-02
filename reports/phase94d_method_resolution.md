# Phase 94D — Intra-File Method Resolution

**Status:** Implemented  
**Date:** 2026-05-31  
**Scope:** `callgraph.py` only (depgraph/impact consume callgraph edges automatically)  
**Constraints:** no detector changes, no benchmark changes, unknown beats guessing

---

## Summary

Phase 94D adds **proven** intra-file method call resolution to the call graph. The resolver extends Phase 93A module-level `Name()` resolution with same-file method edges when the receiver and callee class are **provably** known from AST facts alone.

Resolved patterns:

| Pattern | Proof required |
|---------|----------------|
| `self.method()` | Caller is a method; first parameter is `self`; enclosing class defines `method` |
| `cls.method()` | Receiver is `cls`; caller is `@classmethod` or first param is `cls` |
| `obj.method()` | `obj` assigned exactly once via `ClassName()` for a module-level class in the file |
| `ClassName.method()` | `ClassName` is a module-level class defined in the file |

**Never resolved:** parameters (`o.method()`), `super().method()`, chained attributes, reassigned instances, inherited methods not defined in-file, dynamic receivers.

Feature flag: `callgraph.METHOD_RESOLUTION_ENABLED = True` (set `False` to revert to Phase 93A behavior).

---

## Before / after metrics (`local_jarvis`)

Measured via `graph summary --project .` and `phase94c_gap_analysis.py`.

| Metric | Phase 94C (before) | Phase 94D (after) | Delta |
|--------|-------------------:|------------------:|------:|
| Resolved `calls` edges | 6,965 | **7,510** | **+545** |
| Unresolved call sites | 60,186 | **59,644** | **−542** |
| Total call sites | 67,151 | 67,154 | +3 |
| **Resolution rate** | **10.37%** | **11.18%** | **+0.81 pp** |

### Method-call gap (taxonomy)

| Metric | Before | After | Delta |
|--------|-------:|------:|------:|
| Unresolved `method_calls` (94C taxonomy) | 20,864 | **20,323** | **−541** |

The new edges align 1:1 with the method-call bucket shrinkage — no heuristic inflation elsewhere.

### Why not ~20k new edges?

Phase 94C counted **all** attribute calls as `method_calls`, including:

- Cross-file receivers (still unresolved at callgraph layer)
- `super()`, chained, and unknown receivers
- Calls where the callee method is not defined on the proven class in the same file

Phase 94D only resolves the **strict subset** listed above (~2.6% of prior method-call gap on `local_jarvis`).

---

## Implementation

**File:** `builder_core/bug_intelligence/callgraph.py`

1. `_build_class_method_index()` — class qualname → `{method_name: method_qualname}` from same-file `ClassDef` bodies only  
2. `_local_instance_bindings()` — variables with a **single** proven `ClassName()` assignment  
3. `_resolve_method_call()` — applies `self` / `cls` / instance / class-name rules  
4. `build_call_graph()` — emits resolved edges with optional `resolution: "method"` on call sites  

Module-level `Name()` resolution unchanged (`resolution: "module_level"`).

**Not changed:** `cross_file.py`, detectors, benchmarks, promotion, `depgraph` logic (only consumes more resolved call sites from callgraph).

---

## Impact on downstream consumers

### Dependency graph (94A)

- New `calls` edges with `scope: "intra_file"` from method caller → callee in the same file  
- Example: `Service.run → Service.compute` in fixture repos  
- `calls_unresolved` decreases proportionally; cross-file `shadowed` annotations on `self.*` attempts remain (cross_file conservative policy unchanged)

### Execution paths (94B / impact)

- Resolved `self.start() → self.run()` chains now appear in reverse path traversal  
- Fixture: `main.py::App.run` gains an execution path from `App.start` after 94D  
- `super().method()` and parameter receivers still produce **no** resolved path (correct)

### Impact analysis

- Function-level **direct dependents** now include proven intra-class callers (e.g. `C.m → C.other` when `self.other()` resolves)  
- Risk/transitive closure grows only along **resolved** edges — conservative contract preserved  
- Tests updated: impact “unresolved method” fixture uses `super().other()` instead of `self.other()`

---

## Regression tests

**New:** `builder_core/tests/test_phase94d_method_resolution.py`

| Test | Asserts |
|------|---------|
| `test_self_method_call_resolved` | `self.helper()` edge |
| `test_cls_classmethod_resolved` | `cls.factory()` edge |
| `test_local_instance_method_resolved` | `obj = Worker(); obj.helper()` |
| `test_class_name_method_resolved` | `Worker.factory()` |
| `test_parameter_receiver_stays_unresolved` | `o.helper()` not resolved |
| `test_reassigned_instance_stays_unresolved` | dual assignment blocks proof |
| `test_super_call_stays_unresolved` | no edge on `super().f()` |
| `test_depgraph_intra_file_method_edge` | depgraph `calls` edge |
| `test_execution_path_reaches_method_via_self` | impact path to target |
| `test_method_resolution_disable_restores_conservatism` | flag off → unresolved |
| `test_benchmark_unchanged` | mini QuixBugs / holdout |

**Existing suites:** 263 tests pass (93A, 94A, 94B, RU-2/3 unchanged except 94B super fixture).

---

## Safety / precision safeguards

1. **No inheritance guessing** — only methods **defined on the proven class** in the same file  
2. **No parameter typing** — `def f(o): o.m()` stays unresolved  
3. **Single-assignment instance proof** — reassignment voids binding  
4. **No chained / super / dynamic** receivers  
5. **Callee must exist in qualname index** — missing method → unresolved  
6. **Disable flag** — instant rollback to Phase 93A call semantics  

---

## Recommended follow-ups (not in 94D)

| Priority | Target | Est. additional gain |
|----------|--------|---------------------|
| P1 | Stop cross_file marking `self.*` as `shadowed` (policy fix) | cleaner unresolved taxonomy |
| P2 | Same-file nested class instance proof | small |
| P3 | Cross-file method export index | medium (94C scenario B) |

---

## Reproducibility

```powershell
cd local_jarvis
py -3 -m builder_core.cli graph summary --project .
py -3 -c "import sys; sys.path.insert(0,'.'); from builder_core.scripts.phase94c_gap_analysis import analyze; import json; print(json.dumps({k: analyze('.')[k] for k in ('resolved_calls','unresolved_calls','baseline_resolved_rate','combined_taxonomy')}, indent=2))"
py -3 -m pytest builder_core/tests/test_phase94d_method_resolution.py -q
```

---

## Acceptance

| Criterion | Status |
|-----------|--------|
| Resolve `self` / `cls` / proven instance / class-name calls | Done |
| Never guess | Done |
| Before/after metrics | Done (§2) |
| Impact on graph / paths / impact | Done (§5) |
| Regression tests | Done |
| No detector changes | Verified |
| QuixBugs / Holdout unchanged | Verified (mini fixture + 93A skips) |
