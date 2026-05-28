"""Phase 46.4 price integrity tests."""

from __future__ import annotations

from pathlib import Path

from actions.registry import ActionRegistry
from brain.intent_classifier import classify_rules
from core.types import CommandRequest, Intent


def _fixture(root: Path) -> None:
    (root / "reports" / "live_paper" / "dual").mkdir(parents=True)
    (root / "reports" / "backtests").mkdir(parents=True)
    (root / "cache" / "yahoo").mkdir(parents=True)
    (root / "reports" / "live_paper" / "dual" / "live.txt").write_text(
        "AAPL 2026-01-01T09:30:00 live_close=137.0 open=136 high=138 low=135 close=137 selected_bar_timestamp=2026-01-01T09:30:00",
        encoding="utf-8",
    )
    (root / "reports" / "backtests" / "backtest.txt").write_text(
        "AAPL 2026-01-01T09:30:00 backtest_close=136.5 open=136 high=137 low=135 close=136.5",
        encoding="utf-8",
    )
    (root / "cache" / "yahoo" / "AAPL.json").write_text(
        '{"symbol":"AAPL","timestamp":"2026-01-01T09:30:00","adj_close":136.4,"close":137.0}',
        encoding="utf-8",
    )


def _patch(monkeypatch, root: Path, tmp_path: Path) -> None:
    import investigation.price_integrity as pi

    monkeypatch.setattr(pi, "TRADING_PROJECT_ROOT", root)
    monkeypatch.setattr(pi, "PRICE_REPORT_DIR", tmp_path / "price_integrity")
    monkeypatch.setattr(pi, "_LAST_AUDIT", None)


def test_price_integrity_commands_registered(monkeypatch, tmp_path):
    root = tmp_path / "trading"
    _fixture(root)
    _patch(monkeypatch, root, tmp_path)
    expected = {
        "audit price integrity": Intent.AUDIT_PRICE_INTEGRITY,
        "compare candle sources": Intent.COMPARE_CANDLE_SOURCES,
        "trace price source AAPL": Intent.TRACE_PRICE_SOURCE,
        "find close price mismatches": Intent.FIND_CLOSE_PRICE_MISMATCHES,
        "inspect data cache drift": Intent.INSPECT_DATA_CACHE_DRIFT,
        "check timestamp alignment": Intent.CHECK_TIMESTAMP_ALIGNMENT,
        "check adjusted price usage": Intent.CHECK_ADJUSTED_PRICE_USAGE,
        "check duplicate bars": Intent.CHECK_DUPLICATE_BARS,
        "generate price integrity report": Intent.GENERATE_PRICE_INTEGRITY_REPORT,
    }
    registry = ActionRegistry()
    for phrase, intent in expected.items():
        assert classify_rules(phrase).intent == intent
        assert intent.value in registry._actions


def test_price_integrity_detects_mismatch(monkeypatch, tmp_path):
    import investigation.price_integrity as pi

    root = tmp_path / "trading"
    _fixture(root)
    _patch(monkeypatch, root, tmp_path)
    text = pi.find_close_price_mismatches()
    assert "AAPL" in text
    assert "delta=" in text
    assert "evidence path:" in text


def test_price_integrity_report_saved(monkeypatch, tmp_path):
    import investigation.price_integrity as pi

    root = tmp_path / "trading"
    _fixture(root)
    _patch(monkeypatch, root, tmp_path)
    text = pi.generate_price_integrity_report()
    assert "Price integrity report saved" in text
    assert list((tmp_path / "price_integrity").glob("*_price_integrity.json"))
    assert list((tmp_path / "price_integrity").glob("*_price_integrity.md"))


def test_price_integrity_read_only(monkeypatch, tmp_path):
    import investigation.price_integrity as pi

    root = tmp_path / "trading"
    _fixture(root)
    _patch(monkeypatch, root, tmp_path)
    before = {p: p.read_text(encoding="utf-8") for p in root.rglob("*") if p.is_file()}
    pi.audit_price_integrity()
    after = {p: p.read_text(encoding="utf-8") for p in root.rglob("*") if p.is_file()}
    assert before == after


def test_price_integrity_action_read_only(monkeypatch, tmp_path):
    root = tmp_path / "trading"
    _fixture(root)
    _patch(monkeypatch, root, tmp_path)
    registry = ActionRegistry()
    result = registry._actions[Intent.AUDIT_PRICE_INTEGRITY.value].execute(
        CommandRequest(raw_text="audit price integrity", intent=Intent.AUDIT_PRICE_INTEGRITY)
    )
    assert result.data["read_only"] is True
