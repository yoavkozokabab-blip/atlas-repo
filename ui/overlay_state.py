"""Thread-safe overlay state (UI-only, no command execution)."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from threading import Lock
from typing import Callable

from config import OVERLAY_MAX_TEXT_CHARS
from ui.overlay_presence import (
    CONFIRM_GUIDANCE,
    DEFAULT_IDLE_SUGGESTIONS,
    ERROR_SUGGESTIONS,
    SUBTEXT_CONFIRMATION,
    SUBTEXT_EXECUTING,
    SUBTEXT_READY,
    SUBTEXT_RECORDING,
    SUBTEXT_TRANSCRIBING,
    sanitize_suggestion_chips,
    truncate_result_for_overlay,
)
from vision.redaction import redact_sensitive_text

COMMAND_HISTORY_MAX = 5
SESSION_TIMELINE_MAX = 6

PIPELINE_STAGES: tuple[str, ...] = (
    "WAKE",
    "RECORD",
    "TRANSCRIBE",
    "EXECUTE",
    "SPEAK",
    "COMPLETE",
)


class OverlayPhase(str, Enum):
    IDLE = "idle"
    READY = "ready"
    WAKE_DETECTED = "wake_detected"
    LISTENING = "listening"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    EXECUTING = "executing"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    SPEAKING = "speaking"
    COMPLETE = "complete"
    DONE = "complete"
    ERROR = "error"


PHASE_STATUS: dict[OverlayPhase, str] = {
    OverlayPhase.IDLE: "",
    OverlayPhase.READY: "READY",
    OverlayPhase.WAKE_DETECTED: "WAKE DETECTED",
    OverlayPhase.LISTENING: "RECORDING",
    OverlayPhase.RECORDING: "RECORDING",
    OverlayPhase.TRANSCRIBING: "TRANSCRIBING",
    OverlayPhase.THINKING: "EXECUTING",
    OverlayPhase.EXECUTING: "EXECUTING",
    OverlayPhase.AWAITING_CONFIRMATION: "CONFIRMATION",
    OverlayPhase.SPEAKING: "SPEAKING",
    OverlayPhase.COMPLETE: "COMPLETE",
    OverlayPhase.ERROR: "ERROR",
}

PHASE_PIPELINE_INDEX: dict[OverlayPhase, int] = {
    OverlayPhase.WAKE_DETECTED: 0,
    OverlayPhase.LISTENING: 1,
    OverlayPhase.RECORDING: 1,
    OverlayPhase.TRANSCRIBING: 2,
    OverlayPhase.THINKING: 3,
    OverlayPhase.EXECUTING: 3,
    OverlayPhase.AWAITING_CONFIRMATION: 3,
    OverlayPhase.SPEAKING: 4,
    OverlayPhase.COMPLETE: 5,
    OverlayPhase.READY: -1,
    OverlayPhase.ERROR: -1,
    OverlayPhase.IDLE: -1,
}


@dataclass(frozen=True)
class OverlaySnapshot:
    """Immutable view for UI polling."""

    phase: OverlayPhase = OverlayPhase.IDLE
    visible: bool = False
    status_text: str = ""
    sub_status_text: str = ""
    intent_label: str = ""
    transcript: str = ""
    result_summary: str = ""
    suggestions: tuple[str, ...] = ()
    workflow_hint: str = ""
    pulse_active: bool = False
    quiet_ready: bool = False
    error_message: str = ""
    hide_after_monotonic: float | None = None
    updated_at: str = ""
    version: int = 0
    command_history: tuple[str, ...] = ()
    pipeline_stage: int = -1
    system_metrics: dict[str, str] = field(default_factory=dict)
    workspace_mode: str = "idle"
    session_timeline: tuple[str, ...] = ()
    ambient_hint: str = ""
    voice_quality: str = ""
    active_project: str = ""
    viseme_level: float = 0.0


def redact_overlay_text(text: str) -> str:
    """Redact secrets before showing transcript or result on overlay."""
    if not text:
        return ""
    return redact_sensitive_text(text)[:OVERLAY_MAX_TEXT_CHARS]


def pipeline_index_for_phase(phase: OverlayPhase) -> int:
    if phase == OverlayPhase.DONE:
        return PHASE_PIPELINE_INDEX[OverlayPhase.COMPLETE]
    return PHASE_PIPELINE_INDEX.get(phase, -1)


_PHASE_BY_NAME: dict[str, OverlayPhase] = {
    "idle": OverlayPhase.IDLE,
    "ready": OverlayPhase.READY,
    "wake_detected": OverlayPhase.WAKE_DETECTED,
    "listening": OverlayPhase.RECORDING,
    "recording": OverlayPhase.RECORDING,
    "transcribing": OverlayPhase.TRANSCRIBING,
    "thinking": OverlayPhase.EXECUTING,
    "executing": OverlayPhase.EXECUTING,
    "awaiting_confirmation": OverlayPhase.AWAITING_CONFIRMATION,
    "confirmation": OverlayPhase.AWAITING_CONFIRMATION,
    "speaking": OverlayPhase.SPEAKING,
    "done": OverlayPhase.COMPLETE,
    "complete": OverlayPhase.COMPLETE,
    "error": OverlayPhase.ERROR,
}


class OverlayState:
    """Mutable overlay model; safe to update from voice/tray threads."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._snap = OverlaySnapshot()
        self._listeners: list[Callable[[OverlaySnapshot], None]] = []
        self.enabled = True

    @property
    def state(self) -> str:
        return self._snap.phase.value

    @property
    def status_text(self) -> str:
        return self._snap.status_text

    @property
    def transcript(self) -> str:
        return self._snap.transcript

    @property
    def result_summary(self) -> str:
        return self._snap.result_summary

    @property
    def last_error(self) -> str:
        return self._snap.error_message

    @property
    def command_history(self) -> tuple[str, ...]:
        return self._snap.command_history

    def show(self, state: str, status_text: str = "") -> None:
        """Update visible phase (UI-only)."""
        key = (state or "idle").strip().lower().replace("-", "_")
        label = status_text.strip() or PHASE_STATUS.get(
            _PHASE_BY_NAME.get(key, OverlayPhase.IDLE), ""
        )
        if key == "wake_detected":
            self.set_wake_detected()
            if status_text:
                self._update(status_text=label)
            return
        if key in ("listening", "recording"):
            self.set_recording()
            if status_text:
                self._update(status_text=label)
            return
        if key == "transcribing":
            self.set_transcribing()
            if status_text:
                self._update(status_text=label)
            return
        if key in ("thinking", "executing"):
            self.set_executing(status_hint=status_text)
            return
        if key == "speaking":
            self.set_speaking()
            if status_text:
                self._update(status_text=label)
            return
        if key in ("done", "complete"):
            self.set_complete(summary=self._snap.result_summary)
            if status_text:
                self._update(status_text=label)
            return
        if key == "error":
            self._apply_error(label or "ERROR")
            return
        if key == "idle":
            self.hide()
            return
        if key == "ready":
            self.set_ready()
            return
        phase = _PHASE_BY_NAME.get(key, OverlayPhase.IDLE)
        self._update(
            phase=phase,
            visible=phase != OverlayPhase.IDLE,
            status_text=label,
            pipeline_stage=pipeline_index_for_phase(phase),
            pulse_active=phase
            in {
                OverlayPhase.RECORDING,
                OverlayPhase.TRANSCRIBING,
                OverlayPhase.SPEAKING,
                OverlayPhase.WAKE_DETECTED,
                OverlayPhase.EXECUTING,
            },
        )
        self._emit()

    def hide(self) -> None:
        self._update(
            phase=OverlayPhase.IDLE,
            visible=False,
            status_text="",
            sub_status_text="",
            intent_label="",
            transcript="",
            result_summary="",
            suggestions=(),
            workflow_hint="",
            pulse_active=False,
            quiet_ready=False,
            error_message="",
            hide_after_monotonic=None,
            pipeline_stage=-1,
        )
        self._emit()

    def reset(self) -> None:
        """Clear overlay display to idle."""
        self.hide()

    def subscribe(self, listener: Callable[[OverlaySnapshot], None]) -> None:
        with self._lock:
            self._listeners.append(listener)

    def snapshot(self) -> OverlaySnapshot:
        with self._lock:
            return self._snap

    def push_command_history(self, summary: str) -> None:
        """Keep last N command summaries (redacted, English display only)."""
        safe = redact_overlay_text(summary).strip()
        if not safe:
            return
        with self._lock:
            history = list(self._snap.command_history)
            history.append(safe)
            if len(history) > COMMAND_HISTORY_MAX:
                history = history[-COMMAND_HISTORY_MAX:]
            self._snap = replace(
                self._snap,
                command_history=tuple(history),
                version=self._snap.version + 1,
            )

    def set_system_metrics(self, metrics: dict[str, str]) -> None:
        with self._lock:
            self._snap = replace(
                self._snap,
                system_metrics=dict(metrics),
                version=self._snap.version + 1,
            )
        self._emit()

    def push_timeline_event(self, label: str) -> None:
        from config import HUD_SESSION_TIMELINE_ENABLED

        if not HUD_SESSION_TIMELINE_ENABLED:
            return
        safe = redact_overlay_text(label).strip()
        if not safe:
            return
        with self._lock:
            timeline = list(self._snap.session_timeline)
            timeline.append(safe[:80])
            if len(timeline) > SESSION_TIMELINE_MAX:
                timeline = timeline[-SESSION_TIMELINE_MAX:]
            self._snap = replace(
                self._snap,
                session_timeline=tuple(timeline),
                version=self._snap.version + 1,
            )
        self._emit()

    def set_viseme_level(self, level: float) -> None:
        val = max(0.0, min(1.0, float(level)))
        with self._lock:
            self._snap = replace(
                self._snap,
                viseme_level=val,
                version=self._snap.version + 1,
            )
        self._emit()

    def refresh_operating_context(self) -> None:
        """Read-only workspace + session fields for HUD (never fails caller)."""
        from config import HUD_WORKSPACE_MODE_ENABLED

        if not HUD_WORKSPACE_MODE_ENABLED:
            return
        try:
            from pathlib import Path

            from conversation.suggestion_engine import build_workspace_suggestions
            from core.session import SessionState
            from operating.workspace_context import get_cached_mode

            session = SessionState.load()
            mode = get_cached_mode() or session.activity_mode or "idle"
            hints = build_workspace_suggestions(mode)
            ambient = hints[0] if hints else ""
            proj = Path(session.current_project_root or ".").name
            vq = "ok"
            try:
                from voice.wake_diagnostics import format_wake_diagnostics

                wd = format_wake_diagnostics()
                if wd:
                    vq = wd.splitlines()[0][:24]
            except Exception:
                pass
            with self._lock:
                self._snap = replace(
                    self._snap,
                    workspace_mode=mode[:16],
                    ambient_hint=redact_overlay_text(ambient)[:96],
                    active_project=proj[:32],
                    voice_quality=vq[:24],
                    version=self._snap.version + 1,
                )
            self._emit()
        except Exception:
            pass

    def _emit(self) -> None:
        snap = self._snap
        listeners = list(self._listeners)
        for fn in listeners:
            try:
                fn(snap)
            except Exception:
                pass

    def _update(self, **changes) -> OverlaySnapshot:
        with self._lock:
            phase = changes.get("phase", self._snap.phase)
            if phase == OverlayPhase.DONE:
                phase = OverlayPhase.COMPLETE
                changes["phase"] = phase
            if "pipeline_stage" not in changes and isinstance(phase, OverlayPhase):
                changes["pipeline_stage"] = pipeline_index_for_phase(phase)
            if "status_text" not in changes and isinstance(phase, OverlayPhase):
                changes.setdefault("status_text", PHASE_STATUS.get(phase, ""))
            self._snap = replace(
                self._snap,
                version=self._snap.version + 1,
                updated_at=datetime.now(timezone.utc).isoformat(),
                **changes,
            )
            return self._snap

    def set_ready(self, *, quiet: bool = False) -> None:
        self.refresh_operating_context()
        self._update(
            phase=OverlayPhase.READY,
            visible=not quiet,
            status_text=PHASE_STATUS[OverlayPhase.READY],
            sub_status_text=SUBTEXT_READY,
            intent_label="",
            pulse_active=True,
            quiet_ready=quiet,
            error_message="",
            hide_after_monotonic=None,
            pipeline_stage=-1,
            suggestions=sanitize_suggestion_chips(DEFAULT_IDLE_SUGGESTIONS),
        )
        self._emit()

    def set_wake_detected(self) -> None:
        self._update(
            phase=OverlayPhase.WAKE_DETECTED,
            visible=True,
            status_text=PHASE_STATUS[OverlayPhase.WAKE_DETECTED],
            sub_status_text="",
            intent_label="",
            quiet_ready=False,
            pulse_active=True,
            transcript="",
            result_summary="",
            suggestions=(),
            workflow_hint="",
            error_message="",
            hide_after_monotonic=None,
            pipeline_stage=0,
        )
        self._emit()

    def set_listening(self) -> None:
        self.set_recording()

    def set_recording(self, *, sub_status: str = "") -> None:
        self._update(
            phase=OverlayPhase.RECORDING,
            visible=True,
            status_text=PHASE_STATUS[OverlayPhase.RECORDING],
            sub_status_text=(sub_status or SUBTEXT_RECORDING)[:120],
            intent_label="",
            quiet_ready=False,
            pulse_active=True,
            error_message="",
            hide_after_monotonic=None,
            pipeline_stage=1,
        )
        self._emit()

    def set_transcribing(self, *, sub_status: str = "") -> None:
        self._update(
            phase=OverlayPhase.TRANSCRIBING,
            visible=True,
            status_text=PHASE_STATUS[OverlayPhase.TRANSCRIBING],
            sub_status_text=(sub_status or SUBTEXT_TRANSCRIBING)[:120],
            pulse_active=True,
            pipeline_stage=2,
        )
        self._emit()

    def set_thinking(self, *, status_hint: str = "") -> None:
        self.set_executing(status_hint=status_hint)

    def set_executing(
        self,
        *,
        intent_label: str = "",
        status_hint: str = "",
        sub_status: str = "",
    ) -> None:
        hint = (status_hint or "").strip()
        label = (intent_label or hint or "Processing command")[:120]
        sub = (sub_status or hint or SUBTEXT_EXECUTING)[:120]
        self._update(
            phase=OverlayPhase.EXECUTING,
            visible=True,
            status_text=PHASE_STATUS[OverlayPhase.EXECUTING],
            intent_label=label,
            sub_status_text=sub,
            pulse_active=True,
            pipeline_stage=3,
        )
        self._emit()

    def set_awaiting_confirmation(
        self,
        *,
        intent_label: str = "",
        guidance: str = "",
    ) -> None:
        label = (intent_label or "Pending action")[:120]
        guide = (guidance or CONFIRM_GUIDANCE)[:120]
        self._update(
            phase=OverlayPhase.AWAITING_CONFIRMATION,
            visible=True,
            status_text=PHASE_STATUS[OverlayPhase.AWAITING_CONFIRMATION],
            intent_label=label,
            sub_status_text=f"{SUBTEXT_CONFIRMATION} {guide}".strip()[:160],
            pulse_active=False,
            pipeline_stage=3,
        )
        self._emit()

    def set_workflow_hint(self, hint: str) -> None:
        safe = redact_overlay_text(hint)[:120]
        if not safe:
            return
        self._update(workflow_hint=safe)
        self._emit()

    def set_transcript(self, text: str, *, show: bool = True) -> None:
        safe = redact_overlay_text(text) if show else ""
        if safe and not safe.lower().startswith("i heard:"):
            safe = f"I heard: {safe}"
        self._update(transcript=safe)
        self._emit()

    def set_suggestions(self, phrases: list[str] | tuple[str, ...] | None) -> None:
        chips = sanitize_suggestion_chips(phrases)
        self._update(suggestions=chips)
        self._emit()

    def set_complete(
        self,
        *,
        summary: str = "",
        show_result: bool = True,
        suggestions: list[str] | tuple[str, ...] | None = None,
    ) -> None:
        safe = truncate_result_for_overlay(summary) if show_result and summary else ""
        chips = sanitize_suggestion_chips(suggestions) if suggestions else self._snap.suggestions
        if safe:
            self.push_command_history(safe)
        self._update(
            phase=OverlayPhase.COMPLETE,
            visible=True,
            status_text=PHASE_STATUS[OverlayPhase.COMPLETE],
            result_summary=safe or self._snap.result_summary,
            suggestions=chips,
            sub_status_text="",
            intent_label="",
            pulse_active=False,
            pipeline_stage=5,
        )
        self._emit()

    def set_done(self, *, summary: str = "", show_result: bool = True) -> None:
        self.set_complete(summary=summary, show_result=show_result)

    def set_result(
        self,
        summary: str,
        *,
        show: bool = True,
        speaking: bool = False,
        suggestions: list[str] | tuple[str, ...] | None = None,
        intent_label: str = "",
    ) -> None:
        safe = truncate_result_for_overlay(summary) if show else ""
        chips = sanitize_suggestion_chips(suggestions)
        label = (intent_label or "")[:120]
        if speaking:
            self._update(
                phase=OverlayPhase.SPEAKING,
                visible=True,
                result_summary=safe,
                suggestions=chips,
                intent_label=label,
                status_text=PHASE_STATUS[OverlayPhase.SPEAKING],
                sub_status_text="Speaking response...",
                pulse_active=True,
                pipeline_stage=4,
            )
        else:
            if safe:
                self.push_command_history(safe)
            self._update(
                phase=OverlayPhase.COMPLETE,
                visible=True,
                result_summary=safe,
                suggestions=chips,
                intent_label=label,
                status_text=PHASE_STATUS[OverlayPhase.COMPLETE],
                sub_status_text="",
                pulse_active=False,
                pipeline_stage=5,
            )
        self._emit()

    def set_speaking(self, *, sub_status: str = "Speaking response...") -> None:
        self._update(
            phase=OverlayPhase.SPEAKING,
            visible=True,
            status_text=PHASE_STATUS[OverlayPhase.SPEAKING],
            sub_status_text=sub_status[:120],
            pulse_active=True,
            pipeline_stage=4,
            voice_quality="SPEAKING",
        )
        self._emit()

    def set_voice_output_status(self, status: str, *, detail: str = "") -> None:
        label = (status or "").strip().upper()[:40]
        sub = (detail or label)[:120]
        phase = self._snap.phase
        if label == "SPEAKING":
            phase = OverlayPhase.SPEAKING
        elif label == "STREAMING RESPONSE":
            phase = OverlayPhase.SPEAKING
        self._update(
            phase=phase,
            visible=True,
            status_text=label or self._snap.status_text,
            sub_status_text=sub,
            voice_quality=label,
            pulse_active=label in {"SPEAKING", "STREAMING RESPONSE"},
        )
        self._emit()

    def set_error(self, message: str) -> None:
        self._apply_error(message)

    def _apply_error(self, message: str) -> None:
        safe = redact_overlay_text(message)[:200]
        if safe and "Try saying:" not in safe:
            safe = f"{safe}\nTry saying: show voice debug"
        self._update(
            phase=OverlayPhase.ERROR,
            visible=True,
            status_text=PHASE_STATUS[OverlayPhase.ERROR],
            error_message=safe,
            sub_status_text="Try saying: show voice debug",
            intent_label="",
            suggestions=sanitize_suggestion_chips(ERROR_SUGGESTIONS),
            pulse_active=False,
            pipeline_stage=-1,
        )
        self._emit()

    def schedule_hide_at(self, monotonic_deadline: float) -> None:
        self._update(hide_after_monotonic=monotonic_deadline)
        self._emit()
