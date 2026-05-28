"""
JARVIS visual overlay (PySide6) — display-only, reflects runtime state.

Never executes commands; wake/voice flows still use app.handle_text_command().
"""

from __future__ import annotations

import queue
import threading
import weakref
import time
from typing import TYPE_CHECKING, Callable

from config import (
    OVERLAY_ALWAYS_ON_TOP,
    OVERLAY_AUTO_HIDE_SECONDS,
    OVERLAY_ENABLED,
    OVERLAY_FADE_MS,
    OVERLAY_HEIGHT_RATIO,
    OVERLAY_OPACITY,
    OVERLAY_POSITION,
    OVERLAY_QT_ENABLED,
    OVERLAY_SHOW_AUDIO_PULSE,
    OVERLAY_SHOW_COMMAND_HISTORY,
    OVERLAY_SHOW_HUD_LABELS,
    OVERLAY_SHOW_RESULT,
    OVERLAY_SHOW_ROTATING_RINGS,
    OVERLAY_SHOW_SYSTEM_PANELS,
    OVERLAY_SHOW_TRANSCRIPT,
    OVERLAY_SHOW_WAVEFORM,
    OVERLAY_STYLE,
    OVERLAY_TEST_DISPLAY_SECONDS,
    OVERLAY_WIDTH_RATIO,
    OVERLAY_STARTUP_WAIT_SECONDS,
    OVERLAY_READY_VISIBLE_SECONDS,
    OVERLAY_RECOVERY_BACKOFF_SECONDS,
    OVERLAY_STAY_OPEN_ON_ERROR,
    OVERLAY_STAY_OPEN_ON_SUGGESTIONS,
    OVERLAY_UPDATE_QUEUE_SIZE,
)
from ui.overlay_theme import get_overlay_theme, resolve_overlay_theme_name
from core.logger import setup_logger
from ui.overlay_state import OverlayPhase, OverlayState

if TYPE_CHECKING:
    from core.app import JarvisApp

logger = setup_logger("jarvis.ui.overlay")

_controller: OverlayController | None = None
_overlay_instances: weakref.WeakSet[OverlayController] = weakref.WeakSet()


def _qt_object_alive(obj: object | None) -> bool:
    if obj is None:
        return False
    try:
        from shiboken6 import isValid

        return bool(isValid(obj))
    except Exception:
        try:
            obj.objectName()  # type: ignore[attr-defined]
            return True
        except RuntimeError:
            return False


def _stop_qtimer_safe(timer: object | None) -> None:
    """Stop/delete a QTimer only on its owning Qt thread."""
    if timer is None or not _qt_object_alive(timer):
        return
    try:
        from PySide6.QtCore import QMetaObject, Qt, QThread

        owner_thread = timer.thread()  # type: ignore[attr-defined]
        if owner_thread is not None and QThread.currentThread() != owner_thread:
            QMetaObject.invokeMethod(timer, "stop", Qt.ConnectionType.QueuedConnection)
            QMetaObject.invokeMethod(timer, "deleteLater", Qt.ConnectionType.QueuedConnection)
            return
        timer.stop()  # type: ignore[attr-defined]
        timer.deleteLater()  # type: ignore[attr-defined]
    except RuntimeError:
        pass
    except Exception as exc:
        logger.debug("qt timer stop skipped: %s", exc)


def _runtime_overlay_enabled() -> bool:
    try:
        from core.runtime_state import get_runtime_state

        return get_runtime_state().overlay_enabled
    except Exception:
        return False


