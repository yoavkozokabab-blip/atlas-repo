"""Direct smoke test for Phase 46.5 execution investigation commands."""

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
import investigation.execution_investigation as ei


def main() -> None:
    root = Path(tempfile.mkdtemp()) / "trading"
    dual = root / "reports" / "live_paper" / "dual"
    dual.mkdir(parents=True)
    (dual / "execution_decision_summary.json").write_text(
        '{"n_new_signals": 5, "n_execution_attempts": 0, "n_execution_accepted": 0, '
        '"reason_if_no_attempt": "not_relevant_to_last_bar"}',
        encoding="utf-8",
    )
    (dual / "live_summary_latest.json").write_text(
        '{"execution_adapter": "ExecutionDisabledAdapter", "dry_run": true}',
        encoding="utf-8",
    )
    (dual / "execution_order_events.csv").write_text(
        "symbol,adapter,status,reason\n"
        "AAPL,ExecutionDisabledAdapter,rejected,adapter_disabled\n",
        encoding="utf-8",
    )
    report_dir = Path(tempfile.mkdtemp()) / "execution"
    ei.TRADING_PROJECT_ROOT = root
    ei.EXECUTION_REPORT_DIR = report_dir
    ei._LAST_AUDIT = None

    commands = [
        "audit execution path",
        "explain zero execution attempts",
        "trace signal to order AAPL",
        "show execution blockers",
        "rank execution block reasons",
        "inspect execution adapter",
        "compare signal count to order attempts",
        "generate execution investigation report",
    ]
    registry = ActionRegistry()
    for cmd in commands:
        intent = classify_rules(cmd).intent
        action = registry._actions[intent.value]
        result = action.execute(CommandRequest(raw_text=cmd, intent=intent))
        assert result.status.name == "SUCCESS", (cmd, result.status, result.message)
        assert result.data.get("read_only") is True, cmd
        print(f"OK {cmd} -> {intent.value}")
    print("SMOKE PASS")


if __name__ == "__main__":
    main()
