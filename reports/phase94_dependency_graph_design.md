# Phase 94 — Dependency Graph Subsystem (Design Only)

**Status:** Design only. No code, no detector change, no benchmark change.
**Date:** 2026-05-30
**What this is:** a **deterministic dependency graph built only from code
structure**, assembled from the existing static resolvers.
**What this is NOT:** a repository knowledge graph, semantic memory, or AI
reasoning. No inference, no LLM, no semantic/causal edges. Static analysis only;
unknown beats guessing.

---

## 1. Problem statement

Builder Core analyzes one repository at a time but holds no first-class model of
how that repository is *wired together*. The interprocedural work (93A–93D)
produces call/import facts, but they are ephemeral, detector-scoped, and not a
unified, queryable structure. Without a stable structural model, JARVIS cannot
answer the questions that the next wave of features needs:

- *If I change this function/file, what else is affected?* (impact)
- *What changed structurally between two revisions?* (change analysis)
- *What is the module dependency shape — cycles, God-modules, layering?* (architecture)
- *A risky function exists here; who is exposed through the call/import edges?* (risk propagation)

Phase 94 fills this gap with a **deterministic dependency graph**: nodes for the
repository, its modules, classes, and functions; edges for *contains*, *imports*,
*calls*, *references*. It is **infrastructure only** — assembled from code
structure, consumed by nothing in this phase, and the substrate every future
consumer will read.

## 2. Dependency graph vs knowledge graph (the critical distinction)

This subsystem is a **dependency graph**, categorically different from a
knowledge graph. The distinction governs every later decision.

| | **Dependency graph (this)** | **Knowledge graph (explicitly NOT this)** |
|---|---|---|
| Edge meaning | mechanical code relationships: *A imports B*, *A calls B*, *A contains B* | semantic/conceptual: *relates-to*, *is-similar*, *is-about* |
| Ground truth | a single deterministic answer from the AST/imports | a judgment; often probabilistic |
| How edges are made | static resolution (no guessing) | inference, embeddings, heuristics, sometimes an LLM |
| Determinism | byte-identical on re-run | varies with model/threshold |
| Lifetime | ephemeral analysis state | persisted, queryable memory |
| Verifiability | every edge traces to a line of code | edges are not individually code-verifiable |
| Failure mode | a missing edge (under-approximation) | a *wrong* edge stated with confidence |

A dependency edge is true the way a compiler is true: *this name resolves to that
definition*. A knowledge edge is an assertion about meaning. We build only the
former. When resolution is uncertain, we record **unknown** rather than inventing
a plausible edge — the opposite of how a knowledge/AI system behaves.

## 3. Node types

| Node | Identity (deterministic, human-readable) | Key attributes |
|---|---|---|
| **repository** | repo root (one per analysis) | file count, language=python, build timestamp |
| **file/module** | repo-relative POSIX path | dotted module (`module_map`), `is_package` (`__init__`), `parse_ok`, line count |
| **class** | `(file, qualname)` | line, base-class names (→ *references*), methods (→ *contains*) |
| **function** | `FunctionId = (file, qualname)` — reused from `callgraph` | line, params, `is_async`, decorator names |

For Python, *file == module*; the module node carries the dotted name as an
attribute (no separate file/module split). Identities are syntactic and stable —
no hashing, no collisions.

## 4. Edge types

All edges are **directed, typed, deterministic**, carry **provenance** (source
line) and a **`resolved`** flag. Unresolved relationships are explicit or omitted —
never guessed.

| Edge | From → To | Source | Notes |
|---|---|---|---|
| **contains** | repo→module, module→{function,class}, class→method, function→nested function | AST structure | **Always known, 100% precise** — the structural spine |
| **imports** | module → module | `imports.py` + `module_map` | resolved → edge to a project module; third-party/unresolved → marked **external**, not resolved into the project |
| **calls** | function → function | `callgraph` (intra) + `cross_file` (cross) | **resolved only**; carries call-site line + usage class. Unresolved calls → no edge (counted as a per-caller annotation) |
| **references** | class→class (base), fn/class→fn (decorator), name→fn/class (binding) | base/decorator/name resolution via the import table | non-invoking uses that **resolve deterministically** to a project node; unknown → no edge |

`references` is intentionally narrow in Phase 94: base classes, decorators, and
direct name references to imported/module-level project symbols.

## 5. Relationship to the existing modules

The graph **reuses, never re-implements**. It is the unified, typed *assembled
view* of what these modules already compute:

