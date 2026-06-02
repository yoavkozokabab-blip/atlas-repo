# Phase 93 — Interprocedural Architecture Plan

**Status:** Architecture plan only. No code, no pseudocode, no implementation.
**Date:** 2026-05-30
**Context:** Phase 92A commit `784bf4a0`, Phase 92B commit `b1056d00`. QuixBugs
12 TP / 0 FP, Holdout 2 TP / 0 FP, 122 tests passing.
**Goal:** Design the *smallest* interprocedural layer that preserves precision,
unlocks future contract reasoning and recall, and avoids a major rewrite.

---

## 1. Problem statement

Every detector in Builder Core today reasons about **one function in isolation**.
That ceiling is now the binding constraint. The questions that block both
precision and recall are call-site questions:

- Is an implicit `None` return a **contract** or a **forgotten return**? (depends
  on how callers use the result)
- Does untrusted input reach a dangerous sink **through a helper function**?
  (depends on what the helper does with its argument)
- Can this value be `None` here because a **callee** sometimes returns `None`?

None of these are answerable inside a single function body. We need a small,
disciplined way to let facts cross the function boundary — a function **call
graph** plus bounded **function summaries** — without inlining, without path
explosion, and without weakening the precision-first culture.

## 2. Why Phase 92B exposed this limitation

Phase 92B built a fact-backed `inconsistent_return` detector that fires on
"value return on some path + no explicit `None` + can fall through to implicit
`None`." It was **quarantined** because it false-fired on the correct QuixBugs
`next_permutation.py`, which *intentionally* falls through to `None` when there
is no next permutation.

The detector had all the *intraprocedural* facts right. What it could not see is
the only thing that disambiguates the two cases:

> **How do callers use the return value?**
> - If callers null-check it (`if x is None`, `if not x`, `x or default`), the
>   implicit `None` is a **contract** → not a bug.
> - If callers dereference it unconditionally (`f().attr`, `f()[i]`, `len(f())`),
>   the implicit `None` would crash → a **bug**, with high confidence.

That is a call-site fact. The quarantine is therefore not a detector flaw — it is
the precise signal that the next capability must be interprocedural. Phase 92B is
the motivating, concrete consumer that keeps Phase 93 honest and minimal.

## 3. Current Builder Core pipeline

One file at a time, intraprocedural, through `bug_intelligence/engine.py`:

```
analyze_source(text, rel_path)
  ParseAgent            text -> AST
  FactExtractionAgent   facts.extract_module_facts  (dataflow + valueflow,
                        per function: returns, return_summary, nullability,
                        intervals, taint sources/sinks, loops, container state)
  LogicBugAgent         patterns.run_all            -> unified Findings
  FactLogicAgent        fact_detectors              -> unified Findings (92B)
  SecurityAgent         security.py (taint)         -> unified Findings
  AlgorithmAgent        semantic_reasoning (wrapped)-> unified Findings
  FindingRankerAgent    dedupe + rank
  EvidenceFormatterAgent
```

The benchmark verdict counts only grounded kinds `{semantic, data_flow,
value_flow}` (security and pattern excluded). Everything above is **per-file**;
there is no notion of "what calls this" or "what this returns to its callers."

## 4. Proposed call graph architecture

A **lightweight, analysis-time call graph** — emphatically *not* a repository
knowledge graph (that is explicitly out of scope). Properties:

- **Ephemeral.** Built per analysis run, held in memory, never persisted or
  exposed as a queryable store. It exists only to propagate facts.
- **Nodes** = functions, keyed by a stable Function Identity (§5).
- **Edges** = *resolved* call relationships (caller → callee), plus the reverse
  index (callee → call sites) which is what contract reasoning needs.
- **Conservative resolution.** A call that cannot be resolved unambiguously
  (dynamic dispatch, attribute call on an unknown object, `getattr`, decorators
  that wrap, `*args` forwarding) becomes an **UNRESOLVED edge** carrying
  `UNKNOWN`. Unresolved is the default, not the exception.
- **Bounded.** Hard caps on node count, edge count, and propagation iterations;
  beyond the cap the layer degrades to today's pure intraprocedural behavior.

The call graph is built in two layers that share one abstraction (§7, §8): an
**intra-file** graph (MVP) and a **cross-file** graph (bounded extension). A
detector never reads the graph directly; it reads the **summaries and call-site
usage facts** that the graph produces.

## 5. Function identity design

Deterministic, human-readable, no hashing:

- **FunctionId = (file, qualname)**.
  - `file` = repo-relative POSIX path (single file in the intra-file stage).
  - `qualname` = the dotted path within the module: top-level `func`, methods
    `Class.method`, nested `outer.inner`.
