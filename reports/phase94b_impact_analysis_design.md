# Phase 94B — Impact Analysis Engine (Design Only)

**Status:** Design only. No implementation, no code shipped, no behavior changed.
**Date:** 2026-05-31
**Constraints honored:** no detector changes, no benchmark changes, no promotion
changes, no LLM reasoning, read-only/local/deterministic, **unknown beats
guessing**.

This document specifies *what to build* and *how it must behave*. It defines no
functions and writes no code. It binds the design to the data structures that
already exist (Phase 93C/94A) so a later implementation has zero ambiguity.

---

## 0. Scope, inputs, and non-goals

**In scope (design):** an Impact Analysis Engine that answers, deterministically
and from static facts only, five questions about a file / module / function:

| # | Question | Primary graph operation | Highest-confidence source |
|---|---|---|---|
| 1 | What **files** depend on this file? | reverse `imports` + reverse `calls`/`references` whose target lives in the file, lifted to files | `imports` edges |
| 2 | What **functions** depend on this function? | reverse `calls` edges to `function:<path>::<qual>` | `calls` (intra + cross-file) |
| 3 | What **modules** import this module? | reverse `imports` edges to `module:<path>` | `imports` edges |
| 4 | What **execution paths** reach this code? | reverse BFS over `calls` edges from target up to entrypoint functions | `calls` + repository entrypoints |
| 5 | What **may break** if it changes? | transitive reverse closure over `imports`+`calls`+`references`, risk- and confidence-scored | all resolved edges |

**Inputs (already present; consumed read-only, never modified):**

- `bug_intelligence/depgraph.py` — `build_graph(root)` → the directed graph
  (`nodes`, `edges`, `unresolved`, `statistics`, `parse_errors`, optional
  `degraded`). **This is the spine of the engine.**
- `bug_intelligence/callgraph.py` — intra-file resolved calls + `callers_of`
  (already folded into depgraph `calls` edges, `scope="intra_file"`).
- `bug_intelligence/cross_file.py` — cross-file resolved calls (folded into
  depgraph `calls` edges, `scope="cross_file"`) and per-file `unresolved` reasons.
- `bug_intelligence/module_map.py` — `path_to_module` / `module_to_path` (the
  file ↔ dotted-module bridge; ambiguous modules are deliberately absent).
- `bug_intelligence/imports.py` — the per-file import table (the only authority
  for cross-file symbol resolution).
- `repository_understanding.py` — `classify_file_role`, `discover_subsystems`,
  `production_subsystems`, entry-file detection (role/subsystem/entrypoint facts).

**Non-goals (explicit):** no new edge *kinds*; no semantic/name-only inference; no
runtime tracing; no detector/finding emission; no benchmark or promotion
interaction; no persisted cache beyond an optional ephemeral JSON export; no LLM.

---

## 1. Problem statement

Builder Core can already *describe* structure (Phase 94A dependency graph) and
*classify* it (RU-2 roles/subsystems), but it cannot yet answer the question a
builder actually asks before touching code: **"if I change this, what is
affected, how badly, and how sure are we?"**

The dependency graph is **forward-directed**: an edge `from → to` means *from
depends on to* (A imports B; caller calls callee; subclass references base).
Impact analysis is the **reverse** question — *who points at the target* — plus
two scores the raw graph does not provide:

- a **risk** estimate (blast radius / how much is downstream), and
- a **confidence** estimate (how complete the answer is, given unresolved edges).

Doing this safely is non-trivial because the static graph is *intentionally
sparse and conservative*: `callgraph` resolves only same-file, unshadowed,
module-level direct calls; `cross_file` resolves only directly-imported `func()`
and `module.func()`; **all method calls, dynamic dispatch, star/ambiguous
imports, and attribute calls are UNRESOLVED by design.** A naive reverse
traversal would therefore (a) *miss* real dependents (false "safe") and (b) be
tempted to *guess* the missing ones (false "impact"). The engine's central job is
to **separate what is proven from what is merely possible**, and to never present
the second as the first.

