# Files Changed — Sprint 3

## Modified

### `agents/intent_routing.py`
- Changed: `open_browser`, `open_website`, `search_web`, `find_information`, `summarize_this_page`, `summarize_current`, `what_tab`, `browser` → `AgentId.BROWSER` (was `AgentId.OPERATOR`)
- Changed: `open_app`, `focus_window`, `what_is_on_my_screen`, `summarize_this_screen`, `click_button`, `type_this`, `list_open_windows`, `switch_to_chrome`, `show_desktop`, `desktop`, `mouse_`, `discover_apps`, `list_apps`, `approve_app`, `forget_app`, `describe_screen`, `read_screen`, `take_screenshot`, `find_on_screen` → `AgentId.DESKTOP` (was `AgentId.OPERATOR`)
- Added: explicit trading intent rows (`run_live`, `open_trading_dashboard`, `enable_kill_switch`, `disable_kill_switch`, `show_open_positions`, `show_last_errors`, `show_rejection_reasons`, `search_trading`, `trading_`) → `AgentId.TRADING`
- Removed: catch-all `if "trading" in value → AgentId.RESEARCH` block

### `core/startup_validation.py`
- Added: `validate_win32_dependencies()` function — checks `win32gui`, `tesseract`, `playwright`
- Modified: `run_startup_validation()` — calls `validate_win32_dependencies()`, returns `"dependencies_missing"` key

### `core/runtime_bootstrap.py`
- Added: call to `build_default_registry()` + `validate_registry()` at first bootstrap (S3.1)
- Added: call to `get_health_monitor_agent().start()` at first bootstrap (S3.5)

## Created

### `tests/test_sprint3_agents.py`
17 new tests covering S3.1–S3.6.

## Already Existed (Verified Complete, No Changes Needed)
- `agents/registry.py` — AgentRegistry, AgentRegistration, build_default_registry, validate_registry
- `agents/browser_agent.py` — BrowserAgent with health_check
- `agents/desktop_agent.py` — DesktopAgent with health_check
- `agents/trading_agent.py` — TradingAgent with health_check
- `agents/health_monitor_agent.py` — HealthMonitorAgent, run_storage_health_checks, 30s heartbeat
- `agents/base.py` — AgentId enum including BROWSER, DESKTOP, TRADING, HEALTH_MONITOR
