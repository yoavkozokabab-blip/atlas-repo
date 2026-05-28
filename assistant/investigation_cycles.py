"""Autonomous investigation cycle runner (Phase 54)."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

from config import PROJECT_ROOT
from core.logger import setup_logger

logger = setup_logger("jarvis.assistant.investigation_cycles")

CYCLE_REPORT_DIR = PROJECT_ROOT / "reports" / "autonomous_investigations"
MAX_SECTION_CHARS = 1200


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_section(label: str, fn, *, limit: int = MAX_SECTION_CHARS) -> str:
    try:
        body = fn()
        if callable(body):
            body = body()
        text = str(body or "")
        return f"## {label}\n{text[:limit]}"
    except Exception as exc:
        return f"## {label}\nunavailable: {exc}"


def run_investigation_cycle(*, kind: str = "manual", include_nightly: bool = False) -> dict[str, Any]:
    """Run a read-only autonomous investigation cycle."""
    from runtime.result_stream import stream_progress, stream_result

    started = time.perf_counter()
    stream_progress(f"starting investigation cycle ({kind})...")

    sections: list[str] = [f"# Autonomous Investigation Cycle ({kind})", f"Generated: {_now()}"]
    anomalies: list[str] = []
    recommendations: list[dict[str, Any]] = []

    stream_progress("gathering runtime health...")
    runtime = _safe_section("Runtime health", lambda: __import__("runtime.healing_engine", fromlist=["show_runtime_health"]).show_runtime_health())
    sections.append(runtime)
    if "degraded" in runtime.lower() or "failed" in runtime.lower():
        anomalies.append("Runtime health degraded")

    stream_progress("gathering execution health...")
    execution = _safe_section(
        "Execution health",
        lambda: __import__("operational.trading_operations", fromlist=["summarize_trading_health"]).summarize_trading_health(),
    )
    sections.append(execution)

    stream_progress("analyzing blockers...")
    from investigation.blocker_trends import detect_trend_anomalies, record_blocker_snapshot

    snapshot = record_blocker_snapshot(source=kind)
    top_blockers = sorted((snapshot.get("counts") or {}).items(), key=lambda x: x[1], reverse=True)[:5]
    sections.append("## Blocker snapshot\n" + "\n".join(f"- {k}: {v}" for k, v in top_blockers))
    anomalies.extend(detect_trend_anomalies())

    stream_progress("detecting anomalies...")
    try:
        from runtime.dashboard_health import probe_dashboard_health

        probe = probe_dashboard_health()
        if probe.get("status") in {"degraded", "failed"}:
            anomalies.append(f"Dashboard status={probe.get('status')}")
    except Exception:
        pass

    stream_progress("ranking hypotheses...")
    from assistant.hypothesis_engine import refresh_hypotheses

    hypotheses = refresh_hypotheses()
    if hypotheses:
        top = hypotheses[0]
        sections.append(
            "## Top hypothesis\n"
            f"- {top.get('title')} (confidence={top.get('confidence', 0):.2f})\n"
            f"- verify: {top.get('verify_command', 'n/a')}"
        )
        stream_result(f"top hypothesis: {top.get('title', '')[:100]}")
        recommendations.append(
            {
                "severity": "warning",
                "confidence": top.get("confidence", 0),
                "recurrence": top.get("recurrence", 1),
                "impact": "execution suppression",
                "command": top.get("verify_command", ""),
                "summary": top.get("title", ""),
            }
        )

    if include_nightly:
        stream_progress("running nightly divergence clustering...")
        from investigation.divergence_clustering import cluster_replay_divergences

        clusters = cluster_replay_divergences()
        if clusters.get("clusters"):
            top_cluster = clusters["clusters"][0]
            sections.append(
                "## Divergence clusters\n"
                f"- largest: {top_cluster.get('type')} count={top_cluster.get('count')}"
            )
            anomalies.append(f"Divergence cluster: {top_cluster.get('type')}")

        stream_progress("running nightly validation sweep preview...")
        try:
            from investigation.historical_validation import run_historical_validation_sweep

            sweep = run_historical_validation_sweep()
            sections.append(
                "## Historical validation\n"
                f"- signals analyzed: {sweep.total_signals_analyzed}\n"
                f"- unresolved divergences: {sweep.unresolved_divergences}"
            )
        except Exception as exc:
            sections.append(f"## Historical validation\nunavailable: {exc}")

    stream_progress("generating recommendations...")
    if not recommendations:
        recommendations.append(
            {
                "severity": "info",
                "confidence": 0.6,
                "recurrence": 1,
                "impact": "monitoring",
                "command": "summarize trading health",
                "summary": "Continue operational monitoring",
            }
        )
    sections.append("## Recommendations")
    for rec in recommendations[:5]:
        sections.append(
            f"- [{rec['severity']}] {rec['summary']} "
            f"(confidence={rec['confidence']:.2f}, cmd={rec['command']})"
        )

    elapsed = round(time.perf_counter() - started, 2)
    body_md = "\n\n".join(sections) + f"\n\nElapsed: {elapsed}s\n"
    payload = {
        "kind": kind,
        "started_at": _now(),
        "elapsed_seconds": elapsed,
        "anomalies": anomalies,
        "recommendations": recommendations,
        "hypotheses": hypotheses,
        "blocker_snapshot": snapshot,
    }

    CYCLE_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = CYCLE_REPORT_DIR / f"{ts}_cycle.json"
    md_path = CYCLE_REPORT_DIR / f"{ts}_cycle.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    md_path.write_text(body_md, encoding="utf-8")
    payload["report_json"] = str(json_path)
    payload["report_markdown"] = str(md_path)

    from assistant.intelligence_timeline import append_timeline_entry

    for anomaly in anomalies[:5]:
        append_timeline_entry(
            "execution_anomaly",
            anomaly,
            severity="warning",
            source=f"cycle:{kind}",
            metadata={"suggested_action": recommendations[0].get("command", "") if recommendations else ""},
        )
    append_timeline_entry(
        "investigation_cycle",
        f"Cycle {kind} completed in {elapsed}s with {len(anomalies)} anomalies",
        severity="info" if not anomalies else "warning",
        source="investigation_cycles",
        metadata={"report": str(json_path)},
    )

    try:
        from assistant.notifications import notify_proactive

        if anomalies:
            notify_proactive(
                "Autonomous investigation findings",
                "; ".join(anomalies[:3])[:200],
                suggested_action=recommendations[0].get("command", "show intelligence timeline"),
            )
    except Exception:
        pass

    stream_progress("investigation cycle complete")
    return payload


def run_nightly_investigation() -> dict[str, Any]:
    return run_investigation_cycle(kind="nightly", include_nightly=True)


def summarize_autonomous_findings() -> str:
    reports = sorted(CYCLE_REPORT_DIR.glob("*_cycle.json"), reverse=True)
    if not reports:
        return "No autonomous investigation cycles recorded yet."
    latest = json.loads(reports[0].read_text(encoding="utf-8"))
    lines = [
        "Autonomous findings (latest cycle):",
        f"  kind: {latest.get('kind', 'unknown')}",
        f"  elapsed: {latest.get('elapsed_seconds', 0)}s",
        f"  anomalies: {len(latest.get('anomalies') or [])}",
    ]
    for anomaly in (latest.get("anomalies") or [])[:5]:
        lines.append(f"  - {anomaly}")
    recs = latest.get("recommendations") or []
    if recs:
        lines.append(f"  top recommendation: {recs[0].get('summary', '')} -> {recs[0].get('command', '')}")
    if latest.get("report_markdown"):
        lines.append(f"  report: {latest['report_markdown']}")
    return "\n".join(lines)


def summarize_operational_anomalies() -> str:
    from assistant.intelligence_timeline import explain_recent_anomalies

    return explain_recent_anomalies()
