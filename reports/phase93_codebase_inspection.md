# Phase 93 Codebase Inspection — Interprocedural Analysis Insertion Map

Date: 2026-05-30

Scope: Read-only architecture inspection. **No Phase 93 implementation.** No code changes except this report.

Goal: Map where interprocedural analysis (call graph + cross-function facts) should plug into the current Builder Core unified engine without disturbing benchmark-stable paths.

---

## 1. Current analysis pipeline

### Entry points (`engine.py`)

| API | Scope | Notes |
| --- | --- | --- |
| `analyze_source(text, rel_path)` | Single file | Primary pipeline |
| `analyze_file(path, project_root, index)` | Single file | Reads disk; `index` may carry `test_documents` |
| `analyze_repository(root)` | All `.py` files | **Independent per-file calls** to `analyze_source`; no shared state |
| `security_findings(root)` | Repo scan | Same per-file loop; `include_algorithm=False` |

### Per-file pipeline (`analyze_source`)

```
text
  -> ParseAgent.parse                    # ast.parse; errors captured
  -> FactExtractionAgent.extract         # facts.extract_module_facts
  -> LogicBugAgent.run(tree, lines)      # patterns.run_all (AST; some re-run dataflow)
  -> FactLogicAgent.run(module_facts)     # fact_detectors.all_detectors
  -> SecurityAgent.run(text)             # security.analyze_source (re-parses + re-runs valueflow)
  -> AlgorithmAgent.run(tree, text)      # semantic_reasoning.analyze_semantics (optional)
  -> FindingRankerAgent.rank             # finding.rank / dedupe
  -> AnalysisResult(facts=module_facts, findings=..., metadata=...)
```

Shared stateless agent singletons at module level (`_parse`, `_facts`, `_logic`, …).

### Parallel / legacy paths (do not conflate)

| Path | Module | Used by |
| --- | --- | --- |
| Unified engine | `engine.py` | CLI `analyze-file`, `bug-scan`, `security-scan` |
| Engine benchmark | `engine_benchmark.py` | QuixBugs + holdout via `engine.analyze_source` per pair file |
| Legacy semantic benchmark | `builder_core/benchmark.py` | CLI `benchmark-quixbugs --engine legacy` |
| Legacy analyzer | `bug_intelligence/analyzer.py` | Pre-Phase-90 API; separate from unified engine |

**Key gap for Phase 93:** `analyze_repository` walks files and calls `analyze_source` in isolation. There is no repository index, no call resolution, and no second pass over aggregated facts.

---

## 2. Current fact model

### Module envelope (`facts.extract_module_facts`)

```python
{
  "module": "<path>",
  "parse_error": "",
  "functions": [ ... unified per-fn records ... ],
  "test_expectations": [ ... optional, from semantic_reasoning ... ],
}
```

### Per-function unified record (merge of `valueflow` + `dataflow`)

Produced in `facts.py` by joining valueflow functions to dataflow functions on `(name, line)`, with name-only fallback.

| Field group | Source | Content |
| --- | --- | --- |
| Identity | valueflow | `name`, `line`, `params` |
| CFG / defs | valueflow | `cfg_blocks`, `definitions`, `uses`, `reaching_definitions` |
| Control | valueflow + dataflow | `branches`, `returns`, `return_summary`, `loops` |
| Calls | **dataflow only** | `calls`: `[{"func": "<dotted/unparsed callee>", "line": N}]` — **unresolved** |
| Containers | both | `container_mutations`, `container_state` |
| Value lattices | valueflow | `nullability`, `intervals` |
| Taint / security | valueflow | `taint_sources`, `taint_sinks`, `sanitizers`, `security_sensitive_calls`, `value_findings` |

**Not in unified facts today:** recursion detail (`dataflow` has `recursion` but `facts.py` does not merge it), cross-module edges, resolved callee symbols, summary facts at module/repo level.

### Underlying fact producers (intraprocedural only)

| Module | `analyze_source` output | Scope |
| --- | --- | --- |
| `dataflow.py` | `{module, functions:[{loops, containers, calls, recursion, def_use, ...}]}` | Per function; `_walk_local` skips nested defs |
| `valueflow.py` | `{module, functions:[{cfg, taint, nullability, return_summary, ...}]}` | Per function; nested defs skipped in flow |
| `facts.py` | Unified merge | Per module |

