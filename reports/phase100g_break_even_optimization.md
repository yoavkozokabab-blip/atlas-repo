# Phase 100G — Break-Even Optimization Analysis

**Status:** Analysis + optimization design. No implementation.
**Date:** 2026-06-01
**Input:** `reports/phase100e_context_compression_execution.md`
**Question:** Why was break-even **2,227 tasks**, and how is it reduced?
**Constraint posture:** all proposals are deterministic and **change no detector,
finding, or benchmark behavior** — they only change *when and how* the index/graph
is computed and stored.

---

## 0. Why break-even is 2,227 (the math)

Break-even `N` is where cumulative steady-state savings repay the one-time build:

```
N × per_task_savings  =  build_cost
N = build_cost / per_task_savings
  = 6,453,965 token-equiv  /  ~2,898 token-equiv saved per task
  ≈ 2,227 tasks
```

The numerator dominates. Per-task savings (~2.9K tokens; suite compression 3.17×,
70.5% cost reduction) are **healthy** — that side already works. The problem is a
**6.45M token-equivalent, 316.7-second build** that is treated as a **per-run** cost
(rebuilt from scratch) with **no persistence and no incremental reuse**.

Two independent levers move 2,227 toward ~1:

1. **Shrink the build** (this report §1–§2): it is doing large amounts of provably
   unnecessary work, including a **degraded depgraph that returns nothing**.
2. **Stop rebuilding it** (this report §3–§4): persist once, update incrementally, so
   the build is amortized over the repository's entire query lifetime, not 20 tasks.

**Bonus finding (§5):** the degraded depgraph also *lowers Arm B quality* on impact
tasks — so fixing it improves the PARTIAL verdict's quality side too.

---

## 1. Indexing cost drivers

`indexer.build_index` (the larger half of the build) does, in one pass:

| Driver | What it costs | Evidence |
|---|---|---|
| **Per-file static analysis at index time** | Runs `python_analysis.analyze_python` (full AST parse + logic/semantic/fact detector passes) on **every production `.py` (≈665 files)** during `init` | `indexer.py:242` loops `analyze_python(...)` over `python_sources` |
| **Full text read + chunking** | Reads and chunks ~4,060 indexed files (doc + code chunkers, up to `MAX_TOTAL_CHUNKS`) | `build_index` walk + `_doc_chunks`/`_code_chunks` |
| **Git history scan** | `recent_log` + `churn_counts` over the repo | `indexer.py` git block |
| **Role classification + subsystem map** | `classify_file_role` per file + `discover_subsystems` (re-parses production docs for imports) | RU-2 path |

**Dominant driver:** the **per-file detector analysis** (`analyze_python` × 665).
This is the heavy CPU in the index build, and most of it is **premature** — the vast
majority of `ask`/`graph`/`impact` queries never read precomputed per-file findings.
It is paid eagerly at build time and re-paid on every rebuild.

---

## 2. Depgraph cost drivers

`depgraph.build_graph` is the second half — and it is the clearest waste.

| Driver | What it costs | Evidence |
|---|---|---|
| **No role filter on the file walk** | Walks + **reads every `.py` in the repo** via `engine._collect_python_files`, whose `SKIP_DIRS` excludes only VCS/build dirs — **not `data/`, not benchmark corpora** | engine `SKIP_DIRS` has no `data`/`external_benchmarks` entry |
| **Reads the benchmark corpora** | **5,984 of 7,539 `.py` (79%) live under `data/`** (BugsInPy probe + corpora) and are read on every build | measured: `find data -name '*.py'` = 5,984; total = 7,539 |
| **Degrades after paying I/O** | 7,539 > `_MAX_FILES = 5000` → returns `too_many_files` **degraded graph** — i.e. it reads thousands of files and produces an **empty** graph | `depgraph.degraded = True` in 100E; `_MAX_FILES=5000` |
| **(When not degraded) re-parse + qualnames** | `ast.parse` every file (again — the indexer already parsed production files), `_compute_qualnames` for all functions, `_attach_parents` whole-tree walk per file, `module_map`, import tables, per-file call graphs, `cross_file` project context (O(functions)) | `build_graph_from_files` |

**Root cause of the degraded graph:** the depgraph counts **7,539** Python files
because it never applies the RU-2 role filter that the indexer already uses
(`is_indexable` excludes `benchmark`/`dataset`/`generated`). Remove the 5,984 `data/`
files and the count is ~1,555 — **well under the 5,000 cap**, so the graph is no
longer degraded, and 79% of the walk/read disappears.

**This single fix (apply the RU-2 role filter to the depgraph walk) both cuts the
build I/O by ~79% and converts a useless degraded graph into a real one.**

---

## 3. Caching opportunities