**Design principle:** *Asserted impact uses only `resolved` edges. Everything
unresolved that could plausibly reach the target is reported in a separate
"possible / unverified" channel with its reason. Absence of a resolved path is
reported as "no resolved path found (coverage is partial)," never as
"unreachable" or "safe."*

---

## 2. Direct impact analysis

**Definition:** the depth-1 reverse neighborhood of the target over resolved
edges — the set of nodes that *directly* depend on the target.

### 2.1 Target resolution (granularity bridge)

The engine accepts a target at one of three granularities and resolves it to a
set of graph node-ids before traversal:

- **file** `path/to/x.py` → the `module:<path>` node **and** every
  `function:<path>::*` / `class:<path>::*` node whose `path` equals the file.
- **module** `pkg.mod` → via `module_map.module_to_path`, the single
  `module:<path>` node (ambiguous dotted names are unresolvable → reported as
  "module not uniquely mapped," unknown).
- **function** `path/to/x.py::qualname` → the exact `function:<path>::<qual>`
  node (qualname as produced by `callgraph._compute_qualnames`, e.g.
  `Outer.method`).

### 2.2 Direct dependents per question

Built from a **reverse-adjacency index** computed once from `graph["edges"]`,
keyed by the edge `to` field, partitioned by edge `type`, **including only edges
with `resolved == true`**:

- **Q3 (modules importing this module):** `reverse_imports[module:<path>]` → the
  set of `from` module nodes. This is the cleanest, highest-confidence query;
  it can be cross-checked against `statistics.top_imported_modules` (in-degree).
- **Q2 (functions depending on this function):**
  `reverse_calls[function:<path>::<qual>]` → the set of `from` function nodes,
  each tagged with its `scope` (`intra_file` | `cross_file`) and call-site `line`.
- **Q1 (files depending on this file):** the union, lifted to files, of:
  (a) sources of `reverse_imports` to the file's `module` node, and
  (b) sources of `reverse_calls` / `reverse_references` whose `to` node has
  `path == target file`. Each contributing edge is kept as **evidence**.

### 2.3 Evidence (every asserted dependent is auditable)

A direct-impact item is never a bare id. It carries: dependent node-id, dependent
**role** (`classify_file_role`) and subsystem, edge `type`, source `path`,
`line`, `scope`, and `resolved=true`. This mirrors RU-2's "evidence quality": a
reviewer can open the exact file:line that creates the dependency.

---

## 3. Transitive impact analysis

**Definition:** the reverse-reachable closure of the target over resolved
`imports` + `calls` + `references` edges — everything that could be affected
*indirectly*.

### 3.1 Traversal

- A bounded **reverse BFS** from the target node-set, following resolved reverse
  edges, recording the **depth** at which each node is first reached and the
  **edge type** that reached it.
- **Fixpoint with a visited-set** so cycles (the graph *has* import cycles, see
  `statistics.import_cycles`) terminate; each node is expanded once.
- **Deterministic order:** frontier sorted by `(depth, node-id)`; output sorted
  by `(depth, role-rank, node-id)`. Same repo ⇒ byte-identical result.

### 3.2 Bounds (see §11)

`--max-depth` (default e.g. 6, hard cap e.g. 25) and a max impact-set size cap.
When a cap is hit the result is **truncated and declared** (`"truncated": true`,
with the count omitted), never silently cut. A degraded graph (§9) short-circuits
to `confidence: "unknown"`.

### 3.3 What transitive impact is *not*

It is **not** an execution guarantee. A module appearing in the closure means
"there exists a static resolved dependency chain to the target," not "this will
run." Conversely, because the call graph is sparse, the closure is a **lower
bound** on true impact — the engine states this explicitly and pairs the set with
the confidence score and the possible/unverified channel (§6).

---

## 4. Risk scoring

