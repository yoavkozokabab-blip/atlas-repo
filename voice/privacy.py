"""Wake-word / voice privacy guards (no audio persistence)."""

from __future__ import annotations

from pathlib import Path

from config import WAKE_WORD_DEBUG
from core.file_cleanup import remove_file_best_effort
from core.logger import setup_logger

logger = setup_logger("jarvis.voice.privacy")

_FORBIDDEN_PERSIST_DIRS = (
    "wake_audio",
    "wakeword_clips",
    "mic_recordings",
)


def ensure_no_audio_persistence(path: Path | None) -> None:
    """
    Delete temporary audio file after STT; never move to project data dirs.
    """
    if path is None:
        return
    try:
        resolved = path.resolve()
        parts = {p.lower() for p in resolved.parts}
        for bad in _FORBIDDEN_PERSIST_DIRS:
            if bad in parts:
                logger.warning("Refusing to leave audio under persist-like path: %s", resolved)
        if resolved.exists() and not remove_file_best_effort(resolved):
            logger.warning("Audio cleanup could not remove temporary file: %s", resolved)
    except OSError as exc:
        if WAKE_WORD_DEBUG:
            logger.debug("Audio cleanup: %s", exc)


def validate_runtime_privacy(*, debug: bool | None = None) -> list[str]:
    """
    Return privacy warnings (empty if OK). No raw audio should be stored.
    """
    warnings: list[str] = []
    dbg = WAKE_WORD_DEBUG if debug is None else debug
    if dbg:
        warnings.append("WAKE_WORD_DEBUG=true — console debug only; no audio files.")
    return warnings