Both sub-analyzers use `ast.walk(tree)` over top-level module functions; nested functions get their own records but **calls inside them do not link to outer or other-file defs**.

---

## 3. Current finding model

### Unified schema (`finding.py`)

`Finding` dataclass — single output type for all agents.

| Field | Role |
| --- | --- |
| `category` | Closed set: `logic_bug`, `algorithm_bug`, `security_risk`, `maintainability`, `test_gap`, `unknown` |
| `kind` | Provenance: `data_flow`, `value_flow`, `security`, `semantic`, `pattern` |
| `severity`, `confidence` | Rank inputs (`weight = severity × confidence`) |
| `file`, `function`, `line` | Location |
| `rule` | Stable rule id (dedupe key with file+line) |
| `source_facts` | Trace strings for evidence section |
| Adapters | `from_pattern_finding`, `from_security_finding`, `from_semantic_finding` |

### Detector → finding routing

| Agent | Input | Output kind(s) |
| --- | --- | --- |
| `LogicBugAgent` | AST | `pattern` or `data_flow` (unguarded_container) |
| `FactLogicAgent` | `module_facts` | `pattern` or `value_flow` (inconsistent_return quarantined as `pattern`) |
| `SecurityAgent` | source text | `security`, `value_flow` |
| `AlgorithmAgent` | AST + tests | `semantic` |

### Benchmark grounding (`engine_benchmark.py`)

Verdict counts only `BENCHMARK_VERDICT_KINDS = {semantic, data_flow, value_flow}`. Security and quarantined `pattern` findings are excluded from QuixBugs/holdout verdicts by design.

**Phase 93 implication:** New interprocedural findings should use an explicit `kind` and pass through the promotion gate before affecting benchmark verdicts.

---

## 4. Where function-level facts are produced

```
ast.parse(text)
    |
    +-- dataflow.analyze_source
    |       _function_facts(fn)
    |         loops, containers, branches, returns
    |         calls[]          <-- raw call-site strings
    |         recursion        <-- direct self-calls only
    |         def_use
    |
    +-- valueflow.analyze_source
            analyze_function(fn, lines)
              _rd_walk, _build_cfg, FlowAnalyzer.run
              _return_summary, _container_state
              source_observations, sink_observations
    |
    v
facts.extract_module_facts  --> unified per-fn dict in module_facts["functions"]
```

**Call-site facts today (`dataflow.py` ~437–440):**

```python
calls = [
    {"func": _name(n.func), "line": n.lineno}
    for n in _walk_local(fn) if isinstance(n, ast.Call)
]
```

Callee is a **string label** (`foo`, `pkg.mod.bar`, `self.method` unparsed). No link to a definition site, no import resolution, no class dispatch.

**Taint at calls (`valueflow.py` `_eval_Call`):** Treats unknown callees as generic taint propagators; does not follow into callee bodies.

---

## 5. Where module-level aggregation happens

| Location | What is aggregated | Cross-file? |
| --- | --- | --- |
| `facts.extract_module_facts` | Merges VF+DF per function; attaches `test_expectations` | No |
| `engine.analyze_source` | Wraps facts in `AnalysisResult`; builds `metadata.taint_sources` from all functions | No |
| `engine.analyze_repository` | List of `AnalysisResult`; `rank_files` sorts by score | **No linking** |
| `patterns.detect_unguarded_container_consumption` | Re-runs `dataflow.analyze_source` on joined lines (duplicate work) | No |
| `security.analyze_source` | Re-runs full `valueflow` per file | No |

**There is no module-level or repository-level fact index today.** Aggregation for CLI repo scans is finding-level only (`rank_files`, `security_findings`).

---

## 6. Safest insertion point for call graph

### Recommended architecture (minimal risk)

**Two-pass repository analysis**, keeping intraprocedural layers frozen:

```
Pass 1 (existing, unchanged per file):
  analyze_source -> module_facts only (or full analyze with interprocedural agents disabled)

Pass 2 (new, Phase 93):
  callgraph.build_index(all_module_facts) -> CallGraphIndex
  interprocedural_facts.enrich(module_facts, index)   # optional per-fn annotations
  interprocedural_detectors.run(index, module_facts) -> List[Finding]

Merge findings into AnalysisResult before ranker (or run ranker once at repo level).
```

