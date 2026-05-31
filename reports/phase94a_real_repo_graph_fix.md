# Phase 94A Real Repository Graph Fix

## Summary

Fixed a `KeyError` on `ast.ClassDef` when building the dependency graph on `local_jarvis`. The graph CLI (`graph summary`, `graph export`) now completes successfully on the full repository.

## Reproduction

```powershell
cd local_jarvis
py -3 -m builder_core.cli graph summary --project .
```

**Before fix:**

```
KeyError: <ast.ClassDef object at 0x...>
  File "builder_core/bug_intelligence/depgraph.py", line 77, in _build_indexes
    cls_index.setdefault(mod, {})[child.name] = (rel, qn[child])
```

## Root cause

`depgraph._build_indexes()` and several later code paths looked up class nodes in `callgraph._compute_qualnames()`. That helper intentionally indexes **functions only** — it walks `ClassDef` nodes to build prefixes for nested methods but never stores the class AST node in the returned map.

Any repository with module-level classes triggers the crash. `local_jarvis` has hundreds of action/model classes; the first sorted file with a top-level class is:

| File | Class | Line |
|------|-------|------|
| `actions/app_actions.py` | `DiscoverAppsAction` | 55 |

## Fix

Added `_compute_structure_qualnames()` in `depgraph.py` — a small, depgraph-local helper that maps both `ClassDef` and function nodes to dotted qualnames (same naming rules as the callgraph walker).

Updated `depgraph.py` to use it for:

- `_build_indexes()` class (and function) symbol index
- `contains` edges for classes
- `references` edges whose owner is a class

**Not changed:** `callgraph.py`, detectors, benchmarks, promotion logic, or the bug-finding pipeline.

## Minimal failing fixture

```python
graph = build_graph_from_files("/repo", [
    ("actions/app_actions.py", "class DiscoverAppsAction:\n    pass\n"),
])
# Before fix: KeyError in _build_indexes
# After fix: one class node, qualname DiscoverAppsAction
```

## Regression tests

Added to `builder_core/tests/test_phase94a_depgraph.py`:

1. `test_module_level_class_does_not_crash` — mirrors the real-repo trigger (`DiscoverAppsAction` fixture)
2. `test_nested_class_does_not_crash` — nested `Outer.Inner` fixture does not crash; top-level class node created

## Verification

| Check | Result |
|-------|--------|
| `graph summary --project .` on `local_jarvis` | OK (no crash) |
| `graph export --project .` on `local_jarvis` | OK (JSON written) |
| Full `builder_core` test suite | **230 passed** |
| QuixBugs mini benchmark (`test_benchmark_unchanged`) | 1 TP / 0 FP |
| Holdout (`test_benchmark_unchanged`) | `available: false` (unchanged) |

**Sample `local_jarvis` graph stats after fix:**

- **9,493** nodes (1 repo, 1,408 modules, 964 classes, 7,120 functions)
- **18,966** edges (contains, imports, calls, references)
- Unresolved annotations preserved for external imports and unresolved calls

## Files changed

| File | Change |
|------|--------|
| `builder_core/bug_intelligence/depgraph.py` | `_compute_structure_qualnames()`; class qualname lookups |
| `builder_core/tests/test_phase94a_depgraph.py` | 2 regression tests |
| `reports/phase94a_real_repo_graph_fix.md` | This report |
