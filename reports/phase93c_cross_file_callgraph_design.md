# Phase 93C — Cross-file Call Graph (Design Only)

**Status:** Design only. No code, no findings, no detector promotion.
**Date:** 2026-05-30
**Context:** 93A commit `fcbdf7b6`, 93B commit `eec4ab5c`. 155 tests passing.
QuixBugs 12 TP / 0 FP, Holdout 2 TP / 0 FP. The 93B `inconsistent_return`
promotion gate works at 0 FP but fires on **0 corpus files** because analysis is
intra-file: callers live in other files and are therefore invisible.
**Goal:** the *smallest safe* cross-file extension to the 93A layer.

---

## 0. TL;DR

- Cross-file is the next lever because every 93B promotion needs a caller, and
  callers usually live in other files. Today the engine sees one file at a time.
- The extension is **additive, project-scoped, and parallel**: it populates a new
  `interproc.cross_file` fact namespace **only** in project-analysis mode. The
  single-file path (`analyze_source`) — and therefore the benchmark — is byte-for-
  byte unchanged.
- **FunctionId needs no extension** (`(file, qualname)` is already globally unique).
- Resolution authority is an explicit **import table**; only unambiguous
  imported-name and `module.attr` calls resolve. Everything else stays UNRESOLVED.
- **No detector reads cross-file facts in 93C.** The 93B detector keeps reading the
  intra-file usage set, so no verdict can move. A future, separately-gated phase
  flips the consumer behind its own 0-FP gate.

---

## 1. Why cross-file is the next lever

The 93B promotion rule is *"promote iff a resolved caller dereferences the result
and none null-checks it."* That decision can only be made about callers the
analyzer can see. The engine's measured entry point analyzes a **single file**, so:

- In QuixBugs/holdout, each algorithm lives alone in its file; its callers are the
  test harness in a different file → 0 visible callers → every finding quarantines.
- In real repositories, the caller of a helper is almost always in another module.

So the 93B capability is *dormant on real code* until callers across files become
visible. Cross-file resolution is the single change that activates it — and it is
also the prerequisite for any future cross-function taint or nullability work.

> Honest caveat: cross-file is *necessary but not always sufficient* for these
> corpora. QuixBugs test callers do `r = f(...); assert r` — a truthiness check,
> which the usage classifier treats as a null-check → still quarantined. So
> cross-file is expected to add **0** QuixBugs promotions and is justified by real
> repositories and multi-file holdout cases, not by a QuixBugs number. The design
> must not be sold on recall it will not produce here.

## 2. Preserve intra-file behavior exactly

The engine has two entry points; the split is the safety mechanism:

- **`analyze_source(text, rel_path)`** — single file, **no project context**. The
  cross-file resolver has nothing to resolve against, so it produces nothing and
  the result is identical to today. The QuixBugs/holdout benchmark calls
  `analyze_source` per file independently → **benchmark behavior is unchanged by
  construction.**
- **`analyze_repository(root)`** (used by `bug-scan`) — gains an optional
  project **pre-pass** that builds the project module map, import tables, and a
  cross-file call/summary table, then passes that context into each file's
  analysis so it can populate `interproc.cross_file`.

Cross-file is therefore *only* reachable through the multi-file path, never
through the per-file benchmark path. Intra-file `interproc` facts (93A/93B) are
left untouched.

## 3. Function identity — no extension needed

`FunctionId = (file, qualname)` with `file` a repo-relative POSIX path is already
**globally unique within a project**. Cross-file resolution maps a call to one of
these existing identities; it invents no new identity scheme. The only new
structures are *indexes over* existing FunctionIds (§4) — not a change to identity.

## 4. New structures: project module map + per-file import tables

Two ephemeral, deterministic structures, built once per project pass:

- **Project module map** — repo-relative path ↔ dotted module path for the common
  package layout (`pkg/mod.py` ↔ `pkg.mod`, honoring `__init__.py` packages). Any
  layout that is ambiguous (namespace packages, `src/` rewrites, generated paths)
  is **left out of the map**, making calls into it UNRESOLVED.
