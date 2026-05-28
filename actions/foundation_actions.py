"""Phase 43 — foundation diagnostics (read-only, router-safe)."""

from __future__ import annotations

import os
from pathlib import Path

from actions.base import BaseAction
from core.results import result_failed, result_success
from core.types import CommandRequest, CommandResult, Intent


def _chrome_path_status() -> str:
    from config import CHROME_EXE

    path = Path(os.path.expandvars(str(CHROME_EXE)))
    return f"{'found' if path.is_file() else 'MISSING'}: {path}"


def _cursor_path_status() -> str:
    from config import CURSOR_EXE

    path = Path(os.path.expandvars(str(CURSOR_EXE)))
    return f"{'found' if path.is_file() else 'MISSING'}: {path}"


class ShowLauncherStatusAction(BaseAction):
    intent = Intent.SHOW_LAUNCHER_STATUS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        lines = ["Launcher status (read-only)"]
        lines.append(f"  chrome: {_chrome_path_status()}")
        lines.append(f"  cursor: {_cursor_path_status()}")
        try:
            from apps.app_registry import AppRegistry
            from config import APPROVED_APPS_PATH

            reg = AppRegistry(APPROVED_APPS_PATH)
            approved = reg.list_approved()
            lines.append(f"  approved_apps: {len(approved)}")
            for app in approved[:12]:
                ok = Path(app.shortcut_path).exists() if app.shortcut_path else False
                lines.append(
                    f"    - {app.app_id}: {'ok' if ok else 'missing'} ({app.display_name})"
                )
        except Exception as exc:
            lines.append(f"  approved_apps: error ({exc})")
        try:
            from websites.registry import WebsiteRegistry
            from config import APPROVED_WEBSITES_PATH

            wreg = WebsiteRegistry(APPROVED_WEBSITES_PATH)
            sites = [w.website_id for w in wreg.list_approved()]
            lines.append(f"  allowlisted_websites: {', '.join(sites[:20]) or '(none)'}")
        except Exception as exc:
            lines.append(f"  websites: error ({exc})")
        lines.append("  tip: approve apps with 'approve app <name>' after discovery")
        return result_success(Intent.SHOW_LAUNCHER_STATUS, "\n".join(lines))


class ShowControlStatusAction(BaseAction):
    intent = Intent.SHOW_CONTROL_STATUS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        import config as cfg

        lines = [
            "Computer control status",
            f"  enabled: {cfg.COMPUTER_CONTROL_ENABLED}",
            "  allowed: focus_window, clipboard read/write (confirmed), window list,",
            "           get_focused_app, minimize/maximize (allowlisted)",
            "  blocked: arbitrary shell, unrestricted keyboard/mouse automation",
        ]
        if not cfg.COMPUTER_CONTROL_ENABLED:
            lines.append(f"  message: {cfg.COMPUTER_CONTROL_DISABLED_MESSAGE}")
        return result_success(Intent.SHOW_CONTROL_STATUS, "\n".join(lines))


class ShowScreenStatusAction(BaseAction):
    intent = Intent.SHOW_SCREEN_STATUS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        import config as cfg

        lines = [
            "Screen understanding status",
            f"  SCREEN_UNDERSTANDING_ENABLED: {cfg.SCREEN_UNDERSTANDING_ENABLED}",
            f"  VISION_ENABLED: {cfg.VISION_ENABLED}",
            f"  SCREEN_OCR_ENABLED: {cfg.SCREEN_OCR_ENABLED}",
            f"  SCREEN_CAPTURE_MODE: {cfg.SCREEN_CAPTURE_MODE}",
            f"  SCREEN_REDACTION_ENABLED: {cfg.SCREEN_REDACTION_ENABLED}",
            f"  SCREEN_BLOCK_SECRET_WINDOWS: {cfg.SCREEN_BLOCK_SECRET_WINDOWS}",
        ]
        lines.append("  commands: describe screen, analyze active window, read screen text")
        return result_success(Intent.SHOW_SCREEN_STATUS, "\n".join(lines))


class BenchmarkVoiceModesAction(BaseAction):
    intent = Intent.BENCHMARK_VOICE_MODES.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        import config as cfg

        modes = [
            ("stable-small", {"VOICE_RUNTIME_MODE": "stable", "STT_MODEL": "small"}),
            ("stable-base", {"VOICE_RUNTIME_MODE": "stable", "STT_MODEL": "base"}),
            ("instant-base", {"VOICE_LATENCY_MODE": "instant", "STT_MODEL": "base"}),
            ("instant-tiny", {"VOICE_LATENCY_MODE": "instant", "STT_MODEL": "tiny"}),
        ]
        lines = [
            "Voice mode benchmark (config-only — no mic required)",
            f"  current: runtime={cfg.VOICE_RUNTIME_MODE or 'default'} "
            f"latency={cfg.VOICE_LATENCY_MODE or 'default'} model={cfg.STT_MODEL}",
            "",
        ]
        recommended = "stable-small"
        for label, overrides in modes:
            lines.append(
                f"  {label}: streaming={overrides.get('VOICE_LATENCY_MODE') == 'instant'} "
                f"multipass=off stack=off model={overrides.get('STT_MODEL', cfg.STT_MODEL)} "
                f"beam<=2 timeout<={cfg.STT_WAKE_FALLBACK_TIMEOUT_SECONDS:.0f}s"
            )
        lines.extend(
            [
                "",
                f"  recommended_profile: {recommended} (CPU-safe baseline)",
                "  phrase_set: open dashboard, show voice debug, open discord",
                "  note: run wake/word tests manually for real STT timings",
            ]
        )
        return result_success(Intent.BENCHMARK_VOICE_MODES, "\n".join(lines))