class OverlayController:
    """Bridge voice/wake events → overlay state → Qt window (UI thread)."""

    def __init__(self) -> None:
        self._state = OverlayState()
        self._enabled = OVERLAY_ENABLED
        self._qt_thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._stop_qt = threading.Event()
        self._window = None
        self._app = None
        self._hide_timer: threading.Thread | None = None
        self._qt_start_count = 0
        self._qt_crash_count = 0
        self._last_qt_exception: str | None = None
        self._last_qt_exit_monotonic: float | None = None
        self._last_recovery_monotonic = 0.0
        self._update_queue: queue.Queue[Callable[[], None]] = queue.Queue(
            maxsize=max(8, OVERLAY_UPDATE_QUEUE_SIZE)
        )
        self._queue_thread = threading.Thread(
            target=self._overlay_queue_worker,
            name="jarvis-overlay-queue",
            daemon=True,
        )
        self._queue_thread.start()
        _overlay_instances.add(self)

    def is_enabled(self) -> bool:
        return self._enabled

    def is_active(self) -> bool:
        return self._enabled and _runtime_overlay_enabled()

    def health_snapshot(self) -> dict[str, object]:
        thread_alive = bool(self._qt_thread and self._qt_thread.is_alive())
        return {
            "enabled": self._enabled,
            "runtime_enabled": _runtime_overlay_enabled(),
            "qt_thread_alive": thread_alive,
            "qt_start_count": self._qt_start_count,
            "qt_crash_count": self._qt_crash_count,
            "last_qt_exception": self._last_qt_exception,
            "queue_size": self._update_queue.qsize(),
        }

    def recover_if_crashed(self, *, reason: str = "overlay_health_check") -> bool:
        if not self._enabled or not _runtime_overlay_enabled() or not OVERLAY_QT_ENABLED:
            return False
        if self._qt_thread and self._qt_thread.is_alive():
            return False
        now = time.monotonic()
        if now - self._last_recovery_monotonic < OVERLAY_RECOVERY_BACKOFF_SECONDS:
            return False
        self._last_recovery_monotonic = now
        self._window = None
        self._app = None
        self._stop_qt.clear()
        self._ready.clear()
        try:
            from services.runtime_monitor import get_runtime_monitor

            get_runtime_monitor().record_recovery(
                "overlay",
                "restart_qt_thread",
                reason=reason,
                ok=True,
                detail=self._last_qt_exception or "",
            )
        except Exception:
            pass
        self.ensure_started()
        return bool(self._qt_thread and self._qt_thread.is_alive())

    def set_enabled(self, enabled: bool, *, runtime: object | None = None) -> None:
        self._enabled = enabled
        try:
            if runtime is not None and hasattr(runtime, "set_overlay"):
                runtime.set_overlay(enabled)
            else:
                from core.runtime_state import get_runtime_state

                get_runtime_state().set_overlay(enabled)
        except Exception:
            pass
        if enabled:
            self.ensure_started()
        elif not self._state.snapshot().visible:
            self._state.hide()

    def ensure_started(self) -> None:
        if not self._enabled:
            return
        if not OVERLAY_QT_ENABLED:
            self._ready.set()
            return
        if self._qt_thread and self._qt_thread.is_alive():
            return
        if self._qt_thread is not None and self._ready.is_set():
            self.recover_if_crashed(reason="ensure_started_dead_thread")
            if self._qt_thread and self._qt_thread.is_alive():
                return
        self._stop_qt.clear()
        self._ready.clear()
        self._qt_thread = threading.Thread(
            target=self._run_qt_loop,
            name="jarvis-overlay-qt",
            daemon=True,
        )
        self._qt_start_count += 1
        self._qt_thread.start()
        if not self._ready.wait(timeout=OVERLAY_STARTUP_WAIT_SECONDS):
            logger.debug("Overlay Qt thread not ready within %.1fs (continuing)", OVERLAY_STARTUP_WAIT_SECONDS)

    def _overlay_queue_worker(self) -> None:
        while not self._stop_qt.is_set():
            try:
                fn = self._update_queue.get(timeout=0.1)
            except queue.Empty:
                try:
                    from core.test_runtime import is_test_mode

                    if not is_test_mode():
                        from services.runtime_monitor import get_runtime_monitor

                        get_runtime_monitor().heartbeat("overlay_queue")
                except Exception:
                    pass
                continue
            try:
                try:
                    from services.runtime_monitor import get_runtime_monitor

                    get_runtime_monitor().heartbeat("overlay_queue")
                except Exception:
                    pass
                fn()
            except Exception as exc:
                logger.debug("Overlay update failed: %s", exc)
            finally:
                self._update_queue.task_done()

    def _enqueue_update(self, fn: Callable[[], None]) -> None:
        if not OVERLAY_QT_ENABLED:
            try:
                self._run_update(fn)
            except Exception as exc:
                logger.debug("Overlay sync update failed: %s", exc)
            return
        try:
            self._update_queue.put_nowait(fn)
        except queue.Full:
            try:
                self._update_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._update_queue.put_nowait(fn)
            except queue.Full:
                logger.debug("Overlay update dropped (queue full)")

    def _drain_update_queue(self) -> None:
        while True:
            try:
                self._update_queue.get_nowait()
                self._update_queue.task_done()
            except queue.Empty:
                break

    def stop(self, *, join_timeout: float = 2.0) -> None:
        self._stop_qt.set()
        self._state.hide()
        self._drain_update_queue()
        if OVERLAY_QT_ENABLED and self._window is not None:
            try:
                from PySide6.QtCore import QMetaObject, Qt
                from PySide6.QtWidgets import QApplication

                app = QApplication.instance()
                if app is not None:
                    QMetaObject.invokeMethod(
                        app,
                        "quit",
                        Qt.ConnectionType.QueuedConnection,
                    )
            except Exception as exc:
                logger.debug("Overlay quit: %s", exc)
        self._join_qt_thread(timeout=join_timeout)
        if self._queue_thread and self._queue_thread.is_alive():
            self._queue_thread.join(timeout=join_timeout)
        self._window = None
        self._app = None

    def _join_qt_thread(self, *, timeout: float = 2.0) -> None:
        thread = self._qt_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)
        self._qt_thread = None

    def _apply_if_active(self, fn) -> None:
        if not self.is_active():
            return
        self.recover_if_crashed(reason="overlay_update")
        self._enqueue_update(lambda: self._run_update(fn))

    def _run_update(self, fn) -> None:
        if not self.is_active():
            return
        self.recover_if_crashed(reason="overlay_run_update")
        self.ensure_started()
        fn()

    def on_wake_detected(self) -> None:
        def _go() -> None:
            self._state.push_timeline_event("wake")
            self._state.set_wake_detected()

        self._apply_if_active(_go)

    def on_listening(self) -> None:
        self.on_recording()

    def on_recording(self, *, sub_status: str = "") -> None:
        def _go() -> None:
            self._state.set_recording(sub_status=sub_status)

        self._apply_if_active(_go)

    def on_transcribing(self, *, sub_status: str = "") -> None:
        def _go() -> None:
            self._state.set_transcribing(sub_status=sub_status)

        self._apply_if_active(_go)

    def on_transcript(self, text: str) -> None:
        def _go() -> None:
            self._state.set_transcript(text, show=OVERLAY_SHOW_TRANSCRIPT)

        self._apply_if_active(_go)

    def on_heard_transcript(self, raw: str, normalized: str) -> None:
        def _go() -> None:
            raw_s = (raw or "").strip()
            norm_s = (normalized or "").strip()
            display = f"I heard:\nRAW: {raw_s[:160]}\nNORMALIZED: {norm_s[:160]}"
            self._state.set_transcript(display, show=OVERLAY_SHOW_TRANSCRIPT)

        self._apply_if_active(_go)

    def on_thinking(self, *, status_hint: str = "") -> None:
        self.on_executing(status_hint=status_hint)

    def on_executing(
        self,
        *,
        intent_label: str = "",
        status_hint: str = "",
        sub_status: str = "",
    ) -> None:
        def _go() -> None:
            label = intent_label or status_hint or "command"
            self._state.push_timeline_event(f"cmd: {label}")
            self._state.set_executing(
                intent_label=intent_label,
                status_hint=status_hint,
                sub_status=sub_status,
            )

        self._apply_if_active(_go)

    def on_awaiting_confirmation(
        self,
        *,
        intent_label: str = "",
        guidance: str = "",
    ) -> None:
        def _go() -> None:
            self._state.push_timeline_event("confirm")
            self._state.set_awaiting_confirmation(
                intent_label=intent_label,
                guidance=guidance,
            )

        self._apply_if_active(_go)

    def on_workflow_hint(self, hint: str) -> None:
        def _go() -> None:
            self._state.set_workflow_hint(hint)

        self._apply_if_active(_go)

    def on_result(
        self,
        summary: str,
        *,
        speaking: bool = False,
        suggestions: list[str] | tuple[str, ...] | None = None,
        intent_label: str = "",
    ) -> None:
        def _go() -> None:
            self._state.push_timeline_event("result")
            self._state.set_result(
                summary,
                show=OVERLAY_SHOW_RESULT,
                speaking=speaking,
                suggestions=suggestions,
                intent_label=intent_label,
            )
            if speaking:
                try:
                    from ui.overlay_voice_status import notify_overlay_voice_output_status

                    notify_overlay_voice_output_status("STREAMING RESPONSE")
                except Exception:
                    pass
            else:
                self._schedule_auto_hide()

        self._apply_if_active(_go)

    def on_tts_started(self) -> None:
        def _go() -> None:
            snap = self._state.snapshot()
            if snap.phase == OverlayPhase.SPEAKING:
                return
            self._state.set_speaking()

        self._apply_if_active(_go)

    def on_tts_finished(self) -> None:
        def _go() -> None:
            snap = self._state.snapshot()
            if snap.phase == OverlayPhase.SPEAKING:
                self._state.set_complete(
                    summary=snap.result_summary,
                    show_result=False,
                    suggestions=snap.suggestions,
                )
            self._schedule_auto_hide()

        self._apply_if_active(_go)

    def on_ready(self, *, quiet: bool = False) -> None:
        def _go() -> None:
            self._state.set_ready(quiet=quiet)
            if not quiet:
                self._schedule_auto_hide(ready_only=True)

        if quiet:
            try:
                self._run_update(lambda: self._state.set_ready(quiet=True))
            except Exception as exc:
                logger.debug("overlay ready (quiet): %s", exc)
        else:
            self._apply_if_active(_go)

    def on_done(self, *, speaking: bool = False) -> None:
        def _go() -> None:
            if speaking:
                self._state.set_speaking()
            else:
                self._schedule_auto_hide()

        self._apply_if_active(_go)

    def on_error(self, message: str) -> None:
        def _go() -> None:
            self._state.push_timeline_event("error")
            self._state.set_error(message)
            self._schedule_auto_hide()

        self._apply_if_active(_go)

    def on_idle(self) -> None:
        if not self._enabled:
            return
        self._state.hide()

    def run_test_sequence(self) -> None:
        """Tray test — cycles full HUD states for ~5s without executing commands."""
        if not self._enabled:
            self.set_enabled(True)
        from core.runtime_state import get_runtime_state

        get_runtime_state().set_overlay(True)
        try:
            from ui.overlay_hud import fetch_hud_system_metrics

            self._state.set_system_metrics(fetch_hud_system_metrics())
        except Exception:
            pass

        hold = max(3.0, float(OVERLAY_TEST_DISPLAY_SECONDS))

        def _demo() -> None:
            self.on_wake_detected()
            time.sleep(0.45)
            self.on_listening()
            time.sleep(0.45)
            self.on_transcribing()
            time.sleep(0.4)
            self.on_transcript("show dashboard health")
            time.sleep(0.35)
            self.on_thinking()
            time.sleep(0.5)
            self.on_result("Dashboard health: OK (test preview only).", speaking=False)
            self.on_done(speaking=False)
            time.sleep(hold)
            self._state.hide()

        threading.Thread(target=_demo, name="jarvis-overlay-test", daemon=True).start()

    def _hide_or_quiet(self) -> None:
        try:
            from ui.quiet_mode import hide_overlay_after_auto_hide, is_quiet_mode

            if is_quiet_mode():
                self._state.set_ready(quiet=True)
                hide_overlay_after_auto_hide()
            else:
                self._state.hide()
        except Exception:
            self._state.hide()

    def _schedule_auto_hide(self, *, ready_only: bool = False) -> None:
        snap = self._state.snapshot()
        if ready_only or snap.phase == OverlayPhase.READY:
            delay = max(1.0, float(OVERLAY_READY_VISIBLE_SECONDS))
        else:
            delay = max(1.0, float(OVERLAY_AUTO_HIDE_SECONDS))
            if snap.phase == OverlayPhase.ERROR and OVERLAY_STAY_OPEN_ON_ERROR:
                delay = max(delay, float(OVERLAY_AUTO_HIDE_SECONDS) + float(OVERLAY_READY_VISIBLE_SECONDS))
            if snap.suggestions and OVERLAY_STAY_OPEN_ON_SUGGESTIONS:
                delay = max(delay, float(OVERLAY_AUTO_HIDE_SECONDS) + float(OVERLAY_READY_VISIBLE_SECONDS))
        deadline = time.monotonic() + delay
        self._state.schedule_hide_at(deadline)

        def _hide_later() -> None:
            remaining = deadline - time.monotonic()
            if remaining > 0:
                time.sleep(remaining)
            snap = self._state.snapshot()
            if snap.hide_after_monotonic != deadline:
                return
            if snap.phase in {OverlayPhase.COMPLETE, OverlayPhase.SPEAKING, OverlayPhase.ERROR}:
                self._state.set_ready()
                self._schedule_auto_hide(ready_only=True)
                return
            if snap.phase == OverlayPhase.READY:
                self._hide_or_quiet()

        if self._hide_timer and self._hide_timer.is_alive():
            pass
        self._hide_timer = threading.Thread(
            target=_hide_later,
            name="jarvis-overlay-hide",
            daemon=True,
        )
        self._hide_timer.start()

    def _run_qt_loop(self) -> None:
        try:
            from PySide6.QtWidgets import QApplication

            import sys

            qt_app = QApplication.instance()
            if qt_app is None:
                qt_app = QApplication(sys.argv)

            self._app = qt_app
            theme_name = resolve_overlay_theme_name()
            logger.info("Overlay Qt starting (style=%s)", theme_name)
            self._window = JarvisOverlayWindow(
                self._state,
                opacity=OVERLAY_OPACITY,
                always_on_top=OVERLAY_ALWAYS_ON_TOP,
                theme_name=theme_name,
            )
            self._ready.set()
            metrics_tick = 0
            while not self._stop_qt.is_set():
                snap = self._state.snapshot()
                if snap.hide_after_monotonic and time.monotonic() >= snap.hide_after_monotonic:
                    if snap.phase in {OverlayPhase.COMPLETE, OverlayPhase.SPEAKING, OverlayPhase.ERROR}:
                        self._state.set_ready()
                        self._schedule_auto_hide(ready_only=True)
                    elif snap.phase == OverlayPhase.READY:
                        self._hide_or_quiet()
                metrics_tick += 1
                if metrics_tick % 150 == 0:
                    try:
                        from ui.overlay_hud import fetch_hud_system_metrics

                        self._state.set_system_metrics(fetch_hud_system_metrics())
                        self._state.refresh_operating_context()
                    except Exception:
                        pass
                qt_app.processEvents()
                time.sleep(0.02)
            if self._window is not None:
                self._window.shutdown()
                self._window = None
        except ImportError as exc:
            logger.warning("PySide6 not available for overlay: %s", exc)
            self._last_qt_exception = f"ImportError: {exc}"
            self._ready.set()
        except Exception as exc:
            logger.warning("Overlay Qt loop failed: %s", exc)
            self._qt_crash_count += 1
            self._last_qt_exception = f"{type(exc).__name__}: {exc}"
            try:
                from services.runtime_monitor import get_runtime_monitor

                get_runtime_monitor().record_recovery(
                    "overlay",
                    "qt_loop_crashed",
                    reason=str(exc),
                    ok=False,
                )
            except Exception:
                pass
            self._ready.set()
        finally:
            self._last_qt_exit_monotonic = time.monotonic()


