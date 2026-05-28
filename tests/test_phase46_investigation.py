"""Phase 46 expert investigation engine tests."""

from __future__ import annotations

from pathlib import Path

from actions.registry import ActionRegistry
from brain.intent_classifier import classify_rules
from core.types import CommandRequest, Intent


def _make_trading_fixture(root: Path) -> None:
    (root / "algo_scanner" / "backtest").mkdir(parents=True)
    (root / "algo_scanner" / "strategy").mkdir(parents=True)
    (root / "services").mkdir(parents=True)
    (root / "analytics").mkdir(parents=True)
    (root / "reports" / "live_paper" / "dual").mkdir(parents=True)
    (root / "reports" / "live_paper" / "state").mkdir(parents=True)
    (root / "reports" / "backtests").mkdir(parents=True)
    (root / "universe").mkdir(parents=True)
    (root / "configs").mkdir(parents=True)
    (root / "algo_scanner" / "backtest" / "fib_quality.py").write_text(
        "bar = df.iloc[-1]\nrank = score_signal(bar)\nstop_loss = bar.close * .95\n",
        encoding="utf-8",
    )
    (root / "algo_scanner" / "strategy" / "real_algo.py").write_text(
        "last_closed_bar = bars.iloc[-2]\nentry_gate = signal and not stale_price\n",
        encoding="utf-8",
    )
    (root / "services" / "live_paper_engine.py").write_text(
        "n_execution_attempts = 0\nexcept Exception:\n    pass\n",
        encoding="utf-8",
    )
    (root / "services" / "live_dual_paper_cycle.py").write_text(
        "processed_symbols = 738\nexecution_adapter_disabled = True\n",
        encoding="utf-8",
    )
    (root / "services" / "portfolio_manager.py").write_text(
        "max_open_positions = 5\nrisk_cap = 0.02\n",
        encoding="utf-8",
    )
    (root / "analytics" / "portfolio_engine.py").write_text(
        "position_size = risk_per_trade / stop_distance\n",
        encoding="utf-8",
    )
    (root / "reports" / "live_paper" / "dual" / "latest.txt").write_text(
        "signal entry ranking risk stale price universe config window slippage state n_execution_attempts=0",
        encoding="utf-8",
    )
    (root / "reports" / "backtests" / "backtest_latest.txt").write_text(
        "completed bars ranking entry stop target risk universe slippage",
        encoding="utf-8",
    )
    (root / "universe" / "symbols.txt").write_text("AAPL\nMSFT\n", encoding="utf-8")
    (root / "configs" / "strategy.yaml").write_text("max_open_positions: 5\n", encoding="utf-8")


def test_phase46_commands_classify():
    expected = {
        "phase 46 status": Intent.PHASE46_STATUS,
        "build investigation graph": Intent.BUILD_INVESTIGATION_GRAPH,
        "show investigation graph": Intent.SHOW_INVESTIGATION_GRAPH,
        "search investigation graph stale": Intent.SEARCH_INVESTIGATION_GRAPH,
        "trace algorithm behavior": Intent.TRACE_ALGORITHM_BEHAVIOR,
        "diff live and backtest logic": Intent.DIFF_LIVE_BACKTEST_LOGIC,
        "hunt algorithm bugs": Intent.HUNT_ALGORITHM_BUGS,
        "propose algorithm patch": Intent.PROPOSE_ALGORITHM_PATCH,
        "plan verification run": Intent.PLAN_VERIFICATION_RUN,
    }
    for phrase, intent in expected.items():
        assert classify_rules(phrase).intent == intent


def test_graph_building_and_search(monkeypatch, tmp_path):
    import phase45_investigation as p46

    root = tmp_path / "trading"
    _make_trading_fixture(root)
    monkeypatch.setattr(p46, "TRADING_PROJECT_ROOT", root)

    graph = p46.build_investigation_graph()
    search = p46.search_investigation_graph("stale")

    assert "Nodes:" in graph
    assert "Edges:" in graph
    assert "confidence=" in graph
    assert str(root) in graph
    assert "stale" in search.lower()


def test_ranked_hypotheses_include_evidence(monkeypatch, tmp_path):
    import phase45_investigation as p46

    root = tmp_path / "trading"
    _make_trading_fixture(root)
    monkeypatch.setattr(p46, "TRADING_PROJECT_ROOT", root)

    text = p46.compare_live_vs_backtest()

    assert "Ranked hypotheses:" in text
    assert "HIGH" in text
    assert "why it matters:" in text
    assert "how to verify:" in text
    assert "suggested test:" in text
    assert "evidence:" in text


