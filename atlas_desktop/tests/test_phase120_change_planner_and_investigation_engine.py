"""Phase 120 — change planner, investigation engine, prompts, impact simulation."""

from __future__ import annotations

from pathlib import Path

import pytest

from atlas_desktop import api, planning_engine, server


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _planner_repo(tmp_path: Path) -> Path:
    root = tmp_path / "app"
    _write(root / "auth" / "login.py", "def login():\n    return True\n")
    _write(root / "auth" / "session.py", "from auth.login import login\n")
    _write(root / "api" / "stripe_billing.py", "def charge():\n    return 1\n")
    _write(root / "logging" / "audit.py", "def audit(event):\n    pass\n")
    _write(root / "services" / "backtest.py", "def run_backtest():\n    return []\n")
    _write(root / "services" / "paper_trading.py", "from services.backtest import run_backtest\n")
    _write(root / "notify" / "telegram_alerts.py", "def send_alert():\n    pass\n")
    _write(root / "ui" / "dashboard.py", "def render_metrics():\n    return {}\n")
    _write(root / "core" / "hub.py", "def hub():\n    return 0\n")
    return root


@pytest.fixture()
def planner_scan(tmp_path):
    api._STATE.update({"path": None, "scan": None, "graph": None, "index": None, "risks": None, "scan_cache": {}})
    result = api.scan_repository(str(_planner_repo(tmp_path)))
    assert result["ok"], result
    return result


def _graph_paths() -> set[str]:
    graph = api._STATE.get("graph") or {}
    return {
        n["path"]
        for n in graph.get("nodes", [])
        if n.get("type") == "module" and n.get("path")
    }


def _assert_grounded_paths(paths: list[str]) -> None:
    allowed = _graph_paths()
    for path in paths:
        assert path in allowed, f"Hallucinated path not in graph: {path}"


def test_change_plan_authentication_request(planner_scan):
    res = api.plan_change("Add user authentication with login sessions")
    assert res["ok"]
    plan = res["plan"]
    assert plan["intent"] == "authentication"
    assert plan["goal"]
    _assert_grounded_paths(plan["likely_affected_modules"])
    assert any("auth" in p for p in plan["likely_affected_modules"])
    assert res["prompts"]["claude"]
    assert res["prompts"]["codex"]
    assert res["prompts"]["cursor"]
    assert "Claude" in res["prompts"]["claude"] or "plan" in res["prompts"]["claude"].lower()


def test_change_plan_billing_request(planner_scan):
    res = api.plan_change("Add Stripe billing and subscriptions")
    assert res["ok"]
    plan = res["plan"]
    assert plan["intent"] == "billing"
    _assert_grounded_paths(plan["files_to_inspect_first"])
    assert any("stripe" in p or "billing" in p for p in plan["likely_affected_modules"])


def test_change_plan_logging_request(planner_scan):
    res = api.plan_change("Add audit logging for security events")
    assert res["ok"]
    plan = res["plan"]
    assert plan["intent"] in {"audit_logging", "general"}
    _assert_grounded_paths(plan["likely_affected_modules"])
    assert any("audit" in p or "log" in p for p in plan["likely_affected_modules"])


def test_investigation_paper_trading_symptom(planner_scan):
    res = api.investigate_symptom("The backtest is better than paper trading")
    assert res["ok"]
    plan = res["plan"]
    assert plan["intent"] == "paper_trading"
    _assert_grounded_paths(plan["likely_modules"])
    assert any("backtest" in p or "paper" in p for p in plan["likely_modules"])
    assert plan["confidence"]
    assert res["prompts"]["claude"]


def test_investigation_dashboard_mismatch(planner_scan):
    res = api.investigate_symptom("Dashboard numbers are wrong on the metrics page")
    assert res["ok"]
    plan = res["plan"]
    assert plan["intent"] == "dashboard_mismatch"
    _assert_grounded_paths(plan["suggested_files_to_inspect"])


def test_investigation_delayed_alerts(planner_scan):
    res = api.investigate_symptom("Telegram alerts are delayed by several minutes")
    assert res["ok"]
    plan = res["plan"]
    assert plan["intent"] == "delayed_alerts"
    _assert_grounded_paths(plan["likely_modules"])


