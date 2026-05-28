"""TTS configuration status (read-only)."""

from __future__ import annotations

from dataclasses import dataclass

from config import (
    TTS_ASYNC,
    TTS_ENABLED,
    TTS_ENGINE,
    TTS_FORCE_ENGINE,
    TTS_LANGUAGE,
    TTS_MAX_CHARS,
    TTS_RATE_RAW,
    TTS_VOICE,
    TTS_VOLUME,
)
from voice.tts_config import normalize_tts_engine, resolve_edge_tts_rate, resolve_pyttsx_rate


@dataclass
class TtsStatus:
    enabled: bool
    engine: str
    voice: str
    rate_raw: str
    edge_rate: str
    pyttsx_rate: int
    language: str
    volume: float
    max_chars: int
    async_mode: bool
    last_provider: str | None
    last_success: bool | None
    last_error: str | None
    async_failure_count: int
    edge_available: bool
    pyttsx_available: bool


_last_provider: str | None = None
_last_success: bool | None = None
_last_error: str | None = None
_async_failure_count: int = 0


def record_tts_run(*, provider: str, error: str | None = None) -> None:
    global _last_provider, _last_error, _last_success
    _last_provider = provider
    _last_error = error
    _last_success = error is None


def record_tts_async_failure(error: str, *, provider: str | None = None) -> None:
    """Record a background (TTS_ASYNC) worker failure."""
    global _last_provider, _last_error, _last_success, _async_failure_count
    _async_failure_count += 1
    if provider:
        _last_provider = provider
    _last_error = error
    _last_success = False


def reset_tts_status_cache() -> None:
    global _last_provider, _last_error, _last_success, _async_failure_count
    _last_provider = None
    _last_error = None
    _last_success = None
    _async_failure_count = 0


def _edge_import_ok() -> bool:
    try:
        import edge_tts  # noqa: F401

        return True
    except ImportError:
        return False


def _pyttsx_import_ok() -> bool:
    try:
        import pyttsx3  # noqa: F401

        return True
    except ImportError:
        return False


def get_tts_status() -> TtsStatus:
    engine = normalize_tts_engine(TTS_ENGINE)
    if TTS_FORCE_ENGINE:
        engine = normalize_tts_engine(TTS_FORCE_ENGINE)
    return TtsStatus(
        enabled=TTS_ENABLED,
        engine=engine,
        voice=TTS_VOICE or "(default)",
        rate_raw=TTS_RATE_RAW,
        edge_rate=resolve_edge_tts_rate(TTS_RATE_RAW),
        pyttsx_rate=resolve_pyttsx_rate(TTS_RATE_RAW),
        language=TTS_LANGUAGE,
        volume=TTS_VOLUME,
        max_chars=TTS_MAX_CHARS,
        async_mode=TTS_ASYNC,
        last_provider=_last_provider,
        last_success=_last_success,
        last_error=_last_error,
        async_failure_count=_async_failure_count,
        edge_available=_edge_import_ok(),
        pyttsx_available=_pyttsx_import_ok(),
    )


def format_tts_status(status: TtsStatus | None = None) -> str:
    s = status or get_tts_status()
    lines = [
        "TTS status",
        f"  Enabled: {'yes' if s.enabled else 'no'}",
        f"  Engine (config): {s.engine}",
        f"  Voice: {s.voice}",
        f"  Rate (raw): {s.rate_raw}",
        f"  Edge rate: {s.edge_rate}",
        f"  pyttsx3 rate: {s.pyttsx_rate}",
        f"  Language (pyttsx3): {s.language}",
        f"  Volume: {s.volume}",
        f"  Max chars: {s.max_chars}",
        f"  Async: {'yes' if s.async_mode else 'no'}",
        f"  edge-tts package: {'yes' if s.edge_available else 'no'}",
        f"  pyttsx3 package: {'yes' if s.pyttsx_available else 'no'}",
    ]
    if s.last_provider:
        lines.append(f"  Last engine: {s.last_provider}")
    if s.last_success is not None:
        lines.append(f"  Last success: {'yes' if s.last_success else 'no'}")
    if s.last_error:
        lines.append(f"  Last error: {s.last_error}")
    if s.async_failure_count:
        lines.append(f"  Async failure count: {s.async_failure_count}")
    if s.engine == "edge_tts":
        lines.append("  Fallback: pyttsx3 on edge-tts failure")
    return "\n".join(lines)
