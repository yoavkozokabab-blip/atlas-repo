"""Premium Iron Man / JARVIS HUD widgets (PySide6 QPainter — UI only)."""

from __future__ import annotations

import math
import random
from datetime import datetime

from ui.overlay_state import (
    PIPELINE_STAGES,
    OverlayPhase,
    OverlaySnapshot,
    OverlayState,
)
from ui.overlay_theme import OverlayTheme


def fetch_hud_system_metrics() -> dict[str, str]:
    """Read-only system stats for HUD panels; safe placeholders if psutil unavailable."""
    now = datetime.now()
    metrics: dict[str, str] = {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "cpu": "N/A",
        "ram": "N/A",
        "storage": "N/A",
        "network": "N/A",
        "power": "ONLINE",
    }
    try:
        from voice.streaming_stt.realtime_metrics import get_realtime_metrics

        rt = get_realtime_metrics()
        if rt is not None:
            metrics.update(rt.as_hud_dict())
    except Exception:
        pass
    try:
        import psutil

        metrics["cpu"] = f"{psutil.cpu_percent(interval=0.1):.0f}%"
        mem = psutil.virtual_memory()
        metrics["ram"] = f"{mem.percent:.0f}%"
        total_gb = 0.0
        used_gb = 0.0
        for part in psutil.disk_partitions(all=False):
            if part.fstype and "cdrom" in part.opts.lower():
                continue
            try:
                usage = psutil.disk_usage(part.mountpoint)
                total_gb += usage.total
                used_gb += usage.used
            except (PermissionError, OSError):
                continue
        if total_gb > 0:
            metrics["storage"] = f"{100.0 * used_gb / total_gb:.0f}%"
        addrs: list[str] = []
        for _name, addr_list in psutil.net_if_addrs().items():
            for addr in addr_list:
                if getattr(addr, "family", None) == 2 and addr.address:
                    if not addr.address.startswith("127."):
                        addrs.append(addr.address)
        metrics["network"] = addrs[0] if addrs else "LOCAL"
    except Exception:
        metrics["cpu"] = "42%"
        metrics["ram"] = "58%"
        metrics["storage"] = "61%"
        metrics["network"] = "LOCAL"
    try:
        from pathlib import Path

        from core.session import SessionState
        from operating.workspace_context import get_cached_mode

        session = SessionState.load()
        metrics["project"] = Path(session.current_project_root or ".").name[:24]
        metrics["workspace"] = get_cached_mode() or session.activity_mode or "idle"
        metrics["voice"] = "ok"
        try:
            from voice.wake_diagnostics import format_wake_diagnostics

            wd = format_wake_diagnostics()
            if wd:
                metrics["voice"] = wd.splitlines()[0][:28]
        except Exception:
            pass
    except Exception:
        metrics["project"] = "n/a"
        metrics["workspace"] = "idle"
        metrics["voice"] = "ok"
    return metrics


def _phase_pulse(snap: OverlaySnapshot) -> bool:
    return snap.phase in {
        OverlayPhase.WAKE_DETECTED,
        OverlayPhase.LISTENING,
        OverlayPhase.RECORDING,
        OverlayPhase.TRANSCRIBING,
        OverlayPhase.EXECUTING,
        OverlayPhase.SPEAKING,
        OverlayPhase.READY,
    }


def _phase_waveform(snap: OverlaySnapshot) -> bool:
    return snap.phase in {
        OverlayPhase.LISTENING,
        OverlayPhase.RECORDING,
        OverlayPhase.TRANSCRIBING,
        OverlayPhase.SPEAKING,
    }


def _workspace_tint_shift(mode: str) -> tuple[int, int, int]:
    """Subtle RGB shift for workspace mode (Phase 40d)."""
    key = (mode or "idle").lower()
    if key == "coding":
        return (0, 30, 40)
    if key == "trading":
        return (40, 20, 0)
    if key == "studying":
        return (20, 0, 35)
    if key == "focus":
        return (-10, 10, 20)
    return (0, 0, 0)


def _phase_reactor_tint(snap: OverlaySnapshot) -> tuple[int, int, int]:
    """RGB accent tint by pipeline phase."""
    phase = snap.phase
    if phase in (OverlayPhase.RECORDING, OverlayPhase.LISTENING):
        base = (0, 220, 255)
    elif phase == OverlayPhase.TRANSCRIBING:
        base = (120, 200, 255)
    elif phase in (OverlayPhase.EXECUTING, OverlayPhase.THINKING, OverlayPhase.AWAITING_CONFIRMATION):
        base = (255, 180, 60)
    elif phase == OverlayPhase.SPEAKING:
        base = (80, 255, 180)
    elif phase == OverlayPhase.ERROR:
        base = (255, 80, 100)
    elif phase == OverlayPhase.READY:
        base = (0, 200, 240)
    else:
        base = (0, 180, 220)
    try:
        from config import HUD_WORKSPACE_MODE_ENABLED

        if HUD_WORKSPACE_MODE_ENABLED and snap.workspace_mode:
            dr, dg, db = _workspace_tint_shift(snap.workspace_mode)
            return (
                max(0, min(255, base[0] + dr)),
                max(0, min(255, base[1] + dg)),
                max(0, min(255, base[2] + db)),
            )
    except Exception:
        pass
    return base


