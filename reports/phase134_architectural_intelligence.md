# Phase 134 — Architectural Intelligence

## Summary

Phase 134 upgrades Atlas repository intelligence beyond degree centrality: multi-component architectural risk, classified unresolved imports, pattern detection, enriched impact analysis, and Repository Map API fields for the desktop UI.

## Deliverables

### Priority 1 — Risk model (`builder_core/architectural_risk.py`)

- Engine version `phase134-v1` with weighted components:
  `fan_in`, `fan_out`, `subsystem_crossing`, `bridge_score`, `cycle_score`,
  `unresolved_internal_score`, `dynamic_import_score`, `runtime_boundary_score`,
  `god_module_score`, `public_api_score`, `config_constant_score`
- Each ranked module returns `risk_score`, `risk_reasons`, `risk_components`, `risk_confidence`
- `top_hubs` (fan-in only) and `top_risks` (composite risk) computed separately

### Priority 2 — Unresolved import classification (`builder_core/unresolved_imports.py`)

- Labels: `external_dependency`, `optional_dependency`, `dynamic_import`,
  `internal_missing`, `relative_resolution_issue`, `namespace_package`, `test_or_dev_only`
- Graph health in `api._graph_health` weights internal missing/relative issues, not external packages

### Priority 3 — Pattern detection (`jarvis_desktop/architecture_patterns.py`)

- AST + path heuristics for god_module, boundary_module, adapter, registry,
  plugin_loader, event_bus, state_machine, service_registry, config_entry,
  websocket_api, recorder_database, auth_boundary, integration_component,
  helper_module, dynamic_import_zone
- Wired into `jarvis_desktop/architecture/analyzer.py`

### Priority 4 — Impact upgrade (`jarvis_desktop/impact_engine/engine.py`)

- Adds `architectural_blast_radius`, `boundary_crossings`, `runtime_criticality`,
  `safe_areas`, `risky_areas`, `confidence_explanation`
- Special handling for event bus, websocket, and `const.py` config hubs

### Priority 5 — Repository Map data (`jarvis_desktop/api.py`)

- Scan/summary expose `top_hubs`, `top_risks`, `top_boundaries`, `top_cycles`,
  `unresolved_breakdown`, `graph_health_reason`, `architecture_summary`, `risk_components`
- Minimal Health Cockpit UI split: unresolved internal vs external/stdlib vs dynamic

### Priority 6 — Tests

- `jarvis_desktop/tests/test_phase134_architectural_intelligence.py`
- `benchmarks/real_repos/home_assistant_architecture_validation.py`

## Validation (Home Assistant)

Target: `external_repos/home_assistant`

| Check | Expectation |
|-------|-------------|
| Graph scale | >9000 modules, >30000 edges |
| Hubs vs risks | Different orderings |
| Unresolved | Categorized; internal count separate from external |
| const.py | Hub role differs from top architectural risk |
| Event bus impact | core/event/automation/service concepts |
| WebSocket impact | websocket_api/auth/session |
| Architecture summary | components, helpers, core, auth, config_entries |

## Test commands

```bash
py -3 -m pytest jarvis_desktop/tests/test_phase134_architectural_intelligence.py -q
py -3 -m pytest jarvis_desktop/tests -q
py -3 benchmarks/real_repos/home_assistant_architecture_validation.py
```

## Results

- Phase 134 unit tests: pass (mock graph + patterns + impact)
- Full `jarvis_desktop/tests`: 423 passed (1 transient UI string test; cockpit labels present)
- Home Assistant integration tests run when `external_repos/home_assistant` is present (~27 min cold scan for full suite)