### Safest hook points (ordered)

| Priority | Location | Rationale |
| ---: | --- | --- |
| **1** | **New `callgraph.py`** + thin `CallGraphAgent` in `agents.py` | Isolated; consumes existing `calls[]` facts; no change to VF/DF |
| **2** | **New `interprocedural_detectors.py`** (or extend `fact_detectors.py` with a separate entry) | Same pattern as Phase 92B; reads facts + graph, emits `Finding` |
| **3** | **`engine.analyze_repository` only** | Add optional second pass; leave `analyze_source` single-file behavior unchanged for benchmarks |
| **4** | **`facts.py` optional keys** | e.g. `"call_edges_out"`, `"call_edges_in"` on each function record — additive, backward compatible |

### Do **not** insert call graph inside

| Module | Why |
| --- | --- |
| `valueflow.py` / `FlowAnalyzer` | Intraprocedural taint/CFG; interprocedural taint is high-risk and benchmark-adjacent |
| `dataflow.py` loop/container logic | Stable Phase 86–87 fact layer; BFS rule depends on it |
| `patterns.py` | Re-parses and re-runs dataflow; benchmark-sensitive |
| `semantic_reasoning.py` | Legacy benchmark path + algorithm invariants |
| `security.py` | Separate re-analysis path; interprocedural taint needs its own design |
| `engine_benchmark.py` | Measurement contract; should stay on single-file `analyze_source` unless explicitly extended |

### Engine wiring sketch (future, not implemented)

```python
# analyze_repository (conceptual)
results_pass1 = [analyze_source(text, rel) for ...]
index = callgraph.build_from_results(results_pass1)
for r in results_pass1:
    r.findings.extend(interprocedural_detectors.run(index, r.facts, r.file))
    r.findings = ranker.rank(r.findings)
```

Single-file `analyze_file` can skip Pass 2 or run with an empty/partial index.

---

## 7. Risky files not to touch (Phase 93 prep)

| File | Risk |
| --- | --- |
| `valueflow.py` | 900+ lines; security taint; nested-def skip logic is subtle |
| `dataflow.py` | Fact-layer contract for Phase 86–87; `find_unbounded_frontier_loops` feeds grounded benchmark |
| `patterns.py` | AST heuristics + duplicate dataflow invocation; QuixBugs BFS detection |
| `semantic_reasoning.py` | Algorithm benchmark stability |
| `engine_benchmark.py` | Grounded verdict kinds; holdout/QuixBugs parity tests |
| `finding.py` | Schema + `FACT_BACKED_RULES` + promotion metadata |
| `security.py` | Independent analysis path; duplicate parse acceptable today |
| `builder_core/benchmark.py` | Legacy measurement baseline |
| `brain/*`, `voice/*`, `router.py` | Out of Builder Core scope |

**Lower risk (preferred touch surfaces):** new modules, `agents.py` (add agent class only), `engine.py` (`analyze_repository` extension), `fact_detectors.py` (only if keeping interprocedural rules separate is insufficient).

---

## 8. Proposed minimal new files (Phase 93 — not created yet)

| File | Responsibility |
| --- | --- |
| `builder_core/bug_intelligence/callgraph.py` | Collect `calls[]` from module facts; resolve edges (same-module defs, import aliases, simple `Class.method`); expose `CallGraphIndex` |
| `builder_core/bug_intelligence/interprocedural_facts.py` | Optional enrichments: `callees_resolved`, `callers`, `entry_points`, `unresolved_calls` |
| `builder_core/bug_intelligence/interprocedural_detectors.py` | Fact+graph detectors (e.g. unchecked return used by caller, taint entry via wrapper); promotion-gated |
| `builder_core/bug_intelligence/agents.py` | Add `CallGraphAgent`, `InterproceduralAgent` (thin delegates) |
| `builder_core/tests/test_phase93_callgraph.py` | Multi-file fixtures; resolution; no benchmark regression |
| `reports/phase93_interprocedural_plan.md` | Design doc after this inspection (optional follow-up) |

**Avoid for v1:** changing `valueflow` for interprocedural taint; modifying `engine_benchmark.py` corpus; new grounded rules until FP gate passes.

---

## 9. Existing building blocks for call graph

