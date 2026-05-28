"""Phase 49 autonomous operational healing (safe, bounded, audited)."""

from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import DATA_DIR, PROJECT_ROOT, TRADING_DASHBOARD_URL
from core.logger import setup_logger

logger = setup_logger("jarvis.runtime.healing")

HEALING_REPORT_DIR = PROJECT_ROOT / "reports" / "runtime_healing"
HEALING_STATE_PATH = DATA_DIR / "healing_state.json"
LOCK_GLOB = ("*.lock", "jarvis_*.lock", "speak.lock", "tts.lock")

MAX_RECOVERY_ATTEMPTS_PER_HOUR = int(os.getenv("HEALING_MAX_RECOVERIES_PER_HOUR", "6"))
RECOVERY_COOLDOWN_SECONDS = int(os.getenv("HEALING_RECOVERY_COOLDOWN_SECONDS", "120"))


@dataclass
class HealingState:
    recovery_times: list[float] = field(default_factory=list)
    recovery_log: list[dict[str, Any]] = field(default_factory=list)
    last_incident_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "recovery_times": self.recovery_times[-100:],
            "recovery_log": self.recovery_log[-100:],
            "last_incident_id": self.last_incident_id,
        }


def _load_state() -> HealingState:
    if not HEALING_STATE_PATH.exists():
        return HealingState()
    try:
        payload = json.loads(HEALING_STATE_PATH.read_text(encoding="utf-8"))
        return HealingState(
            recovery_times=list(payload.get("recovery_times") or []),
            recovery_log=list(payload.get("recovery_log") or []),
            last_incident_id=str(payload.get("last_incident_id") or ""),
        )
    except (OSError, json.JSONDecodeError, TypeError):
        return HealingState()


def _save_state(state: HealingState) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    HEALING_STATE_PATH.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _can_recover(state: HealingState) -> tuple[bool, str]:
    now = time.monotonic()
    recent = [t for t in state.recovery_times if now - t < 3600]
    if len(recent) >= MAX_RECOVERY_ATTEMPTS_PER_HOUR:
        return False, f"recovery limit reached ({MAX_RECOVERY_ATTEMPTS_PER_HOUR}/hour)"
    if recent and now - recent[-1] < RECOVERY_COOLDOWN_SECONDS:
        return False, f"cooldown active ({RECOVERY_COOLDOWN_SECONDS}s)"
    return True, ""


def _record_recovery(state: HealingState, action: str, ok: bool, detail: str) -> None:
    entry = {
        "ts": _now_iso(),
        "action": action,
        "ok": ok,
        "detail": detail[:500],
    }
    state.recovery_times.append(time.monotonic())
    state.recovery_log.append(entry)
    _save_state(state)
    _save_incident_report(action, ok, detail, entry)


def _save_incident_report(action: str, ok: bool, detail: str, entry: dict[str, Any]) -> str:
    HEALING_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    incident_id = f"{ts}_{action.replace(' ', '_')}"
    payload = {
        "incident_id": incident_id,
        "created_at": _now_iso(),
        "action": action,
        "ok": ok,
        "detail": detail,
        "entry": entry,
        "reversible": True,
    }
    json_path = HEALING_REPORT_DIR / f"{incident_id}.json"
    md_path = HEALING_REPORT_DIR / f"{incident_id}.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                f"# Runtime Incident ({action})",
                f"- ok: {ok}",
                f"- detail: {detail}",
                f"- created: {payload['created_at']}",
            ]
        ),
        encoding="utf-8",
    )
    state = _load_state()
    state.last_incident_id = incident_id
    _save_state(state)
    return str(md_path)


