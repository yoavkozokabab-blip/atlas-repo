"""Provider health monitoring and latency benchmarking (Phase 57)."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from core.logger import setup_logger

logger = setup_logger("jarvis.voice.providers.health")

_lock = threading.Lock()
_benchmarks: dict[str, "ProviderBenchmarkResult"] = {}


@dataclass
class ProviderBenchmarkResult:
    provider: str
    available: bool
    first_chunk_ms: float | None = None
    error: str = ""
    probed_at: float = field(default_factory=time.time)

    def format_line(self) -> str:
        if self.error:
            return f"  {self.provider}: error={self.error[:80]}"
        return (
            f"  {self.provider}: first_chunk_ms={self._fmt(self.first_chunk_ms)} "
            f"available={'yes' if self.available else 'no'}"
        )

    @staticmethod
    def _fmt(value: float | None) -> str:
        return f"{value:.1f}" if value is not None else "n/a"


def benchmark_provider(provider, *, probe_text: str = "Realtime latency probe.") -> ProviderBenchmarkResult:
    name = getattr(provider, "name", "unknown")
    if not provider.is_available():
        result = ProviderBenchmarkResult(provider=name, available=False, error="unavailable")
        _store(result)
        return result

    t0 = time.perf_counter()
    first_ms: float | None = None
    try:
        chunks = provider.stream(probe_text)
        for chunk in chunks:
            if chunk.data:
                first_ms = (time.perf_counter() - t0) * 1000.0
                break
            if (time.perf_counter() - t0) > 5.0:
                break
        try:
            provider.cancel()
        except Exception:
            pass
        result = ProviderBenchmarkResult(
            provider=name,
            available=True,
            first_chunk_ms=first_ms,
        )
    except Exception as exc:
        result = ProviderBenchmarkResult(provider=name, available=False, error=str(exc))
    _store(result)
    return result


def benchmark_all_providers(*, probe_text: str = "Realtime latency probe.") -> list[ProviderBenchmarkResult]:
    from voice.providers.registry import get_provider_chain

    results: list[ProviderBenchmarkResult] = []
    for provider in get_provider_chain():
        if provider.fallback_only:
            continue
        results.append(benchmark_provider(provider, probe_text=probe_text))
    return results


def get_provider_benchmarks() -> dict[str, ProviderBenchmarkResult]:
    with _lock:
        return dict(_benchmarks)


def _store(result: ProviderBenchmarkResult) -> None:
    with _lock:
        _benchmarks[result.provider] = result


def show_realtime_provider_status() -> str:
    from voice.providers.registry import get_provider_chain, get_provider_health, select_provider

    selected = select_provider()
    health = get_provider_health()
    benchmarks = get_provider_benchmarks()
    lines = [
        "Realtime TTS provider status:",
        f"  active: {selected.name if selected else 'none'}",
        f"  fallback_only active: {'yes' if selected and selected.fallback_only else 'no'}",
        "  providers:",
    ]
    for item in health:
        bench = benchmarks.get(item.name)
        bench_ms = bench.first_chunk_ms if bench else None
        lines.append(
            f"    - {item.name}: {'ok' if item.available else 'missing'} "
            f"latency={item.latency_class} fallback_only={item.fallback_only} "
            f"bench_first_chunk_ms={ProviderBenchmarkResult._fmt(bench_ms)} "
            f"({item.reason})"
        )
    return "\n".join(lines)


def format_benchmark_report(results: list[ProviderBenchmarkResult] | None = None) -> str:
    if results is None:
        results = list(get_provider_benchmarks().values())
    lines = ["Realtime provider latency benchmark:", f"  probes: {len(results)}"]
    for item in results:
        lines.append(item.format_line())
    if results:
        measured = [r for r in results if r.first_chunk_ms is not None]
        if measured:
            best = min(measured, key=lambda r: r.first_chunk_ms or 99999)
            lines.append(f"  fastest: {best.provider} ({best.first_chunk_ms:.1f} ms first chunk)")
    return "\n".join(lines)


def reset_provider_health_for_tests() -> None:
    global _benchmarks
    with _lock:
        _benchmarks = {}