def _make_pulse_widget(parent, theme):
    import math

    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QColor, QPainter, QPen
    from PySide6.QtWidgets import QWidget

    class _Pulse(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._theme = theme
            self._pulse = 0.0
            self._active = False
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._tick)
            self._timer.start(40)
            self.setFixedSize(theme.circle_size, theme.circle_size)
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        def set_active(self, active: bool) -> None:
            self._active = active
            self.update()

        def _tick(self) -> None:
            if self._active:
                self._pulse = (self._pulse + 0.14) % (2 * math.pi)
            else:
                self._pulse *= 0.92
            self.update()

        def shutdown(self) -> None:
            _stop_qtimer_safe(getattr(self, "_timer", None))
            self._timer = None

        def closeEvent(self, event) -> None:
            self.shutdown()
            super().closeEvent(event)

        def paintEvent(self, _event) -> None:
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            cx, cy = self.width() // 2, self.height() // 2
            base = 46
            pulse = 0.5 + 0.5 * math.sin(self._pulse)
            ring = base + int(10 * pulse) if self._active else base

            glow = QColor(self._theme.glow_outer)
            glow.setAlpha(60)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(glow)
            p.drawEllipse(cx - ring - 14, cy - ring - 14, (ring + 14) * 2, (ring + 14) * 2)

            pen = QPen(QColor(self._theme.accent))
            pen.setWidth(self._theme.ring_width)
            p.setPen(pen)
            inner = QColor(0, 30, 55, 90)
            p.setBrush(inner)
            p.drawEllipse(cx - ring, cy - ring, ring * 2, ring * 2)

            pen.setColor(QColor(self._theme.glow))
            pen.setWidth(1)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(cx - ring - 6, cy - ring - 6, (ring + 6) * 2, (ring + 6) * 2)

            if self._active:
                arc_pen = QPen(QColor(self._theme.glow))
                arc_pen.setWidth(2)
                p.setPen(arc_pen)
                span = int(220 * pulse)
                p.drawArc(
                    cx - ring,
                    cy - ring,
                    ring * 2,
                    ring * 2,
                    int(self._pulse * 180 / math.pi * 16) % 5760,
                    span * 16,
                )
            p.end()

    return _Pulse(parent)


