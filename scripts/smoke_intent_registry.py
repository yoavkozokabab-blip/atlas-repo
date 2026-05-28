"""Direct smoke for intent registry fix and Phase 46 execution commands."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    import brain.english_voice_phrases  # noqa: F401
    import brain.intent_classifier  # noqa: F401
    from actions.registry import ActionRegistry
    from brain.intent_classifier import classify_rules
    from core.intent_validation import format_validation_report, validate_intent_registry_consistency
    from core.types import CommandRequest, Intent
    import investigation.execution_investigation as ei

    issues = validate_intent_registry_consistency()
    print(format_validation_report(issues))
    if issues:
        raise SystemExit(1)

    classifier_phrases = {
        "run historical validation sweep": Intent.RUN_HISTORICAL_VALIDATION_SWEEP,
        "audit execution path": Intent.AUDIT_EXECUTION_PATH,
        "explain zero execution attempts": Intent.EXPLAIN_ZERO_EXECUTION_ATTEMPTS,
        "show execution blockers": Intent.SHOW_EXECUTION_BLOCKERS,
        "inspect execution adapter": Intent.INSPECT_EXECUTION_ADAPTER,
    }
    for phrase, intent in classifier_phrases.items():
        got = classify_rules(phrase)
        assert got.intent == intent, (phrase, got.intent, intent)
        print(f"OK classify {phrase} -> {intent.value}")

    root = Path(tempfile.mkdtemp()) / "trading"
    dual = root / "reports" / "live_paper" / "dual"
    dual.mkdir(parents=True)
    (dual / "execution_decision_summary.json").write_text(
        '{"n_new_signals": 5, "n_execution_attempts": 0, "n_execution_accepted": 0, '
        '"reason_if_no_attempt": "not_relevant_to_last_bar", "execution_adapter": "ExecutionDisabledAdapter"}',
        encoding="utf-8",
    )
    (dual / "live_summary_latest.json").write_text(
        '{"execution_adapter": "ExecutionDisabledAdapter", "dry_run": true}',
        encoding="utf-8",
    )
    report_dir = Path(tempfile.mkdtemp()) / "execution"
    ei.TRADING_PROJECT_ROOT = root
    ei.EXECUTION_REPORT_DIR = report_dir
    ei._LAST_AUDIT = None

    action_phrases = [
        "audit execution path",
        "explain zero execution attempts",
        "show execution blockers",
        "inspect execution adapter",
    ]
    registry = ActionRegistry()
    for cmd in action_phrases:
        intent = classify_rules(cmd).intent
        result = registry._actions[intent.value].execute(CommandRequest(raw_text=cmd, intent=intent))
        assert result.status.name == "SUCCESS", (cmd, result.status, result.message)
        assert result.data.get("read_only") is True, cmd
        print(f"OK action {cmd}")

    print("SMOKE PASS")


if __name__ == "__main__":
    main()
