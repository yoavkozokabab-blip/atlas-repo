"""Windows system tray control for JARVIS."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING

from core.logger import setup_logger
from core.runtime_state import RuntimeState, get_runtime_state
from core.types import ActionStatus, Intent
from ui.notifications import notify

if TYPE_CHECKING:
    from core.app import JarvisApp

logger = setup_logger("jarvis.ui.tray")

# Tray menu → command text (must map to safe read-only / open intents only)
TRAY_MENU_COMMANDS: dict[str, str] = {
    "show_capabilities": "show capabilities",
    "show_dashboard_health": "show dashboard health",
    "open_trading_dashboard": "open trading dashboard",
    "open_chatgpt": "open chatgpt",
    "open_tradingview": "open tradingview",
    "open_youtube": "open youtube",
    "open_gmail": "open gmail",
    "show_last_errors": "show last errors",
    "describe_screen": "describe screen",
    "detect_screen_errors": "detect screen errors",
    "get_focused_app": "get focused app",
    "get_clipboard_summary": "get clipboard summary",
}

# Intents that must NOT appear on tray menu (confirm-required / destructive)
TRAY_FORBIDDEN_INTENTS = frozenset(
    {
        "run_live_daily_loop",
        "run_live_weekly_loop",
        "stop_trading_loop",
        "shutdown_jarvis",
        "enable_kill_switch",
        "disable_kill_switch",
        "focus_window",
        "copy_text_to_clipboard",
        "clear_clipboard",
        "minimize_window",
        "maximize_window",
    }
)


def _create_icon_image():
    from PIL import Image, ImageDraw

    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((4, 4, size - 4, size - 4), fill=(30, 120, 220, 255))
    draw.rectangle((22, 18, 42, 46), fill=(255, 255, 255, 255))
    return img


class JarvisTrayApp:
    """Background tray icon; all actions use handle_text_command()."""

    def __init__(
        self,
        app: "JarvisApp",
        *,
        runtime: RuntimeState | None = None,
        start_voice_thread: bool = False,
        start_wakeword_thread: bool = False,
        enable_watchdog: bool = True,
    ) -> None:
        self.app = app
        self.runtime = runtime or app.runtime
        self.runtime.tray_enabled = True
        self._icon = None
        self._voice_thread: threading.Thread | None = None
        self._wakeword_detector = None
        self._start_voice_thread = start_voice_thread
        self._start_wakeword_thread = start_wakeword_thread
        self._enable_watchdog = enable_watchdog

    def _run_command(self, command_text: str, *, title: str | None = None) -> None:
        """Route through the same pipeline as console/voice."""
        result = self.app.handle_text_command(
            command_text,
            input_mode="text",
            print_result=False,
        )
        self.runtime.record_result(result.summary, result.error)
        heading = title or result.intent.value
        msg = result.summary
        if result.status == ActionStatus.CONFIRMATION_REQUIRED:
            msg += "\n(Use console/voice and reply yes to confirm.)"
        try:
            notify(heading, msg, icon=self._icon)
        except Exception as exc:
            logger.debug("Tray notification failed: %s", exc)
            print(f"[{heading}] {msg}")

    def _toggle_speak(self, _icon=None, _item=None) -> None:
        self.runtime.set_speak(not self.runtime.speak_enabled)
        self.app.speak_enabled = self.runtime.speak_enabled
        self.app.tts.enabled = self.runtime.speak_enabled
        notify("JARVIS", f"Speak results: {'On' if self.runtime.speak_enabled else 'Off'}", icon=self._icon)

    def _toggle_overlay(self, _icon=None, _item=None) -> None:
        from ui.overlay_app import get_overlay_controller

        enabling = not self.runtime.overlay_enabled
        self.runtime.set_overlay(enabling)
        ctrl = get_overlay_controller()
        ctrl.set_enabled(enabling, runtime=self.runtime)
        notify(
            "JARVIS",
            f"Visual overlay: {'On' if enabling else 'Off'}",
            icon=self._icon,
        )

    def _show_overlay_test(self, _icon=None, _item=None) -> None:
        from ui.overlay_app import get_overlay_controller

        ctrl = get_overlay_controller()
        if not self.runtime.overlay_enabled:
            self.runtime.set_overlay(True)
            ctrl.set_enabled(True)
        ctrl.run_test_sequence()
        notify("JARVIS", "Overlay test sequence started (UI only).", icon=self._icon)

    def _toggle_wake_word(self, _icon=None, _item=None) -> None:
        enabling = not self.runtime.wake_word_enabled
        self.runtime.set_wake_word(enabling)
        if enabling:
            self._start_wakeword_background()
            notify(
                "JARVIS",
                "Wake word enabled — says activate listening only.",
                icon=self._icon,
            )
        else:
            self._stop_wakeword_background()
            notify("JARVIS", "Wake word disabled.", icon=self._icon)

    def _start_wakeword_background(self) -> None:
        if self._wakeword_detector is not None:
            return
        try:
            from voice.wakeword_loop import start_wakeword_loop

            self._wakeword_detector = start_wakeword_loop(self.app)
            thread = getattr(self._wakeword_detector, "_thread", None)
            if not (thread and thread.is_alive()):
                self.runtime.set_wake_word(False)
                print(
                    "[WARNING] Wake word disabled — model file not found. "
                    "Voice push-to-talk still available.",
                    flush=True,
                )
                self._wakeword_detector = None
                return
            print("Wake word listener started", flush=True)
            logger.info("Wake word listener started")
        except Exception as exc:
            self.runtime.increment_wake_error(str(exc))
            self.runtime.set_wake_word(False)
            logger.warning("Wake word start failed: %s", exc)
            print(f"[WARNING] Wake word failed to start: {exc}", flush=True)

    def _stop_wakeword_background(self) -> None:
        if self._wakeword_detector is None:
            return
        try:
            from voice.wakeword_loop import stop_wakeword_loop

            stop_wakeword_loop(self._wakeword_detector)
        except Exception as exc:
            logger.debug("Wake word stop: %s", exc)
        self._wakeword_detector = None

    def _show_wake_word_status(self, _icon=None, _item=None) -> None:
        from voice.wakeword_state import format_status

        msg = format_status(self.runtime)
        try:
            notify("Wake Word Status", msg, icon=self._icon)
        except Exception as exc:
            logger.debug("Wake status notify: %s", exc)
            print(msg)

    def _toggle_voice(self, _icon=None, _item=None) -> None:
        enabling = not self.runtime.voice_enabled
        self.runtime.set_voice(enabling)
        if enabling:
            self._start_voice_background()
            notify(
                "JARVIS",
                "Voice mode enabled (push-to-talk in background). "
                "Requires microphone.",
                icon=self._icon,
            )
        else:
            notify("JARVIS", "Voice mode disabled.", icon=self._icon)

    def _start_voice_background(self) -> None:
        if self._voice_thread and self._voice_thread.is_alive():
            return

        def _run() -> None:
            from voice.voice_loop import run_voice_loop

            try:
                run_voice_loop(self.app, hotkey=False, runtime=self.runtime)
            except Exception as exc:
                logger.warning("Voice loop ended: %s", exc)
                self.runtime.record_result("", str(exc))
            finally:
                expected_stop = not (
                    self.runtime.voice_enabled
                    and self.runtime.running
                    and self.app._running
                )
                if expected_stop:
                    try:
                        from core.thread_registry import get_thread_registry

                        get_thread_registry().deregister_if_thread(
                            "jarvis-voice-loop",
                            threading.current_thread(),
                        )
                    except Exception:
                        pass

        self._voice_thread = threading.Thread(target=_run, daemon=True, name="jarvis-voice")
        try:
            from core.thread_registry import get_thread_registry

            get_thread_registry().register("jarvis-voice-loop", self._voice_thread)
        except Exception:
            pass
        self._voice_thread.start()

    def restart_background_services(self, *, reason: str = "watchdog") -> list[dict[str, object]]:
        """Best-effort, in-process restart path for optional background services."""
        actions: list[dict[str, object]] = []

        if self.runtime.voice_enabled:
            alive = self._voice_thread is not None and self._voice_thread.is_alive()
            if not alive:
                try:
                    self._start_voice_background()
                    ok = self._voice_thread is not None and self._voice_thread.is_alive()
                    actions.append(
                        {
                            "component": "voice",
                            "action": "restart_thread",
                            "ok": ok,
                            "reason": reason,
                        }
                    )
                except Exception as exc:
                    actions.append(
                        {
                            "component": "voice",
                            "action": "restart_thread",
                            "ok": False,
                            "reason": reason,
                            "detail": str(exc),
                        }
                    )

        if self.runtime.wake_word_enabled:
            detector_thread = getattr(self._wakeword_detector, "_thread", None)
            alive = bool(detector_thread and detector_thread.is_alive())
            if not alive:
                try:
                    self._stop_wakeword_background()
                    self._start_wakeword_background()
                    detector_thread = getattr(self._wakeword_detector, "_thread", None)
                    ok = bool(detector_thread and detector_thread.is_alive())
                    actions.append(
                        {
                            "component": "wakeword",
                            "action": "restart_detector",
                            "ok": ok,
                            "reason": reason,
                        }
                    )
                except Exception as exc:
                    actions.append(
                        {
                            "component": "wakeword",
                            "action": "restart_detector",
                            "ok": False,
                            "reason": reason,
                            "detail": str(exc),
                        }
                    )

        if self.runtime.overlay_enabled:
            try:
                from ui.overlay_app import get_overlay_controller

                recovered = get_overlay_controller().recover_if_crashed(reason=reason)
                if recovered:
                    actions.append(
                        {
                            "component": "overlay",
                            "action": "restart_qt_thread",
                            "ok": True,
                            "reason": reason,
                        }
                    )
            except Exception as exc:
                actions.append(
                    {
                        "component": "overlay",
                        "action": "restart_qt_thread",
                        "ok": False,
                        "reason": reason,
                        "detail": str(exc),
                    }
                )

        return actions

    def _open_console(self, _icon=None, _item=None) -> None:
        root = str(Path(__file__).resolve().parent.parent)
        try:
            from ui.console_ui import open_console_window

            open_console_window(root)
            notify("JARVIS", "Opening console window…", icon=self._icon)
        except OSError as exc:
            notify("JARVIS", f"Could not open console: {exc}", icon=self._icon)

    def _exit(self, _icon=None, _item=None) -> None:
        self.stop()
        notify("JARVIS", "JARVIS tray exiting.", icon=self._icon)

    def _build_menu(self):
        import pystray

        speak_label = lambda _: (
            f"Speak Results: {'On' if self.runtime.speak_enabled else 'Off'}"
        )
        voice_label = lambda _: (
            f"Voice Mode: {'On' if self.runtime.voice_enabled else 'Off'}"
        )
        wake_label = lambda _: (
            f"Wake Word: {'On' if self.runtime.wake_word_enabled else 'Off'}"
        )
        overlay_label = lambda _: (
            f"Overlay: {'On' if self.runtime.overlay_enabled else 'Off'}"
        )

        return pystray.Menu(
            pystray.MenuItem("Open Console", self._open_console),
            pystray.MenuItem(voice_label, self._toggle_voice),
            pystray.MenuItem(wake_label, self._toggle_wake_word),
            pystray.MenuItem(speak_label, self._toggle_speak),
            pystray.MenuItem(overlay_label, self._toggle_overlay),
            pystray.MenuItem("Show Overlay Test", self._show_overlay_test),
            pystray.MenuItem("Show Wake Word Status", self._show_wake_word_status),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Show Capabilities",
                lambda: self._run_command(
                    TRAY_MENU_COMMANDS["show_capabilities"],
                    title="Capabilities",
                ),
            ),
            pystray.MenuItem(
                "Show Dashboard Health",
                lambda: self._run_command(
                    TRAY_MENU_COMMANDS["show_dashboard_health"],
                    title="Dashboard",
                ),
            ),
            pystray.MenuItem(
                "Open Trading Dashboard",
                lambda: self._run_command(
                    TRAY_MENU_COMMANDS["open_trading_dashboard"],
                    title="Dashboard",
                ),
            ),
            pystray.MenuItem(
                "Open ChatGPT",
                lambda: self._run_command(
                    TRAY_MENU_COMMANDS["open_chatgpt"],
                    title="ChatGPT",
                ),
            ),
            pystray.MenuItem(
                "Open TradingView",
                lambda: self._run_command(
                    TRAY_MENU_COMMANDS["open_tradingview"],
                    title="TradingView",
                ),
            ),
            pystray.MenuItem(
                "Open YouTube",
                lambda: self._run_command(
                    TRAY_MENU_COMMANDS["open_youtube"],
                    title="YouTube",
                ),
            ),
            pystray.MenuItem(
                "Open Gmail",
                lambda: self._run_command(
                    TRAY_MENU_COMMANDS["open_gmail"],
                    title="Gmail",
                ),
            ),
            pystray.MenuItem(
                "Show Last Errors",
                lambda: self._run_command(
                    TRAY_MENU_COMMANDS["show_last_errors"],
                    title="Errors",
                ),
            ),
            pystray.MenuItem(
                "Describe Screen",
                lambda: self._run_command(
                    TRAY_MENU_COMMANDS["describe_screen"],
                    title="Screen",
                ),
            ),
            pystray.MenuItem(
                "Detect Screen Errors",
                lambda: self._run_command(
                    TRAY_MENU_COMMANDS["detect_screen_errors"],
                    title="Screen errors",
                ),
            ),
            pystray.MenuItem(
                "Focused App",
                lambda: self._run_command(
                    TRAY_MENU_COMMANDS["get_focused_app"],
                    title="Focused app",
                ),
            ),
            pystray.MenuItem(
                "Clipboard Summary",
                lambda: self._run_command(
                    TRAY_MENU_COMMANDS["get_clipboard_summary"],
                    title="Clipboard",
                ),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit JARVIS", self._exit),
        )

    def start(self, *, debug_startup: bool = False) -> None:
        from core.startup import StartupError, append_startup_log, print_debug_thread_status

        try:
            import pystray
        except ImportError as exc:
            raise StartupError(
                f"pystray is not installed: {exc}. Run: pip install pystray Pillow"
            ) from exc

        try:
            image = _create_icon_image()
            self._icon = pystray.Icon(
                "local_jarvis",
                image,
                "JARVIS",
                menu=self._build_menu(),
            )
        except Exception as exc:
            raise StartupError(f"Could not create tray icon: {exc}") from exc

        if self._start_voice_thread or self.runtime.voice_enabled:
            self.runtime.set_voice(True)
            self._start_voice_background()

        if self._start_wakeword_thread or self.runtime.wake_word_enabled:
            self.runtime.set_wake_word(True)
            self._start_wakeword_background()

        self._watchdog = None
        if self._enable_watchdog:
            try:
                from services.watchdog_runtime import (
                    attach_tray_to_watchdog,
                    ensure_process_watchdog,
                    get_process_watchdog,
                    is_watchdog_running,
                )

                self.runtime.tray_enabled = True
                if is_watchdog_running():
                    attach_tray_to_watchdog(self)
                    self._watchdog = get_process_watchdog()
                    append_startup_log("watchdog reattached for tray")
                else:
                    self._watchdog = ensure_process_watchdog(
                        runtime=self.runtime,
                        tray_app=self,
                    )
                    append_startup_log("watchdog started")
            except Exception as exc:
                logger.warning("Watchdog failed to start (tray continues): %s", exc)
                print(f"[WARNING] Watchdog failed: {exc}", flush=True)
                append_startup_log("watchdog failed", exc=exc)
                self._watchdog = None

        try:
            from ui.overlay_app import start_overlay_for_tray

            start_overlay_for_tray(self.app)
        except Exception as exc:
            logger.debug("Overlay tray init: %s", exc)

        append_startup_log("tray icon run() starting")
        logger.info("Tray icon run() — blocking main thread")
        print("Tray started. JARVIS is running in background.", flush=True)
        print("Look for the tray icon near the clock. Right-click for menu.", flush=True)

        try:
            from ui.operator_console import start_operator_console

            start_operator_console(self.app, tray_app=self, background_mode=True)
        except Exception as exc:
            logger.debug("Operator console: %s", exc)

        if debug_startup:
            print_debug_thread_status(self)

        print("Entering tray icon.run() — blocks until Exit from tray menu.", flush=True)
        try:
            try:
                self._icon.run()
            except Exception as exc:
                append_startup_log("tray run() failed", exc=exc)
                raise StartupError(f"Tray exited with error: {exc}") from exc
            if self.runtime.running and self.app._running:
                print(
                    "[WARNING] icon.run() returned while still running — entering keepalive loop.",
                    flush=True,
                )
                append_startup_log("tray keepalive: icon.run() returned early")
                import time

                while self.runtime.running and self.app._running:
                    time.sleep(1.0)
        finally:
            if hasattr(self, "_watchdog") and self._watchdog is not None:
                self._watchdog.stop()
            append_startup_log("tray run() ended")

    def stop(self) -> None:
        try:
            from memory.session_memory import persist_session_summary

            persist_session_summary()
        except Exception as exc:
            logger.debug("Session summary on stop: %s", exc)
        try:
            from ui.overlay_app import reset_overlay_controller

            reset_overlay_controller()
        except Exception as exc:
            logger.debug("Overlay stop: %s", exc)
        if hasattr(self, "_watchdog"):
            try:
                self._watchdog.stop()
            except Exception as exc:
                logger.debug("Watchdog stop: %s", exc)
        self.runtime.stop()
        self.app._running = False
        self.runtime.set_voice(False)
        self.runtime.set_wake_word(False)
        self._stop_wakeword_background()
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception as exc:
                logger.debug("Tray stop: %s", exc)
        self._icon = None
