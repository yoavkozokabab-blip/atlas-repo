# Phase 94A — Dependency Graph Implementation

Date: 2026-05-31

Status: **Implemented**

Design input: `reports/phase94_dependency_graph_design.md`

Scope: Deterministic structure-only dependency graph assembled from existing static resolvers. No LLM, no semantic edges, no detector/benchmark changes.

---

## 1. What was built

| Component | Path |
| --- | --- |
| Graph assembler + serializer | `builder_core/bug_intelligence/depgraph.py` |
| Optional engine entry point | `engine.build_dependency_graph(root)` |
| CLI | `builder_core.cli graph {build,summary,export}` |
| Tests | `builder_core/tests/test_phase94a_depgraph.py` |

---

## 2. Graph model

### Node types

| Type | Identity | Key attributes |
| --- | --- | --- |
| `repository` | `repository:<abs_root>` | `python_files`, `root` |
| `module` | `module:<rel_path>` | `dotted`, `is_package`, `parse_ok`, `line_count` |
| `class` | `class:<rel_path>::<qualname>` | `line`, `bases` |
| `function` | `function:<rel_path>::<qualname>` | `line`, `params`, `is_async`, `decorators` |

### Edge types

| Type | From → To | Source module | `resolved` |
| --- | --- | --- | --- |
| `contains` | repo→module, module→class/function, class→method, function→nested | AST + `callgraph._compute_qualnames` | always `true` |
| `imports` | module → module | `imports.py` + `module_map` | `true` for project modules only |
| `calls` | function → function | `callgraph` (intra) + `cross_file` (cross) | `true` only |
| `references` | class/function → class/function | import-table resolution of bases/decorators | `true` only |

Unresolved relationships are **not** fabricated as project edges. They are recorded under:

```json
"unresolved": {
  "imports_external": [...],
  "calls_unresolved": [...],
  "references_unresolved": [...]
}
```

---

## 3. Construction algorithm

Single deterministic pass (reuses existing resolvers read-only):

1. Collect Python files (`engine._collect_python_files`), sorted by path.
2. Parse each file once; syntax error → `module` node with `parse_ok=false`, no contents.
3. Build `module_map`; create repository + module nodes and `contains` edges.
4. Walk AST qualnames for class/function nodes and `contains` hierarchy.
5. Emit `imports` edges from module-level import table.
6. Emit intra-file `calls` from `callgraph.build_call_graph`.
7. Emit cross-file `calls` from `cross_file.build_project_context` resolved edges.
8. Emit `references` for resolved imported base classes and decorators.
9. Sort nodes/edges; compute statistics.

Caps inherited from Phase 93C: `_MAX_FILES=5000`, `_MAX_FUNCTIONS=50000`. Exceeded → degraded graph (repository node only + reason).

---

## 4. Graph export

```python
depgraph.export_json(graph)  # sort_keys=True, indent=2, trailing newline
```

Same repository bytes → byte-identical JSON (tested).

Schema version: `1`

---

## 5. Graph statistics

Embedded in `graph["statistics"]`:

| Field | Description |
| --- | --- |
| `node_counts` / `edge_counts` | Per-type counts |
| `total_nodes` / `total_edges` | Totals |
| `top_imported_modules` | Top 10 by resolved `imports` indegree |
| `top_called_functions` | Top 10 by resolved `calls` indegree |
| `largest_components` | Top 10 undirected connected components (any edge type) |
| `import_cycles` | Module import cycles (DFS) |
| `unresolved_counts` | Counts per unresolved bucket |

Human-readable summary: `depgraph.format_summary(graph)`

---

## 6. CLI

Equivalent to the requested `jarvis graph` commands via Builder Core CLI:

```powershell
# Build + short confirmation
py -3 -m builder_core.cli graph build --project .

# Full statistics
py -3 -m builder_core.cli graph summary --project .

# Deterministic JSON export (default: .jarvis_builder/depgraph.json)
py -3 -m builder_core.cli graph export --project .
py -3 -m builder_core.cli graph export --project . --output path\to\depgraph.json
```

Each command rebuilds from source (Phase 94 Option A ephemeral — no incremental cache).

---

## 7. Engine entry point

```python
from builder_core.bug_intelligence import engine
graph = engine.build_dependency_graph(project_root)
```

Additive only. Does **not** modify `analyze_source`, findings, or benchmark paths.

---

## 8. Tests

`builder_core/tests/test_phase94a_depgraph.py` (13 tests):

| Test | Coverage |
| --- | --- |
| `test_contains_hierarchy_small_repo` | repo→module→function spine |
| `test_cross_file_call_edge` | `import a` + `a.f()` cross-file `calls` |
| `test_intra_file_call_edge` | same-file direct call |
| `test_unresolved_external_import_not_project_edge` | `import requests` → unresolved, no project import edge |
| `test_unresolved_call_not_edge` | unknown callee → annotation, no edge |
| `test_import_cycle_detected` | `a↔b` import cycle in statistics |
| `test_imports_resolved_between_project_modules` | package import edge |
| `test_parse_error_module_node_without_contents` | broken file isolated |
| `test_export_is_deterministic` | byte-identical JSON |
| `test_statistics_top_lists` | top called function ranking |
| `test_engine_entry_point` | `build_dependency_graph` |
| `test_benchmark_unchanged` | mini QuixBugs 1 TP / 0 FP unchanged |
| `test_build_graph_cli_smoke` | `graph build` command |

Full suite: **223 passed**.

---

## 9. Constraints honored

| Constraint | Status |
| --- | --- |
| No LLM | yes |
| No semantic / AI edges | yes |
| Unknown beats guessing | yes — unresolved explicit |
| Reuses `module_map`, `imports`, `callgraph`, `cross_file` | yes — read-only |
| No detector changes | yes |
| No benchmark changes | yes — QuixBugs/holdout tests unchanged |
| Ephemeral (no auto cache) | yes — export only on explicit command |
| Not consumed by detectors | yes |

---

## 10. Files changed

| File | Change |
| --- | --- |
| `builder_core/bug_intelligence/depgraph.py` | **new** |
| `builder_core/bug_intelligence/engine.py` | **additive** `build_dependency_graph()` only |
| `builder_core/cli.py` | **additive** `graph` subcommands |
| `builder_core/tests/test_phase94a_depgraph.py` | **new** |
| `reports/phase94a_dependency_graph_implementation.md` | **new** |

**Not changed:** `fact_detectors.py`, `finding.py`, `engine_benchmark.py`, `patterns.py`, `semantic_reasoning.py`, resolvers (read-only consumption).

---

## 11. Example statistics (mini fixture)

For a three-module package with cross-file call:

```
nodes: 7 (1 repo, 3 modules, 3 functions)
edges: contains + imports + calls
top_called_functions: helper (indegree from cross-file callers)
import_cycles: none
```

---

## 12. Future work (out of scope for 94A)

- Disk cache with content-hash invalidation (Phase 94 Option B)
- Impact analysis / architecture viz consumers (separate gated phases)
- `references` expansion (module-level name bindings)
- Incremental rebuild

---

## 13. Verification commands

```powershell
py -3 -m pytest builder_core\tests\test_phase94a_depgraph.py -q
py -3 -m pytest builder_core\tests\ -q
py -3 -m builder_core.cli graph summary --project .
```
