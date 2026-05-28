"""Phase 57 — realtime TTS provider adapters."""

from voice.providers.provider_health import (
    benchmark_all_providers,
    format_benchmark_report,
    show_realtime_provider_status,
)
from voice.providers.registry import (
    get_provider_chain,
    get_provider_health,
    select_provider,
    speak_with_failover,
)

__all__ = [
    "benchmark_all_providers",
    "format_benchmark_report",
    "get_provider_chain",
    "get_provider_health",
    "select_provider",
    "show_realtime_provider_status",
    "speak_with_failover",
]
