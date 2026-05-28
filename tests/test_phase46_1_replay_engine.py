"""Phase 46.1 deterministic replay and verification engine tests."""

from __future__ import annotations

from pathlib import Path

from actions.registry import ActionRegistry
from brain.intent_classifier import classify_rules
from core.types import CommandRequest, Intent


def _fixture(root: Path) -> None:
    (root / "reports" / "live_paper" / "dual").mkdir(parents=True)
    (root / "reports" / "backtests").mkdir(parents=True)
    (root / "reports" / "live_paper" / "state").mkdir(parents=True)
    (root / "configs").mkdir(parents=True)
    (root / "universe").mkdir(parents=True)
    (root / "services").mkdir(parents=True)
    (root / "algo_scanner" / "backtest").mkdir(parents=True)
    (root / "algo_scanner" / "strategy").mkdir(parents=True)
    (root / "reports" / "live_paper" / "dual" / "latest_AAPL.txt").write_text(
        "AAPL 2026-01-01T09:35:00 close: 101.5 signal entry ranking risk stale price n_execution_attempts=0",
        encoding="utf-8",
    )
    (root / "reports" / "backtests" / "backtest_AAPL.txt").write_text(
        "AAPL 2026-01-01T09:30:00 close: 100.5 completed bars ranking entry stop target universe slippage",
        encoding="utf-8",
    )
    (root / "configs" / "strategy.yaml").write_text("max_open_positions: 5\n", encoding="utf-8")
    (root / "universe" / "symbols.txt").write_text("AAPL\nMSFT\n", encoding="utf-8")
    (root / "services" / "live_paper_engine.py").write_text(
        "last_closed_bar = bars.iloc[-2]\nn_execution_attempts = 0\nexcept Exception:\n    pass\n",
        encoding="utf-8",
    )
    (root / "algo_scanner" / "backtest" / "fib_quality.py").write_text(
        "bar = df.iloc[-1]\nscore = rank_signal(bar)\n",
        encoding="utf-8",
    )
    (root / "algo_scanner" / "strategy" / "real_algo.py").write_text(
        "entry_gate = signal and not stale_price\n",
        encoding="utf-8",
    )


def _patch_roots(monkeypatch, root: Path, tmp_path: Path) -> None:
    import investigation.fixture_builder as fixture_builder
    import investigation.replay_engine as replay_engine
    import investigation.replay_snapshot as replay_snapshot
    import phase45_investigation

    monkeypatch.setattr(replay_engine, "TRADING_PROJECT_ROOT", root)
    monkeypatch.setattr(phase45_investigation, "TRADING_PROJECT_ROOT", root)
    monkeypatch.setattr(fixture_builder, "GENERATED_DIR", tmp_path / "tests" / "generated")
    monkeypatch.setattr(replay_snapshot, "SNAPSHOT_DIR", tmp_path / "reports" / "jarvis_investigations" / "replays")


def test_deterministic_replay_consistency(monkeypatch, tmp_path):
    import investigation.replay_engine as replay_engine

    root = tmp_path / "trading"
    _fixture(root)
    _patch_roots(monkeypatch, root, tmp_path)

    a = replay_engine.replay_symbol("AAPL")
    b = replay_engine.replay_symbol("AAPL")

    assert a.replay_hash == b.replay_hash
    assert a.config_hash == b.config_hash
    assert a.universe_hash == b.universe_hash
    assert a.selected_bars


def test_identical_replay_hashes(monkeypatch, tmp_path):
    import investigation.replay_engine as replay_engine

    root = tmp_path / "trading"
    _fixture(root)
    _patch_roots(monkeypatch, root, tmp_path)

    hashes = {replay_engine.replay_symbol("AAPL").replay_hash for _ in range(3)}
    assert len(hashes) == 1


def test_divergence_detection(monkeypatch, tmp_path):
    from investigation.replay_diff import diff_live_backtest

    root = tmp_path / "trading"
    _fixture(root)
    _patch_roots(monkeypatch, root, tmp_path)

    diff = diff_live_backtest("AAPL")
    assert diff.first_divergence
    assert diff.divergence_reasons
    assert diff.evidence_paths