class JarvisOverlayWindow:
    """Frameless always-on-top overlay; polls OverlayState."""

    def __init__(
        self,
        state: OverlayState,
        *,
        opacity: float = 0.88,
        always_on_top: bool = True,
        theme_name: str | None = None,
    ) -> None:
        from PySide6.QtCore import Qt, QTimer
        from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

        from ui.overlay_hud import build_premium_hud_widget
        from ui.overlay_theme import window_stylesheet

        self._state = state
        self._premium = False
        self._full_screen = False
        theme = get_overlay_theme(theme_name)
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        if always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint

        if theme.premium:
            self._premium = True
            self._full_screen = theme.full_screen
            self._root = build_premium_hud_widget(
                state,
                theme,
                show_audio_pulse=OVERLAY_SHOW_AUDIO_PULSE,
                show_rotating_rings=OVERLAY_SHOW_ROTATING_RINGS,
                fade_ms=OVERLAY_FADE_MS,
                show_waveform=OVERLAY_SHOW_WAVEFORM,
                show_system_panels=OVERLAY_SHOW_SYSTEM_PANELS,
                show_command_history=OVERLAY_SHOW_COMMAND_HISTORY,
                show_hud_labels=OVERLAY_SHOW_HUD_LABELS,
            )
            self._root.setWindowFlags(flags)
            self._root.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self._root.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
            self._root.setWindowOpacity(max(0.3, min(1.0, opacity)))
            self._circle = None
        else:
            self._root = QWidget()
            self._root.setObjectName("jarvisOverlayRoot")
            self._root.setWindowFlags(flags)
            self._root.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self._root.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
            self._root.setWindowOpacity(max(0.3, min(1.0, opacity)))
            self._root.setFixedSize(theme.window_width, theme.window_height)
            self._root.setStyleSheet(window_stylesheet(theme, opacity))
            self._root.setFocusPolicy(Qt.FocusPolicy.NoFocus)

            layout = QVBoxLayout(self._root)
            layout.setContentsMargins(18, 16, 18, 14)
            layout.setSpacing(8)

            self._circle = _make_pulse_widget(self._root, theme)
            layout.addWidget(self._circle, alignment=Qt.AlignmentFlag.AlignHCenter)

            self._status = QLabel("JARVIS")
            self._status.setObjectName("statusLabel")
            self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._status.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            layout.addWidget(self._status)

            self._transcript = QLabel("")
            self._transcript.setObjectName("transcriptLabel")
            self._transcript.setWordWrap(True)
            self._transcript.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._transcript.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            layout.addWidget(self._transcript)

            self._result = QLabel("")
            self._result.setObjectName("resultLabel")
            self._result.setWordWrap(True)
            self._result.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._result.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            layout.addWidget(self._result)

            self._error = QLabel("")
            self._error.setObjectName("errorLabel")
            self._error.setWordWrap(True)
            self._error.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._error.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            layout.addWidget(self._error)

        self._last_version = -1
        self._closed = False
        self._timer = QTimer(self._root)
        self._timer.timeout.connect(self._sync_from_state)
        self._timer.start(50)

        self._position_overlay(theme)
        self._root.hide()

    def _position_overlay(self, theme) -> None:
        from PySide6.QtWidgets import QApplication

        screen = QApplication.primaryScreen()
        if screen is None:
            self._root.move(80, 80)
            return
        geo = screen.availableGeometry()
        if getattr(self, "_full_screen", False):
            w_ratio = max(0.5, min(1.0, OVERLAY_WIDTH_RATIO))
            h_ratio = max(0.5, min(1.0, OVERLAY_HEIGHT_RATIO))
            width = int(geo.width() * w_ratio)
            height = int(geo.height() * h_ratio)
            self._root.resize(width, height)
            if OVERLAY_POSITION == "center":
                x = geo.left() + (geo.width() - width) // 2
                y = geo.top() + (geo.height() - height) // 2
            else:
                x = geo.left() + (geo.width() - width) // 2
                y = geo.top() + (geo.height() - height) // 2
            self._root.move(max(geo.left(), x), max(geo.top(), y))
            return
        if not self._premium:
            self._root.setFixedSize(theme.window_width, theme.window_height)
        x = geo.center().x() - self._root.width() // 2
        y = geo.bottom() - self._root.height() - 56
        self._root.move(max(geo.left(), x), max(geo.top(), y))

    def _sync_from_state(self) -> None:
        if getattr(self, "_closed", False):
            return
        if not _qt_object_alive(self._root):
            return
        snap = self._state.snapshot()
        if self._premium:
            fade = float(getattr(self._root, "_fade", 0.0))
            try:
                from ui.quiet_mode import is_overlay_window_visible

                window_visible = is_overlay_window_visible()
            except Exception:
                window_visible = True
            if (snap.visible or fade > 0.01) and window_visible:
                if not self._root.isVisible():
                    self._root.show()
                    self._root.raise_()
            elif fade <= 0.01 or not window_visible:
                self._root.hide()
            return

        if snap.version == self._last_version:
            return
        self._last_version = snap.version

        if not self._premium:
            self._status.setText(snap.status_text or "JARVIS")
            self._transcript.setText(snap.transcript)
            self._transcript.setVisible(bool(snap.transcript))
            self._result.setText(snap.result_summary)
            self._result.setVisible(bool(snap.result_summary))
            self._error.setText(snap.error_message)
            self._error.setVisible(bool(snap.error_message))
            if self._circle is not None:
                self._circle.set_active(snap.pulse_active)

        try:
            from ui.quiet_mode import is_overlay_window_visible

            window_visible = is_overlay_window_visible()
        except Exception:
            window_visible = True
        if snap.visible and window_visible:
            if not self._root.isVisible():
                self._root.show()
                self._root.raise_()
        elif not self._premium or not window_visible:
            self._root.hide()

    def shutdown(self) -> None:
        if getattr(self, "_closed", False):
            return
        self._closed = True
        _stop_qtimer_safe(getattr(self, "_timer", None))
        self._timer = None
        circle = getattr(self, "_circle", None)
        if circle is not None and hasattr(circle, "shutdown") and _qt_object_alive(circle):
            try:
                circle.shutdown()
            except RuntimeError as exc:
                logger.debug("overlay circle shutdown: %s", exc)
        root = getattr(self, "_root", None)
        if _qt_object_alive(root):
            _stop_qtimer_safe(getattr(root, "_timer", None))
            try:
                root._timer = None  # type: ignore[attr-defined]
            except Exception:
                pass
            try:
                root.close()
            except RuntimeError as exc:
                logger.debug("overlay root close: %s", exc)

    def close(self) -> None:
        self.shutdown()


