"""Active TTS backend selection for stable/safe runtime."""

from __future__ import annotations

from voice.audio_verified import has_verified_audio_backend
from voice.tts_playback_trace import is_tts_safe_mode
from voice.tts_subprocess import SHELL_SUBPROCESS_BACKEND, SUBPROCESS_BACKEND

DIRECT_PYTTSX3_BACKEND = "direct_pyttsx3"

_SUBPROCESS_BACKENDS = frozenset(
    {SUBPROCESS_BACKEND, SHELL_SUBPROCESS_BACKEND, "subprocess"}
)


def get_configured_tts_backend() -> str:
    try:
        import config as cfg

        return (getattr(cfg, "TTS_BACKEND", "") or "").strip().lower()
    except Exception:
        return ""


def get_verified_normal_speech_backend() -> str | None:
    """User-verified audible backend; overrides voice-stack / config when set."""
    if not has_verified_audio_backend():
        return None
    from voice.audio_status import get_selected_verified_audio_backend

    return get_selected_verified_audio_backend()


def must_use_verified_backend_for_normal_speech() -> bool:
    return get_verified_normal_speech_backend() is not None


def get_active_tts_backend() -> str:
    verified = get_verified_normal_speech_backend()
    if verified:
        return verified
    if is_tts_safe_mode():
        return "unverified"
    return get_configured_tts_backend() or "default"


def prefer_subprocess_pyttsx3() -> bool:
    verified = get_verified_normal_speech_backend()
    if not verified:
        return False
    if verified == DIRECT_PYTTSX3_BACKEND:
        return False
    try:
        from voice.audio_status import is_force_direct_normal_mode

        if is_force_direct_normal_mode():
            return False
    except Exception:
        pass
    return verified in _SUBPROCESS_BACKENDS


def prefer_direct_pyttsx3() -> bool:
    verified = get_verified_normal_speech_backend()
    if verified == DIRECT_PYTTSX3_BACKEND:
        return True
    try:
        from voice.audio_status import is_force_direct_normal_mode

        return is_force_direct_normal_mode()
    except Exception:
        return False


def should_ignore_voice_stack_tts_engine() -> bool:
    """Stable/safe runtime must not apply edge_tts profile over verified backend."""
    if not is_tts_safe_mode():
        return False
    return must_use_verified_backend_for_normal_speech()


def normal_speech_must_not_use_edge_tts() -> bool:
    """Block edge_tts / voice-stack streaming for normal speech."""
    if must_use_verified_backend_for_normal_speech():
        return True
    return is_tts_safe_mode()
