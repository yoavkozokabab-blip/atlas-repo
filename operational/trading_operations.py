"""Trading operations assistant (Phase 50)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from config import PROJECT_ROOT, TRADING_PROJECT_ROOT
from core.logger import setup_logger

logger = setup_logger("jarvis.operational.trading")

TRADING_OPS_REPORT_DIR = PROJECT_ROOT / "reports" / "trading_operations"


def _save_report(name: str, body: str) -> str:
    TRADING_OPS_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    md = TRADING_OPS_REPORT_DIR / f"{ts}_{name}.md"
    md.write_text(body, encoding="utf-8")
    return str(md)


def summarize_trading_health() -> str:
    from runtime.result_stream import stream_progress, stream_result

    sections: list[str] = ["Trading health summary:"]
    stream_progress("scanning reports...")
    try:
        from investigation.execution_investigation import audit_execution_path

        stream_progress("analyzing execution blockers...")
        audit = audit_execution_path()[:800]
        sections.append(audit)
        if "blocker" in audit.lower():
            top = next((line for line in audit.splitlines() if "blocker" in line.lower()), "")
            if top:
                stream_result(top.strip()[:160])
    except Exception as exc:
        sections.append(f"  execution audit unavailable: {exc}")
    try:
        from runtime.healing_engine import show_runtime_health

        stream_progress("checking runtime health...")
        sections.append(show_runtime_health())
    except Exception as exc:
        sections.append(f"  runtime health unavailable: {exc}")
    try:
        from investigation.execution_cleanup import show_stale_open_positions

        stream_progress("checking stale open positions...")
        stale = show_stale_open_positions()
        sections.append(stale)
        if "stale" in stale.lower():
            stream_result("stale open positions detected", severity="warning")
            try:
                from assistant.notifications import notify_stale_positions_detected

                notify_stale_positions_detected(stale.splitlines()[0][:120])
            except Exception:
                pass
    except Exception as exc:
        sections.append(f"  stale positions unavailable: {exc}")
    body = "\n\n".join(sections)
    report = _save_report("trading_health", body)
    return f"{body}\n\nreport: {report}"


def explain_why_no_trades_today() -> str:
    try:
        from investigation.execution_investigation import explain_zero_execution_attempts

        return explain_zero_execution_attempts()
    except Exception as exc:
        return f"Unable to explain zero trades: {exc}"


def compare_today_vs_yesterday() -> str:
    dual = TRADING_PROJECT_ROOT / "reports" / "live_paper" / "dual"
    today = datetime.now(timezone.utc).date().isoformat()
    lines = [f"Compare today ({today}) vs yesterday:"]
    summary_path = dual / "execution_decision_summary.json"
    if summary_path.exists():
        try:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
            lines.append(f"  current eligible signals hint: {payload.get('signals_eligible', payload.get('n_signals', 'n/a'))}")
            lines.append(f"  execution attempts: {payload.get('execution_attempts', payload.get('n_orders', 'n/a'))}")
            lines.append(f"  primary blocker: {payload.get('primary_execution_blocker', payload.get('reason_if_no_attempt', 'n/a'))}")
        except json.JSONDecodeError:
            lines.append("  execution_decision_summary.json invalid")
    else:
        lines.append("  no current execution summary found")
    lines.append("  note: historical day-over-day requires archived daily reports")
    return "\n".join(lines)


def show_top_operational_blockers() -> str:
    try:
        from investigation.execution_investigation import rank_execution_block_reasons

        return rank_execution_block_reasons()
    except Exception as exc:
        return f"Blocker ranking unavailable: {exc}"


def show_current_execution_risk() -> str:
    try:
        from investigation.execution_cleanup import _build_preview

        preview = _build_preview()
        return "\n".join(
            [
                "Current execution risk:",
                f"  open risk fraction daily: {preview.open_risk_fraction_daily_before}",
                f"  cap: {preview.daily_max_total_risk_cap}",
                f"  kill switch: {preview.kill_switch_enabled}",
                f"  adapter health: {preview.adapter_health_ok}",
                f"  execution enabled: {preview.execution_enabled}",
                f"  primary blocker: {preview.primary_execution_blocker}",
            ]
        )
    except Exception as exc:
        return f"Execution risk unavailable: {exc}"


def summarize_live_engine_status() -> str:
    lines = ["Live engine status:"]
    engine = TRADING_PROJECT_ROOT / "services" / "live_paper_engine.py"
    cycle = TRADING_PROJECT_ROOT / "services" / "live_dual_paper_cycle.py"
    lines.append(f"  engine file: {'present' if engine.exists() else 'missing'}")
    lines.append(f"  cycle file: {'present' if cycle.exists() else 'missing'}")
    state = TRADING_PROJECT_ROOT / "reports" / "live_paper" / "dual" / "state" / "open_positions.json"
    if state.exists():
        try:
            positions = json.loads(state.read_text(encoding="utf-8"))
            count = len(positions) if isinstance(positions, list) else 0
            lines.append(f"  open positions: {count}")
        except json.JSONDecodeError:
            lines.append("  open positions: invalid json")
    else:
        lines.append("  open positions: none")
    try:
        from investigation.execution_investigation import inspect_execution_adapter

        lines.append(inspect_execution_adapter()[:500])
    except Exception as exc:
        lines.append(f"  adapter inspect failed: {exc}")
    return "\n".join(lines)
