# Phase 88 — Builder Intelligence Architecture Review

**Status:** Architecture review (no code, no new rules, no benchmark work)
**Date:** 2026-05-30
**Author:** CTO / Principal Engineer
**Inputs:** Phases 80, 82, 83, 84, 85, 86, 87

**Current measured state**
- QuixBugs (in-domain): precision 100%, recall 30% (12/40)
- External holdout (out-of-domain): precision 100%, recall 16.7%
- Data-flow fact layer exists (Phase 86), consumed by exactly one rule (Phase 87)

---

## 0. TL;DR

We are precision-saturated and recall-starved. Precision is 100% in and out of
domain; recall is 30% / 16.7%. That profile means the engine only fires when it
is *certain*, and it is rarely certain because **it reasons about names and
shapes, not about values and paths**. The fix is not more rules. It is a deeper
representation.

- **Highest-leverage missing capability: Data Flow Expansion** (a value-aware,
  CFG-backed data-flow engine, with an intraprocedural taint pass as its
  security beachhead). It is the shared substrate every other engine needs.
- **Delete** the duplicated second analysis stack and the name-bound,
  benchmark-memorizing algorithm rules.
- **Rewrite** the analysis core into one pipeline with one Finding schema, and
  promote `dataflow.py` from a boolean fact-bag into a value-flow framework.
- **Phase 89** = build that substrate and rewire ≥6 rules onto it.

---

## 1. The system as built (one-paragraph map)

Builder Core today has **two parallel bug-analysis stacks**:
(A) `python_analysis.analyze_python` → `semantic_reasoning.analyze_semantics`
(+ `algorithm_profiles`), which drives `benchmark.py` / `external_benchmark.py`
and the precision/recall numbers; and (B) `bug_intelligence/{patterns, analyzer,
ranking}.py`, which drives the CLI `analyze-file` / `bug-scan`. They have
**different Finding representations** (dict vs the `findings.Finding`
dataclass), **overlapping-but-divergent rules** (e.g. `algorithm_mismatch` in B
vs `bfs_*` in A), and **separate benchmarks**. Underneath both sits the Phase 86
`dataflow.py` fact layer — the one genuinely transferable asset — used by a
single rule (`unguarded_container_consumption`). Repository understanding
(Phase 80 `ask`/`retrieval`/`indexer`) is keyword search over text chunks, with
no symbol table or call graph. There is **no security model of any kind**.

---

## 2. Top 5 architectural bottlenecks

Ranked by how much they cap the four goals (bug detection, logic reasoning,
security analysis, repository understanding).

### B1 — Two divergent analysis stacks (the duplication tax)
Every detection improvement must be implemented twice and inevitably drifts. The
two stacks disagree on the same file (A emits `bfs_queue_exhaustion`, B emitted
`algorithm_mismatch`), carry two Finding schemas, and are measured by different
harnesses. This is the **#1 structural drag**: it doubles the cost of every
other fix and makes a single source of truth impossible.
*Blocks:* all four goals (as a tax on every change).

### B2 — No value model: rules reason one function at a time over shallow facts
There is no CFG, no reaching-definitions-with-values, no nullability, no
interval/range, no path feasibility. The Phase 86 layer emits *booleans about
containers and loop guards*, not *what a value can be*. Consequently entire bug
classes are structurally undetectable: null dereference, real index off-by-one,
boundary/overflow, infeasible branches, resource leaks. **This is the recall
ceiling.** 30%/16.7% is what you get when you can only catch bugs visible in the
syntax tree.
*Blocks:* bug detection, logic reasoning, security (taint is a value-flow
problem).

### B3 — Name-bound rules dominate (memorization, not generalization)
Per Phases 85/87, most semantic rules match exact function names and variable
shapes (`gcd`, `mergesort`, `quicksort`, `shortest_path*`, `find_in_sorted`,
`possible_change`, `subsequences`; and the DFS/binary/factorial/fibonacci
branches of `algorithm_mismatch`). They inflate in-domain QuixBugs and evaporate
out-of-domain — exactly the 30% → 16.7% cliff. The architecture currently
*rewards* adding lookup-table rules instead of representational depth.
*Blocks:* bug detection and logic reasoning on unseen repos (transfer).