Today there is **no content-hash or mtime caching** anywhere in the build (grep
found none; the depgraph docstring states it *"does not implement incremental disk
caching"*). Every `init` rebuilds everything from zero. Opportunities, ranked:

| # | Opportunity | Effect |
|---|---|---|
| 3.1 | **Persist the depgraph** to `./.jarvis/` (the index is already persisted via `store.save_index`; `depgraph.export_json` exists but is unused by the build) | The 6.45M build becomes a **once-per-commit** cost reused by every query, not per-run |
| 3.2 | **Per-file content-hash cache** — key each file's `{role, chunks, AST, analysis}` by a hash of its bytes; on rebuild, reuse cache for unchanged files | Rebuild cost ∝ **changed** files, not all files |
| 3.3 | **Share parsed ASTs across stages** — the indexer (`analyze_python`), the depgraph, and `discover_subsystems` each parse the same files independently (2–3× redundant `ast.parse`); parse once, pass the tree | Removes duplicate parsing of every production file |
| 3.4 | **Memoize `module_map` / qualnames** — deterministic from the file set; cache keyed by the set hash | Avoids recompute when the file set is unchanged |
| 3.5 | **Cache the per-file detector analysis** (the §1 dominant driver) keyed by content hash | Unchanged files skip re-analysis entirely |

Persistence (3.1) is the highest-leverage single change: it directly removes the
"rebuilt per run" assumption that *creates* the 2,227 break-even framing.

---

## 4. Incremental update opportunities

Caching answers "don't recompute unchanged files." Incremental update answers "after
the first build, only touch what changed."

| # | Opportunity | Effect |
|---|---|---|
| 4.1 | **Git-diff-driven re-index** — after the first build, process only `git diff --name-only <last_indexed_commit>..HEAD`; reuse cached entries for everything else | A typical commit touches a handful of files → build delta is **near-zero** |
| 4.2 | **Per-file hash short-circuit** — even without git, compare each file's content hash to the cached hash; recompute only on mismatch | Robust to non-git edits |
| 4.3 | **Dependency-aware depgraph refresh** — when file `X` changes, recompute `X`'s nodes/edges plus only the edges that *touch* `X`. The set of dependents whose cross-file edges need refresh is exactly the **reverse-dependency closure of `X`**, which the **Phase 94B impact engine already computes** | A 1-file change refreshes ~`X` + its direct dependents, not the whole graph |
| 4.4 | **Subsystem-map delta** — `discover_subsystems` only needs recompute for subsystems containing a changed file | Avoids full re-derivation |

**Key reuse:** 4.3 needs no new analysis — the 94B impact engine *is* the
reverse-dependency oracle. Incremental depgraph maintenance is "impact analysis run
backward at write time."

---

## 5. The compounding effect (and a quality bonus)

Applying the levers in order:

| Stage | Change | Build cost | Effective break-even |
|---|---|---|---|
| Today | rebuild-everything, walk all 7,539 `.py`, degraded graph, eager per-file analysis | ~6.45M / 316.7s | **~2,227** |
| + §2 role filter | depgraph skips 5,984 `data/` files; graph no longer degraded | I/O −~79% on the graph half; usable graph | lower |
| + §1 defer/cache analysis | stop eager per-file detector analysis at index time (or cache it) | removes the dominant index CPU | lower |
| + §3.1 persist | pay the build **once per commit**, not per run | amortized over the repo's whole query lifetime | **→ ~1** |
| + §4 incremental | per-commit delta ∝ changed files | near-zero ongoing | **~1, sustained** |

The two levers are multiplicative: a smaller build (§1–§2) **and** a build paid once
then incrementally (§3–§4) collapse 2,227 toward the first build only.

**Quality bonus (addresses the PARTIAL verdict):** in 100E the impact tasks that
should be JARVIS's strongest (`I2`, `I4`, `I6`) scored **Q(B)=1** — low — precisely
because the depgraph was **degraded/empty**, so `impact-file`/`impact-module` had no
graph to answer from. The §2 role filter that fixes the build cost **also restores a
real graph**, which should raise those impact-task quality scores — improving the
`quality_non_inferiority` gate that 100E failed, not just the break-even.

---

## 6. Recommendations (ranked by leverage / effort)

| Rank | Action | Lever | Risk |
|---:|---|---|---|
| 1 | **Apply the RU-2 role filter to the depgraph file walk** (exclude `benchmark`/`dataset`/`generated`) | §2 — −79% files, un-degrades the graph, +quality | Low (pure scope reduction; benchmark corpora are not architecture) |
| 2 | **Persist the depgraph to `./.jarvis/`** and load it instead of rebuilding | §3.1 — removes per-run rebuild | Low (index already persists) |
| 3 | **Defer or content-hash-cache per-file detector analysis** at index time | §1/§3.5 — removes dominant index CPU | Low–Med (ensure queries that need findings still get them) |
| 4 | **Git-diff + per-file hash incremental rebuild** | §4.1/§4.2 — near-zero per-commit delta | Med (cache-invalidation correctness; verify byte-stable output vs full rebuild) |
| 5 | **Share parsed ASTs across indexer/depgraph/subsystems** | §3.3 — removes 2–3× redundant parsing | Med (refactor; keep determinism) |
| 6 | **Dependency-aware (impact-driven) depgraph refresh** | §4.3 — minimal-set graph maintenance | Med–High (correctness of the refresh closure) |

**Safety invariant for all of the above:** outputs must remain **byte-identical** to
a from-scratch build for the same commit (determinism is the product's trust
contract). Every incremental/cached path must be validated against a full rebuild on
the QuixBugs/holdout/`local_jarvis` snapshots; detectors, findings, and benchmark
numbers (QuixBugs 12/0, holdout 2/0) must not move.

---

## 7. Bottom line

Break-even is 2,227 because a **6.45M-token-equivalent build** is repaid by only
**~2.9K tokens/task** — and that build is **bloated and thrown away each run**. It is
bloated chiefly because the **depgraph walks 7,539 `.py`, 79% of them benchmark
corpora under `data/`, then degrades past the 5,000-file cap and returns an empty
graph**, while the indexer eagerly runs full per-file detector analysis. Apply the
RU-2 role filter (−79% files, un-degrade), persist the graph, cache/defer per-file
analysis, and rebuild incrementally from `git diff`, and the effective break-even
collapses from **2,227 to ≈1 first build** — while *also* restoring the depgraph that
the impact tasks needed to pass the quality gate.
