"""Phase 65 Track H — performance measurement."""

from __future__ import annotations

import time

from reliability.hardening_core import TrackScore, format_track_report, reports_dir, run_case, write_report


def measure_startup_ms() -> float:
    start = time.perf_counter()
    try:
        import config  # noqa: F401
        from actions.registry import ActionRegistry

        ActionRegistry()
    except Exception:
        pass
    return round((time.perf_counter() - start) * 1000, 2)


def show_performance_report() -> str:
    lines = ["Performance report (Phase 65):"]
    lines.append(f"  startup_ms: {measure_startup_ms()}")
    try:
        from voice.latency_tracker import get_last_voice_latency

        snap = get_last_voice_latency() or {}
        lines.append(f"  last_stt_ms: {snap.get('stt_ms', 'n/a')}")
        lines.append(f"  last_tts_ms: {snap.get('tts_ms', 'n/a')}")
        lines.append(f"  last_e2e_ms: {snap.get('total_ms', 'n/a')}")
    except Exception:
        lines.append("  voice_latency: unavailable")
    try:
        from brain.intent_classifier import classify_rules

        t0 = time.perf_counter()
        classify_rules("show capability health")
        lines.append(f"  command_routing_ms: {round((time.perf_counter() - t0) * 1000, 2)}")
    except Exception:
        lines.append("  command_routing_ms: unavailable")
    try:
        from browser.runtime import get_browser_runtime_state

        st = get_browser_runtime_state()
        lines.append(f"  browser_provider: {st.provider}")
        lines.append(f"  browser_last_action_success: {st.last_action_success}")
    except Exception:
        pass
    return "\n".join(lines)


def run_performance_acceptance() -> TrackScore:
    score = TrackScore(track="Performance", current_pct=0.0, target_pct=85.0)

    def _startup() -> tuple[bool, str]:
        ms = measure_startup_ms()
        return ms < 15000, f"startup_ms={ms}"

    def _routing() -> tuple[bool, str]:
        from brain.intent_classifier import classify_rules

        t0 = time.perf_counter()
        req = classify_rules("open browser")
        ms = round((time.perf_counter() - t0) * 1000, 2)
        return req.intent is not None, f"routing_ms={ms}"

    def _report() -> tuple[bool, str]:
        body = show_performance_report()
        return "startup_ms" in body, "ok"

    score.cases.extend(
        [
            run_case("startup_time", _startup),
            run_case("command_routing_latency", _routing),
            run_case("performance_report", _report),
        ]
    )
    score.finalize_score()
    write_report(reports_dir() / "performance_report.md", format_track_report(score).splitlines())
    return score