def _subsystem_snapshot() -> dict[str, Any]:
    snap: dict[str, Any] = {}
    try:
        from core.runtime_state import get_runtime_state

        rt = get_runtime_state()
        snap["runtime"] = {
            "running": rt.running,
            "voice_enabled": rt.voice_enabled,
            "overlay_enabled": rt.overlay_enabled,
            "wake_word_enabled": rt.wake_word_enabled,
            "speak_enabled": rt.speak_enabled,
        }
    except Exception as exc:
        snap["runtime"] = {"error": str(exc)}

    try:
        from ui.operator_console import get_operator_console

        console = get_operator_console()
        snap["operator_console"] = {
            "active": console is not None and console.is_alive(),
            "queue_length": console.queue_length() if console else 0,
        }
    except Exception as exc:
        snap["operator_console"] = {"error": str(exc)}

    try:
        from ui.overlay_app import get_overlay_controller

        ctrl = get_overlay_controller()
        overlay_snap = ctrl._state.snapshot()
        snap["overlay"] = (
            overlay_snap.__dict__
            if hasattr(overlay_snap, "__dict__")
            else {"phase": getattr(overlay_snap, "phase", overlay_snap)}
        )
    except Exception as exc:
        snap["overlay"] = {"error": str(exc)}

    try:
        from voice.wakeword_loop import get_active_detector

        detector = get_active_detector()
        thread = getattr(detector, "_thread", None)
        snap["wake_listener"] = {"alive": bool(thread and thread.is_alive())}
    except Exception as exc:
        snap["wake_listener"] = {"error": str(exc)}

    try:
        from services.runtime_monitor import get_runtime_monitor

        snap["runtime_monitor"] = get_runtime_monitor().status_snapshot()
    except Exception as exc:
        snap["runtime_monitor"] = {"error": str(exc)}

    try:
        from runtime.dashboard_health import dashboard_status_label, probe_dashboard_health

        probe = probe_dashboard_health()
        snap["dashboard"] = probe
    except Exception as exc:
        snap["dashboard"] = {"reachable": False, "url": TRADING_DASHBOARD_URL, "error": str(exc), "status": "failed"}

    try:
        from voice.tts import is_speaking

        snap["tts"] = {"speaking": is_speaking()}
    except Exception as exc:
        snap["tts"] = {"error": str(exc)}

    return snap


def collect_runtime_health() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    snap = _subsystem_snapshot()
    dash_status = "unknown"

    def _add(name: str, ok: bool, detail: str, severity: str = "ok") -> None:
        checks.append({"name": name, "ok": ok, "detail": detail, "severity": severity})

    rt = snap.get("runtime", {})
    _add("runtime", bool(rt.get("running", True)), f"running={rt.get('running')}")

    overlay = snap.get("overlay", {})
    if hasattr(overlay, "get"):
        phase = str(overlay.get("phase", ""))
    else:
        phase = str(getattr(overlay, "phase", overlay))
    overlay_ok = phase not in {"error", "stuck_speak", "speak"}
    if phase.lower() in {"speak", "speaking"}:
        overlay_ok = False
    _add("overlay", overlay_ok, f"phase={phase}", "warning" if not overlay_ok else "ok")

    wake = snap.get("wake_listener", {})
    _add("wake_listener", bool(wake.get("alive")), f"alive={wake.get('alive')}")

    console = snap.get("operator_console", {})
    qlen = int(console.get("queue_length") or 0)
    _add("operator_console", bool(console.get("active")), f"queue={qlen}", "warning" if qlen > 10 else "ok")

    dash = snap.get("dashboard", {})
    dash_status = str(dash.get("status") or ("healthy" if dash.get("reachable") else "failed"))
    dash_ok = dash_status == "healthy"
    dash_severity = "ok"
    if dash_status == "starting":
        dash_severity = "warning"
        dash_ok = True
    elif dash_status == "degraded":
        dash_severity = "warning"
    elif dash_status == "failed":
        dash_severity = "warning"
        dash_ok = False
    _add(
        "dashboard",
        dash_ok,
        f"status={dash_status} detail={dash.get('detail') or dash.get('url')}",
        dash_severity,
    )

    tts = snap.get("tts", {})
    tts_ok = not bool(tts.get("speaking"))
    _add("tts_worker", tts_ok, f"speaking={tts.get('speaking')}", "warning" if not tts_ok else "ok")

    monitor = snap.get("runtime_monitor", {})
    issues = monitor.get("issues") or []
    _add("runtime_monitor", not issues, f"issues={len(issues)}", "warning" if issues else "ok")

    overall = "healthy"
    if any(c["severity"] == "warning" for c in checks):
        overall = "degraded"
    if any(not c["ok"] and c.get("name") == "dashboard" and dash_status == "failed" for c in checks):
        overall = "failed"
    elif any(not c["ok"] for c in checks):
        overall = "degraded"

    return {
        "checked_at": _now_iso(),
        "overall": overall,
        "checks": checks,
        "snapshot": snap,
    }


