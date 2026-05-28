"""Unified trading operations dashboard (Phase 51)."""

from __future__ import annotations

from datetime import datetime, timezone

from config import PROJECT_ROOT

REPORT_DIR = PROJECT_ROOT / "reports" / "trading_operations"


def show_trading_operations_dashboard() -> str:
    from runtime.result_stream import stream_progress

    sections: list[str] = ["Trading operations dashboard:", f"  generated: {datetime.now(timezone.utc).isoformat()}"]

    stream_progress("gathering execution blockers...")
    try:
        from investigation.execution_investigation import show_execution_blockers

        sections.append("\n## Execution blockers")
        sections.append(show_execution_blockers()[:600])
    except Exception as exc:
        sections.append(f"\nExecution blockers unavailable: {exc}")

    stream_progress("checking stale positions...")
    try:
        from investigation.execution_cleanup import show_stale_open_positions

        sections.append("\n## Stale positions")
        sections.append(show_stale_open_positions()[:400])
    except Exception as exc:
        sections.append(f"\nStale positions unavailable: {exc}")

    stream_progress("checking runtime health...")
    try:
        from runtime.healing_engine import show_runtime_health

        sections.append("\n## Runtime health")
        sections.append(show_runtime_health()[:500])
    except Exception as exc:
        sections.append(f"\nRuntime health unavailable: {exc}")

    stream_progress("assembling trading operations view...")
    try:
        from operational.trading_operations import show_current_execution_risk, summarize_live_engine_status

        sections.append("\n## Execution risk")
        sections.append(show_current_execution_risk())
        sections.append("\n## Live engine")
        sections.append(summarize_live_engine_status()[:500])
    except Exception as exc:
        sections.append(f"\nTrading ops unavailable: {exc}")

    try:
        from memory.task_memory import show_recent_investigations

        sections.append("\n## Recent investigations")
        sections.append(show_recent_investigations()[:400])
    except Exception:
        pass

    try:
        from investigation.patch_apply import show_patch_workflow_status

        sections.append("\n## Patch workflow")
        sections.append(show_patch_workflow_status()[:400])
    except Exception:
        pass

    body = "\n".join(sections)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"{ts}_trading_ops_dashboard.md"
    path.write_text(body, encoding="utf-8")
    return f"{body}\n\nreport: {path}"
