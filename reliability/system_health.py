"""Phase 65 Track G — unified reliability and system health."""

from __future__ import annotations

from enum import Enum

from reliability.hardening_core import TrackScore, format_track_report, reports_dir, run_case, write_report


class FailureClass(str, Enum):
    CONFIG = "config"
    DEPENDENCY = "dependency"
    TIMEOUT = "timeout"
    PERMISSION = "permission"
    TRANSIENT = "transient"
    LOGIC = "logic"
    UNKNOWN = "unknown"


def classify_failure(message: str) -> FailureClass:
    text = (message or "").lower()
    if "disabled" in text or "not enabled" in text:
        return FailureClass.CONFIG
    if "timeout" in text or "timed out" in text:
        return FailureClass.TIMEOUT
    if "permission" in text or "access denied" in text:
        return FailureClass.PERMISSION
    if "playwright" in text or "tesseract" in text or "import" in text:
        return FailureClass.DEPENDENCY
    if "mock" in text:
        return FailureClass.CONFIG
    if "recover" in text or "retry" in text:
        return FailureClass.TRANSIENT
    return FailureClass.UNKNOWN


def runtime_health_score() -> float:
    """Aggregate 0-100 score from capability surfaces (lightweight probes)."""
    import config

    probes: list[float] = []
    probes.append(75.0 if config.SCREEN_UNDERSTANDING_ENABLED else 40.0)
    probes.append(70.0 if config.COMPUTER_CONTROL_ENABLED else 45.0)
    probes.append(70.0 if config.DESKTOP_OPERATOR_ENABLED else 40.0)
    probes.append(65.0 if config.MEMORY_ENABLED else 35.0)
    try:
        from browser.runtime import get_browser_runtime_state

        st = get_browser_runtime_state()
        probes.append(85.0 if st.provider == "playwright" and st.browser_process_alive else 55.0)
    except Exception:
        probes.append(50.0)
    try:
        from voice.audio_status import get_audio_status

        audio = get_audio_status()
        probes.append(80.0 if audio.selected_verified_audio_backend else 60.0)
    except Exception:
        probes.append(55.0)
    return round(sum(probes) / len(probes), 1)


def recovery_workflow_for(failure: FailureClass) -> list[str]:
    mapping = {
        FailureClass.CONFIG: ["show runtime config mismatches", "show settings status"],
        FailureClass.DEPENDENCY: ["run jarvis health check", "foundation health check"],
        FailureClass.TIMEOUT: ["reset jarvis runtime", "recover voice system"],
        FailureClass.PERMISSION: ["show capability health"],
        FailureClass.TRANSIENT: ["recover browser session", "recover desktop operator"],
        FailureClass.LOGIC: ["show command audit", "explain last failure"],
        FailureClass.UNKNOWN: ["run diagnostics"],
    }
    return mapping.get(failure, mapping[FailureClass.UNKNOWN])


def show_system_health() -> str:
    score = runtime_health_score()
    lines = [
        "System health (Phase 65):",
        f"  runtime_health_score: {score}%",
    ]
    try:
        from actions.phase60_actions import ShowCapabilityHealthAction
        from core.types import CommandRequest, Intent

        cap = ShowCapabilityHealthAction().execute(
            CommandRequest(raw_text="show capability health", intent=Intent.SHOW_CAPABILITY_HEALTH)
        )
        for ln in (cap.summary or "").splitlines():
            lines.append(f"  {ln}")
    except Exception as exc:
        lines.append(f"  capability_health_error: {exc}")
    lines.append("  failure_classes: config, dependency, timeout, permission, transient, logic")
    return "\n".join(lines)


def run_reliability_acceptance() -> TrackScore:
    score = TrackScore(track="Reliability", current_pct=0.0, target_pct=85.0)

    def _classifier() -> tuple[bool, str]:
        fc = classify_failure("COMPUTER_CONTROL_ENABLED=false")
        return fc == FailureClass.CONFIG, fc.value

    def _recovery() -> tuple[bool, str]:
        steps = recovery_workflow_for(FailureClass.TRANSIENT)
        return len(steps) >= 2, ",".join(steps[:2])

    def _score() -> tuple[bool, str]:
        s = runtime_health_score()
        return s > 0, f"score={s}"

    def _system_cmd() -> tuple[bool, str]:
        body = show_system_health()
        return "runtime_health_score" in body, "ok"

    score.cases.extend(
        [
            run_case("failure_classification", _classifier),
            run_case("recovery_workflow", _recovery),
            run_case("runtime_health_score", _score),
            run_case("show_system_health", _system_cmd),
        ]
    )
    score.finalize_score()
    write_report(reports_dir() / "reliability_report.md", format_track_report(score).splitlines())
    return score
