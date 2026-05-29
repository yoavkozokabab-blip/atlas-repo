# Sprint 3 Report — Agent Architecture
**Date:** 2026-05-29  
**Sprint:** 3 (Weeks 5–6, per roadmap_to_90_percent.md)

---

## Items Delivered

### S3.1 — Formalise 12-agent registry ✅
**File:** `agents/registry.py`  
Registry existed but was not called at startup. Fixed: `core/runtime_bootstrap.py` now calls `build_default_registry()` and `validate_registry()` at first bootstrap. All 11 current agents registered with `health_check`, `intent_prefixes`, `depends_on`.

### S3.2 — Extract Browser Agent from Operator Agent ✅
**Files:** `agents/browser_agent.py` (already existed), `agents/intent_routing.py` (fixed)  
`browser_agent.py` was complete. The gap was `intent_routing.py` still routing `open_browser`, `search_web`, `what_tab`, etc. to `AgentId.OPERATOR`. Fixed: all browser intents now route to `AgentId.BROWSER`.

### S3.3 — Extract Desktop Agent from Operator Agent ✅
**Files:** `agents/desktop_agent.py` (already existed), `agents/intent_routing.py` (fixed)  
Same pattern. Desktop intents (`open_app`, `take_screenshot`, `focus_window`, etc.) now route to `AgentId.DESKTOP` instead of `AgentId.OPERATOR`.

### S3.4 — Formalise Trading Agent ✅
**Files:** `agents/trading_agent.py` (already existed), `agents/intent_routing.py` (fixed)  
Trading intents were falling through the old catch-all `if "trading" in value → RESEARCH`. Fixed: explicit routing rows added for all trading prefixes (`run_live`, `open_trading_dashboard`, `enable_kill_switch`, etc.), catch-all removed.

### S3.5 — Formalise Health Monitor Agent ✅
**File:** `agents/health_monitor_agent.py` (already existed), `core/runtime_bootstrap.py` (fixed)  
`HealthMonitorAgent` was complete with 30s heartbeat thread registered in ThreadRegistry. The gap was that `start()` was never called. Fixed: `runtime_bootstrap.py` calls `get_health_monitor_agent().start()` at first bootstrap.

### S3.6 — Win32 startup validation ✅
**File:** `core/startup_validation.py` (extended)  
Added `validate_win32_dependencies()` that checks:
- `win32gui` importable → desktop window control
- `tesseract` in PATH → OCR pipeline
- `playwright.sync_api` importable → real browser provider

Reports each as `available=True/False`. Integrated into `run_startup_validation()` under key `"dependencies_missing"`. Informational only; never fatal.

---

## Tests Added
**File:** `tests/test_sprint3_agents.py` — 17 tests, all pass.

| Test | Covers |
|------|--------|
| `test_agent_registry_register_and_get` | S3.1 register/lookup |
| `test_agent_registry_validate_healthy` | S3.1 healthy case |
| `test_agent_registry_validate_unhealthy` | S3.1 unhealthy case |
| `test_agent_registry_health_check_exception_is_unhealthy` | S3.1 exception safety |
| `test_agent_registry_snapshot` | S3.1 snapshot |
| `test_browser_intents_route_to_browser` | S3.2 routing |
| `test_desktop_intents_route_to_desktop` | S3.3 routing |
| `test_operator_no_longer_owns_browser_desktop` | S3.2/S3.3 regression guard |
| `test_trading_intents_route_to_trading` | S3.4 routing |
| `test_trading_no_longer_falls_through_to_research` | S3.4 regression guard |
| `test_health_monitor_agent_starts_and_stops` | S3.5 thread lifecycle |
| `test_health_monitor_agent_start_idempotent` | S3.5 idempotency |
| `test_health_monitor_storage_checks_return_items` | S3.5 storage checks |
| `test_validate_win32_dependencies_returns_dict` | S3.6 return type |
| `test_validate_win32_dependencies_missing_modules` | S3.6 never raises |
| `test_run_startup_validation_includes_dependencies_key` | S3.6 integration |
| `test_validate_registry_function_returns_list` | S3.1 module-level fn |

---

## What Was NOT Done (Scope boundary)
- Sprint 4 items (memory consolidation, TTS consolidation, file renames)
- New features, new commands, new agents
- UI changes
- Speculative improvements
