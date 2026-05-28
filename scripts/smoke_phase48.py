"""Direct smoke test for Phase 48 patch apply pipeline."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from actions.registry import ActionRegistry
from brain.intent_classifier import classify_rules
from core.types import ActionStatus, CommandRequest, Intent
import investigation.execution_cleanup as ec
import investigation.execution_investigation as ei
import investigation.patch_apply as pa


def _fixture(root: Path) -> None:
    state = root / "reports" / "live_paper" / "dual" / "state"
    dual = state.parent
    state.mkdir(parents=True)
    (state / "open_positions.json").write_text(
        '[{"symbol":"AAPL","stop_loss_hit":true},{"symbol":"MSFT","stop_loss_hit":true}]',
        encoding="utf-8",
    )
    (dual / "execution_decision_summary.json").write_text(
        '{"execution_mode":"paper","open_risk_fraction_daily":0.1125,"reason_if_no_attempt":"not_relevant_to_last_bar"}',
        encoding="utf-8",
    )
    (dual / "live_summary_latest.json").write_text(
        '{"execution_adapter":"ExecutionDisabledAdapter","execution_mode":"paper","dry_run":true}',
        encoding="utf-8",
    )
    services = root / "services"
    services.mkdir(parents=True)
    (services / "live_paper_engine.py").write_text("# paper engine\n", encoding="utf-8")
    (services / "live_dual_paper_cycle.py").write_text("# dual cycle\n", encoding="utf-8")


def main() -> None:
    import config

    root = Path(tempfile.mkdtemp()) / "trading"
    _fixture(root)
    backup_root = Path(tempfile.mkdtemp()) / "backups"
    report_dir = Path(tempfile.mkdtemp()) / "patch_apply"
    config.TRADING_PROJECT_ROOT = root
    ei.TRADING_PROJECT_ROOT = root
    pa.BACKUP_ROOT = backup_root
    pa.APPLY_REPORT_DIR = report_dir
    pa.STATE_PATH = Path(tempfile.mkdtemp()) / "patch_apply_state.json"
    pa.HISTORY_PATH = report_dir / "history.jsonl"
    ec._LAST_PREVIEW = None

    registry = ActionRegistry()
    steps = [
        ("validate patch safety", False),
        ("show approved patch", False),
        ("apply approved patch confirm", True),
        ("replay after patch", False),
        ("compare pre post patch", False),
        ("rollback last patch confirm", True),
    ]
    for cmd, need_confirm in steps:
        intent = classify_rules(cmd).intent
        action = registry._actions[intent.value]
        request = CommandRequest(
            raw_text=cmd,
            intent=intent,
            confirmed="confirm" in cmd,
        )
        result = action.execute(request)
        if need_confirm and result.status == ActionStatus.CONFIRMATION_REQUIRED:
            result = action.execute(
                CommandRequest(raw_text=cmd, intent=intent, confirmed=True)
            )
        assert result.status == ActionStatus.SUCCESS, (cmd, result.status, result.summary)
        print(f"OK {cmd} -> {intent.value}")

    blocked = pa.validate_scope_path("algo_scanner/strategy/real_algo.py")
    assert "REFUSE" in blocked
    assert backup_root.exists()
    print("SMOKE PASS")


if __name__ == "__main__":
    main()