- **Redefinition / overload** (same qualname twice): disambiguated by definition
  line; the call resolver maps a call to the definition in scope at that point,
  and if two are plausible it marks the edge UNRESOLVED.
- **External / library functions** have no FunctionId; calls to them are
  UNRESOLVED by construction (we never invent a summary for code we cannot see).
- Identity is intentionally *syntactic and conservative*. We accept missing some
  real edges (recall cost) in exchange for never inventing a wrong one
  (precision win).

## 6. Cross-function fact propagation

Two small, monotone passes over the graph. No inlining; only fixed-size summaries
flow.

**(a) Function summary lattice** (bounded fields, each joins to `UNKNOWN` on
disagreement):
- `return_nullability` ∈ {definite_value, maybe_none, unknown}
- `may_raise` ∈ {no_raise, may_raise, unknown}
- `taint_signature`: which parameters flow to the return, and which flow to a
  known dangerous sink inside the function (param-indexed, small).

**(b) Call-site usage facts** (the reverse index — the Phase 92B unlock):
for each function, aggregate across its resolved call sites how the **return
value is consumed**: `null_checked`, `dereferenced`, `stored_then_unknown`,
`ignored`. This yields a per-callee verdict like *"every caller null-checks the
result"* (⇒ `None` is a contract) vs *"some caller dereferences it"* (⇒ a `None`
fall-through is a real bug).

**Propagation procedure (described, not coded):** a worklist fixpoint. Leaf
functions (no resolved out-edges) get summaries first; callers refine their
intraprocedural facts using callee summaries (e.g. `x = callee()` with
`return_nullability = maybe_none` makes `x` maybe-None at that site). Recursive
cycles join to `UNKNOWN` (widening to top) so the fixpoint terminates in bounded
iterations. The call-site usage pass is a single reverse aggregation. Both passes
are deterministic given a fixed file ordering.

The output is attached to the existing fact model as new, clearly-namespaced
fields (e.g. an `interproc` section per function) — **additively**, leaving every
existing fact untouched.

## 7. Intra-file stage (the MVP)

The smallest shippable unit, and the one that fits today's single-file engine
with minimal change:

- Scope the call graph to the functions defined in **one file**.
- Resolve calls to same-file functions; everything else is UNRESOLVED.
- Compute summaries + call-site usage for that file, attach to `module_facts`.
- Detectors gain interprocedural facts **only for same-file call relationships**.

This already covers a large, real class of cases (helpers and their callers in
the same module, which is exactly the `next_permutation`-style pattern) and lets
the contract-reasoning idea be validated before any project-wide machinery
exists. It is a localized addition to `analyze_source`, not a rewrite.

## 8. Cross-file stage (bounded extension, staged after the MVP)

Same summary/usage abstraction, wider graph:

- A **project pre-pass** walks the repo (reusing the existing file-collection in
  `engine.analyze_repository`), resolves cross-file calls via **name/import
  resolution** (conservative: only unambiguous `from m import f` / `import m`
  style targets; star-imports and dynamic imports stay UNRESOLVED), computes a
  global summary table, then per-file analysis consults that table.
- Hard caps (max functions, max edges, time budget); over the cap → fall back to
  intra-file only. Still **ephemeral**, still no persisted graph.

Cross-file is designed now but **gated behind the intra-file MVP proving value**.
Shipping order: identity + intra-file graph + summaries → validate → cross-file.

## 9. Precision safeguards

The non-negotiables that keep this from regressing the discipline:

1. **Conservative-by-default resolution.** Unresolved/ambiguous → `UNKNOWN`. We
   never assume a callee's behavior we cannot prove.
2. **Soundness direction toward `UNKNOWN`/top.** Lattice joins widen to `UNKNOWN`
   on any disagreement or cycle. Detectors may fire only on **definite** facts,
   never on `UNKNOWN`.
3. **New findings get a new, non-verdict kind.** Any interprocedural detector
   emits a kind (e.g. `interproc`) that is **not** in `BENCHMARK_VERDICT_KINDS`
   until it passes the promote/quarantine gate. The layer therefore **cannot**
   change the benchmark verdict by construction.
4. **Same promote/quarantine gate as Phase 92B.** Zero FP on QuixBugs correct +
   holdout fixed, or it stays a diagnostic.
5. **Additive facts only.** Existing intraprocedural facts and detectors are
   untouched; the layer can be disabled with no behavioral change.
6. **Determinism + bounds.** Fixed ordering, monotone fixpoint, hard caps →
   reproducible and terminating; degrade to intraprocedural over the cap.
7. **No LLM, no heuristics-by-name.** Resolution and summaries are structural.

