"""Trading log intelligence tests."""

from pathlib import Path

from actions.trading_logs import ShowRejectionReasonsAction, SummarizeLatestLogAction
from actions.log_utils import latest_log_file
from core.types import CommandRequest, Intent


def test_latest_log_selection(tmp_path: Path, monkeypatch):
    logs = tmp_path / "reports" / "live_paper" / "scheduled_logs"
    logs.mkdir(parents=True)
    old = logs / "old.log"
    new = logs / "new.log"
    old.write_text("ok\n", encoding="utf-8")
    new.write_text("ERROR something failed\nrejected trade\n", encoding="utf-8")

    monkeypatch.setattr("actions.log_utils.TRADING_REPORTS_ROOT", tmp_path / "reports" / "live_paper")
    monkeypatch.setattr("actions.log_utils.TRADING_REPORTS_DUAL", tmp_path / "reports" / "live_paper" / "dual")
    monkeypatch.setattr("actions.log_utils.TRADING_REPORTS_LOGS", logs)

    latest = latest_log_file()
    assert latest is not None
    assert latest.name == "new.log"


def test_rejection_reason_aggregation(tmp_path: Path, monkeypatch):
    logs = tmp_path / "reports" / "live_paper" / "scheduled_logs"
    logs.mkdir(parents=True)
    (logs / "run.log").write_text(
        "entry_trigger_not_hit for AAPL\n"
        "entry_trigger_not_hit for MSFT\n"
        "risk_check_failed\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("actions.log_utils.TRADING_REPORTS_ROOT", tmp_path / "reports" / "live_paper")
    monkeypatch.setattr("actions.log_utils.TRADING_REPORTS_DUAL", tmp_path / "reports" / "live_paper" / "dual")
    monkeypatch.setattr("actions.log_utils.TRADING_REPORTS_LOGS", logs)

    action = ShowRejectionReasonsAction()
    req = CommandRequest(raw_text="reasons", intent=Intent.SHOW_REJECTION_REASONS)
    result = action.execute(req)
    assert result.status.value == "success"
    assert "entry_trigger_not_hit" in result.summary


def test_summarize_latest_log(tmp_path: Path, monkeypatch):
    logs = tmp_path / "reports" / "live_paper" / "scheduled_logs"
    logs.mkdir(parents=True)
    (logs / "a.log").write_text("WARNING x\nERROR bad\n", encoding="utf-8")
    monkeypatch.setattr("actions.log_utils.TRADING_REPORTS_ROOT", tmp_path / "reports" / "live_paper")
    monkeypatch.setattr("actions.log_utils.TRADING_REPORTS_DUAL", tmp_path / "reports" / "live_paper" / "dual")
    monkeypatch.setattr("actions.log_utils.TRADING_REPORTS_LOGS", logs)

    action = SummarizeLatestLogAction()
    req = CommandRequest(raw_text="summarize", intent=Intent.SUMMARIZE_LATEST_LOG)
    result = action.execute(req)
    assert result.status.value == "success"
    assert "Error-like lines" in result.summary