| Module | Role in the graph |
|---|---|
| `module_map.py` | dotted name per **module** node; resolves *imports* targets to project modules |
| `imports.py` | source of *imports* edges; the import authority for cross-file *calls*/*references* |
| `callgraph.py` | **FunctionId** identity, intra-file *calls* edges, the *contains* qualname hierarchy, call-site usage carried on edges |
| `cross_file.py` | cross-file *calls* edges (resolved only) + the same conservative resolution discipline |
| `summaries.py` | **optional** node enrichment (attach `return_nullability`/`may_raise` to function nodes). **Not** a structural input — graph shape is independent of summaries |

Net: Phase 94 adds a **graph model + assembler + serializer**, not a new analysis.
The ephemeral 93A/93C structures are untouched (detectors still read them); the
dependency graph is a separate, additive artifact.

## 6. Graph construction algorithm (described, not coded)

A single deterministic pass, reusing the resolvers:

1. **Collect** the repo's Python files (the existing file walk; skip the usual
   ignored dirs). Sort by path for determinism.
2. **Parse** each file once (accept pre-parsed ASTs to avoid double work). A parse
   failure → a `module` node with `parse_ok=False`; skip its contents.
3. **Module map.** Build path↔dotted via `module_map`; create one **module** node
   per file (dotted name, `is_package`, line count). Create the **repository** node
   and a `contains` edge repo→each module.
4. **Contains hierarchy.** Walk each module's AST for class/function definitions
   (reusing `callgraph`'s qualname logic); create **class**/**function** nodes and
   `contains` edges (module→top-level defs, class→methods, function→nested funcs).
   This layer is exhaustive and exact.
5. **Imports edges.** From each file's import table (`imports.py`), emit
   module→module `imports` edges; resolve targets via `module_map` (project module
   → resolved edge; otherwise → external, `resolved=False`).
6. **Intra-file calls.** From `callgraph`, emit function→function `calls` edges for
   same-file resolved calls, carrying call-site line + usage class.
7. **Cross-file calls.** From `cross_file` resolution (import-table-driven,
   single-candidate only), emit function→function `calls` edges across modules.
   Unresolved calls become a per-caller unresolved annotation, never an edge.
8. **References.** Emit `references` edges for class bases, decorators, and direct
   name bindings that resolve to a project class/function; unknown → none.
9. **Finalize.** Sort nodes and edges by stable keys; produce a deterministic,
   serializable representation (cache-ready). Same input bytes → byte-identical
   output.

No step infers, scores, or guesses; every non-structural edge traces to a resolver
decision with a line number.

## 7. Unknown / unresolved handling

- **Resolution authority is the import table** (93C) — no name-only global lookup,
  no "a function named foo exists somewhere, so resolve to it."
- **Every non-`contains` edge carries `resolved`.** Resolved edges target a real
  project node; unresolved/third-party are marked **external** (named, not
  resolved) or recorded as an unresolved annotation — they are **counted, never
  fabricated**.
- **Unresolved reasons are preserved** (star import, ambiguous, third-party,
  symbol-not-found, shadowed, dynamic) so consumers can reason about coverage.
- **Under-approximate, never over-approximate.** A missing edge is acceptable; a
  wrong edge is not. This is the whole posture.

## 8. Storage — ephemeral vs optional disk cache

| | **A — Ephemeral per run** | **B — Cached on disk** |
|---|---|---|
| Lifetime | in memory, discarded | persisted (e.g. `.jarvis_builder/depgraph.json`) |
| Correctness | **always fresh** | risk of **silent staleness** → wrong impact analysis |
| Complexity | minimal | cache keys, invalidation, schema versioning |
| Cost | recomputed each run (linear) | amortized; only changed files rebuilt |
| History/diff | none | enables change-analysis over time |
| Footprint/security | none | a structure-only file under the repo (low risk, but real) |
| Precedent | matches 93A/93C (ephemeral) | new persistence surface |

**Recommendation: Phase 94 ships Option A (ephemeral) with a deterministic,
serializable, cache-ready schema.** Precision-first: a stale cache silently yields
a wrong impact graph — worse than recomputation. Caching becomes a later additive
step, enabled only when (a) content-hash invalidation is proven correct, (b) a
staleness test exists, and (c) rebuild cost is a measured bottleneck. Designing the
schema serializable now makes Option B a drop-in, not a rewrite.

## 9. Incremental rebuild strategy

(Phase 94 is full-rebuild-each-run; this is the design for the future cached form.)

- **Per-file content hash** keys each module's nodes/edges.
- **Dependency-aware invalidation:** a file's *outgoing* edges depend on its own
  content; a file's *incoming* `calls`/`imports`/`references` depend on its
  **module-level symbol table** (exported function/class names). Therefore:
  - file content changed → rebuild its nodes + outgoing edges;
  - file's exported symbols changed → re-resolve edges **targeting** that module
    from its importers/callers.
- **Conservative default:** when the invalidation scope is uncertain → **full
  rebuild**. Never serve a possibly-stale edge.

## 10. Performance limits

- **One parse per file** (accept pre-parsed ASTs from the project pass).
- **Linear build** ~ O(files + defs + calls + imports); determinism sorting is
  O(n log n).
- **Compact model** — identities + line numbers only; **no source text stored**.
- **Hard caps** (max files/nodes/edges) → degrade to partial/skip (the 93C
  pattern), never hang.
