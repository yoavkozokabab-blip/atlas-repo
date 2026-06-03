# Generalization Report — Django

**Language:** python · **Framework:** web framework · **Category:** python
**Path:** `C:\J.A.R.V.I.S\django`
**Status:** ok

## Repository Summary

- Modules: **929** · Edges: **2916** · Subsystems: 9 · Files: 6868
- Massive mode: False · graph detail: imports · scan time: 19.4s

## Final Score

| Understanding | Impact | Investigation | Build Plan | **Overall** |
|---:|---:|---:|---:|---:|
| 100.0 | 65.1 | 100.0 | 100.0 | **89.5** |

## Repository Understanding Results

Score **100.0** / 100. Components: graph_built 20.0, explanation 15.0, subsystems 15.0, entry_points 10.0, runtime_boundaries 15.0, top_risks 10.0, hubs_vs_risks_separated 15.0

## Impact Results

Score **65.1** / 100 · resolution rate 0.667 · fallback rate 0.333 (6/9 concepts resolved).

- `what breaks if I remove authentication` → label='authentication' modules=['django/contrib/auth/__init__.py', 'django/contrib/auth/migrations/0011_update_proxy_permissions.py'] direct=27 indirect=41
- `what breaks if I remove caching` → label=None modules=[] direct=0 indirect=0
- `what breaks if I remove configuration` → label=None modules=[] direct=0 indirect=0
- `what breaks if I remove the logging layer` → label=None modules=[] direct=0 indirect=0

## Investigation Results

Score **100.0** / 100 · grounded 1.0 · clean (no dotfiles) 1.0 · avg modules/symptom 8.0.

- `duplicate events are being fired` → ['django/core/checks/registry.py', 'django/db/models/signals.py', 'django/apps/registry.py']
- `websocket connections keep disconnecting` → ['django/conf/urls/i18n.py', 'django/contrib/auth/views.py', 'django/core/handlers/wsgi.py']
- `authentication fails intermittently` → ['django/contrib/auth/middleware.py', 'django/contrib/auth/__init__.py', 'django/core/checks/security/sessions.py']

## Build Plan Results

Score **100.0** / 100 · plans with affected modules 4/4.

- `add distributed tracing` → ['django/middleware/http.py', 'django/middleware/csrf.py', 'django/contrib/auth/middleware.py']
- `add rate limiting` → ['django/contrib/auth/middleware.py', 'django/core/management/commands/migrate.py', 'django/middleware/csrf.py']

## Failure Analysis

| Scenario | Expected | Actual | Root cause | Subsystem | Category |
|---|---|---|---|---|---|
| what breaks if I remove caching | concept resolves to modules | fallback / no target | concept absent from repo or not in resolver map | target_resolver / impact_engine | semantic_routing_failure |
| what breaks if I remove configuration | concept resolves to modules | fallback / no target | concept absent from repo or not in resolver map | target_resolver / impact_engine | semantic_routing_failure |
| what breaks if I remove the logging layer | concept resolves to modules | fallback / no target | concept absent from repo or not in resolver map | target_resolver / impact_engine | semantic_routing_failure |

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