def show_runtime_health() -> str:
    health = collect_runtime_health()
    lines = [
        f"Runtime health: {health['overall'].upper()}",
        f"  checked: {health['checked_at']}",
    ]
    for check in health["checks"]:
        flag = "OK" if check["ok"] else check["severity"].upper()
        lines.append(f"  [{flag}] {check['name']}: {check['detail']}")
    return "\n".join(lines)


def show_healing_actions() -> str:
    state = _load_state()
    lines = ["Recent healing actions:"]
    if not state.recovery_log:
        lines.append("  (none recorded)")
    for item in state.recovery_log[-15:]:
        lines.append(f"  - {item.get('ts')} {item.get('action')} ok={item.get('ok')} {item.get('detail', '')[:80]}")
    lines.append(f"  recovery limit: {MAX_RECOVERY_ATTEMPTS_PER_HOUR}/hour")
    lines.append(f"  cooldown: {RECOVERY_COOLDOWN_SECONDS}s")
    lines.append(f"  last incident: {state.last_incident_id or 'none'}")
    return "\n".join(lines)


def show_stuck_workers() -> str:
    try:
        from services.runtime_monitor import get_runtime_monitor

        status = get_runtime_monitor().status_snapshot()
    except Exception as exc:
        return f"Stuck worker scan failed: {exc}"
    ops = status.get("active_operations") or []
    issues = status.get("issues") or []
    lines = ["Stuck worker scan:"]
    if ops:
        for op in ops[:20]:
            if isinstance(op, dict):
                lines.append(
                    f"  - {op.get('name')} age={op.get('age_seconds')}s thread={op.get('thread')}"
                )
    else:
        lines.append("  no slow operations tracked")
    if issues:
        lines.append("Runtime issues:")
        for issue in issues[:10]:
            msg = issue.get("message") if isinstance(issue, dict) else str(issue)
            lines.append(f"  - {msg}")
    return "\n".join(lines)


def clear_stale_locks(*, confirmed: bool = False) -> str:
    if not confirmed:
        return "Clear stale locks requires confirmation. Re-run with confirm."
    removed: list[str] = []
    for pattern in LOCK_GLOB:
        for path in DATA_DIR.glob(pattern):
            try:
                age = time.time() - path.stat().st_mtime
                if age > 300:
                    path.unlink(missing_ok=True)
                    removed.append(path.name)
            except OSError:
                continue
    state = _load_state()
    _record_recovery(state, "clear_stale_locks", True, f"removed={len(removed)}")
    return f"Cleared stale locks: {', '.join(removed) or 'none found'}"


def recover_overlay(*, confirmed: bool = False) -> str:
    state = _load_state()
    allowed, reason = _can_recover(state)
    if not allowed:
        return f"Recover overlay blocked: {reason}"
    if not confirmed:
        return "Recover overlay requires confirmation. Re-run with confirm."
    try:
        from ui.overlay_app import get_overlay_controller

        ok = get_overlay_controller().recover_if_crashed(reason="healing_engine")
        detail = "overlay recovered" if ok else "overlay already healthy"
        _record_recovery(state, "recover_overlay", True, detail)
        return detail
    except Exception as exc:
        _record_recovery(state, "recover_overlay", False, str(exc))
        return f"Recover overlay failed: {exc}"


def recover_voice_system(*, confirmed: bool = False) -> str:
    state = _load_state()
    allowed, reason = _can_recover(state)
    if not allowed:
        return f"Recover voice blocked: {reason}"
    if not confirmed:
        return "Recover voice system requires confirmation. Re-run with confirm."
    try:
        from voice.tts_watchdog import kill_stuck_speech, stop_speech_hard

        kill_stuck_speech("healing_engine recover voice", from_watchdog=False)
        stop_speech_hard()
        detail = "voice/TTS soft recovery completed"
        _record_recovery(state, "recover_voice_system", True, detail)
        return detail
    except Exception as exc:
        _record_recovery(state, "recover_voice_system", False, str(exc))
        return f"Recover voice failed: {exc}"


