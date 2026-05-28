"""Phase 48 patch apply tests (safe unit scope)."""

from __future__ import annotations

from pathlib import Path

import investigation.execution_cleanup as ec
import investigation.execution_investigation as ei
import investigation.patch_apply as pa


def _fixture(root: Path) -> None:
    state = root / "reports" / "live_paper" / "dual" / "state"
    dual = state.parent
    state.mkdir(parents=True)
    (state / "open_positions.json").write_text(
        '[{"symbol":"AAPL","stop_loss_hit":true}]',
        encoding="utf-8",
    )
    (dual / "execution_decision_summary.json").write_text(
        '{"execution_mode":"paper","open_risk_fraction_daily":0.1125}',
        encoding="utf-8",
    )
    (dual / "live_summary_latest.json").write_text(
        '{"execution_adapter":"ExecutionDisabledAdapter","execution_mode":"paper"}',
        encoding="utf-8",
    )


def _patch(monkeypatch, root: Path, tmp_path: Path) -> None:
    monkeypatch.setattr("config.TRADING_PROJECT_ROOT", root)
    monkeypatch.setattr(ei, "TRADING_PROJECT_ROOT", root)
    monkeypatch.setattr(pa, "BACKUP_ROOT", tmp_path / "backups")
    monkeypatch.setattr(pa, "APPLY_REPORT_DIR", tmp_path / "patch_apply")
    monkeypatch.setattr(pa, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(pa, "HISTORY_PATH", tmp_path / "patch_apply" / "history.jsonl")
    monkeypatch.setattr(ec, "_LAST_PREVIEW", None)
    if pa.STATE_PATH.exists():
        pa.STATE_PATH.unlink()


def test_blocked_scope_rejected(monkeypatch, tmp_path):
    root = tmp_path / "trading"
    _fixture(root)
    _patch(monkeypatch, root, tmp_path)
    msg = pa.validate_scope_path("algo_scanner/strategy/real_algo.py")
    assert "REFUSE" in msg


def test_apply_requires_validation_and_confirm(monkeypatch, tmp_path):
    root = tmp_path / "trading"
    _fixture(root)
    _patch(monkeypatch, root, tmp_path)
    assert "refused" in pa.apply_approved_patch(confirmed=False).lower()
    pa.validate_patch_safety()
    text = pa.apply_approved_patch(confirmed=True)
    assert "Patch apply completed" in text
    assert "broker orders: NOT sent" in text


def test_backup_and_rollback(monkeypatch, tmp_path):
    root = tmp_path / "trading"
    _fixture(root)
    _patch(monkeypatch, root, tmp_path)
    pa.validate_patch_safety()
    pa.apply_approved_patch(confirmed=True)
    state = pa._load_state()
    assert state.last_backup_id
    assert (pa.BACKUP_ROOT / state.last_backup_id).exists()
    result = pa.rollback_last_patch(confirmed=True)
    assert "ROLLBACK SUCCESS" in result


def test_no_strategy_file_mutation(monkeypatch, tmp_path):
    root = tmp_path / "trading"
    _fixture(root)
    strategy = root / "algo_scanner" / "strategy" / "real_algo.py"
    strategy.parent.mkdir(parents=True)
    strategy.write_text("# strategy\n", encoding="utf-8")
    before = strategy.read_text(encoding="utf-8")
    _patch(monkeypatch, root, tmp_path)
    pa.validate_patch_safety()
    pa.apply_approved_patch(confirmed=True)
    assert strategy.read_text(encoding="utf-8") == before
