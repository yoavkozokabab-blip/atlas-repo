# Phase 93A — Interprocedural Infrastructure

**Status:** Implemented and verified. Infrastructure only.
**Date:** 2026-05-30
**Scope:** Build the interprocedural substrate. No new findings, no detector
promotion, no benchmark behavior change, no recall work, no contract inference,
no repository knowledge graph.

---

## 0. TL;DR

- Added an **ephemeral, conservative, same-file call graph** (`callgraph.py`) and
  **bounded function summaries with monotone worklist propagation**
  (`summaries.py`).
- Wired via a single `InterproceduralAgent` that **attaches facts** to the model
  and **emits zero findings**. No detector consumes them.
- **QuixBugs 12 TP / 0 FP and Holdout 2 TP / 0 FP — unchanged.** Full suite:
  **143 passed** (122 + 21 new). Disable by emptying one list.

---

## 1. Function identity model

`FunctionId = (file, qualname)`. `qualname` is the dotted path within the module:
top-level `func`, methods `Class.method`, nested `outer.inner`. Deterministic and
human-readable; no hashing. Functions are matched to value-flow facts by
definition line (unique per def).

## 2. Call graph (`callgraph.py`) — same-file direct only, no guessing

- **Resolvable target** = an unshadowed, module-level function defined in the
  same file. A bare `Name(...)` call to such a function is a **resolved edge**.
- **Everything else is UNRESOLVED**, explicitly: attribute/method calls
  (`o.method()`), calls to unknown names, and calls whose name is shadowed by a
  local parameter/assignment/nested-def. `unresolved_count` is reported.
- The graph is **ephemeral** (built per analysis, never persisted/queried) — this
  is deliberately *not* a repository knowledge graph.

## 3. Result-usage facts (the §5 deliverable)

Per resolved callee, aggregated across its call sites:
`uses_return`, `null_checked`, `dereferenced` — derived by classifying how each
call's result is consumed (`ignored` / `returned` / `null_checked` /
`dereferenced` / `used_value`), including a light scan of the assigned variable's
later uses. These are the facts a future *promoted* `inconsistent_return` will
need (contract vs forgotten return) — recorded now, consumed by nothing yet.

## 4. Summaries (`summaries.py`)

Bounded, fixed-size per function:
- `return_nullability` ∈ {definite_value, maybe_none, unknown}
- `may_raise` ∈ {no_raise, may_raise, unknown}
- `taint_signature` = {`params_to_return`, `reaches_sink`} (base-only in 93A)

## 5. Worklist propagation — monotone, widens to UNKNOWN on ambiguity

A deterministic worklist over a short lattice chain; the join only moves a value
**up** the chain, so it is monotone and converges in bounded iterations (cycles
terminate — verified by `test_recursion_terminates`).
- **Nullability** widens to **unknown** when a return-position call is unresolved
  (we cannot prove non-None). A resolved `return callee()` inherits the callee's
  nullability (`wrapper → maybe_none` from `leaf`).
- **may_raise**: a *proven* raise is the top of its chain and is never erased by
  ambiguity; an *unprovable* `no_raise` widens to **unknown** when an outgoing
  call is unresolved. (`raiser → may_raise`; `calls_unknown → unknown`.)

## 6. Wiring — additive, findings-free, disableable

`engine.analyze_source` runs the augmenter list after fact extraction:
`_fact_augmenters = [A.InterproceduralAgent()]`. The agent attaches
`module_facts["interproc"] = {call_graph, summaries}` and returns. It creates no
`Finding`, introduces no new finding kind, and is read by no detector. **Removing
the single `InterproceduralAgent()` entry** (or emptying the list) disables the
feature with zero behavior change — `test_disable_by_emptying_augmenters` proves
the `interproc` key simply disappears and findings are unaffected.

## 7. Results

| Check | Result |
|---|---|
| `pytest builder_core/tests/ -q` | **143 passed** (122 + 21 new) |
| QuixBugs (unified) | **12 TP / 0 FP** (unchanged) |
| Holdout (unified) | **2 TP / 0 FP** (unchanged) |
| New findings emitted | **none** (no `interproc` kind/rule) |
| Detector consuming new facts | **none** |
| Disable cost | remove one agent registration |

Acceptance: ✅ all existing tests pass · ✅ QuixBugs 12/0 · ✅ Holdout 2/0 ·
✅ no new findings · ✅ no detector consumes new facts · ✅ one-line disable.

## 8. Tests added (`test_phase93a_interprocedural.py`, 21)

Identity/qualname (module/method/nested); resolution conservatism (direct
resolved; method/unknown/shadowed → unresolved); usage facts (null_checked /
dereferenced / ignored); summaries (nullability base + propagation +
unknown-widening; may_raise explicit + propagation + widening; taint_signature
present); determinism; cycle termination; engine attaches `interproc`; engine
emits no interproc finding; disable-by-emptying; QuixBugs/holdout parity.

## 9. Limitations (by design)

- **Intra-file only.** Cross-file resolution is a later, separately-gated stage.
- **Conservative recall.** Nested-function and method targets are UNRESOLVED on
  purpose (no guessing) — a recall cost paid to never invent a wrong edge.
- **`taint_signature` is base-only** (not propagated) and approximate; sufficient
  as infrastructure, not yet a detector input.
- **Nothing is consumed.** This phase deliberately moves no metric.

## 10. Next

Phase 93B / 94 (separate, gated): a *promoted* interprocedural detector — e.g.
`inconsistent_return` that fires only when a resolved caller **dereferences** the
result of a function that can fall through to None, and stays silent when callers
**null-check** it — validated through the same 0-FP promote/quarantine gate. Plus
the deferred ranker sort-then-dedupe fix required at first promotion.