def test_hypothesis_verification(monkeypatch, tmp_path):
    from investigation.replay_report import verify_top_hypothesis_command as report_verify

    root = tmp_path / "trading"
    _fixture(root)
    _patch_roots(monkeypatch, root, tmp_path)

    text = report_verify("AAPL")
    assert "Hypothesis verification report" in text
    assert "confidence:" in text
    assert "reproducibility_score:" in text


def test_stale_bar_detection(monkeypatch, tmp_path):
    from investigation.replay_diff import format_replay_diff, diff_live_backtest

    root = tmp_path / "trading"
    _fixture(root)
    _patch_roots(monkeypatch, root, tmp_path)

    text = format_replay_diff(diff_live_backtest("AAPL"))
    assert "stale" in text.lower() or "incomplete candle" in text.lower()


def test_ordering_mismatch_detection(monkeypatch, tmp_path):
    from investigation.replay_engine import replay_symbol

    root = tmp_path / "trading"
    _fixture(root)
    _patch_roots(monkeypatch, root, tmp_path)

    replay = replay_symbol("AAPL")
    rank = replay.steps[1]
    assert rank.name == "ranking"
    assert "symbol_order" in rank.inputs


def test_replay_snapshot(monkeypatch, tmp_path):
    from investigation.replay_snapshot import export_replay_snapshot

    root = tmp_path / "trading"
    _fixture(root)
    _patch_roots(monkeypatch, root, tmp_path)

    path = export_replay_snapshot("AAPL")
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "replay_hash" in text
    assert "evidence_references" in text


def test_fixture_generation(monkeypatch, tmp_path):
    from investigation.fixture_builder import build_verification_fixture

    root = tmp_path / "trading"
    _fixture(root)
    _patch_roots(monkeypatch, root, tmp_path)

    path = build_verification_fixture("AAPL")
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "two_bar_mismatch" in text
    assert "ranking_order" in text


def test_no_execution_side_effects(monkeypatch, tmp_path):
    from phase45_investigation import plan_verification_run

    root = tmp_path / "trading"
    _fixture(root)
    _patch_roots(monkeypatch, root, tmp_path)

    def _boom(*_args, **_kwargs):
        raise AssertionError("subprocess must not run")

    monkeypatch.setattr("subprocess.Popen", _boom)
    assert "not executed" in plan_verification_run().lower()


def test_replay_commands_classify_and_registry(monkeypatch, tmp_path):
    import brain.english_voice_phrases  # noqa: F401
    import brain.intent_classifier  # noqa: F401

    root = tmp_path / "trading"
    _fixture(root)
    _patch_roots(monkeypatch, root, tmp_path)

    expected = {
        "replay symbol AAPL": Intent.REPLAY_SYMBOL,
        "replay latest signal": Intent.REPLAY_LATEST_SIGNAL,
        "replay live vs backtest AAPL": Intent.REPLAY_LIVE_VS_BACKTEST,
        "verify top hypothesis": Intent.VERIFY_TOP_HYPOTHESIS,
        "verify all hypotheses": Intent.VERIFY_ALL_HYPOTHESES,
        "show replay timeline": Intent.SHOW_REPLAY_TIMELINE,
        "show replay diff": Intent.SHOW_REPLAY_DIFF,
        "build verification fixture": Intent.BUILD_VERIFICATION_FIXTURE,
        "export replay snapshot": Intent.EXPORT_REPLAY_SNAPSHOT,
        "trace signal lifecycle": Intent.TRACE_SIGNAL_LIFECYCLE,
        "trace execution lifecycle": Intent.TRACE_EXECUTION_LIFECYCLE,
        "show causality graph": Intent.SHOW_CAUSALITY_GRAPH,
        "investigation confidence report": Intent.INVESTIGATION_CONFIDENCE_REPORT,
    }
    for phrase, intent in expected.items():
        assert classify_rules(phrase).intent == intent
    registry = ActionRegistry()
    for intent in expected.values():
        assert intent.value in registry._actions
    result = registry._actions[Intent.REPLAY_SYMBOL.value].execute(
        CommandRequest(raw_text="replay symbol AAPL", intent=Intent.REPLAY_SYMBOL)
    )
    assert result.data["read_only"] is True
    assert "Deterministic replay: AAPL" in result.summary
