"""
Live paper orchestration: same `_trades_for_symbol` engine as validation/paper, last closed bar only.

No strategy logic changes — slicing OHLCV, dedup, and mapping to state only.
"""

from __future__ import annotations

import logging
import os
import time
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import json
import numpy as np

from algo_scanner.config import AppConfig
from run_paper_trading import PAPER_STRESS, paper_stress_trade
from run_train_test_validation import fetch_ohlcv_range_with_meta, min_bars_required
from services.live_paper_state import (
    LivePaperState,
    alert_dedup_key,
    atomic_write_json,
    atomic_write_text,
    append_jsonl_row,
    append_csv_row,
    ensure_execution_order_events_files,
    get_atomic_write_stats,
    reset_atomic_write_stats,
    output_scope_key,
    signal_dedup_key,
    summary_alert_dedup_key,
)
from services.live_reporting import (
    LIVE_REPORT_CSV_FIELDS,
    append_live_report_csv,
    summary_to_pretty_text,
    write_live_report_latest_txt,
    write_open_positions_report_csv,
)
from services.live_run_lock import LiveRunLock
from services.live_signal_engine import _apply_live_mode_relaxed_cfg
from services.live_production_constants import (
    DAILY_INTERVAL,
    DAILY_MAX_OPEN_POSITIONS,
    DAILY_MAX_TOTAL_RISK,
    DAILY_PRESET_NAME,
    DAILY_RISK_PER_TRADE,
    WEEKLY_INTERVAL,
    WEEKLY_MAX_OPEN_POSITIONS,
    WEEKLY_MAX_TOTAL_RISK,
    WEEKLY_PRESET_NAME,
    WEEKLY_RISK_PER_TRADE,
    assert_weekly_algo_config,
    build_weekly_algo_config,
    position_size_shares_floor,
    require_preset_name_matches,
)
from services.paper_trading_constants import (
    PAPER_POSITIONS_JSON,
    PAPER_REGIME_MODE,
    PAPER_TRADING_PRESET_NAME,
    PAPER_UNIVERSE_FILE,
    assert_paper_algo_config,
    build_paper_algo_config,
    load_safety_state,
    maybe_warn_signal_anomalies,
    print_paper_config_banner,
    save_safety_state,
    ensure_universe_file_readable,
    validate_paper_universe_path,
)
from services.paper_trading_log import paper_live_log_event, paper_live_log_line
from services.portfolio_manager import (
    PortfolioConstraints,
    can_allocate_new_position,
    load_portfolio_state,
    paper_simulation_entry_open,
    position_size_shares,
    record_symbol_exit,
    reentry_allowed,
    save_portfolio_state,
    strategy_capacity_positions,
    total_open_risk_fraction,
    write_paper_positions_snapshot,
)
from services.telegram_alerts import stress_config_summary
from services.execution import (
    ExecutionAdapter,
    build_execution_adapter,
)
from services.execution.risk_manager import RiskConfig, size_trade_for_execution
from services.live_exit_price_validation import evaluate_validated_live_exit
from services.live_fill_drift import (
    apply_fill_drift_guard,
    evaluate_fill_drift,
    fill_drift_auto_close_enabled,
    reconcile_entry_fill_drift,
)
from tools.trading_dashboard.backend.control_service import (
    CONTROL_STATE_PATH,
    daily_new_positions_count as control_daily_new_positions_count,
    effective_max_orders_per_run as control_effective_max_orders_per_run,
    evaluate_pre_order_controls,
    load_control_state,
    merged_allowed_symbols,
    record_new_position_for_day,
    risk_config_from_control_state,
    save_control_state,
    trading_day_key,
)
from validation_cli_common import require_universe_file, resolve_universe_path

from services.entry_candidate_ranking import (
    alphabet_bias_audit_summary,
    deterministic_daily_shuffle,
    log_candidate_pipeline,
    log_universe_order_loaded,
    rank_entry_intents,
    scan_order_seed_for_run,
)

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
from services.live_signal_models import LiveSignalCandidate

PAPER_OPEN_POSITIONS_CSV = ROOT / "reports" / "paper_open_positions.csv"
PAPER_CLOSED_TRADES_CSV = ROOT / "reports" / "paper_closed_trades.csv"
PAPER_OPEN_POSITIONS_DETAILED_JSON = ROOT / "reports" / "paper_open_positions_detailed.json"
PAPER_CLOSED_TRADES_DETAILED_JSON = ROOT / "reports" / "paper_closed_trades_detailed.json"


def _build_execution_adapter(execution_mode: str, logger_obj: logging.Logger) -> ExecutionAdapter:
    return build_execution_adapter(execution_mode, logger=logger_obj)


class ExecutionDisabledAdapter(ExecutionAdapter):
    """Non-trading adapter used only when broker preflight fails before scanning."""

    def __init__(self, *, adapter_name: str, reason: str) -> None:
        self.adapter_name = str(adapter_name or "disabled")
        self.reason = str(reason or "execution_disabled")
        self.dry_run = False

    def place_order(self, signal: dict[str, Any]) -> dict[str, Any]:
        _ = signal
        return {
            "accepted": False,
            "adapter": self.adapter_name,
            "event": "place_order_failed",
            "error": self.reason,
        }

    def close_position(self, symbol: str) -> dict[str, Any]:
        _ = symbol
        return {
            "accepted": False,
            "adapter": self.adapter_name,
            "event": "close_order_rejected",
            "error": self.reason,
        }

    def get_positions(self) -> list[dict[str, Any]]:
        return []

    def get_account(self) -> dict[str, Any]:
        return {"adapter": self.adapter_name, "error": self.reason}


def _record_execution_event(execution_events: list[dict[str, Any]] | None, event_type: str, **payload: Any) -> None:
    row = {"event_type": str(event_type), "ts": utc_now_iso(), **payload}
    if execution_events is not None:
        execution_events.append(row)


EXECUTION_ORDER_EVENT_FIELDS = [
    "timestamp",
    "ts",
    "event_type",
    "adapter",
    "symbol",
    "side",
    "engine",
    "interval",
    "position_id",
    "qty",
    "qty_local",
    "qty_broker",
    "order_type",
    "submitted_order_type",
    "submitted_limit_price",
    "submitted_stop_price",
    "intended_entry_price",
    "actual_filled_avg_price",
    "fill_slippage_r",
    "max_slippage_r",
    "submitted_order_payload_json",
    "entry_price",
    "entry",
    "stop",
    "target",
    "risk",
    "risk_per_share",
    "risk_amount",
    "rr",
    "config",
    "preset",
    "signal_date",
    "intended_entry_date",
    "exit_price",
    "current_price",
    "stop_loss",
    "take_profit",
    "gap_through_stop",
    "loss_beyond_stop_reason",
    "bar_timestamp",
    "price_source",
    "price_method",
    "price_timestamp",
    "price_age_seconds",
    "price_stale",
    "quote_bid",
    "quote_ask",
    "quote_mid",
    "quote_spread",
    "quote_spread_pct",
    "current_r",
    "triggered_rule",
    "mfe_r",
    "mae_r",
    "bars_held",
    "days_held",
    "close_state",
    "close_reason",
    "attempt_count",
    "broker_order_id",
    "broker_status",
    "source",
    "managed_by_strategy",
    "status",
    "order_id",
    "alpaca_order_id",
    "reason",
    "error",
    "accepted",
    "dry_run",
    "submitted_at",
    "request_source",
    "raw_response_json",
]


def _execution_event_counts(events: list[dict[str, Any]] | None) -> dict[str, int]:
    rows = [row for row in (events or []) if isinstance(row, dict)]
    return {
        "attempts": sum(1 for row in rows if row.get("event_type") == "place_order_attempt"),
        "accepted": sum(1 for row in rows if row.get("event_type") in ("place_order_success", "place_order_dry_run")),
        "rejected": sum(1 for row in rows if row.get("event_type") in ("place_order_rejected", "place_order_skipped", "order_skipped", "place_order_failed")),
        "success": sum(1 for row in rows if row.get("event_type") == "place_order_success"),
        "failed": sum(1 for row in rows if row.get("event_type") == "place_order_failed"),
        "dry_run": sum(1 for row in rows if row.get("event_type") == "place_order_dry_run"),
        "skipped": sum(1 for row in rows if row.get("event_type") in ("place_order_skipped", "order_skipped")),
    }


def _execution_close_event_counts(events: list[dict[str, Any]] | None) -> dict[str, int]:
    rows = [row for row in (events or []) if isinstance(row, dict)]
    accepted_types = {
        "close_order_success",
        "close_order_submitted",
        "close_order_filled",
        "close_order_dry_run",
        "close_order_already_closed",
    }
    return {
        "attempts": sum(1 for row in rows if row.get("event_type") == "close_order_attempt"),
        "accepted": sum(1 for row in rows if row.get("event_type") in accepted_types),
        "rejected": sum(1 for row in rows if row.get("event_type") == "close_order_rejected"),
        "failed": sum(1 for row in rows if row.get("event_type") == "close_order_failed"),
        "skipped": sum(1 for row in rows if row.get("event_type") in ("close_order_skipped", "close_skipped")),
    }


