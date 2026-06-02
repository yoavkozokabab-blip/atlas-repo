# Phase 94E - Export Index Resolution

Date: 2026-05-31

## Status

Implemented and Builder Core verified.

Phase 94E adds a conservative project export index for cross-file callable
resolution. The implementation improves resolved call coverage without changing
detectors, benchmarks, finding promotion, browser code, voice code, or runtime
routing.

The repository-wide pytest acceptance command was attempted but did not finish
within 15 minutes. A bounded top-level test run isolated the first failure as an
unrelated pre-existing voice/audio assertion:

`tests/test_audio_route_prove.py::test_format_audio_status_user_fields`

That failure is outside the Phase 94E scope and was intentionally left
untouched.

## Safe Resolution Scope

The export index resolves only concrete project-defined callable targets:

1. `from module import symbol`
2. `import module; module.symbol`
3. Explicit and unambiguous package `__init__.py` re-exports
4. Project class construction only when the class has an explicit
   project-defined `__init__` method

The constructor edge targets the real `Class.__init__` function node. The graph
does not invent class-call nodes.

The implementation deliberately does not resolve:

- star imports
- dynamic imports
- ambiguous imported names
- third-party modules
- shadowed names
- implicit package magic
- ordinary-module re-export chains
- runtime assignment exports
- inherited or default constructors without a concrete local `__init__`

## Opportunity Inventory

Before implementation, the Phase 94D graph had `1,724` cross-file
`symbol_not_found` call sites in the sampled tree.

| Miss shape | Count |
| --- | ---: |
| Explicit imported class construction | 1,711 |
| Construction with a concrete project-defined `__init__` | 328 |
| Other imported symbol misses | 13 |
| Explicit package `__init__.py` re-export opportunity | 1 |

The safe opportunity was therefore narrow and measurable: `328` concrete
constructor targets and `1` explicit package re-export.

## Implementation

Added `builder_core/bug_intelligence/export_index.py`.

The index:

- records module-level functions;
- records classes only when they define an explicit `__init__`, mapping the
  class export to the concrete `Class.__init__` function;
- follows explicit direct imports from package `__init__.py` files;
- iterates explicit package re-export chains to a fixpoint;
- drops ambiguous bindings instead of guessing.

Updated `builder_core/bug_intelligence/cross_file.py`.

The cross-file resolver now uses the export index. The additive behavior is
guarded by `EXPORT_INDEX_ENABLED`, which provides an immediate rollback to the
legacy module-level function index.

## Before And After Metrics

Metrics were measured on the same post-edit working tree with
`EXPORT_INDEX_ENABLED=False` and `EXPORT_INDEX_ENABLED=True`. This avoids
pollution from added regression fixtures and provides an apples-to-apples
comparison.

| Metric | Flag off | Flag on | Delta |
| --- | ---: | ---: | ---: |
| Resolved calls | 7,576 | 7,905 | +329 |
| Unresolved calls | 60,057 | 59,728 | -329 |
| Total call sites | 67,633 | 67,633 | 0 |
| Resolution rate | 11.20% | 11.69% | +0.49 percentage points |
| Cross-file `symbol_not_found` | 1,744 | 1,415 | -329 |

The cross-file `symbol_not_found` reduction is `18.86%`.

## Unresolved Reason Distribution

Protected unresolved reasons remain unchanged.

| Raw unresolved reason | Flag off | Flag on | Delta |
| --- | ---: | ---: | ---: |
| `dynamic_or_complex` | 3,267 | 3,267 | 0 |
| `intra_file_unresolved` | 38,680 | 38,680 | 0 |
| `shadowed` | 13,361 | 13,361 | 0 |
| `star_import` | 1 | 1 | 0 |
| `symbol_not_found` | 1,744 | 1,415 | -329 |
| `third_party_or_unknown_module` | 3,004 | 3,004 | 0 |

## Graph And Impact Verification

`py -3 -m builder_core.cli graph summary --project .`

Completed successfully:

- nodes: `10,070`
- edges: `20,636`
- call edges: `7,905`
- unresolved calls: `59,728`

The summary now includes real constructor targets such as:

- `core/app.py::JarvisApp.__init__`
- `actions/registry.py::ActionRegistry.__init__`
- `voice/tts.py::TTSService.__init__`
- `brain/router.py::CommandRouter.__init__`

`py -3 -m builder_core.cli impact-file --project . actions/base.py --top 5`

Completed successfully with a deterministic impact report.

## Regression Coverage

Added `builder_core/tests/test_phase94e_export_index_resolution.py`.

The regression suite proves:

- direct imported explicit constructors resolve;
- module-handle explicit constructors resolve;
- explicit package re-exports resolve;
- explicit package re-export aliases resolve;
- graph constructor edges target real `Class.__init__` functions;
- default and inherited constructors remain unresolved;
- runtime assignment exports remain unresolved;
- implicit package magic remains unresolved;
- ordinary-module re-export chains remain unresolved;
- dynamic imports remain unresolved;
- ambiguous package re-exports remain unresolved;
- star imports remain unresolved;
- the rollback flag restores legacy behavior.

## Verification Results

Focused export-index, cross-file, method-resolution, dependency-graph, and
impact-analysis suite:

```text
py -3 -m pytest builder_core\tests\test_phase94e_export_index_resolution.py builder_core\tests\test_phase93c_cross_file.py builder_core\tests\test_phase94d_method_resolution.py builder_core\tests\test_phase94a_depgraph.py builder_core\tests\test_phase94b_impact_analysis.py -q -p no:cacheprovider
77 passed in 1.01s
```

Builder Core suite:

```text
py -3 -m pytest builder_core\tests\ -q -p no:cacheprovider
283 passed in 12.48s
```

QuixBugs benchmark:

```text
py -3 -m builder_core.cli benchmark-quixbugs --project C:\Repos\QuixBugs
12 TP / 0 FP
precision: 1.0
recall: 0.3
```

Holdout benchmark:

```text
py -3 scripts\run_phase84_holdout_benchmark.py
QuixBugs: 12 TP / 0 FP
Holdout: 2 TP / 0 FP / 10 FN / 12 TN
precision: 1.0
recall: 0.1667
accuracy: 0.5833
```

Repository collection:

```text
py -3 -m pytest --collect-only -q -p no:cacheprovider
1775 tests collected in 6.94s
```

Repository-wide suite attempt:

```text
py -3 -m pytest -q -p no:cacheprovider
timed out after approximately 15 minutes without a final pytest summary
```

Bounded top-level failure isolation:

```text
py -3 -m pytest tests\ -q -p no:cacheprovider --maxfail=1
1 failed, 48 passed, 4 warnings in 10.69s
FAILED tests/test_audio_route_prove.py::test_format_audio_status_user_fields
```

## Files Changed

- `builder_core/bug_intelligence/export_index.py`
- `builder_core/bug_intelligence/cross_file.py`
- `builder_core/tests/test_phase94e_export_index_resolution.py`
- `reports/phase94e_export_index_resolution.md`

## Safety Confirmation

- No detector changes.
- No benchmark changes.
- No promotion changes.
- No browser, voice, trading, website, or router changes.
- No dynamic, shadowed, ambiguous, third-party, or runtime-assignment
  resolution.
- QuixBugs unchanged.
- Holdout unchanged.
- Instant rollback is available by setting `EXPORT_INDEX_ENABLED=False`.