## 10. Benchmark impact expectations

- **Phase 93 itself: no movement, by design.** It is infrastructure. It adds
  facts and a new non-verdict kind; it promotes **no** detector. Expected result:
  **QuixBugs 12 TP / 0 FP and Holdout 2 TP / 0 FP, unchanged.** This is the
  acceptance bar, not a disappointment — the layer's job is to enable later,
  gated recall, not to chase a number now.
- **Future (post-93, gated):** the intended first consumer is a *promoted*
  `inconsistent_return` that fires only when a function can fall through to
  `None` **and** at least one resolved caller dereferences the result — and is
  silent when callers null-check it (the `next_permutation` case). That, and
  cross-function taint, are where recall can rise *with* precision — but each must
  pass the gate on its own, in its own phase.

## 11. Risks

| Risk | Mitigation |
|---|---|
| Call resolution imprecision (dynamic dispatch, decorators, `*args`, monkeypatch) | UNRESOLVED → `UNKNOWN`; never assume |
| Fixpoint non-termination on cycles | Monotone join + widening to top + bounded iterations |
| Performance on large repos (cross-file) | Caps + time budget + intra-file-first; degrade gracefully |
| Scope creep into a repository knowledge graph | Hard boundary: ephemeral, analysis-only, not persisted/queryable |
| Engine becomes project-aware (bigger change) | Intra-file MVP needs no project pass; cross-file staged separately |
| A new interproc detector silently shifts the verdict | New non-verdict `kind`; gate before promotion |
| Hidden coupling / regressions | Additive facts; layer disableable; full suite + benchmark parity required |

## 12. Rollback strategy

- The layer is **additive and flag-gated.** Disabling the interprocedural pass
  returns the engine to today's exact single-file behavior — no verdict change,
  because no verdict-eligible detector depends on the new facts in Phase 93.
- **Independently revertible stages:** function identity + intra-file graph,
  summary propagation, call-site usage, cross-file — each is a separate, small
  commit; reverting any one leaves the rest working.
- Because Phase 93 promotes nothing, rollback can never regress QuixBugs/holdout.

## 13. Acceptance criteria

- `pytest builder_core/tests/ -q` passes.
- **QuixBugs unchanged: 12 TP / 0 FP.** **Holdout unchanged: 2 TP / 0 FP.**
- Call graph resolution is conservative: tests assert that dynamic/attribute/
  ambiguous calls resolve to `UNRESOLVED`/`UNKNOWN`, and that a clear same-file
  call resolves correctly.
- Summaries and call-site usage are **deterministic** (stable across runs) and
  **bounded** (fixed fields; caps enforced).
- The new findings, if any, carry a **non-verdict kind** and do not enter the
  grounded verdict; no detector is promoted in Phase 93.
- The intra-file stage is shippable and useful **without** the cross-file stage.
- No legacy benchmark behavior changed; no unrelated files touched.

## 14. Exact files likely to change in implementation

**New (analysis-only, under `builder_core/bug_intelligence/`):**
- `callgraph.py` — Function Identity + conservative call resolution + the
  ephemeral intra-file graph (later extended for cross-file).
- `summaries.py` — the bounded summary lattice, the monotone propagation
  fixpoint, and the call-site usage aggregation.

**Modified (additive only):**
- `facts.py` — attach an `interproc` section (summaries + call-site usage) to
  each function's facts; nothing existing removed or changed.
- `valueflow.py` — expose per-call-site "how is this Call's result used"
  (null-checked / dereferenced / stored / ignored), feeding call-site usage.
- `agents.py` — a new `InterproceduralAgent` (pipeline stage) that builds the
  graph and runs propagation between fact extraction and the detectors.
- `engine.py` — orchestrate the new stage in `analyze_source` (intra-file) and,
  later, host the cross-file pre-pass alongside `analyze_repository`.

**New tests + report:**
- `tests/test_phase93_interprocedural.py` (resolution conservatism, summary
  determinism/bounds, benchmark parity, non-verdict kind).
- `reports/phase93_*` implementation report at build time.

**Explicitly NOT changed in Phase 93:**
- `finding.py` verdict/ranking logic, `engine_benchmark.py` verdict kinds, every
  existing detector, and anything outside `bug_intelligence/`. No repository
  knowledge graph, no persisted store, no LLM.

---

### One-line summary

Phase 93 adds an **ephemeral, conservative, summary-based call graph** — intra-
file first — that lets bounded facts cross the function boundary, promotes
nothing, changes no benchmark number, and exists solely to make the
contract-vs-bug question (the exact thing that quarantined Phase 92B) answerable
under the same precision-first gate.
