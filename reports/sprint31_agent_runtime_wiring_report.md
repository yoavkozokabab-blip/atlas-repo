# Sprint 3.1 — Agent Runtime Wiring Report

**Date:** 2026-05-28  
**Fix:** B01 — Agent routing was metadata-only  
**Status:** Complete

---

## Problem

`agents/intent_routing.py` resolved owning agents, and `agents/registry.py` ran startup health checks, but `ActionRegistry.execute()` called handlers directly with no agent resolution, health gating, or per-command metadata. Browser, desktop, trading, and coding commands behaved the same as before Sprint 3 routing tables existed.

---

## Solution

Added `agents/runtime_wiring.py` and wired it into `actions/registry.py` `execute()`:

1. **Resolve** — `agent_for_intent(request.intent)` → `agent_id`
2. **Health** — `AgentRegistry.health_check()` plus `depends_on` chain → `agent_health`
3. **Gate** — For `BROWSER`, `DESKTOP`, `TRADING`, `CODING`: block unsafe intents when unhealthy (diagnostic `*_health`, `*_debug`, `*_status` intents still run)
4. **Execute** — Existing `BaseAction` handler unchanged
5. **Record** — Every `CommandResult.data` includes:
   - `agent_id`
   - `agent_health`
   - `routing_source` (`intent_routing.agent_for_intent`)

Unhealthy unsafe commands return `ActionStatus.FAILED` with `blocked_by_agent_health: true` in `data`; handlers are not invoked.

---

## Files changed

| File | Change |
|------|--------|
| `agents/runtime_wiring.py` | New — resolution, health evaluation, gating, metadata attach |
| `actions/registry.py` | `execute()` wraps handlers with runtime wiring |
| `agents/intent_routing.py` | Docstring — routing used at execute time |
| `agents/registry.py` | Docstring — documents wiring hook |
| `tests/test_sprint3_agents.py` | Execution-path tests for browser/desktop/trading/coding + unhealthy block |

---

## Routing verification (execution path)

| Command / intent | Owning agent | Recorded on result |
|------------------|--------------|-------------------|
| `open_browser` | `browser` | Yes |
| `summarize_this_screen` | `desktop` | Yes |
| `run_live_daily_loop` | `trading` | Yes |
| `find_function` | `coding` | Yes |

---

## What did not change

- No handler rewrites; all `BaseAction` implementations unchanged
- `brain/router.py` still calls `registry.execute()` — single hook point
- No new commands, UI, or capabilities
- `ExecutiveAgent.delegate()` automatically picks up metadata via registry

---

## Tests

```text
py -3 -m pytest tests/test_sprint3_agents.py tests/test_intent_registry_consistency.py -q
# 29 passed in ~3s (2026-05-28)
```

New cases in `test_sprint3_agents.py`:

- `test_open_browser_records_browser_agent`
- `test_summarize_this_screen_records_desktop_agent`
- `test_trading_command_records_trading_agent`
- `test_coding_command_records_coding_agent`
- `test_unhealthy_browser_blocks_open_browser`
- `test_unhealthy_browser_allows_show_browser_health`

---

## Acceptance

- [x] B01 fixed — agents affect execution (health gate + metadata), not metadata-only tables
- [x] Every command via `ActionRegistry.execute` records `agent_id`, `agent_health`, `routing_source`
- [x] Existing handlers not bypassed
- [x] Unhealthy owner blocks unsafe actions; diagnostics allowed