- **Per-file import table** — for each file, map local names → a candidate target
  `(module path, qualname)`:
  - `from pkg.mod import func [as alias]` → `alias|func` → `(pkg.mod, func)`
  - `from .mod import func` / `from . import mod` → resolved relative to the file's
    package
  - `import pkg.mod [as m]` → `m`/`pkg.mod` is a *module* handle for `m.func()`

The import table is the **only** resolution authority (§6).

## 5. Safe resolution rules

A cross-file call resolves **only** when it maps, through the import table and
module map, to **exactly one** project FunctionId:

| Call form | Resolves when |
|---|---|
| `func(...)` where `func` is a directly-imported name | the import target module is in the project and defines module-level `func`; `func` not shadowed locally |
| `mod.func(...)` where `mod` is an imported module handle | the module is in the project and defines module-level `func` |

**Explicitly UNRESOLVED (no exceptions):** star imports (`from m import *`),
re-exports through `__init__`, aliased/conditional/`importlib` dynamic imports,
calls on variables or unknown-object attributes, **method** calls, third-party /
stdlib targets (not in the project), shadowed names, and **any case with 0 or >1
candidate FunctionIds**. Unresolved calls are counted exactly as in 93A and widen
summaries to UNKNOWN.

Class methods, inheritance, and decorators are out of scope → UNRESOLVED. This is
a deliberate recall cost.

## 6. No package-wide guessing

Resolution never does a name-only global lookup. The presence of a function named
`foo` somewhere in the project does **not** resolve a bare `foo()` — only an
explicit import of that `foo` does. If the import table yields no target, the call
is UNRESOLVED. **Unknown beats guessing**, every time.

## 7. Parallel, unconsumed facts (why no detector/verdict can move)

Cross-file results are written to a **new, separate namespace**:
`interproc.cross_file = { call_graph, summaries, usage_by_callee }`. The existing
`interproc.call_graph` / `interproc.summaries` remain **intra-file only and
unchanged**.

The 93B `inconsistent_return` detector continues to read **only** the intra-file
`usage_by_callee`. It does **not** read `interproc.cross_file` in 93C. Therefore:
- no detector code changes;
- no promotion decision changes;
- no benchmark verdict changes — guaranteed twice over (the benchmark never builds
  a project context, *and* the detector ignores cross-file facts even if present).

A future phase (§10) is the *only* place the detector is wired to merge cross-file
usage, behind its own gate.

## 8. Cross-file summary propagation

Reuse the 93A machinery verbatim, widened across files:
- the same bounded lattices (`return_nullability`, `may_raise`, `taint_signature`);
- the same monotone worklist with **widen-to-UNKNOWN on ambiguity** (an unresolved
  cross-file callee widens exactly like an unresolved intra-file one);
- the same determinism (fixed file ordering) and bounded iteration cap; cross-file
  cycles terminate by the same monotonicity argument.