def test_prompt_generation_includes_repo_context(planner_scan):
    res = api.plan_change("Add Redis caching layer")
    assert res["ok"]
    for tool in ("claude", "codex", "cursor"):
        prompt = res["prompts"][tool]
        assert prompt
        assert "Redis" in prompt or "redis" in prompt or "cache" in prompt.lower()


def test_impact_simulation_file_level(planner_scan):
    target = "auth/login.py"
    res = api.change_impact_simulation(target)
    assert res["ok"]
    sim = res["simulation"]
    assert sim["risk_level"] in {"low", "medium", "high", "unknown"}
    assert "potentially_affected_modules" in sim
    assert sim["tests_likely_affected"]
    assert res["limitations"]


def test_impact_simulation_module_level(planner_scan):
    res = api.change_impact_simulation("core/hub.py")
    assert res["ok"]
    assert res["target"]


def test_analytics_failure_does_not_break_planning(planner_scan, monkeypatch):
    import builtins

    real_open = builtins.open

    def deny(path, mode="r", *args, **kwargs):
        if "a" in mode and "analytics.jsonl" in str(path):
            raise PermissionError(13, "denied", str(path))
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", deny)
    res = api.plan_change("Add user authentication")
    assert res["ok"]
    assert res["plan"]["likely_affected_modules"]


def test_planning_routes_registered():
    routes = set(server.ROUTES)
    assert ("POST", "/api/planning/change") in routes
    assert ("POST", "/api/planning/investigate") in routes
    assert ("POST", "/api/planning/impact") in routes


def test_investigation_graph_module_count_symptom(planner_scan):
    res = api.investigate_symptom("scan graph shows wrong module count")
    assert res["ok"]
    plan = res["plan"]
    assert plan["intent"] == "graph_module_count"
    assert "DEBUG ANALYSIS" in res["formatted"]
    assert "## Executive Summary" in res["formatted"]
    assert plan.get("logical_hypothesis")
    assert plan.get("verification_steps")
    # Phase 123 — ranked hypotheses structure
    assert plan.get("hypotheses")
    assert plan.get("most_likely_root_cause")


def test_change_plan_includes_actionable_fields(planner_scan):
    res = api.plan_change("Add user authentication with login sessions")
    plan = res["plan"]
    assert plan.get("files_likely_to_change")
    assert plan.get("implementation_order")
    assert plan.get("verification_plan")
    assert plan.get("risk_level") in {"low", "medium", "high"}


def test_impact_direct_only_label(planner_scan):
    res = api.impact("auth/login.py")
    assert res["ok"]
    assert res.get("impact_scope") == "direct_only"
    assert res.get("transitive_available") is False


def test_token_savings_hidden_from_cockpit_by_default(planner_scan):
    summary = api.current_summary()
    sav = summary.get("token_savings") or {}
    assert sav.get("verified") is False
    assert sav.get("show_in_cockpit") is False


def test_formatters_include_headers():
    plan = {
        "goal": "Add auth",
        "likely_affected_modules": ["auth/login.py"],
        "likely_affected_subsystems": ["auth"],
        "entry_points": [],
        "files_to_inspect_first": ["auth/login.py"],
        "dependencies_involved": {"outbound_imports": [], "inbound_importers": []},
        "architectural_risks": [],
        "tests_likely_affected": [],
        "estimated_change_size": "Small",
        "confidence": "medium",
    }
    inv = {
        "symptom": "dashboard pnl is wrong",
        "likely_modules": ["ui/dashboard.py"],
        "most_likely_source": "ui/dashboard.py",
        "why": "test",
        "logical_hypothesis": "test hypothesis",
        "evidence": ["e1"],
        "confidence": "medium",
        "inspect_first": ["ui/dashboard.py"],
        "verification_steps": ["step1"],
        "risk_if_fixed": "risk",
        "limitations": ["lim"],
    }
    inv_text = planning_engine.format_investigation_plan_markdown(inv)
    assert "DEBUG ANALYSIS" in inv_text
    assert "## Executive Summary" in inv_text

    text = planning_engine.format_change_plan_markdown(plan)
    assert "CHANGE PLAN" in text
    assert "## Executive Summary" in text