### B4 — No interprocedural or repository-level model
Analysis stops at the function boundary. There is no call graph, no symbol
table, no def/ref/call edges; `ask` is keyword retrieval over chunks. So bugs
and taint cannot propagate across functions, and the system cannot answer the
questions that define repository understanding ("what calls this", "where is
this defined", "what breaks if I change X"). Real-world bugs are
cross-function; we cannot see them.
*Blocks:* repository understanding (directly), bug/security detection
(interprocedural cases).

### B5 — No security model at all
No taint, no source/sink catalog, no secret/sensitive-data tracking, no trust
boundaries. Security analysis is absent. It also **cannot be added as patterns**:
without data flow, a "security engine" degrades into grepping for `eval`/`SQL`,
which is precisely the name-bound trap B3 warns against.
*Blocks:* security analysis (entirely).

> Honorable mention (B6): the benchmark itself is overfit bait — 40
> single-function algorithm bugs plus a 12-case holdout, no real-repo corpus, no
> security corpus, no severity weighting. The optimizer is pulled toward
> algorithm-name memorization because that is what the metric measures.

**Note the dependency structure:** B2 is the root. B5 sits on top of B2 (taint =
data flow). B4 is B2 widened across functions. B3 is the symptom of not having
B2. Fix the value/data-flow substrate and four of the five move together.

---

## 3. What to build in the next 30 days

One coherent track (this *is* Phase 89; see §7), sequenced to de-risk:

- **Days 1–4 — Unify the core.** Collapse stacks A and B into one pipeline with
  one Finding schema. One parse → one fact provider → one rule evaluator → one
  ranking → two thin front-ends (CLI + benchmark). Nothing else can be built
  cleanly until this exists.
- **Days 4–10 — CFG substrate + reaching definitions.** Per-function control-flow
  graph (basic blocks, edges, loop headers, dominators-lite) and precise def-use
  / reaching definitions to replace the current name-set approximation.
- **Days 10–18 — Value lattices.** Attach nullability (None / maybe / not-None),
  interval/range (indices and bounds), and container-state (generalizing
  Phase 86) to defs and uses. Expose as facts.
- **Days 16–22 — Taint pass (security beachhead).** Declarative source catalog
  (params, `input`, `os.environ`, request/file/IO reads) and sink catalog
  (`eval`/`exec`, `subprocess`/`os.system`, SQL/command string building,
  path joins, deserialization). Report reachable source→sink flows.
- **Days 20–27 — Rule rewire.** Re-express ≥6 existing rules as fact-consumers
  (off-by-one from interval-vs-`len`; null-deref from nullability; the Phase 87
  frontier rule as a value-flow view) and retire the matching name-bound rules.
- **Days 27–30 — Honest corpus + consolidation.** Add a small real-repo
  regression corpus and a security micro-corpus to the harness so we measure
  transfer, not memorization; write the phase report.

---

## 4. What to delete

1. **One of the two analysis stacks.** Keep the unified core; delete the
   redundant path and the second Finding schema. The duplication tax (B1) ends
   here.
2. **The name-bound algorithm rules** (the Phase 85 quarantine list): per-name
   checks for `gcd`, `mergesort`, `quicksort`, `bucketsort`, `kheapsort`,
   `shortest_path*`, `find_in_sorted`, `possible_change`, `subsequences`, and the
   DFS / binary-search / factorial / fibonacci branches of `algorithm_mismatch`.
   They are memorized QuixBugs answers; they pollute the precision/recall signal
   and block generalization. If retained at all, isolate them behind a
   `benchmark_specific` flag excluded from the real metric — do not let them vote.
3. **Style rules masquerading as bug findings** in the decision path:
   `unused_variable`, `unused_result`, `untested_module`, `untested_function`
   (keep as advisory output only).
4. **Keyword `ask` as the repository-understanding answer** — mark interim;
   it is replaced once a symbol/knowledge layer exists (not this phase).

## 5. What to rewrite

1. **The analysis core → one pipeline.** `parse → CFG → value-flow facts → rule
   evaluation → unified Finding → ranking → report`, with the CLI and the
   benchmark as thin consumers of the same core.
2. **`dataflow.py` → a value-flow framework.** Promote it from a boolean
   fact-bag into CFG-backed reaching definitions with lattice values; expose the
   current Phase 86 booleans as derived, backward-compatible views so Phase 87's
   rule keeps working.
3. **`semantic_reasoning.py` rules → fact-consumers.** Behavior-bound predicates
   over value facts, not AST-name matchers.
4. **The benchmark harness.** Add a transferable real-repo corpus + a security
   micro-corpus + severity weighting so the metric stops rewarding name
   memorization and starts rewarding transfer.

---

## 6. The single highest-leverage missing capability

**Choice: Data Flow Expansion** (value-aware, CFG-backed data flow, with an
intraprocedural taint pass as its security output).

It is the only option on the menu that advances **all four goals at once**,
because it is the substrate the others are built from:

- **Code understanding** ← def-use chains + value provenance + CFG answer "where
  does this value come from and what can it be."
- **Bug finding** ← nullability, intervals, feasibility unlock whole bug classes
  (null-deref, real off-by-one, boundary) and let the name-bound rules be
  rewritten as transferable value rules.
- **Logic reasoning** ← intervals / nullability / path-sensitivity *are* logic
  facts; infeasible branches stop generating noise.
- **Security reasoning** ← taint = source→sink data flow. This is the first
  *correct* security capability (not grep), and it falls directly out of the
  same engine.

**Why not the others (each is downstream of, or weaker than, data flow):**

- **Control Flow Graph** — necessary but not sufficient; it is *inside* this
  choice (data flow needs a CFG). Shipping CFG alone finds no bugs by itself.
- **Invariant Engine** — needs facts to check invariants over. Built before data
  flow, it would re-encode today's heuristics as "invariants" and re-overfit
  (the Phase 85 warning). Build it *on* the value engine, later.
- **Test Reasoning Engine** — improves *confirmation* and precision where tests
  exist; we are already at 100% precision. It does not lift the recall ceiling
  and depends on tests existing. High value, wrong bottleneck now.
- **Security Intelligence Engine** — the *goal*, but a credible one is taint
  analysis, i.e. data flow. Built without this substrate it is regex
  sink-matching (B3 again). Data Flow Expansion delivers the security beachhead
  *and* the substrate for the full engine next.
- **Multi-Agent Analysis Engine** — non-deterministic, expensive, and contrary to
  the deterministic-first principle that has gotten us 100% precision. Wrong
  altitude at this maturity.
- **Repository Knowledge Graph** — highest leverage for *repository
  understanding* and the right spine for interprocedural work, but it moves
  bug/logic/security recall the least per unit effort right now: the QuixBugs and
  holdout bugs are single-function value bugs, not cross-file ones. It is the
  correct **Phase 90** (widen), after Phase 89 (deepen).

The strategic shape: there are two axes of expansion — **deeper** (richer values
within a function = Data Flow Expansion) and **wider** (across functions =
Knowledge Graph). The bugs we are missing are mostly *deep*, and depth is also
what unlocks security. Deepen first, widen second.

---

## 7. Phase 89 (exactly one phase)

### Phase 89 — Value-Aware Data Flow & Taint (the substrate phase)

**Objective.** Turn the shallow intraprocedural fact layer into a value-aware,
CFG-backed data-flow engine, ship the first security capability (intraprocedural
source→sink taint), and unify the two analysis stacks behind it.

**Why this phase creates the largest single jump.** It simultaneously raises the
floor on code understanding (provenance), bug finding (value bug classes + rule
rewire), logic reasoning (intervals/nullability/feasibility), and security
reasoning (taint) — because all four read from the same new substrate. Every
later engine (invariants, test reasoning, full security, interprocedural,
knowledge graph) plugs into it.

**Scope / components.**
1. **Unified analysis core** — one pipeline, one Finding schema; CLI and
   benchmark become thin consumers. (Removes B1 as a precondition of the work,
   not as a side quest.)
2. **CFG substrate** — per-function basic blocks, edges, loop headers,
   dominators-lite. Read-only, AST-based.
3. **Reaching definitions / precise def-use** over the CFG.
4. **Value lattices** — nullability, interval/range, container-state
   (generalizing Phase 86), constantness, and a taint mark — attached to defs
   and uses, exposed as facts.
5. **Taint pass (security beachhead)** — declarative source and sink catalogs;
   report reachable source→sink flows with the path as evidence.
6. **Rule rewire** — re-express ≥6 rules as value-fact consumers; retire the
   matching name-bound rules. Phase 87's `unguarded_container_consumption`
   becomes a derived view, unchanged in behavior.

**Acceptance criteria (proven in-phase except where noted).**
- One analysis pipeline and one Finding schema; the duplicate stack is gone.
- CFG + reaching definitions available as facts for every analyzed function.
- ≥3 value lattices live (nullability, interval, container-state).
- Taint pass flags ≥1 documented source→sink class with **zero false positives**
  on a held-out correct sample.
- ≥6 rules rewired to facts; **net name-bound rule count decreases**.
- **No regression:** holdout precision stays 100%; holdout recall does not fall
  below 16.7%; QuixBugs recall stays ≥25%. (Measured in the follow-on benchmark
  phase, not as new benchmark work here.)

**Explicit boundaries.**
- **Intraprocedural only.** Interprocedural via a call graph is **Phase 90**
  (the "widen" phase / Repository Knowledge Graph).
- Python only; read-only; deterministic; no LLM; additive under `builder_core/`.
- No target repositories modified.

**What Phase 89 deliberately does *not* do.** No invariant engine (needs these
facts first), no multi-agent/LLM layer, no cross-file knowledge graph, no
recall-chasing heuristics. One substrate, built once, used by everything after.

---

## 8. Sequencing after Phase 89 (context only — not a roadmap commitment)

1. **Phase 89 — Value-Aware Data Flow & Taint** (deepen). ← build this
2. Phase 90 — Repository Knowledge Graph + interprocedural propagation (widen).
3. Phase 91 — Invariant Engine on top of the value facts.
4. Phase 92 — Full Security Intelligence Engine (taint + secrets + trust
   boundaries) on the same substrate.
5. Phase 93 — Test Reasoning Engine for confirmation / spec comparison.

The order is forced by dependencies, not preference: depth (89) enables security
and the rewrite of the memorized rules; width (90) enables cross-function bugs
and real repository understanding; everything else stands on those two.
