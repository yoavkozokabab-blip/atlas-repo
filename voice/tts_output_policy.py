"""TTS output policy — tool mode, human session priority, mute guards (Phase 59.2)."""

from __future__ import annotations

from dataclasses import dataclass, field

from core.logger import setup_logger

logger = setup_logger("jarvis.voice.tts_output_policy")

_last_decision: "TtsOutputDecision | None" = None


@dataclass(frozen=True)
class TtsOutputDecision:
    allowed: bool
    reason: str
    audio_mode: str
    voice_path: str
    session_active: bool
    tool_first_mode: bool
    speak_enabled: bool
    suppress_flags: dict[str, bool] = field(default_factory=dict)
    overlay_status: str = ""


def conversational_session_has_priority() -> bool:
    try:
        import config as cfg

        if not getattr(cfg, "HUMAN_CONVERSATIONAL_RUNTIME_ENABLED", False):
            return False
        from conversation.human_runtime import is_session_active

        return is_session_active()
    except Exception:
        return False


def is_explicit_mute_active(*, speak_enabled: bool | None = None) -> bool:
    if speak_enabled is not None:
        return not speak_enabled
    try:
        from core.runtime_state import get_runtime_state

        return not get_runtime_state().speak_enabled
    except Exception:
        return False


def evaluate_tts_output(
    *,
    speak_enabled: bool | None = None,
    voice_path: str = "unknown",
    input_mode: str = "",
    intent: str = "",
) -> TtsOutputDecision:
    """Decide whether live TTS/playback is allowed and why."""
    try:
        from voice.tts_policy_trace import log_tts_policy_context

        log_tts_policy_context(
            stage="evaluate_tts_output.enter",
            speak_enabled=speak_enabled,
            voice_path=voice_path,
            input_mode=input_mode,
            intent=intent,
        )
    except Exception:
        pass
    if speak_enabled is None:
        try:
            from core.runtime_state import get_runtime_state

            speak_enabled = get_runtime_state().speak_enabled
        except Exception:
            speak_enabled = True

    suppress: dict[str, bool] = {}
    session_active = conversational_session_has_priority()
    tool_first = False
    try:
        from voice.tool_first_mode import is_tool_first_mode

        tool_first = is_tool_first_mode()
    except Exception:
        pass

    def _finish(decision: TtsOutputDecision) -> TtsOutputDecision:
        _remember(decision)
        _trace_eval_exit(decision, voice_path=voice_path, input_mode=input_mode, intent=intent)
        return decision

    if not speak_enabled:
        suppress["speak_disabled"] = True
        return _finish(
            TtsOutputDecision(
                allowed=False,
                reason="speak_disabled",
                audio_mode="muted",
                voice_path=voice_path,
                session_active=session_active,
                tool_first_mode=tool_first,
                speak_enabled=False,
                suppress_flags=suppress,
                overlay_status="MUTED",
            )
        )

    if session_active:
        return _finish(
            TtsOutputDecision(
                allowed=True,
                reason="conversational_session_priority",
                audio_mode="conversational",
                voice_path=voice_path,
                session_active=True,
                tool_first_mode=tool_first,
                speak_enabled=True,
                suppress_flags=suppress,
                overlay_status="STREAMING RESPONSE",
            )
        )

    try:
        from voice.backend_verification import conversational_playback_allowed

        conv_allowed, conv_reason = conversational_playback_allowed(session_active=False)
        if conv_allowed:
            return _finish(
                TtsOutputDecision(
                    allowed=True,
                    reason=conv_reason,
                    audio_mode="conversational",
                    voice_path=voice_path,
                    session_active=False,
                    tool_first_mode=tool_first,
                    speak_enabled=True,
                    suppress_flags=suppress,
                    overlay_status="STREAMING RESPONSE",
                )
            )
    except Exception:
        pass

    if tool_first:
        suppress["tool_first_mode"] = True
        verified = False
        try:
            from voice.audio_verified import has_verified_audio_backend

            verified = has_verified_audio_backend()
        except Exception:
            pass
        try:
            from voice.audio_status import is_debug_force_audio_enabled

            if is_debug_force_audio_enabled():
                verified = True
        except Exception:
            pass
        if not verified:
            return _finish(
                TtsOutputDecision(
                    allowed=False,
                    reason="tool_first_unverified_backend",
                    audio_mode="deferred",
                    voice_path=voice_path,
                    session_active=False,
                    tool_first_mode=True,
                    speak_enabled=True,
                    suppress_flags=suppress,
                    overlay_status="TTS BLOCKED",
                )
            )

    return _finish(
        TtsOutputDecision(
            allowed=True,
            reason="allowed",
            audio_mode="normal",
            voice_path=voice_path,
            session_active=session_active,
            tool_first_mode=tool_first,
            speak_enabled=True,
            suppress_flags=suppress,
            overlay_status="",
        )
    )