class FoundationHealthCheckAction(BaseAction):
    intent = Intent.FOUNDATION_HEALTH_CHECK.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        import config as cfg

        sections: list[tuple[str, str]] = []
        fixes: list[str] = []
        status = "PASS"

        try:
            from voice.runtime_mode import format_stable_mode_banner, is_stable_voice_mode

            voice_line = format_stable_mode_banner()
            if not is_stable_voice_mode():
                status = "DEGRADED"
                fixes.append("set VOICE_RUNTIME_MODE=stable for reliable voice")
        except Exception as exc:
            voice_line = f"voice: error ({exc})"
            status = "FAIL"

        sections.append(("voice", voice_line))
        sections.append(
            (
                "wake",
                f"enabled={cfg.WAKE_WORD_ENABLED} threshold={cfg.WAKE_WORD_THRESHOLD} "
                f"listen_s={cfg.WAKE_MAX_LISTEN_SECONDS}",
            )
        )
        sections.append(
            (
                "stt",
                f"engine={cfg.STT_ENGINE} model={cfg.STT_MODEL} device={cfg.STT_DEVICE_REQUEST} "
                f"streaming={cfg.STT_STREAMING_BUFFER_ENABLED} multipass={cfg.STT_MULTIPASS_ENABLED}",
            )
        )

        try:
            from voice.voice_debug_store import get_voice_debug_snapshot

            dbg = get_voice_debug_snapshot()
            sections.append(
                (
                    "transcript",
                    f"raw={dbg.last_raw_transcript[:80]!r} norm={dbg.last_normalized_transcript[:80]!r}",
                )
            )
        except Exception:
            sections.append(("transcript", "none recorded"))

        try:
            from voice.audio_status import format_audio_status, get_audio_status

            audio = get_audio_status()
            sections.append(("audio", format_audio_status()))
            if audio.last_success is False:
                status = "DEGRADED" if status == "PASS" else status
                fixes.append("run: test direct speech")
        except Exception as exc:
            sections.append(("audio", f"error ({exc})"))
            status = "FAIL"
            fixes.append("run: test direct speech")

        launcher = ShowLauncherStatusAction().execute(
            CommandRequest(raw_text="", intent=Intent.SHOW_LAUNCHER_STATUS, confidence=1.0)
        )
        sections.append(("launcher", launcher.summary.split("\n")[0]))

        screen = ShowScreenStatusAction().execute(
            CommandRequest(raw_text="", intent=Intent.SHOW_SCREEN_STATUS, confidence=1.0)
        )
        sections.append(("screen", screen.summary.split("\n")[0]))

        control = ShowControlStatusAction().execute(
            CommandRequest(raw_text="", intent=Intent.SHOW_CONTROL_STATUS, confidence=1.0)
        )
        sections.append(("control", control.summary.split("\n")[0]))

        try:
            from ui.overlay_app import get_overlay_controller

            snap = get_overlay_controller()._state.snapshot()
            sections.append(
                (
                    "overlay",
                    f"visible={snap.visible} phase={snap.phase.value}",
                )
            )
        except Exception as exc:
            sections.append(("overlay", f"error ({exc})"))

        try:
            from services.runtime_monitor import get_runtime_monitor

            mon = get_runtime_monitor().run_once()
            timeouts = len(mon.get("timeouts", []))
            sections.append(("runtime", f"timeouts={timeouts} lag_warn={mon.get('event_loop_lag', 0)}"))
            if timeouts > 0:
                status = "DEGRADED"
                fixes.append("run: show voice latency budget")
        except Exception as exc:
            sections.append(("runtime", f"error ({exc})"))

        lines = [f"Foundation health: {status}"]
        for name, body in sections:
            lines.append(f"  [{name}] {body}")
        if fixes:
            lines.append("Top fixes:")
            for i, fix in enumerate(fixes[:3], 1):
                lines.append(f"  {i}. {fix}")
        else:
            lines.append("Try next: Hey Jarvis → open dashboard")

        intent = Intent.FOUNDATION_HEALTH_CHECK
        if status == "FAIL":
            return result_failed(intent, "\n".join(lines))
        return result_success(intent, "\n".join(lines), data={"status": status})


class ShowRuntimeThreadsAction(BaseAction):
    intent = Intent.SHOW_RUNTIME_THREADS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from voice.runtime_threads import format_runtime_threads

        tray_app = None
        try:
            from ui.operator_console import get_operator_console

            oc = get_operator_console()
            if oc is not None:
                tray_app = oc._tray_app
        except Exception:
            pass
        return result_success(
            Intent.SHOW_RUNTIME_THREADS,
            format_runtime_threads(tray_app),
        )
