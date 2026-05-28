"""Phase 46.2 patch simulation tests."""

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
    (root / "reports" / "live_paper" / "dual" / "latest_AAPL.txt").write_text(
        "AAPL 2026-01-01T09:35:00 close: 137.0 signal selected_bar_complete false incomplete execution skipped",
        encoding="utf-8",
    )
    (root / "reports" / "backtests" / "backtest_AAPL.txt").write_text(
        "AAPL 2026-01-01T09:30:00 close: 136.5 completed bars ranking entry stop target universe slippage",
        encoding="utf-8",
    )
    (root / "services" / "live_paper_engine.py").write_text(
        "candidate_bar = bars.iloc[-1]\n",
        encoding="utf-8",
    )
    (root / "algo_scanner" / "backtest" / "fib_quality.py").write_text(
        "bar = df.iloc[-2]\n",
        encoding="utf-8",
    )


def _patch(monkeypatch, root: Path, tmp_path: Path) -> None:
    import investigation.fixture_builder as fixture_builder
    import investigation.patch_simulation as patch_sim
    import investigation.replay_engine as replay_engine

    monkeypatch.setattr(replay_engine, "TRADING_PROJECT_ROOT", root)
    monkeypatch.setattr(patch_sim, "TRADING_PROJECT_ROOT", root)
    monkeypatch.setattr(patch_sim, "SIMULATION_DIR", tmp_path / "reports" / "patch_simulations")
    monkeypatch.setattr(fixture_builder, "GENERATED_DIR", tmp_path / "tests" / "generated")


def test_candidate_generation():
    from investigation.patch_simulation import generate_patch_candidates

    candidates = generate_patch_candidates()
    assert {c.candidate_id for c in candidates} == {"A", "B", "C", "D"}
    assert "incomplete_bar" in candidates[2].minimal_diff


def test_no_production_file_mutation(monkeypatch, tmp_path):
    from investigation.patch_simulation import run_patch_simulation

    root = tmp_path / "trading"
    _fixture(root)
    _patch(monkeypatch, root, tmp_path)
    prod = root / "services" / "live_paper_engine.py"
    before = prod.read_text(encoding="utf-8")
    run_patch_simulation("AAPL")
    assert prod.read_text(encoding="utf-8") == before


def test_simulated_replay_fixes_incomplete_bar(monkeypatch, tmp_path):
    from investigation.patch_simulation import run_patch_simulation

    root = tmp_path / "trading"
    _fixture(root)
    _patch(monkeypatch, root, tmp_path)
    sim = run_patch_simulation("AAPL")
    assert sim.divergence_fixed is True
    assert sim.new_divergence_introduced is False


def test_before_after_diff(monkeypatch, tmp_path):
    from investigation.patch_simulation import compare_replay_before_after

    root = tmp_path / "trading"
    _fixture(root)
    _patch(monkeypatch, root, tmp_path)
    text = compare_replay_before_after("AAPL")
    assert "Fixed mismatch: yes" in text
    assert "Before:" in text
    assert "After simulated fix:" in text


def test_impact_estimate_handles_missing_files(monkeypatch, tmp_path):
    from investigation.patch_simulation import estimate_patch_impact
    import investigation.patch_simulation as patch_sim

    monkeypatch.setattr(patch_sim, "TRADING_PROJECT_ROOT", tmp_path / "missing")
    text = estimate_patch_impact()
    assert "affected symbols: unknown" in text
    assert "confidence: LOW" in text


def test_patch_proposal_preview_only(monkeypatch, tmp_path):
    from investigation.patch_simulation import upgraded_patch_proposal

    root = tmp_path / "trading"
    _fixture(root)
    _patch(monkeypatch, root, tmp_path)
    text = upgraded_patch_proposal()
    assert "preview only" in text.lower()
    assert "Unified diff preview" in text
    assert "Risk score" in text


def test_approval_required_before_apply(monkeypatch, tmp_path):
    from investigation.patch_simulation import approve_patch_apply, run_patch_simulation

    root = tmp_path / "trading"
    _fixture(root)
    _patch(monkeypatch, root, tmp_path)
    run_patch_simulation("AAPL")
    assert "not enabled" in approve_patch_apply()


def test_report_saved(monkeypatch, tmp_path):
    from investigation.patch_simulation import generate_patch_simulation_report, run_patch_simulation

    root = tmp_path / "trading"
    _fixture(root)
    _patch(monkeypatch, root, tmp_path)
    run_patch_simulation("AAPL")
    text = generate_patch_simulation_report()
    assert "Patch simulation report saved:" in text
    assert list((tmp_path / "reports" / "patch_simulations").glob("*_patch_simulation.md"))


def test_no_live_trading_execution(monkeypatch, tmp_path):
    from investigation.patch_simulation import run_patch_simulation

    root = tmp_path / "trading"
    _fixture(root)
    _patch(monkeypatch, root, tmp_path)

    def _boom(*_args, **_kwargs):
        raise AssertionError("subprocess must not run")

    monkeypatch.setattr("subprocess.Popen", _boom)
    assert run_patch_simulation("AAPL").divergence_fixed is True


def test_router_security_unchanged_and_commands_registered(monkeypatch, tmp_path):
    import brain.english_voice_phrases  # noqa: F401
    import brain.intent_classifier  # noqa: F401

    root = tmp_path / "trading"
    _fixture(root)
    _patch(monkeypatch, root, tmp_path)
    expected = {
        "simulate patch for top hypothesis": Intent.SIMULATE_PATCH_TOP_HYPOTHESIS,
        "run patch simulation": Intent.RUN_PATCH_SIMULATION,
        "compare replay before after": Intent.COMPARE_REPLAY_BEFORE_AFTER,
        "estimate patch impact": Intent.ESTIMATE_PATCH_IMPACT,
        "generate patch simulation report": Intent.GENERATE_PATCH_SIMULATION_REPORT,
        "show patch simulation": Intent.SHOW_PATCH_SIMULATION,
        "approve patch apply": Intent.APPROVE_PATCH_APPLY,
        "reject patch apply": Intent.REJECT_PATCH_APPLY,
    }
    registry = ActionRegistry()
    for phrase, intent in expected.items():
        assert classify_rules(phrase).intent == intent
        assert intent.value in registry._actions
    result = registry._actions[Intent.RUN_PATCH_SIMULATION.value].execute(
        CommandRequest(raw_text="run patch simulation", intent=Intent.RUN_PATCH_SIMULATION)
    )
    assert result.data["read_only"] is True
