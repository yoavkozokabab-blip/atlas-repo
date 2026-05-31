# Phase 93C — Cross-file Interprocedural Infrastructure (Implementation)

**Status:** Implemented and verified. Infrastructure only.
**Date:** 2026-05-30
**Design:** `reports/phase93c_cross_file_callgraph_design.md`
**Scope:** Cross-file call resolution into a parallel, unconsumed fact namespace.
No detector / benchmark / finding / promotion changes; no knowledge graph; no LLM.

---

## 0. TL;DR

- Added `module_map.py`, `imports.py`, `cross_file.py`: an **ephemeral,
  import-table-driven, project-scoped** cross-file resolver.
- Resolves **only** directly-imported `func()` and module-handle `mod.func()`
  calls with a **single project candidate**. Star / ambiguous / third-party /
  shadowed / dynamic / symbol-not-found → **explicit UNRESOLVED**.
- Facts land under **`interproc.cross_file`** and are consumed by **no detector**.
- Active **only in project mode** (`analyze_repository`); `analyze_source`
  (and the benchmark) pass no context → unchanged.
- **QuixBugs 12 TP / 0 FP, Holdout 2 TP / 0 FP — unchanged.** Full suite:
  **171 passed**. One feature flag disables all cross-file behavior.

---

## 1. New modules

- **`module_map.py`** — repo path ↔ dotted module path for the common layout
  (`pkg/mod.py` ↔ `pkg.mod`, `pkg/__init__.py` ↔ `pkg`). Non-identifier path
  segments and any dotted name two files would share are dropped → UNRESOLVED.
- **`imports.py`** — per-file **import table** from MODULE-LEVEL imports only:
  `from pkg.mod import f [as a]` → direct; `import pkg.mod [as m]` → module
  handle; `from .mod import f` / `from . import mod` → relative (resolved against
  the file's package directory). Records `has_star` and `ambiguous` (a local name
  bound from two different targets). Imports inside functions/try/conditionals are
  not collected → those calls stay UNRESOLVED.
- **`cross_file.py`** — the resolver + project-context builder. Reuses the 93A
  call-site helpers (qualnames, bound-name shadowing, usage classification) to
  classify how each resolved cross-file call's **result** is used.

## 2. Exact resolution + explicit UNRESOLVED

A call resolves only when it maps, via the import table, to **exactly one**
project `FunctionId = (file, qualname)`:

| Form | Resolves |
|---|---|
| `func()`, `func` directly imported, unshadowed, single candidate | → callee module-level function |
| `mod.func()`, `mod` an imported module handle, single candidate | → callee module-level function |

UNRESOLVED reasons recorded per file: `star_import`, `ambiguous_import`,
`third_party_or_unknown_module`, `symbol_not_found`, `shadowed`,
`dynamic_or_complex`. **No name-only global lookup — unknown beats guessing.**

## 3. Fact namespace (parallel, unconsumed)

`interproc.cross_file` (attached per file in project mode):
- `usage_by_callee` — for functions **defined in this file**, how cross-file
  callers use the result (`uses_return` / `null_checked` / `dereferenced`);
- `outgoing` — resolved cross-file calls made from this file;
- `unresolved` — explicit cross-file UNRESOLVED reasons;
- `enabled`.

The intra-file 93A facts (`interproc.call_graph`, `interproc.summaries`) are
**untouched**. The 93B `inconsistent_return` detector still reads only the
intra-file `usage_by_callee`, so **no detector consumes cross-file facts** — proven
by `test_no_detector_consumes_cross_file`: a helper with the missing-return shape
and a cross-file deref-caller stays `kind=pattern` (quarantined).

## 4. Engine wiring (additive; benchmark-safe by construction)

- `analyze_source(..., project_context=None)`: when a context is supplied
  (project mode), attaches the file's `cross_file` slice; when `None`
  (single-file, and the per-file benchmark path) attaches nothing → identical to
  before.
- `analyze_repository`: builds the project context once (behind
  `cross_file.CROSS_FILE_ENABLED`) and threads it into each file's analysis.
- The benchmark calls `analyze_source` per file with no context → cross-file is
  never even built for it → verdict cannot move.

## 5. Feature flag + rollback

`cross_file.CROSS_FILE_ENABLED = True`. Setting it `False` makes
`build_project_context` return `None` → `analyze_repository` threads `None` → no
`cross_file` key anywhere (`test_feature_flag_disables_all_cross_file`). Because
no detector reads these facts, disabling can never change a finding or a number.
The three modules + the project pre-pass are independently revertible.

## 6. Safety / bounds

- Read-only, deterministic (fixed file order; `test_resolution_is_deterministic`).
- Cross-file cycles terminate (`test_cross_file_cycle_terminates`).
- Hard caps (`_MAX_FILES`, `_MAX_FUNCTIONS`) → degrade to no context.
- Ephemeral: built per `analyze_repository` run, never persisted/queried — **not**
  a repository knowledge graph.

## 7. Results

| Check | Result |
|---|---|
| `pytest builder_core/tests/ -q` | **171 passed** (155 + 16 new) |
| QuixBugs (unified) | **12 TP / 0 FP** (unchanged) |
| Holdout (unified) | **2 TP / 0 FP** (unchanged) |
| `bug-scan` (project mode, cross-file active) | findings unchanged |
| Detector consuming cross-file facts | **none** |
| Disable feature | one flag removes all cross-file behavior |
| Security smoke | passed (static only) |

Acceptance: ✅ all tests pass · ✅ QuixBugs 12/0 · ✅ Holdout 2/0 · ✅ no detector
consumes cross-file facts · ✅ disabling the feature removes all cross-file behavior.

## 8. Tests (`test_phase93c_cross_file.py`, 16)

Direct / module / relative imports resolve; star / ambiguous / third-party /
shadowed / symbol-not-found are UNRESOLVED with explicit reasons; determinism;
cross-file cycle terminates; single-file has no `cross_file` key; project mode
attaches it; **no detector consumes it** (helper stays quarantined); feature-flag
disables all of it; QuixBugs/holdout parity.

## 9. Honest notes / limitations

- **No recall movement.** Cross-file facts are unconsumed; this is infrastructure.
  The capability to *use* cross-file usage in promotion is a future, separately-
  gated phase (resolution-precision + 0-FP + parity gates, per the design).
- **Conservative coverage.** Methods, inheritance, decorators, dynamic/conditional
  imports, star imports, and unusual package layouts are UNRESOLVED by design — a
  recall cost paid to never invent an edge.
- **Intra-file 93A unchanged**; cross-file summary *propagation* (the design's §8)
  is deferred until a consumer needs it (the resolved edges + usage are sufficient
  infrastructure for the next gated phase).

## 10. Next

A gated cross-file consumer phase: wire `inconsistent_return` (and later
cross-function nullability/taint) to read `interproc.cross_file.usage_by_callee`,
behind a resolution-precision gate, a 0-FP gate on a multi-file corpus, and the
benchmark-parity gate.