A deterministic, explainable score answering Q5 ("what may break"). **No LLM, no
learned weights** — a fixed, documented function of structural facts already in
the graph and RU-2 roles. The score is always accompanied by the **factors** that
produced it (evidence, not a black box).

### 4.1 Factors (all derived from existing facts)

| Factor | Source | Why it raises risk |
|---|---|---|
| **Direct fan-in** | count of resolved reverse edges (Q1–Q3) | more immediate dependents = larger blast radius |
| **Transitive size** | size of §3 closure | indirect reach |
| **Production-role weight** | `classify_file_role` of dependents | breaking `production_code` matters more than `test`; `benchmark`/`dataset`/`generated` dependents weighted ~0 |
| **Subsystem spread** | distinct `discover_subsystems` buckets in the impact set | cross-subsystem changes are riskier than local ones |
| **Entrypoint reachability** | is the target on a resolved path from an entry file (§10)? | user-facing code (voice/cli/main) is higher stakes |
| **Cycle membership** | `statistics.import_cycles` | changes inside an import cycle ripple unpredictably |
| **Public surface** | has `cross_file`-scoped dependents (imported elsewhere) vs intra-file only | wider contract |

### 4.2 Combination and bucketing

- A fixed weighted sum of normalized factors → a numeric `risk_score`, mapped to
  `low` / `medium` / `high` by **fixed published thresholds**.
- Weights and thresholds are **constants documented in this report** and in the
  output (`risk.weights_version`) so a score is reproducible and reviewable.
- **Role guard:** `benchmark` / `dataset` / `generated` dependents never inflate
  risk (consistent with RU-2 — they are not production surface).
- Risk is **orthogonal to confidence** (§5): a high-risk target with low
  confidence is reported as "high potential blast radius, but the dependent set
  is incomplete" — the two scores are never multiplied into one misleading number.

---

## 5. Confidence scoring

Confidence answers "**how complete and trustworthy is this impact set?**" It is a
function of *unresolved* structure near the target and the analyzability of the
dependent files — **not** of how scary the change is.

### 5.1 Signals that lower confidence

- **Unresolved calls** touching the target's files (`unresolved.calls_unresolved`
  with reasons: `intra_file_unresolved`, method/attribute calls, `shadowed`,
  `dynamic_or_complex`) — real callers may be hidden.
- **Star / ambiguous imports** in candidate dependents (`star_import`,
  `ambiguous_import`) — a file that `from target import *` *might* use the symbol.
- **`symbol_not_found` / `third_party_or_unknown_module`** near the boundary.
- **`parse_errors`** in files that could plausibly depend on the target — those
  files are **opaque**; the engine can neither confirm nor deny dependency.
- **Degraded graph** (`too_many_files` / `too_many_functions`) ⇒ confidence
  `unknown` (the graph itself is incomplete).

### 5.2 Computation and buckets

- `resolved_ratio` = resolved edges incident to the impact frontier ÷ (those
  resolved edges + unresolved items that *could* reach the target).
- Mapped to `high` / `medium` / `low` / `unknown` by fixed thresholds, with any
  of {degraded, parse-opaque dependents present, star/ambiguous import in
  frontier} forcing **at most `medium`** and surfacing the reason.
- The bucket is paired with the **caveats list** (§6) so "low" is always
  explained, never bare.

**Rule:** low confidence changes the *wording and exit code*, not the asserted
set. The engine still reports exactly the resolved dependents; it simply states
the set may be incomplete and routes the unknowns to the possible/unverified
channel.

---

## 6. Unresolved edge handling

This is the core of "unknown beats guessing." The depgraph already enumerates
every unresolved relationship with a reason; the engine **routes**, never
**resolves**, them.

