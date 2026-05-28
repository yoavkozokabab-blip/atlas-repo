"""Voice profile auto-tuning from local diagnostics (Phase 42 v2)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from config import PROJECT_ROOT
from core.logger import setup_logger

logger = setup_logger("jarvis.voice.auto_tune")

_ENV_PATH = PROJECT_ROOT / ".env"
_SAFE_KEYS = frozenset(
    {
        "VOICE_PROFILE",
        "STT_MODEL",
        "STT_BEAM_SIZE",
        "WAKE_SILENCE_SECONDS",
        "WAKE_WORD_THRESHOLD",
        "STT_LOW_CONFIDENCE_BLOCK_WAKE",
        "FAST_VOICE_MODE",
        "WAKE_MAX_LISTEN_SECONDS",
    }
)
_FORBIDDEN_SUBSTRINGS = (
    "api_key",
    "secret",
    "token",
    "password",
    "openai",
    "deepgram",
    "cloud",
    "STT_ENGINE=deepgram",
)


@dataclass(frozen=True)
class TuneRecommendation:
    key: str
    value: str
    reason: str


def analyze_voice_diagnostics() -> list[TuneRecommendation]:
    """Inspect local diagnostics; return safe .env recommendations only."""
    recs: list[TuneRecommendation] = []
    try:
        from voice.stt_diagnostics import snapshot as stt_snap
        from voice.voice_debug_store import get_voice_debug_snapshot
        from voice.wake_diagnostics import snapshot as wake_snap

        stt = stt_snap()
        voice = get_voice_debug_snapshot()
        wake = wake_snap()
    except Exception as exc:
        logger.debug("auto_tune diagnostics: %s", exc)
        return [
            TuneRecommendation(
                key="VOICE_PROFILE",
                value="balanced",
                reason="use balanced — diagnostics unavailable",
            )
        ]

    if stt.consecutive_empty_wake >= 2 or wake.empty_after_wake_count >= 2:
        recs.append(
            TuneRecommendation(
                key="WAKE_SILENCE_SECONDS",
                value="1.8",
                reason="increase wake silence to 1.8 — repeated empty wake sessions",
            )
        )
        recs.append(
            TuneRecommendation(
                key="WAKE_MAX_LISTEN_SECONDS",
                value="6",
                reason="allow slightly longer wake capture after empty sessions",
            )
        )

    if stt.low_confidence_count >= 3 or voice.low_confidence_count >= 3:
        recs.append(
            TuneRecommendation(
                key="VOICE_PROFILE",
                value="accurate",
                reason="switch to accurate profile — frequent low-confidence STT",
            )
        )
        recs.append(
            TuneRecommendation(
                key="STT_BEAM_SIZE",
                value="5",
                reason="increase STT beam for clearer command recognition",
            )
        )

    if wake.clipped_session_count >= 2:
        recs.append(
            TuneRecommendation(
                key="WAKE_SILENCE_SECONDS",
                value="2.0",
                reason="increase wake silence — clipped command estimate",
            )
        )

    if wake.false_trigger_cooldown_count >= 3:
        recs.append(
            TuneRecommendation(
                key="WAKE_WORD_THRESHOLD",
                value="0.52",
                reason="lower wake threshold to 0.52 — reduce false-trigger cooldown skips",
            )
        )

    if not recs and voice.last_low_confidence:
        recs.append(
            TuneRecommendation(
                key="VOICE_PROFILE",
                value="balanced",
                reason="use balanced — last transcript was low confidence",
            )
        )

    if not recs:
        recs.append(
            TuneRecommendation(
                key="VOICE_PROFILE",
                value="balanced",
                reason="use balanced — voice pipeline looks healthy",
            )
        )
    return recs


def format_auto_tune_report(*, apply: bool = False) -> str:
    recs = analyze_voice_diagnostics()
    lines = ["Voice auto-tune recommendations (local, supervised)"]
    for r in recs:
        lines.append(f"  - {r.reason}")
        lines.append(f"    {r.key}={r.value}")
    if apply:
        lines.append("")
        lines.append("Applied safe .env updates (non-secret keys only).")
    else:
        lines.append("")
        lines.append("Say 'apply auto tune voice' to apply after confirmation.")
    return "\n".join(lines)


def apply_safe_env_recommendations(recs: list[TuneRecommendation]) -> list[str]:
    """Update .env with allowed keys only; never touch secrets or cloud STT."""
    applied: list[str] = []
    if not _ENV_PATH.is_file():
        content = ""
    else:
        content = _ENV_PATH.read_text(encoding="utf-8")
    for rec in recs:
        if rec.key not in _SAFE_KEYS:
            continue
        blob = f"{rec.key}={rec.value}".lower()
        if any(bad in blob for bad in _FORBIDDEN_SUBSTRINGS):
            continue
        pattern = re.compile(rf"^{re.escape(rec.key)}=.*$", re.MULTILINE)
        line = f"{rec.key}={rec.value}"
        if pattern.search(content):
            content = pattern.sub(line, content, count=1)
        else:
            content = content.rstrip() + "\n" + line + "\n"
        applied.append(line)
    if applied:
        try:
            _ENV_PATH.write_text(content, encoding="utf-8")
        except OSError as exc:
            logger.warning("auto_tune .env write failed: %s", exc)
            return []
    return applied