- **Hard caps**: max project functions, max edges, time budget. Over the cap →
  the project pass degrades to **intra-file only** (today's behavior), never partial
  guessing.

## 9. No repository knowledge graph

Everything in §4/§8 is **ephemeral**: built at the start of a project analysis,
held in memory, discarded at the end. It is never persisted, indexed for queries,
or exposed as a product surface. It is analysis scaffolding, not a knowledge graph.

## 10. Promotion gates for future consumers

Before any future phase lets a detector read `interproc.cross_file`, it must pass:

1. **Resolution-precision gate.** On a labeled multi-file fixture set, sampled
   resolved cross-file edges must be **100% correct** (no mis-resolution). A single
   wrong edge → resolver stays UNRESOLVED-only.
2. **0-FP detector gate** (same shape as 93B). With cross-file usage informing
   promotion, **0 false positives** on the correct/fixed side of a *multi-file*
   corpus (new fixtures + any multi-file holdout cases). Any FP → keep the consumer
   on intra-file usage; do not enable cross-file consumption.
3. **Benchmark parity gate.** QuixBugs 12 TP / 0 FP and Holdout 2 TP / 0 FP must
   remain unchanged.
4. **Kill-switch.** A single flag disables cross-file consumption instantly; the
   resolver itself has a separate flag to fall back to intra-file-only.

Only with all four green may a consumer be promoted — and only that one consumer.

## 11. Tests — tiny multi-file fixtures

Each test builds a small temp project (2–3 files) and asserts resolution and
namespacing. No real corpus needed for the infrastructure tests.

- `from m import f; f()` → resolves to `m.py::f`.
- `import m; m.f()` → resolves to `m.py::f`.
- `from .m import f` (package with `__init__.py`) → resolves.
- `from m import *; f()` → **UNRESOLVED**.
- two modules each defining `f`, imported ambiguously → **UNRESOLVED**.
- third-party / stdlib import (`from os import getcwd; getcwd()`) → **UNRESOLVED**
  (target not in project).
- locally shadowed imported name → **UNRESOLVED**.
- cross-file facts land under `interproc.cross_file`; intra-file `interproc`
  facts are **bit-identical** to the no-cross-file run.
- `analyze_source` on a single file produces **no** `cross_file` key.
- cross-file summary propagation is deterministic and terminates on a 2-file cycle.
- **benchmark parity**: QuixBugs 12/0, Holdout 2/0 unchanged.
- **no new findings / no new kind** emitted by the project pass.

## 12. Rollback strategy

- The cross-file layer is a **new module + an optional project pre-pass**, gated by
  a flag and registered in one place (the project-pass augmenter list). Removing
  that one registration disables it; the engine reverts to pure intra-file.
- Because **no detector consumes cross-file facts in 93C**, disabling can never
  change a finding or a benchmark number.
- Independently revertible commits: (a) module map + import tables, (b) cross-file
  resolver, (c) cross-file summary propagation, (d) cross-file usage aggregation.
  Reverting any one leaves the rest working and the intra-file path intact.

## 13. Acceptance criteria (for the eventual 93C implementation)

- All existing tests pass; QuixBugs 12 TP / 0 FP and Holdout 2 TP / 0 FP unchanged.
- `analyze_source` single-file output is unchanged (no `cross_file` key, identical
  intra-file `interproc` facts).
- Cross-file resolution is conservative: every star/ambiguous/third-party/shadowed
  case resolves to UNRESOLVED (test-asserted); only explicit single-candidate
  imports resolve.
- Cross-file facts are namespaced under `interproc.cross_file` and consumed by **no**
  detector; no new finding, no new kind, no verdict change.
- Deterministic and bounded; degrades to intra-file over caps.
- Disable by removing one registration.

## 14. Files likely to change (future implementation, for reference)

**New (analysis-only, under `builder_core/bug_intelligence/`):**
- `module_map.py` — repo path ↔ dotted module path (conservative).
- `imports.py` — per-file import table extraction (safe forms only).
- `cross_file.py` — project resolver + cross-file call graph + cross-file summary
  propagation (reusing `summaries.py` lattices).

**Modified (additive only):**
- `agents.py` — a `CrossFileAgent` used **only** by the project pass; it writes
  `interproc.cross_file` and emits no findings.
- `engine.py` — an optional project pre-pass in `analyze_repository` that builds the
  context and threads it into per-file analysis. `analyze_source` unchanged.

**Explicitly NOT changed in 93C:**
- `fact_detectors.py` and every detector (no consumption of cross-file facts).
- `finding.py`, `engine_benchmark.py` verdict logic and kinds.
- The single-file path and the legacy benchmark.

---

### One-line summary

Phase 93C adds an **ephemeral, import-table-driven, project-scoped** cross-file
call graph that writes to a **parallel, unconsumed** fact namespace — activating
only in multi-file mode, resolving only explicit single-candidate imports,
leaving the single-file path and every benchmark verdict exactly as they are, and
gating any future consumer behind a resolution-precision + 0-FP + parity check.
