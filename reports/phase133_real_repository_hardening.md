# Phase 133 — Real Repository Hardening (Home Assistant)

Generated: 2026-06-03

## Problem

Scanning `external_repos/home_assistant` indexed ~25k files, but the Repository Map showed **1 module and 0 edges**. Root causes:

1. **Graph cap ordering** — FULL-detail builds aborted when `len(files) > 5000`, returning a degraded single-repository node. Import-only graphs must run *before* that cap (fixed in `depgraph.build_graph_from_files`).
2. **Subsystem mega-collapse** — `architecture_clusters=True` on subsystem view merged ~9.7k modules into ~5 nodes (`Homeassistant`, `Script`, …). Subsystem view now keeps granular subsystems for large repos.
3. **Shallow subsystem keys** — Top-level-only grouping (`homeassistant`) prevented useful hierarchy. Subsystems now use `homeassistant/components/<domain>` and `homeassistant/<area>`.

## Fixes delivered

### 1. Repository map / graph

| Area | Change |
|------|--------|
| Import graph | `DETAIL_IMPORTS` builds before `_MAX_FILES` cap; HA yields **9708 modules**, **36013** resolved import edges |
| Subsystem discovery | `repository_understanding._subsystem_name()` — deeper paths for HA and generic `src/lib` layouts |
| Subsystem graph UI | `current_graph(subsystem)` disables architecture mega-clusters for subsystem mode |
| Cluster matching | `_architecture_pattern_matches()` — segment/path-boundary matching; HA-specific cluster labels (Event Bus, WebSocket, Auth, Components, …) |
| Path → subsystem | `_subsystem_for_path()` — HA component-level fallback |

### 2. Semantic impact resolution

New module: `jarvis_desktop/impact_engine/target_resolver.py`

- **Concept target mapper** — phrases → ranked module paths (websocket, event bus, auth, automation, recorder, config entries, …)
- **Architecture symbol resolver** — `EventBus`, `async_fire`, `ConfigEntry`, etc. via evidence store + path scan
- **`analyze_impact`** — uses semantic/symbol resolution when path lookup fails; adds resolved candidates to affected set

### 3. Runtime symptom routing

Existing + extended in `planning_engine.py`:

- Config/dotfile paths **excluded** from runtime investigation scoring (`_is_config_path`, `runtime=True`)
- Symptom-specific path boosts (`_RUNTIME_BOOSTS`) for duplicate events, websocket, auth, recorder, automation
- Build boosts (`_BUILD_BOOSTS`) wired into `plan_change` for distributed tracing and rate limiting

`evidence_engine/architecture_patterns.py` — shared penalties and build-localization boosts.

### 4. Architecture pattern detection

Generalizable patterns (not hardcoded single files): `EventBus`, `async_fire`, `async_listen`, `websocket_api`, `ConfigEntry`, `async_setup_entry`, `dispatcher_send`, `ServiceRegistry`, `StateMachine`, etc.

### 5. Build plan localization

- `plan_change` applies `_build_boosts_for_text(goal)` for tracing / rate-limit / websocket / auth requests
- `precision_engine._concept_path_boost` uses `build_plan_path_boost()` for boundary-aware file ranking

## Validation

```bash
py -3 -m pytest jarvis_desktop/tests/test_phase133_home_assistant_real_repo.py -q
```

| Test | Result |
|------|--------|
| Graph modules > 500 | Pass (~9708) |
| Graph edges > 500 | Pass (~36013) |
| Subsystem view not collapsed | Pass (many granular subsystem nodes) |
| Websocket impact | Pass |
| Event bus impact | Pass |
| Duplicate events — no config in top hypotheses | Pass |
| Distributed tracing build plan | Pass |
| Rate limiting build plan | Pass |

Repository path: `C:\J.A.R.V.I.S\local_jarvis\external_repos\home_assistant` (skipped with clear message if missing).

## Constraints honored

- Local-only — no web or LLM calls
- No new concept catalog entries
- No UI redesign

## Files touched

- `builder_core/repository_understanding.py`
- `builder_core/bug_intelligence/depgraph.py` (import-before-cap documented)
- `jarvis_desktop/api.py`
- `jarvis_desktop/impact_engine/target_resolver.py` (new)
- `jarvis_desktop/impact_engine/engine.py`
- `jarvis_desktop/evidence_engine/architecture_patterns.py` (new)
- `jarvis_desktop/evidence_engine/precision_engine.py`
- `jarvis_desktop/planning_engine.py`
- `jarvis_desktop/tests/test_phase133_home_assistant_real_repo.py` (new)
