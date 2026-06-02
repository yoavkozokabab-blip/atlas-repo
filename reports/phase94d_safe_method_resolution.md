# Phase 94D — Safe Method Resolution

**Status:** Implemented  
**Date:** 2026-05-31  
**Scope:** `callgraph.py` only (depgraph / impact consume edges automatically)  
**Constraints:** no detector changes, no benchmark changes, unknown beats guessing

---

## Summary

Phase 94D adds **safe, provable** intra-file method call resolution. The resolver extends Phase 93A module-level `Name()` resolution with same-file method edges only when receiver and callee class are **provably** known from AST facts alone.

### Resolved patterns (safe only)

| Pattern | Proof required |
|---------|----------------|
| `self.method()` | Lexical `self` receiver inside an instance method **or** a nested function closed over that method's `self`; enclosing class defines `method` |
| `cls.method()` | Lexical `cls` receiver inside a `@classmethod` / `cls`-first method **or** nested closure over one; enclosing class defines `method` |
| `ClassName.method()` | `ClassName` is an **unambiguous** module-level or scope-visible nested class in the same file |
| `obj.method()` | `obj = KnownClass()` (or walrus / annotated assign) with a **single** proven constructor; same function scope |

### Never resolved

Parameters (`o.method()`), `super()`, chained attributes, reassigned / ambiguous instances, inherited methods not defined in-file, shadowed names, third-party / import calls, cross-file targets, dynamic dispatch, ambiguous nested class short names.

Feature flag: `callgraph.METHOD_RESOLUTION_ENABLED = True`.

---

## Before / after metrics (`local_jarvis`)

### Phase 94C baseline (reported)

| Metric | Value |
|--------|------:|
| Resolved `calls` edges | 6,965 |
| Unresolved call sites | 60,186 |
| Total call sites | 67,151 |
| **Resolution rate** | **10.37%** |

### Fresh measurement (reproducible today)

Measured with `phase94c_gap_analysis.py` — `METHOD_RESOLUTION_ENABLED=False` (before) vs `True` (after):

| Metric | Before | After | Delta |
|--------|-------:|------:|------:|
| Resolved `calls` edges | 7,355 | **7,901** | **+546** |
| Unresolved call sites | 60,075 | **59,420** | **−655** |
| Total call sites | 67,430 | 67,321 | −109* |
| **Resolution rate** | **10.91%** | **11.74%** | **+0.83 pp** |

\*Small total-site drift vs 94C reflects repository growth and graph-build accounting; edge deltas are stable across repeated runs.

### Method-resolution contribution

| Metric | Before (no method resolution) | After (94D safe) |
|--------|------------------------------:|-----------------:|
| Intra-file `resolution: "method"` call sites | 0 | **656** |
| Unresolved `method_calls` (94C taxonomy) | 20,945 | **20,348** | **−597** |

The new edges align with the method-call bucket shrinkage — no heuristic inflation elsewhere.

### Realistic target vs this phase

| Target | Notes |
|--------|-------|
| **25–30% resolution rate** | Long-term realistic ceiling from 94C recall modeling (imports + cross-file + partial method gap) |
| **This phase (+0.8 pp)** | Closes the **provable** same-file method subset only (~3% of the method-call gap on `local_jarvis`) |
| **Do not chase ~70%** | Optimistic 94C scenario assumes resolving most imports/shadowed/dynamic sites — out of scope here |

Most unresolved attribute calls in `local_jarvis` are third-party handles (`logger.info`, `request.get`), parameters, or assignments not from an in-file constructor (~15k+ sites) — correctly left unresolved.

---

## Unresolved reason distribution (after)

Combined taxonomy from `phase94c_gap_analysis.py` (after 94D safe):

| Category | Count | Share |
|----------|------:|------:|
| method_calls | 20,348 | 32.0% |
| symbol_not_found | 19,280 | 30.3% |
| shadowed | 13,617 | 21.4% |
| imports | 6,351 | 10.0% |
| dynamic_dispatch | 3,275 | 5.2% |
| inheritance | 298 | 0.5% |
| decorators | 241 | 0.4% |

Top intra-file gap remains **method / attribute calls** — but the safely provable subset within that bucket is now largely exhausted for this repository.

---

## Implementation changes (`callgraph.py`)