| depgraph source | Engine treatment |
|---|---|
| `unresolved.imports_external` (`third_party_or_unknown_module`, `star_import`) | **Excluded** from asserted impact (third-party). A *star import in a candidate dependent* is additionally listed under `possible_additional_impact` (the file might use the target). |
| `unresolved.calls_unresolved` (`intra_file_unresolved`, attribute/method, `shadowed`, `dynamic_or_complex`) | Listed under `possible_additional_impact` with file+line+reason. **Never** added to the asserted dependent set. |
| `unresolved.references_unresolved` (`base_class`, `decorator` unknown) | Same — possible inheritance/decoration dependency, unverified. |
| `parse_errors[]` | Listed under `unanalyzed` — files that could not be parsed; explicitly "cannot confirm or deny dependency." |
| `degraded` graph | Whole result flagged `confidence: unknown`, asserted set marked partial. |

**Three-channel contract for every query:**

1. `asserted` — resolved-edge dependents (high trust, full evidence).
2. `possible_additional_impact` — unresolved items that *could* reach the target,
   each with a reason; **explicitly not** part of the asserted answer.
3. `unanalyzed` — opaque files (parse errors / degraded).

A target with zero asserted dependents but non-empty channels 2/3 is reported as
**"no proven dependents; N possible, M unanalyzed — impact UNKNOWN,"** which is
categorically different from **"no dependents — safe."**

---

## 7. Output format

Two synchronized renderings, mirroring depgraph's existing `export_json` /
`format_summary` pattern (stable, sorted, schema-versioned).

### 7.1 Machine output (deterministic JSON)

Illustrative shape (a data contract, not code):

```
{
  "schema_version": 1,
  "weights_version": 1,
  "repository_root": "<abs/posix>",
  "target": {"kind": "function|module|file", "id": "...", "path": "...",
             "qualname": "...", "role": "production_code", "subsystem": "voice"},
  "questions": {
    "files_dependent":   [ {"path": "...", "role": "...", "via": ["imports","calls"],
                            "evidence": [{"type":"imports","from":"...","line":12}]} ],
    "functions_dependent":[ {"id": "function:...::q", "scope": "cross_file",
                            "line": 88} ],
    "modules_importing": [ {"id": "module:...", "dotted": "...", "line": 3} ],
    "execution_paths":   [ ["function:voice/voice_loop.py::handle",
                            "function:core/app.py::run",
                            "function:<target>"] ],
    "may_break": { "direct_count": N, "transitive_count": M, "truncated": false }
  },
  "risk":       {"bucket": "high", "score": 0.0, "factors": [ {"name":"fan_in","value":12} ]},
  "confidence": {"bucket": "medium", "resolved_ratio": 0.0, "caveats": ["star_import in a/b.py"]},
  "possible_additional_impact": [ {"file":"...","line":40,"reason":"intra_file_unresolved"} ],
  "unanalyzed": ["broken/file.py"],
  "degraded": false
}
```

Determinism requirements: all lists sorted by stable keys; floats rounded to a
fixed precision; identical repo ⇒ identical bytes (same guarantee depgraph
already meets).

### 7.2 Human summary

A `format_summary`-style text block: target line (path / role / subsystem),
then **DIRECT IMPACT**, **TRANSITIVE IMPACT (count + truncation note)**,
**EXECUTION PATHS** (or "no resolved path found — coverage is partial"),
**RISK** (bucket + top factors), **CONFIDENCE** (bucket + caveats),
**POSSIBLE (UNVERIFIED)**, **UNANALYZED**. Every asserted line shows `path:line`.

---

## 8. CLI design

A new top-level subcommand `impact`, sibling to the existing `graph` group,
reusing the established `_add_project_arg` and `.jarvis_builder/` conventions.
(Alternative considered: nest as `graph impact`. Rejected for UX — impact is a
distinct builder intent, not a graph-inspection mode. Either is mechanically
trivial; top-level chosen for discoverability.)

```
builder_core impact --file    path/to/x.py        [common opts]   # Q1 (+Q5 at file level)
builder_core impact --module  pkg.mod             [common opts]   # Q3
builder_core impact --function path/to/x.py::qual  [common opts]  # Q2, Q4, Q5
builder_core impact --paths-to path/to/x.py::qual  [common opts]  # Q4 explicit
```

