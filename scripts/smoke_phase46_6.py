"""Direct smoke test for Phase 46.6 execution flow commands."""

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
import investigation.execution_flow as ef


def main() -> None:
    root = Path(tempfile.mkdtemp()) / "trading"
    dual = root / "reports" / "live_paper" / "dual"
    dual.mkdir(parents=True)
    (dual / "execution_decision_summary.json").write_text(
        """
        {
          "n_new_signals": 4,
          "n_signals_eligible": 4,
          "n_signals_blocked": 4,
          "n_execution_attempts": 0,
          "n_execution_accepted": 0,
          "signal_detection_mode": "last_closed_bar",
          "reason_if_no_attempt": "not_relevant_to_last_bar",
          "entry_blocks": {"overlap": 2, "max_open": 1, "duplicate": 1},
          "kill_switch_enabled": true
        }
        """.strip(),
        encoding="utf-8",
    )
    (dual / "live_summary_latest.json").write_text(
        '{"execution_adapter": "ExecutionDisabledAdapter", "dry_run": true, "kill_switch_enabled": true}',
        encoding="utf-8",
    )
    (dual / "live_signals.csv").write_text(
        "symbol,timestamp,signal,side\n"
        "AAPL,2026-05-04T15:30:00+00:00,1,long\n"
        "MSFT,2026-05-04T15:30:00+00:00,1,long\n",
        encoding="utf-8",
    )
    (dual / "execution_order_events.csv").write_text(
        "symbol,adapter,status,reason,accepted,dry_run\n"
        "AAPL,ExecutionDisabledAdapter,rejected,overlap,false,true\n",
        encoding="utf-8",
    )
    report_dir = Path(tempfile.mkdtemp()) / "execution_flow"
    import investigation.execution_investigation as ei

    ei.TRADING_PROJECT_ROOT = root
    ei.EXECUTION_REPORT_DIR = Path(tempfile.mkdtemp()) / "execution"
    ei._LAST_AUDIT = None
    ef.FLOW_REPORT_DIR = report_dir
    ef._LAST_FLOW = None

    commands = [
        "trace signal to execution AAPL",
        "trace blocked signal AAPL",
        "explain top execution blocker",
        "reconstruct execution flow",
        "show signal lifecycle timeline",
        "rank dead signal causes",
        "simulate unblock scenario",
        "propose execution fix",
        "generate execution flow report",
    ]
    registry = ActionRegistry()
    for cmd in commands:
        intent = classify_rules(cmd).intent
        action = registry._actions[intent.value]
        result = action.execute(CommandRequest(raw_text=cmd, intent=intent))
        assert result.status.name == "SUCCESS", (cmd, result.status, result.message)
        assert result.data.get("read_only") is True, cmd
        print(f"OK {cmd} -> {intent.value}")

    text = ef.trace_blocked_signal("AAPL")
    assert "Blocked signal trace" in text
    assert "AAPL" in text
    report_files = list(report_dir.glob("*_execution_flow.json"))
    assert report_files, "expected execution flow report"
    print("SMOKE PASS")


if __name__ == "__main__":
    main()