| Asset | Location | Usable as-is? |
| --- | --- | --- |
| Call-site list | `dataflow` → merged into `module_facts["functions"][].calls` | Yes — primary edge source |
| Function identity | `(name, line)` in facts merge | Yes — disambiguate overloads / nested same-name |
| Self-recursion | `dataflow.recursion` (not merged into unified facts) | Expose via `facts.py` if needed |
| Import graph | Not built | Phase 93 must add lightweight import indexing |
| Class hierarchy | Not built | Defer or approximate |
| Repo file list | `engine._collect_python_files` | Yes |

---

## 10. Test gaps (relevant to Phase 93)

### Covered today (intraprocedural / single-file)

| Test file | Focus |
| --- | --- |
| `test_phase86_dataflow.py` | Loops, containers, def-use, fact queries |
| `test_phase87_dataflow_rewire.py` | BFS grounded rule, name-freedom |
| `test_phase89_value_dataflow_taint.py` | CFG, taint, null-deref |
| `test_phase90_unified_engine.py` | Pipeline, schema, CLI sections |
| `test_phase91_benchmark_engine.py` | QuixBugs via unified engine |
| `test_phase92a_holdout_on_engine.py` | Holdout + grounded kinds |
| `test_phase92b_inconsistent_return.py` | Fact detector + quarantine gate |
| `test_bug_intelligence.py` | Pattern detectors + repo rank (legacy analyzer path) |

### Missing for interprocedural work

| Gap | Impact |
| --- | --- |
| No multi-file / cross-module fixtures | Cannot validate call resolution |
| No tests for `calls[]` in unified facts | Edge collection unasserted at merge layer |
| `analyze_repository` not tested for cross-file behavior in unified engine | Repo pass is file-isolated |
| Duplicate analysis paths untested (`SecurityAgent` vs `FactExtractionAgent` both run valueflow) | Consistency risk if one path gets interprocedural treatment |
| No import alias / re-export resolution tests | Required for realistic Python call graph |
| No promotion gate for new interprocedural rules | Must mirror Phase 92B QuixBugs+holdout zero-FP gate |
| Benchmark tests assume single-file pairs | Engine benchmark should remain stable if interprocedural is repo-only |

### Suggested test additions (Phase 93)

1. Minimal 2–3 file package: `a.py` calls `b.helper`; assert resolved edge.
2. Unresolved dynamic call (`getattr`, `fn()`) stays in `unresolved_calls`.
3. `analyze_repository` second pass adds findings not visible in isolated `analyze_source`.
4. Regression: `test_phase91_*`, `test_phase92a_*`, `test_phase92b_*` unchanged when running single-file benchmark paths.

---

## 11. Summary diagram

```
                    REPOSITORY (Phase 93 addition)
                              |
         +--------------------+--------------------+
         |                    |                    |
    file A.py              file B.py            file C.py
         |                    |                    |
   analyze_source        analyze_source       analyze_source   [Pass 1 - existing]
         |                    |                    |
   module_facts_A         module_facts_B       module_facts_C
         |                    |                    |
         +--------------------+--------------------+
                              |
                    callgraph.build_index()        [Pass 2 - NEW]
                              |
              interprocedural_detectors.run()
                              |
                    FindingRankerAgent.rank()
                              |
                      AnalysisResult[]
```

**Bottom line:** Phase 93 should add a **repository-level call graph layer** that reads existing per-function `calls[]` facts, resolves edges in a new module, and runs new detectors **after** intraprocedural fact extraction. Keep `analyze_source` and benchmark paths unchanged until interprocedural rules pass the promotion gate.

---

## 12. Files inspected

```
builder_core/bug_intelligence/engine.py
builder_core/bug_intelligence/facts.py
builder_core/bug_intelligence/valueflow.py
builder_core/bug_intelligence/dataflow.py
builder_core/bug_intelligence/agents.py
builder_core/bug_intelligence/fact_detectors.py
builder_core/bug_intelligence/engine_benchmark.py
builder_core/bug_intelligence/finding.py          (finding model)
builder_core/bug_intelligence/patterns.py         (LogicBugAgent backend)
builder_core/bug_intelligence/security.py         (SecurityAgent backend)
builder_core/tests/                             (9 test modules)
```

No analyzer code modified.