def _runtime_status_lines() -> list[tuple[str, bool]]:
    """Read-only runtime flags for HUD display (no side effects)."""
    try:
        from core.runtime_state import get_runtime_state
        from voice.audio_status import get_audio_status
        from voice.transcriber import get_stt_status

        rt = get_runtime_state()
        audio = get_audio_status()
        stt = get_stt_status()
        return [
            ("VOICE MODULE", rt.voice_enabled),
            (f"MIC/STT {stt.model.upper()} {stt.device.upper()}", rt.voice_enabled),
            (f"AUDIO {audio.playback_backend.upper()[:18]}", bool(audio.enabled)),
            ("WAKE WORD", rt.wake_word_enabled),
            ("OVERLAY HUD", rt.overlay_enabled),
            ("SECURITY LAYER", True),
        ]
    except Exception:
        return [
            ("VOICE MODULE", True),
            ("SPEECH RECOGNITION", True),
            ("TTS ENGINE", True),
            ("WAKE WORD", True),
            ("OVERLAY HUD", True),
            ("SECURITY LAYER", True),
        ]


def build_premium_hud_widget(
    state: OverlayState,
    theme: OverlayTheme,
    *,
    show_audio_pulse: bool = True,
    show_rotating_rings: bool = True,
    fade_ms: int = 250,
    show_waveform: bool = True,
    show_system_panels: bool = True,
    show_command_history: bool = True,
    show_hud_labels: bool = True,
):
    """Factory for premium HUD (compact or full-screen based on theme)."""
    if theme.full_screen:
        return build_premium_full_hud_widget(
            state,
            theme,
            show_audio_pulse=show_audio_pulse,
            show_rotating_rings=show_rotating_rings,
            fade_ms=fade_ms,
            show_waveform=show_waveform,
            show_system_panels=show_system_panels,
            show_command_history=show_command_history,
            show_hud_labels=show_hud_labels,
        )
    return _build_compact_premium_hud(
        state,
        theme,
        show_audio_pulse=show_audio_pulse,
        show_rotating_rings=show_rotating_rings,
        fade_ms=fade_ms,
    )