def _execution_exit_diagnostics(events: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = [row for row in (events or []) if isinstance(row, dict)]
    close_counts = _execution_close_event_counts(rows)
    breached = [row for row in rows if row.get("event_type") == "exit_breach"]
    close_skips = [row for row in rows if row.get("event_type") in ("close_order_skipped", "close_skipped")]
    skip_reasons = Counter(str(row.get("reason") or "unknown") for row in close_skips)
    details: list[dict[str, Any]] = []
    detail_event_types = {
        "exit_breach",
        "close_order_attempt",
        "close_order_submitted",
        "close_order_filled",
        "close_order_success",
        "close_order_rejected",
        "close_order_failed",
        "close_order_already_closed",
        "close_order_retry",
        "close_order_partial",
        "close_order_confirmed",
        "close_order_failed_fatal",
        "close_retry_state_restored",
        "close_skipped",
        "exit_check",
        "engine_exit_condition",
        "reconciled_missing_at_broker",
    }
    for row in rows:
        if row.get("event_type") in detail_event_types:
            details.append(
                {
                    "timestamp": row.get("timestamp") or row.get("ts"),
                    "event_type": row.get("event_type"),
                    "symbol": row.get("symbol"),
                    "position_id": row.get("position_id"),
                    "reason": row.get("reason"),
                    "current_price": row.get("current_price"),
                    "stop_loss": row.get("stop_loss") or row.get("stop"),
                    "take_profit": row.get("take_profit") or row.get("target"),
                    "qty": row.get("qty"),
                    "current_r": row.get("current_r"),
                    "triggered_rule": row.get("triggered_rule"),
                    "mfe_r": row.get("mfe_r"),
                    "mae_r": row.get("mae_r"),
                    "bars_held": row.get("bars_held"),
                    "days_held": row.get("days_held"),
                    "managed_by_strategy": row.get("managed_by_strategy"),
                    "close_state": row.get("close_state"),
                    "status": row.get("status"),
                    "error": row.get("error"),
                    "order_id": row.get("alpaca_order_id") or row.get("order_id"),
                }
            )
    return {
        "positions_checked_for_exit": sum(1 for row in rows if row.get("event_type") == "exit_check"),
        "stop_breaches_detected": sum(1 for row in breached if str(row.get("reason") or "") == "stop_loss_breached"),
        "target_breaches_detected": sum(1 for row in breached if str(row.get("reason") or "") == "take_profit_hit"),
        "close_attempts": close_counts["attempts"],
        "close_accepted": close_counts["accepted"],
        "close_rejected": close_counts["rejected"],
        "close_failed": close_counts["failed"],
        "close_skipped": close_counts["skipped"],
        "skip_reason": str(skip_reasons.most_common(1)[0][0]) if skip_reasons else "",
        "symbols_checked": sorted(
            {
                str(row.get("symbol") or "").strip().upper()
                for row in rows
                if row.get("event_type") == "exit_check" and str(row.get("symbol") or "").strip()
            }
        ),
        "exits_triggered_count": sum(
            1
            for row in rows
            if row.get("event_type") in ("exit_breach", "engine_exit_condition")
        ),
        "per_position": details[-100:],
        "symbol_details": details[-100:],
    }


def _merge_execution_exit_diagnostics(
    summary: dict[str, Any],
    events: list[dict[str, Any]] | None,
    state: LivePaperState | None = None,
) -> dict[str, Any]:
    diag = _execution_exit_diagnostics(events)
    diag["open_positions_count"] = len(state.open_positions) if state is not None else int(summary.get("n_open_positions_after") or 0)
    if state is not None:
        try:
            retry_doc = load_close_retry_queue(state)
            pending = retry_doc.get("pending") if isinstance(retry_doc, dict) else []
            diag["close_retry_queue_count"] = len(pending) if isinstance(pending, list) else 0
            diag["close_retry_queue_path"] = str(state.paths()["close_retry_queue"])
        except Exception:
            diag["close_retry_queue_count"] = None
            diag["close_retry_queue_path"] = ""
    summary["exit_decision_summary"] = diag
    summary["open_positions_count"] = diag["open_positions_count"]
    summary["positions_checked_for_exit"] = diag["positions_checked_for_exit"]
    summary["stop_breaches_detected"] = diag["stop_breaches_detected"]
    summary["target_breaches_detected"] = diag["target_breaches_detected"]
    summary["close_attempts"] = diag["close_attempts"]
    summary["close_accepted"] = diag["close_accepted"]
    summary["close_rejected"] = diag["close_rejected"]
    summary["close_skipped"] = diag["close_skipped"]
    summary["exit_skip_reason"] = diag["skip_reason"]
    summary["symbols_checked_for_exit"] = diag["symbols_checked"]
    summary["exits_triggered_count"] = diag["exits_triggered_count"]
    summary["close_retry_queue_count"] = diag.get("close_retry_queue_count")
    summary["close_retry_queue_path"] = diag.get("close_retry_queue_path")
    return diag


def _normalize_order_block_reason(reason: Any) -> str:
    raw = str(reason or "").strip()
    if not raw:
        return "other:unknown"
    key = raw.lower()
    exact = {
        "already_processed_signal": "overlap_blocked",
        "entry_alert_already_sent": "overlap_blocked",
        "reentry_cooldown_bars": "overlap_blocked",
        "duplicate_symbol_open": "already_in_position",
        "symbol_already_open": "already_in_position",
        "duplicate_symbol_cross_engine": "overlap_blocked",
        "duplicate_symbol_same_engine": "overlap_blocked",
        "max_open_positions": "max_positions_reached",
        "max_new_positions_per_day_reached": "max_positions_reached",
        "max_total_risk": "exposure_limit_reached",
        "max_total_open_risk_exceeded": "exposure_limit_reached",
        "combined_hard_cap_block": "exposure_limit_reached",
        "shares_lte_zero": "risk_check_failed",
        "stop_distance_lte_zero": "risk_check_failed",
        "qty_risk_based_lte_zero": "risk_check_failed",
        "qty_position_cap_lte_zero": "risk_check_failed",
        "qty_lte_zero": "risk_check_failed",
        "market_closed": "market_closed",
        "stale_price_entry_blocked": "stale_price_entry_blocked",
        "price_unavailable_entry_blocked": "price_unavailable_entry_blocked",
        "stale_price_exit_blocked": "stale_price_exit_blocked",
        "price_unavailable_exit_blocked": "price_unavailable_exit_blocked",
    }
    if key in exact:
        return exact[key]
    if "delayed" in key:
        return "delayed_entry_failed"
    if "trigger" in key:
        return "entry_trigger_not_hit"
    if "confirmation" in key or "confirm" in key:
        return "confirmation_failed"
    if "insufficient" in key or "missing" in key or "no_ohlcv" in key:
        return "insufficient_data"
    if "market_closed" in key:
        return "market_closed"
    if "max_open_positions" in key or "max_positions" in key:
        return "max_positions_reached"
    if "exposure" in key or "max_total" in key or "risk_exceeded" in key:
        return "exposure_limit_reached"
    if "duplicate" in key or "already_open" in key or "in_position" in key:
        return "already_in_position"
    if "risk" in key or "qty" in key or "shares" in key or "stop_distance" in key:
        return "risk_check_failed"
    return f"other:{raw}"


def _candidate_rank_value(row: dict[str, Any] | None) -> float | None:
    if not isinstance(row, dict):
        return None
    for key in ("candidate_rank", "rank", "original_signal_rank", "portfolio_rank"):
        value = _coerce_float_or_none(row.get(key))
        if value is not None:
            return float(value)
    return None


def _candidate_score_value(row: dict[str, Any] | None) -> float | None:
    if not isinstance(row, dict):
        return None
    for key in ("candidate_score", "score", "original_signal_score"):
        value = _coerce_float_or_none(row.get(key))
        if value is not None:
            return float(value)
    return None


def _capacity_admission_diagnostics(
    *,
    candidate: dict[str, Any],
    open_positions: list[dict[str, Any]],
    constraints: PortfolioConstraints,
) -> dict[str, Any]:
    managed = strategy_capacity_positions(open_positions)
    candidate_rank = _candidate_rank_value(candidate)
    candidate_score = _candidate_score_value(candidate)
    ranked_positions = [
        p
        for p in managed
        if _candidate_rank_value(p) is not None or _candidate_score_value(p) is not None
    ]
    worst_by_rank = max(ranked_positions, key=lambda p: _candidate_rank_value(p) or float("-inf"), default=None)
    worst_by_score = min(ranked_positions, key=lambda p: _candidate_score_value(p) or float("inf"), default=None)
    worst_rank = _candidate_rank_value(worst_by_rank) if worst_by_rank else None
    worst_score = _candidate_score_value(worst_by_score) if worst_by_score else None
    try:
        rank_gap_min = float(os.getenv("LIVE_REPLACEMENT_MIN_RANK_GAP", "5") or 5.0)
    except ValueError:
        rank_gap_min = 5.0
    try:
        score_gap_min = float(os.getenv("LIVE_REPLACEMENT_MIN_SCORE_GAP", "0") or 0.0)
    except ValueError:
        score_gap_min = 0.0
    replacement_by_rank = (
        candidate_rank is not None
        and worst_rank is not None
        and (float(worst_rank) - float(candidate_rank)) >= rank_gap_min
    )
    replacement_by_score = (
        candidate_score is not None
        and worst_score is not None
        and (float(candidate_score) - float(worst_score)) > score_gap_min
    )
    replacement_candidate = bool(replacement_by_rank or replacement_by_score)
    strategy_risk = total_open_risk_fraction(open_positions, capital=float(constraints.capital), strategy_only=True)
    return {
        "managed_positions_count": len(managed),
        "max_open_positions": int(constraints.max_open_positions),
        "strategy_risk_fraction": strategy_risk,
        "max_total_risk_pct": float(constraints.max_total_risk),
        "risk_per_trade_pct": float(constraints.risk_per_trade),
        "capacity_blocked_candidate_rank": candidate_rank,
        "capacity_blocked_candidate_score": candidate_score,
        "worst_existing_position_rank": worst_rank,
        "worst_existing_position_score": worst_score,
        "worst_existing_position_symbol": str((worst_by_rank or worst_by_score or {}).get("symbol") or "").strip().upper(),
        "replacement_candidate": replacement_candidate,
        "replacement_reason": (
            "rank_gap"
            if replacement_by_rank
            else "score_gap"
            if replacement_by_score
            else "not_significantly_better"
        ),
        "rank_gap_min": rank_gap_min,
        "score_gap_min": score_gap_min,
        "auto_replacement_enabled": str(os.getenv("LIVE_ENABLE_RANKED_REPLACEMENT", "")).strip().lower()
        in {"1", "true", "yes", "on"},
    }


def _execution_block_diagnostics(events: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = [row for row in (events or []) if isinstance(row, dict)]
    reasons = Counter(
        str(row.get("reason") or "other:unknown").strip() or "other:unknown"
        for row in rows
        if row.get("event_type") == "order_skipped"
    )
    return {
        "signals_seen": sum(1 for row in rows if row.get("event_type") == "signal_seen"),
        "signals_blocked": sum(reasons.values()),
        "block_reasons": dict(sorted(reasons.items())),
    }


def _merge_execution_block_diagnostics(summary: dict[str, Any], events: list[dict[str, Any]] | None) -> dict[str, Any]:
    diag = _execution_block_diagnostics(events)
    summary["signals_seen"] = int(diag["signals_seen"])
    summary["signals_blocked"] = int(diag["signals_blocked"])
    summary["block_reasons"] = diag["block_reasons"]
    return diag


def _reason_if_no_execution_attempt(summary: dict[str, Any], events: list[dict[str, Any]] | None) -> str:
    counts = _execution_event_counts(events)
    if counts["attempts"] > 0:
        return ""
    reason_counter: Counter[str] = Counter(
        str(row.get("reason") or "").strip()
        for row in (events or [])
        if isinstance(row, dict) and row.get("event_type") in ("place_order_rejected", "place_order_skipped", "order_skipped", "place_order_failed")
    )
    reason_counter.pop("", None)
    if reason_counter:
        return str(reason_counter.most_common(1)[0][0])
    if bool(summary.get("execution_kill_switch_enabled")):
        return "kill_switch_enabled"
    if int(summary.get("n_symbols_with_signal_on_last_bar") or 0) == 0 and int(summary.get("n_new_signals") or 0) == 0:
        return "zero_valid_last_bar_signals"
    if int(summary.get("n_new_signals") or 0) == 0:
        return "zero_new_signals"
    if int(summary.get("n_new_entries") or 0) == 0:
        return "no_entries_passed_execution_guards"
    return ""


def _build_execution_decision_summary(
    *,
    state: LivePaperState,
    summary: dict[str, Any],
    execution_events: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    funnel_doc = summary.get("live_trade_funnel_debug_doc")
    funnel_doc = funnel_doc if isinstance(funnel_doc, dict) else {}
    last_bar = funnel_doc.get("E_last_bar_and_signals") if isinstance(funnel_doc.get("E_last_bar_and_signals"), dict) else {}
    entry_stage = funnel_doc.get("F_entry_stage") if isinstance(funnel_doc.get("F_entry_stage"), dict) else {}
    counts = _execution_event_counts(execution_events)
    block_diag = _execution_block_diagnostics(execution_events)
    exit_diag = _execution_exit_diagnostics(execution_events)
    return {
        "run_timestamp": str(summary.get("run_timestamp") or ""),
        "signal_detection_mode": str(summary.get("signal_detection_mode_used") or ""),
        "universe_count": int(summary.get("run_debug_total_symbols_seen") or summary.get("n_symbols_attempted") or 0),
        "n_symbols_processed": int(summary.get("n_symbols_processed") or 0),
        "n_new_signals": int(summary.get("n_new_signals") or 0),
        "n_new_entries": int(summary.get("n_new_entries") or 0),
        "stop_loss_triggered_count": int(summary.get("stop_loss_triggered_count") or 0),
        "signals_seen": int(block_diag["signals_seen"]),
        "signals_blocked": int(block_diag["signals_blocked"]),
        "block_reasons": block_diag["block_reasons"],
        "n_execution_attempts": counts["attempts"],
        "n_execution_accepted": counts["accepted"],
        "n_execution_rejected": counts["rejected"],
        "n_execution_success": counts["success"],
        "n_execution_failed": counts["failed"],
        "n_execution_dry_run": counts["dry_run"],
        "n_execution_skipped": counts["skipped"],
        "reason_if_no_attempt": _reason_if_no_execution_attempt(summary, execution_events),
        "open_positions_count": len(state.open_positions),
        "positions_checked_for_exit": int(exit_diag["positions_checked_for_exit"]),
        "stop_breaches_detected": int(exit_diag["stop_breaches_detected"]),
        "target_breaches_detected": int(exit_diag["target_breaches_detected"]),
        "close_attempts": int(exit_diag["close_attempts"]),
        "close_accepted": int(exit_diag["close_accepted"]),
        "close_rejected": int(exit_diag["close_rejected"]),
        "close_skipped": int(exit_diag["close_skipped"]),
        "exit_skip_reason": str(exit_diag["skip_reason"]),
        "symbols_checked": exit_diag["symbols_checked"],
        "exits_triggered_count": int(exit_diag["exits_triggered_count"]),
        "per_position": exit_diag["per_position"],
        "exit_decision_details": exit_diag["symbol_details"],
        "last_bar_relevant_rows": last_bar.get("last_bar_relevant_trade_rows") if isinstance(last_bar, dict) else {},
        "entry_blocks": entry_stage.get("entries_blocked") if isinstance(entry_stage, dict) else {},
        "executed": entry_stage.get("entries_executed") if isinstance(entry_stage, dict) else {},
        "output_dir": str(summary.get("output_dir") or state.output_dir.resolve()),
        "execution_mode": str(summary.get("execution_mode") or ""),
        "alpaca_dry_run": bool(summary.get("execution_alpaca_dry_run", False)),
        "execution_adapter_health_ok": bool(summary.get("execution_adapter_health_ok", True)),
        "execution_degraded": bool(summary.get("execution_degraded", False)),
        "execution_enabled": bool(summary.get("execution_enabled", True)),
        "state_write_ok": bool(summary.get("state_write_ok", True)),
        "fallback_writes_count": int(summary.get("fallback_writes_count", 0) or 0),
        "run_status": str(summary.get("run_status") or ""),
        "historical_entry_log_path": str(state.paths()["live_signals_csv"]),
        "historical_entry_log_is_current": False,
        "runtime_seconds": float(summary.get("runtime_seconds") or 0.0),
    }


def _write_execution_decision_summary(
    *,
    state: LivePaperState,
    summary: dict[str, Any],
    execution_events: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    doc = _build_execution_decision_summary(
        state=state,
        summary=summary,
        execution_events=execution_events,
    )
    atomic_write_json(state.paths()["execution_decision_summary_json"], doc)
    summary["execution_decision_summary_json"] = str(state.paths()["execution_decision_summary_json"].resolve())
    return doc


def _append_execution_order_event(
    state: LivePaperState,
    *,
    event_type: str,
    symbol: str = "",
    side: str | None = None,
    qty: Any = None,
    order_type: Any = None,
    submitted_order_type: Any = None,
    submitted_limit_price: Any = None,
    submitted_stop_price: Any = None,
    intended_entry_price: Any = None,
    actual_filled_avg_price: Any = None,
    fill_slippage_r: Any = None,
    max_slippage_r: Any = None,
    submitted_order_payload: Any = None,
    entry: Any = None,
    stop: Any = None,
    target: Any = None,
    risk: Any = None,
    risk_per_share: Any = None,
    risk_amount: Any = None,
    rr: Any = None,
    config: Any = None,
    preset: Any = None,
    signal_date: Any = None,
    intended_entry_date: Any = None,
    exit_price: Any = None,
    current_price: Any = None,
    stop_loss: Any = None,
    take_profit: Any = None,
    gap_through_stop: Any = None,
    loss_beyond_stop_reason: Any = None,
    bar_timestamp: Any = None,
    price_source: Any = None,
    price_method: Any = None,
    price_timestamp: Any = None,
    price_age_seconds: Any = None,
    price_stale: Any = None,
    quote_bid: Any = None,
    quote_ask: Any = None,
    quote_mid: Any = None,
    quote_spread: Any = None,
    quote_spread_pct: Any = None,
    capacity_blocked_candidate_rank: Any = None,
    worst_existing_position_rank: Any = None,
    replacement_candidate: Any = None,
    managed_positions_count: Any = None,
    max_open_positions: Any = None,
    strategy_risk_fraction: Any = None,
    max_total_risk_pct: Any = None,
    current_r: Any = None,
    triggered_rule: Any = None,
    mfe_r: Any = None,
    mae_r: Any = None,
    bars_held: Any = None,
    days_held: Any = None,
    reason: str | None = None,
    adapter: str | None = None,
    engine: Any = None,
    interval: Any = None,
    position_id: Any = None,
    qty_local: Any = None,
    qty_broker: Any = None,
    close_state: Any = None,
    close_reason: Any = None,
    attempt_count: Any = None,
    broker_order_id: Any = None,
    broker_status: Any = None,
    source: Any = None,
    managed_by_strategy: Any = None,
    result: dict[str, Any] | None = None,
    status: Any = None,
    accepted: bool | None = None,
    dry_run: bool | None = None,
    error: Any = None,
) -> None:
    payload = result or {}
    raw_response = payload.get("raw_response") if isinstance(payload, dict) else None
    if raw_response is None and payload:
        raw_response = payload
    if risk_per_share is None and entry is not None and stop is not None:
        try:
            risk_per_share = abs(float(entry) - float(stop))
        except (TypeError, ValueError):
            risk_per_share = None
    if rr is None and entry is not None and stop is not None and target is not None:
        try:
            risk_den = abs(float(entry) - float(stop))
            if risk_den > 1e-12:
                side_hint = str(side or payload.get("side") or "long").strip().lower()
                rr = ((float(entry) - float(target)) / risk_den) if side_hint in ("short", "sell") else ((float(target) - float(entry)) / risk_den)
        except (TypeError, ValueError):
            rr = None
    if risk_amount is None and risk is not None:
        risk_amount = risk
    if risk_amount is None and risk_per_share is not None and qty is not None:
        try:
            risk_amount = abs(float(risk_per_share)) * abs(float(qty))
        except (TypeError, ValueError):
            risk_amount = None
    if intended_entry_price is None:
        intended_entry_price = payload.get("intended_entry_price") or entry
    if actual_filled_avg_price is None:
        actual_filled_avg_price = payload.get("filled_avg_price") or payload.get("actual_filled_avg_price")
    if fill_slippage_r is None and intended_entry_price is not None and actual_filled_avg_price is not None and risk_per_share is not None:
        try:
            risk_den = abs(float(risk_per_share))
            if risk_den > 1e-12:
                fill_slippage_r = abs(float(actual_filled_avg_price) - float(intended_entry_price)) / risk_den
        except (TypeError, ValueError):
            fill_slippage_r = None
    if submitted_order_payload is None:
        submitted_order_payload = payload.get("request")
    submitted_order_payload_json = (
        json.dumps(submitted_order_payload, default=str, separators=(",", ":"))
        if submitted_order_payload is not None
        else ""
    )
    ts = utc_now_iso()
    row = {
        "timestamp": ts,
        "ts": ts,
        "event_type": str(event_type),
        "adapter": str(adapter or payload.get("adapter") or "").strip(),
        "symbol": str(symbol or "").strip().upper(),
        "side": str(side or payload.get("side") or "").strip().lower(),
        "engine": engine,
        "interval": interval,
        "position_id": position_id,
        "qty": qty if qty is not None else payload.get("qty"),
        "qty_local": qty_local,
        "qty_broker": qty_broker if qty_broker is not None else payload.get("remaining_qty"),
        "order_type": order_type if order_type is not None else payload.get("submitted_order_type") or payload.get("type"),
        "submitted_order_type": submitted_order_type if submitted_order_type is not None else payload.get("submitted_order_type") or payload.get("type"),
        "submitted_limit_price": submitted_limit_price if submitted_limit_price is not None else payload.get("submitted_limit_price"),
        "submitted_stop_price": submitted_stop_price if submitted_stop_price is not None else payload.get("submitted_stop_price"),
        "intended_entry_price": intended_entry_price,
        "actual_filled_avg_price": actual_filled_avg_price,
        "fill_slippage_r": fill_slippage_r,
        "max_slippage_r": max_slippage_r if max_slippage_r is not None else payload.get("max_slippage_r"),
        "submitted_order_payload_json": submitted_order_payload_json,
        "entry_price": entry,
        "entry": entry,
        "stop": stop,
        "target": target,
        "risk": risk,
        "risk_per_share": risk_per_share,
        "risk_amount": risk_amount if risk_amount is not None else risk,
        "rr": rr,
        "config": config,
        "preset": preset,
        "signal_date": signal_date,
        "intended_entry_date": intended_entry_date,
        "exit_price": exit_price,
        "current_price": current_price,
        "stop_loss": stop_loss if stop_loss is not None else stop,
        "take_profit": take_profit if take_profit is not None else target,
        "gap_through_stop": gap_through_stop,
        "loss_beyond_stop_reason": loss_beyond_stop_reason,
        "bar_timestamp": str(bar_timestamp or "").strip(),
        "price_source": price_source,
        "price_method": price_method,
        "price_timestamp": price_timestamp,
        "price_age_seconds": price_age_seconds,
        "price_stale": price_stale,
        "quote_bid": quote_bid,
        "quote_ask": quote_ask,
        "quote_mid": quote_mid,
        "quote_spread": quote_spread,
        "quote_spread_pct": quote_spread_pct,
        "capacity_blocked_candidate_rank": capacity_blocked_candidate_rank,
        "worst_existing_position_rank": worst_existing_position_rank,
        "replacement_candidate": replacement_candidate,
        "managed_positions_count": managed_positions_count,
        "max_open_positions": max_open_positions,
        "strategy_risk_fraction": strategy_risk_fraction,
        "max_total_risk_pct": max_total_risk_pct,
        "current_r": current_r,
        "triggered_rule": triggered_rule,
        "mfe_r": mfe_r,
        "mae_r": mae_r,
        "bars_held": bars_held,
        "days_held": days_held,
        "close_state": close_state,
        "close_reason": close_reason if close_reason is not None else reason,
        "attempt_count": attempt_count,
        "broker_order_id": broker_order_id if broker_order_id is not None else payload.get("broker_order_id"),
        "broker_status": broker_status if broker_status is not None else payload.get("status"),
        "source": source,
        "managed_by_strategy": managed_by_strategy,
        "status": status if status is not None else payload.get("status"),
        "order_id": payload.get("order_id"),
        "alpaca_order_id": payload.get("order_id") or payload.get("broker_order_id"),
        "reason": str(reason or payload.get("error") or payload.get("reason") or payload.get("status") or "").strip(),
        "error": (
            str(error).strip()
            if error is not None
            else (str(payload.get("error") or "").strip() if isinstance(payload, dict) else "")
        ),
        "accepted": payload.get("accepted") if accepted is None else bool(accepted),
        "dry_run": payload.get("dry_run") if dry_run is None else bool(dry_run),
        "submitted_at": payload.get("submitted_at"),
        "request_source": "live_paper_monitor",
        "raw_response_json": json.dumps(raw_response, default=str, separators=(",", ":")) if raw_response is not None else "",
    }
    append_csv_row(
        state.paths()["execution_order_events_csv"],
        row,
        EXECUTION_ORDER_EVENT_FIELDS,
    )
    append_jsonl_row(state.paths()["execution_order_events_jsonl"], row)


def _record_order_skipped_for_signal(
    *,
    state: LivePaperState,
    execution_events: list[dict[str, Any]] | None,
    symbol: str,
    raw_reason: Any,
    adapter: str = "",
    signal_bar_date: str = "",
    combo_label: str = "",
    interval: str = "",
    engine_label: str = "",
    details: dict[str, Any] | None = None,
    event_kwargs: dict[str, Any] | None = None,
) -> str:
    reason = _normalize_order_block_reason(raw_reason)
    payload = {
        "raw_reason": str(raw_reason or "").strip(),
        "signal_bar_date": signal_bar_date,
        "combo_label": combo_label,
        "interval": interval,
        "engine": engine_label,
        "details": details or {},
    }
    _record_execution_event(
        execution_events,
        "order_skipped",
        symbol=symbol,
        adapter=adapter,
        reason=reason,
        raw_reason=payload["raw_reason"],
        signal_bar_date=signal_bar_date,
        combo_label=combo_label,
        interval=interval,
        engine=engine_label,
        details=payload["details"],
    )
    _append_execution_order_event(
        state,
        event_type="order_skipped",
        symbol=symbol,
        adapter=adapter,
        status="skipped",
        reason=reason,
        result=payload,
        accepted=False,
        **(event_kwargs or {}),
    )
    logger.info(
        "[execution_block] event_type=order_skipped symbol=%s reason=%s raw_reason=%s engine=%s combo=%s interval=%s signal_bar_date=%s",
        str(symbol).strip().upper(),
        reason,
        payload["raw_reason"],
        engine_label,
        combo_label,
        interval,
        signal_bar_date,
    )
    return reason


def _reconcile_adapter_positions(
    execution_adapter: ExecutionAdapter,
    open_positions: list[dict[str, Any]],
) -> dict[str, Any]:
    adapter_rows = execution_adapter.get_positions()
    adapter_symbols = {str(r.get("symbol", "")).strip().upper() for r in adapter_rows if str(r.get("symbol", "")).strip()}
    state_symbols = {
        str(r.get("symbol", "")).strip().upper()
        for r in open_positions
        if str(r.get("symbol", "")).strip()
    }
    only_adapter = sorted(adapter_symbols - state_symbols)
    only_state = sorted(state_symbols - adapter_symbols)
    mismatch_count = len(only_adapter) + len(only_state)
    return {
        "adapter_position_count": len(adapter_rows),
        "dashboard_open_position_count": len(open_positions),
        "engine_open_position_count": len(open_positions),
        "mismatch_count": mismatch_count,
        "only_in_adapter": only_adapter[:50],
        "only_in_dashboard": only_state[:50],
    }


def _safe_reconcile_adapter_positions(
    execution_adapter: ExecutionAdapter | None,
    open_positions: list[dict[str, Any]],
) -> dict[str, Any]:
    if execution_adapter is None:
        return {
            "adapter_position_count": 0,
            "dashboard_open_position_count": len(open_positions),
            "engine_open_position_count": len(open_positions),
            "mismatch_count": 0,
            "only_in_adapter": [],
            "only_in_dashboard": [],
            "reconciliation_ok": True,
            "reconciliation_error": "",
        }
    try:
        base = _reconcile_adapter_positions(execution_adapter, open_positions)
        base["reconciliation_ok"] = True
        base["reconciliation_error"] = ""
        return base
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[execution] adapter=%s action=reconcile_failed error=%s: %s",
            type(execution_adapter).__name__,
            type(exc).__name__,
            exc,
        )
        return {
            "adapter_position_count": 0,
            "dashboard_open_position_count": len(open_positions),
            "engine_open_position_count": len(open_positions),
            "mismatch_count": 0,
            "only_in_adapter": [],
            "only_in_dashboard": [],
            "reconciliation_ok": False,
            "reconciliation_error": f"{type(exc).__name__}: {exc}",
        }


def _resolve_position_via_reconcile(
    *,
    state: LivePaperState,
    pos: dict[str, Any],
    execution_adapter: ExecutionAdapter | None,
    execution_events: list[dict[str, Any]] | None,
    source: str,
    triggering_reason: str = "",
    reconciliation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Override any pending/fatal close state when the broker confirms the position is gone.

    Clears retry queue fields, removes fatal retry timers, marks
    ``broker_confirmed_closed`` and emits ``close_resolved_by_reconcile`` (and
    ``retry_queue_item_removed_after_reconcile`` when there was a pending/fatal
    item). Callers are expected to remove ``pos`` from ``state.open_positions``
    and persist the retry queue afterwards.
    """
    sym = str(pos.get("symbol", "")).strip().upper()
    pid = _ensure_position_identity(pos, state=state, execution_events=execution_events, reason="reconcile_resolution")
    adapter_name = type(execution_adapter).__name__ if execution_adapter is not None else ""
    previous_close_state = str(pos.get("close_state") or "").strip().upper()
    previous_close_reason = str(pos.get("close_reason") or "").strip()
    previous_attempt_count = int(pos.get("close_attempt_count", 0) or 0)
    was_pending = previous_close_state in CLOSE_RETRY_PENDING_STATES
    was_fatal = previous_close_state == "CLOSE_FAILED_FATAL"
    had_retry_item = was_pending or was_fatal or bool(str(pos.get("next_retry_at") or "").strip())

    pos["pre_reconcile_close_state"] = previous_close_state
    pos["pre_reconcile_close_reason"] = previous_close_reason
    pos["close_state"] = "CLOSED"
    pos["close_reason"] = "broker_confirmed_closed"
    pos["broker_confirmed_closed"] = True
    pos["broker_qty"] = 0.0
    pos["pending_close_qty"] = 0.0
    pos["next_retry_at"] = ""
    pos["last_retry_error"] = ""
    pos["last_close_error"] = ""
    pos["last_close_order_status"] = ""
    pos["fatal_after_minutes"] = 0.0
    pos["last_reconciled_at"] = utc_now_iso()

    logger.warning(
        "[execution] event=close_resolved_by_reconcile symbol=%s position_id=%s previous_close_state=%s source=%s triggering_reason=%s",
        sym,
        pid,
        previous_close_state or "OPEN",
        source,
        triggering_reason or "",
    )
    _record_execution_event(
        execution_events,
        "close_resolved_by_reconcile",
        symbol=sym,
        position_id=pid,
        adapter=adapter_name,
        previous_close_state=previous_close_state or "OPEN",
        previous_close_reason=previous_close_reason,
        close_state="CLOSED",
        close_reason="broker_confirmed_closed",
        attempt_count=previous_attempt_count,
        reason="broker_confirmed_closed",
        source=source,
        triggering_reason=triggering_reason,
        broker_confirmed_closed=True,
    )
    _append_execution_order_event(
        state,
        event_type="close_resolved_by_reconcile",
        symbol=sym,
        position_id=pid,
        adapter=adapter_name,
        side=_position_side(pos),
        qty=_position_quantity(pos),
        entry=_position_entry_price(pos),
        stop=_position_stop_loss(pos),
        target=_position_take_profit(pos),
        stop_loss=_position_stop_loss(pos),
        take_profit=_position_take_profit(pos),
        close_state="CLOSED",
        close_reason="broker_confirmed_closed",
        attempt_count=previous_attempt_count,
        reason="broker_confirmed_closed",
        status="resolved_by_reconcile",
        managed_by_strategy=True,
        result={
            "previous_close_state": previous_close_state or "OPEN",
            "previous_close_reason": previous_close_reason,
            "source": source,
            "triggering_reason": triggering_reason,
            "reconciliation": reconciliation or {},
        },
        accepted=True,
        dry_run=bool(getattr(execution_adapter, "dry_run", False)) if execution_adapter is not None else False,
    )

    if had_retry_item:
        logger.warning(
            "[execution] event=retry_queue_item_removed_after_reconcile symbol=%s position_id=%s previous_close_state=%s",
            sym,
            pid,
            previous_close_state or "OPEN",
        )
        _record_execution_event(
            execution_events,
            "retry_queue_item_removed_after_reconcile",
            symbol=sym,
            position_id=pid,
            adapter=adapter_name,
            previous_close_state=previous_close_state or "OPEN",
            previous_close_reason=previous_close_reason,
            reason="broker_confirmed_closed",
            source=source,
        )
        _append_execution_order_event(
            state,
            event_type="retry_queue_item_removed_after_reconcile",
            symbol=sym,
            position_id=pid,
            adapter=adapter_name,
            close_state="CLOSED",
            close_reason="broker_confirmed_closed",
            reason="broker_confirmed_closed",
            status="retry_queue_cleared",
            managed_by_strategy=True,
            result={
                "previous_close_state": previous_close_state or "OPEN",
                "source": source,
                "triggering_reason": triggering_reason,
            },
            accepted=True,
        )

    return {
        "previous_close_state": previous_close_state or "OPEN",
        "previous_close_reason": previous_close_reason,
        "had_retry_item": had_retry_item,
        "was_fatal": was_fatal,
        "was_pending": was_pending,
    }


def reconcile_missing_broker_positions(
    *,
    state: LivePaperState,
    reconciliation: dict[str, Any],
    execution_adapter: ExecutionAdapter | None,
    execution_events: list[dict[str, Any]] | None,
) -> int:
    if (
        execution_adapter is None
        or isinstance(execution_adapter, ExecutionDisabledAdapter)
        or not bool(reconciliation.get("reconciliation_ok", False))
    ):
        return 0
    missing = {str(sym or "").strip().upper() for sym in (reconciliation.get("only_in_dashboard") or [])}
    missing.discard("")
    if not missing:
        return 0
    adapter_name = type(execution_adapter).__name__
    removed = 0
    for pos in list(state.open_positions):
        sym = str(pos.get("symbol", "")).strip().upper()
        if sym not in missing:
            continue
        qty = _position_quantity(pos)
        stop_loss = _position_stop_loss(pos)
        take_profit = _position_take_profit(pos)

        # Step 1 (overrides any pending/fatal close state):
        #   - mark broker_confirmed_closed
        #   - clear retry queue / fatal timers
        #   - emit close_resolved_by_reconcile (+ retry_queue_item_removed_after_reconcile if needed)
        resolution = _resolve_position_via_reconcile(
            state=state,
            pos=pos,
            execution_adapter=execution_adapter,
            execution_events=execution_events,
            source="reconcile_missing_broker_positions",
            triggering_reason="only_in_dashboard",
            reconciliation=reconciliation,
        )

        row = {
            "symbol": sym,
            "adapter": adapter_name,
            "reason": "reconciled_missing_at_broker",
            "side": _position_side(pos),
            "qty": qty,
            "entry": _position_entry_price(pos),
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "status": "reconciled_missing_at_broker",
            "previous_close_state": resolution["previous_close_state"],
            "broker_confirmed_closed": True,
        }
        logger.warning(
            "[execution] type=reconcile action=remove_missing_broker_position symbol=%s adapter=%s previous_close_state=%s",
            sym,
            adapter_name,
            resolution["previous_close_state"],
        )
        _record_execution_event(execution_events, "reconciled_missing_at_broker", **row)
        _append_execution_order_event(
            state,
            event_type="reconciled_missing_at_broker",
            symbol=sym,
            side=row["side"],
            qty=qty,
            entry=row["entry"],
            stop=stop_loss,
            target=take_profit,
            stop_loss=stop_loss,
            take_profit=take_profit,
            close_state="CLOSED",
            close_reason="broker_confirmed_closed",
            adapter=adapter_name,
            status="reconciled_missing_at_broker",
            reason="reconciled_missing_at_broker",
            result={
                "accepted": True,
                "adapter": adapter_name,
                "broker_confirmed_closed": True,
                "previous_close_state": resolution["previous_close_state"],
                "raw_response": {"reconciliation": reconciliation},
            },
            accepted=True,
            dry_run=bool(getattr(execution_adapter, "dry_run", False)),
        )
        state.remove_open_position(pos)
        _persist_close_retry_queue_safely(state)
        removed += 1
    return removed


def record_external_broker_positions(
    *,
    state: LivePaperState,
    reconciliation: dict[str, Any],
    execution_adapter: ExecutionAdapter | None,
    execution_events: list[dict[str, Any]] | None,
) -> int:
    if (
        execution_adapter is None
        or isinstance(execution_adapter, ExecutionDisabledAdapter)
        or not bool(reconciliation.get("reconciliation_ok", False))
    ):
        return 0
    external = {str(sym or "").strip().upper() for sym in (reconciliation.get("only_in_adapter") or [])}
    external.discard("")
    if not external:
        return 0
    adapter_name = type(execution_adapter).__name__
    logged = 0
    for sym in sorted(external):
        row = {
            "symbol": sym,
            "adapter": adapter_name,
            "reason": "external_broker_position_unmanaged",
            "status": "UNMANAGED_EXTERNAL",
            "close_state": "UNMANAGED_EXTERNAL",
            "managed_by_strategy": False,
        }
        _record_execution_event(
            execution_events,
            "reconciliation_external_position_detected",
            **row,
        )
        _append_execution_order_event(
            state,
            event_type="broker_position_imported_unmanaged",
            symbol=sym,
            adapter=adapter_name,
            status="UNMANAGED_EXTERNAL",
            reason="external_broker_position_unmanaged",
            close_state="UNMANAGED_EXTERNAL",
            close_reason="",
            source="alpaca_adapter",
            managed_by_strategy=False,
            result={"accepted": True, "raw_response": {"reconciliation": reconciliation}},
            accepted=True,
            dry_run=bool(getattr(execution_adapter, "dry_run", False)),
        )
        logged += 1
    return logged


def _coerce_float_or_none(v: Any) -> float | None:
    try:
        if v is None:
            return None
        out = float(v)
        return out if out == out else None
    except Exception:
        return None


def _merge_open_position_symbols(
    symbols: list[str],
    open_positions: list[dict[str, Any]],
) -> tuple[list[str], set[str]]:
    ordered: list[str] = []
    seen: set[str] = set()
    for raw in symbols:
        sym = str(raw or "").strip().upper()
        if not sym or sym in seen:
            continue
        seen.add(sym)
        ordered.append(sym)
    open_only: set[str] = set()
    for pos in open_positions:
        sym = str(pos.get("symbol", "")).strip().upper()
        if not sym or sym in seen:
            continue
        seen.add(sym)
        ordered.append(sym)
        open_only.add(sym)
    if open_only:
        logger.warning(
            "open_position_symbols_added_for_exit_checks count=%s symbols=%s",
            len(open_only),
            sorted(open_only)[:50],
        )
    return ordered, open_only


def _position_side(pos: dict[str, Any]) -> str:
    raw = str(
        pos.get("side")
        or pos.get("position_side")
        or pos.get("direction")
        or pos.get("order_side")
        or ""
    ).strip().lower()
    if raw in ("short", "sell"):
        return "short"
    if raw in ("long", "buy"):
        return "long"
    qty = _coerce_float_or_none(pos.get("paper_shares", pos.get("shares", pos.get("qty"))))
    if qty is not None and qty < 0:
        return "short"
    return "long"


def _position_quantity(pos: dict[str, Any]) -> float:
    qty = _coerce_float_or_none(pos.get("paper_shares", pos.get("shares", pos.get("qty"))))
    if qty is None:
        return 0.0
    return abs(float(qty))


def _position_stop_loss(pos: dict[str, Any]) -> float | None:
    for key in ("stop_loss", "stop_price", "stop"):
        val = _coerce_float_or_none(pos.get(key))
        if val is not None:
            return float(val)
    return None


def _position_take_profit(pos: dict[str, Any]) -> float | None:
    for key in ("take_profit", "target_price", "target"):
        val = _coerce_float_or_none(pos.get(key))
        if val is not None:
            return float(val)
    return None


def _position_entry_price(pos: dict[str, Any]) -> float:
    val = _coerce_float_or_none(pos.get("paper_entry_open"))
    if val is None:
        val = _coerce_float_or_none(pos.get("entry_price"))
    if val is None:
        val = _coerce_float_or_none(pos.get("entry"))
    return float(val or 0.0)


def _clean_identity_part(value: Any, fallback: str = "unknown") -> str:
    raw = str(value or "").strip()
    if not raw:
        raw = fallback
    return raw.replace("|", "-").replace("\\", "/")


def _canonical_position_id(
    *,
    symbol: Any,
    engine: Any,
    interval: Any,
    side: Any,
    entry_timestamp: Any,
) -> str:
    return "|".join(
        [
            _clean_identity_part(symbol).upper(),
            _clean_identity_part(engine).lower(),
            _clean_identity_part(interval).lower(),
            _clean_identity_part(side).lower(),
            _clean_identity_part(entry_timestamp),
        ]
    )


def _position_engine(pos: dict[str, Any]) -> str:
    return str(pos.get("engine_label") or pos.get("engine") or pos.get("preset_name") or pos.get("combo_label") or "").strip()


def _position_interval(pos: dict[str, Any]) -> str:
    return str(pos.get("interval") or pos.get("timeframe") or "").strip()


def _position_opened_timestamp(pos: dict[str, Any]) -> str:
    return str(pos.get("entry_timestamp") or pos.get("opened_at") or pos.get("entry_date") or "").strip()


def _ensure_position_identity(
    pos: dict[str, Any],
    *,
    state: LivePaperState | None = None,
    execution_events: list[dict[str, Any]] | None = None,
    reason: str = "position_id_generated",
) -> str:
    existing = str(pos.get("position_id") or "").strip()
    if existing:
        return existing
    sym = str(pos.get("symbol", "")).strip().upper()
    generated = _canonical_position_id(
        symbol=sym,
        engine=_position_engine(pos),
        interval=_position_interval(pos),
        side=_position_side(pos),
        entry_timestamp=_position_opened_timestamp(pos),
    )
    pos["position_id"] = generated
    logger.warning("[execution] event=position_id_generated symbol=%s position_id=%s reason=%s", sym, generated, reason)
    _record_execution_event(
        execution_events,
        "position_id_generated",
        symbol=sym,
        position_id=generated,
        reason=reason,
        engine=_position_engine(pos),
        interval=_position_interval(pos),
    )
    if state is not None:
        _append_execution_order_event(
            state,
            event_type="position_id_generated",
            symbol=sym,
            position_id=generated,
            engine=_position_engine(pos),
            interval=_position_interval(pos),
            side=_position_side(pos),
            reason=reason,
            status="generated",
            accepted=True,
        )
    return generated


def _parse_utc_timestamp(value: Any) -> pd.Timestamp | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        ts = pd.Timestamp(raw)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        else:
            ts = ts.tz_convert("UTC")
        return ts
    except Exception:
        return None


def _age_seconds(value: Any, *, now: pd.Timestamp | None = None) -> float | None:
    ts = _parse_utc_timestamp(value)
    if ts is None:
        return None
    now_ts = now or pd.Timestamp.now(tz="UTC")
    if now_ts.tzinfo is None:
        now_ts = now_ts.tz_localize("UTC")
    return max(0.0, float((now_ts - ts).total_seconds()))


def _env_truthy(name: str, default: bool = False) -> bool:
    raw = str(os.getenv(name, "1" if default else "0") or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _max_price_age_seconds_for_interval(interval: str | None = None) -> float:
    raw = str(os.getenv("MAX_PRICE_AGE_SECONDS", "") or "").strip()
    if raw:
        try:
            return max(1.0, float(raw))
        except ValueError:
            logger.warning("invalid MAX_PRICE_AGE_SECONDS=%s; using interval default", raw)
    iv = str(interval or "").strip().lower()
    if iv in ("1wk", "1w", "weekly", "wk"):
        return 8.0 * 24.0 * 3600.0
    return 4.0 * 24.0 * 3600.0


def _price_is_stale(price_timestamp: Any, *, interval: str | None = None) -> tuple[bool, float | None, float]:
    threshold = _max_price_age_seconds_for_interval(interval)
    age = _age_seconds(price_timestamp)
    if age is None:
        return False, None, threshold
    return bool(age > threshold), age, threshold


def _latest_ohlc_bar(df: pd.DataFrame | None) -> dict[str, Any] | None:
    if df is None or df.empty:
        return None
    row = df.iloc[-1]
    ts = pd.Timestamp(df.index[-1])
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return {
        "timestamp": ts.isoformat(),
        "bar_index": len(df) - 1,
        "open": _coerce_float_or_none(row.get("open")),
        "high": _coerce_float_or_none(row.get("high")),
        "low": _coerce_float_or_none(row.get("low")),
        "close": _coerce_float_or_none(row.get("close")),
        "price_source": "ohlc_bar",
        "price_method": "bar",
        "price_age_seconds": _age_seconds(ts.isoformat()),
    }


def _detect_stop_loss_breach(pos: dict[str, Any], df: pd.DataFrame | None) -> dict[str, Any] | None:
    validation = _strategy_position_validation(pos)
    if not validation["managed_by_strategy"]:
        return None
    stop_loss = validation["stop_loss"]
    take_profit = validation["take_profit"]
    if stop_loss is None or take_profit is None:
        return None
    bar = _latest_ohlc_bar(df)
    if bar is None:
        return None
    side = str(validation["side"])
    open_px = bar.get("open")
    gap_through_stop = False
    if side == "short":
        high_px = bar.get("high")
        if high_px is None or float(high_px) < float(stop_loss):
            return None
        gap_through_stop = open_px is not None and float(open_px) > float(stop_loss)
        exit_price = float(open_px) if gap_through_stop else float(stop_loss)
    else:
        low_px = bar.get("low")
        if low_px is None or float(low_px) > float(stop_loss):
            return None
        gap_through_stop = open_px is not None and float(open_px) < float(stop_loss)
        exit_price = float(open_px) if gap_through_stop else float(stop_loss)
    return {
        "side": side,
        "stop_loss": float(stop_loss),
        "take_profit": float(take_profit),
        "exit_price": float(exit_price),
        "bar_timestamp": str(bar["timestamp"]),
        "bar_index": int(bar["bar_index"]),
        "bar_open": bar.get("open"),
        "bar_high": bar.get("high"),
        "bar_low": bar.get("low"),
        "bar_close": bar.get("close"),
        "price_source": "ohlc_bar",
        "price_method": "bar",
        "price_timestamp": str(bar["timestamp"]),
        "price_age_seconds": bar.get("price_age_seconds"),
        "price_stale": bool((bar.get("price_age_seconds") or 0) > _max_price_age_seconds_for_interval(None)),
        "gap_through_stop": bool(gap_through_stop),
        "loss_beyond_stop_reason": "gap_through_stop" if gap_through_stop else "",
    }


def _adapter_positions_by_symbol(adapter_positions: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in adapter_positions or []:
        if not isinstance(row, dict):
            continue
        sym = str(row.get("symbol", "")).strip().upper()
        if sym and sym not in out:
            out[sym] = row
    return out


def _adapter_current_price(row: dict[str, Any] | None) -> float | None:
    if not isinstance(row, dict):
        return None
    for key in ("current_price", "mark", "last_price", "market_price"):
        val = _coerce_float_or_none(row.get(key))
        if val is not None and val > 0:
            return float(val)
    return None


def _pick_alpaca_price_row(details_map: Any, sym_u: str) -> dict[str, Any] | None:
    """Resolve Alpaca ``get_latest_price_details`` row despite key aliasing (BRK.B vs BRK-B)."""
    if not isinstance(details_map, dict) or not sym_u:
        return None
    if sym_u in details_map and isinstance(details_map[sym_u], dict):
        return details_map[sym_u]
    su = sym_u.strip().upper()
    for k, v in details_map.items():
        if str(k).strip().upper() == su and isinstance(v, dict):
            return v
    return None


def _detail_row_to_live_price(row: dict[str, Any]) -> tuple[float, str, str, str] | None:
    price = _coerce_float_or_none(row.get("price"))
    if price is None or price <= 0:
        return None
    method = str(row.get("price_method") or "").strip().lower()
    if method == "trade":
        source_label = "alpaca_trade"
    elif method == "mid":
        source_label = "alpaca_quote_mid"
    elif method in ("ask", "bid"):
        source_label = f"alpaca_quote_{method}"
    else:
        source_label = f"alpaca_{method or 'quote'}"
    ts_raw = str(row.get("price_timestamp") or "").strip()
    ts_out = ts_raw or utc_now_iso()
    return float(price), source_label, method or "trade", ts_out


def _emit_execution_price_trace(
    *,
    execution_events: list[dict[str, Any]] | None,
    state: "LivePaperState | None",
    sym_u: str,
    execution_adapter: ExecutionAdapter | None,
    decision_kind: str,
    market_is_open: bool | None,
    interval: str,
    result: dict[str, Any],
) -> None:
    payload = {
        "symbol": sym_u,
        "adapter": type(execution_adapter).__name__ if execution_adapter is not None else "",
        "decision_kind": decision_kind,
        "market_is_open": market_is_open,
        "interval": interval,
        "selected_source": result.get("selected_source") or "",
        "selected_price_method": result.get("price_method") or "",
        "price": result.get("price"),
        "price_timestamp": result.get("price_timestamp") or "",
        "price_age_seconds": result.get("price_age_seconds"),
        "price_stale": result.get("price_stale"),
        "quote_bid": result.get("quote_bid"),
        "quote_ask": result.get("quote_ask"),
        "quote_mid": result.get("quote_mid"),
        "quote_spread": result.get("quote_spread"),
        "quote_spread_pct": result.get("quote_spread_pct"),
        "stale_decision_reason": result.get("stale_decision_reason") or "",
        "block_reason": result.get("block_reason") or "",
        "fallback_chain": result.get("fallback_chain") or [],
        "ok": bool(result.get("ok")),
    }
    _record_execution_event(execution_events, "execution_price_trace", **payload)
    if state is not None:
        _append_execution_order_event(
            state,
            event_type="execution_price_trace",
            symbol=sym_u,
            adapter=type(execution_adapter).__name__ if execution_adapter is not None else "",
            interval=interval,
            current_price=result.get("price"),
            price_source=result.get("price_source"),
            price_method=result.get("price_method"),
            price_timestamp=result.get("price_timestamp"),
            price_age_seconds=result.get("price_age_seconds"),
            price_stale=result.get("price_stale"),
            quote_bid=result.get("quote_bid"),
            quote_ask=result.get("quote_ask"),
            quote_mid=result.get("quote_mid"),
            quote_spread=result.get("quote_spread"),
            quote_spread_pct=result.get("quote_spread_pct"),
            reason=str(result.get("block_reason") or result.get("stale_decision_reason") or ""),
            status="ok" if result.get("ok") else "blocked",
            managed_by_strategy=True,
            result={
                "decision_kind": decision_kind,
                "market_is_open": market_is_open,
                "selected_source": result.get("selected_source"),
                "fallback_chain": result.get("fallback_chain"),
                "stale_decision_reason": result.get("stale_decision_reason"),
                "block_reason": result.get("block_reason"),
            },
            accepted=bool(result.get("ok")),
        )
    kind = str(decision_kind or "").strip().lower()
    ev_name = "exit_price_source_selected" if kind == "exit" else "entry_price_source_selected"
    if result.get("price") is not None:
        _record_execution_event(
            execution_events,
            ev_name,
            symbol=sym_u,
            adapter=type(execution_adapter).__name__ if execution_adapter is not None else "",
            price=result.get("price"),
            current_price=result.get("price"),
            price_source=result.get("price_source"),
            price_method=result.get("price_method"),
            price_timestamp=result.get("price_timestamp"),
            price_age_seconds=result.get("price_age_seconds"),
            price_stale=bool(result.get("price_stale")),
            quote_bid=result.get("quote_bid"),
            quote_ask=result.get("quote_ask"),
            quote_mid=result.get("quote_mid"),
            quote_spread=result.get("quote_spread"),
            quote_spread_pct=result.get("quote_spread_pct"),
            reason=str(result.get("selected_source") or ""),
            fallback_chain=result.get("fallback_chain"),
            block_reason=result.get("block_reason"),
            stale_decision_reason=result.get("stale_decision_reason"),
        )
        if state is not None:
            _append_execution_order_event(
                state,
                event_type=ev_name,
                symbol=sym_u,
                adapter=type(execution_adapter).__name__ if execution_adapter is not None else "",
                current_price=result.get("price"),
                price_source=result.get("price_source"),
                price_method=result.get("price_method"),
                price_timestamp=result.get("price_timestamp"),
                price_age_seconds=result.get("price_age_seconds"),
                price_stale=bool(result.get("price_stale")),
                quote_bid=result.get("quote_bid"),
                quote_ask=result.get("quote_ask"),
                quote_mid=result.get("quote_mid"),
                quote_spread=result.get("quote_spread"),
                quote_spread_pct=result.get("quote_spread_pct"),
                reason=str(result.get("selected_source") or ""),
                status="ok",
                managed_by_strategy=True,
                accepted=True,
            )


def _resolve_execution_price(
    *,
    sym: str,
    execution_adapter: ExecutionAdapter | None,
    adapter_row: dict[str, Any] | None,
    interval: str,
    decision_kind: str,
    market_is_open: bool | None,
    df: pd.DataFrame | None,
    execution_events: list[dict[str, Any]] | None,
    state: "LivePaperState | None" = None,
) -> dict[str, Any]:
    """Resolve execution reference price with explicit source tracing (see AGENTS)."""
    sym_u = str(sym or "").strip().upper()
    chain: list[dict[str, Any]] = []
    force_live_priority = market_is_open is True
    block_reason = ""
    stale_decision_reason = ""
    price: float | None = None
    price_source = ""
    price_method = ""
    price_timestamp = ""
    price_age_seconds: float | None = None
    price_stale = False
    selected_source = ""
    market_detail_row: dict[str, Any] = {}

    def _chain(step: str, outcome: str, **extra: Any) -> None:
        chain.append({"step": step, "outcome": outcome, **extra})

    if not sym_u:
        _chain("symbol", "error", detail="empty_symbol")
        out = {
            "ok": False,
            "price": None,
            "price_source": "",
            "price_method": "",
            "price_timestamp": "",
            "price_age_seconds": None,
            "price_stale": False,
            "block_reason": "price_unavailable_" + ("exit" if decision_kind == "exit" else "entry") + "_blocked",
            "stale_decision_reason": "",
            "selected_source": "",
            "fallback_chain": chain,
        }
        _emit_execution_price_trace(
            execution_events=execution_events,
            state=state,
            sym_u=sym_u,
            execution_adapter=execution_adapter,
            decision_kind=decision_kind,
            market_is_open=market_is_open,
            interval=interval,
            result=out,
        )
        return out

    if execution_adapter is None:
        _chain("live_adapter", "miss", detail="execution_adapter_none")
    elif isinstance(execution_adapter, ExecutionDisabledAdapter):
        _chain("live_adapter", "skipped", detail="execution_disabled_adapter")
    elif not hasattr(execution_adapter, "get_latest_price_details"):
        _chain("alpaca_trade", "skipped", detail="adapter_has_no_get_latest_price_details")
    else:
        details_map: Any = {}
        try:
            details_map = execution_adapter.get_latest_price_details([sym_u])
            _chain("alpaca_get_latest_price_details", "ok", detail="called")
        except Exception as exc:  # noqa: BLE001
            _chain("alpaca_get_latest_price_details", "error", detail=f"{type(exc).__name__}: {exc}")
            details_map = {}
        row = _pick_alpaca_price_row(details_map, sym_u)
        if isinstance(row, dict):
            parsed = _detail_row_to_live_price(row)
            if parsed is not None:
                price, price_source, price_method, price_timestamp = parsed
                market_detail_row = dict(row)
                price_age_seconds = _age_seconds(price_timestamp)
                price_stale = False
                selected_source = price_source
                _chain(price_source, "ok", price=price, price_timestamp=price_timestamp)
            else:
                _chain("alpaca_trade_or_quote", "miss", detail="no_positive_price_in_row")
        else:
            _chain("alpaca_trade_or_quote", "miss", detail="no_row_for_symbol")

    if price is None and execution_adapter is not None and not isinstance(execution_adapter, ExecutionDisabledAdapter):
        bp = _adapter_current_price(adapter_row)
        if bp is not None and bp > 0:
            price = float(bp)
            price_source = "alpaca_position_current_price"
            price_method = "broker_mark"
            price_timestamp = utc_now_iso()
            price_age_seconds = 0.0
            price_stale = False
            selected_source = price_source
            _chain("broker_position_row_cached", "ok", price=price)
        elif hasattr(execution_adapter, "get_position"):
            try:
                prow = execution_adapter.get_position(sym_u)
            except Exception as exc:  # noqa: BLE001
                prow = None
                _chain("broker_get_position", "error", detail=f"{type(exc).__name__}: {exc}")
            if isinstance(prow, dict):
                bp2 = _adapter_current_price(prow)
                if bp2 is not None and bp2 > 0:
                    price = float(bp2)
                    price_source = "alpaca_position_current_price"
                    price_method = "broker_get_position"
                    price_timestamp = utc_now_iso()
                    price_age_seconds = 0.0
                    price_stale = False
                    selected_source = price_source
                    _chain("broker_get_position", "ok", price=price)
                else:
                    _chain("broker_get_position", "miss", detail="no_current_price_in_row")
            elif prow is None:
                _chain("broker_get_position", "miss", detail="no_position_row")

    if price is None and df is not None:
        bar = _latest_ohlc_bar(df)
        if bar is None or _positive_price(bar.get("close")) is None:
            _chain("ohlc_bar", "miss", detail="no_bar_or_close")
            block_reason = "price_unavailable_" + ("exit" if decision_kind == "exit" else "entry") + "_blocked"
        else:
            price_ts = str(bar.get("timestamp") or "")
            px = float(_positive_price(bar.get("close")) or 0.0)
            stale, age, threshold = _price_is_stale(price_ts, interval=interval)
            price_age_seconds = age
            price_timestamp = price_ts
            price_method = "bar"
            price_source = "ohlc_bar"
            selected_source = "ohlc_bar"
            allow_stale_ohlcv = force_live_priority or _env_truthy("ALLOW_STALE_PRICE_STOP_EXITS", False)
            if stale and not allow_stale_ohlcv:
                block_reason = "stale_price_" + ("exit" if decision_kind == "exit" else "entry") + "_blocked"
                stale_decision_reason = f"ohlcv_age_exceeds_threshold age_seconds={age} threshold_seconds={threshold}"
                price_stale = True
                _chain("ohlc_bar", "blocked_stale", price_timestamp=price_ts, price_age_seconds=age, threshold_seconds=threshold)
            elif stale and allow_stale_ohlcv:
                price = px
                price_stale = True
                stale_decision_reason = (
                    "market_open_stale_guard_suppressed_using_ohlcv_close"
                    if force_live_priority
                    else "allow_stale_price_env_using_ohlcv_close"
                )
                _chain(
                    "ohlc_bar",
                    "ok_stale_suppressed",
                    price=price,
                    price_timestamp=price_ts,
                    price_age_seconds=age,
                    threshold_seconds=threshold,
                    reason=stale_decision_reason,
                )
            else:
                price = px
                price_stale = False
                stale_decision_reason = ""
                _chain("ohlc_bar", "ok", price=price, price_timestamp=price_ts, price_age_seconds=age)
    elif price is None:
        _chain("ohlc_bar", "skipped", detail="no_dataframe_for_ohlcv_fallback")
        block_reason = "price_unavailable_" + ("exit" if decision_kind == "exit" else "entry") + "_blocked"

    ok = bool(price is not None and not block_reason)
    quote_bid_for_spread = _coerce_float_or_none(market_detail_row.get("quote_bid"))
    quote_ask_for_spread = _coerce_float_or_none(market_detail_row.get("quote_ask"))
    out = {
        "ok": ok,
        "price": price,
        "price_source": price_source,
        "price_method": price_method,
        "price_timestamp": price_timestamp,
        "price_age_seconds": price_age_seconds,
        "price_stale": price_stale,
        "block_reason": block_reason,
        "stale_decision_reason": stale_decision_reason,
        "selected_source": selected_source,
        "fallback_chain": chain,
        "trade_price": market_detail_row.get("trade_price"),
        "quote_bid": market_detail_row.get("quote_bid"),
        "quote_ask": market_detail_row.get("quote_ask"),
        "quote_mid": market_detail_row.get("quote_mid"),
        "quote_spread": (
            (quote_ask_for_spread - quote_bid_for_spread)
            if quote_bid_for_spread is not None and quote_ask_for_spread is not None
            else None
        ),
        "quote_spread_pct": market_detail_row.get("quote_spread_pct"),
    }
    _emit_execution_price_trace(
        execution_events=execution_events,
        state=state,
        sym_u=sym_u,
        execution_adapter=execution_adapter,
        decision_kind=decision_kind,
        market_is_open=market_is_open,
        interval=interval,
        result=out,
    )
    return out


def _live_broker_price_lookup(
    *,
    sym: str,
    execution_adapter: ExecutionAdapter | None,
    adapter_row: dict[str, Any] | None,
    execution_events: list[dict[str, Any]] | None,
    state: "LivePaperState | None" = None,
) -> dict[str, Any] | None:
    """Backward-compatible wrapper: live-first resolve without OHLCV (tests, helpers)."""
    res = _resolve_execution_price(
        sym=sym,
        execution_adapter=execution_adapter,
        adapter_row=adapter_row,
        interval="1d",
        decision_kind="exit",
        market_is_open=True,
        df=None,
        execution_events=execution_events,
        state=state,
    )
    if res.get("price") is None:
        return None
    return {
        "price": float(res["price"]),
        "price_source": str(res.get("price_source") or ""),
        "price_method": str(res.get("price_method") or ""),
        "price_timestamp": str(res.get("price_timestamp") or utc_now_iso()),
        "price_age_seconds": float(res.get("price_age_seconds") or 0.0),
        "price_stale": False,
        "fetch_error": "",
    }


def _build_adapter_mark_exit_from_live_price(
    pos: dict[str, Any],
    live_detail: dict[str, Any],
    *,
    adapter_row: dict[str, Any] | None = None,
    market_detail: dict[str, Any] | None = None,
    execution_events: list[dict[str, Any]] | None = None,
    sym: str | None = None,
) -> dict[str, Any] | None:
    """Validated live TP/SL exit from execution-resolved price (spike-resistant)."""
    validation = _strategy_position_validation(pos)
    if not validation["managed_by_strategy"]:
        return None
    sym_u = str(sym or pos.get("symbol") or "").strip().upper()

    def _record(event_type: str, **payload: Any) -> None:
        payload.pop("symbol", None)
        _record_execution_event(execution_events, event_type, symbol=sym_u, **payload)

    return evaluate_validated_live_exit(
        pos=pos,
        live_detail=live_detail,
        adapter_row=adapter_row,
        market_detail=market_detail,
        record_event=_record,
        strategy_validation=validation,
    )


def _detect_adapter_mark_exit(
    pos: dict[str, Any],
    adapter_positions: list[dict[str, Any]] | None,
    *,
    execution_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    validation = _strategy_position_validation(pos)
    if not validation["managed_by_strategy"]:
        return None
    symbol = str(pos.get("symbol", "")).strip().upper()
    if not symbol:
        return None
    adapter_row = _adapter_positions_by_symbol(adapter_positions).get(symbol)
    current_price = _adapter_current_price(adapter_row)
    if current_price is None:
        return None
    live_detail = {
        "price": float(current_price),
        "price_source": "alpaca_position_current_price",
        "price_method": "broker_mark",
        "price_timestamp": utc_now_iso(),
        "price_age_seconds": 0.0,
        "broker_current_price": float(current_price),
    }

    def _record(event_type: str, **payload: Any) -> None:
        payload.pop("symbol", None)
        _record_execution_event(execution_events, event_type, symbol=symbol, **payload)

    return evaluate_validated_live_exit(
        pos=pos,
        live_detail=live_detail,
        adapter_row=adapter_row,
        market_detail=live_detail,
        record_event=_record,
        strategy_validation=validation,
    )


def _actual_r_for_position_exit(pos: dict[str, Any], exit_price: float) -> float:
    entry = _position_entry_price(pos)
    stop_loss = _position_stop_loss(pos)
    if entry <= 0 or stop_loss is None:
        return 0.0
    risk_per_share = abs(float(entry) - float(stop_loss))
    if risk_per_share <= 1e-12:
        return 0.0
    if _position_side(pos) == "short":
        return (float(entry) - float(exit_price)) / risk_per_share
    return (float(exit_price) - float(entry)) / risk_per_share


def _position_risk_per_share(pos: dict[str, Any]) -> float | None:
    value = _coerce_float_or_none(pos.get("risk_per_share"))
    if value is not None and value > 0:
        return float(abs(value))
    entry = _position_entry_price(pos)
    stop_loss = _position_stop_loss(pos)
    if entry <= 0 or stop_loss is None or stop_loss <= 0:
        return None
    risk = abs(float(entry) - float(stop_loss))
    return float(risk) if risk > 1e-12 else None


def _position_risk_amount(pos: dict[str, Any]) -> float | None:
    for key in ("risk_amount", "dollar_risk", "initial_risk_dollars", "risk"):
        value = _coerce_float_or_none(pos.get(key))
        if value is not None and value > 0:
            return float(value)
    risk_per_share = _position_risk_per_share(pos)
    qty = _position_quantity(pos)
    if risk_per_share is None or qty <= 0:
        return None
    return float(risk_per_share) * float(qty)


def _position_rr(pos: dict[str, Any]) -> float | None:
    for key in ("rr", "final_rr", "expected_r_from_backtest", "r_multiple"):
        value = _coerce_float_or_none(pos.get(key))
        if value is not None and value > 0:
            return float(value)
    entry = _position_entry_price(pos)
    stop_loss = _position_stop_loss(pos)
    take_profit = _position_take_profit(pos)
    if entry <= 0 or stop_loss is None or take_profit is None:
        return None
    risk = abs(float(entry) - float(stop_loss))
    if risk <= 1e-12:
        return None
    if _position_side(pos) == "short":
        return (float(entry) - float(take_profit)) / risk
    return (float(take_profit) - float(entry)) / risk


def _position_config_label(pos: dict[str, Any]) -> str:
    return str(pos.get("config") or pos.get("preset") or pos.get("preset_name") or pos.get("combo_label") or "").strip()


def _position_intent_context(pos: dict[str, Any]) -> dict[str, Any]:
    risk_per_share = _position_risk_per_share(pos)
    risk_amount = _position_risk_amount(pos)
    rr = _position_rr(pos)
    config_label = _position_config_label(pos)
    return {
        "position_id": str(pos.get("position_id") or "").strip(),
        "risk_per_share": risk_per_share,
        "risk_amount": risk_amount,
        "rr": rr,
        "config": config_label,
        "preset": str(pos.get("preset") or pos.get("preset_name") or config_label).strip(),
        "signal_date": str(pos.get("signal_date") or pos.get("signal_bar_date") or "").strip()[:10],
        "intended_entry_date": str(pos.get("intended_entry_date") or pos.get("entry_date") or "").strip()[:10],
    }


def _loss_beyond_stop_reason(pos: dict[str, Any], exit_price: float, *, fallback: str = "") -> str:
    actual_r = _actual_r_for_position_exit(pos, float(exit_price))
    if actual_r >= -1.000001:
        return ""
    existing = str(pos.get("loss_beyond_stop_reason") or fallback or "").strip()
    return existing or "exit_price_beyond_planned_stop"


def _positive_price(value: Any) -> float | None:
    val = _coerce_float_or_none(value)
    if val is None or val <= 0:
        return None
    return float(val)


def _strategy_position_validation(pos: dict[str, Any]) -> dict[str, Any]:
    _ensure_position_identity(pos, reason="strategy_position_validation")
    symbol = str(pos.get("symbol", "")).strip().upper()
    qty = _position_quantity(pos)
    entry = _position_entry_price(pos)
    stop_loss = _positive_price(_position_stop_loss(pos))
    take_profit = _positive_price(_position_take_profit(pos))
    side = _position_side(pos)
    risk_per_share = abs(float(entry) - float(stop_loss)) if entry > 0 and stop_loss is not None else 0.0
    engine = _position_engine(pos)
    preset = str(pos.get("preset_name") or pos.get("combo_label") or pos.get("config") or "").strip()
    opened_at = str(pos.get("entry_timestamp") or pos.get("opened_at") or pos.get("entry_date") or "").strip()
    missing: list[str] = []
    if not symbol:
        missing.append("symbol")
    if qty <= 0:
        missing.append("quantity")
    if entry <= 0:
        missing.append("entry_price")
    if stop_loss is None:
        missing.append("stop_loss")
    if take_profit is None:
        missing.append("take_profit")
    if risk_per_share <= 0:
        missing.append("risk_per_share")
    if side not in ("long", "short"):
        missing.append("side")
    if not (engine or preset):
        missing.append("engine_or_preset")
    if not opened_at:
        missing.append("opened_timestamp")
    if pos.get("fill_drift_exceeded") or pos.get("invalid_fill_drift"):
        missing.append("fill_drift_exceeded")
    if pos.get("entry_fill_pending"):
        missing.append("entry_fill_pending")
    return {
        "managed_by_strategy": not missing,
        "symbol": symbol,
        "side": side,
        "qty": qty,
        "entry_price": entry,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "risk_per_share": risk_per_share,
        "engine": engine,
        "preset": preset,
        "position_id": str(pos.get("position_id") or ""),
        "missing_fields": missing,
        "reason": "valid_strategy_position" if not missing else "invalid_strategy_position_fields",
    }


def _position_is_strategy_managed(pos: dict[str, Any]) -> bool:
    return bool(_strategy_position_validation(pos)["managed_by_strategy"])


def _current_r_for_position(pos: dict[str, Any], price: Any) -> float | None:
    px = _positive_price(price)
    if px is None:
        return None
    entry = _position_entry_price(pos)
    stop_loss = _positive_price(_position_stop_loss(pos))
    if entry <= 0 or stop_loss is None:
        return None
    risk = abs(float(entry) - float(stop_loss))
    if risk <= 1e-12:
        return None
    if _position_side(pos) == "short":
        return (float(entry) - float(px)) / risk
    return (float(px) - float(entry)) / risk


def _latest_close_price(df: pd.DataFrame | None) -> float | None:
    bar = _latest_ohlc_bar(df)
    if bar is None:
        return None
    return _positive_price(bar.get("close"))


def _days_held_from_position(pos: dict[str, Any]) -> int | None:
    raw = str(pos.get("entry_date") or pos.get("entry_timestamp") or "").strip()
    if not raw:
        return None
    try:
        entered = pd.Timestamp(raw).date()
        now_d = pd.Timestamp.utcnow().date()
        return max(0, int((now_d - entered).days))
    except Exception:
        return None


def _entry_index_for_open_position(pos: dict[str, Any], df: pd.DataFrame) -> int | None:
    if df is None or df.empty:
        return None
    entry_date = str(pos.get("entry_date") or "").strip()[:10]
    raw_idx = pos.get("entry_bar", pos.get("entry_bar_index", pos.get("candidate_signal_bar")))
    try:
        idx = int(raw_idx)
        if 0 <= idx < len(df):
            if not entry_date or str(pd.Timestamp(df.index[idx]).date()) == entry_date:
                return idx
    except Exception:
        pass
    if entry_date:
        for i, ts in enumerate(df.index):
            try:
                if str(pd.Timestamp(ts).date()) == entry_date:
                    return int(i)
            except Exception:
                continue
    return None


NON_ACTIONABLE_ENGINE_EXIT_REASONS = {"", "eod", "eod_forced", "eod_forced_fallback"}


def _evaluate_engine_exit_for_open_position(
    *,
    sym: str,
    pos: dict[str, Any],
    df: pd.DataFrame | None,
    cfg: Any | None,
    combo_label: str,
    interval: str,
    adapter_mark_price: float | None = None,
) -> dict[str, Any]:
    """Evaluate existing backtest exit rules against an already-open live position.

    This is execution-layer wiring only: the actual rule implementation remains in
    ``fib_quality._simulate_long_exit_optional_time_stop``.
    """
    validation = _strategy_position_validation(pos)
    base: dict[str, Any] = {
        "symbol": sym,
        "combo_label": combo_label,
        "interval": interval,
        "side": validation["side"],
        "qty": validation["qty"],
        "entry_price": validation["entry_price"],
        "stop_loss": validation["stop_loss"],
        "take_profit": validation["take_profit"],
        "risk_per_share": validation["risk_per_share"],
        "days_held": _days_held_from_position(pos),
        "managed_by_strategy": validation["managed_by_strategy"],
        "invalid_fields": validation["missing_fields"],
        "triggered": False,
        "triggered_rule": "",
        "skipped_exit_reason": "",
        "close_attempt_status": "",
    }
    price_for_r = adapter_mark_price if adapter_mark_price is not None else _latest_close_price(df)
    base["current_price"] = price_for_r
    base["current_r"] = _current_r_for_position(pos, price_for_r)

    if not validation["managed_by_strategy"]:
        base["skipped_exit_reason"] = validation["reason"]
        return base
    if validation["side"] != "long":
        base["skipped_exit_reason"] = "engine_exit_rules_long_only"
        return base
    if cfg is None:
        base["skipped_exit_reason"] = "missing_engine_config"
        return base
    if df is None or df.empty:
        base["skipped_exit_reason"] = "insufficient_data"
        return base

    df_l = df.rename(columns=str.lower)
    required = {"high", "low", "close"}
    if not required.issubset(set(df_l.columns)):
        base["skipped_exit_reason"] = "invalid_ohlcv"
        return base
    entry_idx = _entry_index_for_open_position(pos, df_l)
    if entry_idx is None:
        base["skipped_exit_reason"] = "entry_bar_not_found"
        return base
    if entry_idx >= len(df_l) - 1:
        base["bars_held"] = 0
        base["skipped_exit_reason"] = "insufficient_bars_after_entry"
        return base

    high = df_l["high"].values.astype(float)
    low = df_l["low"].values.astype(float)
    close = df_l["close"].values.astype(float)
    open_arr = df_l["open"].values.astype(float) if "open" in df_l.columns else close.copy()
    ema50 = pd.Series(close).ewm(span=50, adjust=False).mean().to_numpy()
    atr_period = max(5, int(getattr(cfg, "candidate_atr_period", 14)))
    tr1 = pd.Series(high - low)
    tr2 = pd.Series(np.abs(high - np.r_[close[0], close[:-1]]))
    tr3 = pd.Series(np.abs(low - np.r_[close[0], close[:-1]]))
    atr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(atr_period, min_periods=1).mean().to_numpy()
    atr_pct_arr = np.where(close != 0, 100.0 * atr / close, 0.0)

    from algo_scanner.backtest.fib_quality import (
        _cfg_pessimistic_bar_fill,
        _simulate_long_exit_optional_time_stop,
    )

    realism_on = bool(
        getattr(cfg, "use_execution_realism", False)
        or getattr(cfg, "execution_realism_enabled", False)
    )
    gap_on = bool(realism_on and getattr(cfg, "use_gap_through_stop_logic", True))
    entry = float(validation["entry_price"])
    stop = float(validation["stop_loss"])
    target = float(validation["take_profit"])
    ex = _simulate_long_exit_optional_time_stop(
        high,
        low,
        close,
        int(entry_idx),
        entry,
        stop,
        target,
        time_stop_enabled=bool(getattr(cfg, "time_stop_enabled", False)),
        time_stop_weeks=int(getattr(cfg, "time_stop_weeks", 16)),
        time_stop_min_R=float(getattr(cfg, "time_stop_min_R", 0.5)),
        trend_break_enabled=bool(getattr(cfg, "trend_break_enabled", False)),
        ema50=ema50,
        atr_pct=atr_pct_arr,
        weak_trade_exit_enabled=bool(getattr(cfg, "weak_trade_exit_enabled", False)),
        weak_trade_check_bars=int(getattr(cfg, "weak_trade_check_bars", 6)),
        weak_trade_min_progress_r=float(getattr(cfg, "weak_trade_min_progress_r", 0.5)),
        weak_trade_atr_contraction_factor=float(getattr(cfg, "weak_trade_atr_contraction_factor", 0.7)),
        weak_trade_require_higher_high=bool(getattr(cfg, "weak_trade_require_higher_high", True)),
        open_=open_arr,
        gap_through_stops=gap_on,
        early_failure_exit_enabled=bool(getattr(cfg, "early_failure_exit_enabled", False)),
        early_failure_check_bars=int(getattr(cfg, "early_failure_check_bars", 5)),
        early_failure_min_mfe_r=float(getattr(cfg, "early_failure_min_mfe_r", 0.3)),
        early_failure_mae_r_threshold=float(getattr(cfg, "early_failure_mae_r_threshold", -0.8)),
        early_failure_fill_mode=str(getattr(cfg, "early_failure_fill_mode", "close")),
        early_failure_stop_fraction=float(getattr(cfg, "early_failure_stop_fraction", 0.4)),
        max_holding_bars=int(getattr(cfg, "max_holding_bars", 52)),
        early_momentum_exit_enabled=bool(getattr(cfg, "early_momentum_exit_enabled", True)),
        early_momentum_bars=int(getattr(cfg, "early_momentum_bars", 4)),
        early_momentum_target_r=float(getattr(cfg, "early_momentum_target_r", 0.5)),
        mfe_r_gate_exit_enabled=bool(getattr(cfg, "mfe_r_gate_exit_enabled", False)),
        mfe_r_gate_bars=int(getattr(cfg, "mfe_r_gate_bars", 4)),
        mfe_r_gate_min_r=float(getattr(cfg, "mfe_r_gate_min_r", 1.0)),
        max_allowed_mae_r_early=getattr(cfg, "max_allowed_mae_r_early", None),
        mae_check_bars=int(getattr(cfg, "mae_check_bars", 2)),
        max_allowed_mae_r_mid=getattr(cfg, "max_allowed_mae_r_mid", None),
        mae_mid_check_bars=int(getattr(cfg, "mae_mid_check_bars", 4)),
        stop_exit_slippage_frac=float(getattr(cfg, "execution_stop_exit_slippage_frac", 0) or 0),
        target_exit_haircut_frac=float(getattr(cfg, "execution_target_exit_haircut_frac", 0) or 0),
        force_worst_case_same_bar=_cfg_pessimistic_bar_fill(cfg)
        or bool(getattr(cfg, "execution_force_worst_case_fills", False)),
    )
    if not isinstance(ex, dict):
        base["skipped_exit_reason"] = "no_exit_condition_active"
        return base
    exit_idx = int(ex.get("exit_idx", len(df_l) - 1))
    exit_idx = max(0, min(exit_idx, len(df_l) - 1))
    reason = str(ex.get("exit_reason") or "")
    base.update(
        {
            "bars_held": int(ex.get("bars_held", max(0, exit_idx - int(entry_idx))) or 0),
            "mfe_r": _coerce_float_or_none(ex.get("mfe_r")),
            "mae_r": _coerce_float_or_none(ex.get("mae_r")),
            "engine_exit_date": str(pd.Timestamp(df_l.index[exit_idx]).date()),
            "engine_exit_bar": exit_idx,
            "triggered_rule": reason,
        }
    )
    if reason in NON_ACTIONABLE_ENGINE_EXIT_REASONS:
        base["skipped_exit_reason"] = "no_exit_condition_active"
        return base

    exit_px = float(entry) + float(ex.get("pnl", 0.0) or 0.0)
    trade = {
        "symbol": sym,
        "candidate_signal_bar": int(pos.get("candidate_signal_bar", entry_idx) or entry_idx),
        "entry_bar": int(entry_idx),
        "entry_date": str(pos.get("entry_date") or pd.Timestamp(df_l.index[entry_idx]).date())[:10],
        "entry": entry,
        "stop": stop,
        "target": target,
        "exit_bar": exit_idx,
        "exit_date": str(pd.Timestamp(df_l.index[exit_idx]).date()),
        "exit_reason": reason,
        "pnl": float(ex.get("pnl", exit_px - entry) or 0.0),
        "pnl_per_share": float(ex.get("pnl", exit_px - entry) or 0.0),
        "r_multiple": float(ex.get("r_multiple", 0.0) or 0.0),
        "bars_held": int(ex.get("bars_held", max(0, exit_idx - int(entry_idx))) or 0),
        "mae_r": _coerce_float_or_none(ex.get("mae_r")),
        "mfe_r": _coerce_float_or_none(ex.get("mfe_r")),
        "source_signal_type": str(pos.get("source_signal_type") or "live_open_position_exit_replay"),
        "live_exit_replay": True,
    }
    base["triggered"] = True
    base["trade"] = trade
    base["close_attempt_status"] = "exit_condition_active"
    return base


def _adapter_position_for_symbol(
    execution_adapter: ExecutionAdapter | None,
    symbol: str,
) -> tuple[dict[str, Any] | None, str]:
    if execution_adapter is None or not hasattr(execution_adapter, "get_positions"):
        return None, "adapter_unavailable"
    try:
        rows = execution_adapter.get_positions()
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"
    sym = str(symbol or "").strip().upper()
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("symbol", "")).strip().upper() == sym:
            return row, ""
    return None, ""


def _broker_qty_from_position_row(row: dict[str, Any] | None) -> float:
    if not isinstance(row, dict):
        return 0.0
    qty = _coerce_float_or_none(row.get("qty", row.get("quantity", row.get("shares"))))
    return abs(float(qty or 0.0))


def _mark_close_workflow(
    pos: dict[str, Any],
    *,
    state_name: str,
    reason: str,
    broker_qty: float | None = None,
    order_id: str | None = None,
    order_status: str | None = None,
    error: str | None = None,
) -> None:
    now = utc_now_iso()
    _ensure_position_identity(pos, reason="close_workflow")
    pos["close_state"] = str(state_name)
    pos["close_reason"] = str(reason or pos.get("close_reason") or "")
    if "close_requested_at" not in pos or str(state_name) == "CLOSE_REQUIRED":
        pos["close_requested_at"] = now
    pos["last_close_attempt_at"] = now
    if str(state_name) == "CLOSE_REQUESTED":
        pos["close_attempt_count"] = int(pos.get("close_attempt_count", 0) or 0) + 1
    else:
        pos["close_attempt_count"] = int(pos.get("close_attempt_count", 0) or 0)
    if order_id:
        pos["last_close_order_id"] = str(order_id)
    if order_status:
        pos["last_close_order_status"] = str(order_status)
    if error:
        pos["last_close_error"] = str(error)
    if broker_qty is not None:
        pos["broker_qty"] = float(broker_qty)
        pos["pending_close_qty"] = float(broker_qty)
    state_u = str(state_name).strip().upper()
    if state_u in CLOSE_RETRY_PENDING_STATES:
        _schedule_close_retry(
            pos,
            reason=str(reason or pos.get("close_reason") or "pending_close_retry"),
            error=error,
            broker_qty=broker_qty,
            force_due=state_u in {"CLOSE_REQUIRED", "CLOSE_RETRY", "CLOSE_PARTIAL", "VERIFY_CLOSED"},
        )
    elif state_u in CLOSE_RETRY_TERMINAL_STATES:
        pos["next_retry_at"] = ""
        pos["pending_close_qty"] = 0.0
    pos["last_reconciled_at"] = now


def _verify_close_with_broker(
    *,
    sym: str,
    pos: dict[str, Any],
    execution_adapter: ExecutionAdapter | None,
    execution_events: list[dict[str, Any]] | None,
    reason: str,
    adapter_name: str,
) -> tuple[bool, float, str]:
    broker_row, err = _adapter_position_for_symbol(execution_adapter, sym)
    if err:
        _mark_close_workflow(pos, state_name="CLOSE_RETRY", reason=reason, error=err)
        _record_execution_event(
            execution_events,
            "close_order_retry",
            symbol=sym,
            adapter=adapter_name,
            reason=reason,
            close_state="CLOSE_RETRY",
            error=err,
        )
        return False, _position_quantity(pos), err
    broker_qty = _broker_qty_from_position_row(broker_row)
    if broker_row is None or broker_qty <= 0:
        pos["close_state"] = "CLOSED"
        pos["broker_qty"] = 0.0
        pos["pending_close_qty"] = 0.0
        pos["last_reconciled_at"] = utc_now_iso()
        _record_execution_event(
            execution_events,
            "close_order_confirmed",
            symbol=sym,
            adapter=adapter_name,
            reason=reason,
            close_state="CLOSED",
            qty=0.0,
        )
        return True, 0.0, ""
    local_qty = _position_quantity(pos)
    close_state = "CLOSE_PARTIAL" if broker_qty < local_qty else "CLOSE_RETRY"
    _mark_close_workflow(pos, state_name=close_state, reason=reason, broker_qty=broker_qty)
    _record_execution_event(
        execution_events,
        "close_order_partial" if close_state == "CLOSE_PARTIAL" else "close_order_retry",
        symbol=sym,
        adapter=adapter_name,
        reason=reason,
        close_state=close_state,
        qty=broker_qty,
    )
    return False, broker_qty, "broker_position_still_open"


CLOSE_RETRY_PENDING_STATES = {"CLOSE_REQUIRED", "CLOSE_REQUESTED", "CLOSE_SUBMITTED", "CLOSE_RETRY", "CLOSE_PARTIAL", "VERIFY_CLOSED"}
CLOSE_RETRY_TERMINAL_STATES = {"CLOSED", "CLOSE_FAILED_FATAL", "UNMANAGED_EXTERNAL"}


def _close_retry_float_env(name: str, default: float, *, minimum: float = 0.0) -> float:
    raw = str(os.getenv(name, "") or "").strip()
    if not raw:
        return float(default)
    try:
        return max(float(minimum), float(raw))
    except ValueError:
        logger.warning("invalid %s=%s; using default=%s", name, raw, default)
        return float(default)


def _close_retry_int_env(name: str, default: int, *, minimum: int = 1) -> int:
    raw = str(os.getenv(name, "") or "").strip()
    if not raw:
        return int(default)
    try:
        return max(int(minimum), int(float(raw)))
    except ValueError:
        logger.warning("invalid %s=%s; using default=%s", name, raw, default)
        return int(default)


def _close_retry_config() -> dict[str, Any]:
    return {
        "close_retry_backoff_seconds": _close_retry_float_env("CLOSE_RETRY_BACKOFF_SECONDS", 15.0, minimum=1.0),
        "close_retry_jitter_seconds": _close_retry_float_env("CLOSE_RETRY_JITTER_SECONDS", 3.0, minimum=0.0),
        "close_retry_max_attempts": _close_retry_int_env("CLOSE_RETRY_MAX_ATTEMPTS", 8, minimum=1),
        "close_retry_fatal_after_minutes": _close_retry_float_env("CLOSE_RETRY_FATAL_AFTER_MINUTES", 45.0, minimum=1.0),
    }


def _deterministic_retry_jitter(position_id: str, max_jitter_seconds: float) -> float:
    if max_jitter_seconds <= 0:
        return 0.0
    seed = sum(ord(ch) for ch in str(position_id or ""))
    return (float(seed % 1000) / 1000.0) * float(max_jitter_seconds)


def _iso_after_seconds(seconds: float) -> str:
    ts = pd.Timestamp.now(tz="UTC") + pd.Timedelta(seconds=max(0.0, float(seconds)))
    return ts.replace(microsecond=0).isoformat()


def _schedule_close_retry(
    pos: dict[str, Any],
    *,
    reason: str,
    error: str | None = None,
    broker_qty: float | None = None,
    force_due: bool = False,
) -> None:
    cfg = _close_retry_config()
    pid = _ensure_position_identity(pos, reason="close_retry_schedule")
    now = utc_now_iso()
    first_failure = str(pos.get("first_close_failure_at") or "").strip()
    if not first_failure:
        pos["first_close_failure_at"] = now
    pos["close_retry_reason"] = str(reason or pos.get("close_reason") or "pending_close_retry")
    if error:
        pos["last_retry_error"] = str(error)
    pos["retry_backoff_seconds"] = float(cfg["close_retry_backoff_seconds"])
    pos["fatal_after_minutes"] = float(cfg["close_retry_fatal_after_minutes"])
    if broker_qty is not None:
        pos["broker_qty"] = float(broker_qty)
        pos["pending_close_qty"] = float(broker_qty)
    if force_due:
        pos["next_retry_at"] = now
    else:
        delay = float(cfg["close_retry_backoff_seconds"]) + _deterministic_retry_jitter(pid, float(cfg["close_retry_jitter_seconds"]))
        pos["next_retry_at"] = _iso_after_seconds(delay)


def _close_retry_due(pos: dict[str, Any]) -> bool:
    raw = str(pos.get("next_retry_at") or "").strip()
    if not raw:
        return True
    ts = _parse_utc_timestamp(raw)
    if ts is None:
        return True
    return pd.Timestamp.now(tz="UTC") >= ts


def _close_retry_fatal_due(pos: dict[str, Any]) -> tuple[bool, str]:
    cfg = _close_retry_config()
    attempts = int(pos.get("close_attempt_count", 0) or 0)
    if attempts >= int(cfg["close_retry_max_attempts"]):
        return True, "close_retry_max_attempts_exceeded"
    first_failure = str(pos.get("first_close_failure_at") or pos.get("close_requested_at") or "").strip()
    age = _age_seconds(first_failure)
    fatal_after_minutes = float(pos.get("fatal_after_minutes") or cfg["close_retry_fatal_after_minutes"])
    if age is not None and age >= fatal_after_minutes * 60.0:
        return True, "close_retry_fatal_after_minutes_exceeded"
    return False, ""


def _validate_fatal_against_broker(
    *,
    sym: str,
    execution_adapter: ExecutionAdapter | None,
) -> tuple[str, dict[str, Any] | None, float, str]:
    """Confirm a fatal-close candidate against the live broker.

    Returns a tuple ``(verdict, broker_row, broker_qty, broker_error)`` where
    ``verdict`` is one of:

    - ``"broker_confirms_position"`` - broker still reports the symbol with qty>0;
      proceed with fatal escalation.
    - ``"broker_missing_position"`` - broker confirms no such position; the
      caller must resolve via reconcile and skip fatal.
    - ``"broker_unreachable"`` - broker lookup failed transiently; the caller
      must NOT escalate to fatal this cycle (defer to next retry).
    """
    if execution_adapter is None or isinstance(execution_adapter, ExecutionDisabledAdapter):
        return "broker_unreachable", None, 0.0, "execution_adapter_unavailable"
    broker_row, broker_err = _adapter_position_for_symbol(execution_adapter, sym)
    if broker_err:
        return "broker_unreachable", None, 0.0, broker_err
    qty = _broker_qty_from_position_row(broker_row)
    if broker_row is None or qty <= 0:
        return "broker_missing_position", broker_row, 0.0, ""
    return "broker_confirms_position", broker_row, qty, ""


def _close_retry_item_from_position(pos: dict[str, Any]) -> dict[str, Any]:
    pid = _ensure_position_identity(pos, reason="close_retry_queue")
    return {
        "position_id": pid,
        "symbol": str(pos.get("symbol", "")).strip().upper(),
        "engine": _position_engine(pos),
        "interval": _position_interval(pos),
        "side": _position_side(pos),
        "entry_timestamp": _position_opened_timestamp(pos),
        "close_state": str(pos.get("close_state") or ""),
        "close_reason": str(pos.get("close_reason") or ""),
        "close_requested_at": pos.get("close_requested_at"),
        "last_close_attempt_at": pos.get("last_close_attempt_at"),
        "close_attempt_count": int(pos.get("close_attempt_count", 0) or 0),
        "first_close_failure_at": pos.get("first_close_failure_at"),
        "next_retry_at": pos.get("next_retry_at"),
        "retry_backoff_seconds": pos.get("retry_backoff_seconds"),
        "fatal_after_minutes": pos.get("fatal_after_minutes"),
        "close_retry_reason": pos.get("close_retry_reason"),
        "last_retry_error": pos.get("last_retry_error") or pos.get("last_close_error"),
        "pending_close_qty": pos.get("pending_close_qty"),
        "broker_qty": pos.get("broker_qty"),
        "last_close_order_id": pos.get("last_close_order_id"),
        "last_close_order_status": pos.get("last_close_order_status"),
        "last_close_error": pos.get("last_close_error"),
        "updated_at": utc_now_iso(),
    }


def load_close_retry_queue(state: LivePaperState) -> dict[str, Any]:
    path = state.paths()["close_retry_queue"]
    if not path.is_file():
        return {"updated_at": "", "pending": []}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            pending = raw.get("pending") if isinstance(raw.get("pending"), list) else []
            return {"updated_at": str(raw.get("updated_at") or ""), "pending": [x for x in pending if isinstance(x, dict)]}
    except Exception as exc:  # noqa: BLE001
        logger.warning("close_retry_queue_read_failed path=%s error=%s", path, exc)
    return {"updated_at": "", "pending": []}


def save_close_retry_queue_from_state(state: LivePaperState) -> dict[str, Any]:
    pending: list[dict[str, Any]] = []
    for pos in state.open_positions:
        close_state = str(pos.get("close_state") or "").strip().upper()
        if close_state in CLOSE_RETRY_PENDING_STATES:
            pending.append(_close_retry_item_from_position(pos))
    doc = {"updated_at": utc_now_iso(), "pending": pending, "count": len(pending)}
    atomic_write_json(state.paths()["close_retry_queue"], doc)
    return doc


def merge_close_retry_queue_into_positions(
    state: LivePaperState,
    execution_events: list[dict[str, Any]] | None = None,
) -> int:
    queue = load_close_retry_queue(state)
    pending = queue.get("pending") if isinstance(queue, dict) else []
    if not isinstance(pending, list):
        return 0
    by_pid: dict[str, dict[str, Any]] = {}
    by_symbol: dict[str, list[dict[str, Any]]] = {}
    for pos in state.open_positions:
        pid = _ensure_position_identity(pos, state=state, execution_events=execution_events, reason="restart_recovery_identity")
        by_pid[pid] = pos
        by_symbol.setdefault(str(pos.get("symbol", "")).strip().upper(), []).append(pos)

    restored = 0
    retry_fields = {
        "close_state",
        "close_reason",
        "close_requested_at",
        "last_close_attempt_at",
        "close_attempt_count",
        "first_close_failure_at",
        "next_retry_at",
        "retry_backoff_seconds",
        "fatal_after_minutes",
        "close_retry_reason",
        "last_retry_error",
        "pending_close_qty",
        "broker_qty",
        "last_close_order_id",
        "last_close_order_status",
        "last_close_error",
    }
    for item in pending:
        pid = str(item.get("position_id") or "").strip()
        sym = str(item.get("symbol") or "").strip().upper()
        pos = by_pid.get(pid)
        if pos is None and sym and len(by_symbol.get(sym, [])) == 1:
            pos = by_symbol[sym][0]
        if pos is None:
            continue
        current_state = str(pos.get("close_state") or "").strip().upper()
        if current_state in CLOSE_RETRY_TERMINAL_STATES:
            continue
        for key in retry_fields:
            if item.get(key) not in (None, ""):
                pos[key] = item.get(key)
        if not str(pos.get("close_state") or "").strip():
            pos["close_state"] = "CLOSE_RETRY"
        restored += 1
        _record_execution_event(
            execution_events,
            "close_retry_state_restored",
            symbol=sym,
            position_id=pos.get("position_id"),
            close_state=pos.get("close_state"),
            reason=pos.get("close_retry_reason") or pos.get("close_reason"),
        )
    return restored


def _persist_close_retry_queue_safely(state: LivePaperState) -> None:
    try:
        save_close_retry_queue_from_state(state)
    except Exception as exc:  # noqa: BLE001
        logger.warning("close_retry_queue_save_failed error=%s", f"{type(exc).__name__}: {exc}")


def _realized_pnl_for_position_exit(pos: dict[str, Any], exit_price: float) -> float:
    entry = _position_entry_price(pos)
    qty = _position_quantity(pos)
    if _position_side(pos) == "short":
        return (float(entry) - float(exit_price)) * qty
    return (float(exit_price) - float(entry)) * qty


def _stop_loss_triggered_count(events: list[dict[str, Any]] | None) -> int:
    return sum(
        1
        for row in (events or [])
        if isinstance(row, dict)
        and row.get("event_type") == "close_position"
        and str(row.get("reason") or "") in ("stop_loss_hit", "stop_loss_breached")
    )


def _append_json_list(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict[str, Any]] = []
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                existing = [x for x in raw if isinstance(x, dict)]
        except Exception:
            existing = []
    existing.append(dict(row))
    payload = json.dumps(existing, indent=2, default=str) + "\n"
    atomic_write_text(path, payload, encoding="utf-8")


def _paper_open_row_from_position(pos: dict[str, Any]) -> dict[str, Any]:
    intent = _position_intent_context(pos)
    entry_price = _coerce_float_or_none(pos.get("entry_price", pos.get("entry")))
    stop_price = _coerce_float_or_none(pos.get("stop_price", pos.get("stop_loss", pos.get("stop"))))
    target_price = _coerce_float_or_none(pos.get("target_price", pos.get("take_profit", pos.get("target"))))
    return {
        "symbol": pos.get("symbol"),
        "position_id": pos.get("position_id"),
        "engine": pos.get("engine_label"),
        "interval": pos.get("interval"),
        "combo_label": pos.get("combo_label"),
        "config": intent["config"],
        "preset": intent["preset"],
        "entry_timestamp": pos.get("entry_timestamp"),
        "entry_date": str(pos.get("entry_date", ""))[:10],
        "intended_entry_date": intent["intended_entry_date"],
        "signal_date": intent["signal_date"],
        "signal_bar_date": pos.get("signal_bar_date"),
        "entry_price": entry_price,
        "entry": entry_price,
        "stop_price": stop_price,
        "stop_loss": stop_price,
        "target_price": target_price,
        "take_profit": target_price,
        "rr": intent["rr"],
        "dynamic_rr": _coerce_float_or_none(pos.get("dynamic_rr")),
        "resistance_rr": _coerce_float_or_none(pos.get("resistance_rr")),
        "final_rr": _coerce_float_or_none(pos.get("final_rr")),
        "trend_strength_label": pos.get("trend_strength_label"),
        "risk_per_share": intent["risk_per_share"],
        "risk_amount": intent["risk_amount"],
        "risk_pct_from_entry": _coerce_float_or_none(pos.get("risk_pct_from_entry")),
        "shares": _coerce_float_or_none(pos.get("shares", pos.get("paper_shares"))),
        "dollar_risk": _coerce_float_or_none(pos.get("dollar_risk", pos.get("initial_risk_dollars"))),
        "score": _coerce_float_or_none(pos.get("score")),
        "rank": pos.get("rank"),
        "notes": pos.get("notes"),
        "reason": pos.get("reason"),
        "delayed_entry_bars_effective": pos.get("delayed_entry_bars_effective"),
        "delayed_relax_pct_effective": pos.get("delayed_relax_pct_effective"),
        "live_mode_relaxed": bool(pos.get("live_mode_relaxed", False)),
        "source_signal_type": pos.get("source_signal_type"),
        "original_signal_score": _coerce_float_or_none(pos.get("original_signal_score")),
        "original_signal_rank": pos.get("original_signal_rank"),
        "original_signal_notes": pos.get("original_signal_notes"),
        "original_signal_reason": pos.get("original_signal_reason"),
        "status": "open",
    }


def export_paper_trade_details(state: LivePaperState) -> None:
    rows = [_paper_open_row_from_position(p) for p in state.open_positions]
    PAPER_OPEN_POSITIONS_CSV.parent.mkdir(parents=True, exist_ok=True)
    with PAPER_OPEN_POSITIONS_CSV.open("w", newline="", encoding="utf-8") as f:
        import csv as _csv

        w = _csv.DictWriter(f, fieldnames=PAPER_OPEN_EXPORT_FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in PAPER_OPEN_EXPORT_FIELDS})
    payload = json.dumps(rows, indent=2, default=str) + "\n"
    atomic_write_text(PAPER_OPEN_POSITIONS_DETAILED_JSON, payload, encoding="utf-8")


def validate_universe_for_live_paper(
    universe_file: Path,
    *,
    allow_universe_override: bool,
    universe_explicit_cli: bool,
) -> Path:
    """
    Resolve universe path and enforce STRICT validated parity or DEBUG override (orchestration only).

    When ``allow_universe_override`` and ``universe_explicit_cli`` are both True, only checks
    that the file exists and is readable. Otherwise requires the locked paper universe path.
    """
    uni_path = resolve_universe_path(universe_file)
    if allow_universe_override and universe_explicit_cli:
        ensure_universe_file_readable(uni_path)
        msg = f"DEBUG universe override allowed: {uni_path.resolve()}"
        logger.info("%s", msg)
        print(msg, flush=True)
        return uni_path
    validate_paper_universe_path(uni_path)
    logger.info(
        "STRICT universe parity mode active (required file: %s)",
        str(PAPER_UNIVERSE_FILE.resolve()),
    )
    print("STRICT universe parity mode active", flush=True)
    return uni_path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clip_to_fully_closed_bars(
    df: pd.DataFrame,
    interval: str,
    as_of: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, str | None]:
    """
    Drop the newest row while it is still inside the incomplete period relative to ``as_of`` (UTC).

    Heuristic (conservative): weekly bars complete after Friday 21:00 UTC of that ISO week;
    daily bars complete after the session day (next day ~20:00 UTC).
    """
    if df is None or df.empty:
        return df, None
    as_of = pd.Timestamp.now(tz="UTC") if as_of is None else pd.Timestamp(as_of)
    if as_of.tzinfo is None:
        as_of = as_of.tz_localize("UTC")
    d = df.copy()
    iv = interval.lower().strip()
    while len(d) > 0:
        last_raw = d.index[-1]
        last = pd.Timestamp(last_raw)
        if last.tzinfo is None:
            last = last.tz_localize("UTC")
        else:
            last = last.tz_convert("UTC")
        trim = False
        if iv in ("1wk", "1w", "weekly"):
            d0 = last.normalize()
            days_to_fri = (4 - d0.weekday()) % 7
            fri = d0 + pd.Timedelta(days=days_to_fri)
            week_end = fri + pd.Timedelta(hours=21)
            trim = as_of < week_end
        elif iv in ("1d", "d", "day"):
            bar_day_end = last.normalize() + pd.Timedelta(days=1, hours=20)
            trim = as_of < bar_day_end
        else:
            trim = False
        if not trim:
            break
        d = d.iloc[:-1]
    if d.empty:
        return d, None
    last_bar_date = str(pd.Timestamp(d.index[-1]).date())
    return d, last_bar_date


def _align_bench_to_df(bench_df: pd.DataFrame, d: pd.DataFrame) -> pd.DataFrame:
    if bench_df.empty or d.empty:
        return bench_df
    b = bench_df.copy()
    b = b.reindex(d.index).ffill()
    return b


def run_symbol_trades(
    sym: str,
    d: pd.DataFrame,
    bench_df: pd.DataFrame,
    cfg: Any,
    app: AppConfig,
    uni_source: str,
    signal_debug: Any = None,
    trade_funnel: Any = None,
    engine: str = "unknown",
    post_sim_near_last_bar_tap: Any = None,
) -> list[dict[str, Any]]:
    from algo_scanner.backtest.fib_quality import _trades_for_symbol
    from analytics.delayed_entry_experiment import new_delayed_entry_counters

    d_delay = int(getattr(cfg, "delayed_entry_bars", 0) or 0)
    delayed_entry_counters = new_delayed_entry_counters() if d_delay > 0 else None

    b = _align_bench_to_df(bench_df, d)
    return _trades_for_symbol(
        sym,
        d,
        cfg,
        b,
        app.timeframe,
        uni_source,
        delayed_entry_bars=d_delay,
        delayed_entry_counters=delayed_entry_counters,
        research_min_close_position_in_range=getattr(cfg, "research_min_close_position_in_range", None),
        research_min_body_range_ratio=getattr(cfg, "research_min_body_range_ratio", None),
        research_must_reach_min_r=getattr(cfg, "research_must_reach_min_r", None),
        research_must_reach_within_bars=getattr(cfg, "research_must_reach_within_bars", None),
        signal_debug=signal_debug,
        trade_funnel=trade_funnel,
        engine=engine,
        post_sim_near_last_bar_tap=post_sim_near_last_bar_tap,
    )


def _signal_bar_date_str(df: pd.DataFrame, candidate_signal_bar: int) -> str:
    i = int(candidate_signal_bar)
    if i < 0 or i >= len(df):
        return ""
    return str(pd.Timestamp(df.index[i]).date())


def _trade_from_live_candidate(
    candidate: LiveSignalCandidate,
    *,
    sym: str,
    df: pd.DataFrame,
) -> dict[str, Any]:
    signal_date = str(candidate.signal_bar_time)[:10]
    candidate_signal_bar = max(0, len(df) - 1)
    for i in range(len(df) - 1, -1, -1):
        if str(pd.Timestamp(df.index[i]).date()) == signal_date:
            candidate_signal_bar = int(i)
            break
    entry_price = _coerce_float_or_none(getattr(candidate, "entry_price", None))
    if entry_price is None:
        entry_price = _coerce_float_or_none(getattr(candidate, "entry", None))
    stop_price = _coerce_float_or_none(getattr(candidate, "stop_price", None))
    if stop_price is None:
        stop_price = _coerce_float_or_none(getattr(candidate, "stop", None))
    target_price = _coerce_float_or_none(getattr(candidate, "target_price", None))
    if target_price is None:
        target_price = _coerce_float_or_none(getattr(candidate, "target", None))
    if entry_price is None or stop_price is None or target_price is None:
        raise ValueError(
            f"external signal missing required prices symbol={sym} entry={entry_price} stop={stop_price} target={target_price}"
        )
    print("[DEBUG SIGNAL]", flush=True)
    print(sym, entry_price, stop_price, target_price, flush=True)

    risk = float(entry_price) - float(stop_price)
    trade = {
        "symbol": sym,
        "candidate_signal_bar": int(candidate_signal_bar),
        "entry_bar": int(candidate_signal_bar),
        "entry_date": signal_date,
        "entry": float(entry_price),
        "stop": float(stop_price),
        "target": float(target_price),
        "r_multiple": float(candidate.rr),
        "dynamic_rr": _coerce_float_or_none(getattr(candidate, "dynamic_rr", None)),
        "resistance_rr": _coerce_float_or_none(getattr(candidate, "resistance_rr", None)),
        "final_rr": _coerce_float_or_none(getattr(candidate, "final_rr", None)),
        "trend_strength_label": getattr(candidate, "trend_strength_label", None),
        "risk_per_share": float(risk),
        "exit_reason": "open_last_bar_live",
        "bars_held": 0,
        "return_pct": 0.0,
        "score": _coerce_float_or_none(getattr(candidate, "score", None)),
        "rank": getattr(candidate, "rank", None),
        "notes": str(getattr(candidate, "notes", "") or ""),
        "reason": str(getattr(candidate, "reason", getattr(candidate, "reason_summary", "")) or ""),
        "source_signal_type": "external_live_signal",
        "original_signal_score": _coerce_float_or_none(getattr(candidate, "score", None)),
        "original_signal_rank": getattr(candidate, "rank", None),
        "original_signal_notes": str(getattr(candidate, "notes", "") or ""),
        "original_signal_reason": str(getattr(candidate, "reason_summary", "") or ""),
    }
    print("[DEBUG TRADE CREATED]", flush=True)
    print(sym, trade["entry"], trade["stop"], trade["target"], flush=True)
    return trade


def find_matching_trade(open_pos: dict[str, Any], trades: list[dict[str, Any]]) -> dict[str, Any] | None:
    cs = int(open_pos.get("candidate_signal_bar", -2))
    ed = str(open_pos.get("entry_date", ""))[:10]
    for t in trades:
        if int(t.get("candidate_signal_bar", -3)) == cs and str(t.get("entry_date", ""))[:10] == ed:
            return t
    return None


def build_position_from_trade(
    t: dict[str, Any],
    *,
    combo_label: str,
    interval: str,
    df: pd.DataFrame,
    last_checked_bar_date: str,
    engine_label: str = "daily",
    preset_name: str | None = None,
    live_mode_relaxed: bool = False,
) -> dict[str, Any]:
    sig_date = _signal_bar_date_str(df, int(t.get("candidate_signal_bar", 0)))
    entry_timestamp = utc_now_iso()
    side = "short" if str(t.get("side") or "").strip().lower() == "short" else "long"
    entry_px = float(t.get("entry", 0.0) or 0.0)
    stop_px = float(t.get("stop", 0.0) or 0.0)
    target_px = float(t.get("target", 0.0) or 0.0)
    risk_per_share = abs(entry_px - stop_px)
    rr_value = _coerce_float_or_none(t.get("final_rr"))
    if rr_value is None or rr_value <= 0:
        rr_value = _coerce_float_or_none(t.get("r_multiple"))
    if (rr_value is None or rr_value <= 0) and risk_per_share > 1e-12:
        rr_value = ((entry_px - target_px) / risk_per_share) if side == "short" else ((target_px - entry_px) / risk_per_share)
    preset_label = str(preset_name or combo_label)
    intended_entry_date = str(t.get("entry_date", ""))[:10]
    position_id = _canonical_position_id(
        symbol=str(t.get("symbol", "")),
        engine=str(engine_label),
        interval=str(interval),
        side=side,
        entry_timestamp=entry_timestamp,
    )
    return {
        "symbol": str(t.get("symbol", "")),
        "position_id": position_id,
        "combo_label": combo_label,
        "interval": interval,
        "engine_label": str(engine_label),
        "preset_name": str(preset_name or combo_label),
        "signal_bar_date": sig_date,
        "candidate_signal_bar": int(t.get("candidate_signal_bar", 0)),
        "entry_bar": int(t.get("entry_bar", 0)),
        "entry_date": intended_entry_date,
        "intended_entry_date": intended_entry_date,
        "entry_price": entry_px,
        "entry": entry_px,
        "stop": stop_px,
        "target": target_px,
        "stop_price": stop_px,
        "target_price": target_px,
        "stop_loss": stop_px,
        "take_profit": target_px,
        "expected_r_from_backtest": float(t.get("r_multiple", 0.0) or 0.0),
        "rr": rr_value,
        "dynamic_rr": _coerce_float_or_none(t.get("dynamic_rr")),
        "resistance_rr": _coerce_float_or_none(t.get("resistance_rr")),
        "final_rr": _coerce_float_or_none(t.get("final_rr")),
        "trend_strength_label": t.get("trend_strength_label"),
        "bars_held": int(t.get("bars_held", 0) or 0),
        "entry_timestamp": entry_timestamp,
        "signal_date": sig_date,
        "config": preset_label,
        "preset": preset_label,
        "side": side,
        "risk_per_share": float(risk_per_share),
        "risk_amount": None,
        "risk_pct_from_entry": (
            float(risk_per_share) / entry_px
            if entry_px > 0
            else None
        ),
        "score": _coerce_float_or_none(t.get("score")),
        "rank": t.get("rank"),
        "candidate_rank": t.get("candidate_rank"),
        "candidate_score": _coerce_float_or_none(t.get("candidate_score")),
        "notes": str(t.get("notes", "") or ""),
        "reason": str(t.get("reason", "") or ""),
        "delayed_entry_bars_effective": t.get("delayed_entry_bars"),
        "delayed_relax_pct_effective": t.get("delayed_trigger_relaxation_pct"),
        "live_mode_relaxed": bool(live_mode_relaxed),
        "source_signal_type": str(t.get("source_signal_type", "internal_trade_reconstruction")),
        "original_signal_score": _coerce_float_or_none(t.get("original_signal_score")),
        "original_signal_rank": t.get("original_signal_rank"),
        "original_signal_notes": t.get("original_signal_notes"),
        "original_signal_reason": t.get("original_signal_reason"),
        "status": "open",
        "entry_alert_sent": False,
        "exit_alert_sent": False,
        "last_checked_bar_date": last_checked_bar_date,
        "source": "live_paper_monitor",
        "engine_trade_extras": {
            k: t.get(k)
            for k in (
                "exit_reason",
                "exit_bar",
                "mae_r",
                "mfe_r",
                "delayed_entry_bars",
                "entry_delay_applied",
                "delayed_confirm_mode",
                "delayed_trigger_price",
                "delayed_trigger_relaxation_pct",
            )
            if k in t
        },
    }


def _penultimate_bar_date_str(df: pd.DataFrame) -> str | None:
    if df is None or len(df.index) < 2:
        return None
    return str(pd.Timestamp(df.index[-2]).date())


def trade_is_relevant_to_last_bar(
    t: dict[str, Any],
    df: pd.DataFrame,
    last_bar_date: str,
    *,
    live_mode_relaxed: bool = False,
) -> bool:
    lb = str(last_bar_date)[:10]
    sig = _signal_bar_date_str(df, int(t.get("candidate_signal_bar", -1)))
    ent = str(t.get("entry_date", ""))[:10]
    if sig == lb or ent == lb:
        return True
    if live_mode_relaxed:
        prev = _penultimate_bar_date_str(df)
        if prev and (sig == prev or ent == prev):
            return True
    return False


def _last_bar_debug_flags(
    trades: list[dict[str, Any]],
    df: pd.DataFrame,
    last_bar_date: str,
    *,
    live_mode_relaxed: bool = False,
) -> tuple[bool, bool, bool]:
    """
    Read-only snapshot for logging: per trade list, whether any trade has
    entry_date <= last bar, entry_date == last bar, or signal bar on last bar.
    """
    lb = str(last_bar_date)[:10]
    try:
        last_d = pd.Timestamp(lb).date()
    except Exception:
        return False, False, False
    prev_d: Any = None
    if live_mode_relaxed:
        ps = _penultimate_bar_date_str(df)
        if ps:
            try:
                prev_d = pd.Timestamp(ps).date()
            except Exception:
                prev_d = None
    any_entry_le = False
    any_entry_eq = False
    any_signal_on_last = False
    prev_s = _penultimate_bar_date_str(df)
    for t in trades:
        ent_raw = str(t.get("entry_date", ""))[:10]
        if ent_raw:
            try:
                ed = pd.Timestamp(ent_raw).date()
                if ed <= last_d:
                    any_entry_le = True
                if ed == last_d or (live_mode_relaxed and prev_d is not None and ed == prev_d):
                    any_entry_eq = True
            except Exception:
                pass
        sig = _signal_bar_date_str(df, int(t.get("candidate_signal_bar", 0)))
        if sig and (sig == lb or (live_mode_relaxed and prev_s and sig == prev_s)):
            any_signal_on_last = True
    return any_entry_le, any_entry_eq, any_signal_on_last


def count_signals_rejected_as_old(
    sym: str,
    combo_label: str,
    interval: str,
    df: pd.DataFrame,
    trades: list[dict[str, Any]],
    last_bar_date: str,
    state: LivePaperState,
    *,
    live_mode_relaxed: bool = False,
) -> int:
    """How many last-bar-relevant trades would skip entry because signal was already processed (dedup)."""
    n = 0
    for t in trades:
        if not trade_is_relevant_to_last_bar(t, df, last_bar_date, live_mode_relaxed=live_mode_relaxed):
            continue
        sig_date = _signal_bar_date_str(df, int(t.get("candidate_signal_bar", 0)))
        sk = signal_dedup_key(sym, combo_label, sig_date, interval)
        if state.has_processed_signal(sk):
            n += 1
    return n


def apply_stress_r(t: dict[str, Any]) -> tuple[float, float]:
    """Returns (actual_r_live, exit_price)."""
    tt = dict(t)
    tt["effective_exit"] = float(tt["entry"]) + float(tt.get("pnl_per_share", 0.0))
    st = paper_stress_trade(tt)
    ar = float(st.get("stressed_r_multiple", t.get("r_multiple", 0.0)))
    ex = float(st.get("effective_exit", tt["effective_exit"]))
    return ar, ex


SIGNAL_CSV_FIELDS = [
    "run_timestamp",
    "symbol",
    "combo_label",
    "interval",
    "signal_bar_date",
    "entry_date",
    "candidate_signal_bar",
    "entry",
    "stop",
    "target",
    "entry_price",
    "stop_loss",
    "take_profit",
    "risk_per_share",
    "risk_amount",
    "rr",
    "config",
    "preset",
    "signal_date",
    "intended_entry_date",
    "position_id",
    "expected_r",
    "last_bar_date",
    "paper_entry_open",
    "paper_shares",
    "submitted_order_type",
    "submitted_limit_price",
    "submitted_stop_price",
    "actual_filled_avg_price",
    "fill_slippage_r",
    "live_reference_price",
    "live_reference_price_source",
    "live_reference_price_method",
    "live_reference_price_timestamp",
    "quote_bid",
    "quote_ask",
    "quote_mid",
    "quote_spread",
    "quote_spread_pct",
]

CLOSED_CSV_FIELDS = [
    "run_timestamp",
    "symbol",
    "combo_label",
    "interval",
    "entry_date",
    "intended_entry_date",
    "signal_date",
    "exit_date",
    "entry_price",
    "entry",
    "stop_price",
    "stop_loss",
    "target_price",
    "take_profit",
    "risk_per_share",
    "risk_amount",
    "rr",
    "config",
    "preset",
    "position_id",
    "paper_entry_open",
    "paper_shares",
    "exit_price",
    "exit_reason",
    "gap_through_stop",
    "loss_beyond_stop_reason",
    "expected_r_from_backtest",
    "actual_r_live",
    "bars_held",
    "stress_config",
    "submitted_order_type",
    "submitted_limit_price",
    "submitted_stop_price",
    "actual_filled_avg_price",
    "fill_slippage_r",
]

LIVE_RUN_HISTORY_FIELDS = [
    "run_timestamp",
    "mode",
    "interval",
    "combos",
    "n_symbols_attempted",
    "n_symbols_processed",
    "n_symbols_skipped",
    "n_open_positions_before",
    "n_open_positions_after",
    "n_new_signals",
    "n_new_signals_daily",
    "n_new_signals_weekly",
    "n_new_entries",
    "n_new_exits",
    "n_alerts_sent",
    "n_alerts_failed",
    "n_errors",
    "errors_sample",
    "runtime_seconds",
    "timestamp",
    "run_status",
    "execution_adapter_ok",
    "orders_attempted",
    "orders_success",
    "orders_failed",
    "signals_generated",
    "open_positions_count",
    "duration_sec",
    "error_summary",
]

PAPER_OPEN_EXPORT_FIELDS = [
    "symbol",
    "position_id",
    "engine",
    "interval",
    "combo_label",
    "config",
    "preset",
    "entry_timestamp",
    "entry_date",
    "intended_entry_date",
    "signal_date",
    "signal_bar_date",
    "entry_price",
    "entry",
    "stop_price",
    "stop_loss",
    "target_price",
    "take_profit",
    "rr",
    "dynamic_rr",
    "resistance_rr",
    "final_rr",
    "trend_strength_label",
    "risk_per_share",
    "risk_amount",
    "risk_pct_from_entry",
    "shares",
    "dollar_risk",
    "score",
    "rank",
    "notes",
    "reason",
    "delayed_entry_bars_effective",
    "delayed_relax_pct_effective",
    "live_mode_relaxed",
    "source_signal_type",
    "original_signal_score",
    "original_signal_rank",
    "original_signal_notes",
    "original_signal_reason",
    "status",
]

PAPER_CLOSED_EXPORT_FIELDS = PAPER_OPEN_EXPORT_FIELDS + [
    "exit_timestamp",
    "exit_date",
    "exit_price",
    "exit_reason",
    "gap_through_stop",
    "loss_beyond_stop_reason",
    "realized_pnl_dollars",
    "realized_r",
    "hold_bars_or_days_if_available",
]


def _process_stop_loss_exit(
    *,
    sym: str,
    combo_label: str,
    interval: str,
    pos: dict[str, Any],
    stop_hit: dict[str, Any],
    state: LivePaperState,
    run_timestamp: str,
    dry_run: bool,
    telegram_dry_run: bool,
    send_message: Any,
    build_exit: Any,
    output_scope: str,
    stop_check_df: pd.DataFrame | None,
    portfolio_state: dict[str, Any] | None,
    execution_adapter: ExecutionAdapter | None,
    execution_events: list[dict[str, Any]] | None,
) -> tuple[int, int, int]:
    alerts_sent = 0
    alerts_failed = 0
    exit_px = float(stop_hit["exit_price"])
    side = str(stop_hit.get("side") or _position_side(pos))
    qty = _position_quantity(pos)
    entry_px = _position_entry_price(pos)
    stop_loss = float(stop_hit.get("stop_loss") or (_position_stop_loss(pos) or 0.0))
    take_profit = _coerce_float_or_none(stop_hit.get("take_profit"))
    if take_profit is None:
        take_profit = _position_take_profit(pos)
    current_price = _coerce_float_or_none(stop_hit.get("current_price"))
    bar_timestamp = str(stop_hit.get("bar_timestamp") or "")
    price_source = str(stop_hit.get("price_source") or stop_hit.get("source") or "").strip()
    price_method = str(stop_hit.get("price_method") or "").strip()
    price_timestamp = str(stop_hit.get("price_timestamp") or bar_timestamp or "").strip()
    price_age_seconds = _coerce_float_or_none(stop_hit.get("price_age_seconds"))
    price_stale = bool(stop_hit.get("price_stale", False))
    order_reason = str(stop_hit.get("reason") or "stop_loss_breached")
    exit_reason = str(stop_hit.get("exit_reason") or ("take_profit_hit" if order_reason == "take_profit_hit" else "stop_loss_hit"))
    current_r = _current_r_for_position(pos, current_price if current_price is not None else exit_px)
    try:
        exit_date = str(pd.Timestamp(bar_timestamp).date())
    except Exception:
        exit_date = bar_timestamp[:10]
    actual_r = _actual_r_for_position_exit(pos, exit_px)
    gap_through_stop = bool(stop_hit.get("gap_through_stop", False))
    loss_beyond_stop_reason = str(
        stop_hit.get("loss_beyond_stop_reason") or _loss_beyond_stop_reason(pos, exit_px)
    ).strip()
    exp_bt = float(pos.get("expected_r_from_backtest", 0.0) or 0.0)
    ok = True
    text = build_exit(
        symbol=sym,
        combo_label=combo_label,
        interval=interval,
        entry_date=str(pos.get("entry_date", ""))[:10],
        exit_date=exit_date,
        entry_price=float(entry_px),
        exit_price=float(exit_px),
        exit_reason=exit_reason,
        actual_r_live=float(actual_r),
        bars_held="",
        stress_summary=stress_config_summary(PAPER_STRESS),
        expected_r_from_backtest=exp_bt,
        delta_r=float(actual_r) - exp_bt,
    )

    adapter_name = type(execution_adapter).__name__ if execution_adapter is not None else ""
    logger.warning(
        "[execution] type=forced_exit action=close_position symbol=%s side=%s reason=%s exit_price=%s bar_timestamp=%s",
        sym,
        side,
        order_reason,
        exit_px,
        bar_timestamp,
    )

    exec_ok = True
    exec_result: dict[str, Any] = {
        "accepted": True,
        "adapter": adapter_name,
        "event": "close_position",
        "symbol": sym,
    }
    already_closed = False
    _mark_close_workflow(pos, state_name="CLOSE_REQUIRED", reason=order_reason, broker_qty=qty)
    _persist_close_retry_queue_safely(state)
    _record_execution_event(
        execution_events,
        "exit_breach",
        symbol=sym,
        adapter=adapter_name,
        reason=order_reason,
        triggered_rule=order_reason,
        side=side,
        qty=qty,
        current_price=current_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        current_r=current_r,
        exit_price=exit_px,
        bar_timestamp=bar_timestamp,
        source=str(stop_hit.get("source") or "ohlc_bar"),
        price_source=price_source,
        price_method=price_method,
        price_timestamp=price_timestamp,
        price_age_seconds=price_age_seconds,
        price_stale=price_stale,
        close_state="CLOSE_REQUIRED",
    )
    if execution_adapter is not None:
        logger.info("[execution] type=attempt action=close_position symbol=%s adapter=%s reason=%s", sym, adapter_name, order_reason)
        _mark_close_workflow(pos, state_name="CLOSE_REQUESTED", reason=order_reason, broker_qty=qty)
        _persist_close_retry_queue_safely(state)
        _record_execution_event(
            execution_events,
            "close_order_attempt",
            symbol=sym,
            adapter=adapter_name,
            reason=order_reason,
            triggered_rule=order_reason,
            side=side,
            qty=qty,
            current_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            current_r=current_r,
            exit_price=exit_px,
            bar_timestamp=bar_timestamp,
            close_state="CLOSE_REQUESTED",
        )
        _append_execution_order_event(
            state,
            event_type="close_order_attempt",
            symbol=sym,
            side=side,
            qty=qty,
            entry=entry_px,
            stop=stop_loss,
            target=take_profit,
            current_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            exit_price=exit_px,
            bar_timestamp=bar_timestamp,
            current_r=current_r,
            triggered_rule=order_reason,
            close_state="CLOSE_REQUESTED",
            close_reason=order_reason,
            attempt_count=pos.get("close_attempt_count"),
            broker_order_id=pos.get("last_close_order_id"),
            broker_status=pos.get("last_close_order_status"),
            source=str(stop_hit.get("source") or "ohlc_bar"),
            price_source=price_source,
            price_method=price_method,
            price_timestamp=price_timestamp,
            price_age_seconds=price_age_seconds,
            price_stale=price_stale,
            gap_through_stop=gap_through_stop,
            loss_beyond_stop_reason=loss_beyond_stop_reason,
            managed_by_strategy=True,
            adapter=adapter_name,
            reason=order_reason,
        )
        try:
            exec_result = execution_adapter.close_position(sym)
        except Exception as exc:  # noqa: BLE001
            exec_result = {
                "accepted": False,
                "adapter": adapter_name,
                "event": "close_order_failed",
                "error": f"{type(exc).__name__}: {exc}",
                "symbol": sym,
            }
            logger.exception("[execution] type=failure action=close_position symbol=%s adapter=%s reason=%s", sym, adapter_name, order_reason)
        exec_ok = bool(exec_result.get("accepted", False))
        _mark_close_workflow(
            pos,
            state_name="CLOSE_SUBMITTED" if exec_ok else "CLOSE_RETRY",
            reason=order_reason,
            broker_qty=qty,
            order_id=str(exec_result.get("order_id") or exec_result.get("broker_order_id") or ""),
            order_status=str(exec_result.get("status") or exec_result.get("event") or ""),
            error=str(exec_result.get("error") or "") or None,
        )
        _persist_close_retry_queue_safely(state)
        already_closed = str(exec_result.get("error") or "").strip() == "no_open_position"
        if already_closed:
            exec_ok = True
            logger.warning("[execution] type=idempotent_close action=close_position symbol=%s reason=no_open_position", sym)
        if bool(exec_result.get("dry_run", False)):
            _record_execution_event(
                execution_events,
                "close_order_dry_run",
                symbol=sym,
                adapter=adapter_name,
                reason=order_reason,
                triggered_rule=order_reason,
                side=side,
                qty=qty,
                current_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                current_r=current_r,
                close_state="CLOSE_SUBMITTED",
                result=exec_result,
            )
            _append_execution_order_event(
                state,
                event_type="close_order_dry_run",
                symbol=sym,
                side=side,
                qty=qty,
                entry=entry_px,
                stop=stop_loss,
                target=take_profit,
                current_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                exit_price=exit_px,
                bar_timestamp=bar_timestamp,
                current_r=current_r,
                triggered_rule=order_reason,
                close_state=str(pos.get("close_state") or "CLOSE_SUBMITTED"),
                close_reason=order_reason,
                attempt_count=pos.get("close_attempt_count"),
                broker_order_id=pos.get("last_close_order_id"),
                broker_status=pos.get("last_close_order_status"),
                source=str(stop_hit.get("source") or "ohlc_bar"),
                gap_through_stop=gap_through_stop,
                loss_beyond_stop_reason=loss_beyond_stop_reason,
                managed_by_strategy=True,
                adapter=adapter_name,
                reason=order_reason,
                result=exec_result,
                accepted=True,
                dry_run=True,
            )
        if not bool(exec_result.get("accepted", False)) and not already_closed:
            logger.warning(
                "[execution] type=rejection action=close_position symbol=%s adapter=%s reason=%s details=%s",
                sym,
                adapter_name,
                order_reason,
                exec_result,
            )
            _record_execution_event(
                execution_events,
                "close_order_failed" if str(exec_result.get("event") or "") == "close_order_failed" else "close_order_rejected",
                symbol=sym,
                adapter=adapter_name,
                reason=order_reason,
                triggered_rule=order_reason,
                side=side,
                qty=qty,
                current_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                current_r=current_r,
                close_state="CLOSE_RETRY",
                result=exec_result,
            )
            _append_execution_order_event(
                state,
                event_type="close_order_failed" if str(exec_result.get("event") or "") == "close_order_failed" else "close_order_rejected",
                symbol=sym,
                side=side,
                qty=qty,
                entry=entry_px,
                stop=stop_loss,
                target=take_profit,
                current_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                exit_price=exit_px,
                bar_timestamp=bar_timestamp,
                current_r=current_r,
                triggered_rule=order_reason,
                close_state=str(pos.get("close_state") or "CLOSE_RETRY"),
                close_reason=order_reason,
                attempt_count=pos.get("close_attempt_count"),
                broker_order_id=pos.get("last_close_order_id"),
                broker_status=pos.get("last_close_order_status"),
                source=str(stop_hit.get("source") or "ohlc_bar"),
                gap_through_stop=gap_through_stop,
                loss_beyond_stop_reason=loss_beyond_stop_reason,
                managed_by_strategy=True,
                adapter=adapter_name,
                reason=order_reason,
                result=exec_result,
                accepted=False,
            )
        else:
            close_success_event_type = "close_order_already_closed" if already_closed else (
                "close_order_filled"
                if str(exec_result.get("status") or "").strip().lower() in ("filled", "closed")
                else "close_order_submitted"
            )
            _record_execution_event(
                execution_events,
                close_success_event_type,
                symbol=sym,
                adapter=adapter_name,
                reason=order_reason,
                triggered_rule=order_reason,
                side=side,
                qty=qty,
                current_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                current_r=current_r,
                close_state="CLOSE_SUBMITTED",
                result=exec_result,
            )
            _append_execution_order_event(
                state,
                event_type=close_success_event_type,
                symbol=sym,
                side=side,
                qty=qty,
                entry=entry_px,
                stop=stop_loss,
                target=take_profit,
                current_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                exit_price=exit_px,
                bar_timestamp=bar_timestamp,
                current_r=current_r,
                triggered_rule=order_reason,
                close_state=str(pos.get("close_state") or "CLOSE_SUBMITTED"),
                close_reason=order_reason,
                attempt_count=pos.get("close_attempt_count"),
                broker_order_id=pos.get("last_close_order_id"),
                broker_status=pos.get("last_close_order_status"),
                source=str(stop_hit.get("source") or "ohlc_bar"),
                gap_through_stop=gap_through_stop,
                loss_beyond_stop_reason=loss_beyond_stop_reason,
                managed_by_strategy=True,
                adapter=adapter_name,
                reason=order_reason,
                result=exec_result,
                accepted=True,
                dry_run=bool(exec_result.get("dry_run", False)),
            )

    _record_execution_event(
        execution_events,
        "close_position",
        symbol=sym,
        adapter=adapter_name,
        side=side,
        qty=qty,
        entry=entry_px,
        stop=stop_loss,
        target=take_profit,
        current_price=current_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        exit_price=exit_px,
        bar_timestamp=bar_timestamp,
        reason=order_reason,
        triggered_rule=order_reason,
        accepted=bool(exec_ok),
        current_r=current_r,
        close_state=str(pos.get("close_state") or ""),
        result=exec_result,
    )
    _append_execution_order_event(
        state,
        event_type="close_position",
        symbol=sym,
        side=side,
        qty=qty,
        entry=entry_px,
        stop=stop_loss,
        target=take_profit,
        current_price=current_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        exit_price=exit_px,
        bar_timestamp=bar_timestamp,
        current_r=current_r,
        triggered_rule=order_reason,
        close_state=str(pos.get("close_state") or ""),
        close_reason=order_reason,
        attempt_count=pos.get("close_attempt_count"),
        broker_order_id=pos.get("last_close_order_id"),
        broker_status=pos.get("last_close_order_status"),
        source=str(stop_hit.get("source") or "ohlc_bar"),
        price_source=price_source,
        price_method=price_method,
        price_timestamp=price_timestamp,
        price_age_seconds=price_age_seconds,
        price_stale=price_stale,
        gap_through_stop=gap_through_stop,
        loss_beyond_stop_reason=loss_beyond_stop_reason,
        managed_by_strategy=True,
        adapter=adapter_name,
        status="closed" if exec_ok and not already_closed else ("already_closed" if already_closed else "rejected"),
        reason=order_reason,
        result={**exec_result, "raw_response": {"stop_hit": stop_hit, "adapter_result": exec_result}},
        accepted=bool(exec_ok),
        dry_run=bool(exec_result.get("dry_run", False)),
    )

    if not exec_ok:
        _persist_close_retry_queue_safely(state)
        alerts_failed += 1
        return 0, alerts_sent, alerts_failed
    if bool(exec_result.get("dry_run", False)):
        pos["close_state"] = "CLOSE_REQUIRED"
        pos["last_close_order_status"] = "dry_run_not_submitted"
        pos["last_close_error"] = "dry_run_close_not_confirmed"
        _schedule_close_retry(pos, reason=order_reason, error="dry_run_close_not_confirmed", force_due=True)
        _persist_close_retry_queue_safely(state)
        alerts_failed += 1
        return 0, alerts_sent, alerts_failed
    if execution_adapter is not None and not bool(exec_result.get("dry_run", False)):
        broker_closed, broker_qty, verify_error = _verify_close_with_broker(
            sym=sym,
            pos=pos,
            execution_adapter=execution_adapter,
            execution_events=execution_events,
            reason=order_reason,
            adapter_name=adapter_name,
        )
        if not broker_closed:
            _append_execution_order_event(
                state,
                event_type="close_order_retry" if broker_qty > 0 else "close_order_failed",
                symbol=sym,
                side=side,
                qty=broker_qty,
                entry=entry_px,
                stop=stop_loss,
                target=take_profit,
                current_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                exit_price=exit_px,
                bar_timestamp=bar_timestamp,
                current_r=current_r,
                triggered_rule=order_reason,
                adapter=adapter_name,
                status=str(pos.get("close_state") or "CLOSE_RETRY"),
                reason=order_reason,
                result={"accepted": False, "error": verify_error, "raw_response": {"broker_qty": broker_qty}},
                accepted=False,
            )
            _persist_close_retry_queue_safely(state)
            alerts_failed += 1
            return 0, alerts_sent, alerts_failed

    if not dry_run:
        if telegram_dry_run:
            logger.info("[telegram_dry_run] FORCED EXIT %s", text[:500])
        else:
            ok = send_message(text, parse_mode=None)
    else:
        ok = True
        logger.info("[dry_run] FORCED EXIT %s", text[:300])
    if ok:
        alerts_sent += 1
    else:
        alerts_failed += 1

    realized_pnl = _realized_pnl_for_position_exit(pos, exit_px)
    realized_r = (
        float(realized_pnl) / float(pos.get("dollar_risk", 0.0))
        if float(pos.get("dollar_risk", 0.0) or 0.0) > 0
        else None
    )
    if not dry_run:
        closed_detail = {
            "symbol": sym,
            "engine": str(pos.get("engine_label", "")),
            "entry_timestamp": pos.get("entry_timestamp"),
            "entry_date": str(pos.get("entry_date", ""))[:10],
            "signal_bar_date": pos.get("signal_bar_date"),
            "entry_price": float(entry_px),
            "stop_price": float(pos.get("stop_price", pos.get("stop", 0.0)) or 0.0),
            "target_price": float(pos.get("target_price", pos.get("target", 0.0)) or 0.0),
            "risk_per_share": _coerce_float_or_none(pos.get("risk_per_share")),
            "risk_pct_from_entry": _coerce_float_or_none(pos.get("risk_pct_from_entry")),
            "shares": qty,
            "dollar_risk": _coerce_float_or_none(pos.get("dollar_risk")),
            "score": _coerce_float_or_none(pos.get("score")),
            "rank": pos.get("rank"),
            "notes": pos.get("notes"),
            "reason": pos.get("reason"),
            "delayed_entry_bars_effective": pos.get("delayed_entry_bars_effective"),
            "delayed_relax_pct_effective": pos.get("delayed_relax_pct_effective"),
            "live_mode_relaxed": bool(pos.get("live_mode_relaxed", False)),
            "source_signal_type": pos.get("source_signal_type"),
            "original_signal_score": _coerce_float_or_none(pos.get("original_signal_score")),
            "original_signal_rank": pos.get("original_signal_rank"),
            "original_signal_notes": pos.get("original_signal_notes"),
            "original_signal_reason": pos.get("original_signal_reason"),
            "status": "closed",
            "exit_timestamp": utc_now_iso(),
            "exit_date": exit_date,
            "exit_price": float(exit_px),
            "exit_reason": exit_reason,
            "realized_pnl_dollars": float(realized_pnl),
            "realized_r": _coerce_float_or_none(realized_r),
            "hold_bars_or_days_if_available": "",
        }
        closed_detail.update(
            {
                "position_id": pos.get("position_id"),
                "combo_label": combo_label,
                "interval": interval,
                "config": _position_config_label(pos),
                "preset": str(pos.get("preset") or pos.get("preset_name") or _position_config_label(pos)),
                "entry": float(entry_px),
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "risk_amount": _position_risk_amount(pos),
                "rr": _position_rr(pos),
                "signal_date": str(pos.get("signal_date") or pos.get("signal_bar_date") or "")[:10],
                "intended_entry_date": str(pos.get("intended_entry_date") or pos.get("entry_date") or "")[:10],
                "gap_through_stop": bool(gap_through_stop),
                "loss_beyond_stop_reason": loss_beyond_stop_reason,
            }
        )
        append_csv_row(
            state.paths()["live_closed_trades_csv"],
            {
                "run_timestamp": run_timestamp,
                "symbol": sym,
                "combo_label": combo_label,
                "interval": interval,
                "entry_date": str(pos.get("entry_date", ""))[:10],
                "intended_entry_date": str(pos.get("intended_entry_date") or pos.get("entry_date") or "")[:10],
                "signal_date": str(pos.get("signal_date") or pos.get("signal_bar_date") or "")[:10],
                "exit_date": exit_date,
                "entry_price": float(entry_px),
                "entry": float(entry_px),
                "stop_price": stop_loss,
                "stop_loss": stop_loss,
                "target_price": take_profit,
                "take_profit": take_profit,
                "risk_per_share": _position_risk_per_share(pos),
                "risk_amount": _position_risk_amount(pos),
                "rr": _position_rr(pos),
                "config": _position_config_label(pos),
                "preset": str(pos.get("preset") or pos.get("preset_name") or _position_config_label(pos)),
                "position_id": pos.get("position_id"),
                "paper_entry_open": _coerce_float_or_none(pos.get("paper_entry_open")),
                "paper_shares": _position_quantity(pos),
                "exit_price": float(exit_px),
                "exit_reason": exit_reason,
                "gap_through_stop": bool(gap_through_stop),
                "loss_beyond_stop_reason": loss_beyond_stop_reason,
                "expected_r_from_backtest": exp_bt,
                "actual_r_live": float(actual_r),
                "bars_held": "",
                "stress_config": str(asdict(PAPER_STRESS)),
                "submitted_order_type": pos.get("entry_order_type"),
                "submitted_limit_price": pos.get("entry_order_limit_price"),
                "submitted_stop_price": pos.get("entry_order_stop_price"),
                "actual_filled_avg_price": pos.get("actual_fill_price"),
                "fill_slippage_r": pos.get("fill_drift_r"),
            },
            CLOSED_CSV_FIELDS,
        )
        append_csv_row(PAPER_CLOSED_TRADES_CSV, closed_detail, PAPER_CLOSED_EXPORT_FIELDS)
        _append_json_list(PAPER_CLOSED_TRADES_DETAILED_JSON, closed_detail)
    if stop_check_df is not None and portfolio_state is not None:
        try:
            record_symbol_exit(sym, stop_check_df, int(stop_hit.get("bar_index", len(stop_check_df) - 1)), portfolio_state)
        except Exception:
            logger.exception("record_symbol_exit failed sym=%s reason=%s", sym, order_reason)
    paper_live_log_event(
        "EXIT",
        symbol=sym,
        exit_date=exit_date,
        exit_reason=exit_reason,
        actual_r_live=float(actual_r),
    )
    state.remove_open_position(pos)
    _persist_close_retry_queue_safely(state)
    return 1, alerts_sent, alerts_failed


def process_close_retry_watchdog(
    *,
    state: LivePaperState,
    combo_labels: list[str],
    interval_by_combo: dict[str, str],
    run_timestamp: str,
    dry_run: bool,
    telegram_dry_run: bool,
    send_message: Any,
    build_exit: Any,
    output_scope: str,
    portfolio_state: dict[str, Any] | None = None,
    execution_adapter: ExecutionAdapter | None = None,
    execution_adapter_positions: list[dict[str, Any]] | None = None,
    execution_events: list[dict[str, Any]] | None = None,
    execution_market_is_open: bool | None = None,
) -> tuple[int, int, int]:
    """Persistent close-retry watchdog. Runs before entry processing."""
    exits_closed = 0
    alerts_sent = 0
    alerts_failed = 0
    default_combo = combo_labels[0] if combo_labels else ""
    merge_close_retry_queue_into_positions(state, execution_events)
    for pos in list(state.open_positions):
        close_state = str(pos.get("close_state") or "").strip().upper()
        if close_state not in CLOSE_RETRY_PENDING_STATES:
            continue
        pid = _ensure_position_identity(pos, state=state, execution_events=execution_events, reason="close_retry_watchdog")
        sym = str(pos.get("symbol", "")).strip().upper()
        if not sym:
            continue
        validation = _strategy_position_validation(pos)
        if not validation["managed_by_strategy"]:
            _record_execution_event(
                execution_events,
                "close_skipped",
                symbol=sym,
                position_id=pid,
                reason="invalid_strategy_position_fields",
                close_state=close_state,
                managed_by_strategy=False,
                invalid_fields=validation["missing_fields"],
            )
            _append_execution_order_event(
                state,
                event_type="close_skipped",
                symbol=sym,
                position_id=pid,
                side=_position_side(pos),
                qty=_position_quantity(pos),
                stop_loss=_position_stop_loss(pos),
                take_profit=_position_take_profit(pos),
                close_state=close_state,
                reason="invalid_strategy_position_fields",
                status="skipped",
                managed_by_strategy=False,
            )
            continue

        fatal, fatal_reason = _close_retry_fatal_due(pos)
        if fatal:
            # Fatal-after-timeout / max-attempts may only escalate while the
            # broker still confirms the position exists. If reconcile finds
            # the position is already absent at the broker, override fatal
            # and resolve via reconcile.
            broker_verdict, _broker_row, _broker_qty_live, broker_err = _validate_fatal_against_broker(
                sym=sym,
                execution_adapter=execution_adapter,
            )
            if broker_verdict == "broker_missing_position":
                _resolve_position_via_reconcile(
                    state=state,
                    pos=pos,
                    execution_adapter=execution_adapter,
                    execution_events=execution_events,
                    source="close_retry_watchdog",
                    triggering_reason=fatal_reason,
                )
                state.remove_open_position(pos)
                _persist_close_retry_queue_safely(state)
                exits_closed += 1
                continue
            if broker_verdict == "broker_unreachable":
                logger.warning(
                    "[execution] event=close_retry_fatal_deferred symbol=%s position_id=%s reason=%s broker_error=%s",
                    sym,
                    pid,
                    fatal_reason,
                    broker_err,
                )
                _mark_close_workflow(
                    pos,
                    state_name="CLOSE_RETRY",
                    reason=str(pos.get("close_reason") or pos.get("close_retry_reason") or "pending_close_retry"),
                    error=broker_err or "broker_unreachable_during_fatal_check",
                )
                _record_execution_event(
                    execution_events,
                    "close_retry_fatal_deferred",
                    symbol=sym,
                    position_id=pid,
                    adapter=type(execution_adapter).__name__ if execution_adapter is not None else "",
                    reason=fatal_reason,
                    close_state="CLOSE_RETRY",
                    error=broker_err or "broker_unreachable_during_fatal_check",
                )
                _persist_close_retry_queue_safely(state)
                continue

            _mark_close_workflow(
                pos,
                state_name="CLOSE_FAILED_FATAL",
                reason=str(pos.get("close_reason") or pos.get("close_retry_reason") or fatal_reason),
                error=fatal_reason,
                broker_qty=_position_quantity(pos),
            )
            logger.critical("[execution] event=close_order_failed_fatal symbol=%s position_id=%s reason=%s", sym, pid, fatal_reason)
            _record_execution_event(
                execution_events,
                "close_order_failed_fatal",
                symbol=sym,
                position_id=pid,
                reason=fatal_reason,
                close_state="CLOSE_FAILED_FATAL",
                attempt_count=pos.get("close_attempt_count"),
                error=pos.get("last_close_error") or pos.get("last_retry_error"),
                broker_confirmed_position=True,
            )
            _append_execution_order_event(
                state,
                event_type="close_order_failed_fatal",
                symbol=sym,
                position_id=pid,
                side=_position_side(pos),
                qty=_position_quantity(pos),
                stop_loss=_position_stop_loss(pos),
                take_profit=_position_take_profit(pos),
                close_state="CLOSE_FAILED_FATAL",
                close_reason=pos.get("close_reason"),
                attempt_count=pos.get("close_attempt_count"),
                reason=fatal_reason,
                status="fatal",
                error=pos.get("last_close_error") or pos.get("last_retry_error"),
                managed_by_strategy=True,
            )
            if callable(send_message) and not telegram_dry_run:
                try:
                    if send_message(
                        f"CRITICAL: close retry fatal for {sym}\nreason={fatal_reason}\nposition_id={pid}",
                        parse_mode=None,
                    ):
                        alerts_sent += 1
                    else:
                        alerts_failed += 1
                except Exception:
                    logger.exception("telegram critical close retry alert failed symbol=%s", sym)
                    alerts_failed += 1
            continue

        if not _close_retry_due(pos):
            _record_execution_event(
                execution_events,
                "close_skipped",
                symbol=sym,
                position_id=pid,
                reason="close_retry_not_due",
                close_state=close_state,
                next_retry_at=pos.get("next_retry_at"),
            )
            continue

        adapter_row = _adapter_positions_by_symbol(execution_adapter_positions).get(sym)
        if execution_adapter is not None:
            fresh_row, err = _adapter_position_for_symbol(execution_adapter, sym)
            if err:
                _mark_close_workflow(
                    pos,
                    state_name="CLOSE_RETRY",
                    reason=str(pos.get("close_reason") or pos.get("close_retry_reason") or "pending_close_retry"),
                    error=err,
                )
                _record_execution_event(
                    execution_events,
                    "close_order_retry",
                    symbol=sym,
                    position_id=pid,
                    reason="broker_position_refresh_failed",
                    close_state="CLOSE_RETRY",
                    error=err,
                )
                continue
            adapter_row = fresh_row or adapter_row
        broker_qty = _broker_qty_from_position_row(adapter_row)
        combo = str(pos.get("combo_label") or default_combo)
        if combo not in combo_labels and combo_labels:
            combo = default_combo
        interval = str(pos.get("interval") or interval_by_combo.get(combo) or "") or "1d"
        res_wd = _resolve_execution_price(
            sym=sym,
            execution_adapter=execution_adapter,
            adapter_row=adapter_row,
            interval=interval,
            decision_kind="exit",
            market_is_open=execution_market_is_open,
            df=None,
            execution_events=execution_events,
            state=state,
        )
        retry_price = res_wd.get("price") if res_wd.get("ok") else _adapter_current_price(adapter_row)
        retry_reason = str(pos.get("close_reason") or pos.get("close_retry_reason") or "pending_close_retry")
        retry_hit = {
            "side": _position_side(pos),
            "stop_loss": _position_stop_loss(pos),
            "take_profit": _position_take_profit(pos),
            "current_price": retry_price,
            "exit_price": retry_price or _position_entry_price(pos),
            "bar_timestamp": utc_now_iso(),
            "bar_index": -1,
            "source": "close_retry_watchdog",
            "reason": retry_reason,
            "exit_reason": retry_reason,
            "broker_qty": broker_qty,
        }
        xe, ae, af = _process_stop_loss_exit(
            sym=sym,
            combo_label=combo,
            interval=interval,
            pos=pos,
            stop_hit=retry_hit,
            state=state,
            run_timestamp=run_timestamp,
            dry_run=dry_run,
            telegram_dry_run=telegram_dry_run,
            send_message=send_message,
            build_exit=build_exit,
            output_scope=output_scope,
            stop_check_df=None,
            portfolio_state=portfolio_state,
            execution_adapter=execution_adapter,
            execution_events=execution_events,
        )
        exits_closed += xe
        alerts_sent += ae
        alerts_failed += af
    _persist_close_retry_queue_safely(state)
    return exits_closed, alerts_sent, alerts_failed


def process_exits_for_symbol(
    *,
    sym: str,
    combo_label: str,
    interval: str,
    trades: list[dict[str, Any]],
    state: LivePaperState,
    run_timestamp: str,
    dry_run: bool,
    telegram_dry_run: bool,
    send_message: Any,
    build_exit: Any,
    output_scope: str,
    df: pd.DataFrame | None = None,
    portfolio_state: dict[str, Any] | None = None,
    execution_adapter: ExecutionAdapter | None = None,
    execution_adapter_health_ok: bool = True,
    execution_adapter_positions: list[dict[str, Any]] | None = None,
    execution_events: list[dict[str, Any]] | None = None,
    verbose_execution_events: bool = False,
    stop_check_df: pd.DataFrame | None = None,
    stop_loss_only: bool = False,
    engine_cfg: Any | None = None,
    execution_market_is_open: bool | None = None,
) -> tuple[int, int, int]:
    """Returns (exits_closed, alerts_sent, alerts_failed)."""
    exits_closed = 0
    alerts_sent = 0
    alerts_failed = 0

    for pos in list(state.open_positions):
        if pos.get("symbol", "").strip().upper() != sym.strip().upper():
            continue
        pos_combo = str(pos.get("combo_label") or "").strip()
        if pos_combo and pos_combo != combo_label:
            continue
        adapter_row = _adapter_positions_by_symbol(execution_adapter_positions).get(sym.strip().upper())
        price_df = stop_check_df if stop_check_df is not None else df
        res_px = _resolve_execution_price(
            sym=sym,
            execution_adapter=execution_adapter,
            adapter_row=adapter_row,
            interval=interval,
            decision_kind="exit",
            market_is_open=execution_market_is_open,
            df=price_df,
            execution_events=execution_events,
            state=state,
        )
        diag_price = res_px["price"] if res_px["price"] is not None else _latest_close_price(price_df)
        adapter_mark_price = res_px["price"]
        adapter_mark_exit = None
        market_detail: dict[str, Any] | None = None
        if (
            res_px["price"] is not None
            and execution_adapter is not None
            and hasattr(execution_adapter, "get_latest_price_details")
        ):
            try:
                details_map = execution_adapter.get_latest_price_details([sym.strip().upper()])
                market_detail = _pick_alpaca_price_row(details_map, sym.strip().upper())
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "[execution] exit_market_detail_fetch_failed symbol=%s error=%s",
                    sym,
                    exc,
                )
        if res_px["price"] is not None:
            adapter_mark_exit = _build_adapter_mark_exit_from_live_price(
                pos,
                res_px,
                adapter_row=adapter_row,
                market_detail=market_detail,
                execution_events=execution_events,
                sym=sym,
            )
        validation = _strategy_position_validation(pos)
        pending_close_state = str(pos.get("close_state") or "").strip().upper()
        _record_execution_event(
            execution_events,
            "exit_check",
            symbol=sym,
            combo_label=combo_label,
            side=_position_side(pos),
            qty=_position_quantity(pos),
            current_price=diag_price,
            stop_loss=_position_stop_loss(pos),
            take_profit=_position_take_profit(pos),
            current_r=_current_r_for_position(pos, diag_price),
            days_held=_days_held_from_position(pos),
            managed_by_strategy=validation["managed_by_strategy"],
            close_state=pending_close_state or str(pos.get("status") or "OPEN"),
            skipped_exit_reason="" if validation["managed_by_strategy"] else validation["reason"],
            source=str(res_px.get("selected_source") or res_px.get("price_source") or "execution_price_resolve"),
            price_source_trace=res_px.get("selected_source"),
            execution_market_is_open=execution_market_is_open,
        )
        if not validation["managed_by_strategy"]:
            logger.warning(
                "[execution] type=exit_skip symbol=%s reason=invalid_strategy_position_fields missing=%s",
                sym,
                validation["missing_fields"],
            )
            _record_execution_event(
                execution_events,
                "close_skipped",
                symbol=sym,
                reason=validation["reason"],
                side=_position_side(pos),
                qty=_position_quantity(pos),
                current_price=diag_price,
                stop_loss=_position_stop_loss(pos),
                take_profit=_position_take_profit(pos),
                current_r=_current_r_for_position(pos, diag_price),
                managed_by_strategy=False,
                close_state=pending_close_state or "INVALID_STRATEGY_POSITION_FIELDS",
                invalid_fields=validation["missing_fields"],
            )
            _append_execution_order_event(
                state,
                event_type="close_skipped",
                symbol=sym,
                adapter=type(execution_adapter).__name__ if execution_adapter is not None else "",
                side=_position_side(pos),
                qty=_position_quantity(pos),
                entry=_position_entry_price(pos),
                stop=_position_stop_loss(pos),
                target=_position_take_profit(pos),
                current_price=diag_price,
                stop_loss=_position_stop_loss(pos),
                take_profit=_position_take_profit(pos),
                current_r=_current_r_for_position(pos, diag_price),
                reason=validation["reason"],
                status="invalid_strategy_position_fields",
            )
            continue
        if pos.get("entry_fill_pending") or str(pos.get("close_state") or "").upper() == "FILL_DRIFT_MANUAL_REVIEW":
            skip_reason = "entry_fill_pending" if pos.get("entry_fill_pending") else "fill_drift_manual_review"
            _record_execution_event(
                execution_events,
                "exit_skipped",
                symbol=sym,
                position_id=pos.get("position_id"),
                reason=skip_reason,
                entry_fill_pending=bool(pos.get("entry_fill_pending")),
                entry_order_status=pos.get("entry_order_status"),
                fill_drift_exceeded=bool(pos.get("fill_drift_exceeded")),
            )
            continue
        if pending_close_state in {"CLOSE_REQUIRED", "CLOSE_RETRY", "CLOSE_PARTIAL", "VERIFY_CLOSED", "CLOSE_SUBMITTED"}:
            fatal, fatal_reason = _close_retry_fatal_due(pos)
            if fatal:
                # Fatal-after-timeout / max-attempts must be validated against
                # the live broker. If the broker confirms the position is
                # already gone, override fatal and resolve via reconcile.
                broker_verdict, _broker_row, _broker_qty_live, broker_err = _validate_fatal_against_broker(
                    sym=sym,
                    execution_adapter=execution_adapter,
                )
                if broker_verdict == "broker_missing_position":
                    _resolve_position_via_reconcile(
                        state=state,
                        pos=pos,
                        execution_adapter=execution_adapter,
                        execution_events=execution_events,
                        source="process_exits_for_symbol",
                        triggering_reason=fatal_reason,
                    )
                    state.remove_open_position(pos)
                    _persist_close_retry_queue_safely(state)
                    exits_closed += 1
                    continue
                if broker_verdict == "broker_unreachable":
                    logger.warning(
                        "[execution] event=close_retry_fatal_deferred symbol=%s position_id=%s reason=%s broker_error=%s",
                        sym,
                        pos.get("position_id"),
                        fatal_reason,
                        broker_err,
                    )
                    _mark_close_workflow(
                        pos,
                        state_name="CLOSE_RETRY",
                        reason=str(pos.get("close_reason") or pos.get("close_retry_reason") or "pending_close_retry"),
                        error=broker_err or "broker_unreachable_during_fatal_check",
                    )
                    _record_execution_event(
                        execution_events,
                        "close_retry_fatal_deferred",
                        symbol=sym,
                        position_id=pos.get("position_id"),
                        adapter=type(execution_adapter).__name__ if execution_adapter is not None else "",
                        reason=fatal_reason,
                        close_state="CLOSE_RETRY",
                        error=broker_err or "broker_unreachable_during_fatal_check",
                    )
                    _persist_close_retry_queue_safely(state)
                    continue

                _mark_close_workflow(
                    pos,
                    state_name="CLOSE_FAILED_FATAL",
                    reason=str(pos.get("close_reason") or fatal_reason),
                    error=fatal_reason,
                    broker_qty=_broker_qty_from_position_row(adapter_row) if adapter_row else _position_quantity(pos),
                )
                _append_execution_order_event(
                    state,
                    event_type="close_order_failed_fatal",
                    symbol=sym,
                    position_id=pos.get("position_id"),
                    adapter=type(execution_adapter).__name__ if execution_adapter is not None else "",
                    side=_position_side(pos),
                    qty=_position_quantity(pos),
                    stop_loss=_position_stop_loss(pos),
                    take_profit=_position_take_profit(pos),
                    close_state="CLOSE_FAILED_FATAL",
                    close_reason=pos.get("close_reason"),
                    attempt_count=pos.get("close_attempt_count"),
                    reason=fatal_reason,
                    status="fatal",
                    error=pos.get("last_close_error") or pos.get("last_retry_error"),
                    managed_by_strategy=True,
                )
                _persist_close_retry_queue_safely(state)
                continue
            if not _close_retry_due(pos):
                _record_execution_event(
                    execution_events,
                    "close_skipped",
                    symbol=sym,
                    position_id=pos.get("position_id"),
                    reason="close_retry_not_due",
                    close_state=pending_close_state,
                    next_retry_at=pos.get("next_retry_at"),
                )
                continue
            retry_hit = {
                "side": _position_side(pos),
                "stop_loss": _position_stop_loss(pos),
                "take_profit": _position_take_profit(pos),
                "current_price": diag_price,
                "exit_price": diag_price or _position_entry_price(pos),
                "bar_timestamp": utc_now_iso(),
                "bar_index": -1,
                "source": "pending_close_workflow",
                "reason": str(pos.get("close_reason") or "pending_close_retry"),
                "exit_reason": str(pos.get("close_reason") or "pending_close_retry"),
            }
            xe, ae, af = _process_stop_loss_exit(
                sym=sym,
                combo_label=combo_label,
                interval=interval,
                pos=pos,
                stop_hit=retry_hit,
                state=state,
                run_timestamp=run_timestamp,
                dry_run=dry_run,
                telegram_dry_run=telegram_dry_run,
                send_message=send_message,
                build_exit=build_exit,
                output_scope=output_scope,
                stop_check_df=stop_check_df if stop_check_df is not None else df,
                portfolio_state=portfolio_state,
                execution_adapter=execution_adapter,
                execution_events=execution_events,
            )
            exits_closed += xe
            alerts_sent += ae
            alerts_failed += af
            continue
        if res_px.get("block_reason") in ("stale_price_exit_blocked", "price_unavailable_exit_blocked"):
            br = str(res_px["block_reason"])
            logger.warning(
                "[execution] event=%s symbol=%s interval=%s stale_decision_reason=%s fallback_chain=%s",
                br,
                sym,
                interval,
                res_px.get("stale_decision_reason"),
                res_px.get("fallback_chain"),
            )
            _record_execution_event(
                execution_events,
                "close_skipped",
                symbol=sym,
                position_id=pos.get("position_id"),
                reason=br,
                side=_position_side(pos),
                qty=_position_quantity(pos),
                current_price=diag_price,
                stop_loss=_position_stop_loss(pos),
                take_profit=_position_take_profit(pos),
                current_r=_current_r_for_position(pos, diag_price),
                managed_by_strategy=True,
                close_state=pending_close_state or "OPEN",
                price_source=res_px.get("price_source"),
                price_method=res_px.get("price_method"),
                price_timestamp=res_px.get("price_timestamp"),
                price_age_seconds=res_px.get("price_age_seconds"),
                price_stale=bool(res_px.get("price_stale")),
                fallback_chain=res_px.get("fallback_chain"),
                stale_decision_reason=res_px.get("stale_decision_reason"),
            )
            _append_execution_order_event(
                state,
                event_type="close_skipped",
                symbol=sym,
                position_id=pos.get("position_id"),
                adapter=type(execution_adapter).__name__ if execution_adapter is not None else "",
                side=_position_side(pos),
                qty=_position_quantity(pos),
                entry=_position_entry_price(pos),
                stop=_position_stop_loss(pos),
                target=_position_take_profit(pos),
                current_price=diag_price,
                stop_loss=_position_stop_loss(pos),
                take_profit=_position_take_profit(pos),
                current_r=_current_r_for_position(pos, diag_price),
                reason=br,
                status="skipped",
                price_source=res_px.get("price_source"),
                price_method=res_px.get("price_method"),
                price_timestamp=res_px.get("price_timestamp"),
                price_age_seconds=res_px.get("price_age_seconds"),
                price_stale=bool(res_px.get("price_stale")),
            )
            continue
        if adapter_mark_exit is not None:
            xe, ae, af = _process_stop_loss_exit(
                sym=sym,
                combo_label=combo_label,
                interval=interval,
                pos=pos,
                stop_hit=adapter_mark_exit,
                state=state,
                run_timestamp=run_timestamp,
                dry_run=dry_run,
                telegram_dry_run=telegram_dry_run,
                send_message=send_message,
                build_exit=build_exit,
                output_scope=output_scope,
                stop_check_df=stop_check_df if stop_check_df is not None else df,
                portfolio_state=portfolio_state,
                execution_adapter=execution_adapter,
                execution_events=execution_events,
            )
            exits_closed += xe
            alerts_sent += ae
            alerts_failed += af
            continue
        stop_hit = _detect_stop_loss_breach(pos, stop_check_df if stop_check_df is not None else df)
        if stop_hit is not None:
            xe, ae, af = _process_stop_loss_exit(
                sym=sym,
                combo_label=combo_label,
                interval=interval,
                pos=pos,
                stop_hit=stop_hit,
                state=state,
                run_timestamp=run_timestamp,
                dry_run=dry_run,
                telegram_dry_run=telegram_dry_run,
                send_message=send_message,
                build_exit=build_exit,
                output_scope=output_scope,
                stop_check_df=stop_check_df if stop_check_df is not None else df,
                portfolio_state=portfolio_state,
                execution_adapter=execution_adapter,
                execution_events=execution_events,
            )
            exits_closed += xe
            alerts_sent += ae
            alerts_failed += af
            continue
        if stop_loss_only:
            continue
        t = find_matching_trade(pos, trades)
        if t is None:
            replay = _evaluate_engine_exit_for_open_position(
                sym=sym,
                pos=pos,
                df=df,
                cfg=engine_cfg,
                combo_label=combo_label,
                interval=interval,
                adapter_mark_price=adapter_mark_price,
            )
            _record_execution_event(
                execution_events,
                "engine_exit_condition" if replay.get("triggered") else "close_skipped",
                symbol=sym,
                reason=str(replay.get("triggered_rule") or replay.get("skipped_exit_reason") or "no_matching_engine_trade"),
                triggered_rule=replay.get("triggered_rule"),
                side=replay.get("side"),
                qty=replay.get("qty"),
                current_price=replay.get("current_price"),
                stop_loss=replay.get("stop_loss"),
                take_profit=replay.get("take_profit"),
                current_r=replay.get("current_r"),
                mfe_r=replay.get("mfe_r"),
                mae_r=replay.get("mae_r"),
                bars_held=replay.get("bars_held"),
                days_held=replay.get("days_held"),
                managed_by_strategy=replay.get("managed_by_strategy"),
                close_state="CLOSE_REQUIRED" if replay.get("triggered") else "OPEN",
                close_attempt_status=replay.get("close_attempt_status"),
            )
            if not replay.get("triggered"):
                logger.warning(
                    "[execution] type=exit_skip symbol=%s reason=%s entry_date=%s",
                    sym,
                    replay.get("skipped_exit_reason") or "no_matching_engine_trade",
                    pos.get("entry_date"),
                )
                _append_execution_order_event(
                    state,
                    event_type="close_skipped",
                    symbol=sym,
                    adapter=type(execution_adapter).__name__ if execution_adapter is not None else "",
                    side=replay.get("side"),
                    qty=replay.get("qty"),
                    entry=replay.get("entry_price"),
                    stop=replay.get("stop_loss"),
                    target=replay.get("take_profit"),
                    current_price=replay.get("current_price"),
                    stop_loss=replay.get("stop_loss"),
                    take_profit=replay.get("take_profit"),
                    current_r=replay.get("current_r"),
                    mfe_r=replay.get("mfe_r"),
                    mae_r=replay.get("mae_r"),
                    bars_held=replay.get("bars_held"),
                    days_held=replay.get("days_held"),
                    reason=str(replay.get("skipped_exit_reason") or "no_matching_engine_trade"),
                    status="skipped",
                )
                continue
            t = dict(replay.get("trade") or {})
            _mark_close_workflow(
                pos,
                state_name="CLOSE_REQUIRED",
                reason=str(t.get("exit_reason") or replay.get("triggered_rule") or "engine_exit"),
                broker_qty=_broker_qty_from_position_row(adapter_row) if adapter_row else _position_quantity(pos),
            )

        ak = alert_dedup_key(
            "exit",
            sym,
            combo_label,
            str(pos.get("last_checked_bar_date", "")),
            str(pos.get("entry_date", ""))[:10],
            str(t.get("exit_date", ""))[:10],
            interval=interval,
            output_scope=output_scope,
        )
        if state.alert_already_sent(ak):
            if execution_adapter is not None:
                broker_closed, broker_qty, verify_error = _verify_close_with_broker(
                    sym=sym,
                    pos=pos,
                    execution_adapter=execution_adapter,
                    execution_events=execution_events,
                    reason="exit_alert_already_sent_verify_broker",
                    adapter_name=type(execution_adapter).__name__,
                )
                if not broker_closed:
                    _schedule_close_retry(
                        pos,
                        reason="exit_alert_already_sent_broker_still_open",
                        error=verify_error,
                        broker_qty=broker_qty,
                        force_due=True,
                    )
                    _append_execution_order_event(
                        state,
                        event_type="close_order_retry",
                        symbol=sym,
                        position_id=pos.get("position_id"),
                        adapter=type(execution_adapter).__name__,
                        side=_position_side(pos),
                        qty=broker_qty,
                        stop_loss=_position_stop_loss(pos),
                        take_profit=_position_take_profit(pos),
                        close_state=str(pos.get("close_state") or "CLOSE_RETRY"),
                        reason="exit_alert_already_sent_broker_still_open",
                        status="retry",
                        error=verify_error,
                        managed_by_strategy=True,
                    )
                    _persist_close_retry_queue_safely(state)
                    continue
            state.remove_open_position(pos)
            _persist_close_retry_queue_safely(state)
            continue

        ar, exit_px = apply_stress_r(t)
        exp_bt = float(pos.get("expected_r_from_backtest", 0.0) or 0.0)
        d_r = float(ar) - exp_bt
        text = build_exit(
            symbol=sym,
            combo_label=combo_label,
            interval=interval,
            entry_date=str(pos.get("entry_date", ""))[:10],
            exit_date=str(t.get("exit_date", ""))[:10],
            entry_price=float(pos.get("entry_price", 0.0)),
            exit_price=float(exit_px),
            exit_reason=str(t.get("exit_reason", "")),
            actual_r_live=float(ar),
            bars_held=t.get("bars_held", ""),
            stress_summary=stress_config_summary(PAPER_STRESS),
            expected_r_from_backtest=exp_bt,
            delta_r=d_r,
        )
        ok = True
        exec_ok = True
        close_reason = str(t.get("exit_reason", "") or "engine_exit")
        close_qty = _position_quantity(pos)
        close_stop = _position_stop_loss(pos)
        close_target = _position_take_profit(pos)
        close_current_price = _coerce_float_or_none(exit_px)
        close_current_r = _current_r_for_position(pos, close_current_price)
        close_mfe_r = _coerce_float_or_none(t.get("mfe_r"))
        close_mae_r = _coerce_float_or_none(t.get("mae_r"))
        close_bars_held = t.get("bars_held", "")
        close_days_held = _days_held_from_position(pos)
        if execution_adapter is not None:
            logger.info("[execution] type=attempt action=close_position symbol=%s adapter=%s", sym, type(execution_adapter).__name__)
            _mark_close_workflow(
                pos,
                state_name="CLOSE_REQUESTED",
                reason=close_reason,
                broker_qty=_broker_qty_from_position_row(adapter_row) if adapter_row else close_qty,
            )
            _record_execution_event(
                execution_events,
                "close_order_attempt",
                symbol=sym,
                adapter=type(execution_adapter).__name__,
                reason=close_reason,
                triggered_rule=close_reason,
                side=_position_side(pos),
                qty=close_qty,
                current_price=close_current_price,
                stop_loss=close_stop,
                take_profit=close_target,
                current_r=close_current_r,
                mfe_r=close_mfe_r,
                mae_r=close_mae_r,
                bars_held=close_bars_held,
                days_held=close_days_held,
                exit_price=exit_px,
                close_state="CLOSE_REQUESTED",
            )
            _append_execution_order_event(
                state,
                event_type="close_order_attempt",
                symbol=sym,
                adapter=type(execution_adapter).__name__,
                side=_position_side(pos),
                qty=close_qty,
                entry=_position_entry_price(pos),
                stop=close_stop,
                target=close_target,
                current_price=close_current_price,
                stop_loss=close_stop,
                take_profit=close_target,
                exit_price=exit_px,
                current_r=close_current_r,
                triggered_rule=close_reason,
                mfe_r=close_mfe_r,
                mae_r=close_mae_r,
                bars_held=close_bars_held,
                days_held=close_days_held,
                reason=close_reason,
            )
            try:
                exec_result = execution_adapter.close_position(sym)
            except Exception as exc:  # noqa: BLE001
                exec_result = {
                    "accepted": False,
                    "adapter": type(execution_adapter).__name__,
                    "event": "close_order_failed",
                    "error": f"{type(exc).__name__}: {exc}",
                }
                logger.exception("[execution] type=failure action=close_position symbol=%s adapter=%s", sym, type(execution_adapter).__name__)
            exec_ok = bool(exec_result.get("accepted", False))
            _mark_close_workflow(
                pos,
                state_name="CLOSE_SUBMITTED" if exec_ok else "CLOSE_RETRY",
                reason=close_reason,
                broker_qty=_broker_qty_from_position_row(adapter_row) if adapter_row else close_qty,
                order_id=str(exec_result.get("order_id") or exec_result.get("broker_order_id") or ""),
                order_status=str(exec_result.get("status") or exec_result.get("event") or ""),
                error=str(exec_result.get("error") or "") or None,
            )
            if bool(exec_result.get("dry_run", False)):
                _record_execution_event(
                    execution_events,
                    "close_order_dry_run",
                    symbol=sym,
                    adapter=type(execution_adapter).__name__,
                    reason=close_reason,
                    side=_position_side(pos),
                    qty=close_qty,
                    current_price=close_current_price,
                    stop_loss=close_stop,
                    take_profit=close_target,
                    current_r=close_current_r,
                    triggered_rule=close_reason,
                    mfe_r=close_mfe_r,
                    mae_r=close_mae_r,
                    bars_held=close_bars_held,
                    days_held=close_days_held,
                    close_state="CLOSE_SUBMITTED",
                    result=exec_result,
                )
                _append_execution_order_event(
                    state,
                    event_type="close_order_dry_run",
                    symbol=sym,
                    adapter=type(execution_adapter).__name__,
                    side=_position_side(pos),
                    qty=close_qty,
                    entry=_position_entry_price(pos),
                    stop=close_stop,
                    target=close_target,
                    current_price=close_current_price,
                    stop_loss=close_stop,
                    take_profit=close_target,
                    exit_price=exit_px,
                    current_r=close_current_r,
                    triggered_rule=close_reason,
                    mfe_r=close_mfe_r,
                    mae_r=close_mae_r,
                    bars_held=close_bars_held,
                    days_held=close_days_held,
                    reason=close_reason,
                    result=exec_result,
                    accepted=True,
                    dry_run=True,
                )
            if not exec_ok:
                logger.warning(
                    "[execution] type=rejection action=close_position symbol=%s adapter=%s details=%s",
                    sym,
                    type(execution_adapter).__name__,
                    exec_result,
                )
                _record_execution_event(
                    execution_events,
                    "close_order_failed" if str(exec_result.get("event") or "") == "close_order_failed" else "close_order_rejected",
                    symbol=sym,
                    adapter=type(execution_adapter).__name__,
                    reason=close_reason,
                    side=_position_side(pos),
                    qty=close_qty,
                    current_price=close_current_price,
                    stop_loss=close_stop,
                    take_profit=close_target,
                    current_r=close_current_r,
                    triggered_rule=close_reason,
                    mfe_r=close_mfe_r,
                    mae_r=close_mae_r,
                    bars_held=close_bars_held,
                    days_held=close_days_held,
                    close_state="CLOSE_RETRY",
                    result=exec_result,
                )
                _append_execution_order_event(
                    state,
                    event_type="close_order_failed" if str(exec_result.get("event") or "") == "close_order_failed" else "close_order_rejected",
                    symbol=sym,
                    adapter=type(execution_adapter).__name__,
                    side=_position_side(pos),
                    qty=close_qty,
                    entry=_position_entry_price(pos),
                    stop=close_stop,
                    target=close_target,
                    current_price=close_current_price,
                    stop_loss=close_stop,
                    take_profit=close_target,
                    exit_price=exit_px,
                    current_r=close_current_r,
                    triggered_rule=close_reason,
                    mfe_r=close_mfe_r,
                    mae_r=close_mae_r,
                    bars_held=close_bars_held,
                    days_held=close_days_held,
                    reason=close_reason,
                    result=exec_result,
                    accepted=False,
                )
            else:
                close_success_event_type = (
                    "close_order_filled"
                    if str(exec_result.get("status") or "").strip().lower() in ("filled", "closed")
                    else "close_order_submitted"
                )
                _record_execution_event(
                    execution_events,
                    close_success_event_type,
                    symbol=sym,
                    adapter=type(execution_adapter).__name__,
                    reason=close_reason,
                    side=_position_side(pos),
                    qty=close_qty,
                    current_price=close_current_price,
                    stop_loss=close_stop,
                    take_profit=close_target,
                    current_r=close_current_r,
                    triggered_rule=close_reason,
                    mfe_r=close_mfe_r,
                    mae_r=close_mae_r,
                    bars_held=close_bars_held,
                    days_held=close_days_held,
                    close_state="CLOSE_SUBMITTED",
                    result=exec_result,
                )
                _append_execution_order_event(
                    state,
                    event_type=close_success_event_type,
                    symbol=sym,
                    adapter=type(execution_adapter).__name__,
                    side=_position_side(pos),
                    qty=close_qty,
                    entry=_position_entry_price(pos),
                    stop=close_stop,
                    target=close_target,
                    current_price=close_current_price,
                    stop_loss=close_stop,
                    take_profit=close_target,
                    exit_price=exit_px,
                    current_r=close_current_r,
                    triggered_rule=close_reason,
                    mfe_r=close_mfe_r,
                    mae_r=close_mae_r,
                    bars_held=close_bars_held,
                    days_held=close_days_held,
                    reason=close_reason,
                    result=exec_result,
                    accepted=True,
                    dry_run=bool(exec_result.get("dry_run", False)),
                )
        if not exec_ok:
            alerts_failed += 1
            continue
        if bool(exec_result.get("dry_run", False)):
            pos["close_state"] = "CLOSE_REQUIRED"
            pos["last_close_order_status"] = "dry_run_not_submitted"
            pos["last_close_error"] = "dry_run_close_not_confirmed"
            alerts_failed += 1
            continue
        if execution_adapter is not None and not bool(exec_result.get("dry_run", False)):
            broker_closed, broker_qty, verify_error = _verify_close_with_broker(
                sym=sym,
                pos=pos,
                execution_adapter=execution_adapter,
                execution_events=execution_events,
                reason=close_reason,
                adapter_name=type(execution_adapter).__name__,
            )
            if not broker_closed:
                _append_execution_order_event(
                    state,
                    event_type="close_order_retry" if broker_qty > 0 else "close_order_failed",
                    symbol=sym,
                    adapter=type(execution_adapter).__name__,
                    side=_position_side(pos),
                    qty=broker_qty,
                    entry=_position_entry_price(pos),
                    stop=close_stop,
                    target=close_target,
                    current_price=close_current_price,
                    stop_loss=close_stop,
                    take_profit=close_target,
                    exit_price=exit_px,
                    current_r=close_current_r,
                    triggered_rule=close_reason,
                    mfe_r=close_mfe_r,
                    mae_r=close_mae_r,
                    bars_held=close_bars_held,
                    days_held=close_days_held,
                    reason=close_reason,
                    status=str(pos.get("close_state") or "CLOSE_RETRY"),
                    result={"accepted": False, "error": verify_error, "raw_response": {"broker_qty": broker_qty}},
                    accepted=False,
                )
                alerts_failed += 1
                continue

        if not dry_run:
            if telegram_dry_run:
                logger.info("[telegram_dry_run] EXIT %s", text[:500])
            else:
                ok = send_message(text, parse_mode=None)
        else:
            logger.info("[dry_run] EXIT %s", text[:300])
        if ok:
            alerts_sent += 1
            state.mark_alert_sent(ak)
        else:
            alerts_failed += 1
        shares_f = float(pos.get("paper_shares", pos.get("shares", 0.0)) or 0.0)
        entry_px_f = float(pos.get("entry_price", 0.0) or 0.0)
        realized_pnl = float(exit_px - entry_px_f) * shares_f
        realized_r = (
            float(realized_pnl) / float(pos.get("dollar_risk", 0.0))
            if float(pos.get("dollar_risk", 0.0) or 0.0) > 0
            else None
        )
        if not dry_run:
            closed_detail = {
                "symbol": sym,
                "engine": str(pos.get("engine_label", "")),
                "entry_timestamp": pos.get("entry_timestamp"),
                "entry_date": str(pos.get("entry_date", ""))[:10],
                "signal_bar_date": pos.get("signal_bar_date"),
                "entry_price": entry_px_f,
                "stop_price": float(pos.get("stop_price", pos.get("stop", 0.0)) or 0.0),
                "target_price": float(pos.get("target_price", pos.get("target", 0.0)) or 0.0),
                "risk_per_share": _coerce_float_or_none(pos.get("risk_per_share")),
                "risk_pct_from_entry": _coerce_float_or_none(pos.get("risk_pct_from_entry")),
                "shares": shares_f,
                "dollar_risk": _coerce_float_or_none(pos.get("dollar_risk")),
                "score": _coerce_float_or_none(pos.get("score")),
                "rank": pos.get("rank"),
                "notes": pos.get("notes"),
                "reason": pos.get("reason"),
                "delayed_entry_bars_effective": pos.get("delayed_entry_bars_effective"),
                "delayed_relax_pct_effective": pos.get("delayed_relax_pct_effective"),
                "live_mode_relaxed": bool(pos.get("live_mode_relaxed", False)),
                "source_signal_type": pos.get("source_signal_type"),
                "original_signal_score": _coerce_float_or_none(pos.get("original_signal_score")),
                "original_signal_rank": pos.get("original_signal_rank"),
                "original_signal_notes": pos.get("original_signal_notes"),
                "original_signal_reason": pos.get("original_signal_reason"),
                "status": "closed",
                "exit_timestamp": utc_now_iso(),
                "exit_date": str(t.get("exit_date", ""))[:10],
                "exit_price": float(exit_px),
                "exit_reason": str(t.get("exit_reason", "")),
                "realized_pnl_dollars": float(realized_pnl),
                "realized_r": _coerce_float_or_none(realized_r),
                "hold_bars_or_days_if_available": t.get("bars_held", ""),
            }
            normal_loss_beyond_stop_reason = _loss_beyond_stop_reason(pos, float(exit_px))
            closed_detail.update(
                {
                    "position_id": pos.get("position_id"),
                    "combo_label": combo_label,
                    "interval": interval,
                    "config": _position_config_label(pos),
                    "preset": str(pos.get("preset") or pos.get("preset_name") or _position_config_label(pos)),
                    "entry": entry_px_f,
                    "stop_loss": _position_stop_loss(pos),
                    "take_profit": _position_take_profit(pos),
                    "risk_amount": _position_risk_amount(pos),
                    "rr": _position_rr(pos),
                    "signal_date": str(pos.get("signal_date") or pos.get("signal_bar_date") or "")[:10],
                    "intended_entry_date": str(pos.get("intended_entry_date") or pos.get("entry_date") or "")[:10],
                    "gap_through_stop": False,
                    "loss_beyond_stop_reason": normal_loss_beyond_stop_reason,
                }
            )
            append_csv_row(
                state.paths()["live_closed_trades_csv"],
                {
                    "run_timestamp": run_timestamp,
                    "symbol": sym,
                    "combo_label": combo_label,
                    "interval": interval,
                    "entry_date": str(pos.get("entry_date", ""))[:10],
                    "intended_entry_date": str(pos.get("intended_entry_date") or pos.get("entry_date") or "")[:10],
                    "signal_date": str(pos.get("signal_date") or pos.get("signal_bar_date") or "")[:10],
                    "exit_date": str(t.get("exit_date", ""))[:10],
                    "entry_price": float(pos.get("entry_price", 0.0)),
                    "entry": float(pos.get("entry_price", 0.0)),
                    "stop_price": _position_stop_loss(pos),
                    "stop_loss": _position_stop_loss(pos),
                    "target_price": _position_take_profit(pos),
                    "take_profit": _position_take_profit(pos),
                    "risk_per_share": _position_risk_per_share(pos),
                    "risk_amount": _position_risk_amount(pos),
                    "rr": _position_rr(pos),
                    "config": _position_config_label(pos),
                    "preset": str(pos.get("preset") or pos.get("preset_name") or _position_config_label(pos)),
                    "position_id": pos.get("position_id"),
                    "paper_entry_open": _coerce_float_or_none(pos.get("paper_entry_open")),
                    "paper_shares": _position_quantity(pos),
                    "exit_price": float(exit_px),
                    "exit_reason": str(t.get("exit_reason", "")),
                    "gap_through_stop": False,
                    "loss_beyond_stop_reason": normal_loss_beyond_stop_reason,
                    "expected_r_from_backtest": float(pos.get("expected_r_from_backtest", 0.0)),
                    "actual_r_live": float(ar),
                    "bars_held": t.get("bars_held", ""),
                    "stress_config": str(asdict(PAPER_STRESS)),
                    "submitted_order_type": pos.get("entry_order_type"),
                    "submitted_limit_price": pos.get("entry_order_limit_price"),
                    "submitted_stop_price": pos.get("entry_order_stop_price"),
                    "actual_filled_avg_price": pos.get("actual_fill_price"),
                    "fill_slippage_r": pos.get("fill_drift_r"),
                },
                CLOSED_CSV_FIELDS,
            )
            append_csv_row(PAPER_CLOSED_TRADES_CSV, closed_detail, PAPER_CLOSED_EXPORT_FIELDS)
            _append_json_list(PAPER_CLOSED_TRADES_DETAILED_JSON, closed_detail)
        if df is not None and portfolio_state is not None:
            try:
                record_symbol_exit(sym, df, int(t.get("exit_bar", 0)), portfolio_state)
            except Exception:
                logger.exception("record_symbol_exit failed sym=%s", sym)
        paper_live_log_event(
            "EXIT",
            symbol=sym,
            exit_date=str(t.get("exit_date", ""))[:10],
            exit_reason=str(t.get("exit_reason", "")),
            actual_r_live=float(ar),
        )
        exits_closed += 1
        state.remove_open_position(pos)

    return exits_closed, alerts_sent, alerts_failed


def process_broker_mark_exits_for_open_positions(
    *,
    state: LivePaperState,
    combo_labels: list[str],
    interval_by_combo: dict[str, str],
    run_timestamp: str,
    dry_run: bool,
    telegram_dry_run: bool,
    send_message: Any,
    build_exit: Any,
    output_scope: str,
    portfolio_state: dict[str, Any] | None = None,
    execution_adapter: ExecutionAdapter | None = None,
    execution_adapter_health_ok: bool = True,
    execution_adapter_positions: list[dict[str, Any]] | None = None,
    execution_events: list[dict[str, Any]] | None = None,
    verbose_execution_events: bool = False,
    execution_market_is_open: bool | None = None,
) -> tuple[int, int, int]:
    """Broker-mark exit sweep for open positions, independent of signal/data availability."""
    exits_closed = 0
    alerts_sent = 0
    alerts_failed = 0
    default_combo = combo_labels[0] if combo_labels else ""
    # Reconcile broker-missing positions *before* close-retry watchdog so we
    # never emit CLOSE_FAILED_FATAL / persist fatal CSV rows for symbols the
    # broker already closed in the same cycle.
    reconciliation_pre = _safe_reconcile_adapter_positions(execution_adapter, state.open_positions)
    if bool(reconciliation_pre.get("reconciliation_ok", True)):
        reconcile_missing_broker_positions(
            state=state,
            reconciliation=reconciliation_pre,
            execution_adapter=execution_adapter,
            execution_events=execution_events,
        )
    xe_retry, ae_retry, af_retry = process_close_retry_watchdog(
        state=state,
        combo_labels=combo_labels,
        interval_by_combo=interval_by_combo,
        run_timestamp=run_timestamp,
        dry_run=dry_run,
        telegram_dry_run=telegram_dry_run,
        send_message=send_message,
        build_exit=build_exit,
        output_scope=output_scope,
        portfolio_state=portfolio_state,
        execution_adapter=execution_adapter,
        execution_adapter_positions=execution_adapter_positions,
        execution_events=execution_events,
        execution_market_is_open=execution_market_is_open,
    )
    exits_closed += xe_retry
    alerts_sent += ae_retry
    alerts_failed += af_retry
    for pos in list(state.open_positions):
        sym = str(pos.get("symbol", "")).strip().upper()
        if not sym:
            continue
        combo = str(pos.get("combo_label") or default_combo)
        if combo not in combo_labels and combo_labels:
            combo = default_combo
        interval = str(interval_by_combo.get(combo) or "")
        xe, ae, af = process_exits_for_symbol(
            sym=sym,
            combo_label=combo,
            interval=interval,
            trades=[],
            state=state,
            run_timestamp=run_timestamp,
            dry_run=dry_run,
            telegram_dry_run=telegram_dry_run,
            send_message=send_message,
            build_exit=build_exit,
            output_scope=output_scope,
            df=None,
            portfolio_state=portfolio_state,
            execution_adapter=execution_adapter,
            execution_adapter_health_ok=execution_adapter_health_ok,
            execution_adapter_positions=execution_adapter_positions,
            execution_events=execution_events,
            verbose_execution_events=verbose_execution_events,
            stop_check_df=None,
            stop_loss_only=True,
            execution_market_is_open=execution_market_is_open,
        )
        exits_closed += xe
        alerts_sent += ae
        alerts_failed += af
    _persist_close_retry_queue_safely(state)
    return exits_closed, alerts_sent, alerts_failed


def process_new_entries_for_symbol(
    *,
    sym: str,
    combo_label: str,
    interval: str,
    df: pd.DataFrame,
    trades: list[dict[str, Any]],
    last_bar_date: str,
    state: LivePaperState,
    run_timestamp: str,
    dry_run: bool,
    telegram_dry_run: bool,
    send_message: Any,
    build_entry: Any,
    output_dir: Path,
    output_scope: str,
    cycle_started_perf: float,
    portfolio_state: dict[str, Any] | None = None,
    constraints: PortfolioConstraints | None = None,
    portfolio_skips: dict[str, int] | None = None,
    allocation_fn: Callable[[str, list[dict[str, Any]], float, float], tuple[bool, str]] | None = None,
    use_floor_sizing: bool = False,
    engine_label: str = "daily",
    ranking_preset_name: str | None = None,
    trade_funnel: Any | None = None,
    live_mode_relaxed: bool = False,
    recent_entries_collector: list[dict[str, Any]] | None = None,
    execution_adapter: ExecutionAdapter | None = None,
    execution_adapter_health_ok: bool = True,
    execution_events: list[dict[str, Any]] | None = None,
    execution_skip_counts: dict[str, int] | None = None,
    execution_order_counter: dict[str, int] | None = None,
    execution_max_orders_per_run: int | None = None,
    execution_allowed_symbols: set[str] | None = None,
    execution_risk_config: RiskConfig | None = None,
    execution_account_equity: float | None = None,
    execution_adapter_positions: list[dict[str, Any]] | None = None,
    execution_market_is_open: bool | None = None,
    execution_control_state: dict[str, Any] | None = None,
    execution_control_day: str | None = None,
    execution_daily_order_counter: dict[str, int] | None = None,
    verbose_execution_events: bool = False,
    entry_intent_bucket: list[dict[str, Any]] | None = None,
    silent_signal_telemetry: bool = False,
    placement_phase: str | None = None,
    candidate_log_prefix: str | None = None,
) -> tuple[int, int, int, int]:
    """Returns (new_signals, new_entries, alerts_sent, alerts_failed)."""
    new_signals = 0
    new_entries = 0
    alerts_sent = 0
    alerts_failed = 0
    skips = portfolio_skips or {}
    cst = constraints or PortfolioConstraints()

    for t in trades:
        if not trade_is_relevant_to_last_bar(t, df, last_bar_date, live_mode_relaxed=live_mode_relaxed):
            if execution_skip_counts is not None:
                execution_skip_counts["not_relevant_to_last_bar"] = int(execution_skip_counts.get("not_relevant_to_last_bar", 0)) + 1
            _record_execution_event(
                execution_events,
                "place_order_skipped",
                symbol=sym,
                reason="not_relevant_to_last_bar",
            )
            if trade_funnel is not None:
                trade_funnel.record_trade_not_relevant_last_bar(engine_label, sym)
            continue
        sig_date = _signal_bar_date_str(df, int(t.get("candidate_signal_bar", 0)))
        sk = signal_dedup_key(sym, combo_label, sig_date, interval)
        if trade_funnel is not None:
            trade_funnel.record_last_bar_trade_row(engine_label, sym)
        if not silent_signal_telemetry:
            new_signals += 1
        adapter_name = type(execution_adapter).__name__ if execution_adapter is not None else ""
        signal_entry = _coerce_float_or_none(t.get("entry"))
        signal_stop = _coerce_float_or_none(t.get("stop"))
        signal_target = _coerce_float_or_none(t.get("target"))
        signal_risk_per_share = (
            abs(float(signal_entry) - float(signal_stop))
            if signal_entry is not None and signal_stop is not None
            else None
        )
        signal_rr = _coerce_float_or_none(t.get("final_rr"))
        if signal_rr is None:
            signal_rr = _coerce_float_or_none(t.get("r_multiple"))
        if not silent_signal_telemetry:
            paper_live_log_event("SIGNAL", symbol=sym, signal_bar_date=sig_date, combo_label=combo_label)
            _record_execution_event(
                execution_events,
                "signal_seen",
                symbol=sym,
                adapter=adapter_name,
                signal_bar_date=sig_date,
                combo_label=combo_label,
                interval=interval,
            )
            _append_execution_order_event(
                state,
                event_type="signal_seen",
                symbol=sym,
                adapter=adapter_name,
                entry=signal_entry,
                stop=signal_stop,
                target=signal_target,
                stop_loss=signal_stop,
                take_profit=signal_target,
                risk_per_share=signal_risk_per_share,
                rr=signal_rr,
                config=ranking_preset_name or combo_label,
                preset=ranking_preset_name or combo_label,
                signal_date=sig_date,
                intended_entry_date=str(t.get("entry_date", ""))[:10],
                reason=f"{combo_label}|{interval}|{sig_date}",
            )
        entry_execution_price_info: dict[str, Any] | None = None
        if execution_adapter is not None:
            adapter_row_entry = _adapter_positions_by_symbol(execution_adapter_positions).get(sym.strip().upper())
            res_entry = _resolve_execution_price(
                sym=sym,
                execution_adapter=execution_adapter,
                adapter_row=adapter_row_entry,
                interval=interval,
                decision_kind="entry",
                market_is_open=execution_market_is_open,
                df=df,
                execution_events=execution_events,
                state=state,
            )
            if not res_entry.get("ok"):
                price_block_reason = str(res_entry.get("block_reason") or "price_unavailable_entry_blocked")
                price_ts = str(res_entry.get("price_timestamp") or "")
                price_age = res_entry.get("price_age_seconds")
                price_threshold = _max_price_age_seconds_for_interval(interval)
                if execution_skip_counts is not None:
                    execution_skip_counts["other"] = int(execution_skip_counts.get("other", 0)) + 1
                _record_order_skipped_for_signal(
                    state=state,
                    execution_events=execution_events,
                    symbol=sym,
                    raw_reason=price_block_reason,
                    adapter=adapter_name,
                    signal_bar_date=sig_date,
                    combo_label=combo_label,
                    interval=interval,
                    engine_label=engine_label,
                    details={
                        "price_timestamp": price_ts,
                        "price_age_seconds": price_age,
                        "max_price_age_seconds": price_threshold,
                        "fallback_chain": res_entry.get("fallback_chain"),
                        "stale_decision_reason": res_entry.get("stale_decision_reason"),
                        "selected_source": res_entry.get("selected_source"),
                    },
                )
                logger.warning(
                    "[execution] event=%s symbol=%s interval=%s price_timestamp=%s price_age_seconds=%s threshold_seconds=%s stale_decision_reason=%s",
                    price_block_reason,
                    sym,
                    interval,
                    price_ts,
                    price_age,
                    price_threshold,
                    res_entry.get("stale_decision_reason") or "",
                )
                if trade_funnel is not None:
                    trade_funnel.record_entry_block(engine_label, sym, price_block_reason)
                continue
            entry_execution_price_info = dict(res_entry)
        if state.has_processed_signal(sk):
            paper_live_log_event("SKIP", symbol=sym, reason="already_processed_signal")
            if execution_skip_counts is not None:
                execution_skip_counts["other"] = int(execution_skip_counts.get("other", 0)) + 1
            _record_order_skipped_for_signal(
                state=state,
                execution_events=execution_events,
                symbol=sym,
                raw_reason="already_processed_signal",
                adapter=adapter_name,
                signal_bar_date=sig_date,
                combo_label=combo_label,
                interval=interval,
                engine_label=engine_label,
            )
            if trade_funnel is not None:
                trade_funnel.record_entry_block(engine_label, sym, "already_processed_signal")
            continue
        if state.has_open_for_symbol(sym):
            paper_live_log_event("SKIP", symbol=sym, reason="duplicate_symbol_open")
            if execution_skip_counts is not None:
                execution_skip_counts["duplicate_symbol_open"] = int(execution_skip_counts.get("duplicate_symbol_open", 0)) + 1
            _record_order_skipped_for_signal(
                state=state,
                execution_events=execution_events,
                symbol=sym,
                raw_reason="duplicate_symbol_open",
                adapter=adapter_name,
                signal_bar_date=sig_date,
                combo_label=combo_label,
                interval=interval,
                engine_label=engine_label,
            )
            skips["duplicate"] = int(skips.get("duplicate", 0)) + 1
            if trade_funnel is not None:
                trade_funnel.record_entry_block(engine_label, sym, "duplicate_symbol_open")
            continue

        sig_bar_idx = int(t.get("candidate_signal_bar", 0))
        if portfolio_state is not None and not reentry_allowed(
            sym, df, sig_bar_idx, portfolio_state, min_bars=int(cst.reentry_min_bars)
        ):
            paper_live_log_event("SKIP", symbol=sym, reason="reentry_cooldown_bars")
            if execution_skip_counts is not None:
                execution_skip_counts["other"] = int(execution_skip_counts.get("other", 0)) + 1
            _record_order_skipped_for_signal(
                state=state,
                execution_events=execution_events,
                symbol=sym,
                raw_reason="reentry_cooldown_bars",
                adapter=adapter_name,
                signal_bar_date=sig_date,
                combo_label=combo_label,
                interval=interval,
                engine_label=engine_label,
            )
            skips["cooldown"] = int(skips.get("cooldown", 0)) + 1
            if trade_funnel is not None:
                trade_funnel.record_entry_block(engine_label, sym, "reentry_cooldown_bars")
            continue

        po = paper_simulation_entry_open(df, t)
        if po is None:
            po = float(t.get("entry", 0.0))
        stp = float(t.get("stop", 0.0))
        if execution_adapter is not None and entry_execution_price_info is not None:
            live_entry_price = _coerce_float_or_none(entry_execution_price_info.get("price"))
            planned_risk = abs(float(po) - stp)
            drift = evaluate_fill_drift(
                intended_entry_price=float(po),
                actual_fill_price=live_entry_price,
                risk_per_share=planned_risk,
            )
            if bool(drift.get("evaluated")) and bool(drift.get("fill_drift_exceeded")):
                reason_drift = "entry_fill_drift_exceeds_limit"
                if execution_skip_counts is not None:
                    execution_skip_counts["other"] = int(execution_skip_counts.get("other", 0)) + 1
                _record_execution_event(
                    execution_events,
                    reason_drift,
                    symbol=sym,
                    adapter=adapter_name,
                    intended_entry_price=float(po),
                    current_price=live_entry_price,
                    stop=stp,
                    target=float(t.get("target", 0.0)),
                    risk_per_share=planned_risk,
                    fill_slippage_r=drift.get("fill_drift_r"),
                    max_slippage_r=drift.get("max_drift_r"),
                    price_source=entry_execution_price_info.get("price_source"),
                    price_method=entry_execution_price_info.get("price_method"),
                    price_timestamp=entry_execution_price_info.get("price_timestamp"),
                )
                _record_order_skipped_for_signal(
                    state=state,
                    execution_events=execution_events,
                    symbol=sym,
                    raw_reason=reason_drift,
                    adapter=adapter_name,
                    signal_bar_date=sig_date,
                    combo_label=combo_label,
                    interval=interval,
                    engine_label=engine_label,
                    details={
                        "intended_entry_price": float(po),
                        "live_reference_price": live_entry_price,
                        "risk_per_share": planned_risk,
                        "fill_slippage_r": drift.get("fill_drift_r"),
                        "max_slippage_r": drift.get("max_drift_r"),
                        "price_source": entry_execution_price_info.get("price_source"),
                        "price_method": entry_execution_price_info.get("price_method"),
                        "price_timestamp": entry_execution_price_info.get("price_timestamp"),
                    },
                    event_kwargs={
                        "side": "buy",
                        "entry": float(po),
                        "stop": stp,
                        "target": float(t.get("target", 0.0)),
                        "risk_per_share": planned_risk,
                        "intended_entry_price": float(po),
                        "actual_filled_avg_price": live_entry_price,
                        "fill_slippage_r": drift.get("fill_drift_r"),
                        "max_slippage_r": drift.get("max_drift_r"),
                        "current_price": live_entry_price,
                        "price_source": entry_execution_price_info.get("price_source"),
                        "price_method": entry_execution_price_info.get("price_method"),
                        "price_timestamp": entry_execution_price_info.get("price_timestamp"),
                        "price_age_seconds": entry_execution_price_info.get("price_age_seconds"),
                        "price_stale": entry_execution_price_info.get("price_stale"),
                        "quote_bid": entry_execution_price_info.get("quote_bid"),
                        "quote_ask": entry_execution_price_info.get("quote_ask"),
                        "quote_mid": entry_execution_price_info.get("quote_mid"),
                        "quote_spread": entry_execution_price_info.get("quote_spread"),
                        "quote_spread_pct": entry_execution_price_info.get("quote_spread_pct"),
                        "engine": engine_label,
                        "interval": interval,
                        "managed_by_strategy": True,
                    },
                )
                logger.warning(
                    "[execution] event=%s symbol=%s intended_entry=%s live_price=%s risk_per_share=%s drift_r=%s max_drift_r=%s",
                    reason_drift,
                    sym,
                    po,
                    live_entry_price,
                    planned_risk,
                    drift.get("fill_drift_r"),
                    drift.get("max_drift_r"),
                )
                if trade_funnel is not None:
                    trade_funnel.record_entry_block(engine_label, sym, reason_drift)
                continue
        if entry_intent_bucket is None:
            if allocation_fn is not None:
                ok_alloc, alloc_reason = allocation_fn(sym, state.open_positions, float(po), stp)
            else:
                ok_alloc, alloc_reason = can_allocate_new_position(
                    symbol=sym,
                    open_positions=state.open_positions,
                    planned_entry=float(po),
                    stop=stp,
                    constraints=cst,
                )
            if not ok_alloc:
                capacity_diag: dict[str, Any] = {}
                if str(alloc_reason) == "max_open_positions":
                    capacity_diag = _capacity_admission_diagnostics(
                        candidate=t,
                        open_positions=state.open_positions,
                        constraints=cst,
                    )
                    logger.info(
                        "[capacity] event=capacity_blocked_candidate_rank symbol=%s candidate_rank=%s worst_existing_position_rank=%s replacement_candidate=%s managed_positions=%s max_positions=%s strategy_risk=%s max_total_risk=%s",
                        sym,
                        capacity_diag.get("capacity_blocked_candidate_rank"),
                        capacity_diag.get("worst_existing_position_rank"),
                        capacity_diag.get("replacement_candidate"),
                        capacity_diag.get("managed_positions_count"),
                        capacity_diag.get("max_open_positions"),
                        capacity_diag.get("strategy_risk_fraction"),
                        capacity_diag.get("max_total_risk_pct"),
                    )
                skip_bucket = (
                    "limits"
                    if alloc_reason
                    in (
                        "max_open_positions",
                        "duplicate_symbol_open",
                        "duplicate_symbol_cross_engine",
                        "duplicate_symbol_same_engine",
                        "combined_hard_cap_block",
                    )
                    else "risk"
                )
                skips[skip_bucket] = int(skips.get(skip_bucket, 0)) + 1
                paper_live_log_event("SKIP", symbol=sym, reason=str(alloc_reason))
                if execution_skip_counts is not None:
                    execution_skip_counts["other"] = int(execution_skip_counts.get("other", 0)) + 1
                _record_order_skipped_for_signal(
                    state=state,
                    execution_events=execution_events,
                    symbol=sym,
                    raw_reason=str(alloc_reason),
                    adapter=adapter_name,
                    signal_bar_date=sig_date,
                    combo_label=combo_label,
                    interval=interval,
                    engine_label=engine_label,
                    details={"allocation_reason": str(alloc_reason), **capacity_diag},
                    event_kwargs={
                        "capacity_blocked_candidate_rank": capacity_diag.get("capacity_blocked_candidate_rank"),
                        "worst_existing_position_rank": capacity_diag.get("worst_existing_position_rank"),
                        "replacement_candidate": capacity_diag.get("replacement_candidate"),
                        "managed_positions_count": capacity_diag.get("managed_positions_count"),
                        "max_open_positions": capacity_diag.get("max_open_positions"),
                        "strategy_risk_fraction": capacity_diag.get("strategy_risk_fraction"),
                        "max_total_risk_pct": capacity_diag.get("max_total_risk_pct"),
                    }
                    if capacity_diag
                    else None,
                )
                if trade_funnel is not None:
                    trade_funnel.record_entry_block(engine_label, sym, str(alloc_reason))
                if placement_phase in (
                    "ranked_after_scan",
                    "dual_ranked_after_scan_weekly",
                    "dual_ranked_after_scan_daily",
                ):
                    log_candidate_pipeline(
                        "candidate_skipped_capacity_after_ranking",
                        log_prefix=candidate_log_prefix,
                        symbol=sym,
                        reason=str(alloc_reason),
                        capacity_blocked_candidate_rank=capacity_diag.get("capacity_blocked_candidate_rank"),
                        worst_existing_position_rank=capacity_diag.get("worst_existing_position_rank"),
                        replacement_candidate=capacity_diag.get("replacement_candidate"),
                        managed_positions_count=capacity_diag.get("managed_positions_count"),
                        max_open_positions=capacity_diag.get("max_open_positions"),
                        strategy_risk_fraction=capacity_diag.get("strategy_risk_fraction"),
                        max_total_risk_pct=capacity_diag.get("max_total_risk_pct"),
                    )
                continue

        pos = build_position_from_trade(
            t,
            combo_label=combo_label,
            interval=interval,
            df=df,
            last_checked_bar_date=last_bar_date,
            engine_label=engine_label,
            preset_name=ranking_preset_name or combo_label,
            live_mode_relaxed=live_mode_relaxed,
        )
        if use_floor_sizing:
            shares = position_size_shares_floor(
                capital=float(cst.capital),
                risk_per_trade=float(cst.risk_per_trade),
                entry=float(po),
                stop=stp,
            )
        else:
            shares = position_size_shares(
                capital=float(cst.capital),
                risk_per_trade=float(cst.risk_per_trade),
                entry=float(po),
                stop=stp,
            )
        if shares <= 0:
            skips["risk"] = int(skips.get("risk", 0)) + 1
            paper_live_log_event("SKIP", symbol=sym, reason="shares_lte_zero")
            if execution_skip_counts is not None:
                execution_skip_counts["other"] = int(execution_skip_counts.get("other", 0)) + 1
            _record_order_skipped_for_signal(
                state=state,
                execution_events=execution_events,
                symbol=sym,
                raw_reason="shares_lte_zero",
                adapter=adapter_name,
                signal_bar_date=sig_date,
                combo_label=combo_label,
                interval=interval,
                engine_label=engine_label,
            )
            if trade_funnel is not None:
                trade_funnel.record_entry_block(engine_label, sym, "shares_lte_zero")
            continue

        is_alpaca_execution = execution_adapter is not None and type(execution_adapter).__name__ == "AlpacaExecutionAdapter"
        if execution_adapter is not None and not bool(execution_adapter_health_ok):
            if execution_skip_counts is not None:
                execution_skip_counts["other"] = int(execution_skip_counts.get("other", 0)) + 1
            _record_order_skipped_for_signal(
                state=state,
                execution_events=execution_events,
                symbol=sym,
                raw_reason="adapter_health_failed",
                adapter=adapter_name,
                signal_bar_date=sig_date,
                combo_label=combo_label,
                interval=interval,
                engine_label=engine_label,
            )
            if trade_funnel is not None:
                trade_funnel.record_entry_block(engine_label, sym, "adapter_health_failed")
            continue
        if is_alpaca_execution and execution_control_state is not None:
            control_day = execution_control_day or trading_day_key()
            new_positions_today = int(
                (execution_daily_order_counter or {}).get(
                    "placed_today",
                    control_daily_new_positions_count(execution_control_state, control_day),
                )
            )
            control_decision = evaluate_pre_order_controls(
                symbol=sym,
                control_state=execution_control_state,
                orders_placed_this_run=int((execution_order_counter or {}).get("placed", 0)),
                new_positions_today=new_positions_today,
                allowed_symbols=execution_allowed_symbols,
                max_orders_per_run=execution_max_orders_per_run,
            )
            if not bool(control_decision.get("accepted")):
                if execution_skip_counts is not None:
                    execution_skip_counts["other"] = int(execution_skip_counts.get("other", 0)) + 1
                _record_order_skipped_for_signal(
                    state=state,
                    execution_events=execution_events,
                    symbol=sym,
                    raw_reason=str(control_decision.get("reason", "")),
                    adapter=adapter_name,
                    signal_bar_date=sig_date,
                    combo_label=combo_label,
                    interval=interval,
                    engine_label=engine_label,
                    details={"control": control_decision},
                )
                if trade_funnel is not None:
                    trade_funnel.record_entry_block(engine_label, sym, str(control_decision.get("reason", "execution_control_skipped")))
                continue

        if is_alpaca_execution:
            risk_signal = {
                "symbol": sym,
                "side": "buy",
                "entry": float(po),
                "stop": stp,
                "target": float(t.get("target", 0.0)),
            }
            risk_result = size_trade_for_execution(
                signal=risk_signal,
                equity=execution_account_equity,
                open_positions=state.open_positions,
                adapter_positions=execution_adapter_positions,
                config=execution_risk_config or RiskConfig(),
                market_is_open=execution_market_is_open,
                logger=logger,
            )
            _record_execution_event(
                execution_events,
                "execution_risk_decision",
                symbol=sym,
                accepted=bool(risk_result.get("accepted")),
                reason=str(risk_result.get("reason", "")),
                sizing=risk_result,
            )
            if not bool(risk_result.get("accepted")):
                skips["risk"] = int(skips.get("risk", 0)) + 1
                if execution_skip_counts is not None:
                    execution_skip_counts["other"] = int(execution_skip_counts.get("other", 0)) + 1
                _record_order_skipped_for_signal(
                    state=state,
                    execution_events=execution_events,
                    symbol=sym,
                    raw_reason=str(risk_result.get("reason", "")),
                    adapter=adapter_name,
                    signal_bar_date=sig_date,
                    combo_label=combo_label,
                    interval=interval,
                    engine_label=engine_label,
                    details={"sizing": risk_result},
                )
                if trade_funnel is not None:
                    trade_funnel.record_entry_block(engine_label, sym, str(risk_result.get("reason", "execution_risk_rejected")))
                continue
            shares = float(risk_result.get("qty_final", 0) or 0)
            pos["execution_risk_sizing"] = risk_result

        if execution_adapter is not None and execution_allowed_symbols is not None and sym.upper() not in execution_allowed_symbols:
            if execution_skip_counts is not None:
                execution_skip_counts["other"] = int(execution_skip_counts.get("other", 0)) + 1
            _record_order_skipped_for_signal(
                state=state,
                execution_events=execution_events,
                symbol=sym,
                raw_reason="not_in_allowed_symbols",
                adapter=adapter_name,
                signal_bar_date=sig_date,
                combo_label=combo_label,
                interval=interval,
                engine_label=engine_label,
                details={"allowed_symbols": sorted(execution_allowed_symbols)},
            )
            if trade_funnel is not None:
                trade_funnel.record_entry_block(engine_label, sym, "not_in_allowed_symbols")
            continue

        if (
            execution_adapter is not None
            and execution_max_orders_per_run is not None
            and entry_intent_bucket is None
        ):
            placed_so_far = int((execution_order_counter or {}).get("placed", 0))
            if placed_so_far >= int(execution_max_orders_per_run):
                if execution_skip_counts is not None:
                    execution_skip_counts["other"] = int(execution_skip_counts.get("other", 0)) + 1
                _record_order_skipped_for_signal(
                    state=state,
                    execution_events=execution_events,
                    symbol=sym,
                    raw_reason="max_orders_per_run",
                    adapter=adapter_name,
                    signal_bar_date=sig_date,
                    combo_label=combo_label,
                    interval=interval,
                    engine_label=engine_label,
                    details={
                        "max_orders_per_run": int(execution_max_orders_per_run),
                        "placed_so_far": placed_so_far,
                    },
                )
                if trade_funnel is not None:
                    trade_funnel.record_entry_block(engine_label, sym, "max_orders_per_run")
                continue

        pos["paper_entry_open"] = float(po)
        pos["paper_shares"] = float(shares)
        dist = abs(float(po) - stp)
        pos["initial_risk_dollars"] = float(shares) * float(dist)
        pos["shares"] = float(shares)
        pos["dollar_risk"] = float(shares) * float(dist)
        pos["risk_amount"] = float(shares) * float(dist)
        pos["entry"] = float(t.get("entry", pos.get("entry_price", 0.0)) or 0.0)
        pos["stop_loss"] = float(t.get("stop", pos.get("stop_price", 0.0)) or 0.0)
        pos["take_profit"] = float(t.get("target", pos.get("target_price", 0.0)) or 0.0)
        if not pos.get("rr"):
            pos["rr"] = _position_rr(pos)
        if not pos.get("config"):
            pos["config"] = str(pos.get("preset_name") or combo_label)
        if not pos.get("preset"):
            pos["preset"] = str(pos.get("preset_name") or combo_label)
        if not pos.get("signal_date"):
            pos["signal_date"] = sig_date
        if not pos.get("intended_entry_date"):
            pos["intended_entry_date"] = ent_date
        if not pos.get("source_signal_type"):
            pos["source_signal_type"] = "internal_trade_reconstruction"
        pos["current_r_multiple"] = 0.0
        pos["unrealized_pnl"] = 0.0

        if entry_intent_bucket is not None:
            entry_intent_bucket.append(
                {
                    "symbol": sym,
                    "combo_label": combo_label,
                    "interval": interval,
                    "trade": dict(t),
                    "sig_date": sig_date,
                    "sk": sk,
                    "planned_entry": float(po),
                    "planned_stop": float(stp),
                    "shares": float(shares),
                    "engine_label": engine_label,
                    "pos": dict(pos),
                }
            )
            log_candidate_pipeline(
                "candidate_collected",
                log_prefix=candidate_log_prefix,
                symbol=sym,
                sig_date=sig_date,
                score=t.get("score"),
                r_multiple=t.get("r_multiple"),
                close_position_in_range=t.get("close_position_in_range"),
                volume_ratio=t.get("volume_ratio"),
            )
            continue

        ek = alert_dedup_key(
            "entry",
            sym,
            combo_label,
            last_bar_date,
            str(t.get("entry_date", ""))[:10],
            "",
            interval=interval,
            output_scope=output_scope,
        )
        if state.alert_already_sent(ek):
            state.mark_signal_processed(sk)
            paper_live_log_event("SKIP", symbol=sym, reason="entry_alert_already_sent")
            if execution_skip_counts is not None:
                execution_skip_counts["other"] = int(execution_skip_counts.get("other", 0)) + 1
            _record_order_skipped_for_signal(
                state=state,
                execution_events=execution_events,
                symbol=sym,
                raw_reason="entry_alert_already_sent",
                adapter=adapter_name,
                signal_bar_date=sig_date,
                combo_label=combo_label,
                interval=interval,
                engine_label=engine_label,
            )
            if trade_funnel is not None:
                trade_funnel.record_entry_block(engine_label, sym, "entry_alert_already_sent")
            continue

        open_before = len(state.open_positions)
        ent_date = str(t.get("entry_date", ""))[:10]
        text = build_entry(
            symbol=sym,
            combo_label=combo_label,
            interval=interval,
            signal_bar_date=sig_date,
            planned_entry=float(po),
            stop=float(t.get("stop", 0.0)),
            target=float(t.get("target", 0.0)),
            expected_r=float(t.get("r_multiple", 0.0) or 0.0),
            reason_summary="fib_quality engine (same path as validation/paper)",
            run_timestamp=run_timestamp,
            entry_date=ent_date,
            open_positions_before=open_before,
            open_positions_after=open_before + 1,
            elapsed_sec=time.perf_counter() - cycle_started_perf,
            output_dir_display=str(output_dir.resolve()),
        )
        ok = True
        exec_ok = True
        if execution_adapter is not None:
            requested_entry_order_type = str(os.getenv("LIVE_ENTRY_ORDER_TYPE", "market") or "market").strip().lower()
            live_reference_price = entry_execution_price_info.get("price") if entry_execution_price_info else None
            payload = {
                "symbol": sym,
                "side": "buy",
                "qty": float(shares),
                "entry": float(po),
                "intended_entry_price": float(po),
                "stop": float(t.get("stop", 0.0)),
                "target": float(t.get("target", 0.0)),
                "risk": float(pos.get("dollar_risk", 0.0) or 0.0),
                "risk_per_share": _position_risk_per_share(pos),
                "risk_amount": _position_risk_amount(pos),
                "rr": _position_rr(pos),
                "order_type": requested_entry_order_type,
                "limit_price": float(po) if requested_entry_order_type == "limit" else None,
                "live_reference_price": live_reference_price,
                "price_source": entry_execution_price_info.get("price_source") if entry_execution_price_info else "",
                "price_method": entry_execution_price_info.get("price_method") if entry_execution_price_info else "",
                "price_timestamp": entry_execution_price_info.get("price_timestamp") if entry_execution_price_info else "",
                "price_age_seconds": entry_execution_price_info.get("price_age_seconds") if entry_execution_price_info else None,
                "price_stale": entry_execution_price_info.get("price_stale") if entry_execution_price_info else None,
                "quote_bid": entry_execution_price_info.get("quote_bid") if entry_execution_price_info else None,
                "quote_ask": entry_execution_price_info.get("quote_ask") if entry_execution_price_info else None,
                "quote_mid": entry_execution_price_info.get("quote_mid") if entry_execution_price_info else None,
                "quote_spread": entry_execution_price_info.get("quote_spread") if entry_execution_price_info else None,
                "quote_spread_pct": entry_execution_price_info.get("quote_spread_pct") if entry_execution_price_info else None,
                "config": pos.get("config") or combo_label,
                "preset": pos.get("preset") or pos.get("preset_name") or combo_label,
                "signal_date": sig_date,
                "intended_entry_date": ent_date,
                "position_id": pos.get("position_id"),
            }
            if pos.get("execution_risk_sizing"):
                payload["risk_sizing"] = pos.get("execution_risk_sizing")
            _record_execution_event(
                execution_events,
                "place_order_attempt",
                symbol=payload["symbol"],
                side=payload["side"],
                qty=payload["qty"],
                entry=payload["entry"],
                stop=payload["stop"],
                target=payload["target"],
                risk=payload["risk"],
                risk_per_share=payload.get("risk_per_share"),
                risk_amount=payload.get("risk_amount"),
                rr=payload.get("rr"),
                submitted_order_type=payload.get("order_type"),
                submitted_limit_price=payload.get("limit_price"),
                intended_entry_price=payload.get("intended_entry_price"),
                current_price=payload.get("live_reference_price"),
                price_source=payload.get("price_source"),
                price_method=payload.get("price_method"),
                price_timestamp=payload.get("price_timestamp"),
                price_age_seconds=payload.get("price_age_seconds"),
                price_stale=payload.get("price_stale"),
                quote_bid=payload.get("quote_bid"),
                quote_ask=payload.get("quote_ask"),
                quote_mid=payload.get("quote_mid"),
                quote_spread=payload.get("quote_spread"),
                quote_spread_pct=payload.get("quote_spread_pct"),
                config=payload.get("config"),
                preset=payload.get("preset"),
                signal_date=payload.get("signal_date"),
                intended_entry_date=payload.get("intended_entry_date"),
                position_id=payload.get("position_id"),
                adapter=type(execution_adapter).__name__,
            )
            _append_execution_order_event(
                state,
                event_type="place_order_attempt",
                symbol=payload["symbol"],
                side=payload["side"],
                qty=payload["qty"],
                entry=payload["entry"],
                stop=payload["stop"],
                target=payload["target"],
                risk=payload["risk"],
                risk_per_share=payload.get("risk_per_share"),
                risk_amount=payload.get("risk_amount"),
                rr=payload.get("rr"),
                config=payload.get("config"),
                preset=payload.get("preset"),
                signal_date=payload.get("signal_date"),
                intended_entry_date=payload.get("intended_entry_date"),
                position_id=payload.get("position_id"),
                adapter=type(execution_adapter).__name__,
                submitted_order_type=payload.get("order_type"),
                submitted_limit_price=payload.get("limit_price"),
                intended_entry_price=payload.get("intended_entry_price"),
                current_price=payload.get("live_reference_price"),
                price_source=payload.get("price_source"),
                price_method=payload.get("price_method"),
                price_timestamp=payload.get("price_timestamp"),
                price_age_seconds=payload.get("price_age_seconds"),
                price_stale=payload.get("price_stale"),
                quote_bid=payload.get("quote_bid"),
                quote_ask=payload.get("quote_ask"),
                quote_mid=payload.get("quote_mid"),
                quote_spread=payload.get("quote_spread"),
                quote_spread_pct=payload.get("quote_spread_pct"),
            )
            try:
                exec_result = execution_adapter.place_order(payload)
            except Exception as exc:  # noqa: BLE001
                exec_result = {
                    "accepted": False,
                    "adapter": type(execution_adapter).__name__,
                    "event": "place_order_failed",
                    "error": f"{type(exc).__name__}: {exc}",
                }
                logger.exception("[execution] type=failure action=place_order symbol=%s adapter=%s", sym, type(execution_adapter).__name__)
            exec_ok = bool(exec_result.get("accepted", False))
            if bool(exec_result.get("dry_run", False)):
                _record_execution_event(
                    execution_events,
                    "place_order_dry_run",
                    symbol=sym,
                    adapter=type(execution_adapter).__name__,
                    payload=payload,
                    result=exec_result,
                )
                _append_execution_order_event(
                    state,
                    event_type="place_order_dry_run",
                    symbol=sym,
                    side=payload["side"],
                    qty=payload["qty"],
                    entry=payload["entry"],
                    stop=payload["stop"],
                    target=payload["target"],
                    risk=payload["risk"],
                    risk_per_share=payload.get("risk_per_share"),
                    risk_amount=payload.get("risk_amount"),
                    rr=payload.get("rr"),
                    config=payload.get("config"),
                    preset=payload.get("preset"),
                    signal_date=payload.get("signal_date"),
                    intended_entry_date=payload.get("intended_entry_date"),
                    position_id=payload.get("position_id"),
                    adapter=type(execution_adapter).__name__,
                    submitted_order_type=payload.get("order_type"),
                    submitted_limit_price=payload.get("limit_price"),
                    intended_entry_price=payload.get("intended_entry_price"),
                    current_price=payload.get("live_reference_price"),
                    price_source=payload.get("price_source"),
                    price_method=payload.get("price_method"),
                    price_timestamp=payload.get("price_timestamp"),
                    price_age_seconds=payload.get("price_age_seconds"),
                    price_stale=payload.get("price_stale"),
                    quote_bid=payload.get("quote_bid"),
                    quote_ask=payload.get("quote_ask"),
                    quote_mid=payload.get("quote_mid"),
                    quote_spread=payload.get("quote_spread"),
                    quote_spread_pct=payload.get("quote_spread_pct"),
                    result=exec_result,
                    accepted=True,
                    dry_run=True,
                )
            if not exec_ok:
                failed_event_type = "place_order_failed" if str(exec_result.get("event", "")) == "place_order_failed" else "place_order_rejected"
                logger.warning(
                    "[execution] type=rejection action=place_order symbol=%s adapter=%s details=%s",
                    sym,
                    type(execution_adapter).__name__,
                    exec_result,
                )
                _record_execution_event(
                    execution_events,
                    failed_event_type,
                    symbol=sym,
                    adapter=type(execution_adapter).__name__,
                    result=exec_result,
                )
                _append_execution_order_event(
                    state,
                    event_type=failed_event_type,
                    symbol=sym,
                    side=payload["side"],
                    qty=payload["qty"],
                    entry=payload["entry"],
                    stop=payload["stop"],
                    target=payload["target"],
                    risk=payload["risk"],
                    risk_per_share=payload.get("risk_per_share"),
                    risk_amount=payload.get("risk_amount"),
                    rr=payload.get("rr"),
                    config=payload.get("config"),
                    preset=payload.get("preset"),
                    signal_date=payload.get("signal_date"),
                    intended_entry_date=payload.get("intended_entry_date"),
                    position_id=payload.get("position_id"),
                    adapter=type(execution_adapter).__name__,
                    submitted_order_type=payload.get("order_type"),
                    submitted_limit_price=payload.get("limit_price"),
                    intended_entry_price=payload.get("intended_entry_price"),
                    current_price=payload.get("live_reference_price"),
                    price_source=payload.get("price_source"),
                    price_method=payload.get("price_method"),
                    price_timestamp=payload.get("price_timestamp"),
                    price_age_seconds=payload.get("price_age_seconds"),
                    price_stale=payload.get("price_stale"),
                    quote_bid=payload.get("quote_bid"),
                    quote_ask=payload.get("quote_ask"),
                    quote_mid=payload.get("quote_mid"),
                    quote_spread=payload.get("quote_spread"),
                    quote_spread_pct=payload.get("quote_spread_pct"),
                    result=exec_result,
                    accepted=False,
                )
            else:
                if execution_order_counter is not None:
                    execution_order_counter["placed"] = int(execution_order_counter.get("placed", 0)) + 1
                if is_alpaca_execution and execution_daily_order_counter is not None:
                    execution_daily_order_counter["placed_today"] = int(
                        execution_daily_order_counter.get("placed_today", 0)
                    ) + 1
                if (
                    is_alpaca_execution
                    and execution_control_state is not None
                    and not bool(exec_result.get("dry_run", False))
                ):
                    updated_control_state = record_new_position_for_day(
                        execution_control_state,
                        execution_control_day,
                    )
                    persisted_control_state = save_control_state(updated_control_state)
                    execution_control_state.clear()
                    execution_control_state.update(persisted_control_state)
                _record_execution_event(
                    execution_events,
                    "place_order_success",
                    symbol=sym,
                    adapter=type(execution_adapter).__name__,
                    result=exec_result,
                )
                _append_execution_order_event(
                    state,
                    event_type="place_order_success",
                    symbol=sym,
                    side=payload["side"],
                    qty=payload["qty"],
                    entry=payload["entry"],
                    stop=payload["stop"],
                    target=payload["target"],
                    risk=payload["risk"],
                    risk_per_share=payload.get("risk_per_share"),
                    risk_amount=payload.get("risk_amount"),
                    rr=payload.get("rr"),
                    config=payload.get("config"),
                    preset=payload.get("preset"),
                    signal_date=payload.get("signal_date"),
                    intended_entry_date=payload.get("intended_entry_date"),
                    position_id=payload.get("position_id"),
                    adapter=type(execution_adapter).__name__,
                    submitted_order_type=payload.get("order_type"),
                    submitted_limit_price=payload.get("limit_price"),
                    intended_entry_price=payload.get("intended_entry_price"),
                    current_price=payload.get("live_reference_price"),
                    price_source=payload.get("price_source"),
                    price_method=payload.get("price_method"),
                    price_timestamp=payload.get("price_timestamp"),
                    price_age_seconds=payload.get("price_age_seconds"),
                    price_stale=payload.get("price_stale"),
                    quote_bid=payload.get("quote_bid"),
                    quote_ask=payload.get("quote_ask"),
                    quote_mid=payload.get("quote_mid"),
                    quote_spread=payload.get("quote_spread"),
                    quote_spread_pct=payload.get("quote_spread_pct"),
                    result=exec_result,
                    accepted=True,
                    dry_run=bool(exec_result.get("dry_run", False)),
                )
                order_status = str(exec_result.get("status") or "").strip().lower()
                pos["intended_entry_price"] = float(po)
                pos["entry_order_type"] = str(exec_result.get("submitted_order_type") or exec_result.get("type") or payload.get("order_type") or "")
                pos["entry_order_limit_price"] = exec_result.get("submitted_limit_price") or payload.get("limit_price")
                pos["entry_live_reference_price"] = payload.get("live_reference_price")
                pos["entry_live_price_source"] = payload.get("price_source")
                pos["entry_live_price_method"] = payload.get("price_method")
                pos["entry_live_price_timestamp"] = payload.get("price_timestamp")
                pos["entry_quote_bid"] = payload.get("quote_bid")
                pos["entry_quote_ask"] = payload.get("quote_ask")
                pos["entry_quote_mid"] = payload.get("quote_mid")
                pos["entry_quote_spread"] = payload.get("quote_spread")
                pos["entry_quote_spread_pct"] = payload.get("quote_spread_pct")
                pos["entry_order_id"] = str(exec_result.get("order_id") or "")
                pos["entry_order_status"] = order_status
                pos["entry_order_submitted_at"] = str(exec_result.get("submitted_at") or "")
                if order_status in {"pending_new", "accepted", "new", "pending_cancel"}:
                    pos["entry_fill_pending"] = True
                else:
                    pos["entry_fill_pending"] = False
                filled_avg = _coerce_float_or_none(exec_result.get("filled_avg_price"))
                if filled_avg is not None:
                    pos["actual_fill_price"] = float(filled_avg)
                    drift = evaluate_fill_drift(
                        intended_entry_price=float(po),
                        actual_fill_price=float(filled_avg),
                        risk_per_share=_position_risk_per_share(pos),
                    )
                    if drift.get("fill_drift_exceeded"):
                        apply_fill_drift_guard(
                            pos,
                            drift,
                            record_event=lambda et, **kw: _record_execution_event(execution_events, et, symbol=sym, **kw),
                        )
                        exec_ok = False
        if not exec_ok:
            alerts_failed += 1
            continue

        if not dry_run:
            if telegram_dry_run:
                logger.info("[telegram_dry_run] ENTRY %s", text[:500])
            else:
                ok = send_message(text, parse_mode=None)
        else:
            logger.info("[dry_run] ENTRY %s", text[:300])
        if ok:
            alerts_sent += 1
        else:
            alerts_failed += 1
        state.mark_alert_sent(ek)
        pos["entry_alert_sent"] = bool(ok)
        pos["status"] = "open"
        state.add_open_position(pos)
        state.mark_signal_processed(sk)
        new_entries += 1
        if recent_entries_collector is not None:
            recent_entries_collector.append(dict(pos))
        if trade_funnel is not None:
            trade_funnel.record_entry_executed(engine_label, sym)
        paper_live_log_event(
            "ENTRY",
            symbol=sym,
            entry_date=ent_date,
            paper_entry_open=float(po),
            shares=float(shares),
            stop=float(t.get("stop", 0.0)),
            target=float(t.get("target", 0.0)),
        )

        if not dry_run:
            append_csv_row(
                state.paths()["live_signals_csv"],
                {
                    "run_timestamp": run_timestamp,
                    "symbol": sym,
                    "combo_label": combo_label,
                    "interval": interval,
                    "signal_bar_date": sig_date,
                    "entry_date": str(t.get("entry_date", ""))[:10],
                    "candidate_signal_bar": int(t.get("candidate_signal_bar", 0)),
                    "entry": float(t.get("entry", 0.0)),
                    "stop": float(t.get("stop", 0.0)),
                    "target": float(t.get("target", 0.0)),
                    "entry_price": float(t.get("entry", 0.0)),
                    "stop_loss": float(t.get("stop", 0.0)),
                    "take_profit": float(t.get("target", 0.0)),
                    "risk_per_share": _position_risk_per_share(pos),
                    "risk_amount": _position_risk_amount(pos),
                    "rr": _position_rr(pos),
                    "config": _position_config_label(pos),
                    "preset": str(pos.get("preset") or pos.get("preset_name") or _position_config_label(pos)),
                    "signal_date": sig_date,
                    "intended_entry_date": ent_date,
                    "position_id": pos.get("position_id"),
                    "expected_r": float(t.get("r_multiple", 0.0) or 0.0),
                    "last_bar_date": last_bar_date,
                    "paper_entry_open": float(po),
                    "paper_shares": float(shares),
                    "submitted_order_type": pos.get("entry_order_type"),
                    "submitted_limit_price": pos.get("entry_order_limit_price"),
                    "submitted_stop_price": pos.get("entry_order_stop_price"),
                    "actual_filled_avg_price": pos.get("actual_fill_price"),
                    "fill_slippage_r": pos.get("fill_drift_r"),
                    "live_reference_price": pos.get("entry_live_reference_price"),
                    "live_reference_price_source": pos.get("entry_live_price_source"),
                    "live_reference_price_method": pos.get("entry_live_price_method"),
                    "live_reference_price_timestamp": pos.get("entry_live_price_timestamp"),
                    "quote_bid": payload.get("quote_bid") if execution_adapter is not None else None,
                    "quote_ask": payload.get("quote_ask") if execution_adapter is not None else None,
                    "quote_mid": payload.get("quote_mid") if execution_adapter is not None else None,
                    "quote_spread": payload.get("quote_spread") if execution_adapter is not None else None,
                    "quote_spread_pct": payload.get("quote_spread_pct") if execution_adapter is not None else None,
                },
                SIGNAL_CSV_FIELDS,
            )

    return new_signals, new_entries, alerts_sent, alerts_failed


def run_monitor_cycle(
    *,
    universe_file: Path,
    interval: str,
    combo_labels: list[str],
    output_dir: Path,
    warmup_years: int,
    benchmark: str,
    yahoo_throttle: float,
    dry_run: bool,
    telegram_dry_run: bool,
    telegram_enabled: bool = True,
    as_of: pd.Timestamp | None = None,
    send_message: Any = None,
    build_entry: Any = None,
    build_exit: Any = None,
    mode_label: str = "one_shot",
    signal_detection_mode: str = "last_closed_bar",
    lock_stale_seconds: float = 7200.0,
    runtime_warn_seconds: float | None = None,
    yahoo_fetch_max_retries: int = 2,
    send_lock_warning_telegram: bool = True,
    manage_run_lock: bool = True,
    dual_engine: bool = False,
    allow_universe_override: bool = False,
    universe_explicit_cli: bool = False,
    ohlcv_cache_dir: Path | None = None,
    refresh_cache: bool = False,
    cache_only: bool = False,
    preload_ohlcv: bool = False,
    preload_workers: int | None = None,
    live_mode_relaxed: bool = False,
    live_signals_input: list[LiveSignalCandidate] | None = None,
    live_signals_input_daily: list[LiveSignalCandidate] | None = None,
    live_signals_input_weekly: list[LiveSignalCandidate] | None = None,
    execution_mode: str = "paper",
    execution_max_orders_per_run: int | None = 1,
    execution_allowed_symbols: set[str] | list[str] | tuple[str, ...] | None = None,
    execution_risk_config: RiskConfig | None = None,
    verbose_execution_events: bool = False,
    cycle_wall_started_perf: float | None = None,
    exits_only: bool = False,
) -> dict[str, Any]:
    """One full scan + state update. Mutates ``state`` on disk via returned payload when not dry_run.

    When ``live_mode_relaxed`` is True, uses ``_apply_live_mode_relaxed_cfg`` (same helper as
    ``build_live_signal_candidates``) and last 1–2 bar relevance aligned with
    ``resolve_live_entry_trade`` — without calling the live scanner entrypoints directly.
    """
    from services.telegram_alerts import (
        build_entry_alert,
        build_exit_alert,
        build_pretty_run_summary_alert,
        send_telegram_message,
    )

    if send_message is None:
        send_message = send_telegram_message
    if build_entry is None:
        build_entry = build_entry_alert
    if build_exit is None:
        build_exit = build_exit_alert

    run_ts = utc_now_iso()
    t0 = pd.Timestamp.now(tz="UTC")
    output_dir = Path(output_dir)
    if dual_engine:
        from services.live_production_constants import (
            ensure_dual_engine_directory_layout,
            expected_dual_engine_output_dir,
        )

        default_dual_root = expected_dual_engine_output_dir()
        output_dir = Path(output_dir).resolve()
        ensure_dual_engine_directory_layout(output_dir)
        if output_dir != default_dual_root:
            logger.info(
                "[DUAL MODE ACTIVE] using explicit output_dir override=%s (default=%s)",
                output_dir,
                default_dual_root,
            )
        dual_banner = f"[DUAL MODE ACTIVE] output_dir={output_dir}"
        logger.info("%s", dual_banner)
        print(dual_banner, flush=True)
    output_scope = output_scope_key(output_dir)
    state = LivePaperState(output_dir=output_dir)
    if not dry_run:
        state.load()
    else:
        state.open_positions = []
        state.processed_signals = set()
        state.sent_alert_keys = set()

    n_open_before = len(state.open_positions)
    lock_behavior = "dry_run" if dry_run else "pending"
    lock_acquired = False
    lock_wait_seconds = 0.0
    run_lock: LiveRunLock | None = None
    if not dry_run and manage_run_lock:
        run_lock = LiveRunLock(state.paths()["run_lock"], stale_after_seconds=float(lock_stale_seconds))
        ok_lock, lock_behavior = run_lock.try_acquire()
        lock_acquired = ok_lock
        if not ok_lock:
            exited_due_to_active_lock = lock_behavior == "skipped_existing"
            logger.warning(
                "run aborted: output_dir lock not acquired (reason=%s exited_due_to_active_lock=%s). "
                "If reason is skipped_existing, see prior run.lock log for lock_age_sec and stale_threshold_sec.",
                lock_behavior,
                exited_due_to_active_lock,
            )
            if (
                send_lock_warning_telegram
                and lock_behavior != "skipped_existing"
                and telegram_enabled
                and not telegram_dry_run
            ):
                from services.telegram_alerts import telegram_credentials_available

                if telegram_credentials_available():
                    send_message(
                        "LIVE PAPER: run skipped because another instance holds the lock.\n"
                        f"output_dir={output_dir.resolve()}\nreason={lock_behavior}\n",
                        parse_mode=None,
                    )
            return {
                "run_timestamp": run_ts,
                "mode": mode_label,
                "interval": interval,
                "combos": combo_labels,
                "output_dir": str(output_dir.resolve()),
                "signal_detection_mode_used": signal_detection_mode,
                "lock_acquired": False,
                "lock_behavior": lock_behavior,
                "lock_wait_seconds": lock_wait_seconds,
                "n_symbols_attempted": 0,
                "n_symbols_processed": 0,
                "n_symbols_skipped": 0,
                "n_open_positions_before": n_open_before,
                "n_open_positions_after": n_open_before,
                "n_new_signals": 0,
                "n_new_entries": 0,
                "n_new_exits": 0,
                "stop_loss_triggered_count": 0,
                "n_alerts_sent": 0,
                "n_alerts_failed": 0,
                "n_errors": 0,
                "errors_sample": [],
                "runtime_seconds": 0.0,
                "n_symbols_with_trade_on_last_bar": 0,
                "n_symbols_with_signal_on_last_bar": 0,
                "n_signals_rejected_as_old": 0,
                "n_runtime_warnings": 0,
                "runtime_warnings_sample": [],
                "summary_alert_status": "skipped_lock",
                "summary_alert_dedup_key": "",
                "summary_alert_fail_reason": "",
            }

    elif not dry_run:
        lock_acquired = True
        lock_behavior = "caller_managed"

    try:
        reset_atomic_write_stats()
        cycle_started_perf = float(cycle_wall_started_perf) if cycle_wall_started_perf is not None else time.perf_counter()
        execution_events: list[dict[str, Any]] = []
        state_write_errors: list[str] = []
        execution_skip_counts: dict[str, int] = {"not_relevant_to_last_bar": 0, "duplicate_symbol_open": 0, "other": 0}
        execution_mode_l = str(execution_mode or "paper").strip().lower()
        ensure_execution_order_events_files(
            state.paths()["execution_order_events_csv"],
            state.paths()["execution_order_events_jsonl"],
        )
        execution_adapter: ExecutionAdapter | None = None
        execution_adapter_health: dict[str, Any] = {
            "ok": True,
            "account_ok": True,
            "positions_ok": True,
            "base_url": "",
            "paper": execution_mode_l != "alpaca",
            "error": "",
            "timestamp": utc_now_iso(),
        }
        try:
            execution_adapter = _build_execution_adapter(execution_mode, logger)
            logger.info("[execution] adapter_initialized mode=%s adapter=%s", execution_mode, type(execution_adapter).__name__)
        except Exception as exc:  # noqa: BLE001
            if execution_mode_l != "alpaca":
                raise
            execution_adapter_health = {
                "ok": False,
                "account_ok": False,
                "positions_ok": False,
                "base_url": str(os.getenv("ALPACA_BASE_URL", "")),
                "paper": "paper-api.alpaca.markets" in str(os.getenv("ALPACA_BASE_URL", "")).lower(),
                "error": f"{type(exc).__name__}: {exc}",
                "timestamp": utc_now_iso(),
            }
            logger.exception("[execution] adapter=alpaca action=adapter_init_failed")
            execution_adapter = ExecutionDisabledAdapter(adapter_name="alpaca", reason=execution_adapter_health["error"])
            _record_execution_event(
                execution_events,
                "adapter_health_failed",
                adapter="alpaca",
                error=execution_adapter_health["error"],
                health=execution_adapter_health,
            )
            _append_execution_order_event(
                state,
                event_type="adapter_health_failed",
                adapter="alpaca",
                status="failed",
                reason="adapter_init_failed",
                result={"error": execution_adapter_health["error"], "raw_response": execution_adapter_health},
                accepted=False,
            )
        execution_order_counter: dict[str, int] = {"placed": 0}
        execution_daily_order_counter: dict[str, int] = {"placed_today": 0}
        execution_control_state: dict[str, Any] | None = None
        execution_control_day: str | None = None
        execution_allowed_symbols_set: set[str] | None = None
        if execution_allowed_symbols:
            execution_allowed_symbols_set = {
                str(s).strip().upper()
                for s in execution_allowed_symbols
                if str(s).strip()
            }
        effective_max_orders_per_run = (
            max(0, int(execution_max_orders_per_run))
            if execution_mode_l == "alpaca" and execution_max_orders_per_run is not None
            else None
        )
        effective_risk_config: RiskConfig | None = None
        execution_account_equity: float | None = None
        execution_adapter_positions: list[dict[str, Any]] = []
        execution_market_is_open: bool | None = None
        if execution_mode_l == "alpaca":
            execution_control_state = load_control_state(create_if_missing=True)
            execution_control_day = trading_day_key()
            execution_daily_order_counter["placed_today"] = control_daily_new_positions_count(
                execution_control_state,
                execution_control_day,
            )
            execution_allowed_symbols_set = merged_allowed_symbols(
                execution_control_state,
                execution_allowed_symbols_set,
            )
            effective_max_orders_per_run = control_effective_max_orders_per_run(
                execution_control_state,
                execution_max_orders_per_run,
            )
            effective_risk_config = execution_risk_config or risk_config_from_control_state(execution_control_state)
            env_forces_dry_run = str(os.getenv("ALPACA_DRY_RUN", "")).strip().lower() in ("1", "true", "yes", "on")
            if execution_adapter is not None:
                setattr(
                    execution_adapter,
                    "dry_run",
                    bool(execution_control_state.get("alpaca_dry_run", True)),
                )
            effective_adapter_dry_run = bool(getattr(execution_adapter, "dry_run", execution_control_state.get("alpaca_dry_run", True)))
            if env_forces_dry_run != effective_adapter_dry_run:
                _record_execution_event(
                    execution_events,
                    "execution_env_override_ignored",
                    requested_env_dry_run=env_forces_dry_run,
                    effective_dry_run=effective_adapter_dry_run,
                    reason="control_state_is_authoritative",
                )
            _record_execution_event(
                execution_events,
                "execution_control_context",
                control_state_path=str(CONTROL_STATE_PATH),
                kill_switch_enabled=bool(execution_control_state.get("kill_switch_enabled", True)),
                alpaca_dry_run=effective_adapter_dry_run,
                max_orders_per_run=effective_max_orders_per_run,
                max_new_positions_per_day=int(execution_control_state.get("max_new_positions_per_day", 1)),
                new_positions_today=int(execution_daily_order_counter.get("placed_today", 0)),
                allowed_symbols=sorted(execution_allowed_symbols_set) if execution_allowed_symbols_set is not None else [],
            )
            if execution_adapter is not None:
                check_health = getattr(execution_adapter, "check_health", None)
                if callable(check_health):
                    try:
                        execution_adapter_health = check_health()
                    except Exception as exc:  # noqa: BLE001
                        execution_adapter_health = {
                            "ok": False,
                            "account_ok": False,
                            "positions_ok": False,
                            "base_url": str(getattr(execution_adapter, "base_url", "")),
                            "paper": "paper-api.alpaca.markets" in str(getattr(execution_adapter, "base_url", "")).lower(),
                            "error": f"{type(exc).__name__}: {exc}",
                            "timestamp": utc_now_iso(),
                        }
                event_type = "adapter_health_ok" if bool(execution_adapter_health.get("ok")) else "adapter_health_failed"
                _record_execution_event(
                    execution_events,
                    event_type,
                    adapter=type(execution_adapter).__name__,
                    health=execution_adapter_health,
                    error=str(execution_adapter_health.get("error", "")),
                )
                _append_execution_order_event(
                    state,
                    event_type=event_type,
                    adapter=type(execution_adapter).__name__,
                    status="ok" if bool(execution_adapter_health.get("ok")) else "failed",
                    reason="" if bool(execution_adapter_health.get("ok")) else "adapter_health_failed",
                    result={"error": execution_adapter_health.get("error", ""), "raw_response": execution_adapter_health},
                    accepted=bool(execution_adapter_health.get("ok")),
                    dry_run=effective_adapter_dry_run,
                )
            if execution_adapter is not None and bool(execution_adapter_health.get("ok")):
                try:
                    account = execution_adapter.get_account()
                    execution_account_equity = _coerce_float_or_none(account.get("equity"))
                    if execution_account_equity is None:
                        execution_account_equity = _coerce_float_or_none(account.get("portfolio_value"))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("[execution_risk] failed to read alpaca account equity: %s", exc)
                    _record_execution_event(
                        execution_events,
                        "execution_risk_context_error",
                        reason="account_equity_unavailable",
                        error=f"{type(exc).__name__}: {exc}",
                    )
                try:
                    execution_adapter_positions = execution_adapter.get_positions()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("[execution_risk] failed to read alpaca positions: %s", exc)
                    _record_execution_event(
                        execution_events,
                        "execution_risk_context_error",
                        reason="adapter_positions_unavailable",
                        error=f"{type(exc).__name__}: {exc}",
                    )
                try:
                    get_clock = getattr(execution_adapter, "get_clock", None)
                    clock = get_clock() if callable(get_clock) else {}
                    if isinstance(clock, dict) and clock.get("is_open") is not None:
                        execution_market_is_open = bool(clock.get("is_open"))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("[execution_risk] failed to read alpaca market clock: %s", exc)
                    _record_execution_event(
                        execution_events,
                        "execution_risk_context_error",
                        reason="market_clock_unavailable",
                        error=f"{type(exc).__name__}: {exc}",
                    )
            elif execution_adapter is not None:
                logger.warning("[execution] adapter=alpaca health failed; signal scan will continue with execution disabled")
            try:
                risk_config_doc = effective_risk_config.to_dict() if effective_risk_config is not None else {}
            except Exception:
                risk_config_doc = {}
            _record_execution_event(
                execution_events,
                "execution_risk_context",
                equity=execution_account_equity,
                adapter_position_count=len(execution_adapter_positions),
                market_is_open=execution_market_is_open,
                risk_config=risk_config_doc,
                adapter_health=execution_adapter_health,
            )
        try:
            from ohlcv_parquet_cache import reset_perf_counters

            reset_perf_counters()
        except Exception:
            pass
        uni_path = validate_universe_for_live_paper(
            universe_file,
            allow_universe_override=bool(allow_universe_override),
            universe_explicit_cli=bool(universe_explicit_cli),
        )
        symbols = require_universe_file(uni_path)
        symbols, open_only_symbols = _merge_open_position_symbols(symbols, state.open_positions)
        uni_source = str(uni_path.resolve())
        _raw_symbols = list(symbols)
        _scan_seed = scan_order_seed_for_run(run_ts, uni_source)
        _shuffle_on = os.environ.get("LIVE_ENTRY_SHUFFLE_SCAN_ORDER", "1").strip().lower() not in (
            "0",
            "false",
            "no",
        )
        if _shuffle_on:
            symbols = deterministic_daily_shuffle(_raw_symbols, seed=_scan_seed)
        log_universe_order_loaded(
            universe_path=uni_source,
            raw_count=len(_raw_symbols),
            scan_order=list(symbols),
            seed=_scan_seed,
            shuffle_applied=bool(_shuffle_on),
        )

        from services.live_run_debug_stats import LiveRunDebugStats
        from services.live_signal_debug import LiveSignalDebug
        from services.live_trade_funnel_debug import LiveTradeFunnelDebug, funnel_debug_enabled

        run_dbg = LiveRunDebugStats()
        run_dbg.set_total_symbols_seen(len(symbols))

        _sf_en = os.environ.get("LIVE_SIGNAL_FLOW_DEBUG", "1").strip().lower() not in ("0", "false", "no", "off")
        signal_flow: LiveSignalDebug | None = LiveSignalDebug() if _sf_en else None
        if signal_flow is not None:
            signal_flow.total_symbols = len(symbols)

        trade_funnel: LiveTradeFunnelDebug | None = LiveTradeFunnelDebug() if funnel_debug_enabled() else None
        if trade_funnel is not None:
            trade_funnel.set_totals_seen(len(symbols))

        if dual_engine:
            from services.live_dual_paper_cycle import run_dual_engine_monitor_cycle

            return run_dual_engine_monitor_cycle(
                universe_file=universe_file,
                output_dir=output_dir,
                warmup_years=int(warmup_years),
                benchmark=str(benchmark),
                yahoo_throttle=float(yahoo_throttle),
                dry_run=bool(dry_run),
                telegram_dry_run=bool(telegram_dry_run),
                telegram_enabled=bool(telegram_enabled),
                as_of=as_of,
                send_message=send_message,
                build_entry=build_entry,
                build_exit=build_exit,
                mode_label=str(mode_label),
                signal_detection_mode=str(signal_detection_mode),
                yahoo_fetch_max_retries=int(yahoo_fetch_max_retries),
                runtime_warn_seconds=runtime_warn_seconds,
                state=state,
                run_ts=run_ts,
                cycle_started_perf=cycle_started_perf,
                lock_acquired=bool(lock_acquired),
                lock_behavior=str(lock_behavior),
                lock_wait_seconds=float(lock_wait_seconds),
                n_open_before=int(n_open_before),
                run_debug=run_dbg,
                allow_universe_override=bool(allow_universe_override),
                universe_explicit_cli=bool(universe_explicit_cli),
                signal_flow=signal_flow,
                ohlcv_cache_dir=ohlcv_cache_dir,
                refresh_cache=bool(refresh_cache),
                cache_only=bool(cache_only),
                preload_ohlcv=bool(preload_ohlcv),
                preload_workers=preload_workers,
                trade_funnel=trade_funnel,
                live_mode_relaxed=bool(live_mode_relaxed),
                live_signals_input_daily=live_signals_input_daily,
                live_signals_input_weekly=live_signals_input_weekly,
                execution_mode=str(execution_mode),
                execution_adapter=execution_adapter,
                execution_adapter_health_ok=bool(execution_adapter_health.get("ok", True)),
                execution_adapter_health=execution_adapter_health,
                execution_events=execution_events,
                execution_skip_counts=execution_skip_counts,
                execution_order_counter=execution_order_counter,
                execution_max_orders_per_run=effective_max_orders_per_run,
                execution_allowed_symbols_set=execution_allowed_symbols_set,
                execution_risk_config=effective_risk_config,
                execution_account_equity=execution_account_equity,
                execution_adapter_positions=execution_adapter_positions,
                execution_market_is_open=execution_market_is_open,
                execution_control_state=execution_control_state,
                execution_control_day=execution_control_day,
                execution_daily_order_counter=execution_daily_order_counter,
                verbose_execution_events=bool(verbose_execution_events),
                exits_only=bool(exits_only),
            )

        combo_label_req = str(combo_labels[0]) if combo_labels else PAPER_TRADING_PRESET_NAME
        require_preset_name_matches(str(interval), combo_label_req)
        _iv = str(interval).strip().lower()
        if _iv in ("1d", "d", "day", "daily"):
            if combo_label_req != DAILY_PRESET_NAME:
                raise RuntimeError(f"daily monitor requires {DAILY_PRESET_NAME!r}, got {combo_label_req!r}")
            paper_cfg = build_paper_algo_config()
            assert_paper_algo_config(paper_cfg)
            combo_label = DAILY_PRESET_NAME
        elif _iv in ("1wk", "1w", "weekly", "wk"):
            if combo_label_req != WEEKLY_PRESET_NAME:
                raise RuntimeError(f"weekly monitor requires {WEEKLY_PRESET_NAME!r}, got {combo_label_req!r}")
            paper_cfg = build_weekly_algo_config()
            assert_weekly_algo_config(paper_cfg)
            combo_label = WEEKLY_PRESET_NAME
        else:
            raise RuntimeError(f"locked paper/live interval must be 1d or 1wk (got {interval!r})")

        print_paper_config_banner(
            paper_cfg, interval=str(interval), regime_mode=PAPER_REGIME_MODE, logger=logger
        )
        logger.info("UNIVERSE SIZE: %s", len(symbols))
        print(f"UNIVERSE SIZE: {len(symbols)}", flush=True)

        if not dry_run:
            for p in state.open_positions:
                p["combo_label"] = combo_label

        end_test = pd.Timestamp.now(tz="UTC").normalize()
        fetch_start = end_test - pd.DateOffset(years=int(warmup_years))

        app = AppConfig(project_root=ROOT)
        app.timeframe = "1wk" if interval == "1wk" else interval
        app.yahoo_interval = interval

        errors: list[dict[str, str]] = []
        n_attempted = len(symbols)
        n_processed = 0
        n_skipped = 0
        n_new_signals = 0
        n_new_entries = 0
        n_exits = 0
        n_alerts_sent = 0
        n_alerts_failed = 0
        n_symbols_with_trade_on_last_bar = 0
        n_symbols_with_signal_on_last_bar = 0
        n_signals_rejected_as_old = 0
        runtime_warnings: list[str] = []
        recent_entries: list[dict[str, Any]] = []
        external_signals_by_symbol: dict[str, list[LiveSignalCandidate]] = {}
        if live_signals_input:
            logger.info("[PAPER USING EXTERNAL LIVE SIGNALS]")
            print("[PAPER USING EXTERNAL LIVE SIGNALS]", flush=True)
            for c in live_signals_input:
                sym_u = str(c.symbol).strip().upper()
                if not sym_u:
                    continue
                # Keep per-symbol buckets independent; never reuse a shared list/template.
                external_signals_by_symbol.setdefault(sym_u, []).append(c)

        if live_mode_relaxed:
            logger.info("[PAPER USING LIVE RELAX MODE]")
            print("[PAPER USING LIVE RELAX MODE]", flush=True)
            cfg = _apply_live_mode_relaxed_cfg(paper_cfg)
        else:
            cfg = paper_cfg
        need = min_bars_required(cfg)
        portfolio_state = load_portfolio_state()
        marks: dict[str, float] = {}
        portfolio_skips = {"risk": 0, "limits": 0, "cooldown": 0, "duplicate": 0}
        cap = float(os.environ.get("PAPER_CAPITAL", "100000") or 100_000.0)
        xe_pre, ae_pre, af_pre = process_broker_mark_exits_for_open_positions(
            state=state,
            combo_labels=[combo_label],
            interval_by_combo={combo_label: str(interval)},
            run_timestamp=run_ts,
            dry_run=dry_run,
            telegram_dry_run=telegram_dry_run,
            send_message=send_message,
            build_exit=build_exit,
            output_scope=output_scope,
            portfolio_state=portfolio_state,
            execution_adapter=execution_adapter,
            execution_adapter_health_ok=bool(execution_adapter_health.get("ok", True)),
            execution_adapter_positions=execution_adapter_positions,
            execution_events=execution_events,
            verbose_execution_events=verbose_execution_events,
            execution_market_is_open=execution_market_is_open,
        )
        n_exits += xe_pre
        n_alerts_sent += ae_pre
        n_alerts_failed += af_pre
        broker_exit_symbols_this_cycle = {
            str(row.get("symbol", "")).strip().upper()
            for row in execution_events
            if isinstance(row, dict)
            and row.get("event_type") == "close_position"
            and str(row.get("reason") or "") in ("stop_loss_breached", "take_profit_hit")
        }
        if _iv in ("1d", "d", "day", "daily"):
            constraints = PortfolioConstraints(
                capital=cap,
                risk_per_trade=float(DAILY_RISK_PER_TRADE),
                max_open_positions=int(DAILY_MAX_OPEN_POSITIONS),
                max_total_risk=float(DAILY_MAX_TOTAL_RISK),
            )
            _engine_tag = "daily"
        else:
            constraints = PortfolioConstraints(
                capital=cap,
                risk_per_trade=float(WEEKLY_RISK_PER_TRADE),
                max_open_positions=int(WEEKLY_MAX_OPEN_POSITIONS),
                max_total_risk=float(WEEKLY_MAX_TOTAL_RISK),
            )
            _engine_tag = "weekly"
        safety_state = load_safety_state()

        entry_intent_buffer: list[dict[str, Any]] = []
        symbol_entry_ctx: dict[str, dict[str, Any]] = {}
        defer_entry_placement = (
            not bool(exits_only)
            and os.environ.get("LIVE_DEFER_ENTRY_PLACEMENT", "1").strip().lower()
            not in (
                "0",
                "false",
                "no",
            )
        )

        from services.live_last_bar_diagnostic import last_bar_diagnostic_enabled, make_post_sim_near_last_bar_tap

        _lb_post_sim_rows_se: list[dict[str, Any]] = []
        _lb_tap_se = None
        if last_bar_diagnostic_enabled():
            _lb_tap_se, _lb_post_sim_rows_se = make_post_sim_near_last_bar_tap()
        _diag_sym_rows: list[tuple[str, pd.DataFrame, str, list[dict[str, Any]], str]] = []

        _fetch_kw: dict[str, Any] = {
            "max_retries": int(yahoo_fetch_max_retries),
            "yahoo_throttle": float(yahoo_throttle),
            "cache_dir": ohlcv_cache_dir,
            "refresh_cache": bool(refresh_cache),
            "cache_only": bool(cache_only),
        }
        from services.ohlcv_preload_store import (
            default_preload_workers,
            env_preload_enabled,
            get_raw_meta_from_store,
            log_preload_block,
            preload_ohlcv_store,
        )

        use_preload = bool(preload_ohlcv) or env_preload_enabled()
        ohlcv_store = None
        if use_preload:
            w_pre = int(preload_workers) if preload_workers is not None else default_preload_workers()
            ohlcv_store, pst = preload_ohlcv_store(
                symbols=list(symbols),
                interval=str(interval),
                start=fetch_start,
                end=end_test,
                benchmark_symbol=str(cfg.benchmark_sym or benchmark),
                cache_dir=ohlcv_cache_dir,
                refresh_cache=bool(refresh_cache),
                cache_only=bool(cache_only),
                max_fetch_workers=w_pre,
                yahoo_throttle=float(yahoo_throttle),
                max_retries=int(yahoo_fetch_max_retries),
            )
            pv = ",".join(symbols[: min(10, len(symbols))])
            if len(symbols) > 10:
                pv += "..."
            log_preload_block(enabled=True, symbols_preview=pv, workers=w_pre, stats=pst)
            logger.info("[PRELOAD] loop_data_source=in_memory_store")
            print("[PRELOAD] loop_data_source=in_memory_store", flush=True)

        if use_preload and ohlcv_store is not None:
            bench_df, bench_meta = get_raw_meta_from_store(
                ohlcv_store, str(cfg.benchmark_sym or benchmark), interval
            )
        else:
            bench_df, bench_meta = fetch_ohlcv_range_with_meta(
                str(cfg.benchmark_sym or benchmark),
                interval,
                fetch_start,
                end_test,
                **_fetch_kw,
            )
        if bench_df.empty:
            errors.append({"symbol": "__bench__", "error": f"empty benchmark ({bench_meta})"})
        else:
            for sym in symbols:
                try:
                    if use_preload and ohlcv_store is not None:
                        raw, meta = get_raw_meta_from_store(ohlcv_store, sym, interval)
                    else:
                        raw, meta = fetch_ohlcv_range_with_meta(
                            sym,
                            interval,
                            fetch_start,
                            end_test,
                            **_fetch_kw,
                        )
                    if raw is None or raw.empty:
                        logger.warning("skip %s: no data (%s)", sym, meta)
                        n_skipped += 1
                        run_dbg.record_skip(sym, _engine_tag, "no_ohlcv")
                        if trade_funnel is not None:
                            trade_funnel.record_symbol_skip(sym, "no_ohlcv")
                        continue
                    d0 = raw.rename(columns=str.lower)
                    d, last_bar_date = clip_to_fully_closed_bars(d0, interval, as_of=as_of)
                    stop_loss_closed_this_symbol = False
                    if state.has_open_for_symbol(sym):
                        xe_stop, ae_stop, af_stop = process_exits_for_symbol(
                            sym=sym,
                            combo_label=combo_label,
                            interval=interval,
                            trades=[],
                            state=state,
                            run_timestamp=run_ts,
                            dry_run=dry_run,
                            telegram_dry_run=telegram_dry_run,
                            send_message=send_message,
                            build_exit=build_exit,
                            output_scope=output_scope,
                            df=None,
                            portfolio_state=portfolio_state,
                            execution_adapter=execution_adapter,
                            execution_adapter_positions=execution_adapter_positions,
                            execution_events=execution_events,
                            verbose_execution_events=verbose_execution_events,
                            stop_check_df=d0,
                            stop_loss_only=True,
                            engine_cfg=cfg,
                            execution_market_is_open=execution_market_is_open,
                        )
                        n_exits += xe_stop
                        n_alerts_sent += ae_stop
                        n_alerts_failed += af_stop
                        stop_loss_closed_this_symbol = xe_stop > 0
                    if stop_loss_closed_this_symbol:
                        continue
                    if not last_bar_date or d is None or len(d) < need:
                        logger.warning(
                            "skip %s: not enough closed bars (%s<%s)",
                            sym,
                            len(d) if d is not None else 0,
                            need,
                        )
                        n_skipped += 1
                        run_dbg.record_skip(sym, _engine_tag, "insufficient_closed_bars")
                        if trade_funnel is not None:
                            trade_funnel.record_symbol_skip(sym, "insufficient_closed_bars")
                        continue
                    first_ts = pd.Timestamp(d.index[0]).normalize()
                    if first_ts > fetch_start.normalize():
                        n_skipped += 1
                        run_dbg.record_skip(sym, _engine_tag, "history_start_after_fetch_window")
                        if trade_funnel is not None:
                            trade_funnel.record_symbol_skip(sym, "history_start_after_fetch_window")
                        continue

                    n_processed += 1
                    run_dbg.record_processed(sym, _engine_tag)
                    if trade_funnel is not None:
                        trade_funnel.record_symbol_loaded(sym)
                    ext_rows = external_signals_by_symbol.get(sym.strip().upper()) or []
                    need_engine_scan = state.has_open_for_symbol(sym) or not ext_rows
                    if need_engine_scan:
                        trades = run_symbol_trades(
                            sym,
                            d,
                            bench_df,
                            cfg,
                            app,
                            uni_source,
                            signal_debug=signal_flow,
                            trade_funnel=trade_funnel,
                            engine=_engine_tag,
                            post_sim_near_last_bar_tap=_lb_tap_se,
                        )
                        for t in trades:
                            t["symbol"] = sym
                            t.setdefault("source_signal_type", "internal_trade_reconstruction")
                            t.setdefault("score", None)
                            t.setdefault("rank", None)
                            t.setdefault("notes", "")
                            t.setdefault("reason", "fib_quality engine (internal reconstruction)")
                            t.setdefault("original_signal_score", None)
                            t.setdefault("original_signal_rank", None)
                            t.setdefault("original_signal_notes", "")
                            t.setdefault("original_signal_reason", "")
                    else:
                        trades = []
                    entry_trades = trades
                    if ext_rows:
                        entry_trades = [_trade_from_live_candidate(c, sym=sym, df=d) for c in ext_rows]
                    if last_bar_diagnostic_enabled():
                        _diag_sym_rows.append((sym, d, str(last_bar_date), trades, _engine_tag))

                    try:
                        marks[sym.strip().upper()] = float(d["close"].iloc[-1])
                    except Exception:
                        marks[sym.strip().upper()] = float(trades[-1].get("entry", 0.0) or 0.0) if trades else 0.0

                    entry_le, entry_eq, sig_on_last = _last_bar_debug_flags(
                        trades, d, last_bar_date, live_mode_relaxed=live_mode_relaxed
                    )
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(
                            "last_bar_snapshot sym=%s combo=%s last_closed_bar_date=%s "
                            "trade_entry_date_le_last_bar=%s trade_entry_date_eq_last_bar=%s "
                            "candidate_signal_bar_on_last_bar=%s",
                            sym,
                            combo_label,
                            last_bar_date,
                            entry_le,
                            entry_eq,
                            sig_on_last,
                        )
                    if entry_eq:
                        n_symbols_with_trade_on_last_bar += 1
                    if sig_on_last:
                        n_symbols_with_signal_on_last_bar += 1
                    n_signals_rejected_as_old += count_signals_rejected_as_old(
                        sym,
                        combo_label,
                        interval,
                        d,
                        entry_trades,
                        last_bar_date,
                        state,
                        live_mode_relaxed=live_mode_relaxed,
                    )

                    xe, ae, af = process_exits_for_symbol(
                        sym=sym,
                        combo_label=combo_label,
                        interval=interval,
                        trades=trades,
                        state=state,
                        run_timestamp=run_ts,
                        dry_run=dry_run,
                        telegram_dry_run=telegram_dry_run,
                        send_message=send_message,
                        build_exit=build_exit,
                        output_scope=output_scope,
                        df=d,
                        portfolio_state=portfolio_state,
                        execution_adapter=execution_adapter,
                        execution_adapter_positions=execution_adapter_positions,
                        execution_events=execution_events,
                        verbose_execution_events=verbose_execution_events,
                        stop_check_df=d0,
                        engine_cfg=cfg,
                        execution_market_is_open=execution_market_is_open,
                    )
                    n_exits += xe
                    n_alerts_sent += ae
                    n_alerts_failed += af
                    if exits_only:
                        logger.warning("[single_cycle] exits_only=true; skipping new entry processing for %s", sym)
                        continue
                    if sym.strip().upper() in open_only_symbols or sym.strip().upper() in broker_exit_symbols_this_cycle:
                        continue

                    symbol_entry_ctx[sym.strip().upper()] = {
                        "df": d,
                        "last_bar_date": last_bar_date,
                        "entry_trades": entry_trades,
                    }
                    ns, ne, ae2, af2 = process_new_entries_for_symbol(
                        sym=sym,
                        combo_label=combo_label,
                        interval=interval,
                        df=d,
                        trades=entry_trades,
                        last_bar_date=last_bar_date,
                        state=state,
                        run_timestamp=run_ts,
                        dry_run=dry_run,
                        telegram_dry_run=telegram_dry_run,
                        send_message=send_message,
                        build_entry=build_entry,
                        output_dir=output_dir,
                        output_scope=output_scope,
                        cycle_started_perf=cycle_started_perf,
                        portfolio_state=portfolio_state,
                        constraints=constraints,
                        portfolio_skips=portfolio_skips,
                        use_floor_sizing=True,
                        engine_label=_engine_tag,
                        ranking_preset_name=combo_label,
                        trade_funnel=trade_funnel,
                        live_mode_relaxed=live_mode_relaxed,
                        recent_entries_collector=recent_entries,
                        execution_adapter=execution_adapter,
                        execution_adapter_health_ok=bool(execution_adapter_health.get("ok", True)),
                        execution_events=execution_events,
                        execution_skip_counts=execution_skip_counts,
                        execution_order_counter=execution_order_counter,
                        execution_max_orders_per_run=effective_max_orders_per_run,
                        execution_allowed_symbols=execution_allowed_symbols_set,
                        execution_risk_config=effective_risk_config,
                        execution_account_equity=execution_account_equity,
                        execution_adapter_positions=execution_adapter_positions,
                        execution_market_is_open=execution_market_is_open,
                        execution_control_state=execution_control_state,
                        execution_control_day=execution_control_day,
                        execution_daily_order_counter=execution_daily_order_counter,
                        verbose_execution_events=verbose_execution_events,
                        entry_intent_bucket=entry_intent_buffer if defer_entry_placement else None,
                    )
                    n_new_signals += ns
                    n_new_entries += ne
                    n_alerts_sent += ae2
                    n_alerts_failed += af2

                    xe2, ae3, af3 = process_exits_for_symbol(
                        sym=sym,
                        combo_label=combo_label,
                        interval=interval,
                        trades=trades,
                        state=state,
                        run_timestamp=run_ts,
                        dry_run=dry_run,
                        telegram_dry_run=telegram_dry_run,
                        send_message=send_message,
                        build_exit=build_exit,
                        output_scope=output_scope,
                        df=d,
                        portfolio_state=portfolio_state,
                        execution_adapter=execution_adapter,
                        execution_adapter_positions=execution_adapter_positions,
                        execution_events=execution_events,
                        verbose_execution_events=verbose_execution_events,
                        stop_check_df=d0,
                        engine_cfg=cfg,
                        execution_market_is_open=execution_market_is_open,
                    )
                    n_exits += xe2
                    n_alerts_sent += ae3
                    n_alerts_failed += af3

                except Exception as e:  # noqa: BLE001
                    logger.exception("symbol failed: %s", sym)
                    errors.append({"symbol": sym, "error": f"{type(e).__name__}: {e}"})
                    n_skipped += 1
                    run_dbg.record_skip(sym, _engine_tag, f"exception:{type(e).__name__}")
                    if trade_funnel is not None:
                        trade_funnel.record_symbol_skip(sym, f"exception:{type(e).__name__}")
                    if not dry_run:
                        from services.live_paper_state import append_error_log

                        append_error_log(state.paths()["live_errors_log"], f"{run_ts} {sym} {e!s}")

        if defer_entry_placement and entry_intent_buffer:
            ranked = rank_entry_intents(entry_intent_buffer)
            log_candidate_pipeline("candidate_ranked", n_ranked=len(ranked), defer_scan=True)
            placed_syms: list[str] = []
            for it in ranked:
                sym_u = str(it.get("symbol", "")).strip().upper()
                ctx = symbol_entry_ctx.get(sym_u)
                if not ctx:
                    continue
                trade_for_execution = dict(it.get("trade") or {})
                trade_for_execution.setdefault("candidate_rank", it.get("candidate_rank"))
                trade_for_execution.setdefault("candidate_rank_key", it.get("candidate_rank_key"))
                trade_for_execution.setdefault("candidate_score", trade_for_execution.get("score"))
                trade_for_execution.setdefault("rank", it.get("candidate_rank"))
                log_candidate_pipeline(
                    "candidate_selected",
                    symbol=sym_u,
                    candidate_rank=it.get("candidate_rank"),
                )
                ns3, ne3, ae3b, af3b = process_new_entries_for_symbol(
                    sym=it["symbol"],
                    combo_label=combo_label,
                    interval=interval,
                    df=ctx["df"],
                    trades=[trade_for_execution],
                    last_bar_date=ctx["last_bar_date"],
                    state=state,
                    run_timestamp=run_ts,
                    dry_run=dry_run,
                    telegram_dry_run=telegram_dry_run,
                    send_message=send_message,
                    build_entry=build_entry,
                    output_dir=output_dir,
                    output_scope=output_scope,
                    cycle_started_perf=cycle_started_perf,
                    portfolio_state=portfolio_state,
                    constraints=constraints,
                    portfolio_skips=portfolio_skips,
                    use_floor_sizing=True,
                    engine_label=_engine_tag,
                    ranking_preset_name=combo_label,
                    trade_funnel=trade_funnel,
                    live_mode_relaxed=live_mode_relaxed,
                    recent_entries_collector=recent_entries,
                    execution_adapter=execution_adapter,
                    execution_adapter_health_ok=bool(execution_adapter_health.get("ok", True)),
                    execution_events=execution_events,
                    execution_skip_counts=execution_skip_counts,
                    execution_order_counter=execution_order_counter,
                    execution_max_orders_per_run=effective_max_orders_per_run,
                    execution_allowed_symbols=execution_allowed_symbols_set,
                    execution_risk_config=effective_risk_config,
                    execution_account_equity=execution_account_equity,
                    execution_adapter_positions=execution_adapter_positions,
                    execution_market_is_open=execution_market_is_open,
                    execution_control_state=execution_control_state,
                    execution_control_day=execution_control_day,
                    execution_daily_order_counter=execution_daily_order_counter,
                    verbose_execution_events=verbose_execution_events,
                    silent_signal_telemetry=True,
                    placement_phase="ranked_after_scan",
                )
                n_new_signals += ns3
                n_new_entries += ne3
                n_alerts_sent += ae3b
                n_alerts_failed += af3b
                if ne3 > 0:
                    placed_syms.append(sym_u)
            audit_summary = alphabet_bias_audit_summary(
                placed_syms,
                total_scanned=int(n_processed),
                total_candidates=len(ranked),
            )
            audit_summary["selection_after_full_universe_scan"] = True
            audit_summary["scan_order_seed"] = int(_scan_seed)
            logger.info("alphabet_bias_audit_summary %s", audit_summary)

        if not dry_run:
            try:
                save_portfolio_state(portfolio_state)
            except Exception as exc:  # noqa: BLE001
                logger.exception("save_portfolio_state failed")
                state_write_errors.append(f"save_portfolio_state:{type(exc).__name__}: {exc}")
            try:
                safety_state = maybe_warn_signal_anomalies(
                    n_new_signals=int(n_new_signals),
                    safety=safety_state,
                    logger=logger,
                    is_weekly_engine=(_engine_tag == "weekly"),
                )
                save_safety_state(safety_state)
            except Exception as exc:  # noqa: BLE001
                logger.exception("save_safety_state failed")
                state_write_errors.append(f"save_safety_state:{type(exc).__name__}: {exc}")
            try:
                write_paper_positions_snapshot(
                    state.open_positions,
                    marks,
                    capital=float(constraints.capital),
                    path=PAPER_POSITIONS_JSON,
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("write_paper_positions_snapshot failed")
                state_write_errors.append(f"write_paper_positions_snapshot:{type(exc).__name__}: {exc}")

        top_entries = sorted(
            recent_entries,
            key=lambda p: float(p.get("score")) if p.get("score") is not None else float("-inf"),
            reverse=True,
        )[:5]
        details_lines = ["PAPER TRADE DETAILS"]
        for p in top_entries:
            details_lines.append(
                " - "
                f"symbol={p.get('symbol')} engine={p.get('engine_label')} "
                f"entry={p.get('entry_price')} stop={p.get('stop_price', p.get('stop'))} "
                f"target={p.get('target_price', p.get('target'))} score={p.get('score')} "
                f"rank={p.get('rank')} dollar_risk={p.get('dollar_risk')}"
            )
        summary_lines = (
            "[PAPER SUMMARY]\n"
            f"open_positions={len(state.open_positions)}\n"
            f"new_signals={n_new_signals}\n"
            f"new_entries={n_new_entries}\n"
            f"new_exits={n_exits}\n"
            f"stop_loss_triggered_count={_stop_loss_triggered_count(execution_events)}\n"
            f"skipped_due_to_risk={int(portfolio_skips.get('risk', 0))}\n"
            f"skipped_due_to_limits={int(portfolio_skips.get('limits', 0))}\n"
            f"skipped_due_to_cooldown={int(portfolio_skips.get('cooldown', 0))}\n"
            f"skipped_due_to_duplicate_symbol={int(portfolio_skips.get('duplicate', 0))}\n"
            + "\n".join(details_lines)
        )
        for ln in summary_lines.splitlines():
            logger.info("%s", ln)
        print(summary_lines, flush=True)
        paper_live_log_line(summary_lines.replace("\n", " | "))
        try:
            from ohlcv_parquet_cache import get_perf_snapshot
            from run_train_test_validation import print_ohlcv_perf_block

            print_ohlcv_perf_block()
            logger.info("[PERF] ohlcv snapshot %s", get_perf_snapshot())
        except Exception:
            logger.exception("ohlcv perf logging failed")

        runtime = max(0.0, time.perf_counter() - cycle_started_perf)
        n_open_after = len(state.open_positions)
    
        if runtime_warn_seconds is not None and float(runtime) > float(runtime_warn_seconds):
            runtime_warnings.append(
                f"runtime {float(runtime):.1f}s exceeds warn threshold {float(runtime_warn_seconds):.1f}s"
            )
    
        sum_dedup_key = summary_alert_dedup_key(
            run_timestamp=run_ts,
            interval=interval,
            output_dir=output_dir,
            combos=[combo_label],
        )
        summary_alert_status = "pending"
        summary_alert_fail_reason = ""
    
        reconciliation = _safe_reconcile_adapter_positions(execution_adapter, state.open_positions)
        _record_execution_event(
            execution_events,
            "reconcile_result",
            adapter=type(execution_adapter).__name__,
            ok=bool(reconciliation.get("reconciliation_ok", True)),
            error=str(reconciliation.get("reconciliation_error", "")),
            mismatch_count=reconciliation["mismatch_count"],
            adapter_position_count=reconciliation["adapter_position_count"],
            dashboard_open_position_count=reconciliation["dashboard_open_position_count"],
            engine_open_position_count=reconciliation["engine_open_position_count"],
        )
        _append_execution_order_event(
            state,
            event_type="reconcile_success" if bool(reconciliation.get("reconciliation_ok", True)) else "reconcile_failed",
            adapter=type(execution_adapter).__name__ if execution_adapter is not None else "",
            status="ok" if bool(reconciliation.get("reconciliation_ok", True)) else "failed",
            reason=str(reconciliation.get("reconciliation_error", "")),
            result={"raw_response": reconciliation, "error": str(reconciliation.get("reconciliation_error", ""))},
            accepted=bool(reconciliation.get("reconciliation_ok", True)),
            dry_run=bool(getattr(execution_adapter, "dry_run", False)) if execution_adapter is not None else False,
        )
        adapter_rows_for_drift: list[dict[str, Any]] = []
        if execution_adapter is not None:
            try:
                adapter_rows_for_drift = list(execution_adapter.get_positions())
            except Exception:  # noqa: BLE001
                adapter_rows_for_drift = []
        fill_drift_flagged = reconcile_entry_fill_drift(
            open_positions=state.open_positions,
            adapter_positions=adapter_rows_for_drift,
            execution_events=execution_events,
            record_event=lambda et, **kw: _record_execution_event(execution_events, et, **kw),
        )
        if fill_drift_flagged and fill_drift_auto_close_enabled():
            for pos in list(state.open_positions):
                if not pos.get("fill_drift_exceeded"):
                    continue
                sym_d = str(pos.get("symbol") or "").strip().upper()
                if execution_adapter is None or not sym_d:
                    continue
                try:
                    execution_adapter.close_position(sym_d, qty=_position_quantity(pos))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("[execution] fill_drift_auto_close_failed symbol=%s error=%s", sym_d, exc)
        reconciled_missing_broker_count = reconcile_missing_broker_positions(
            state=state,
            reconciliation=reconciliation,
            execution_adapter=execution_adapter,
            execution_events=execution_events,
        )
        unmanaged_external_broker_count = record_external_broker_positions(
            state=state,
            reconciliation=reconciliation,
            execution_adapter=execution_adapter,
            execution_events=execution_events,
        )
        if reconciled_missing_broker_count:
            n_open_after = len(state.open_positions)
        if verbose_execution_events:
            for row in execution_events[-200:]:
                logger.info("[execution_event] %s", json.dumps(row, default=str))
        else:
            for row in execution_events[-200:]:
                logger.debug("[execution_event] %s", json.dumps(row, default=str))
        logger.info(
            "[execution_summary] mode=%s adapter=%s skipped_not_relevant_to_last_bar_count=%s skipped_duplicate_symbol_open_count=%s skipped_other_count=%s events_tail_count=%s",
            execution_mode,
            type(execution_adapter).__name__,
            execution_skip_counts["not_relevant_to_last_bar"],
            execution_skip_counts["duplicate_symbol_open"],
            execution_skip_counts["other"],
            min(len(execution_events), 30),
        )
        if reconciliation["mismatch_count"] > 0:
            logger.warning(
                "[execution] type=mismatch action=reconcile mismatch_count=%s only_in_adapter=%s only_in_dashboard=%s",
                reconciliation["mismatch_count"],
                reconciliation["only_in_adapter"],
                reconciliation["only_in_dashboard"],
            )
        summary: dict[str, Any] = {
            "run_timestamp": run_ts,
            "mode": mode_label,
            "interval": interval,
            "combos": [combo_label],
            "config_preset": PAPER_TRADING_PRESET_NAME,
            "skipped_due_to_risk": int(portfolio_skips.get("risk", 0)),
            "skipped_due_to_limits": int(portfolio_skips.get("limits", 0)),
            "skipped_due_to_cooldown": int(portfolio_skips.get("cooldown", 0)),
            "skipped_due_to_duplicate_symbol": int(portfolio_skips.get("duplicate", 0)),
            "output_dir": str(output_dir.resolve()),
            "signal_detection_mode_used": signal_detection_mode,
            "lock_acquired": bool(lock_acquired),
            "lock_behavior": lock_behavior,
            "lock_wait_seconds": float(lock_wait_seconds),
            "n_symbols_attempted": n_attempted,
            "n_symbols_processed": n_processed,
            "n_symbols_skipped": n_skipped,
            "n_open_positions_before": n_open_before,
            "n_open_positions_after": n_open_after,
            "n_new_signals": n_new_signals,
            "n_new_entries": n_new_entries,
            "n_new_exits": n_exits,
            "stop_loss_triggered_count": _stop_loss_triggered_count(execution_events),
            "n_alerts_sent": n_alerts_sent,
            "n_alerts_failed": n_alerts_failed,
            "n_errors": len(errors),
            "errors_sample": errors[:50],
            "runtime_seconds": float(runtime),
            "n_symbols_with_trade_on_last_bar": n_symbols_with_trade_on_last_bar,
            "n_symbols_with_signal_on_last_bar": n_symbols_with_signal_on_last_bar,
            "n_signals_rejected_as_old": n_signals_rejected_as_old,
            "n_runtime_warnings": len(runtime_warnings),
            "runtime_warnings_sample": runtime_warnings[:20],
            "summary_alert_status": summary_alert_status,
            "summary_alert_dedup_key": sum_dedup_key,
            "summary_alert_fail_reason": summary_alert_fail_reason,
            "execution_mode": str(execution_mode),
            "execution_adapter": type(execution_adapter).__name__ if execution_adapter is not None else "",
            "execution_adapter_health": execution_adapter_health,
            "execution_adapter_health_ok": bool(execution_adapter_health.get("ok", True)),
            "execution_degraded": bool(execution_mode_l == "alpaca" and not execution_adapter_health.get("ok", False)),
            "execution_enabled": bool(execution_mode_l != "alpaca" or execution_adapter_health.get("ok", False)),
            "execution_max_orders_per_run": effective_max_orders_per_run,
            "execution_orders_placed_count": int(execution_order_counter.get("placed", 0)),
            "execution_allowed_symbols": sorted(execution_allowed_symbols_set) if execution_allowed_symbols_set is not None else [],
            "execution_risk_config": effective_risk_config.to_dict() if effective_risk_config is not None else {},
            "execution_account_equity": execution_account_equity,
            "execution_market_is_open": execution_market_is_open,
            "execution_control_state_path": str(CONTROL_STATE_PATH) if execution_control_state is not None else "",
            "execution_kill_switch_enabled": bool(execution_control_state.get("kill_switch_enabled", False)) if execution_control_state is not None else False,
            "execution_alpaca_dry_run": bool(getattr(execution_adapter, "dry_run", False)) if execution_mode_l == "alpaca" and execution_adapter is not None else bool((execution_control_state or {}).get("alpaca_dry_run", False)),
            "execution_max_new_positions_per_day": int(execution_control_state.get("max_new_positions_per_day", 0)) if execution_control_state is not None else None,
            "execution_new_positions_today_count": int(execution_daily_order_counter.get("placed_today", 0)),
            "execution_adapter_position_count": reconciliation["adapter_position_count"],
            "execution_dashboard_position_count": reconciliation["dashboard_open_position_count"],
            "execution_engine_open_position_count": reconciliation["engine_open_position_count"],
            "execution_position_mismatch_count": reconciliation["mismatch_count"],
            "execution_position_only_in_adapter": reconciliation["only_in_adapter"],
            "execution_position_only_in_dashboard": reconciliation["only_in_dashboard"],
            "execution_reconciliation_ok": bool(reconciliation.get("reconciliation_ok", True)),
            "execution_reconciliation_error": str(reconciliation.get("reconciliation_error", "")),
            "execution_reconciled_missing_broker_count": int(reconciled_missing_broker_count),
            "execution_unmanaged_external_broker_count": int(unmanaged_external_broker_count),
            "last_execution_events": execution_events[-30:],
            "skipped_not_relevant_to_last_bar_count": execution_skip_counts["not_relevant_to_last_bar"],
            "skipped_duplicate_symbol_open_count": execution_skip_counts["duplicate_symbol_open"],
            "skipped_other_count": execution_skip_counts["other"],
        }

        run_dbg.merge_into_summary(summary)
        if signal_flow is not None:
            signal_flow.merge_into_summary(summary)
        if trade_funnel is not None:
            from services.live_production_constants import total_combined_risk_fraction

            _cr = float(total_combined_risk_fraction(state.open_positions, capital=cap))
            trade_funnel.finalize_cycle(
                run_timestamp=run_ts,
                mode=mode_label,
                interval=str(interval),
                output_dir=str(output_dir.resolve()),
                n_new_signals_daily=int(n_new_signals) if _engine_tag == "daily" else 0,
                n_new_signals_weekly=int(n_new_signals) if _engine_tag == "weekly" else 0,
                n_new_entries=int(n_new_entries),
                n_new_exits=int(n_exits),
                n_open_positions=len(state.open_positions),
                combined_risk_fraction=_cr,
                n_signals_rejected_as_old=int(n_signals_rejected_as_old),
            )
            trade_funnel.write_artifacts()
            trade_funnel.merge_into_summary(summary)
            _tf_txt = trade_funnel.format_debug_summary_text()
            for _ln in _tf_txt.splitlines():
                logger.info("%s", _ln)
            print(_tf_txt, flush=True)

        if last_bar_diagnostic_enabled() and _diag_sym_rows:
            from services.live_last_bar_diagnostic import (
                build_last_bar_relevance_diagnostic,
                format_last_bar_diagnostic_console,
                write_last_bar_diagnostic_reports,
            )
            from services.live_production_constants import (
                assert_daily_algo_config,
                assert_weekly_algo_config,
                build_daily_algo_config,
                build_weekly_algo_config,
            )

            packs_single: dict[str, dict[str, Any]] = {}
            for sym, d, lb, trades, eng in _diag_sym_rows:
                su = str(sym).strip().upper()
                if su not in packs_single:
                    packs_single[su] = {
                        "d_d": pd.DataFrame(),
                        "lb_d": "",
                        "trades_d": [],
                        "d_w": pd.DataFrame(),
                        "lb_w": "",
                        "trades_w": [],
                    }
                slot = packs_single[su]
                if str(eng).lower() == "daily":
                    slot["d_d"] = d
                    slot["lb_d"] = lb
                    slot["trades_d"] = trades
                else:
                    slot["d_w"] = d
                    slot["lb_w"] = lb
                    slot["trades_w"] = trades
            cfg_d_se = build_daily_algo_config()
            cfg_w_se = build_weekly_algo_config()
            assert_daily_algo_config(cfg_d_se)
            assert_weekly_algo_config(cfg_w_se)
            _funnel_doc_se = trade_funnel.build_json_document() if trade_funnel is not None else {}
            _ts_safe_se = str(run_ts).replace(":", "-")
            _prefix_se = Path(output_dir) / f"last_bar_relevance_diagnostic_{_ts_safe_se}"
            _diag_doc_se = build_last_bar_relevance_diagnostic(
                run_timestamp=run_ts,
                mode=str(mode_label),
                packs=packs_single,
                cfg_daily=cfg_d_se,
                cfg_weekly=cfg_w_se,
                post_sim_rows=_lb_post_sim_rows_se,
                funnel_doc=_funnel_doc_se,
            )
            _paths_se = write_last_bar_diagnostic_reports(
                _prefix_se, _diag_doc_se, post_sim_rows=_lb_post_sim_rows_se
            )
            summary["last_bar_relevance_diagnostic_json"] = _paths_se.get("json", "")
            summary["last_bar_relevance_diagnostic_prefix"] = str(_prefix_se)
            for _k2, _p2 in _paths_se.items():
                summary[f"last_bar_relevance_diagnostic_{_k2}"] = _p2
            _txt_se = format_last_bar_diagnostic_console(_diag_doc_se)
            for _ln2 in _txt_se.splitlines():
                logger.info("%s", _ln2)
            print(_txt_se, flush=True)

        if logger.isEnabledFor(logging.DEBUG):
            logger.info(
                "last_bar_signal_summary n_symbols_with_trade_on_last_bar=%s "
                "n_symbols_with_signal_on_last_bar=%s n_signals_rejected_as_old=%s",
                n_symbols_with_trade_on_last_bar,
                n_symbols_with_signal_on_last_bar,
                n_signals_rejected_as_old,
            )
    
        if dry_run:
            summary["summary_alert_status"] = "skipped_dry_run"

        if not dry_run:
            from services.telegram_alerts import telegram_credentials_available
    
            run_display = f"{run_ts} (UTC)"
            out_disp = str(output_dir.resolve())
            sm_text = build_pretty_run_summary_alert(
                run_timestamp=run_ts,
                mode=str(mode_label),
                interval=str(interval),
                combos=[combo_label],
                output_dir_display=out_disp,
                run_display=run_display,
                n_symbols_attempted=int(summary["n_symbols_attempted"]),
                n_symbols_processed=int(summary["n_symbols_processed"]),
                n_symbols_skipped=int(summary["n_symbols_skipped"]),
                n_open_positions_before=int(summary["n_open_positions_before"]),
                n_open_positions_after=int(summary["n_open_positions_after"]),
                n_new_signals=int(summary["n_new_signals"]),
                n_new_entries=int(summary["n_new_entries"]),
                n_new_exits=int(summary["n_new_exits"]),
                n_symbols_with_trade_on_last_bar=int(summary["n_symbols_with_trade_on_last_bar"]),
                n_symbols_with_signal_on_last_bar=int(summary["n_symbols_with_signal_on_last_bar"]),
                n_signals_rejected_as_old=int(summary["n_signals_rejected_as_old"]),
                n_alerts_sent=int(summary["n_alerts_sent"]),
                n_alerts_failed=int(summary["n_alerts_failed"]),
                n_errors=int(summary["n_errors"]),
                runtime_seconds=float(summary["runtime_seconds"]),
                signal_detection_mode_used=str(signal_detection_mode),
                n_runtime_warnings=int(summary["n_runtime_warnings"]),
                runtime_warnings_sample=list(summary["runtime_warnings_sample"] or []),
                lock_acquired=bool(lock_acquired),
                lock_behavior=str(lock_behavior),
            )
    
            logger.info("summary alert candidate key=%s", sum_dedup_key)
    
            if telegram_enabled and not telegram_dry_run and telegram_credentials_available():
                if state.alert_already_sent(sum_dedup_key):
                    summary_alert_status = "skipped_due_to_dedup"
                    logger.info("summary alert skipped_due_to_dedup key=%s", sum_dedup_key)
                else:
                    ok_sm = send_message(sm_text, parse_mode=None)
                    if ok_sm:
                        summary_alert_status = "sent"
                        state.mark_alert_sent(sum_dedup_key)
                        summary["n_alerts_sent"] = int(summary["n_alerts_sent"]) + 1
                        logger.info("summary alert sent key=%s", sum_dedup_key)
                    else:
                        summary_alert_status = "failed"
                        summary_alert_fail_reason = "telegram_send_failed"
                        summary["n_alerts_failed"] = int(summary["n_alerts_failed"]) + 1
                        logger.warning("summary alert failed key=%s", sum_dedup_key)
            elif telegram_dry_run:
                summary_alert_status = "skipped_telegram_dry_run"
                logger.info(
                    "[telegram_dry_run] run summary: entries=%s exits=%s alerts=%s/%s",
                    summary["n_new_entries"],
                    summary["n_new_exits"],
                    summary["n_alerts_sent"],
                    summary["n_alerts_failed"],
                )
            else:
                summary_alert_status = "skipped_telegram_disabled"
                logger.info("summary alert skipped (telegram disabled or no credentials)")

            summary["summary_alert_status"] = summary_alert_status
            summary["summary_alert_fail_reason"] = summary_alert_fail_reason
            _write_execution_decision_summary(
                state=state,
                summary=summary,
                execution_events=execution_events,
            )

            try:
                state.save()
            except Exception as exc:  # noqa: BLE001
                logger.exception("state.save failed")
                state_write_errors.append(f"state.save:{type(exc).__name__}: {exc}")
            try:
                export_paper_trade_details(state)
            except Exception as exc:  # noqa: BLE001
                logger.exception("export_paper_trade_details failed")
                state_write_errors.append(f"export_paper_trade_details:{type(exc).__name__}: {exc}")
            from services.live_paper_state import append_csv_row, write_live_summary
            event_counts = _execution_event_counts(execution_events)
            _merge_execution_block_diagnostics(summary, execution_events)
            _merge_execution_exit_diagnostics(summary, execution_events, state)
            summary["state_write_ok"] = len(state_write_errors) == 0
            summary["state_write_errors_sample"] = state_write_errors[:20]
            summary["atomic_write_stats"] = get_atomic_write_stats()
            summary["fallback_writes_count"] = int(summary["atomic_write_stats"].get("fallback_direct_overwrite", 0))
            summary["run_status"] = (
                "success"
                if len(state_write_errors) == 0
                and int(summary.get("n_errors") or 0) == 0
                and not bool(summary.get("execution_degraded", False))
                else "partial_success"
            )
            _write_execution_decision_summary(
                state=state,
                summary=summary,
                execution_events=execution_events,
            )
    
            hist_row = {
                "timestamp": summary["run_timestamp"],
                "run_timestamp": summary["run_timestamp"],
                "run_status": summary["run_status"],
                "execution_adapter_ok": bool(summary.get("execution_adapter_health_ok", True)),
                "orders_attempted": event_counts["attempts"],
                "orders_success": event_counts["success"],
                "orders_failed": event_counts["failed"],
                "signals_generated": summary["n_new_signals"],
                "open_positions_count": summary["n_open_positions_after"],
                "duration_sec": summary["runtime_seconds"],
                "error_summary": "; ".join(state_write_errors[:3]) or str(summary.get("execution_reconciliation_error", "")),
                "mode": summary["mode"],
                "interval": summary["interval"],
                "combos": combo_label,
                "n_symbols_attempted": summary["n_symbols_attempted"],
                "n_symbols_processed": summary["n_symbols_processed"],
                "n_symbols_skipped": summary["n_symbols_skipped"],
                "n_open_positions_before": summary["n_open_positions_before"],
                "n_open_positions_after": summary["n_open_positions_after"],
                "n_new_signals": summary["n_new_signals"],
                "n_new_entries": summary["n_new_entries"],
                "n_new_exits": summary["n_new_exits"],
                "n_alerts_sent": summary["n_alerts_sent"],
                "n_alerts_failed": summary["n_alerts_failed"],
                "n_errors": summary["n_errors"],
                "errors_sample": str(summary.get("errors_sample")),
                "runtime_seconds": summary["runtime_seconds"],
            }
            append_csv_row(
                state.paths()["live_run_history_csv"],
                hist_row,
                LIVE_RUN_HISTORY_FIELDS,
            )
            write_live_summary(state.paths()["live_summary_latest"], summary)
    
            report_row = {k: summary.get(k, "") for k in LIVE_REPORT_CSV_FIELDS}
            report_row["combos"] = combo_label
            append_live_report_csv(state.paths()["live_report_csv"], report_row)
            txt = summary_to_pretty_text(
                title="LIVE PAPER REPORT",
                run_display=run_display,
                output_dir=out_disp,
                summary=summary,
            )
            write_live_report_latest_txt(state.paths()["live_report_latest_txt"], txt)
            write_open_positions_report_csv(state.paths()["open_positions_report_csv"], state.open_positions)
        else:
            _merge_execution_block_diagnostics(summary, execution_events)
            _merge_execution_exit_diagnostics(summary, execution_events, state)
            _write_execution_decision_summary(
                state=state,
                summary=summary,
                execution_events=execution_events,
            )

        return summary
    finally:
        if run_lock is not None and run_lock.held:
            run_lock.release()