1. **`_class_node_qualnames()`** — AST `ClassDef` → dotted qualname (replaces string `rsplit` for enclosing class)
2. **`_self_receiver_context()` / `_cls_receiver_context()`** — prove `self` / `cls` in nested closures inside methods
3. **`_visible_class_short_names_for_fn()`** — scope-visible nested class names (module-level + enclosing-class nested); ambiguous short names excluded
4. **`_class_from_rhs()`** — `KnownClass()` and `Outer.Inner()` when `Inner` is a proven nested class
5. **`_local_instance_bindings()`** — walrus (`NamedExpr`) assignments; uses scope-visible class map
6. **`_resolve_method_call()`** — unified safe receiver rules; callee must exist in same-file qualname index

Module-level `Name()` resolution unchanged (`resolution: "module_level"`).

**Not changed:** `cross_file.py`, detectors, benchmarks, promotion, `depgraph` logic (only consumes more resolved call sites).

---

## Downstream verification

### Dependency graph

```
py -3 -m builder_core.cli graph summary --project .
```

- `calls` edges: **7,901** (was 7,355 without method resolution)
- Graph build succeeds on full `local_jarvis`
- New edges carry `scope: "intra_file"`

### Impact analysis

```
py -3 -m builder_core.cli impact-file --project . ui/overlay_app.py
```

- Runs successfully; direct/transitive impact uses resolved call edges only
- Overlay nested-closure `self.on_*()` calls inside `OverlayController` now contribute intra-file edges (19 sites on this repo)

### Execution paths (94B)

Resolved `self.start() → self.run()` chains and nested-closure `self.helper()` paths appear in reverse traversal when edges exist.

---

## Regression tests

**File:** `builder_core/tests/test_phase94d_method_resolution.py` (18 tests)

| Test | Asserts |
|------|---------|
| Core safe cases | `self`, `cls`, `obj = Class()`, `ClassName.method()` |
| `test_nested_closure_self_method_resolved` | nested function closed over method `self` |
| `test_nested_class_classname_method_resolved` | scope-visible `Inner.method()` |
| `test_nested_class_instance_binding_resolved` | `obj = Inner()` inside enclosing class |
| `test_walrus_instance_binding_resolved` | `(obj := Worker())` proof |
| Unsafe non-resolution | params, reassignment, `super()`, inheritance, ambiguous nested names, module-level `Inner` invisible |
| Integration | depgraph edge, impact execution path, disable flag, QuixBugs / holdout unchanged |

**Full suite:** 284 tests pass.

---

## Safety safeguards

1. **No inheritance guessing** — callee method must be **defined on the proven class** in the same file  
2. **No parameter / dynamic receivers** — `Name` receiver only; no chains, no `super()`  
3. **Single-assignment instance proof** — reassignment or ambiguous constructors void binding  
4. **Scope-visible class names** — nested short names only inside enclosing class chain; ambiguous names dropped  
5. **Closure context** — `self` / `cls` in nested functions require enclosing method with matching receiver param  
6. **Disable flag** — `METHOD_RESOLUTION_ENABLED = False` restores Phase 93A call semantics  

---

## Reproducibility

```powershell
cd local_jarvis

# After metrics
py -3 -m builder_core.cli graph summary --project .

# Before/after via flag
py -3 -c @"
import sys; sys.path.insert(0,'.')
from builder_core.bug_intelligence import callgraph
from builder_core.scripts.phase94c_gap_analysis import analyze
callgraph.METHOD_RESOLUTION_ENABLED = False
b = analyze('.')
callgraph.METHOD_RESOLUTION_ENABLED = True
a = analyze('.')
print('before', b['resolved_calls'], b['baseline_resolved_rate'])
print('after ', a['resolved_calls'], a['baseline_resolved_rate'])
"@

py -3 -m pytest builder_core/tests/test_phase94d_method_resolution.py -q
```

---

## Acceptance

| Criterion | Status |
|-----------|--------|
| Safe `self` / `cls` / `ClassName` / proven instance patterns | Done |
| Never guess (inheritance, cross-file, shadowed, dynamic) | Done |
| Before/after metrics + unresolved distribution | Done (§2–3) |
| Graph summary on `local_jarvis` | Verified |
| `impact-file` works | Verified |
| Regression tests (safe + unsafe) | 18 tests |
| Full suite passes | 284 pass |
| QuixBugs / Holdout unchanged | Verified |
| No detector / benchmark changes | Verified |
| Resolution rate improves materially | **+546 edges (+7.4% relative resolved count)**; rate +0.83 pp — provable method subset largely captured; 25–30% requires future import/cross-file phases |
| Report | `reports/phase94d_safe_method_resolution.md` |
