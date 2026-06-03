# Generalization Report — Home Assistant

**Language:** python · **Framework:** asyncio platform · **Category:** python
**Path:** `C:\J.A.R.V.I.S\local_jarvis\external_repos\home_assistant`
**Status:** ok

## Repository Summary

- Modules: **9709** · Edges: **36013** · Subsystems: 1512 · Files: 25893
- Massive mode: True · graph detail: imports · scan time: 471.3s

## Final Score

| Understanding | Impact | Investigation | Build Plan | **Overall** |
|---:|---:|---:|---:|---:|
| 100.0 | 87.3 | 100.0 | 100.0 | **96.2** |

## Repository Understanding Results

Score **100.0** / 100. Components: graph_built 20.0, explanation 15.0, subsystems 15.0, entry_points 10.0, runtime_boundaries 15.0, top_risks 10.0, hubs_vs_risks_separated 15.0

## Impact Results

Score **87.3** / 100 · resolution rate 0.889 · fallback rate 0.111 (8/9 concepts resolved).

- `what breaks if I remove authentication` → label='authentication' modules=['homeassistant/auth/auth_store.py', 'homeassistant/auth/__init__.py'] direct=39 indirect=3276
- `what breaks if I remove caching` → label='architecture symbol `caching`' modules=['homeassistant/components/anthropic/config_flow.py', 'homeassistant/components/anthropic/const.py'] direct=0 indirect=0
- `what breaks if I remove configuration` → label='architecture symbol `configuration`' modules=['homeassistant/backup_restore.py', 'homeassistant/components/airgradient/button.py'] direct=2 indirect=31
- `what breaks if I remove the logging layer` → label=None modules=[] direct=0 indirect=0

## Investigation Results

Score **100.0** / 100 · grounded 1.0 · clean (no dotfiles) 1.0 · avg modules/symptom 7.8.

- `duplicate events are being fired` → ['homeassistant/bootstrap.py', 'homeassistant/components/airthings_ble/sensor.py', 'homeassistant/components/alexa/smart_home.py']
- `websocket connections keep disconnecting` → ['homeassistant/auth/jwt_wrapper.py', 'homeassistant/components/assist_pipeline/websocket_api.py', 'homeassistant/components/bang_olufsen/websocket.py']
- `authentication fails intermittently` → ['homeassistant/components/auth/login_flow.py', 'homeassistant/auth/__init__.py', 'homeassistant/components/auth/__init__.py']

## Build Plan Results

Score **100.0** / 100 · plans with affected modules 4/4.

- `add distributed tracing` → ['homeassistant/components/assist_pipeline/websocket_api.py', 'homeassistant/components/automation/__init__.py', 'homeassistant/bootstrap.py']
- `add rate limiting` → ['homeassistant/components/assist_pipeline/websocket_api.py', 'homeassistant/components/amazon_polly/tts.py', 'homeassistant/components/assist_pipeline/__init__.py']

## Failure Analysis

| Scenario | Expected | Actual | Root cause | Subsystem | Category |
|---|---|---|---|---|---|
| what breaks if I remove the logging layer | concept resolves to modules | fallback / no target | concept absent from repo or not in resolver map | target_resolver / impact_engine | semantic_routing_failure |

## Top 5 Failures

### 1. Concept "the logging layer" not resolved (fallback)

- **Failure:** Concept "the logging layer" not resolved (fallback)
- **Frequency:** 6 repositories (this repo: 1 scenario)
- **Root Cause:** concept absent from repo or not in resolver map
- **Suggested Future Phase:** Phase 137 — Semantic Generalization (universal concept inference beyond the HA-tuned map)
