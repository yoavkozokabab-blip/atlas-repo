"""TTS recovery test helper (Phase 67)."""

from __future__ import annotations


def recover_tts_and_speak(phrase: str = "TTS recovery test complete.") -> tuple[bool, str]:
    """Attempt direct TTS isolated speak (bypasses tool-first deferral)."""
    try:
        from voice.pyttsx3_completion import run_direct_tts_isolated_test

        result = run_direct_tts_isolated_test(phrase)
        if result.ok:
            return True, f"TTS recovery spoke ({result.elapsed_ms:.0f}ms)"
        return False, f"TTS recovery failed: {result.error or 'unknown'}"[:200]
    except Exception as exc:
        return False, f"TTS recovery failed: {type(exc).__name__}"[:200]
