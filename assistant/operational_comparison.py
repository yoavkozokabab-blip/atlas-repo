"""Operational period comparison intelligence (Phase 55)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _filter_by_window(entries: list[dict[str, Any]], *, hours: float) -> list[dict[str, Any]]:
    cutoff = _now() - timedelta(hours=hours)
    filtered: list[dict[str, Any]] = []
    for entry in entries:
        ts = entry.get("timestamp") or entry.get("updated_at") or entry.get("created_at")
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except ValueError:
            continue
        if dt >= cutoff:
            filtered.append(entry)
    return filtered


def compare_operational_periods() -> str:
    lines = ["Operational period comparison (today vs yesterday):"]
    try:
        from assistant.intelligence_timeline import _load as load_timeline

        entries = load_timeline().get("entries") or []
        today = _filter_by_window(entries, hours=24)
        yesterday = _filter_by_window(entries, hours=48)
        yesterday_only = [e for e in yesterday if e not in today]
        lines.append(f"  timeline events today: {len(today)}")
        lines.append(f"  timeline events yesterday: {len(yesterday_only)}")
    except Exception as exc:
        lines.append(f"  timeline comparison unavailable: {exc}")

    try:
        from investigation.blocker_trends import _load as load_trends

        snapshots = load_trends().get("snapshots") or []
        recent = snapshots[-1].get("counts") if snapshots else {}
        older = snapshots[-2].get("counts") if len(snapshots) > 1 else {}
        lines.append("  blocker deltas:")
        keys = set(recent.keys()) | set(older.keys())
        for key in sorted(keys)[:6]:
            delta = int(recent.get(key, 0)) - int(older.get(key, 0))
            if delta != 0:
                lines.append(f"    {key}: {delta:+d}")
    except Exception as exc:
        lines.append(f"  blocker comparison unavailable: {exc}")

    try:
        from assistant.confidence_tracking import _load as load_confidence

        series = load_confidence().get("series") or {}
        for rid, points in list(series.items())[:3]:
            if len(points) >= 2:
                delta = points[-1].get("causal_score", 0) - points[-2].get("causal_score", 0)
                lines.append(f"  causal delta {rid}: {delta:+.2f}")
    except Exception:
        pass
    return "\n".join(lines)


def compare_before_after_cleanup() -> str:
    lines = ["Before/after cleanup comparison:"]
    try:
        from investigation.execution_cleanup import compare_risk_before_after_cleanup

        lines.append(compare_risk_before_after_cleanup()[:900])
    except Exception as exc:
        lines.append(f"Cleanup comparison unavailable: {exc}")
    try:
        from investigation.blocker_trends import compare_blocker_trends

        lines.append("")
        lines.append(compare_blocker_trends()[:600])
    except Exception:
        pass
    return "\n".join(lines)


def compare_investigation_periods() -> str:
    lines = ["Investigation period comparison:"]
    try:
        from config import PROJECT_ROOT

        report_dir = PROJECT_ROOT / "reports" / "autonomous_investigations"
        reports = sorted(report_dir.glob("*_cycle.json"), reverse=True) if report_dir.is_dir() else []
        if len(reports) >= 2:
            latest = __import__("json").loads(reports[0].read_text(encoding="utf-8"))
            previous = __import__("json").loads(reports[1].read_text(encoding="utf-8"))
            lines.append(f"  latest anomalies: {len(latest.get('anomalies') or [])}")
            lines.append(f"  previous anomalies: {len(previous.get('anomalies') or [])}")
            delta = len(latest.get("anomalies") or []) - len(previous.get("anomalies") or [])
            lines.append(f"  anomaly delta: {delta:+d}")
        else:
            lines.append("  insufficient investigation cycle reports for comparison")
    except Exception as exc:
        lines.append(f"  investigation comparison unavailable: {exc}")

    try:
        from assistant.root_cause_engine import _load as load_root_causes

        history = load_root_causes().get("history") or []
        if len(history) >= 2:
            latest = history[-1]
            previous = history[-2]
            lines.append(
                f"  root cause causal score: {previous.get('causal_score', 0):.2f} -> "
                f"{latest.get('causal_score', 0):.2f}"
            )
    except Exception:
        pass
    return "\n".join(lines)
