# Generalization Report — Atlas (local_jarvis)

**Language:** python · **Framework:** desktop tool · **Category:** python
**Path:** `C:\J.A.R.V.I.S\local_jarvis`
**Status:** ok

## Repository Summary

- Modules: **10680** · Edges: **14940** · Subsystems: 51 · Files: 33237
- Massive mode: True · graph detail: imports · scan time: 724.6s

## Final Score

| Understanding | Impact | Investigation | Build Plan | **Overall** |
|---:|---:|---:|---:|---:|
| 100.0 | 48.2 | 100.0 | 100.0 | **84.5** |

## Repository Understanding Results

Score **100.0** / 100. Components: graph_built 20.0, explanation 15.0, subsystems 15.0, entry_points 10.0, runtime_boundaries 15.0, top_risks 10.0, hubs_vs_risks_separated 15.0

## Impact Results

Score **48.2** / 100 · resolution rate 0.5 · fallback rate 0.5 (4/8 concepts resolved).

- `what breaks if I remove authentication` → label='authentication' modules=['external_repos/home_assistant/homeassistant/auth/auth_store.py', 'external_repos/home_assistant/homeassistant/auth/providers/__init__.py'] direct=15 indirect=8
- `what breaks if I remove caching` → label='architecture symbol `caching`' modules=['external_repos/home_assistant/homeassistant/components/anthropic/config_flow.py', 'external_repos/home_assistant/homeassistant/components/anthropic/const.py'] direct=0 indirect=0
- `what breaks if I remove configuration` → label='' modules=[] direct=206 indirect=197
- `what breaks if I remove the logging layer` → label=None modules=[] direct=0 indirect=0

## Investigation Results

Score **100.0** / 100 · grounded 1.0 · clean (no dotfiles) 1.0 · avg modules/symptom 8.0.

- `duplicate events are being fired` → ['actions/registry.py', 'agents/registry.py', 'apps/app_registry.py']
- `websocket connections keep disconnecting` → ['actions/app_actions.py', 'autonomy/provider.py', 'agents/browser_agent.py']
- `authentication fails intermittently` → ['actions/registry.py', 'actions/session_memory_actions.py', 'external_repos/home_assistant/homeassistant/auth/auth_store.py']

## Build Plan Results

Score **100.0** / 100 · plans with affected modules 4/4.

- `add distributed tracing` → ['actions/phase45_actions.py', 'external_repos/home_assistant/homeassistant/bootstrap.py']
- `add rate limiting` → ['actions/registry.py', 'external_repos/home_assistant/homeassistant/components/amazon_polly/tts.py', 'actions/operating_layer_actions.py']

## Failure Analysis

| Scenario | Expected | Actual | Root cause | Subsystem | Category |
|---|---|---|---|---|---|
| what breaks if I remove the logging layer | concept resolves to modules | fallback / no target | concept absent from repo or not in resolver map | target_resolver / impact_engine | semantic_routing_failure |
| what breaks if I remove the impact engine | concept resolves to modules | fallback / no target | concept absent from repo or not in resolver map | target_resolver / impact_engine | semantic_routing_failure |
| what breaks if I remove the planning engine | concept resolves to modules | fallback / no target | concept absent from repo or not in resolver map | target_resolver / impact_engine | semantic_routing_failure |
| what breaks if I remove the architecture analyzer | concept resolves to modules | fallback / no target | concept absent from repo or not in resolver map | target_resolver / impact_engine | semantic_routing_failure |

## Top 5 Failures

### 1. Concept "the logging layer" not resolved (fallback)

- **Failure:** Concept "the logging layer" not resolved (fallback)
- **Frequency:** 6 repositories (this repo: 1 scenario)
- **Root Cause:** concept absent from repo or not in resolver map
- **Suggested Future Phase:** Phase 137 — Semantic Generalization (universal concept inference beyond the HA-tuned map)

### 2. Concept "the impact engine" not resolved (fallback)

- **Failure:** Concept "the impact engine" not resolved (fallback)
- **Frequency:** 1 repository (this repo: 1 scenario)
- **Root Cause:** concept absent from repo or not in resolver map
- **Suggested Future Phase:** Phase 137 — Semantic Generalization (universal concept inference beyond the HA-tuned map)

### 3. Concept "the planning engine" not resolved (fallback)

- **Failure:** Concept "the planning engine" not resolved (fallback)
- **Frequency:** 1 repository (this repo: 1 scenario)
- **Root Cause:** concept absent from repo or not in resolver map
- **Suggested Future Phase:** Phase 137 — Semantic Generalization (universal concept inference beyond the HA-tuned map)

### 4. Concept "the architecture analyzer" not resolved (fallback)

- **Failure:** Concept "the architecture analyzer" not resolved (fallback)
- **Frequency:** 1 repository (this repo: 1 scenario)
- **Root Cause:** concept absent from repo or not in resolver map
- **Suggested Future Phase:** Phase 137 — Semantic Generalization (universal concept inference beyond the HA-tuned map)
