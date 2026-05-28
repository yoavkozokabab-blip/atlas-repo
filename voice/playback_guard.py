"""Skip real audio output during pytest unless explicitly opted in."""

from __future__ import annotations

from core.test_runtime import allow_audio_playback, is_test_mode


def should_play_audio() -> bool:
    try:
        from voice.tts_playback_trace import is_tts_safe_mode

        if is_tts_safe_mode():
            return True
    except Exception:
        pass
    return allow_audio_playback()