def get_overlay_controller() -> OverlayController:
    global _controller
    if _controller is None:
        _controller = OverlayController()
    return _controller


def stop_all_overlay_controllers(*, join_timeout: float = 1.0) -> None:
    """Stop overlay instances created directly in tests (not only the singleton)."""
    for ctrl in list(_overlay_instances):
        try:
            ctrl.stop(join_timeout=join_timeout)
        except Exception as exc:
            logger.debug("overlay stop: %s", exc)


def reset_overlay_controller() -> None:
    global _controller
    stop_all_overlay_controllers()
    if _controller is not None:
        _controller.stop()
        _controller._join_qt_thread()
    _controller = None


def overlay_is_active() -> bool:
    return get_overlay_controller().is_active()


def notify_overlay_wake_detected() -> None:
    try:
        from ui.quiet_mode import reveal_overlay_for_wake

        reveal_overlay_for_wake()
        get_overlay_controller().on_wake_detected()
    except Exception as exc:
        logger.debug("overlay wake: %s", exc)


def notify_overlay_listening() -> None:
    notify_overlay_recording()


def notify_overlay_recording(*, sub_status: str = "") -> None:
    try:
        get_overlay_controller().on_recording(sub_status=sub_status)
    except Exception as exc:
        logger.debug("overlay recording: %s", exc)


