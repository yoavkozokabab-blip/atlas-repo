"""Sprint 3 tests — agent registry, routing, startup validation (S3.1–S3.6)."""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# S3.1 — AgentRegistry
# ---------------------------------------------------------------------------

def test_agent_registry_register_and_get():
    from agents.registry import AgentRegistry
    from agents.base import AgentId

    reg = AgentRegistry()
    from agents.registry import AgentRegistration

    rec = AgentRegistration(
        agent_id=AgentId.CONVERSATION,
        agent=object(),
        health_check=lambda: True,
        intent_prefixes=("show_voice",),
        depends_on=(),
    )
    reg.register(rec)
    assert reg.get(AgentId.CONVERSATION) is rec


def test_agent_registry_validate_healthy():
    from agents.registry import AgentRegistry, AgentRegistration
    from agents.base import AgentId

    reg = AgentRegistry()
    reg.register(AgentRegistration(
        agent_id=AgentId.CONVERSATION,
        agent=object(),
        health_check=lambda: True,
    ))
    errors = reg.validate()
    assert errors == []


def test_agent_registry_validate_unhealthy():
    from agents.registry import AgentRegistry, AgentRegistration
    from agents.base import AgentId

    reg = AgentRegistry()
    reg.register(AgentRegistration(
        agent_id=AgentId.CONVERSATION,
        agent=object(),
        health_check=lambda: False,
    ))
    errors = reg.validate()
    assert len(errors) == 1
    assert "conversation" in errors[0]


def test_agent_registry_health_check_exception_is_unhealthy():
    from agents.registry import AgentRegistry, AgentRegistration
    from agents.base import AgentId

    def bad_check():
        raise RuntimeError("boom")

    reg = AgentRegistry()
    reg.register(AgentRegistration(
        agent_id=AgentId.MEMORY,
        agent=object(),
        health_check=bad_check,
    ))
    errors = reg.validate()
    assert len(errors) == 1


def test_agent_registry_snapshot():
    from agents.registry import AgentRegistry, AgentRegistration
    from agents.base import AgentId

    reg = AgentRegistry()
    reg.register(AgentRegistration(
        agent_id=AgentId.EXECUTIVE,
        agent=object(),
        health_check=lambda: True,
    ))
    snap = reg.snapshot()
    assert snap["executive"] is True


# ---------------------------------------------------------------------------
# S3.2 / S3.3 — intent routing: BROWSER and DESKTOP
# ---------------------------------------------------------------------------

def test_browser_intents_route_to_browser():
    from agents.intent_routing import agent_for_intent
    from agents.base import AgentId

    for intent in ("open_browser", "open_website", "search_web",
                   "find_information", "summarize_this_page",
                   "summarize_current", "what_tab"):
        result = agent_for_intent(intent)
        assert result == AgentId.BROWSER, (
            f"Expected BROWSER for '{intent}', got {result}"
        )


def test_open_browser_enum_routes_to_browser_agent():
    from agents.intent_routing import agent_for_intent
    from agents.base import AgentId
    from core.types import Intent

    assert agent_for_intent(Intent.OPEN_BROWSER) == AgentId.BROWSER


def test_desktop_intents_route_to_desktop():
    from agents.intent_routing import agent_for_intent
    from agents.base import AgentId

    for intent in ("open_app", "focus_window", "describe_screen",
                   "take_screenshot", "what_is_on_my_screen",
                   "click_button", "type_this"):
        result = agent_for_intent(intent)
        assert result == AgentId.DESKTOP, (
            f"Expected DESKTOP for '{intent}', got {result}"
        )


def test_operator_no_longer_owns_browser_desktop():
    """Operator should not be the resolved agent for any browser or desktop intent."""
    from agents.intent_routing import agent_for_intent
    from agents.base import AgentId

    browser_desktop_intents = (
        "open_browser", "search_web", "open_app", "take_screenshot",
        "describe_screen", "focus_window",
    )
    for intent in browser_desktop_intents:
        result = agent_for_intent(intent)
        assert result != AgentId.OPERATOR, (
            f"OPERATOR should no longer own '{intent}' — got {result}"
        )


