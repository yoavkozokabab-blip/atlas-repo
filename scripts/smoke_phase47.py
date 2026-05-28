"""Direct smoke test for Phase 47 execution cleanup patch preview."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from actions.registry import ActionRegistry
from brain.intent_classifier import classify_rules
from core.types import CommandRequest
import investigation.execution_cleanup as ec
import investigation.execution_investigation as ei


def main() -> None:
    root = Path(tempfile.mkdtemp()) / "trading"
    state = root / "reports" / "live_paper" / "dual" / "state"
    dual = state.parent
    state.mkdir(parents=True)
    (state / "open_positions.json").write_text(
        """
        [
          {"symbol": "AAPL", "entry_date": "2026-04-17", "stop_loss_hit": true, "risk_fraction": 0.0125},
          {"symbol": "MSFT", "entry_date": "2026-04-17", "stop_loss_hit": true, "risk_fraction": 0.0125}
        ]
        """.strip(),
        encoding="utf-8",
    )
    (dual / "execution_decision_summary.json").write_text(
        """
        {
          "n_new_signals": 4,
          "n_signals_eligible": 4,
          "n_signals_blocked": 4,
          "n_execution_attempts": 0,
          "engine_open_position_count": 9,
          "adapter_position_count": 0,
          "open_risk_fraction_daily": 0.1125,
          "daily_max_total_risk_cap": 0.10,
          "kill_switch_enabled": true,
          "primary_execution_blocker": "exposure_limit_reached",
          "reason_if_no_attempt": "not_relevant_to_last_bar",
          "max_total_risk_engine": true
        }
        """.strip(),
        encoding="utf-8",
    )
    (dual / "live_summary_latest.json").write_text(
        '{"execution_adapter": "ExecutionDisabledAdapter", "dry_run": true, "ALPACA_API_KEY": "", "ALPACA_SECRET_KEY": ""}',
        encoding="utf-8",
    )
    (dual / "execution_order_events.csv").write_text(
        "symbol,event_type,adapter,status,reason,accepted\n"
        "AAPL,close_position,ExecutionDisabledAdapter,rejected,stop_loss_hit,false\n"
        "AAPL,close_position,ExecutionDisabledAdapter,rejected,close_order_rejected,false\n",
        encoding="utf-8",
    )
    report_dir = Path(tempfile.mkdtemp()) / "execution_cleanup"
    ei.TRADING_PROJECT_ROOT = root
    ei.EXECUTION_REPORT_DIR = Path(tempfile.mkdtemp()) / "execution"
    ei._LAST_AUDIT = None
    ec.CLEANUP_REPORT_DIR = report_dir
    ec._LAST_PREVIEW = None

    commands = [
        "simulate execution cleanup patch",
        "compare risk before after cleanup",
        "show stale open positions",
        "propose execution cleanup patch",
        "generate execution cleanup report",
    ]
    registry = ActionRegistry()
    for cmd in commands:
        intent = classify_rules(cmd).intent
        action = registry._actions[intent.value]
        result = action.execute(CommandRequest(raw_text=cmd, intent=intent))
        assert result.status.name == "SUCCESS", (cmd, result.status, result.message)
        assert result.data.get("read_only") is True, cmd
        print(f"OK {cmd} -> {intent.value}")

    text = ec.simulate_execution_cleanup_patch()
    assert "preview-only" in text.lower()
    assert "close_order_paper_only" in text
    assert list(report_dir.glob("*_execution_cleanup.json"))
    print("SMOKE PASS")


if __name__ == "__main__":
    main()
