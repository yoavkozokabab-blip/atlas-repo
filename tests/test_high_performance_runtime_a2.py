"""Phase A2 high-performance runtime tests."""

from __future__ import annotations

import asyncio
import time

from core.event_bus import EventBus
from core.performance import (
    BackgroundWorkerPool,
    BatchProcessor,
    LowLatencyQueue,
    StreamingPipeline,
    TTLCache,
)
from core.runtime_state import RuntimeState


def test_event_bus_supports_sync_and_async_delivery():
    bus = EventBus(queue_size=8, batch_size=4, worker_count=1)
    seen: list[str] = []

    def sync_handler(value: str):
        seen.append(f"sync:{value}")

    async def async_handler(value: str):
        seen.append(f"async:{value}")

    bus.subscribe("demo", sync_handler)
    bus.subscribe("demo", async_handler)
    bus.publish("demo", value="direct")
    assert "sync:direct" in seen
    assert "async:direct" in seen

    assert asyncio.run(bus.publish_async("demo", value="queued")) is True

    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline and "sync:queued" not in seen:
        time.sleep(0.01)
    bus.stop()

    assert "sync:queued" in seen
    assert "async:queued" in seen
    assert bus.stats()["handled"] >= 4


def test_low_latency_queue_drops_oldest_and_batches():
    q = LowLatencyQueue[int](max_size=2, drop_oldest=True)
    assert q.put(1)
    assert q.put(2)
    assert q.put(3)

    assert q.get_batch(max_items=4, timeout=0.01) == [2, 3]
    stats = q.stats()
    assert stats.dropped == 1
    assert stats.dequeued == 2


def test_ttl_cache_hits_and_expires():
    cache = TTLCache[int](ttl_seconds=0.03, max_entries=2)
    calls = {"n": 0}

    def factory() -> int:
        calls["n"] += 1
        return calls["n"]

    assert cache.get_or_set("a", factory) == 1
    assert cache.get_or_set("a", factory) == 1
    time.sleep(0.04)
    assert cache.get_or_set("a", factory) == 2
    stats = cache.stats()
    assert stats.hits == 1
    assert stats.misses >= 2


def test_background_worker_pool_runs_work():
    pool = BackgroundWorkerPool(name="test", max_workers=1, queue_size=4)
    handle = pool.submit(lambda x: x + 1, 41, workload="unit")
    try:
        assert handle.result(timeout=1.0) == 42
        assert pool.stats()["completed"] == 1
    finally:
        pool.stop()


def test_batch_processor_and_streaming_pipeline():
    batches: list[list[int]] = []
    processor = BatchProcessor(lambda items: batches.append(items), max_batch_size=3)
    assert processor.add(1) is None
    assert processor.add(2) is None
    processor.add(3)
    assert batches == [[1, 2, 3]]

    pipe = StreamingPipeline[int]().add_stage(lambda x: x * 2).add_stage(lambda x: x + 1)
    assert list(pipe.run([1, 2, 3])) == [3, 5, 7]


def test_runtime_state_snapshot_is_shared_and_versioned():
    state = RuntimeState()
    start = state.version
    state.set_voice(True)
    state.increment_counter("commands")
    state.record_event("demo", detail="ok")
    snap = state.snapshot()

    assert snap["voice_enabled"] is True
    assert snap["version"] > start
    assert snap["runtime_counters"]["commands"] == 1
    assert snap["recent_events"][-1]["name"] == "demo"


def test_acceleration_profile_uses_cached_gpu_probe(monkeypatch):
    import services.high_performance_runtime as hpr
    from services.high_performance_runtime import HighPerformanceRuntime
    from voice.stt_acceleration import AccelerationProbe, SttRuntimeChoice

    monkeypatch.setattr(hpr, "GPU_WORKLOAD_PREFER_GPU", True)
    probe_calls = {"n": 0}

    def fake_probe():
        probe_calls["n"] += 1
        return AccelerationProbe(
            cuda_device_count=1,
            cuda_reason="mock cuda",
            directml_available=False,
            directml_reason="mock dml",
            openvino_available=False,
            openvino_reason="mock ov",
            onnx_providers=("CUDAExecutionProvider", "CPUExecutionProvider"),
        )

    def fake_runtime():
        return SttRuntimeChoice(
            backend="faster_whisper",
            whisper_device="cuda",
            compute_type="float16",
            acceleration="cuda",
            onnx_provider="CUDAExecutionProvider",
            reason="mock",
            fallback_reason=None,
            gpu_warning=None,
            device_request="auto",
        )

    monkeypatch.setattr("voice.stt_acceleration.probe_acceleration", fake_probe)
    monkeypatch.setattr("voice.stt_acceleration.get_stt_runtime", fake_runtime)

    runtime = HighPerformanceRuntime()
    first = runtime.acceleration_profile()
    second = runtime.acceleration_profile()

    assert first.gpu_enabled is True
    assert first.batch_size >= 1
    assert second is first
    assert probe_calls["n"] == 1