- **Selectors** `--file | --module | --function | --paths-to` are mutually
  exclusive; exactly one is required (argparse mutually-exclusive group).
- **Common options:**
  - `--project <root>` (via existing `_add_project_arg`).
  - `--transitive` (default: direct + summary) / `--direct`.
  - `--max-depth N` (transitive bound, §11).
  - `--top N` (cap listed dependents; remainder summarized as "+K more").
  - `--json [PATH]` → deterministic JSON to stdout or to
    `<project>/.jarvis_builder/impact.json` (ephemeral, like `depgraph.json`).
- **Exit codes** (consistent with the `graph` group, which returns `2` when
  degraded): `0` = answered with `high`/`medium` confidence; `2` = `degraded`
  **or** `confidence: unknown` **or** target-not-found; nonzero-but-distinct for
  bad arguments. This lets scripts treat "unknown" as a first-class outcome.
- One graph build per invocation; all selectors answered from the single build.

---

## 9. Dependency graph integration

The engine is a **pure downstream consumer** of `depgraph`. It must not modify
depgraph, its schema, or its outputs.

- **Build/load:** call `depgraph.build_graph(root)` once per invocation (or load a
  previously exported `depgraph.json` of matching `schema_version`). No second
  walk of the repo.
- **Reverse indices:** from `graph["edges"]`, build three reverse maps keyed by
  `to`, partitioned by `type`, filtered to `resolved == true`. O(E), built once.
- **Reuse, don't reinvent:** node-id scheme (`module:`, `function:`, `class:`),
  the `resolved` flag, `scope`, `line`, `target_module`, and `kind` are consumed
  verbatim. `statistics.top_imported_modules` / `top_called_functions` provide
  fan-in shortcuts and a cross-check for Q2/Q3.
- **Degraded propagation:** if `graph["degraded"]` is set, the engine returns a
  degraded result (`confidence: unknown`) without traversal — it never fabricates
  an answer the graph can't support.
- **Schema pinning:** the engine asserts `graph["schema_version"] ==
  GRAPH_SCHEMA_VERSION` it was written against; a mismatch is reported as
  "rebuild the graph," not silently mis-read.

Because depgraph already merged `callgraph` (intra-file) and `cross_file`
(cross-file) into unified `calls` edges with a `scope` tag, the engine needs **no
direct dependency** on callgraph/cross_file/imports/module_map — it reads them
only through depgraph. (Those modules are listed as inputs because they define the
semantics the engine inherits.)

---

## 10. Repository understanding integration

`repository_understanding.py` supplies the *meaning* layer on top of the raw
graph:

- **Roles for weighting & filtering:** `classify_file_role` tags every dependent.
  Risk weighting (§4) uses the role; `benchmark` / `dataset` / `generated`
  dependents are de-weighted to ~0 so frozen corpora never dominate "what may
  break" (consistent with RU-2). Roles also annotate every output line.
- **Entrypoints for execution paths (Q4):** the entry-file set
  (`__init__.py`, `main.py`, `cli.py`, `router.py`, `runtime.py`, `engine.py`,
  `voice_loop.py`, `wakeword.py`, `app.py` — RU-2's `_ENTRY_NAMES`) and
  `production_subsystems` entry files define the **roots** of the reverse-BFS for
  execution paths. A path is `entry_fn → … → target` over resolved `calls` edges.
- **Subsystem grouping & spread:** `discover_subsystems` maps each impacted file
  to a top-level subsystem, powering the "subsystem spread" risk factor and a
  grouped human summary ("impacts voice (3), core (1)").

**Honest limitation (stated, not hidden):** execution paths are built only from
*resolved function-call edges*. Module-body invocation (`if __name__ ==
"__main__"`), method dispatch, and dynamic calls are not function-keyed/resolved,
so some real entrypoint→target paths cannot be reconstructed. When no resolved
path exists, the engine emits **"no resolved execution path found (call-graph
coverage is partial)"** plus any `possible_additional_impact` — it never claims
the code is unreachable.