- **Share the project walk** that `cross_file` already performs, so the marginal
  cost over current project-mode analysis is small.

## 11. Precision safeguards

- **Reuse the conservative resolvers** → inherit "unknown beats guessing" wholesale.
- **`contains` is structural** → 100% precise by construction.
- **Resolved + provenance** on every non-structural edge; external targets marked,
  not resolved into project nodes.
- **No fabricated nodes/edges** — an unresolvable symbol yields nothing.
- **Deterministic identity** (no hashing) → no collision mis-merges.
- **Parse failures isolated** (node flagged; contents omitted).
- **Resolution-precision gate** before any consumer trusts edges for impact claims:
  sampled edges 100% correct (the 93D discipline).

## 12. Future consumers (separate, gated phases — not Phase 94)

- **Impact analysis** — reverse-reachability over `calls`/`imports`/`contains`:
  "what is affected if I change X?"
- **Architecture visualization** — module dependency diagrams, import **cycle**
  detection, fan-in/fan-out, God-modules, layering checks.
- **Risk reports** — overlay bug/security findings on nodes; propagate exposure
  along edges (a risky function's callers are exposed).
- **Change analysis** — diff two graphs across git revisions.
- **Repository intelligence** — the deterministic substrate for higher queries.

Each *reads* the graph; **none is built here**, and each carries its own gate.

## 13. Non-goals

- ❌ Repository knowledge graph (no persisted, queryable semantic store).
- ❌ Semantic relationships (no "similar-to"/"relates-to"/conceptual deps).
- ❌ Causal reasoning (no "X causes Y").
- ❌ AI-generated edges (no LLM, no inference, no "probably calls").
- ❌ Memory system (no cross-session learning, no user data).
- ❌ Runtime/behavioral edges (static only; no dynamic call traces).
- ❌ Cross-language semantic linking (Python AST only for now).

## 14. Exact files likely to change (eventual implementation)

**New (the subsystem; reuses existing resolvers):**
- `builder_core/bug_intelligence/depgraph.py` (or a small `depgraph/` package):
  node/edge model, the assembler (calls `module_map` / `imports` / `callgraph` /
  `cross_file`), and deterministic JSON serialization.

**Modified (additive, optional, findings-free):**
- `engine.py` — an optional `build_dependency_graph(root)` entry point that
  collects files and calls the assembler, returning the graph. It does **not**
  touch `analyze_source` findings or the benchmark path.

**Explicitly NOT changed:** `fact_detectors.py`, `finding.py`,
`engine_benchmark.py`, every detector, and the reused resolvers
(`module_map`/`imports`/`callgraph`/`cross_file`/`summaries`) consumed read-only.

**Plus:** `tests/test_phase94_depgraph.py`, `reports/phase94_*` at build time.

## 15. Acceptance criteria (for the eventual implementation)

- **Deterministic:** same repo → byte-identical serialized graph (tested).
- **Static only, no LLM, no inference.**
- All four node types and all four edge types present and typed.
- `contains` exhaustive and exact (every def has a container; repo→module→def).
- `imports`/`calls`/`references` edges only for **resolved** relationships;
  unresolved explicit; third-party marked **external**.
- **Reuses** `module_map`/`imports`/`callgraph`/`cross_file` — no new resolution.
- **Ephemeral** but **serializable** (cache-ready); no on-disk cache in Phase 94.
- **No detector/benchmark/finding change** — QuixBugs 12/0, Holdout 2/0 unchanged.
- Bounded (caps) and failure-isolated (parse error → flagged node, no fabrication).
- Consumed by **no** current detector; future consumers separately gated.

## 16. Rollback plan

- The subsystem is a **standalone module** with an **optional** engine entry point.
  Removing the `build_dependency_graph` registration (one line) or deleting the
  module disables it entirely.
- It is **ephemeral** in Phase 94 — nothing is persisted, so there is no on-disk
  state to clean up and no migration to reverse.
- **No detector or benchmark depends on it**, so disabling/removing it cannot change
  a finding or a benchmark number (QuixBugs 12/0, Holdout 2/0 are unaffected by
  construction).
- If a disk cache is added later (Option B), rollback adds one step: delete the
  cache file (`.jarvis_builder/depgraph.json`) and fall back to ephemeral rebuild;
  the cache is always reconstructable from source, so deletion is always safe.

---

## 17. Constraints honored

No code · no implementation · no detector changes · no benchmark changes · no
recall work · no UX work · static analysis only · no LLM-generated edges ·
unknown beats guessing.

### One-line summary

Phase 94 designs a **deterministic, structure-only dependency graph** —
`{repository, file/module, class, function}` × `{contains, imports, calls,
references}` — **assembled (not re-derived)** from the existing conservative
resolvers, ephemeral but serializable, consumed by nothing yet, and explicitly
**not** a knowledge, semantic, or AI-memory graph.
