"""Phase A2 high-performance runtime coordinator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, TypeVar

from config import (
    BACKGROUND_WORK_QUEUE_SIZE,
    BACKGROUND_WORKER_COUNT,
    GPU_WORKLOAD_BATCH_SIZE,
    GPU_WORKLOAD_PREFER_GPU,
    RUNTIME_CACHE_MAX_ENTRIES,
    RUNTIME_CACHE_TTL_SECONDS,
)
from core.performance import BackgroundWorkerPool, TTLCache, WorkHandle

T = TypeVar("T")


@dataclass(frozen=True)
class AccelerationProfile:
    preferred_device: str
    stt_backend: str
    stt_compute_type: str
    cuda_devices: int
    directml_available: bool
    openvino_available: bool
    onnx_providers: tuple[str, ...]
    gpu_enabled: bool
    batch_size: int
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "preferred_device": self.preferred_device,
            "stt_backend": self.stt_backend,
            "stt_compute_type": self.stt_compute_type,
            "cuda_devices": self.cuda_devices,
            "directml_available": self.directml_available,
            "openvino_available": self.openvino_available,
            "onnx_providers": list(self.onnx_providers),
            "gpu_enabled": self.gpu_enabled,
            "batch_size": self.batch_size,
            "reason": self.reason,
        }


class HighPerformanceRuntime:
    """Shared worker/cache/GPU profile runtime for latency-sensitive subsystems."""

    def __init__(self) -> None:
        self.cache: TTLCache[Any] = TTLCache(
            ttl_seconds=RUNTIME_CACHE_TTL_SECONDS,
            max_entries=RUNTIME_CACHE_MAX_ENTRIES,
        )
        self.background_workers = BackgroundWorkerPool(
            name="runtime",
            max_workers=BACKGROUND_WORKER_COUNT,
            queue_size=BACKGROUND_WORK_QUEUE_SIZE,
        )

    def start(self) -> None:
        self.background_workers.start()

    def stop(self) -> None:
        self.background_workers.stop()

    def acceleration_profile(self, *, refresh: bool = False) -> AccelerationProfile:
        if refresh:
            self.cache.clear()
        return self.cache.get_or_set(
            "acceleration_profile",
            self._build_acceleration_profile,
            ttl_seconds=RUNTIME_CACHE_TTL_SECONDS,
        )

    def submit_background(
        self,
        fn: Callable[..., T],
        *args: Any,
        workload: str = "background",
        **kwargs: Any,
    ) -> WorkHandle[T]:
        return self.background_workers.submit(fn, *args, workload=workload, **kwargs)

    def status(self) -> dict[str, Any]:
        profile = self.acceleration_profile()
        return {
            "acceleration": profile.to_dict(),
            "workers": self.background_workers.stats(),
            "cache": self.cache.stats().__dict__,
        }

    def _build_acceleration_profile(self) -> AccelerationProfile:
        try:
            from voice.stt_acceleration import get_stt_runtime, probe_acceleration

            probe = probe_acceleration()
            runtime = get_stt_runtime()
            gpu_enabled = bool(
                GPU_WORKLOAD_PREFER_GPU
                and (
                    runtime.whisper_device == "cuda"
                    or runtime.backend == "onnx_directml"
                    or probe.openvino_available
                )
            )
            return AccelerationProfile(
                preferred_device=runtime.whisper_device,
                stt_backend=runtime.backend,
                stt_compute_type=runtime.compute_type,
                cuda_devices=probe.cuda_device_count,
                directml_available=probe.directml_available,
                openvino_available=probe.openvino_available,
                onnx_providers=probe.onnx_providers,
                gpu_enabled=gpu_enabled,
                batch_size=max(1, GPU_WORKLOAD_BATCH_SIZE if gpu_enabled else 1),
                reason=runtime.reason,
            )
        except Exception as exc:
            return AccelerationProfile(
                preferred_device="cpu",
                stt_backend="unknown",
                stt_compute_type="int8",
                cuda_devices=0,
                directml_available=False,
                openvino_available=False,
                onnx_providers=(),
                gpu_enabled=False,
                batch_size=1,
                reason=f"acceleration probe failed: {exc}",
            )


_runtime = HighPerformanceRuntime()


def get_high_performance_runtime() -> HighPerformanceRuntime:
    return _runtime


def get_acceleration_profile(*, refresh: bool = False) -> AccelerationProfile:
    return _runtime.acceleration_profile(refresh=refresh)


def submit_background(
    fn: Callable[..., T],
    *args: Any,
    workload: str = "background",
    **kwargs: Any,
) -> WorkHandle[T]:
    return _runtime.submit_background(fn, *args, workload=workload, **kwargs)