---

## 11. Performance constraints

- **Inherit depgraph caps:** `_MAX_FILES = 5000`, `_MAX_FUNCTIONS = 50000`. Beyond
  these the graph is already `degraded`; the engine returns `unknown` without
  traversal.
- **One build per run.** Reverse-index construction is **O(E)**; a single query is
  a bounded reverse BFS, **O(V + E)** worst case, expand-once via visited-set.
- **Transitive bounds:** `--max-depth` default ~6, hard cap ~25; impact-set size
  cap (e.g. a few thousand) → `truncated: true` when hit. No unbounded closure.
- **Execution-path explosion guard:** enumerate at most K paths (e.g. 20), each at
  most L hops (e.g. 15); beyond that report "target reachable from <entry>; paths
  truncated" rather than enumerating exponentially many paths.
- **Memory:** reverse indices are id→id lists (no AST retained); the engine holds
  the graph dict plus three adjacency maps — linear in graph size.
- **No repeated work:** multiple questions for one target share the single build
  and the single reverse index. No re-parsing, no re-walking, no network.

Performance acceptance: on the local JARVIS repo (~5k Python files, i.e. at the
cap boundary) a single `impact` invocation completes within the same order of
magnitude as `graph summary` (which already builds the full graph), plus linear
traversal overhead.

---

## 12. Precision safeguards

The safeguards that keep the engine from "guessing":

1. **Resolved-only assertion.** Only `resolved == true` edges enter the asserted
   impact set. Unresolved edges are *routed*, never *resolved*.
2. **No name-only inference.** The engine never matches a symbol by name across
   files; it trusts only depgraph's resolver (which itself requires unambiguous
   import-table evidence).
3. **Possible ≠ proven.** Star/ambiguous/dynamic/method-call candidates live in a
   separate `possible_additional_impact` channel with reasons; they are never
   counted in fan-in, risk, or the asserted lists.
4. **Opaque ≠ absent.** `parse_errors` files are `unanalyzed`, distinct from "no
   dependency."
5. **"No proven impact" ≠ "safe."** When the asserted set is empty but channels
   2/3 are non-empty (or the graph is degraded), the verdict is **UNKNOWN**, with
   the reason — not "safe to change."
6. **Determinism.** Stable sorts, fixed weight/threshold constants
   (`weights_version`), rounded floats ⇒ identical repo produces identical output
   (cross-checkable in tests).
7. **Auditable evidence.** Every asserted dependent carries `path:line` + edge
   type so a human can verify it independently.
8. **Cross-check invariant.** Module in-degree computed by the engine must equal
   `statistics.top_imported_modules` counts for the same node — a built-in
   consistency assertion against the source graph.

---

## 13. Acceptance criteria

Because this phase is design-only, these are the criteria a **future**
implementation must satisfy (and the tests that would prove them). No code is
delivered now.

**Functional**

1. Given a file / module / function target, the engine answers all five questions
   from a single `depgraph.build_graph` result.
2. Asserted dependents contain **only** resolved-edge sources, each with
   `path:line` evidence and a role.
3. Unresolved edges that could reach the target appear in
   `possible_additional_impact` with their depgraph reason; **none** appear in the
   asserted set.
4. `parse_errors` dependents appear in `unanalyzed`.
5. Risk and confidence are reported as **separate** buckets, each with factors /
   caveats; weights and thresholds are versioned constants.
6. Execution-path queries return resolved `entry → … → target` chains or the
   explicit "no resolved path found (partial coverage)" message — never a guess.

**Safety / invariants**

7. **Zero** changes to detectors, the QuixBugs/holdout benchmark harness,
   promotion, `depgraph`, or `repository_understanding` behavior. (Benchmark
   re-run must remain QuixBugs 12 TP / 0 FP, holdout 2 TP / 0 FP.)