def notify_overlay_transcribing(*, sub_status: str = "") -> None:
    try:
        get_overlay_controller().on_transcribing(sub_status=sub_status)
    except Exception as exc:
        logger.debug("overlay transcribe: %s", exc)


def notify_overlay_transcript(text: str) -> None:
    try:
        get_overlay_controller().on_transcript(text)
    except Exception as exc:
        logger.debug("overlay transcript: %s", exc)


def notify_overlay_partial_transcript(text: str) -> None:
    """Streaming partial STT (Phase 42)."""
    try:
        snippet = (text or "").strip()[:120]
        if snippet:
            get_overlay_controller().on_transcribing(sub_status=f"… {snippet}")
    except Exception as exc:
        logger.debug("overlay partial transcript: %s", exc)


def notify_overlay_conversation_stream(snap: object) -> None:
    """Phase 42.7 — conversation stream snapshot on HUD."""
    try:
        intent = str(getattr(snap, "primary_intent", "") or "")
        conf = float(getattr(snap, "confidence", 0.0) or 0.0)
        phase = str(getattr(snap, "turn_phase", "") or "")
        ctrl = get_overlay_controller()
        merged = dict(ctrl._state.snapshot().system_metrics)
        merged["conv_intent"] = intent or "—"
        merged["conv_conf"] = f"{conf:.2f}" if conf else "—"
        merged["conv_turn"] = phase or "—"
        prof = getattr(snap, "profile", None)
        if prof is not None:
            merged.update(prof.as_dict())
        ctrl._state.set_system_metrics(merged)
        partial = str(getattr(snap, "reformulated_text", "") or getattr(snap, "partial_text", ""))
        if partial:
            ctrl.on_transcribing(sub_status=f"… {partial[:100]}")
    except Exception as exc:
        logger.debug("overlay conversation stream: %s", exc)


def notify_overlay_realtime_stt_metrics(metrics: object) -> None:
    """Realtime streaming STT latency on HUD (Phase 42.6)."""
    try:
        hud = getattr(metrics, "as_hud_dict", None)
        data = hud() if callable(hud) else {}
        if not data:
            return
        ctrl = get_overlay_controller()
        snap = ctrl._state.snapshot()
        merged = dict(snap.system_metrics)
        merged.update({str(k): str(v) for k, v in data.items()})
        ctrl._state.set_system_metrics(merged)
    except Exception as exc:
        logger.debug("overlay realtime stt metrics: %s", exc)


def notify_overlay_heard_transcript(raw: str, normalized: str) -> None:
    try:
        get_overlay_controller().on_heard_transcript(raw, normalized)
    except Exception as exc:
        logger.debug("overlay heard transcript: %s", exc)


def notify_overlay_thinking(*, status_hint: str = "") -> None:
    notify_overlay_executing(status_hint=status_hint)


def notify_overlay_executing(
    *,
    intent: str = "",
    intent_label: str = "",
    status_hint: str = "",
    sub_status: str = "",
) -> None:
    try:
        from ui.overlay_presence import intent_display_label

        label = intent_label or intent_display_label(intent)
        ctrl = get_overlay_controller()
        ctrl.on_executing(
            intent_label=label,
            status_hint=status_hint,
            sub_status=sub_status,
        )
    except Exception as exc:
        logger.debug("overlay executing: %s", exc)


def notify_overlay_fast_ack(ack_text: str, *, intent: str = "") -> None:
    """Phase 37e / 38a — quick status after classify (display-only)."""
    try:
        notify_overlay_executing(intent=intent, sub_status=ack_text)
    except Exception as exc:
        logger.debug("overlay fast ack: %s", exc)


