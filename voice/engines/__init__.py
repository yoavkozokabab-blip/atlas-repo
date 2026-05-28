"""Phase 41 — multi-engine TTS adapters."""

from voice.engines.registry import (
    get_engine,
    get_engine_chain,
    list_registered_engines,
    synthesize_with_fallback,
)

__all__ = [
    "get_engine",
    "get_engine_chain",
    "list_registered_engines",
    "synthesize_with_fallback",
]
