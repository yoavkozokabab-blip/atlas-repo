"""User-facing replay report helpers."""

from __future__ import annotations

from investigation.causality_trace import format_causality_graph
from investigation.fixture_builder import format_fixture_report
from investigation.hypothesis_verifier import format_verifications, verify_all_hypotheses, verify_hypothesis
from investigation.replay_cache import cache_status
from investigation.replay_diff import diff_live_backtest, format_replay_diff
from investigation.replay_snapshot import format_snapshot_report
from investigation.replay_timeline import format_timeline
from investigation.symbol_replay import (
    replay_latest_signal_report,
    replay_symbol_report,
    trace_execution_lifecycle,
    trace_signal_lifecycle,
)


def replay_symbol_command(symbol: str) -> str:
    return replay_symbol_report(symbol)


def replay_latest_signal_command() -> str:
    return replay_latest_signal_report()


def replay_live_vs_backtest_command(symbol: str) -> str:
    return format_replay_diff(diff_live_backtest(symbol))


def verify_top_hypothesis_command(symbol: str = "AAPL") -> str:
    return format_verifications([verify_hypothesis(symbol=symbol)])


def verify_all_hypotheses_command(symbol: str = "AAPL") -> str:
    return format_verifications(verify_all_hypotheses(symbol=symbol))


def show_replay_timeline_command() -> str:
    return format_timeline()


def show_replay_diff_command(symbol: str = "AAPL") -> str:
    return format_replay_diff(diff_live_backtest(symbol))


def build_verification_fixture_command(symbol: str = "AAPL") -> str:
    return format_fixture_report(symbol)


def export_replay_snapshot_command(symbol: str = "AAPL") -> str:
    return format_snapshot_report(symbol)


def trace_signal_lifecycle_command(symbol: str = "AAPL") -> str:
    return trace_signal_lifecycle(symbol)


def trace_execution_lifecycle_command(symbol: str = "AAPL") -> str:
    return trace_execution_lifecycle(symbol)


def show_causality_graph_command(symbol: str = "AAPL") -> str:
    return format_causality_graph(symbol)


def investigation_confidence_report_command(symbol: str = "AAPL") -> str:
    return "\n\n".join(
        [
            "Investigation confidence report",
            verify_all_hypotheses_command(symbol),
            cache_status(),
            "Confidence upgrades require replay confirmation + deterministic hash match.",
        ]
    )