# ---------------------------------------------------------------------------
# S3.4 — intent routing: TRADING
# ---------------------------------------------------------------------------

def test_trading_intents_route_to_trading():
    from agents.intent_routing import agent_for_intent
    from agents.base import AgentId

    for intent in ("run_live", "open_trading_dashboard", "show_dashboard_health",
                   "enable_kill_switch", "disable_kill_switch",
                   "show_open_positions", "search_trading"):
        result = agent_for_intent(intent)
        assert result == AgentId.TRADING, (
            f"Expected TRADING for '{intent}', got {result}"
        )


def test_trading_no_longer_falls_through_to_research():
    from agents.intent_routing import agent_for_intent
    from agents.base import AgentId

    for intent in ("run_live_prod", "search_trading_log"):
        result = agent_for_intent(intent)
        assert result != AgentId.RESEARCH, (
            f"Trading intent '{intent}' should not fall through to RESEARCH"
        )


# ---------------------------------------------------------------------------
# S3.5 — HealthMonitorAgent
# ---------------------------------------------------------------------------

def test_health_monitor_agent_starts_and_stops():
    from agents.health_monitor_agent import HealthMonitorAgent

    agent = HealthMonitorAgent()
    agent.start()
    assert agent._heartbeat_thread is not None
    assert agent._heartbeat_thread.is_alive()
    agent.stop()
    assert not (agent._heartbeat_thread and agent._heartbeat_thread.is_alive())


def test_health_monitor_agent_start_idempotent():
    from agents.health_monitor_agent import HealthMonitorAgent

    agent = HealthMonitorAgent()
    agent.start()
    thread_before = agent._heartbeat_thread
    agent.start()  # second call should not replace thread
    assert agent._heartbeat_thread is thread_before
    agent.stop()


def test_health_monitor_storage_checks_return_items(tmp_path):
    from agents.health_monitor_agent import run_storage_health_checks

    with patch("config.DATA_DIR", tmp_path):
        items = run_storage_health_checks()
    assert isinstance(items, list)
    assert len(items) >= 1


# ---------------------------------------------------------------------------
# S3.6 — Win32 / dependency startup validation
# ---------------------------------------------------------------------------

def test_validate_win32_dependencies_returns_dict():
    from core.startup_validation import validate_win32_dependencies

    result = validate_win32_dependencies()
    assert isinstance(result, dict)
    assert "win32gui" in result
    assert "tesseract" in result
    assert "playwright" in result
    for k, v in result.items():
        assert isinstance(v, bool), f"Expected bool for {k}, got {type(v)}"


def test_validate_win32_dependencies_missing_modules():
    """When modules are absent, validate_win32_dependencies returns False, not an exception."""
    import importlib

    original_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __import__

    def mock_import(name, *args, **kwargs):
        if name in ("win32gui", "playwright.sync_api"):
            raise ImportError(f"No module named '{name}'")
        return original_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=mock_import):
        from core.startup_validation import validate_win32_dependencies
        # Should not raise even when imports fail
        try:
            result = validate_win32_dependencies()
            assert isinstance(result, dict)
        except Exception as exc:
            pytest.fail(f"validate_win32_dependencies raised unexpectedly: {exc}")


def test_run_startup_validation_includes_dependencies_key():
    from core.startup_validation import run_startup_validation

    result = run_startup_validation()
    assert "dependencies_missing" in result
    assert isinstance(result["dependencies_missing"], list)
    assert "issues" in result
    assert isinstance(result["issues"], list)


# ---------------------------------------------------------------------------
# S3.1 — validate_registry() at module level
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# S3.1 — Agent runtime wiring (execution path)
# ---------------------------------------------------------------------------

