"""Phase 46.5 execution investigation tests."""

from __future__ import annotations

from pathlib import Path

from actions.registry import ActionRegistry
from brain.intent_classifier import classify_rules
from core.types import CommandRequest, Intent


def _fixture(root: Path) -> None:
    dual = root / "reports" / "live_paper" / "dual"
    dual.mkdir(parents=True)
    (dual / "execution_decision_summary.json").write_text(
        """
        {
          "n_new_signals": 5,
          "n_execution_attempts": 0,
          "n_execution_accepted": 0,
          "signal_detection_mode": "last_closed_bar",
          "reason_if_no_attempt": "not_relevant_to_last_bar",
          "entry_blocks": {"duplicate": 2, "max_open": 1}
        }
        """.strip(),
        encoding="utf-8",
    )
    (dual / "live_summary_latest.json").write_text(
        """
        {
          "execution_mode": "alpaca",
          "execution_adapter": "ExecutionDisabledAdapter",
          "dry_run": true,
          "n_new_signals": 5
        }
        """.strip(),
        encoding="utf-8",
    )
    (dual / "execution_order_events.csv").write_text(
        "timestamp,symbol,event_type,adapter,status,reason,accepted,dry_run\n"
        "2026-05-04T15:36:55+00:00,BRK-B,close_position,ExecutionDisabledAdapter,rejected,stop_loss_hit,false,true\n"
        "2026-05-04T15:36:55+00:00,AAPL,entry_attempt,ExecutionDisabledAdapter,rejected,adapter_disabled,false,true\n",
        encoding="utf-8",
    )
    (dual / "live_signals.csv").write_text(
        "symbol,timestamp,signal,side\nAAPL,2026-05-04T15:30:00+00:00,1,long\n",
        encoding="utf-8",
    )


def _patch(monkeypatch, root: Path, tmp_path: Path) -> None:
    import investigation.execution_investigation as ei

    monkeypatch.setattr(ei, "TRADING_PROJECT_ROOT", root)
    monkeypatch.setattr(ei, "EXECUTION_REPORT_DIR", tmp_path / "execution")
    monkeypatch.setattr(ei, "_LAST_AUDIT", None)


def test_execution_commands_registered(monkeypatch, tmp_path):
    root = tmp_path / "trading"
    _fixture(root)
    _patch(monkeypatch, root, tmp_path)
    expected = {
        "audit execution path": Intent.AUDIT_EXECUTION_PATH,
        "explain zero execution attempts": Intent.EXPLAIN_ZERO_EXECUTION_ATTEMPTS,
        "trace signal to order AAPL": Intent.TRACE_SIGNAL_TO_ORDER,
        "show execution blockers": Intent.SHOW_EXECUTION_BLOCKERS,
        "rank execution block reasons": Intent.RANK_EXECUTION_BLOCK_REASONS,
        "inspect execution adapter": Intent.INSPECT_EXECUTION_ADAPTER,
        "compare signal count to order attempts": Intent.COMPARE_SIGNAL_COUNT_TO_ORDER_ATTEMPTS,
        "generate execution investigation report": Intent.GENERATE_EXECUTION_INVESTIGATION_REPORT,
    }
    registry = ActionRegistry()
    for phrase, intent in expected.items():
        assert classify_rules(phrase).intent == intent
        assert intent.value in registry._actions


def test_execution_detects_zero_attempts(monkeypatch, tmp_path):
    import investigation.execution_investigation as ei

    root = tmp_path / "trading"
    _fixture(root)
    _patch(monkeypatch, root, tmp_path)
    text = ei.explain_zero_execution_attempts()
    assert "execution attempts: 0" in text
    assert "ExecutionDisabledAdapter" in text or "execution disabled" in text.lower()
    assert "not relevant to last bar" in text.lower() or "top blocker" in text.lower()


def test_execution_report_saved(monkeypatch, tmp_path):
    import investigation.execution_investigation as ei

    root = tmp_path / "trading"
    _fixture(root)
    _patch(monkeypatch, root, tmp_path)
    text = ei.generate_execution_investigation_report()
    assert "Execution investigation report saved" in text
    assert list((tmp_path / "execution").glob("*_execution_investigation.json"))
    assert list((tmp_path / "execution").glob("*_execution_investigation.md"))


def test_execution_read_only(monkeypatch, tmp_path):
    import investigation.execution_investigation as ei

    root = tmp_path / "trading"
    _fixture(root)
    _patch(monkeypatch, root, tmp_path)
    before = {p: p.read_text(encoding="utf-8") for p in root.rglob("*") if p.is_file()}
    ei.audit_execution_path()
    after = {p: p.read_text(encoding="utf-8") for p in root.rglob("*") if p.is_file()}
    assert before == after


def test_execution_action_read_only(monkeypatch, tmp_path):
    root = tmp_path / "trading"
    _fixture(root)
    _patch(monkeypatch, root, tmp_path)
    registry = ActionRegistry()
    result = registry._actions[Intent.AUDIT_EXECUTION_PATH.value].execute(
        CommandRequest(raw_text="audit execution path", intent=Intent.AUDIT_EXECUTION_PATH)
    )
    assert result.data["read_only"] is True
