"""Phase 47 execution cleanup preview tests (safe unit scope)."""

from __future__ import annotations

from pathlib import Path

import investigation.execution_cleanup as ec
import investigation.execution_investigation as ei


def _fixture(root: Path) -> None:
    state = root / "reports" / "live_paper" / "dual" / "state"
    dual = root / "reports" / "live_paper" / "dual"
    state.mkdir(parents=True)
    dual.mkdir(parents=True)
    (state / "open_positions.json").write_text(
        '[{"symbol":"AAPL","entry_date":"2026-04-17","stop_loss_hit":true}]',
        encoding="utf-8",
    )
    (dual / "execution_decision_summary.json").write_text(
        '{"engine_open_position_count":9,"adapter_position_count":0,'
        '"open_risk_fraction_daily":0.1125,"daily_max_total_risk_cap":0.10,'
        '"n_signals_eligible":4,"n_signals_blocked":4,"n_execution_attempts":0,'
        '"primary_execution_blocker":"exposure_limit_reached"}',
        encoding="utf-8",
    )
    (dual / "live_summary_latest.json").write_text(
        '{"execution_adapter":"ExecutionDisabledAdapter","dry_run":true}',
        encoding="utf-8",
    )
    (dual / "execution_order_events.csv").write_text(
        "symbol,status,reason,accepted\nAAPL,rejected,stop_loss_hit,false\n",
        encoding="utf-8",
    )


def _patch(monkeypatch, root: Path, tmp_path: Path) -> None:
    monkeypatch.setattr(ei, "TRADING_PROJECT_ROOT", root)
    monkeypatch.setattr(ec, "CLEANUP_REPORT_DIR", tmp_path / "execution_cleanup")
    monkeypatch.setattr(ec, "_LAST_PREVIEW", None)
    monkeypatch.setattr(ei, "_LAST_AUDIT", None)


def test_p1_simulation_does_not_claim_broker_accepted(monkeypatch, tmp_path):
    root = tmp_path / "trading"
    _fixture(root)
    _patch(monkeypatch, root, tmp_path)
    text = ec.simulate_execution_cleanup_patch()
    assert "close_order_paper_only" in text
    assert "NOT broker accepted" in text or "not broker" in text.lower()


def test_risk_drops_after_simulated_cleanup(monkeypatch, tmp_path):
    root = tmp_path / "trading"
    _fixture(root)
    _patch(monkeypatch, root, tmp_path)
    preview = ec._build_preview()
    assert preview.risk_after_simulated <= preview.risk_before
    assert preview.open_risk_fraction_daily_after <= preview.open_risk_fraction_daily_before


def test_primary_blocker_prefers_exposure_over_scan_noise(monkeypatch, tmp_path):
    root = tmp_path / "trading"
    _fixture(root)
    _patch(monkeypatch, root, tmp_path)
    preview = ec._build_preview()
    assert "exposure" in preview.primary_execution_blocker.lower()


def test_read_only_no_trading_files_mutated(monkeypatch, tmp_path):
    root = tmp_path / "trading"
    _fixture(root)
    _patch(monkeypatch, root, tmp_path)
    before = {p: p.read_text(encoding="utf-8") for p in root.rglob("*") if p.is_file()}
    ec.generate_execution_cleanup_report()
    after = {p: p.read_text(encoding="utf-8") for p in root.rglob("*") if p.is_file()}
    assert before == after