def notify_overlay_awaiting_confirmation(
    *,
    intent: str = "",
    intent_label: str = "",
    guidance: str = "",
) -> None:
    try:
        from ui.overlay_presence import CONFIRM_GUIDANCE, intent_display_label

        ctrl = get_overlay_controller()
        ctrl.on_awaiting_confirmation(
            intent_label=intent_label or intent_display_label(intent),
            guidance=guidance or CONFIRM_GUIDANCE,
        )
    except Exception as exc:
        logger.debug("overlay confirmation: %s", exc)


def notify_overlay_workflow(hint: str) -> None:
    try:
        get_overlay_controller().on_workflow_hint(hint)
    except Exception as exc:
        logger.debug("overlay workflow: %s", exc)


def notify_overlay_ready(*, quiet: bool = False) -> None:
    try:
        get_overlay_controller().on_ready(quiet=quiet)
    except Exception as exc:
        logger.debug("overlay ready: %s", exc)


def notify_overlay_tts_started() -> None:
    try:
        get_overlay_controller().on_tts_started()
    except Exception as exc:
        logger.debug("overlay tts start: %s", exc)


def notify_overlay_tts_finished() -> None:
    try:
        get_overlay_controller().on_tts_finished()
    except Exception as exc:
        logger.debug("overlay tts finish: %s", exc)


def notify_overlay_viseme(level: float) -> None:
    try:
        ctrl = get_overlay_controller()
        if not ctrl.is_active():
            return

        def _go() -> None:
            ctrl._state.set_viseme_level(level)

        ctrl._apply_if_active(_go)
    except Exception as exc:
        logger.debug("overlay viseme: %s", exc)


def notify_overlay_result(
    summary: str,
    *,
    speaking: bool = False,
    suggestions: list[str] | tuple[str, ...] | None = None,
    intent: str = "",
) -> None:
    try:
        from ui.overlay_presence import intent_display_label

        ctrl = get_overlay_controller()
        ctrl.on_result(
            summary,
            speaking=speaking,
            suggestions=suggestions,
            intent_label=intent_display_label(intent),
        )
    except Exception as exc:
        logger.debug("overlay result: %s", exc)


def notify_overlay_error(message: str) -> None:
    try:
        ctrl = get_overlay_controller()
        ctrl.on_error(message)
    except Exception as exc:
        logger.debug("overlay error: %s", exc)


def notify_overlay_task_started(*, command: str = "", task_id: int | None = None) -> None:
    hint = command[:80] if command else "Background task"
    if task_id is not None:
        hint = f"Task {task_id}: {hint}"
    try:
        notify_overlay_executing(status_hint=hint, sub_status="starting...")
        notify_overlay_workflow(hint)
    except Exception as exc:
        logger.debug("overlay task started: %s", exc)


def notify_overlay_task_progress(
    *,
    command: str = "",
    task_id: int | None = None,
    progress: str = "",
) -> None:
    hint = command[:80] if command else "Background task"
    if task_id is not None:
        hint = f"Task {task_id}: {hint}"
    try:
        notify_overlay_executing(status_hint=hint, sub_status=progress[:120])
    except Exception as exc:
        logger.debug("overlay task progress: %s", exc)


def notify_overlay_task_complete(
    *,
    command: str = "",
    task_id: int | None = None,
    summary: str = "",
    status: str = "success",
) -> None:
    hint = command[:80] if command else "Task complete"
    if task_id is not None:
        hint = f"Task {task_id}"
    try:
        if status in {"failed", "timeout", "cancelled"}:
            notify_overlay_error(summary or f"{hint} {status}")
        else:
            notify_overlay_result(summary or hint, intent=command[:40])
            notify_overlay_workflow(f"{hint} done")
        notify_overlay_assistant_state()
    except Exception as exc:
        logger.debug("overlay task complete: %s", exc)


def notify_overlay_notification(title: str, message: str, *, severity: str = "info") -> None:
    try:
        hint = f"{title}: {message}"[:120]
        notify_overlay_workflow(hint)
        if severity in {"error", "critical", "warning"}:
            get_overlay_controller()._state.set_system_metrics(
                {"notification": hint, "severity": severity}
            )
        notify_overlay_assistant_state()
    except Exception as exc:
        logger.debug("overlay notification: %s", exc)