def _stub_registry_execute(monkeypatch, intent, agent_id, *, healthy: bool = True):
    """Patch ActionRegistry handler and agent registry health for one agent."""
    from actions.registry import ActionRegistry
    from agents.base import AgentId
    from agents.registry import AgentRegistry, AgentRegistration
    from core.results import result_success
    from core.types import CommandRequest, Intent

    action_reg = ActionRegistry()
    action_reg._actions[intent.value].execute = lambda r: result_success(  # type: ignore[method-assign]
        intent,
        "stub ok",
    )

    agent_reg = AgentRegistry()
    agent_reg.register(AgentRegistration(
        agent_id=agent_id,
        agent=object(),
        health_check=lambda: healthy,
    ))
    monkeypatch.setattr(
        "agents.runtime_wiring.ensure_agent_registry",
        lambda: agent_reg,
    )
    return action_reg, CommandRequest(raw_text="test", intent=intent)


def test_open_browser_records_browser_agent(monkeypatch):
    from agents.base import AgentId
    from core.types import Intent

    reg, req = _stub_registry_execute(
        monkeypatch, Intent.OPEN_BROWSER, AgentId.BROWSER, healthy=True,
    )
    result = reg.execute(req)
    assert result.data["agent_id"] == AgentId.BROWSER.value
    assert result.data["agent_health"] is True
    assert result.data["routing_source"] == "intent_routing.agent_for_intent"


def test_summarize_this_screen_records_desktop_agent(monkeypatch):
    from agents.base import AgentId
    from core.types import Intent

    reg, req = _stub_registry_execute(
        monkeypatch, Intent.SUMMARIZE_THIS_SCREEN, AgentId.DESKTOP, healthy=True,
    )
    result = reg.execute(req)
    assert result.data["agent_id"] == AgentId.DESKTOP.value
    assert result.data["agent_health"] is True


def test_trading_command_records_trading_agent(monkeypatch):
    from agents.base import AgentId
    from core.types import Intent

    reg, req = _stub_registry_execute(
        monkeypatch, Intent.RUN_LIVE_DAILY_LOOP, AgentId.TRADING, healthy=True,
    )
    result = reg.execute(req)
    assert result.data["agent_id"] == AgentId.TRADING.value
    assert result.data["agent_health"] is True


def test_coding_command_records_coding_agent(monkeypatch):
    from agents.base import AgentId
    from core.types import Intent

    reg, req = _stub_registry_execute(
        monkeypatch, Intent.FIND_FUNCTION, AgentId.CODING, healthy=True,
    )
    result = reg.execute(req)
    assert result.data["agent_id"] == AgentId.CODING.value
    assert result.data["agent_health"] is True


def test_unhealthy_browser_blocks_open_browser(monkeypatch):
    from agents.base import AgentId
    from core.types import ActionStatus, Intent

    reg, req = _stub_registry_execute(
        monkeypatch, Intent.OPEN_BROWSER, AgentId.BROWSER, healthy=False,
    )
    result = reg.execute(req)
    assert result.status == ActionStatus.FAILED
    assert result.data["agent_id"] == AgentId.BROWSER.value
    assert result.data["agent_health"] is False
    assert result.data.get("blocked_by_agent_health") is True


def test_unhealthy_browser_allows_show_browser_health(monkeypatch):
    from agents.base import AgentId
    from agents.registry import AgentRegistry, AgentRegistration
    from actions.registry import ActionRegistry
    from core.results import result_success
    from core.types import ActionStatus, CommandRequest, Intent

    action_reg = ActionRegistry()
    action_reg._actions[Intent.SHOW_BROWSER_HEALTH.value].execute = (  # type: ignore[method-assign]
        lambda r: result_success(Intent.SHOW_BROWSER_HEALTH, "health ok")
    )
    agent_reg = AgentRegistry()
    agent_reg.register(AgentRegistration(
        agent_id=AgentId.BROWSER,
        agent=object(),
        health_check=lambda: False,
    ))
    monkeypatch.setattr(
        "agents.runtime_wiring.ensure_agent_registry",
        lambda: agent_reg,
    )
    result = action_reg.execute(
        CommandRequest(raw_text="show browser health", intent=Intent.SHOW_BROWSER_HEALTH)
    )
    assert result.status == ActionStatus.SUCCESS
    assert result.data["agent_id"] == AgentId.BROWSER.value
    assert result.data["agent_health"] is False


