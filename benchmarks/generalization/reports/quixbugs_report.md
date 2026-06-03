# Generalization Report — QuixBugs

**Language:** python · **Framework:** algorithms corpus · **Category:** python
**Path:** `C:\repos\quixbugs`
**Status:** ok

## Repository Summary

- Modules: **4** · Edges: **0** · Subsystems: 9 · Files: 365
- Massive mode: False · graph detail: full · scan time: 0.9s

## Final Score

| Understanding | Impact | Investigation | Build Plan | **Overall** |
|---:|---:|---:|---:|---:|
| 65.0 | 12.3 | 100.0 | 81.2 | **61.2** |

## Repository Understanding Results

Score **65.0** / 100. Components: graph_built 0.0, explanation 15.0, subsystems 15.0, entry_points 10.0, runtime_boundaries 0.0, top_risks 10.0, hubs_vs_risks_separated 15.0

## Impact Results

Score **12.3** / 100 · resolution rate 0.143 · fallback rate 0.857 (1/7 concepts resolved).

- `what breaks if I remove authentication` → label=None modules=[] direct=0 indirect=0
- `what breaks if I remove caching` → label=None modules=[] direct=0 indirect=0
- `what breaks if I remove configuration` → label=None modules=[] direct=0 indirect=0
- `what breaks if I remove the logging layer` → label=None modules=[] direct=0 indirect=0

## Investigation Results

Score **100.0** / 100 · grounded 1.0 · clean (no dotfiles) 1.0 · avg modules/symptom 4.0.

- `duplicate events are being fired` → ['tester.py', 'conftest.py', 'python_testcases/node.py']
- `websocket connections keep disconnecting` → ['tester.py', 'conftest.py', 'python_testcases/node.py']
- `authentication fails intermittently` → ['tester.py', 'conftest.py', 'python_testcases/node.py']

## Build Plan Results

Score **81.2** / 100 · plans with affected modules 1/4.

- `add distributed tracing` → []
- `add rate limiting` → []

## Failure Analysis

| Scenario | Expected | Actual | Root cause | Subsystem | Category |
|---|---|---|---|---|---|
| repository_understanding | >=30 modules indexed | 4 modules | graph sparse/degraded for this layout | graph build | graph_failure |
| runtime_boundaries | boundary modules identified | none | no cross-subsystem boundaries detected for this layout | architecture analyzer | architecture_failure |
| what breaks if I remove authentication | concept resolves to modules | fallback / no target | concept absent from repo or not in resolver map | target_resolver / impact_engine | semantic_routing_failure |
| what breaks if I remove caching | concept resolves to modules | fallback / no target | concept absent from repo or not in resolver map | target_resolver / impact_engine | semantic_routing_failure |
| what breaks if I remove configuration | concept resolves to modules | fallback / no target | concept absent from repo or not in resolver map | target_resolver / impact_engine | semantic_routing_failure |
| what breaks if I remove the logging layer | concept resolves to modules | fallback / no target | concept absent from repo or not in resolver map | target_resolver / impact_engine | semantic_routing_failure |
| what breaks if I remove the database layer | concept resolves to modules | fallback / no target | concept absent from repo or not in resolver map | target_resolver / impact_engine | semantic_routing_failure |
| what breaks if I remove the graph algorithms | concept resolves to modules | fallback / no target | concept absent from repo or not in resolver map | target_resolver / impact_engine | semantic_routing_failure |
| add distributed tracing | affected modules | none | no module matched the build concept in this repo | planning_engine | build_plan_failure |
| add rate limiting | affected modules | none | no module matched the build concept in this repo | planning_engine | build_plan_failure |
| add audit logging | affected modules | none | no module matched the build concept in this repo | planning_engine | build_plan_failure |

## Top 5 Failures

### 1. Concept "the logging layer" not resolved (fallback)

- **Failure:** Concept "the logging layer" not resolved (fallback)
- **Frequency:** 6 repositories (this repo: 1 scenario)
- **Root Cause:** concept absent from repo or not in resolver map
- **Suggested Future Phase:** Phase 137 — Semantic Generalization (universal concept inference beyond the HA-tuned map)

### 2. Concept "caching" not resolved (fallback)

- **Failure:** Concept "caching" not resolved (fallback)
- **Frequency:** 3 repositories (this repo: 1 scenario)
- **Root Cause:** concept absent from repo or not in resolver map
- **Suggested Future Phase:** Phase 137 — Semantic Generalization (universal concept inference beyond the HA-tuned map)

### 3. Concept "configuration" not resolved (fallback)

- **Failure:** Concept "configuration" not resolved (fallback)
- **Frequency:** 3 repositories (this repo: 1 scenario)
- **Root Cause:** concept absent from repo or not in resolver map
- **Suggested Future Phase:** Phase 137 — Semantic Generalization (universal concept inference beyond the HA-tuned map)

### 4. Concept "authentication" not resolved (fallback)

- **Failure:** Concept "authentication" not resolved (fallback)
- **Frequency:** 2 repositories (this repo: 1 scenario)
- **Root Cause:** concept absent from repo or not in resolver map
- **Suggested Future Phase:** Phase 137 — Semantic Generalization (universal concept inference beyond the HA-tuned map)

### 5. Graph sparse/degraded (<30 modules indexed)

- **Failure:** Graph sparse/degraded (<30 modules indexed)
- **Frequency:** 1 repository (this repo: 1 scenario)
- **Root Cause:** graph sparse/degraded for this layout
- **Suggested Future Phase:** Phase 139 — Universal Graph Construction (multi-language AST/import coverage)