def test_behavior_trace_output(monkeypatch, tmp_path):
    import phase45_investigation as p46

    root = tmp_path / "trading"
    _make_trading_fixture(root)
    monkeypatch.setattr(p46, "TRADING_PROJECT_ROOT", root)

    text = p46.trace_algorithm_behavior()

    assert "signal detection" in text
    assert "ranking" in text
    assert "entry gate" in text
    assert "paper/live decision" in text
    assert str(root / "services" / "live_paper_engine.py") in text


def test_diff_engine_categories(monkeypatch, tmp_path):
    import phase45_investigation as p46

    root = tmp_path / "trading"
    _make_trading_fixture(root)
    monkeypatch.setattr(p46, "TRADING_PROJECT_ROOT", root)

    text = p46.diff_live_and_backtest_logic()

    for category in ("signal rules", "entry timing", "ranking", "risk sizing", "universe"):
        assert category in text
    assert "severity=" in text
    assert "next verification command:" in text


def test_bug_hunt_finds_known_patterns(monkeypatch, tmp_path):
    import phase45_investigation as p46

    root = tmp_path / "trading"
    _make_trading_fixture(root)
    monkeypatch.setattr(p46, "TRADING_PROJECT_ROOT", root)

    text = p46.hunt_algorithm_bugs()

    assert "issue:" in text
    assert "snippet:" in text
    assert "why suspicious:" in text
    assert "suggested test:" in text


def test_patch_proposal_preview_only(monkeypatch, tmp_path):
    import phase45_investigation as p46

    root = tmp_path / "trading"
    _make_trading_fixture(root)
    monkeypatch.setattr(p46, "TRADING_PROJECT_ROOT", root)

    text = p46.propose_algorithm_patch()

    assert "preview only" in text.lower()
    assert "no files changed" in text.lower()
    assert "Minimal diff" in text
    assert "Rollback plan" in text


def test_verification_plan_command_text():
    import phase45_investigation as p46

    text = p46.plan_verification_run()

    assert "py -3 -m pytest" in text
    assert "compileall" in text
    assert "--dry-run" in text
    assert "not executed" in text.lower()


def test_missing_files_degrade_gracefully(monkeypatch, tmp_path):
    import phase45_investigation as p46

    monkeypatch.setattr(p46, "TRADING_PROJECT_ROOT", tmp_path / "missing")

    assert "No expected behavior files found" in p46.trace_algorithm_behavior()
    assert "Nodes:" in p46.build_investigation_graph()
    assert "No backtest report files found" in p46.inspect_latest_backtest_report()


def test_report_saved_with_sections(monkeypatch, tmp_path):
    import phase45_investigation as p46

    root = tmp_path / "trading"
    _make_trading_fixture(root)
    report_dir = tmp_path / "reports" / "jarvis_investigations"
    monkeypatch.setattr(p46, "TRADING_PROJECT_ROOT", root)
    monkeypatch.setattr(p46, "PHASE46_REPORT_DIR", report_dir)

    text = p46.generate_findings_report()

    assert "Findings report saved:" in text
    assert "Executive Summary" in text
    assert "Top 5 Root Causes" in text
    assert "Evidence Table" in text
    assert list(report_dir.glob("*_findings.md"))


def test_no_live_execution_or_subprocess(monkeypatch, tmp_path):
    import phase45_investigation as p46

    root = tmp_path / "trading"
    _make_trading_fixture(root)
    monkeypatch.setattr(p46, "TRADING_PROJECT_ROOT", root)

    def _boom(*_args, **_kwargs):
        raise AssertionError("subprocess must not be used")

    monkeypatch.setattr("subprocess.Popen", _boom)
    text = p46.run_safe_diagnostics()

    assert "no live trading" in text.lower()


def test_phase46_registry_action_read_only(monkeypatch, tmp_path):
    import phase45_investigation as p46

    root = tmp_path / "trading"
    _make_trading_fixture(root)
    monkeypatch.setattr(p46, "TRADING_PROJECT_ROOT", root)
    registry = ActionRegistry()

    result = registry._actions[Intent.HUNT_ALGORITHM_BUGS.value].execute(
        CommandRequest(raw_text="hunt algorithm bugs", intent=Intent.HUNT_ALGORITHM_BUGS)
    )

    assert result.data["read_only"] is True
    assert "snippet:" in result.summary