def test_command_history_includes_agent_metadata(tmp_path, monkeypatch):
    """Router command_history.jsonl must persist agent execution fields from result.data."""
    import json

    import brain.router as router_module
    from agents.base import AgentId
    from brain.router import CommandRouter
    from core.types import ActionStatus, CommandRequest, CommandResult, Intent

    history = tmp_path / "command_history.jsonl"
    monkeypatch.setattr("config.COMMAND_HISTORY_PATH", history, raising=False)
    monkeypatch.setattr(router_module, "COMMAND_HISTORY_PATH", history, raising=False)
    router_module._history_writers.clear()

    router = CommandRouter()
    request = CommandRequest(
        raw_text="open browser",
        intent=Intent.OPEN_BROWSER,
        confidence=1.0,
    )
    result = CommandResult(
        intent=Intent.OPEN_BROWSER,
        status=ActionStatus.SUCCESS,
        summary="Browser opened.",
        data={
            "agent_id": AgentId.BROWSER.value,
            "agent_health": True,
            "routing_source": "intent_routing.agent_for_intent",
        },
    )
    router._log_command(request, result, duration_ms=12, log_meta={"input_mode": "text"})

    assert history.is_file()
    entry = json.loads(history.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert entry["intent"] == Intent.OPEN_BROWSER.value
    assert entry["agent_id"] == AgentId.BROWSER.value
    assert entry["agent_health"] is True
    assert entry["routing_source"] == "intent_routing.agent_for_intent"


def test_command_history_block_reason_when_agent_unhealthy(tmp_path, monkeypatch):
    import json

    import brain.router as router_module
    from brain.router import CommandRouter
    from core.types import ActionStatus, CommandRequest, CommandResult, Intent

    history = tmp_path / "command_history.jsonl"
    monkeypatch.setattr("config.COMMAND_HISTORY_PATH", history, raising=False)
    monkeypatch.setattr(router_module, "COMMAND_HISTORY_PATH", history, raising=False)
    router_module._history_writers.clear()

    router = CommandRouter()
    request = CommandRequest(raw_text="open browser", intent=Intent.OPEN_BROWSER)
    reason = "browser agent is unhealthy; refusing unsafe execution."
    result = CommandResult(
        intent=Intent.OPEN_BROWSER,
        status=ActionStatus.FAILED,
        summary=reason,
        error=reason,
        data={
            "agent_id": "browser",
            "agent_health": False,
            "routing_source": "intent_routing.agent_for_intent",
            "blocked_by_agent_health": True,
        },
    )
    router._log_command(request, result, duration_ms=5)

    entry = json.loads(history.read_text(encoding="utf-8").strip())
    assert entry["block_reason"] == reason
    assert entry["agent_id"] == "browser"


def test_validate_registry_function_returns_list():
    """validate_registry() must return a list (may be non-empty if agents unhealthy)."""
    # Use a fresh registry to avoid coupling to process state
    from agents.registry import AgentRegistry, AgentRegistration, validate_registry
    from agents.base import AgentId
    import agents.registry as reg_module

    original = reg_module._registry
    try:
        reg_module._registry = AgentRegistry()
        reg_module._registry.register(AgentRegistration(
            agent_id=AgentId.EXECUTIVE,
            agent=object(),
            health_check=lambda: True,
        ))
        errors = validate_registry()
        assert isinstance(errors, list)
        assert errors == []
    finally:
        reg_module._registry = original
