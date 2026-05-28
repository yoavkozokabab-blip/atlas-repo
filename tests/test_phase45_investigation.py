"""Phase 45 read-only investigation engine tests."""

from __future__ import annotations

from pathlib import Path

from actions.registry import ActionRegistry
from brain.intent_classifier import classify_rules
from config import ALLOWED_INTENTS, IMPLEMENTED_INTENTS
from core.types import ActionStatus, CommandRequest, Intent


PHASE45_COMMANDS = {
    "phase 45 status": Intent.PHASE45_STATUS,
    "inspect project": Intent.INSPECT_PROJECT,
    "summarize current project": Intent.SUMMARIZE_CURRENT_PROJECT,
    "find failing tests": Intent.FIND_FAILING_TESTS,
    "explain latest error": Intent.EXPLAIN_LATEST_ERROR,
    "investigate trading mismatch": Intent.INVESTIGATE_TRADING_MISMATCH,
    "compare live vs backtest": Intent.COMPARE_LIVE_VS_BACKTEST,
    "inspect latest live report": Intent.INSPECT_LATEST_LIVE_REPORT,
    "inspect latest backtest report": Intent.INSPECT_LATEST_BACKTEST_REPORT,
    "find recent code changes": Intent.FIND_RECENT_CODE_CHANGES,
    "propose investigation plan": Intent.PROPOSE_INVESTIGATION_PLAN,
    "run safe diagnostics": Intent.RUN_SAFE_DIAGNOSTICS,
    "generate findings report": Intent.GENERATE_FINDINGS_REPORT,
}


def test_phase45_commands_classify():
    for phrase, intent in PHASE45_COMMANDS.items():
        assert classify_rules(phrase).intent == intent


def test_phase45_intents_are_allowlisted_and_registered():
    registry = ActionRegistry()
    for intent in PHASE45_COMMANDS.values():
        assert intent.value in ALLOWED_INTENTS
        assert intent.value in IMPLEMENTED_INTENTS
        assert intent.value in registry._actions


def test_reports_handle_missing_files(monkeypatch, tmp_path):
    import phase45_investigation as p45

    missing_root = tmp_path / "missing_trading_root"
    monkeypatch.setattr(p45, "TRADING_PROJECT_ROOT", missing_root)

    live = p45.inspect_latest_live_report()
    backtest = p45.inspect_latest_backtest_report()

    assert "No live report files found" in live
    assert "No backtest report files found" in backtest
    assert "Evidence checked:" in live
    assert "Evidence checked:" in backtest


def test_compare_live_vs_backtest_includes_required_checks(monkeypatch, tmp_path):
    import phase45_investigation as p45

    root = tmp_path / "trading"
    report_dir = root / "reports" / "live_paper" / "dual"
    report_dir.mkdir(parents=True)
    (report_dir / "latest.txt").write_text(
        "signal entry rank risk stale price universe config window slippage state",
        encoding="utf-8",
    )
    monkeypatch.setattr(p45, "TRADING_PROJECT_ROOT", root)

    text = p45.compare_live_vs_backtest()

    for key in (
        "signal mismatch",
        "entry mismatch",
        "ranking mismatch",
        "risk sizing mismatch",
        "stale price issues",
        "universe differences",
        "config drift",
        "data window differences",
        "execution/slippage assumptions",
        "paper/live state problems",
    ):
        assert key in text
    assert "evidence:" in text
    assert "Next actions:" in text


def test_safe_diagnostics_are_read_only(monkeypatch, tmp_path):
    import phase45_investigation as p45

    project = tmp_path / "proj"
    project.mkdir()
    (project / "main.py").write_text("print('ok')\n", encoding="utf-8")
    monkeypatch.setattr(p45, "PROJECT_ROOT", project)
    monkeypatch.setattr(p45, "TRADING_PROJECT_ROOT", tmp_path / "trading")

    before = sorted(str(p.relative_to(project)) for p in project.rglob("*"))
    text = p45.run_safe_diagnostics()
    after = sorted(str(p.relative_to(project)) for p in project.rglob("*"))

    assert before == after
    assert "read-only" in text.lower()
    assert "no live trading" in text.lower()


def test_phase45_action_output_includes_evidence_and_next_actions(monkeypatch, tmp_path):
    import phase45_investigation as p45

    root = tmp_path / "trading"
    dual = root / "reports" / "live_paper" / "dual"
    dual.mkdir(parents=True)
    (dual / "report.txt").write_text("entry rejected risk stale price", encoding="utf-8")
    monkeypatch.setattr(p45, "TRADING_PROJECT_ROOT", root)

    registry = ActionRegistry()
    action = registry._actions[Intent.COMPARE_LIVE_VS_BACKTEST.value]
    result = action.execute(
        CommandRequest(
            raw_text="compare live vs backtest",
            intent=Intent.COMPARE_LIVE_VS_BACKTEST,
        )
    )

    assert result.status == ActionStatus.SUCCESS
    assert result.data["read_only"] is True
    assert "Evidence roots:" in result.summary
    assert "Next actions:" in result.summary


def test_no_live_execution_or_subprocess(monkeypatch):
    import phase45_investigation as p45

    def _boom(*_args, **_kwargs):
        raise AssertionError("subprocess must not be used")

    monkeypatch.setattr("subprocess.Popen", _boom)
    text = p45.propose_investigation_plan()

    assert "read-only" in text.lower()
    assert "requires approval" in text.lower()
