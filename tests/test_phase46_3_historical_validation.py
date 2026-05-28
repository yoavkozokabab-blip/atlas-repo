"""Phase 46.3 historical validation sweep tests."""

from __future__ import annotations

from pathlib import Path

from actions.registry import ActionRegistry
from brain.intent_classifier import classify_rules
from core.types import CommandRequest, Intent


def _fixture(root: Path) -> None:
    (root / "reports" / "live_paper" / "dual").mkdir(parents=True)
    (root / "reports" / "live_paper" / "state").mkdir(parents=True)
    (root / "reports" / "live_paper_trials").mkdir(parents=True)
    (root / "reports" / "backtests").mkdir(parents=True)
    (root / "reports" / "live_paper" / "dual" / "daily_AAPL.txt").write_text(
        "AAPL signal selected_bar complete=false incomplete_bar index mismatch live=2 backtest=1 close mismatch",
        encoding="utf-8",
    )
    (root / "reports" / "live_paper_trials" / "weekly_MSFT.txt").write_text(
        "MSFT signal selected_bar_complete false incomplete execution skipped",
        encoding="utf-8",
    )
    (root / "reports" / "backtests" / "backtest_AAPL.txt").write_text(
        "AAPL completed signal backtest_close=136.5",
        encoding="utf-8",
    )


def _patch(monkeypatch, root: Path, tmp_path: Path) -> None:
    import investigation.historical_validation as hv

    monkeypatch.setattr(hv, "TRADING_PROJECT_ROOT", root)
    monkeypatch.setattr(hv, "VALIDATION_DIR", tmp_path / "validation_sweeps")
    monkeypatch.setattr(hv, "_LAST_SWEEP", None)


def test_sweep_runs_read_only(monkeypatch, tmp_path):
    import investigation.historical_validation as hv

    root = tmp_path / "trading"
    _fixture(root)
    _patch(monkeypatch, root, tmp_path)
    before = {p: p.read_text(encoding="utf-8") for p in root.rglob("*") if p.is_file()}
    sweep = hv.run_historical_validation_sweep()
    after = {p: p.read_text(encoding="utf-8") for p in root.rglob("*") if p.is_file()}
    assert before == after
    assert sweep.total_signals_analyzed > 0


def test_batch_replay_handles_missing_files(monkeypatch, tmp_path):
    import investigation.historical_validation as hv

    _patch(monkeypatch, tmp_path / "missing", tmp_path)
    sweep = hv.run_historical_validation_sweep()
    assert sweep.total_signals_analyzed == 0
    assert sweep.reduction_pct == 0.0


def test_divergence_reduction_calculation(monkeypatch, tmp_path):
    import investigation.historical_validation as hv

    root = tmp_path / "trading"
    _fixture(root)
    _patch(monkeypatch, root, tmp_path)
    sweep = hv.run_historical_validation_sweep()
    assert sweep.divergences_before >= sweep.divergences_after
    assert sweep.reduction_pct >= 0


def test_unstable_symbol_ranking(monkeypatch, tmp_path):
    import investigation.historical_validation as hv

    root = tmp_path / "trading"
    _fixture(root)
    _patch(monkeypatch, root, tmp_path)
    text = hv.show_worst_divergence_symbols()
    assert "Top unstable symbols" in text
    assert "AAPL" in text or "MSFT" in text


def test_recommendation_generation(monkeypatch, tmp_path):
    import investigation.historical_validation as hv

    root = tmp_path / "trading"
    _fixture(root)
    _patch(monkeypatch, root, tmp_path)
    text = hv.recommend_production_action()
    assert "recommendation:" in text
    assert "safety:" in text


def test_report_generation(monkeypatch, tmp_path):
    import investigation.historical_validation as hv

    root = tmp_path / "trading"
    _fixture(root)
    _patch(monkeypatch, root, tmp_path)
    sweep = hv.run_historical_validation_sweep()
    assert Path(sweep.report_json).is_file()
    assert Path(sweep.report_markdown).is_file()


def test_no_router_security_changes_and_actions(monkeypatch, tmp_path):
    root = tmp_path / "trading"
    _fixture(root)
    _patch(monkeypatch, root, tmp_path)
    expected = {
        "run historical validation sweep": Intent.RUN_HISTORICAL_VALIDATION_SWEEP,
        "show validation sweep": Intent.SHOW_VALIDATION_SWEEP,
        "export validation sweep": Intent.EXPORT_VALIDATION_SWEEP,
        "compare strategy metrics before after": Intent.COMPARE_STRATEGY_METRICS_BEFORE_AFTER,
        "show worst divergence symbols": Intent.SHOW_WORST_DIVERGENCE_SYMBOLS,
        "estimate production risk": Intent.ESTIMATE_PRODUCTION_RISK,
        "recommend production action": Intent.RECOMMEND_PRODUCTION_ACTION,
        "show investigation summary": Intent.SHOW_INVESTIGATION_SUMMARY,
    }
    registry = ActionRegistry()
    for phrase, intent in expected.items():
        assert classify_rules(phrase).intent == intent
        assert intent.value in registry._actions
    result = registry._actions[Intent.RUN_HISTORICAL_VALIDATION_SWEEP.value].execute(
        CommandRequest(
            raw_text="run historical validation sweep",
            intent=Intent.RUN_HISTORICAL_VALIDATION_SWEEP,
        )
    )
    assert result.data["read_only"] is True


def test_no_live_trading_execution(monkeypatch, tmp_path):
    import investigation.historical_validation as hv

    root = tmp_path / "trading"
    _fixture(root)
    _patch(monkeypatch, root, tmp_path)

    def _boom(*_args, **_kwargs):
        raise AssertionError("subprocess must not run")

    monkeypatch.setattr("subprocess.Popen", _boom)
    text = hv.estimate_production_risk()
    assert "no trading executed" in text.lower()
