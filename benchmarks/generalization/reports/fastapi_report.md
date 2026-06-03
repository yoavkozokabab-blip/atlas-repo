# Generalization Report — FastAPI

**Language:** python · **Framework:** web framework · **Category:** python
**Path:** `C:\J.A.R.V.I.S\fastapi`
**Status:** ok

## Repository Summary

- Modules: **73** · Edges: **159** · Subsystems: 7 · Files: 2753
- Massive mode: False · graph detail: full · scan time: 2.9s

## Final Score

| Understanding | Impact | Investigation | Build Plan | **Overall** |
|---:|---:|---:|---:|---:|
| 93.0 | 23.2 | 100.0 | 100.0 | **75.2** |

## Repository Understanding Results

Score **93.0** / 100. Components: graph_built 20.0, explanation 15.0, subsystems 8.0, entry_points 10.0, runtime_boundaries 15.0, top_risks 10.0, hubs_vs_risks_separated 15.0

## Impact Results

Score **23.2** / 100 · resolution rate 0.25 · fallback rate 0.75 (2/8 concepts resolved).

- `what breaks if I remove authentication` → label=None modules=[] direct=0 indirect=0
- `what breaks if I remove caching` → label=None modules=[] direct=0 indirect=0
- `what breaks if I remove configuration` → label=None modules=[] direct=0 indirect=0
- `what breaks if I remove the logging layer` → label=None modules=[] direct=0 indirect=0

## Investigation Results

Score **100.0** / 100 · grounded 1.0 · clean (no dotfiles) 1.0 · avg modules/symptom 5.8.

- `duplicate events are being fired` → ['scripts/sponsors.py', 'fastapi/middleware/asyncexitstack.py', 'scripts/playwright/separate_openapi_schemas/image02.py']
- `websocket connections keep disconnecting` → ['fastapi/applications.py', 'fastapi/__init__.py', 'fastapi/routing.py']
- `authentication fails intermittently` → ['fastapi/security/oauth2.py', 'fastapi/applications.py', 'fastapi/_compat/__init__.py']

## Build Plan Results

Score **100.0** / 100 · plans with affected modules 4/4.

- `add distributed tracing` → ['fastapi/middleware/asyncexitstack.py', 'fastapi/applications.py', 'fastapi/middleware/httpsredirect.py']
- `add rate limiting` → ['fastapi/_compat/v2.py', 'scripts/playwright/separate_openapi_schemas/image02.py', 'scripts/playwright/separate_openapi_schemas/image03.py']

## Failure Analysis

| Scenario | Expected | Actual | Root cause | Subsystem | Category |
|---|---|---|---|---|---|
| what breaks if I remove authentication | concept resolves to modules | fallback / no target | concept absent from repo or not in resolver map | target_resolver / impact_engine | semantic_routing_failure |
| what breaks if I remove caching | concept resolves to modules | fallback / no target | concept absent from repo or not in resolver map | target_resolver / impact_engine | semantic_routing_failure |
| what breaks if I remove configuration | concept resolves to modules | fallback / no target | concept absent from repo or not in resolver map | target_resolver / impact_engine | semantic_routing_failure |
| what breaks if I remove the logging layer | concept resolves to modules | fallback / no target | concept absent from repo or not in resolver map | target_resolver / impact_engine | semantic_routing_failure |
| what breaks if I remove dependency injection | concept resolves to modules | fallback / no target | concept absent from repo or not in resolver map | target_resolver / impact_engine | semantic_routing_failure |
| what breaks if I remove request validation | concept resolves to modules | fallback / no target | concept absent from repo or not in resolver map | target_resolver / impact_engine | semantic_routing_failure |

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

### 5. Concept "dependency injection" not resolved (fallback)

- **Failure:** Concept "dependency injection" not resolved (fallback)
- **Frequency:** 1 repository (this repo: 1 scenario)
- **Root Cause:** concept absent from repo or not in resolver map
- **Suggested Future Phase:** Phase 137 — Semantic Generalization (universal concept inference beyond the HA-tuned map)