def notify_overlay_assistant_state() -> None:
    """Phase 53 — overlay assistant mode snapshot."""
    try:
        ctrl = get_overlay_controller()
        parts: list[str] = []
        try:
            from runtime.background_tasks import get_engine

            running = get_engine().list_running()
            if running:
                task = running[0]
                parts.append(f"Task {task.id} {task.command[:40]} ({task.duration_seconds:.1f}s)")
            recent = get_engine().get_last_completed()
            if recent and recent.result_summary:
                parts.append(f"Done: {recent.result_summary[:60]}")
        except Exception:
            pass
        try:
            from assistant.continuity_engine import get_overlay_snapshot

            snap = get_overlay_snapshot()
            if snap.get("investigation"):
                parts.append(f"Investigating: {snap['investigation'][:50]}")
            if snap.get("blockers"):
                parts.append(f"Blocker: {snap['blockers'][:50]}")
        except Exception:
            pass
        try:
            from assistant.investigation_scheduler import get_overlay_snapshot as get_investigation_overlay

            inv = get_investigation_overlay()
            if inv.get("loop") == "paused":
                parts.append("Investigation loop paused")
            if inv.get("top_hypothesis"):
                parts.append(f"Hypothesis: {inv['top_hypothesis'][:50]}")
            if inv.get("dominant_blocker"):
                parts.append(f"Dominant: {inv['dominant_blocker'][:50]}")
            if inv.get("runtime_severity") not in {"ok", "unknown"}:
                parts.append(f"Runtime: {inv['runtime_severity']}")
            if inv.get("unresolved_anomalies"):
                parts.append(f"Anomalies: {inv['unresolved_anomalies']}")
            if inv.get("latest_finding"):
                parts.append(f"Finding: {inv['latest_finding'][:50]}")
        except Exception:
            pass
        try:
            from assistant.root_cause_engine import get_overlay_snapshot as get_root_cause_overlay

            rc = get_root_cause_overlay()
            if rc.get("dominant_root_cause"):
                parts.append(f"Root cause: {rc['dominant_root_cause'][:50]}")
            if rc.get("confidence_trend") not in {"stable", ""}:
                parts.append(f"Confidence: {rc['confidence_trend']}")
            if rc.get("active_contradictions"):
                parts.append(f"Contradictions: {rc['active_contradictions']}")
            if rc.get("recommended_verification"):
                parts.append(f"Verify: {rc['recommended_verification'][:40]}")
        except Exception:
            pass
        try:
            from assistant.conversation_state import get_overlay_snapshot as get_conversation_overlay

            conv = get_conversation_overlay()
            if conv.get("conversation_topic"):
                parts.append(f"Topic: {conv['conversation_topic'][:50]}")
            if conv.get("interruption_state") not in {"idle", ""}:
                parts.append(f"Interrupt: {conv['interruption_state']}")
            if conv.get("continuous_listening"):
                parts.append("Listening: continuous")
        except Exception:
            pass
        try:
            from assistant.proactive_assistant import get_overlay_snapshot as get_proactive_overlay

            pa = get_proactive_overlay()
            if pa.get("latest_proactive"):
                parts.append(f"Suggest: {pa['latest_proactive'][:50]}")
        except Exception:
            pass
        try:
            from voice.streaming_pipeline import get_pipeline_metrics

            metrics = get_pipeline_metrics()
            if metrics.get("last_latency_ms"):
                parts.append(f"STT latency: {metrics['last_latency_ms']:.0f}ms")
        except Exception:
            pass
        try:
            from assistant.notifications import get_notification_store

            latest = get_notification_store().latest_unread()
            if latest:
                parts.append(f"Alert: {latest.title[:50]}")
        except Exception:
            pass
        if parts:
            ctrl.on_workflow_hint(" | ".join(parts)[:120])
    except Exception as exc:
        logger.debug("overlay assistant state: %s", exc)


def start_overlay(runtime_state: object | None = None, *, force: bool = False) -> None:
    """Start overlay UI thread (config, runtime flag, or CLI --overlay force)."""
    from core.runtime_state import get_runtime_state

    rt = runtime_state if runtime_state is not None else get_runtime_state()
    ctrl = get_overlay_controller()
    enabled = bool(force or OVERLAY_ENABLED or getattr(rt, "overlay_enabled", False))
    if enabled:
        if hasattr(rt, "set_overlay"):
            rt.set_overlay(True)
        ctrl.set_enabled(True, runtime=rt)
        style = resolve_overlay_theme_name()
        logger.info("Overlay enabled (style=%s)", style)
        print(f"Overlay style: {style}", flush=True)
    else:
        if hasattr(rt, "set_overlay"):
            rt.set_overlay(False)


def update_overlay_state(
    state: str,
    status_text: str = "",
    *,
    transcript: str | None = None,
    result_summary: str | None = None,
    error: str | None = None,
) -> None:
    """Update overlay phase and optional text (display-only)."""
    ctrl = get_overlay_controller()
    if not ctrl.is_enabled():
        return
    if state:
        ctrl._state.show(state, status_text)
    if transcript is not None:
        ctrl.on_transcript(transcript)
    if result_summary is not None:
        ctrl.on_result(result_summary, speaking=False)
    if error:
        ctrl.on_error(error)


def show_test_overlay() -> None:
    """Tray/menu test — cycles UI states without executing commands."""
    get_overlay_controller().run_test_sequence()


def stop_overlay() -> None:
    """Stop overlay Qt thread and reset controller."""
    reset_overlay_controller()


def start_overlay_for_tray(app: "JarvisApp") -> None:
    """Start overlay UI thread when tray boots (respects config + runtime)."""
    del app
    from config import BACKGROUND_MODE

    if BACKGROUND_MODE:
        start_overlay_background()
    else:
        start_overlay()


def start_overlay_background(runtime_state: object | None = None) -> None:
    """Enable overlay subsystem hidden (background quiet mode)."""
    from config import BACKGROUND_MODE, OVERLAY_ENABLED, OVERLAY_SHOW_ON_WAKE
    from core.runtime_state import get_runtime_state
    from ui.quiet_mode import hide_overlay_window, init_quiet_mode_from_config

    init_quiet_mode_from_config()
    rt = runtime_state if runtime_state is not None else get_runtime_state()
    enabled = bool(OVERLAY_ENABLED or BACKGROUND_MODE or OVERLAY_SHOW_ON_WAKE)
    if hasattr(rt, "set_overlay"):
        rt.set_overlay(enabled)
    ctrl = get_overlay_controller()
    ctrl.set_enabled(enabled, runtime=rt)
    if enabled:
        ctrl.ensure_started()
    if BACKGROUND_MODE:
        hide_overlay_window(reason="tray_startup")
    logger.info(
        "Overlay background start (enabled=%s quiet=%s)",
        enabled,
        BACKGROUND_MODE,
    )
