"""Verified audible backend gate — no SPEAK / no normal TTS until user confirms."""

from __future__ import annotations

SHELL_SUBPROCESS_BACKEND = "shell_subprocess_pyttsx3"
UNVERIFIED_OVERLAY_MESSAGE = "Audio backend not verified. Run audio route prove."


def has_verified_audio_backend() -> bool:
    from voice.audio_status import get_selected_verified_audio_backend

    return bool(get_selected_verified_audio_backend())


def stable_requires_verified_backend() -> bool:
    try:
        from voice.tool_first_mode import is_tool_first_mode

        if is_tool_first_mode():
            return True
    except Exception:
        pass
    from voice.tts_playback_trace import is_tts_safe_mode

    return is_tts_safe_mode()


def may_use_verified_speech() -> bool:
    try:
        from voice.backend_verification import conversational_playback_allowed
        from conversation.human_runtime import is_session_active

        allowed, _reason = conversational_playback_allowed(session_active=is_session_active())
        if allowed:
            return True
    except Exception:
        pass
    try:
        from voice.tts_output_policy import evaluate_tts_output

        decision = evaluate_tts_output(voice_path="may_use_verified_speech")
        if decision.allowed:
            return True
    except Exception:
        pass
    try:
        from voice.audio_status import ensure_force_audio_debug_applied, is_debug_force_audio_enabled

        if is_debug_force_audio_enabled():
            ensure_force_audio_debug_applied()
            return True
    except Exception:
        pass
    if not stable_requires_verified_backend():
        return True
    return has_verified_audio_backend()


def may_show_speaking_overlay() -> bool:
    return may_use_verified_speech()


def block_unverified_speech_with_warning() -> bool:
    """
    In stable/safe mode without verified backend: warn overlay, block speech.
    Returns True when speech is allowed.
    """
    if may_use_verified_speech():
        return True
    print(f"[TTS] blocked: {UNVERIFIED_OVERLAY_MESSAGE}", flush=True)
    try:
        from ui.overlay_app import notify_overlay_error

        notify_overlay_error(UNVERIFIED_OVERLAY_MESSAGE)
    except Exception:
        pass
    return False


def ask_user_audible_confirmation(
    prompt: str,
    *,
    timeout_seconds: float = 120.0,
) -> bool | None:
    from ui.console_modal import run_modal_yes_no_prompt

    return run_modal_yes_no_prompt(prompt, timeout_seconds=timeout_seconds)