8. No LLM, no network, read-only, never executes analyzed code.
9. Deterministic: identical repo ⇒ byte-identical JSON across runs.
10. Degraded graph / target-not-found ⇒ `confidence: unknown` and exit code `2`.

**Regression tests (synthetic repos, to be authored with the implementation)**

11. `A imports B`, `B.f calls C.g` ⇒ `impact(--function .../C.py::g)` asserts `B.f`
    directly and `A` transitively (file-level), with evidence lines.
12. A `from target import *` dependent ⇒ target appears in
    `possible_additional_impact` (not asserted), confidence ≤ `medium`,
    caveat names the star import.
13. A method/attribute call to a target ⇒ unresolved; verdict UNKNOWN, not "safe."
14. A dependent with a syntax error ⇒ listed in `unanalyzed`.
15. Module in-degree equals `statistics.top_imported_modules` for that node.
16. Re-running the same query twice yields identical bytes.

---

## 14. Rollback strategy

The engine is **purely additive and side-effect-free**, designed for trivial,
behavior-neutral removal — following the existing Phase 93/94 patterns (the
`cross_file.CROSS_FILE_ENABLED` flag and the "remove the single agent
registration" note in `engine.py`).

- **Footprint:** one new module (e.g. `bug_intelligence/impact.py`) + one CLI
  subcommand registration block + its tests. No edits to detectors, depgraph,
  repository_understanding, indexer, retrieval, or the benchmark harness.
- **Feature flag:** an `IMPACT_ENABLED` constant (default on) gating the CLI
  registration; setting it false removes the command with no other change.
- **Hard rollback:** delete the module, the subcommand block, and the tests. Because
  the engine **only reads** depgraph output and **writes nothing** into any
  analysis path (its sole optional write is an ephemeral
  `.jarvis_builder/impact.json`), removing it cannot alter detector findings,
  benchmark verdicts, promotion, or `ask`/`graph` behavior.
- **No migrations:** no persisted schema, no index format change, no shared
  mutable state. `impact.json` is disposable cache output, never an input to
  another subsystem.
- **Verification after rollback:** the full Builder Core suite and the
  QuixBugs/holdout benchmarks must produce identical results to pre-Phase-94B
  (guaranteed by construction, since no shared code path is touched).

---

## Appendix A — Worked example (illustrative)

Target: `--function voice/router.py::Router.dispatch`.

- **Q2 functions_dependent (asserted):** `voice/voice_loop.py::handle_voice_command`
  (`calls`, `scope=cross_file`, line 22) — evidence-backed.
- **Q1 files_dependent (asserted):** `voice/voice_loop.py` (via the call above) and
  any module with a resolved `imports` edge to `voice/router.py`.
- **Q4 execution_paths:** `voice_loop.py::handle_voice_command → router.py::Router.dispatch`
  if that call resolves; otherwise "no resolved execution path found (partial
  coverage)" because `self.dispatch(...)` method calls are unresolved by design.
- **possible_additional_impact:** any `self.dispatch(...)` / dynamic call sites
  flagged `intra_file_unresolved` or method-call-unresolved.
- **risk:** elevated by entrypoint reachability (voice subsystem entry file) and
  production role; **confidence:** ≤ medium if method-call dispatch dominates the
  frontier — with the caveat spelled out.

## Appendix B — Open design questions (for review, not blockers)

1. **Class-change impact (Q5 for a class/method):** should editing a base class
   pull `references`(`base_class`) subclasses into asserted impact by default, or
   keep them as a separate "inheritance impact" sub-channel? (Leaning: separate
   sub-channel, since method-resolution is not modeled.)
2. **File vs symbol granularity in risk:** should a file-level query aggregate the
   max or the sum of its symbols' risk? (Leaning: report both — per-symbol detail
   plus a file roll-up.)
3. **Exported-graph reuse:** should `impact` prefer a fresh
   `build_graph` or an existing `.jarvis_builder/depgraph.json`? (Leaning: fresh
   by default for correctness; `--from-export` opt-in for speed.)