def restart_dashboard(*, confirmed: bool = False) -> str:
    if not confirmed:
        return "Restart dashboard requires confirmation (opens dashboard URL for health check)."
    import webbrowser

    from runtime.dashboard_health import mark_dashboard_open_requested, probe_dashboard_health

    mark_dashboard_open_requested()
    webbrowser.open(TRADING_DASHBOARD_URL)
    probe = probe_dashboard_health()
    state = _load_state()
    _record_recovery(state, "restart_dashboard", True, f"opened {TRADING_DASHBOARD_URL} status={probe.get('status')}")
    return (
        f"Dashboard URL opened: {TRADING_DASHBOARD_URL}\n"
        f"  health status: {probe.get('status')}\n"
        f"  detail: {probe.get('detail')}"
    )


def restart_wake_listener(*, confirmed: bool = False) -> str:
    state = _load_state()
    allowed, reason = _can_recover(state)
    if not allowed:
        return f"Restart wake listener blocked: {reason}"
    if not confirmed:
        return "Restart wake listener requires confirmation."
    try:
        from voice.wakeword_loop import get_active_detector

        detector = get_active_detector()
        stop = getattr(detector, "stop", None)
        start = getattr(detector, "start", None)
        if callable(stop):
            stop()
        if callable(start):
            start()
        _record_recovery(state, "restart_wake_listener", True, "wake listener restarted")
        return "Wake listener restart requested."
    except Exception as exc:
        _record_recovery(state, "restart_wake_listener", False, str(exc))
        return f"Restart wake listener failed: {exc}"


def restart_operator_console(*, confirmed: bool = False) -> str:
    if not confirmed:
        return "Restart operator console requires confirmation (clears queue only)."
    try:
        from ui.operator_console import get_operator_console

        console = get_operator_console()
        if console is None:
            return "Operator console not active."
        with console._queue_cond:
            console._command_queue.clear()
        _record_recovery(_load_state(), "restart_operator_console", True, "queue cleared")
        return "Operator console queue cleared (console thread preserved)."
    except Exception as exc:
        return f"Restart operator console failed: {exc}"


def restart_failed_worker(worker: str = "", *, confirmed: bool = False) -> str:
    worker = (worker or "").strip().lower()
    mapping = {
        "overlay": recover_overlay,
        "voice": recover_voice_system,
        "tts": recover_voice_system,
        "dashboard": restart_dashboard,
        "wake": restart_wake_listener,
        "wake_listener": restart_wake_listener,
        "console": restart_operator_console,
        "operator_console": restart_operator_console,
    }
    if worker not in mapping:
        return f"Unknown worker {worker!r}. Supported: {', '.join(sorted(mapping))}"
    return mapping[worker](confirmed=confirmed)


def validate_runtime_integrity() -> str:
    health = collect_runtime_health()
    stuck = show_stuck_workers()
    lines = [
        "Runtime integrity validation:",
        f"  overall: {health['overall']}",
        f"  checks: {len(health['checks'])}",
    ]
    failed = [c for c in health["checks"] if not c["ok"]]
    lines.append(f"  failed checks: {len(failed)}")
    for check in failed:
        lines.append(f"    - {check['name']}: {check['detail']}")
    lines.append("")
    lines.append(stuck)
    lines.append(f"\nRESULT: {'PASS' if not failed else 'FAIL'}")
    report = _save_incident_report(
        "validate_runtime_integrity",
        not failed,
        f"failed={len(failed)}",
        {"checked_at": health["checked_at"]},
    )
    lines.append(f"  report: {report}")
    return "\n".join(lines)


def phase49_status() -> str:
    health = collect_runtime_health()
    state = _load_state()
    return "\n".join(
        [
            "Phase 49 — Autonomous Operational Healing",
            f"  runtime health: {health['overall']}",
            f"  recovery attempts (1h): {len([t for t in state.recovery_times if time.monotonic() - t < 3600])}",
            f"  max recoveries/hour: {MAX_RECOVERY_ATTEMPTS_PER_HOUR}",
            f"  cooldown seconds: {RECOVERY_COOLDOWN_SECONDS}",
            f"  reports: {HEALING_REPORT_DIR}",
            "  commands: show runtime health, recover overlay, recover voice system, validate runtime integrity",
        ]
    )