def _trace_eval_exit(
    decision: TtsOutputDecision,
    *,
    voice_path: str,
    input_mode: str,
    intent: str,
) -> None:
    try:
        from voice.tts_policy_trace import log_tts_policy_context

        log_tts_policy_context(
            stage="evaluate_tts_output.exit",
            voice_path=voice_path,
            input_mode=input_mode,
            intent=intent,
            decision=decision,
        )
    except Exception:
        pass


def can_attempt_tts(*, voice_path: str = "can_attempt_tts") -> bool:
    """Whether TTS route is available (ignores user mute; checks session + tool-first backend)."""
    decision = evaluate_tts_output(speak_enabled=True, voice_path=voice_path)
    log_tts_output_decision(decision)
    if not decision.allowed:
        notify_overlay_tts_blocked(decision)
    return decision.allowed


def log_tts_output_decision(decision: TtsOutputDecision) -> None:
    logger.info(
        "TTS output decision allowed=%s reason=%s path=%s mode=%s session_active=%s "
        "tool_first=%s suppress=%s",
        decision.allowed,
        decision.reason,
        decision.voice_path,
        decision.audio_mode,
        decision.session_active,
        decision.tool_first_mode,
        decision.suppress_flags,
    )


def get_last_tts_output_decision() -> TtsOutputDecision | None:
    return _last_decision


def format_tts_output_diagnostics() -> str:
    decision = _last_decision
    lines = ["TTS output diagnostics (Phase 59.2):"]
    if decision is None:
        lines.append("  last decision: n/a")
        return "\n".join(lines)
    lines.extend(
        [
            f"  allowed: {'yes' if decision.allowed else 'no'}",
            f"  reason: {decision.reason}",
            f"  audio_mode: {decision.audio_mode}",
            f"  voice_path: {decision.voice_path}",
            f"  session_active: {'yes' if decision.session_active else 'no'}",
            f"  tool_first_mode: {'yes' if decision.tool_first_mode else 'no'}",
            f"  speak_enabled: {'yes' if decision.speak_enabled else 'no'}",
            f"  overlay_status: {decision.overlay_status or 'n/a'}",
            f"  suppress_flags: {decision.suppress_flags or '{}'}",
        ]
    )
    return "\n".join(lines)


def log_speech_synthesis_started(*, voice_path: str, provider: str = "") -> None:
    logger.info(
        "TTS synthesis started path=%s provider=%s session_active=%s",
        voice_path,
        provider or "pending",
        conversational_session_has_priority(),
    )


def notify_overlay_tts_blocked(decision: TtsOutputDecision) -> None:
    if not decision.overlay_status:
        return
    try:
        from ui.overlay_voice_status import notify_overlay_voice_output_status

        notify_overlay_voice_output_status(
            decision.overlay_status,
            detail=decision.reason,
        )
    except Exception as exc:
        logger.debug("overlay TTS blocked notify failed: %s", exc)


def notify_overlay_speaking(*, streaming: bool = False) -> None:
    status = "STREAMING RESPONSE" if streaming else "SPEAKING"
    try:
        from ui.overlay_voice_status import notify_overlay_voice_output_status

        notify_overlay_voice_output_status(status)
    except Exception:
        pass


def notify_overlay_interrupted() -> None:
    try:
        from ui.overlay_voice_status import notify_overlay_voice_output_status

        notify_overlay_voice_output_status("INTERRUPTED")
    except Exception:
        pass


def _remember(decision: TtsOutputDecision) -> None:
    global _last_decision
    _last_decision = decision


def reset_tts_output_policy_for_tests() -> None:
    global _last_decision
    _last_decision = None
