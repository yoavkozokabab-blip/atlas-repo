"""
Dual-engine live paper cycle: daily (v5_daily) + weekly (v2b_weekly) with combined risk cap.

Lazy-imports ``live_paper_engine`` inside ``run_dual_engine_monitor_cycle`` to avoid import cycles.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

from algo_scanner.config import AppConfig
from run_train_test_validation import fetch_ohlcv_range_with_meta, min_bars_required
from services.live_paper_state import LivePaperState, atomic_write_text, output_scope_key, summary_alert_dedup_key
from services.live_production_constants import (
    COMBINED_MAX_TOTAL_RISK,
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
    dual_artifact_paths,
    ensure_dual_engine_directory_layout,
    engine_open_risk_fraction,
    expected_dual_engine_output_dir,
    assert_daily_algo_config,
    assert_weekly_algo_config,
    build_daily_algo_config,
    build_weekly_algo_config,
    make_dual_allocate_fn,
    print_production_dual_banner,
    total_combined_risk_fraction,
)
from services.paper_trading_constants import (
    load_safety_state,
    maybe_warn_signal_anomalies_dual,
    save_safety_state,
)
from services.portfolio_manager import (
    PortfolioConstraints,
    load_portfolio_state,
    save_portfolio_state,
    write_paper_positions_snapshot,
)
from services.paper_trading_log import paper_live_log_line
from services.live_run_debug_stats import LiveRunDebugStats
from tools.trading_dashboard.backend.control_service import CONTROL_STATE_PATH
from validation_cli_common import require_universe_file

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


def _write_engine_split_json(
    *,
    artifact_paths: dict[str, Path],
    state: LivePaperState,
    capital: float,
    marks: dict[str, float],
) -> None:
    def _u_for(p: dict[str, Any]) -> float:
        sym = str(p.get("symbol", "")).strip().upper()
        ep = float(p.get("paper_entry_open") or p.get("entry_price") or 0.0)
        m = float(marks.get(sym, ep) or ep)
        sh = float(p.get("paper_shares") or 0.0)
        return (m - ep) * sh if sh else 0.0

    dr = engine_open_risk_fraction(state.open_positions, capital=capital, engine="daily")
    wr = engine_open_risk_fraction(state.open_positions, capital=capital, engine="weekly")
    cr = total_combined_risk_fraction(state.open_positions, capital=capital)
    syms = sorted({str(p.get("symbol", "")).strip().upper() for p in state.open_positions if p.get("symbol")})
    enriched: list[dict[str, Any]] = []
    for p in state.open_positions:
        sym = str(p.get("symbol", "")).strip().upper()
        ep = float(p.get("paper_entry_open") or p.get("entry_price") or 0.0)
        m = float(marks.get(sym, ep) or ep)
        row = dict(p)
        row["mark_price"] = m
        row["unrealized_pnl"] = _u_for(p)
        enriched.append(row)
    daily_rows = [x for x in enriched if str(x.get("engine_label", "daily")).lower() == "daily"]
    weekly_rows = [x for x in enriched if str(x.get("engine_label", "daily")).lower() == "weekly"]
    du = sum(float(x.get("unrealized_pnl") or 0.0) for x in daily_rows)
    wu = sum(float(x.get("unrealized_pnl") or 0.0) for x in weekly_rows)
    doc = {
        "positions": enriched,
        "daily_risk_fraction": dr,
        "weekly_risk_fraction": wr,
        "combined_risk_fraction": cr,
        "daily_unrealized_pnl_dollars": du,
        "weekly_unrealized_pnl_dollars": wu,
        "combined_unrealized_pnl_dollars": du + wu,
        "open_symbols": syms,
        "daily_max_total_risk_cap": DAILY_MAX_TOTAL_RISK,
        "weekly_max_total_risk_cap": WEEKLY_MAX_TOTAL_RISK,
        "combined_max_total_risk_cap": COMBINED_MAX_TOTAL_RISK,
    }
    for path, rows in (
        (artifact_paths["paper_positions_daily_json"], daily_rows),
        (artifact_paths["paper_positions_weekly_json"], weekly_rows),
        (artifact_paths["paper_positions_combined_json"], doc),
    ):
        payload = ""
        if isinstance(rows, dict):
            payload = json.dumps(rows, indent=2, default=str) + "\n"
        else:
            payload = json.dumps({"positions": rows}, indent=2, default=str) + "\n"
        atomic_write_text(path, payload, encoding="utf-8")


def run_dual_engine_monitor_cycle(
    *,
    universe_file: Path,
    output_dir: Path,
    warmup_years: int,
    benchmark: str,
    yahoo_throttle: float,
    dry_run: bool,
    telegram_dry_run: bool,
    telegram_enabled: bool,
    as_of: pd.Timestamp | None,
    send_message: Any,
    build_entry: Any,
    build_exit: Any,
    mode_label: str,
    signal_detection_mode: str,
    yahoo_fetch_max_retries: int,
    runtime_warn_seconds: float | None,
    state: LivePaperState,
    run_ts: str,
    cycle_started_perf: float,
    lock_acquired: bool,
    lock_behavior: str,
    lock_wait_seconds: float,
    n_open_before: int,
    run_debug: LiveRunDebugStats | None = None,
    allow_universe_override: bool = False,
    universe_explicit_cli: bool = False,
    signal_flow: Any = None,
    trade_funnel: Any = None,
    ohlcv_cache_dir: Path | None = None,
    refresh_cache: bool = False,
    cache_only: bool = False,
    preload_ohlcv: bool = False,
    preload_workers: int | None = None,
    live_mode_relaxed: bool = False,
    live_signals_input_daily: list[Any] | None = None,
    live_signals_input_weekly: list[Any] | None = None,
    execution_mode: str = "paper",
    execution_adapter: Any | None = None,
    execution_adapter_health_ok: bool = True,
    execution_adapter_health: dict[str, Any] | None = None,
    execution_events: list[dict[str, Any]] | None = None,
    execution_skip_counts: dict[str, int] | None = None,
    execution_order_counter: dict[str, int] | None = None,
    execution_max_orders_per_run: int | None = None,
    execution_allowed_symbols_set: set[str] | None = None,
    execution_risk_config: Any | None = None,
    execution_account_equity: float | None = None,
    execution_adapter_positions: list[dict[str, Any]] | None = None,
    execution_market_is_open: bool | None = None,
    execution_control_state: dict[str, Any] | None = None,
    execution_control_day: str | None = None,
    execution_daily_order_counter: dict[str, int] | None = None,
    verbose_execution_events: bool = False,
    exits_only: bool = False,
) -> dict[str, Any]:
    import services.live_paper_engine as lpe

    from services.live_signal_engine import _apply_live_mode_relaxed_cfg

    t0 = pd.Timestamp.now(tz="UTC")
    output_dir = Path(output_dir).resolve()
    execution_events = execution_events if execution_events is not None else []
    execution_skip_counts = execution_skip_counts if execution_skip_counts is not None else {
        "not_relevant_to_last_bar": 0,
        "duplicate_symbol_open": 0,
        "other": 0,
    }
    execution_order_counter = execution_order_counter if execution_order_counter is not None else {"placed": 0}
    execution_daily_order_counter = (
        execution_daily_order_counter if execution_daily_order_counter is not None else {"placed_today": 0}
    )
    execution_mode_l = str(execution_mode or "paper").strip().lower()
    default_dual_root = expected_dual_engine_output_dir()
    if output_dir != default_dual_root:
        logger.info(
            "[dual_cycle] using explicit output_dir override=%s (default=%s)",
            output_dir,
            default_dual_root,
        )
    ensure_dual_engine_directory_layout(output_dir)
    artifact_paths = dual_artifact_paths(dual_root=output_dir)

    from services.paper_trading_log import DualPaperLiveEventLogContext

    with DualPaperLiveEventLogContext(artifact_paths["paper_live_log_combined_txt"]):
        output_scope = output_scope_key(output_dir)
        uni_path = lpe.validate_universe_for_live_paper(
            universe_file,
            allow_universe_override=bool(allow_universe_override),
            universe_explicit_cli=bool(universe_explicit_cli),
        )
        symbols = require_universe_file(uni_path)
        symbols, open_only_symbols = lpe._merge_open_position_symbols(symbols, state.open_positions)
        uni_source = str(uni_path.resolve())
        _raw_syms = list(symbols)
        _scan_seed = scan_order_seed_for_run(run_ts, uni_source)
        _shuffle_on = os.environ.get("LIVE_ENTRY_SHUFFLE_SCAN_ORDER", "1").strip().lower() not in (
            "0",
            "false",
            "no",
        )
        if _shuffle_on:
            symbols = deterministic_daily_shuffle(_raw_syms, seed=_scan_seed)
        log_universe_order_loaded(
            universe_path=uni_source,
            raw_count=len(_raw_syms),
            scan_order=list(symbols),
            seed=_scan_seed,
            shuffle_applied=bool(_shuffle_on),
        )

        if run_debug is None:
            run_debug = LiveRunDebugStats()
        run_debug.set_total_symbols_seen(len(symbols))
        if trade_funnel is not None:
            trade_funnel.set_totals_seen(len(symbols))

        cfg_d = build_daily_algo_config()
        assert_daily_algo_config(cfg_d)
        cfg_w = build_weekly_algo_config()
        assert_weekly_algo_config(cfg_w)
        if live_mode_relaxed:
            logger.info("[PAPER USING LIVE RELAX MODE]")
            print("[PAPER USING LIVE RELAX MODE]", flush=True)
            cfg_d = _apply_live_mode_relaxed_cfg(cfg_d)
            cfg_w = _apply_live_mode_relaxed_cfg(cfg_w)
        print_production_dual_banner(universe_path=uni_path, universe_size=len(symbols), logger=logger)
        logger.info("UNIVERSE SIZE: %s", len(symbols))
        print(f"UNIVERSE SIZE: {len(symbols)}", flush=True)

        app_d = AppConfig(project_root=ROOT)
        app_d.timeframe = DAILY_INTERVAL
        app_d.yahoo_interval = DAILY_INTERVAL
        app_w = AppConfig(project_root=ROOT)
        app_w.timeframe = WEEKLY_INTERVAL
        app_w.yahoo_interval = WEEKLY_INTERVAL
        ext_daily_by_symbol: dict[str, list[Any]] = {}
        ext_weekly_by_symbol: dict[str, list[Any]] = {}
        if live_signals_input_daily:
            for c in live_signals_input_daily:
                sym_u = str(getattr(c, "symbol", "")).strip().upper()
                if sym_u:
                    ext_daily_by_symbol.setdefault(sym_u, []).append(c)
        if live_signals_input_weekly:
            for c in live_signals_input_weekly:
                sym_u = str(getattr(c, "symbol", "")).strip().upper()
                if sym_u:
                    ext_weekly_by_symbol.setdefault(sym_u, []).append(c)

        end_test = pd.Timestamp.now(tz="UTC").normalize()
        fetch_start = end_test - pd.DateOffset(years=int(warmup_years))
        errors: list[dict[str, str]] = []
        n_attempted = len(symbols)
        n_processed = 0
        n_skipped = 0
        n_new_signals_daily = 0
        n_new_signals_weekly = 0
        n_new_entries = 0
        n_exits = 0
        n_alerts_sent = 0
        n_alerts_failed = 0
        n_symbols_with_trade_on_last_bar = 0
        n_symbols_with_signal_on_last_bar = 0
        n_signals_rejected_as_old = 0
        runtime_warnings: list[str] = []
        state_write_errors: list[str] = []
        recent_entries: list[dict[str, Any]] = []
        portfolio_skips: dict[str, int] = defaultdict(int)
        portfolio_state = load_portfolio_state(artifact_paths["paper_portfolio_state_json"])
        cap = float(os.environ.get("PAPER_CAPITAL", "100000") or 100_000.0)
        allocate_w = make_dual_allocate_fn(capital=cap, engine="weekly")
        allocate_d = make_dual_allocate_fn(capital=cap, engine="daily")
        pre_cr = total_combined_risk_fraction(state.open_positions, capital=cap)
        combined_hard_block = pre_cr > float(COMBINED_MAX_TOTAL_RISK) + 1e-9
        if combined_hard_block:
            wmsg = (
                f"[PAPER SAFETY] combined_risk_fraction={pre_cr:.4f} > cap {COMBINED_MAX_TOTAL_RISK}; "
                "blocking all new entries this cycle."
            )
            logger.warning("%s", wmsg)
            print(wmsg, flush=True)
            runtime_warnings.append(wmsg)

            def _noop_alloc(
                _sym: str, _opens: list[dict[str, Any]], _pe: float, _st: float
            ) -> tuple[bool, str]:
                return False, "combined_hard_cap_block"

            allocate_w = _noop_alloc  # type: ignore[assignment]
            allocate_d = _noop_alloc  # type: ignore[assignment]
        cst_weekly = PortfolioConstraints(
            capital=cap,
            risk_per_trade=float(WEEKLY_RISK_PER_TRADE),
            max_open_positions=int(WEEKLY_MAX_OPEN_POSITIONS),
            max_total_risk=float(WEEKLY_MAX_TOTAL_RISK),
            reentry_min_bars=5,
        )
        cst_daily = PortfolioConstraints(
            capital=cap,
            risk_per_trade=float(DAILY_RISK_PER_TRADE),
            max_open_positions=int(DAILY_MAX_OPEN_POSITIONS),
            max_total_risk=float(DAILY_MAX_TOTAL_RISK),
            reentry_min_bars=5,
        )
        marks: dict[str, float] = {}
        safety_state = load_safety_state(artifact_paths["paper_safety_state_json"])

        need_d = min_bars_required(cfg_d)
        need_w = min_bars_required(cfg_w)

        _fk: dict[str, Any] = {
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
            preload_ohlcv_jobs,
        )

        use_preload = bool(preload_ohlcv) or env_preload_enabled()
        ohlcv_store = None
        if use_preload:
            bd_sym = str(cfg_d.benchmark_sym or benchmark)
            bw_sym = str(cfg_w.benchmark_sym or benchmark)
            jobs: list[tuple[str, str]] = []
            for sym in symbols:
                jobs.append((DAILY_INTERVAL, sym))
                jobs.append((WEEKLY_INTERVAL, sym))
            jobs.append((DAILY_INTERVAL, bd_sym))
            jobs.append((WEEKLY_INTERVAL, bw_sym))
            seen_j: set[tuple[str, str]] = set()
            deduped: list[tuple[str, str]] = []
            for iv, sy in jobs:
                sk = (str(iv).strip(), str(sy).strip().upper())
                if sk in seen_j:
                    continue
                seen_j.add(sk)
                deduped.append((str(iv).strip(), str(sy).strip()))
            w_pre = int(preload_workers) if preload_workers is not None else default_preload_workers()
            ohlcv_store, pst = preload_ohlcv_jobs(
                jobs=deduped,
                start=fetch_start,
                end=end_test,
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
            bench_d, _ = get_raw_meta_from_store(ohlcv_store, str(cfg_d.benchmark_sym or benchmark), DAILY_INTERVAL)
            bench_w, _ = get_raw_meta_from_store(ohlcv_store, str(cfg_w.benchmark_sym or benchmark), WEEKLY_INTERVAL)
        else:
            bench_d, _ = fetch_ohlcv_range_with_meta(
                str(cfg_d.benchmark_sym or benchmark),
                DAILY_INTERVAL,
                fetch_start,
                end_test,
                **_fk,
            )
            bench_w, _ = fetch_ohlcv_range_with_meta(
                str(cfg_w.benchmark_sym or benchmark),
                WEEKLY_INTERVAL,
                fetch_start,
                end_test,
                **_fk,
            )
        if bench_d.empty:
            errors.append({"symbol": "__bench__", "error": "empty benchmark daily"})
        if bench_w.empty:
            errors.append({"symbol": "__bench__", "error": "empty benchmark weekly"})

        packs: dict[str, dict[str, Any]] = {}
        from services.live_last_bar_diagnostic import last_bar_diagnostic_enabled, make_post_sim_near_last_bar_tap

        _lb_post_sim_rows: list[dict[str, Any]] = []
        _lb_tap = None
        if last_bar_diagnostic_enabled():
            _lb_tap, _lb_post_sim_rows = make_post_sim_near_last_bar_tap()

        stopped_symbols_this_cycle: set[str] = set()
        xe_pre, ae_pre, af_pre = lpe.process_broker_mark_exits_for_open_positions(
            state=state,
            combo_labels=[WEEKLY_PRESET_NAME, DAILY_PRESET_NAME],
            interval_by_combo={WEEKLY_PRESET_NAME: WEEKLY_INTERVAL, DAILY_PRESET_NAME: DAILY_INTERVAL},
            run_timestamp=run_ts,
            dry_run=dry_run,
            telegram_dry_run=telegram_dry_run,
            send_message=send_message,
            build_exit=build_exit,
            output_scope=output_scope,
            portfolio_state=portfolio_state,
            execution_adapter=execution_adapter,
            execution_adapter_health_ok=bool(execution_adapter_health_ok),
            execution_adapter_positions=execution_adapter_positions,
            execution_events=execution_events,
            verbose_execution_events=verbose_execution_events,
            execution_market_is_open=execution_market_is_open,
        )
        n_exits += xe_pre
        n_alerts_sent += ae_pre
        n_alerts_failed += af_pre
        stopped_symbols_this_cycle.update(
            str(row.get("symbol", "")).strip().upper()
            for row in execution_events
            if isinstance(row, dict)
            and row.get("event_type") == "close_position"
            and str(row.get("reason") or "") in ("stop_loss_breached", "take_profit_hit")
        )
        for sym in symbols:
            try:
                if use_preload and ohlcv_store is not None:
                    raw_d, _md = get_raw_meta_from_store(ohlcv_store, sym, DAILY_INTERVAL)
                    raw_w, _mw = get_raw_meta_from_store(ohlcv_store, sym, WEEKLY_INTERVAL)
                else:
                    raw_d, _md = fetch_ohlcv_range_with_meta(sym, DAILY_INTERVAL, fetch_start, end_test, **_fk)
                    raw_w, _mw = fetch_ohlcv_range_with_meta(sym, WEEKLY_INTERVAL, fetch_start, end_test, **_fk)
                if raw_d is None or raw_d.empty or raw_w is None or raw_w.empty:
                    n_skipped += 1
                    run_debug.record_skip(sym, "dual", "no_ohlcv_pair")
                    if trade_funnel is not None:
                        trade_funnel.record_symbol_skip(sym, "no_ohlcv_pair")
                    continue
                stop_d = raw_d.rename(columns=str.lower)
                stop_w = raw_w.rename(columns=str.lower)
                if state.has_open_for_symbol(sym):
                    for combo_stop, iv_stop, stop_df in (
                        (WEEKLY_PRESET_NAME, WEEKLY_INTERVAL, stop_w),
                        (DAILY_PRESET_NAME, DAILY_INTERVAL, stop_d),
                    ):
                        xe_stop, ae_stop, af_stop = lpe.process_exits_for_symbol(
                            sym=sym,
                            combo_label=combo_stop,
                            interval=iv_stop,
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
                            stop_check_df=stop_df,
                            stop_loss_only=True,
                            engine_cfg=cfg_w if iv_stop == WEEKLY_INTERVAL else cfg_d,
                            execution_market_is_open=execution_market_is_open,
                        )
                        n_exits += xe_stop
                        n_alerts_sent += ae_stop
                        n_alerts_failed += af_stop
                        if xe_stop > 0:
                            stopped_symbols_this_cycle.add(sym.strip().upper())
                d_d, lb_d = lpe.clip_to_fully_closed_bars(stop_d, DAILY_INTERVAL, as_of=as_of)
                d_w, lb_w = lpe.clip_to_fully_closed_bars(stop_w, WEEKLY_INTERVAL, as_of=as_of)
                if not lb_d or not lb_w or d_d is None or len(d_d) < need_d or d_w is None or len(d_w) < need_w:
                    n_skipped += 1
                    run_debug.record_skip(sym, "dual", "insufficient_closed_bars")
                    if trade_funnel is not None:
                        trade_funnel.record_symbol_skip(sym, "insufficient_closed_bars")
                    continue
                first_ts = pd.Timestamp(d_d.index[0]).normalize()
                if first_ts > fetch_start.normalize():
                    n_skipped += 1
                    run_debug.record_skip(sym, "dual", "history_start_after_fetch_window")
                    if trade_funnel is not None:
                        trade_funnel.record_symbol_skip(sym, "history_start_after_fetch_window")
                    continue
                if trade_funnel is not None:
                    trade_funnel.record_symbol_loaded(sym)
                need_daily_scan = state.has_open_for_symbol(sym) or not (ext_daily_by_symbol.get(sym.strip().upper()) or [])
                need_weekly_scan = state.has_open_for_symbol(sym) or not (ext_weekly_by_symbol.get(sym.strip().upper()) or [])
                trades_d = (
                    lpe.run_symbol_trades(
                        sym,
                        d_d,
                        bench_d,
                        cfg_d,
                        app_d,
                        uni_source,
                        signal_debug=signal_flow,
                        trade_funnel=trade_funnel,
                        engine="daily",
                        post_sim_near_last_bar_tap=_lb_tap,
                    )
                    if need_daily_scan
                    else []
                )
                trades_w = (
                    lpe.run_symbol_trades(
                        sym,
                        d_w,
                        bench_w,
                        cfg_w,
                        app_w,
                        uni_source,
                        signal_debug=signal_flow,
                        trade_funnel=trade_funnel,
                        engine="weekly",
                        post_sim_near_last_bar_tap=_lb_tap,
                    )
                    if need_weekly_scan
                    else []
                )
                for t in trades_d:
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
                for t in trades_w:
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
                try:
                    marks[sym.strip().upper()] = float(d_d["close"].iloc[-1])
                except Exception:
                    marks[sym.strip().upper()] = float(trades_d[-1].get("entry", 0.0) or 0.0) if trades_d else 0.0
                packs[sym] = {
                    "d_d": d_d,
                    "lb_d": lb_d,
                    "stop_d": stop_d,
                    "d_w": d_w,
                    "lb_w": lb_w,
                    "stop_w": stop_w,
                    "trades_d": trades_d,
                    "trades_w": trades_w,
                }
            except Exception as e:  # noqa: BLE001
                logger.exception("symbol failed dual (fetch/engine): %s", sym)
                errors.append({"symbol": sym, "error": f"{type(e).__name__}: {e}"})
                n_skipped += 1
                run_debug.record_skip(sym, "dual", f"exception:{type(e).__name__}")
                if trade_funnel is not None:
                    trade_funnel.record_symbol_skip(sym, f"exception:{type(e).__name__}")

        n_processed = len(packs)

        for sym, pk in packs.items():
            d_d, lb_d, d_w, lb_w = pk["d_d"], pk["lb_d"], pk["d_w"], pk["lb_w"]
            trades_d, trades_w = pk["trades_d"], pk["trades_w"]
            for combo, iv, d_, tr, lb in (
                (WEEKLY_PRESET_NAME, WEEKLY_INTERVAL, d_w, trades_w, lb_w),
                (DAILY_PRESET_NAME, DAILY_INTERVAL, d_d, trades_d, lb_d),
            ):
                stop_df = pk["stop_w"] if iv == WEEKLY_INTERVAL else pk["stop_d"]
                xe, ae, af = lpe.process_exits_for_symbol(
                    sym=sym,
                    combo_label=combo,
                    interval=iv,
                    trades=tr,
                    state=state,
                    run_timestamp=run_ts,
                    dry_run=dry_run,
                    telegram_dry_run=telegram_dry_run,
                    send_message=send_message,
                    build_exit=build_exit,
                    output_scope=output_scope,
                    df=d_,
                    portfolio_state=portfolio_state,
                    execution_adapter=execution_adapter,
                    execution_adapter_positions=execution_adapter_positions,
                    execution_events=execution_events,
                    verbose_execution_events=verbose_execution_events,
                    stop_check_df=stop_df,
                    engine_cfg=cfg_w if iv == WEEKLY_INTERVAL else cfg_d,
                    execution_market_is_open=execution_market_is_open,
                )
                n_exits += xe
                n_alerts_sent += ae
                n_alerts_failed += af

        if exits_only:
            open_only_symbols.update(str(sym).strip().upper() for sym in packs)
            logger.warning("[dual_cycle] exits_only=true; skipping all new entry processing")

        defer_dual = (
            not bool(exits_only)
            and os.environ.get("LIVE_DEFER_ENTRY_PLACEMENT", "1").strip().lower()
            not in (
                "0",
                "false",
                "no",
            )
        )

        def _dual_weekly_sym_pass(
            sym: str,
            pk: dict[str, Any],
            *,
            entry_intent_bucket: list[dict[str, Any]] | None,
        ) -> None:
            nonlocal n_new_signals_weekly, n_new_entries, n_alerts_sent, n_alerts_failed, n_exits
            nonlocal n_symbols_with_trade_on_last_bar, n_symbols_with_signal_on_last_bar, n_signals_rejected_as_old
            sy_u = sym.strip().upper()
            if sy_u in open_only_symbols or sy_u in stopped_symbols_this_cycle:
                return
            run_debug.record_processed(sym, "weekly")
            d_w, lb_w, trades_w = pk["d_w"], pk["lb_w"], pk["trades_w"]
            ext_w = ext_weekly_by_symbol.get(sy_u) or []
            entry_trades_w = (
                [lpe._trade_from_live_candidate(c, sym=sym, df=d_w) for c in ext_w]
                if ext_w
                else trades_w
            )
            el, _eq, sigl = lpe._last_bar_debug_flags(trades_w, d_w, lb_w, live_mode_relaxed=live_mode_relaxed)
            if el:
                n_symbols_with_trade_on_last_bar += 1
            if sigl:
                n_symbols_with_signal_on_last_bar += 1
            n_signals_rejected_as_old += lpe.count_signals_rejected_as_old(
                sym,
                WEEKLY_PRESET_NAME,
                WEEKLY_INTERVAL,
                d_w,
                entry_trades_w,
                lb_w,
                state,
                live_mode_relaxed=live_mode_relaxed,
            )
            ns, ne, ae2, af2 = lpe.process_new_entries_for_symbol(
                sym=sym,
                combo_label=WEEKLY_PRESET_NAME,
                interval=WEEKLY_INTERVAL,
                df=d_w,
                trades=entry_trades_w,
                last_bar_date=lb_w,
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
                constraints=cst_weekly,
                portfolio_skips=portfolio_skips,
                allocation_fn=allocate_w,
                use_floor_sizing=True,
                engine_label="weekly",
                ranking_preset_name=WEEKLY_PRESET_NAME,
                trade_funnel=trade_funnel,
                live_mode_relaxed=live_mode_relaxed,
                recent_entries_collector=recent_entries,
                execution_adapter=execution_adapter,
                execution_adapter_health_ok=bool(execution_adapter_health_ok),
                execution_events=execution_events,
                execution_skip_counts=execution_skip_counts,
                execution_order_counter=execution_order_counter,
                execution_max_orders_per_run=execution_max_orders_per_run,
                execution_allowed_symbols=execution_allowed_symbols_set,
                execution_risk_config=execution_risk_config,
                execution_account_equity=execution_account_equity,
                execution_adapter_positions=execution_adapter_positions,
                execution_market_is_open=execution_market_is_open,
                execution_control_state=execution_control_state,
                execution_control_day=execution_control_day,
                execution_daily_order_counter=execution_daily_order_counter,
                verbose_execution_events=verbose_execution_events,
                entry_intent_bucket=entry_intent_bucket,
                candidate_log_prefix="dual" if entry_intent_bucket is not None else None,
            )
            n_new_signals_weekly += ns
            n_new_entries += ne
            n_alerts_sent += ae2
            n_alerts_failed += af2
            if entry_intent_bucket is None:
                xe2, ae3, af3 = lpe.process_exits_for_symbol(
                    sym=sym,
                    combo_label=WEEKLY_PRESET_NAME,
                    interval=WEEKLY_INTERVAL,
                    trades=trades_w,
                    state=state,
                    run_timestamp=run_ts,
                    dry_run=dry_run,
                    telegram_dry_run=telegram_dry_run,
                    send_message=send_message,
                    build_exit=build_exit,
                    output_scope=output_scope,
                    df=d_w,
                    portfolio_state=portfolio_state,
                    execution_adapter=execution_adapter,
                    execution_adapter_positions=execution_adapter_positions,
                    execution_events=execution_events,
                    verbose_execution_events=verbose_execution_events,
                    stop_check_df=pk["stop_w"],
                    engine_cfg=cfg_w,
                    execution_market_is_open=execution_market_is_open,
                )
                n_exits += xe2
                n_alerts_sent += ae3
                n_alerts_failed += af3

        def _dual_daily_sym_pass(
            sym: str,
            pk: dict[str, Any],
            *,
            entry_intent_bucket: list[dict[str, Any]] | None,
        ) -> None:
            nonlocal n_new_signals_daily, n_new_entries, n_alerts_sent, n_alerts_failed, n_exits
            nonlocal n_symbols_with_trade_on_last_bar, n_symbols_with_signal_on_last_bar, n_signals_rejected_as_old
            sy_u = sym.strip().upper()
            if sy_u in open_only_symbols or sy_u in stopped_symbols_this_cycle:
                return
            run_debug.record_processed(sym, "daily")
            d_d, lb_d, trades_d = pk["d_d"], pk["lb_d"], pk["trades_d"]
            ext_d = ext_daily_by_symbol.get(sy_u) or []
            entry_trades_d = (
                [lpe._trade_from_live_candidate(c, sym=sym, df=d_d) for c in ext_d]
                if ext_d
                else trades_d
            )
            el, _eq, sigl = lpe._last_bar_debug_flags(trades_d, d_d, lb_d, live_mode_relaxed=live_mode_relaxed)
            if el:
                n_symbols_with_trade_on_last_bar += 1
            if sigl:
                n_symbols_with_signal_on_last_bar += 1
            n_signals_rejected_as_old += lpe.count_signals_rejected_as_old(
                sym,
                DAILY_PRESET_NAME,
                DAILY_INTERVAL,
                d_d,
                entry_trades_d,
                lb_d,
                state,
                live_mode_relaxed=live_mode_relaxed,
            )
            ns, ne, ae2, af2 = lpe.process_new_entries_for_symbol(
                sym=sym,
                combo_label=DAILY_PRESET_NAME,
                interval=DAILY_INTERVAL,
                df=d_d,
                trades=entry_trades_d,
                last_bar_date=lb_d,
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
                constraints=cst_daily,
                portfolio_skips=portfolio_skips,
                allocation_fn=allocate_d,
                use_floor_sizing=True,
                engine_label="daily",
                ranking_preset_name=DAILY_PRESET_NAME,
                trade_funnel=trade_funnel,
                live_mode_relaxed=live_mode_relaxed,
                recent_entries_collector=recent_entries,
                execution_adapter=execution_adapter,
                execution_adapter_health_ok=bool(execution_adapter_health_ok),
                execution_events=execution_events,
                execution_skip_counts=execution_skip_counts,
                execution_order_counter=execution_order_counter,
                execution_max_orders_per_run=execution_max_orders_per_run,
                execution_allowed_symbols=execution_allowed_symbols_set,
                execution_risk_config=execution_risk_config,
                execution_account_equity=execution_account_equity,
                execution_adapter_positions=execution_adapter_positions,
                execution_market_is_open=execution_market_is_open,
                execution_control_state=execution_control_state,
                execution_control_day=execution_control_day,
                execution_daily_order_counter=execution_daily_order_counter,
                verbose_execution_events=verbose_execution_events,
                entry_intent_bucket=entry_intent_bucket,
                candidate_log_prefix="dual" if entry_intent_bucket is not None else None,
            )
            n_new_signals_daily += ns
            n_new_entries += ne
            n_alerts_sent += ae2
            n_alerts_failed += af2
            if entry_intent_bucket is None:
                xe2, ae3, af3 = lpe.process_exits_for_symbol(
                    sym=sym,
                    combo_label=DAILY_PRESET_NAME,
                    interval=DAILY_INTERVAL,
                    trades=trades_d,
                    state=state,
                    run_timestamp=run_ts,
                    dry_run=dry_run,
                    telegram_dry_run=telegram_dry_run,
                    send_message=send_message,
                    build_exit=build_exit,
                    output_scope=output_scope,
                    df=d_d,
                    portfolio_state=portfolio_state,
                    execution_adapter=execution_adapter,
                    execution_adapter_positions=execution_adapter_positions,
                    execution_events=execution_events,
                    verbose_execution_events=verbose_execution_events,
                    stop_check_df=pk["stop_d"],
                    engine_cfg=cfg_d,
                    execution_market_is_open=execution_market_is_open,
                )
                n_exits += xe2
                n_alerts_sent += ae3
                n_alerts_failed += af3

        if defer_dual:
            weekly_intent_buffer: list[dict[str, Any]] = []
            weekly_symbol_ctx: dict[str, dict[str, Any]] = {}
            n_weekly_syms_scanned = 0
            for sym, pk in packs.items():
                sy_u = sym.strip().upper()
                if sy_u in open_only_symbols or sy_u in stopped_symbols_this_cycle:
                    continue
                n_weekly_syms_scanned += 1
                d_w, lb_w, trades_w = pk["d_w"], pk["lb_w"], pk["trades_w"]
                weekly_symbol_ctx[sy_u] = {
                    "sym": sym,
                    "d_w": d_w,
                    "lb_w": lb_w,
                    "trades_w": trades_w,
                    "stop_w": pk["stop_w"],
                }
                _dual_weekly_sym_pass(sym, pk, entry_intent_bucket=weekly_intent_buffer)

            ranked_w = rank_entry_intents(list(weekly_intent_buffer))
            log_candidate_pipeline("candidate_ranked", log_prefix="dual", engine="weekly", n_ranked=len(ranked_w))
            placed_weekly_syms: list[str] = []
            for it in ranked_w:
                sy_u = str(it.get("symbol", "")).strip().upper()
                ctx = weekly_symbol_ctx.get(sy_u)
                if not ctx:
                    continue
                trade_for_execution = dict(it.get("trade") or {})
                trade_for_execution.setdefault("candidate_rank", it.get("candidate_rank"))
                trade_for_execution.setdefault("candidate_rank_key", it.get("candidate_rank_key"))
                trade_for_execution.setdefault("candidate_score", trade_for_execution.get("score"))
                trade_for_execution.setdefault("rank", it.get("candidate_rank"))
                log_candidate_pipeline(
                    "candidate_selected",
                    log_prefix="dual",
                    engine="weekly",
                    symbol=sy_u,
                    candidate_rank=it.get("candidate_rank"),
                )
                ns, ne, ae2, af2 = lpe.process_new_entries_for_symbol(
                    sym=ctx["sym"],
                    combo_label=WEEKLY_PRESET_NAME,
                    interval=WEEKLY_INTERVAL,
                    df=ctx["d_w"],
                    trades=[trade_for_execution],
                    last_bar_date=ctx["lb_w"],
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
                    constraints=cst_weekly,
                    portfolio_skips=portfolio_skips,
                    allocation_fn=allocate_w,
                    use_floor_sizing=True,
                    engine_label="weekly",
                    ranking_preset_name=WEEKLY_PRESET_NAME,
                    trade_funnel=trade_funnel,
                    live_mode_relaxed=live_mode_relaxed,
                    recent_entries_collector=recent_entries,
                    execution_adapter=execution_adapter,
                    execution_adapter_health_ok=bool(execution_adapter_health_ok),
                    execution_events=execution_events,
                    execution_skip_counts=execution_skip_counts,
                    execution_order_counter=execution_order_counter,
                    execution_max_orders_per_run=execution_max_orders_per_run,
                    execution_allowed_symbols=execution_allowed_symbols_set,
                    execution_risk_config=execution_risk_config,
                    execution_account_equity=execution_account_equity,
                    execution_adapter_positions=execution_adapter_positions,
                    execution_market_is_open=execution_market_is_open,
                    execution_control_state=execution_control_state,
                    execution_control_day=execution_control_day,
                    execution_daily_order_counter=execution_daily_order_counter,
                    verbose_execution_events=verbose_execution_events,
                    silent_signal_telemetry=True,
                    placement_phase="dual_ranked_after_scan_weekly",
                    candidate_log_prefix="dual",
                )
                n_new_signals_weekly += ns
                n_new_entries += ne
                n_alerts_sent += ae2
                n_alerts_failed += af2
                if ne > 0:
                    placed_weekly_syms.append(sy_u)
                xe2, ae3, af3 = lpe.process_exits_for_symbol(
                    sym=ctx["sym"],
                    combo_label=WEEKLY_PRESET_NAME,
                    interval=WEEKLY_INTERVAL,
                    trades=ctx["trades_w"],
                    state=state,
                    run_timestamp=run_ts,
                    dry_run=dry_run,
                    telegram_dry_run=telegram_dry_run,
                    send_message=send_message,
                    build_exit=build_exit,
                    output_scope=output_scope,
                    df=ctx["d_w"],
                    portfolio_state=portfolio_state,
                    execution_adapter=execution_adapter,
                    execution_adapter_positions=execution_adapter_positions,
                    execution_events=execution_events,
                    verbose_execution_events=verbose_execution_events,
                    stop_check_df=ctx["stop_w"],
                    engine_cfg=cfg_w,
                    execution_market_is_open=execution_market_is_open,
                )
                n_exits += xe2
                n_alerts_sent += ae3
                n_alerts_failed += af3

            audit_w = alphabet_bias_audit_summary(
                placed_weekly_syms,
                total_scanned=n_weekly_syms_scanned,
                total_candidates=len(ranked_w),
            )
            audit_w["engine"] = "weekly"
            audit_w["selection_after_full_universe_scan"] = True
            audit_w["scan_order_seed"] = int(_scan_seed)
            logger.info("dual_alphabet_bias_audit_summary %s", audit_w)

            daily_intent_buffer: list[dict[str, Any]] = []
            daily_symbol_ctx: dict[str, dict[str, Any]] = {}
            n_daily_syms_scanned = 0
            for sym, pk in packs.items():
                sy_u = sym.strip().upper()
                if sy_u in open_only_symbols or sy_u in stopped_symbols_this_cycle:
                    continue
                n_daily_syms_scanned += 1
                d_d, lb_d, trades_d = pk["d_d"], pk["lb_d"], pk["trades_d"]
                daily_symbol_ctx[sy_u] = {
                    "sym": sym,
                    "d_d": d_d,
                    "lb_d": lb_d,
                    "trades_d": trades_d,
                    "stop_d": pk["stop_d"],
                }
                _dual_daily_sym_pass(sym, pk, entry_intent_bucket=daily_intent_buffer)

            ranked_d = rank_entry_intents(list(daily_intent_buffer))
            log_candidate_pipeline("candidate_ranked", log_prefix="dual", engine="daily", n_ranked=len(ranked_d))
            placed_daily_syms: list[str] = []
            for it in ranked_d:
                sy_u = str(it.get("symbol", "")).strip().upper()
                ctx = daily_symbol_ctx.get(sy_u)
                if not ctx:
                    continue
                trade_for_execution = dict(it.get("trade") or {})
                trade_for_execution.setdefault("candidate_rank", it.get("candidate_rank"))
                trade_for_execution.setdefault("candidate_rank_key", it.get("candidate_rank_key"))
                trade_for_execution.setdefault("candidate_score", trade_for_execution.get("score"))
                trade_for_execution.setdefault("rank", it.get("candidate_rank"))
                log_candidate_pipeline(
                    "candidate_selected",
                    log_prefix="dual",
                    engine="daily",
                    symbol=sy_u,
                    candidate_rank=it.get("candidate_rank"),
                )
                ns, ne, ae2, af2 = lpe.process_new_entries_for_symbol(
                    sym=ctx["sym"],
                    combo_label=DAILY_PRESET_NAME,
                    interval=DAILY_INTERVAL,
                    df=ctx["d_d"],
                    trades=[trade_for_execution],
                    last_bar_date=ctx["lb_d"],
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
                    constraints=cst_daily,
                    portfolio_skips=portfolio_skips,
                    allocation_fn=allocate_d,
                    use_floor_sizing=True,
                    engine_label="daily",
                    ranking_preset_name=DAILY_PRESET_NAME,
                    trade_funnel=trade_funnel,
                    live_mode_relaxed=live_mode_relaxed,
                    recent_entries_collector=recent_entries,
                    execution_adapter=execution_adapter,
                    execution_adapter_health_ok=bool(execution_adapter_health_ok),
                    execution_events=execution_events,
                    execution_skip_counts=execution_skip_counts,
                    execution_order_counter=execution_order_counter,
                    execution_max_orders_per_run=execution_max_orders_per_run,
                    execution_allowed_symbols=execution_allowed_symbols_set,
                    execution_risk_config=execution_risk_config,
                    execution_account_equity=execution_account_equity,
                    execution_adapter_positions=execution_adapter_positions,
                    execution_market_is_open=execution_market_is_open,
                    execution_control_state=execution_control_state,
                    execution_control_day=execution_control_day,
                    execution_daily_order_counter=execution_daily_order_counter,
                    verbose_execution_events=verbose_execution_events,
                    silent_signal_telemetry=True,
                    placement_phase="dual_ranked_after_scan_daily",
                    candidate_log_prefix="dual",
                )
                n_new_signals_daily += ns
                n_new_entries += ne
                n_alerts_sent += ae2
                n_alerts_failed += af2
                if ne > 0:
                    placed_daily_syms.append(sy_u)
                xe2, ae3, af3 = lpe.process_exits_for_symbol(
                    sym=ctx["sym"],
                    combo_label=DAILY_PRESET_NAME,
                    interval=DAILY_INTERVAL,
                    trades=ctx["trades_d"],
                    state=state,
                    run_timestamp=run_ts,
                    dry_run=dry_run,
                    telegram_dry_run=telegram_dry_run,
                    send_message=send_message,
                    build_exit=build_exit,
                    output_scope=output_scope,
                    df=ctx["d_d"],
                    portfolio_state=portfolio_state,
                    execution_adapter=execution_adapter,
                    execution_adapter_positions=execution_adapter_positions,
                    execution_events=execution_events,
                    verbose_execution_events=verbose_execution_events,
                    stop_check_df=ctx["stop_d"],
                    engine_cfg=cfg_d,
                    execution_market_is_open=execution_market_is_open,
                )
                n_exits += xe2
                n_alerts_sent += ae3
                n_alerts_failed += af3

            audit_d = alphabet_bias_audit_summary(
                placed_daily_syms,
                total_scanned=n_daily_syms_scanned,
                total_candidates=len(ranked_d),
            )
            audit_d["engine"] = "daily"
            audit_d["selection_after_full_universe_scan"] = True
            audit_d["scan_order_seed"] = int(_scan_seed)
            logger.info("dual_alphabet_bias_audit_summary %s", audit_d)

        elif not exits_only:
            for sym, pk in packs.items():
                _dual_weekly_sym_pass(sym, pk, entry_intent_bucket=None)
            for sym, pk in packs.items():
                _dual_daily_sym_pass(sym, pk, entry_intent_bucket=None)

        cr_after = total_combined_risk_fraction(state.open_positions, capital=cap)
        if cr_after > COMBINED_MAX_TOTAL_RISK + 1e-9:
            msg = f"[PAPER SAFETY] combined_risk_fraction={cr_after:.4f} exceeds cap {COMBINED_MAX_TOTAL_RISK}"
            logger.warning("%s", msg)
            print(msg, flush=True)

        if not dry_run:
            try:
                save_portfolio_state(portfolio_state, artifact_paths["paper_portfolio_state_json"])
            except Exception as exc:  # noqa: BLE001
                logger.exception("save_portfolio_state failed")
                state_write_errors.append(f"save_portfolio_state:{type(exc).__name__}: {exc}")
            try:
                safety_state = maybe_warn_signal_anomalies_dual(
                    n_new_signals_daily=int(n_new_signals_daily),
                    n_new_signals_weekly=int(n_new_signals_weekly),
                    safety=safety_state,
                    logger=logger,
                )
                save_safety_state(safety_state, artifact_paths["paper_safety_state_json"])
            except Exception as exc:  # noqa: BLE001
                logger.exception("save_safety_state failed")
                state_write_errors.append(f"save_safety_state:{type(exc).__name__}: {exc}")
            try:
                write_paper_positions_snapshot(
                    state.open_positions,
                    marks,
                    capital=cap,
                    path=artifact_paths["paper_positions_snapshot_json"],
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("write_paper_positions_snapshot failed")
                state_write_errors.append(f"write_paper_positions_snapshot:{type(exc).__name__}: {exc}")
            try:
                _write_engine_split_json(
                    artifact_paths=artifact_paths,
                    state=state,
                    capital=cap,
                    marks=marks,
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("_write_engine_split_json failed")
                state_write_errors.append(f"_write_engine_split_json:{type(exc).__name__}: {exc}")

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
            "[PAPER SUMMARY DUAL]\n"
            f"open_positions={len(state.open_positions)}\n"
            f"new_signals_daily={n_new_signals_daily} new_signals_weekly={n_new_signals_weekly}\n"
            f"new_entries={n_new_entries}\n"
            f"new_exits={n_exits}\n"
            f"stop_loss_triggered_count={lpe._stop_loss_triggered_count(execution_events)}\n"
            f"combined_risk_fraction={total_combined_risk_fraction(state.open_positions, capital=cap):.4f}\n"
            f"skipped={dict(portfolio_skips)}\n"
            + "\n".join(details_lines)
        )
        for ln in summary_lines.splitlines():
            logger.info("%s", ln)
        print(summary_lines, flush=True)
        paper_live_log_line(summary_lines.replace("\n", " | "))
        for path_dest, text in (
            (artifact_paths["paper_live_log_combined_txt"], summary_lines),
            (artifact_paths["paper_live_log_daily_txt"], "[DUAL] daily engine pass complete"),
            (artifact_paths["paper_live_log_weekly_txt"], "[DUAL] weekly engine pass complete"),
        ):
            path_dest.parent.mkdir(parents=True, exist_ok=True)
            with path_dest.open("a", encoding="utf-8") as fh:
                fh.write(run_ts + " " + text.replace("\n", " | ") + "\n")

        runtime = max(0.0, time.perf_counter() - cycle_started_perf)
        n_open_after = len(state.open_positions)
        combo_label = f"{DAILY_PRESET_NAME}+{WEEKLY_PRESET_NAME}"
        sum_dedup_key = summary_alert_dedup_key(
            run_timestamp=run_ts,
            interval="dual",
            output_dir=output_dir,
            combos=[DAILY_PRESET_NAME, WEEKLY_PRESET_NAME],
        )
        reconciliation = lpe._safe_reconcile_adapter_positions(execution_adapter, state.open_positions)
        if execution_adapter is not None:
            lpe._record_execution_event(
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
        lpe._append_execution_order_event(
            state,
            event_type="reconcile_success" if bool(reconciliation.get("reconciliation_ok", True)) else "reconcile_failed",
            adapter=type(execution_adapter).__name__ if execution_adapter is not None else "",
            status="ok" if bool(reconciliation.get("reconciliation_ok", True)) else "failed",
            reason=str(reconciliation.get("reconciliation_error", "")),
            result={"raw_response": reconciliation, "error": str(reconciliation.get("reconciliation_error", ""))},
            accepted=bool(reconciliation.get("reconciliation_ok", True)),
            dry_run=bool(getattr(execution_adapter, "dry_run", False)) if execution_adapter is not None else False,
        )
        reconciled_missing_broker_count = lpe.reconcile_missing_broker_positions(
            state=state,
            reconciliation=reconciliation,
            execution_adapter=execution_adapter,
            execution_events=execution_events,
        )
        unmanaged_external_broker_count = lpe.record_external_broker_positions(
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
        summary: dict[str, Any] = {
            "run_timestamp": run_ts,
            "mode": mode_label,
            "interval": "dual",
            "combos": [DAILY_PRESET_NAME, WEEKLY_PRESET_NAME],
            "config_preset": combo_label,
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
            "n_new_signals": int(n_new_signals_daily) + int(n_new_signals_weekly),
            "n_new_signals_daily": int(n_new_signals_daily),
            "n_new_signals_weekly": int(n_new_signals_weekly),
            "n_new_entries": n_new_entries,
            "n_new_exits": n_exits,
            "stop_loss_triggered_count": lpe._stop_loss_triggered_count(execution_events),
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
            "summary_alert_status": "pending",
            "summary_alert_dedup_key": sum_dedup_key,
            "summary_alert_fail_reason": "",
            "combined_risk_fraction": float(cr_after),
            "execution_mode": str(execution_mode),
            "execution_adapter": type(execution_adapter).__name__ if execution_adapter is not None else "",
            "execution_adapter_health": execution_adapter_health or {},
            "execution_adapter_health_ok": bool(execution_adapter_health_ok),
            "execution_degraded": bool(execution_mode_l == "alpaca" and not bool(execution_adapter_health_ok)),
            "execution_enabled": bool(execution_mode_l != "alpaca" or bool(execution_adapter_health_ok)),
            "execution_max_orders_per_run": execution_max_orders_per_run,
            "execution_orders_placed_count": int(execution_order_counter.get("placed", 0)),
            "execution_allowed_symbols": sorted(execution_allowed_symbols_set) if execution_allowed_symbols_set is not None else [],
            "execution_risk_config": execution_risk_config.to_dict() if hasattr(execution_risk_config, "to_dict") else {},
            "execution_account_equity": execution_account_equity,
            "execution_market_is_open": execution_market_is_open,
            "execution_control_state_path": str(CONTROL_STATE_PATH) if execution_control_state is not None else "",
            "execution_kill_switch_enabled": bool(execution_control_state.get("kill_switch_enabled", False)) if execution_control_state is not None else False,
            "execution_alpaca_dry_run": bool(getattr(execution_adapter, "dry_run", False)) if execution_mode_l == "alpaca" and execution_adapter is not None else False,
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
            "skipped_not_relevant_to_last_bar_count": int(execution_skip_counts.get("not_relevant_to_last_bar", 0)),
            "skipped_duplicate_symbol_open_count": int(execution_skip_counts.get("duplicate_symbol_open", 0)),
            "skipped_other_count": int(execution_skip_counts.get("other", 0)),
        }

        run_debug.merge_into_summary(summary)
        if signal_flow is not None:
            signal_flow.merge_into_summary(summary)
        if trade_funnel is not None:
            trade_funnel.finalize_cycle(
                run_timestamp=run_ts,
                mode=mode_label,
                interval="dual",
                output_dir=str(output_dir.resolve()),
                n_new_signals_daily=int(n_new_signals_daily),
                n_new_signals_weekly=int(n_new_signals_weekly),
                n_new_entries=int(n_new_entries),
                n_new_exits=int(n_exits),
                n_open_positions=len(state.open_positions),
                combined_risk_fraction=float(cr_after),
                n_signals_rejected_as_old=int(n_signals_rejected_as_old),
            )
            trade_funnel.write_artifacts()
            trade_funnel.merge_into_summary(summary)
            _tf_txt = trade_funnel.format_debug_summary_text()
            for _ln in _tf_txt.splitlines():
                logger.info("%s", _ln)
            print(_tf_txt, flush=True)

        if last_bar_diagnostic_enabled() and packs:
            from services.live_last_bar_diagnostic import (
                build_last_bar_relevance_diagnostic,
                format_last_bar_diagnostic_console,
                write_last_bar_diagnostic_reports,
            )

            _funnel_doc = trade_funnel.build_json_document() if trade_funnel is not None else {}
            _ts_safe = str(run_ts).replace(":", "-")
            _prefix = artifact_paths["combined_dir"] / f"last_bar_relevance_diagnostic_{_ts_safe}"
            _diag_doc = build_last_bar_relevance_diagnostic(
                run_timestamp=run_ts,
                mode=mode_label,
                packs=packs,
                cfg_daily=cfg_d,
                cfg_weekly=cfg_w,
                post_sim_rows=_lb_post_sim_rows,
                funnel_doc=_funnel_doc,
            )
            _diag_paths = write_last_bar_diagnostic_reports(_prefix, _diag_doc, post_sim_rows=_lb_post_sim_rows)
            summary["last_bar_relevance_diagnostic_json"] = _diag_paths.get("json", "")
            summary["last_bar_relevance_diagnostic_prefix"] = str(_prefix)
            for _k, _p in _diag_paths.items():
                summary[f"last_bar_relevance_diagnostic_{_k}"] = _p
            _diag_txt = format_last_bar_diagnostic_console(_diag_doc)
            for _ln in _diag_txt.splitlines():
                logger.info("%s", _ln)
            print(_diag_txt, flush=True)

        if not dry_run:
            from services.live_paper_state import append_csv_row, write_live_summary

            summary["summary_alert_status"] = "dual_engine_minimal"
            summary["summary_alert_fail_reason"] = ""
            lpe._merge_execution_block_diagnostics(summary, execution_events)
            lpe._merge_execution_exit_diagnostics(summary, execution_events, state)
            lpe._write_execution_decision_summary(
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
                lpe.export_paper_trade_details(state)
            except Exception as exc:  # noqa: BLE001
                logger.exception("export_paper_trade_details failed")
                state_write_errors.append(f"export_paper_trade_details:{type(exc).__name__}: {exc}")
            hist_row = {
                "timestamp": summary["run_timestamp"],
                "run_timestamp": summary["run_timestamp"],
                "run_status": (
                    "success"
                    if len(state_write_errors) == 0
                    and int(summary.get("n_errors") or 0) == 0
                    and not bool(summary.get("execution_degraded", False))
                    else "partial_success"
                ),
                "execution_adapter_ok": bool(summary.get("execution_adapter_health_ok", True)),
                "orders_attempted": lpe._execution_event_counts(execution_events)["attempts"],
                "orders_success": lpe._execution_event_counts(execution_events)["success"],
                "orders_failed": lpe._execution_event_counts(execution_events)["failed"],
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
                "n_new_signals_daily": summary.get("n_new_signals_daily"),
                "n_new_signals_weekly": summary.get("n_new_signals_weekly"),
                "n_new_entries": summary["n_new_entries"],
                "n_new_exits": summary["n_new_exits"],
                "n_alerts_sent": summary["n_alerts_sent"],
                "n_alerts_failed": summary["n_alerts_failed"],
                "n_errors": summary["n_errors"],
                "errors_sample": str(summary.get("errors_sample")),
                "runtime_seconds": summary["runtime_seconds"],
            }
            summary["state_write_ok"] = len(state_write_errors) == 0
            summary["state_write_errors_sample"] = state_write_errors[:20]
            summary["atomic_write_stats"] = lpe.get_atomic_write_stats()
            summary["fallback_writes_count"] = int(summary["atomic_write_stats"].get("fallback_direct_overwrite", 0))
            summary["run_status"] = hist_row["run_status"]
            lpe._write_execution_decision_summary(
                state=state,
                summary=summary,
                execution_events=execution_events,
            )
            append_csv_row(
                state.paths()["live_run_history_csv"],
                hist_row,
                list(hist_row.keys()),
            )
            write_live_summary(state.paths()["live_summary_latest"], summary)
        else:
            summary["summary_alert_status"] = "skipped_dry_run"
            summary["summary_alert_fail_reason"] = ""
            lpe._merge_execution_block_diagnostics(summary, execution_events)
            lpe._merge_execution_exit_diagnostics(summary, execution_events, state)
            lpe._write_execution_decision_summary(
                state=state,
                summary=summary,
                execution_events=execution_events,
            )

        return summary