def build_premium_full_hud_widget(
    state: OverlayState,
    theme: OverlayTheme,
    *,
    show_audio_pulse: bool = True,
    show_rotating_rings: bool = True,
    fade_ms: int = 250,
    show_waveform: bool = True,
    show_system_panels: bool = True,
    show_command_history: bool = True,
    show_hud_labels: bool = True,
):
    """Full-screen cinematic Iron Man HUD (requires PySide6)."""
    from PySide6.QtCore import Qt, QTimer, QRect
    from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
    from PySide6.QtWidgets import QWidget

    fade_step = max(0.02, 16.0 / max(80, fade_ms))
    timer_ms = 33  # ~30 FPS

    class PremiumFullHudWidget(QWidget):
        def __init__(self, parent=None) -> None:
            super().__init__(parent)
            self._state = state
            self._theme = theme
            self._show_pulse = show_audio_pulse
            self._show_rings = show_rotating_rings
            self._show_waveform = show_waveform
            self._show_system = show_system_panels
            self._show_history = show_command_history
            self._show_labels = show_hud_labels
            self._fade = 0.0
            self._target_fade = 0.0
            self._fade_step = fade_step
            self._tick = 0.0
            self._rings = [0.0, 0.0, 0.0, 0.0, 0.0]
            self._snap = state.snapshot()
            self._wave = [random.uniform(0.2, 0.9) for _ in range(24)]
            self._metrics_cache: dict[str, str] = {}
            self._metrics_tick = 0
            self._closed = False

            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

            self._timer = QTimer(self)
            self._timer.timeout.connect(self._animate)
            self._timer.start(timer_ms)

        def _animate(self) -> None:
            if getattr(self, "_closed", False):
                return
            self._snap = self._state.snapshot()
            if self._snap.visible:
                self._target_fade = 1.0
            else:
                self._target_fade = 0.0
            if self._fade < self._target_fade:
                self._fade = min(1.0, self._fade + self._fade_step)
            elif self._fade > self._target_fade:
                self._fade = max(0.0, self._fade - self._fade_step)

            self._tick = (self._tick + 0.06) % (2 * math.pi)
            speeds = (1.4, -1.0, 0.7, -0.45, 0.3)
            for i, spd in enumerate(speeds):
                self._rings[i] = (self._rings[i] + spd) % 360

            if _phase_waveform(self._snap) and self._show_waveform:
                viseme_boost = self._snap.viseme_level if self._snap.phase == OverlayPhase.SPEAKING else 0.0
                for i in range(len(self._wave)):
                    base = (
                        0.25
                        + 0.65 * abs(math.sin(self._tick * 2.5 + i * 0.55))
                        + random.uniform(-0.04, 0.04)
                    )
                    if viseme_boost > 0.05:
                        base = max(base, 0.2 + 0.75 * viseme_boost * abs(math.sin(self._tick * 3 + i * 0.4)))
                    self._wave[i] = base

            self._metrics_tick += 1
            if self._metrics_tick % 90 == 0 or not self._metrics_cache:
                self._metrics_cache = (
                    self._snap.system_metrics
                    if self._snap.system_metrics
                    else fetch_hud_system_metrics()
                )
            try:
                from config import OVERLAY_FPS_SAMPLE_SECONDS
                from services.observability import get_observability

                get_observability().record_overlay_frame(
                    sample_seconds=OVERLAY_FPS_SAMPLE_SECONDS
                )
            except Exception:
                pass
            self.update()

        def closeEvent(self, event) -> None:  # noqa: N802
            self._closed = True
            if getattr(self, "_timer", None) is not None:
                try:
                    self._timer.stop()
                    self._timer.deleteLater()
                except RuntimeError:
                    pass
                self._timer = None
            super().closeEvent(event)

        def paintEvent(self, _event) -> None:  # noqa: N802
            if getattr(self, "_closed", False) or self._fade <= 0.01:
                return

            from PySide6.QtGui import QRadialGradient

            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setOpacity(self._fade)

            w, h = self.width(), self.height()
            margin = 14
            frame = self.rect().adjusted(margin, margin, -margin, -margin)

            self._draw_viewport_backdrop(p, frame)
            accent = QColor(self._theme.accent)
            dim = QColor(self._theme.text_dim)
            text_col = QColor(self._theme.text)
            glow = QColor(self._theme.glow)

            self._draw_hud_grid(p, frame, accent)
            self._draw_glass_frame(p, frame)
            self._draw_corner_brackets(p, frame, accent)

            if self._show_labels:
                self._draw_header(p, frame, accent, dim)

            left_w = int(w * 0.18)
            right_w = int(w * 0.21)
            bottom_h = int(h * 0.12)
            center = frame.adjusted(left_w, 78, -right_w, -bottom_h)

            self._draw_column_rail(p, frame.adjusted(left_w - 6, 60, left_w - 2, -bottom_h), accent)
            self._draw_column_rail(p, frame.adjusted(w - right_w + 2, 60, w - right_w + 6, -bottom_h), accent)

            if self._show_system:
                self._draw_left_panels(
                    p,
                    frame.adjusted(8, 58, -w + left_w + 4, -bottom_h - 6),
                    dim,
                    text_col,
                    accent,
                )

            self._draw_right_panels(
                p,
                frame.adjusted(w - right_w + 4, 58, -8, -bottom_h - 6),
                dim,
                text_col,
                accent,
            )

            self._draw_center_reactor(p, center, accent, glow, QRadialGradient)

            if self._show_waveform:
                self._draw_voice_panel(p, center, accent, text_col)

            self._draw_result_panel(p, center, text_col, glow)
            self._draw_suggestion_chips(p, center, accent, text_col)

            if self._show_history:
                self._draw_command_history(
                    p,
                    frame.adjusted(left_w, h - bottom_h - 128, -right_w, -bottom_h - 6),
                    dim,
                    text_col,
                )

            self._draw_weather_placeholder(
                p,
                frame.adjusted(w - right_w + 4, frame.bottom() - bottom_h - 108, -8, -bottom_h - 6),
                dim,
                accent,
            )

            self._draw_pipeline_bar(
                p,
                frame.adjusted(left_w, frame.bottom() - bottom_h + 6, -right_w, -10),
                accent,
                dim,
            )

            p.end()

        def _draw_viewport_backdrop(self, p, rect) -> None:
            """Full-area dark glass behind the HUD frame."""
            from PySide6.QtGui import QRadialGradient

            p.fillRect(self.rect(), QColor(0, 0, 0, 140))
            vignette = QRadialGradient(rect.center(), max(rect.width(), rect.height()) * 0.72)
            vignette.setColorAt(0.0, QColor(0, 0, 0, 0))
            vignette.setColorAt(0.75, QColor(0, 0, 0, 40))
            vignette.setColorAt(1.0, QColor(0, 0, 0, 120))
            p.fillRect(rect, vignette)

        def _draw_hud_grid(self, p, rect, accent) -> None:
            pen = QPen(QColor(self._theme.accent_dim))
            pen.setWidth(1)
            col = QColor(self._theme.accent)
            col.setAlpha(18)
            pen.setColor(col)
            p.setPen(pen)
            step = 48
            for x in range(rect.left(), rect.right(), step):
                p.drawLine(x, rect.top(), x, rect.bottom())
            for y in range(rect.top(), rect.bottom(), step):
                p.drawLine(rect.left(), y, rect.right(), y)

        def _draw_glass_frame(self, p, rect) -> None:
            grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
            grad.setColorAt(0.0, QColor(3, 10, 22, 240))
            grad.setColorAt(0.45, QColor(2, 8, 18, 215))
            grad.setColorAt(1.0, QColor(4, 16, 32, 235))
            p.setBrush(grad)
            glow_pen = QPen(QColor(self._theme.glow_outer))
            glow_pen.setWidth(4)
            p.setPen(glow_pen)
            p.drawRoundedRect(rect, 14, 14)
            pen = QPen(QColor(self._theme.accent))
            pen.setWidth(2)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 12, 12)
            inner_pen = QPen(QColor(self._theme.accent_dim))
            inner_pen.setWidth(1)
            inner_pen.setStyle(Qt.PenStyle.DotLine)
            p.setPen(inner_pen)
            p.drawRoundedRect(rect.adjusted(8, 8, -8, -8), 10, 10)

        def _draw_corner_brackets(self, p, rect, accent) -> None:
            pen = QPen(accent)
            pen.setWidth(3)
            p.setPen(pen)
            arm = 36
            inset = 4
            corners = (
                (rect.left() + inset, rect.top() + inset),
                (rect.right() - inset, rect.top() + inset),
                (rect.left() + inset, rect.bottom() - inset),
                (rect.right() - inset, rect.bottom() - inset),
            )
            for i, (cx, cy) in enumerate(corners):
                if i == 0:
                    p.drawLine(cx, cy, cx + arm, cy)
                    p.drawLine(cx, cy, cx, cy + arm)
                elif i == 1:
                    p.drawLine(cx, cy, cx - arm, cy)
                    p.drawLine(cx, cy, cx, cy + arm)
                elif i == 2:
                    p.drawLine(cx, cy, cx + arm, cy)
                    p.drawLine(cx, cy, cx, cy - arm)
                else:
                    p.drawLine(cx, cy, cx - arm, cy)
                    p.drawLine(cx, cy, cx, cy - arm)

        def _draw_column_rail(self, p, rect, accent) -> None:
            pen = QPen(accent)
            pen.setWidth(2)
            col = QColor(self._theme.glow_outer)
            col.setAlpha(90)
            pen.setColor(col)
            p.setPen(pen)
            p.drawLine(rect.center().x(), rect.top(), rect.center().x(), rect.bottom())

        def _draw_header(self, p, rect, accent, dim) -> None:
            title_font = QFont(self._theme.font_family, 22)
            title_font.setBold(True)
            title_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 3)
            p.setFont(title_font)
            p.setPen(accent)
            p.drawText(rect.adjusted(20, 8, 0, 0), Qt.AlignmentFlag.AlignLeft, "J.A.R.V.I.S.")
            sub_font = QFont(self._theme.font_family, 9)
            sub_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.5)
            p.setFont(sub_font)
            p.setPen(dim)
            labels = ("SYSTEM ONLINE", "SECURE ROUTER ENABLED", "VOICE LINK ACTIVE")
            x = rect.right() - 320
            for i, lbl in enumerate(labels):
                p.drawText(x + i * 108, 28, lbl)

        def _draw_left_panels(self, p, rect, dim, text_col, accent) -> None:
            m = self._metrics_cache or fetch_hud_system_metrics()
            rows = (
                ("DATE", m.get("date", "--")),
                ("TIME", m.get("time", "--")),
                ("PROJECT", m.get("project", self._snap.active_project or "--")),
                ("MODE", m.get("workspace", self._snap.workspace_mode or "idle")),
                ("VOICE", m.get("voice", self._snap.voice_quality or "ok")),
                ("CPU", m.get("cpu", "N/A")),
                ("RAM", m.get("ram", "N/A")),
                ("STORAGE", m.get("storage", "N/A")),
                ("NETWORK", m.get("network", "N/A")),
                ("POWER", m.get("power", "ONLINE")),
            )
            y = rect.top()
            panel_h = 52
            for title, value in rows:
                self._draw_metric_card(p, QRect(rect.left(), y, rect.width(), panel_h), title, value, dim, text_col, accent)
                y += panel_h + 8

        def _draw_metric_card(self, p, card, title, value, dim, text_col, accent) -> None:
            p.setPen(QPen(QColor(self._theme.accent), 1))
            p.setBrush(QColor(5, 16, 30, 195))
            p.drawRoundedRect(card, 6, 6)
            p.setPen(QPen(QColor(self._theme.glow_outer), 1))
            p.drawLine(card.left(), card.top(), card.right(), card.top())
            lbl_font = QFont(self._theme.font_family, 8)
            lbl_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.2)
            p.setFont(lbl_font)
            p.setPen(dim)
            p.drawText(card.adjusted(10, 6, -8, 0), Qt.AlignmentFlag.AlignLeft, title)
            val_font = QFont(self._theme.font_family, 14)
            val_font.setBold(True)
            p.setFont(val_font)
            p.setPen(accent)
            p.drawText(card.adjusted(10, -6, -8, -8), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, value)

        def _draw_right_panels(self, p, rect, dim, text_col, accent) -> None:
            status_lines = [
                (f"{name} {'ONLINE' if ok else 'STANDBY'}", ok)
                for name, ok in _runtime_status_lines()
            ]
            shortcut_lines = (
                "OPEN DASHBOARD",
                "RUN DIAGNOSTICS",
                "OPEN APPS",
                "OPEN WEBSITES",
                "WORKFLOWS",
            )
            y = rect.top()
            p.setFont(QFont(self._theme.font_family, 9))
            p.setPen(accent)
            p.drawText(rect.left(), y + 12, "SYSTEM STATUS")
            y += 22
            small = QFont(self._theme.font_family, 8)
            p.setFont(small)
            for line, ok in status_lines:
                p.setPen(QColor(self._theme.success if ok else self._theme.text_dim))
                p.drawText(rect.left() + 4, y, "●")
                p.setPen(text_col if ok else dim)
                p.drawText(rect.left() + 16, y, line)
                y += 16
            y += 12
            p.setFont(QFont(self._theme.font_family, 9))
            p.setPen(accent)
            p.drawText(rect.left(), y, "SHORTCUTS")
            y += 18
            p.setFont(small)
            p.setPen(dim)
            for line in shortcut_lines:
                p.drawText(rect.left() + 4, y, line)
                y += 15
            self._draw_session_timeline(p, rect, y + 8, dim, text_col, accent)

        def _draw_session_timeline(self, p, rect, y: int, dim, text_col, accent) -> None:
            from config import HUD_SESSION_TIMELINE_ENABLED

            if not HUD_SESSION_TIMELINE_ENABLED:
                return
            events = self._snap.session_timeline
            if not events:
                return
            p.setFont(QFont(self._theme.font_family, 9))
            p.setPen(accent)
            p.drawText(rect.left(), y + 12, "SESSION")
            y += 22
            p.setFont(QFont(self._theme.font_family, 8))
            p.setPen(dim)
            for evt in events[-6:]:
                p.drawText(rect.left() + 4, y, f"• {evt[:42]}")
                y += 14

        def _draw_center_reactor(self, p, center, accent, glow, QRadialGradient) -> None:
            cx = center.center().x()
            cy = center.center().y() - 10
            base_r = max(72, min(center.width(), center.height()) // 4)
            pulse = 0.5 + 0.5 * math.sin(self._tick)
            tr, tg, tb = _phase_reactor_tint(self._snap)
            idle_drift = 0.15 * math.sin(self._tick * 0.4) if self._snap.phase == OverlayPhase.READY else 0.0
            pulse_scale = 1.0 + (0.12 * pulse if _phase_pulse(self._snap) else 0.0) + idle_drift

            halo = QRadialGradient(cx, cy, base_r + 100)
            halo.setColorAt(0.0, QColor(tr, tg, tb, 50))
            halo.setColorAt(0.55, QColor(0, 80, 120, 20))
            halo.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.fillRect(center, halo)

            for spread, alpha in ((55, 20), (38, 38), (22, 65), (8, 100)):
                gcol = QColor(tr, tg, tb)
                gcol.setAlpha(alpha)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(gcol)
                r = int((base_r + spread + int(12 * pulse)) * pulse_scale)
                p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

            tick_pen = QPen(QColor(self._theme.accent_dim))
            tick_pen.setWidth(1)
            p.setPen(tick_pen)
            for i in range(12):
                ang = math.radians(i * 30 + self._tick * 20)
                r0 = base_r + 18
                r1 = base_r + 28
                p.drawLine(
                    int(cx + math.cos(ang) * r0),
                    int(cy + math.sin(ang) * r0),
                    int(cx + math.cos(ang) * r1),
                    int(cy + math.sin(ang) * r1),
                )

            if self._show_rings:
                radii = (base_r + 32, base_r + 48, base_r + 64, base_r + 80, base_r + 96)
                widths = (2, 1, 3, 1, 2)
                spans = (110, 90, 130, 80, 100)
                colors = (
                    self._theme.accent_dim,
                    self._theme.glow,
                    self._theme.accent,
                    self._theme.glow,
                    self._theme.accent_dim,
                )
                for angle, radius, width, color, span in zip(
                    self._rings, radii, widths, colors, spans
                ):
                    pen = QPen(QColor(color), width)
                    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                    p.setPen(pen)
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawArc(
                        cx - radius,
                        cy - radius,
                        radius * 2,
                        radius * 2,
                        int(angle * 16),
                        span * 16,
                    )
                    pen.setStyle(Qt.PenStyle.DotLine)
                    pen.setWidth(1)
                    p.setPen(pen)
                    p.drawEllipse(cx - radius, cy - radius, radius * 2, radius * 2)

            orb_r = base_r + (14 if _phase_pulse(self._snap) else 0)
            orb_grad = QRadialGradient(cx, cy, orb_r)
            orb_grad.setColorAt(0.0, QColor(0, 40, 70, 240))
            orb_grad.setColorAt(0.45, QColor(0, 200, 240, 250))
            orb_grad.setColorAt(0.85, QColor(0, 120, 180, 230))
            orb_grad.setColorAt(1.0, QColor(0, 25, 50, 200))
            p.setPen(QPen(accent, 4))
            p.setBrush(orb_grad)
            p.drawEllipse(cx - orb_r, cy - orb_r, orb_r * 2, orb_r * 2)

            core_r = int(orb_r * 0.32)
            core_grad = QRadialGradient(cx, cy, core_r)
            core_grad.setColorAt(0.0, QColor(255, 255, 255, int(220 + 30 * pulse)))
            core_grad.setColorAt(0.5, QColor(180, 245, 255, int(200 + 40 * pulse)))
            core_grad.setColorAt(1.0, QColor(0, 160, 220, 180))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(core_grad)
            p.drawEllipse(cx - core_r, cy - core_r, core_r * 2, core_r * 2)

            status = (self._snap.status_text or "STANDBY").upper()
            title_size = self._theme.title_size + (6 if status in ("RECORDING", "SPEAKING", "EXECUTING") else 4)
            title_font = QFont(self._theme.font_family, title_size)
            title_font.setBold(True)
            title_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 3)
            p.setFont(title_font)
            status_glow = QColor(tr, tg, tb, int(180 + 60 * pulse))
            p.setPen(status_glow)
            status_rect = QRect(cx - 260, cy + orb_r + 24, 520, 48)
            p.drawText(status_rect, Qt.AlignmentFlag.AlignHCenter, status)
            intent_line = (self._snap.intent_label or "").strip()
            sub = (self._snap.sub_status_text or "").strip()
            if not sub:
                if status == "RECORDING":
                    sub = "Recording audio..."
                elif status == "TRANSCRIBING":
                    sub = "Transcribing speech..."
                elif status in ("EXECUTING", "CONFIRMATION"):
                    sub = "Processing..."
                elif status == "READY":
                    sub = "Standing by"
                else:
                    sub = f"Status: {status.title()}"
            sub_font = QFont(self._theme.font_family, 9)
            sub_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.2)
            p.setFont(sub_font)
            p.setPen(QColor(self._theme.text_dim))
            y_sub = cy + orb_r + 54
            if intent_line:
                p.drawText(
                    QRect(cx - 260, y_sub, 520, 20),
                    Qt.AlignmentFlag.AlignHCenter,
                    intent_line[:72],
                )
                y_sub += 20
            p.drawText(
                QRect(cx - 260, y_sub, 520, 22),
                Qt.AlignmentFlag.AlignHCenter,
                sub[:96],
            )
            if self._snap.workflow_hint:
                p.drawText(
                    QRect(cx - 260, y_sub + 20, 520, 18),
                    Qt.AlignmentFlag.AlignHCenter,
                    self._snap.workflow_hint[:96],
                )
            elif self._snap.ambient_hint and self._snap.phase == OverlayPhase.READY:
                p.drawText(
                    QRect(cx - 260, y_sub + 20, 520, 18),
                    Qt.AlignmentFlag.AlignHCenter,
                    self._snap.ambient_hint[:96],
                )

        def _draw_voice_panel(self, p, center, accent, text_col) -> None:
            panel = QRect(
                center.left() + 32,
                center.bottom() - 138,
                center.width() - 64,
                62,
            )
            p.setPen(QPen(accent, 1))
            p.setBrush(QColor(6, 18, 34, 185))
            p.drawRoundedRect(panel, 8, 8)
            p.setFont(QFont(self._theme.font_family, 8))
            p.setPen(QColor(self._theme.text_dim))
            p.drawText(panel.adjusted(10, 4, 0, 0), "VOICE INPUT")

            if _phase_waveform(self._snap) and self._show_pulse:
                bar_w = 5 if self._snap.phase == OverlayPhase.SPEAKING else 4
                gap = 3
                n = len(self._wave)
                total_w = n * (bar_w + gap) - gap
                bx = panel.center().x() - total_w // 2
                by = panel.center().y() + 6
                amp = 28 if self._snap.phase == OverlayPhase.SPEAKING else 22
                for i, level in enumerate(self._wave):
                    bh = int(6 + amp * level)
                    col = QColor(self._theme.accent)
                    col.setAlpha(200)
                    p.setBrush(col)
                    p.setPen(Qt.PenStyle.NoPen)
                    p.drawRoundedRect(bx + i * (bar_w + gap), by - bh // 2, bar_w, bh, 2, 2)

            if self._snap.transcript:
                p.setFont(QFont(self._theme.font_family, self._theme.body_size))
                p.setPen(text_col)
                txt = self._snap.transcript[:120]
                if len(self._snap.transcript) > 120:
                    txt += "..."
                p.drawText(panel.adjusted(12, 28, -12, -6), Qt.AlignmentFlag.AlignLeft, txt)

        def _draw_suggestion_chips(self, p, center, accent, text_col) -> None:
            chips = self._snap.suggestions or ()
            if not chips:
                return
            panel_h = 58 if self._snap.phase == OverlayPhase.READY else 44
            panel = QRect(
                center.left() + 40,
                center.bottom() - (248 if self._snap.phase != OverlayPhase.READY else 268),
                center.width() - 80,
                panel_h,
            )
            p.setPen(QPen(QColor(self._theme.accent_dim), 1))
            p.setBrush(QColor(8, 24, 42, 190))
            p.drawRoundedRect(panel, 8, 8)
            p.setFont(QFont(self._theme.font_family, 8))
            p.setPen(accent)
            header = (
                "SUGGESTED COMMANDS"
                if self._snap.phase == OverlayPhase.READY
                else "SUGGESTIONS (say aloud)"
            )
            p.drawText(panel.adjusted(10, 4, 0, 0), header)
            p.setFont(QFont(self._theme.font_family, 8))
            x = panel.left() + 10
            y = panel.top() + 22
            for chip in chips[:4]:
                label = chip[:48]
                chip_w = min(160, 8 * len(label) + 24)
                chip_rect = QRect(x, y, chip_w, 18)
                p.setPen(QPen(accent, 1))
                p.setBrush(QColor(4, 28, 48, 220))
                p.drawRoundedRect(chip_rect, 6, 6)
                p.setPen(text_col)
                p.drawText(chip_rect.adjusted(6, 2, -4, -2), Qt.AlignmentFlag.AlignLeft, label)
                x += chip_w + 8
                if x > panel.right() - 80:
                    break

        def _draw_result_panel(self, p, center, text_col, glow) -> None:
            if not (self._snap.result_summary or self._snap.error_message):
                return
            panel = QRect(
                center.left() + 60,
                center.bottom() - 200,
                center.width() - 120,
                52,
            )
            msg = self._snap.error_message or self._snap.result_summary
            bg = QColor(48, 12, 16, 200) if self._snap.error_message else QColor(10, 36, 48, 200)
            fg = QColor(self._theme.error) if self._snap.error_message else glow
            p.setPen(QPen(QColor(self._theme.accent_dim), 1))
            p.setBrush(bg)
            p.drawRoundedRect(panel, 8, 8)
            p.setFont(QFont(self._theme.font_family, 9))
            p.setPen(QColor(self._theme.text_dim))
            p.drawText(panel.adjusted(10, 4, 0, 0), "COMMAND RESULT")
            p.setFont(QFont(self._theme.font_family, self._theme.body_size))
            p.setPen(fg)
            display = msg[:140] + ("..." if len(msg) > 140 else "")
            p.drawText(panel.adjusted(10, 18, -10, -8), Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, display)

        def _draw_command_history(self, p, rect, dim, text_col) -> None:
            p.setFont(QFont(self._theme.font_family, 9))
            p.setPen(QColor(self._theme.accent))
            p.drawText(rect.left(), rect.top() + 10, "RECENT SUCCESSFUL COMMANDS")
            y = rect.top() + 26
            p.setFont(QFont(self._theme.font_family, 8))
            history = self._snap.command_history or ()
            if not history:
                p.setPen(dim)
                p.drawText(rect.left() + 4, y, "(no recent commands)")
                return
            for entry in history[-5:]:
                line = entry[:80] + ("..." if len(entry) > 80 else "")
                p.setPen(dim)
                p.drawText(rect.left() + 4, y, "›")
                p.setPen(text_col)
                p.drawText(rect.left() + 14, y, line)
                y += 14

        def _draw_weather_placeholder(self, p, rect, dim, accent) -> None:
            p.setPen(QPen(QColor(self._theme.accent_dim), 1))
            p.setBrush(QColor(6, 16, 28, 160))
            p.drawRoundedRect(rect, 6, 6)
            p.setFont(QFont(self._theme.font_family, 8))
            p.setPen(accent)
            p.drawText(rect.adjusted(10, 8, 0, 0), "ENVIRONMENT")
            p.setPen(dim)
            p.drawText(rect.adjusted(10, 24, 0, 0), "WEATHER: N/A (LOCAL)")
            p.drawText(rect.adjusted(10, 38, 0, 0), "SENSOR LINK: STANDBY")

        def _draw_pipeline_bar(self, p, rect, accent, dim) -> None:
            p.setPen(QPen(accent, 1))
            p.setBrush(QColor(3, 10, 20, 215))
            p.drawRoundedRect(rect, 10, 10)
            p.setFont(QFont(self._theme.font_family, 8))
            p.setPen(accent)
            p.drawText(rect.adjusted(14, 6, 0, 0), "COMMAND PIPELINE")
            stage = self._snap.pipeline_stage
            n = len(PIPELINE_STAGES)
            if n == 0:
                return
            track = rect.adjusted(16, 28, -16, -12)
            step_w = max(48, track.width() // n)
            y_mid = track.center().y() + 4
            x = track.left()
            for i, label in enumerate(PIPELINE_STAGES):
                cx = x + step_w // 2
                active = stage >= 0 and i <= stage
                current = stage >= 0 and i == stage
                dot_r = 7 if current else 5
                dot_col = accent if active else dim
                if active and current:
                    glow_c = QColor(self._theme.glow_outer)
                    glow_c.setAlpha(100)
                    p.setBrush(glow_c)
                    p.setPen(Qt.PenStyle.NoPen)
                    p.drawEllipse(cx - dot_r - 4, y_mid - dot_r - 4, (dot_r + 4) * 2, (dot_r + 4) * 2)
                p.setBrush(dot_col)
                p.setPen(QPen(accent if active else dim, 1))
                p.drawEllipse(cx - dot_r, y_mid - dot_r, dot_r * 2, dot_r * 2)
                if i < n - 1:
                    line_col = accent if active and i < stage else dim
                    p.setPen(QPen(line_col, 2 if active else 1))
                    p.drawLine(cx + dot_r + 2, y_mid, cx + step_w - dot_r - 2, y_mid)
                lbl_col = accent if current else (QColor(self._theme.text) if active else dim)
                p.setPen(lbl_col)
                p.drawText(x, track.top(), step_w, 18, Qt.AlignmentFlag.AlignHCenter, label)
                x += step_w

    return PremiumFullHudWidget()


def _build_compact_premium_hud(
    state: OverlayState,
    theme: OverlayTheme,
    *,
    show_audio_pulse: bool = True,
    show_rotating_rings: bool = True,
    fade_ms: int = 250,
):
    """Compact premium HUD widget (legacy small overlay)."""
    from PySide6.QtCore import Qt, QTimer, QRect
    from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
    from PySide6.QtWidgets import QWidget

    fade_step = max(0.02, 16.0 / max(80, fade_ms))

    class PremiumHudWidget(QWidget):
        HUD_LABELS = (
            "SYSTEM ONLINE",
            "VOICE LINK ACTIVE",
            "SECURE ROUTER ENABLED",
        )

        def __init__(self, parent=None) -> None:
            super().__init__(parent)
            self._state = state
            self._theme = theme
            self._show_pulse = show_audio_pulse
            self._show_rings = show_rotating_rings
            self._fade = 0.0
            self._target_fade = 0.0
            self._fade_step = fade_step
            self._tick = 0.0
            self._ring1 = 0.0
            self._ring2 = 0.0
            self._ring3 = 0.0
            self._snap = state.snapshot()
            self._wave = [random.uniform(0.25, 0.85) for _ in range(12)]

            self.setFixedSize(theme.window_width, theme.window_height)
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

            self._timer = QTimer(self)
            self._timer.timeout.connect(self._animate)
            self._timer.start(33)

        def _animate(self) -> None:
            self._snap = self._state.snapshot()
            if self._snap.visible:
                self._target_fade = 1.0
            else:
                self._target_fade = 0.0
            if self._fade < self._target_fade:
                self._fade = min(1.0, self._fade + self._fade_step)
            elif self._fade > self._target_fade:
                self._fade = max(0.0, self._fade - self._fade_step)

            self._tick = (self._tick + 0.05) % (2 * math.pi)
            if self._show_rings:
                self._ring1 = (self._ring1 + 1.2) % 360
                self._ring2 = (self._ring2 - 0.9) % 360
                self._ring3 = (self._ring3 + 0.55) % 360
            if _phase_waveform(self._snap) and self._show_pulse:
                for i in range(len(self._wave)):
                    self._wave[i] = (
                        0.35
                        + 0.55 * abs(math.sin(self._tick * 2.2 + i * 0.7))
                        + random.uniform(-0.05, 0.05)
                    )
            try:
                from config import OVERLAY_FPS_SAMPLE_SECONDS
                from services.observability import get_observability

                get_observability().record_overlay_frame(
                    sample_seconds=OVERLAY_FPS_SAMPLE_SECONDS
                )
            except Exception:
                pass
            self.update()

        def closeEvent(self, event) -> None:  # noqa: N802
            if getattr(self, "_timer", None) is not None:
                self._timer.stop()
                self._timer.deleteLater()
                self._timer = None
            super().closeEvent(event)

        def paintEvent(self, _event) -> None:  # noqa: N802
            if self._fade <= 0.01:
                return

            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setOpacity(self._fade)

            margin = 14
            panel = self.rect().adjusted(margin, margin, -margin, -margin)

            glass = QLinearGradient(panel.topLeft(), panel.bottomRight())
            glass.setColorAt(0.0, QColor(8, 16, 32, 210))
            glass.setColorAt(0.5, QColor(6, 12, 28, 185))
            glass.setColorAt(1.0, QColor(4, 10, 22, 200))
            p.setPen(QPen(QColor(self._theme.accent_dim), 1))
            p.setBrush(glass)
            p.drawRoundedRect(panel, 22, 22)

            inner = panel.adjusted(12, 10, -12, -10)
            accent = QColor(self._theme.accent)
            dim = QColor(self._theme.text_dim)
            glow = QColor(self._theme.glow)

            label_font = QFont(self._theme.font_family, 8)
            label_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.2)
            p.setFont(label_font)
            y_lbl = inner.top() + 4
            for i, lbl in enumerate(self.HUD_LABELS):
                p.setPen(dim if i else accent)
                p.drawText(inner.left() + 4, y_lbl + i * 14, lbl)

            cx = inner.center().x()
            cy = inner.top() + 118
            base_r = 52

            for spread, alpha in ((28, 35), (18, 55), (8, 90)):
                gcol = QColor(self._theme.glow_outer)
                gcol.setAlpha(alpha)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(gcol)
                r = base_r + spread
                p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

            if self._show_rings:
                for angle, radius, width, color in (
                    (self._ring1, base_r + 22, 1, self._theme.accent_dim),
                    (self._ring2, base_r + 30, 2, self._theme.glow),
                    (self._ring3, base_r + 38, 1, self._theme.accent),
                ):
                    pen = QPen(QColor(color), width)
                    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                    p.setPen(pen)
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawArc(
                        cx - radius,
                        cy - radius,
                        radius * 2,
                        radius * 2,
                        int(angle * 16),
                        120 * 16,
                    )

            pulse = 0.5 + 0.5 * math.sin(self._tick)
            orb_r = base_r + (6 if _phase_pulse(self._snap) else 0)
            orb_grad = QLinearGradient(cx - orb_r, cy - orb_r, cx + orb_r, cy + orb_r)
            orb_grad.setColorAt(0.0, QColor(0, 60, 95, 220))
            orb_grad.setColorAt(0.45, QColor(0, 140, 190, 240))
            orb_grad.setColorAt(1.0, QColor(0, 35, 70, 200))
            p.setPen(QPen(accent, 2))
            p.setBrush(orb_grad)
            p.drawEllipse(cx - orb_r, cy - orb_r, orb_r * 2, orb_r * 2)

            core_r = int(orb_r * 0.38)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(180, 245, 255, int(180 + 50 * pulse)))
            p.drawEllipse(cx - core_r, cy - core_r, core_r * 2, core_r * 2)

            if _phase_waveform(self._snap) and self._show_pulse:
                bar_w = 5
                gap = 4
                total_w = len(self._wave) * (bar_w + gap) - gap
                bx = cx - total_w // 2
                by = cy + orb_r + 18
                for i, level in enumerate(self._wave):
                    bh = int(8 + 28 * level)
                    col = QColor(self._theme.accent)
                    col.setAlpha(160)
                    p.setBrush(col)
                    p.setPen(Qt.PenStyle.NoPen)
                    p.drawRoundedRect(bx + i * (bar_w + gap), by - bh, bar_w, bh, 2, 2)

            status = self._snap.status_text or "JARVIS"
            title_font = QFont(self._theme.font_family, self._theme.title_size)
            title_font.setBold(True)
            p.setFont(title_font)
            p.setPen(accent)
            p.drawText(inner, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, status)

            card_font = QFont(self._theme.font_family, self._theme.body_size)
            p.setFont(card_font)
            card_y = cy + orb_r + 52
            if self._snap.transcript:
                self._draw_card(
                    p,
                    inner.adjusted(8, 0, -8, 0),
                    card_y,
                    self._snap.transcript,
                    QColor(12, 28, 48, 200),
                    QColor(self._theme.text),
                )
                card_y += 44
            if self._snap.result_summary:
                self._draw_card(
                    p,
                    inner.adjusted(8, 0, -8, 0),
                    card_y,
                    self._snap.result_summary,
                    QColor(10, 36, 42, 200),
                    glow,
                )
            if self._snap.error_message:
                self._draw_card(
                    p,
                    inner.adjusted(8, 0, -8, 0),
                    card_y,
                    self._snap.error_message,
                    QColor(48, 12, 16, 210),
                    QColor(self._theme.error),
                )
            p.end()

        def _draw_card(self, p, rect, y, text, bg, fg) -> None:
            lines = text.split("\n")[:3]
            display = "\n".join(lines)
            if len(text) > 120:
                display = text[:117] + "..."
            card_h = 36
            card = QRect(rect.left(), y, rect.width(), card_h)
            p.setPen(QPen(QColor(self._theme.accent_dim), 1))
            p.setBrush(bg)
            p.drawRoundedRect(card, 8, 8)
            p.setPen(fg)
            p.drawText(
                card.adjusted(10, 6, -10, -6),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                display,
            )

    return PremiumHudWidget()
