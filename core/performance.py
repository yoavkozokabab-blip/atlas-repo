"""High-performance runtime primitives for local_jarvis.

Small, dependency-light building blocks used by the event bus, runtime workers,
and voice pipelines. They are intentionally in-process and bounded: when load is
too high they shed stale optional work instead of blocking command handling.
"""

from __future__ import annotations

import queue
import threading
import time
import uuid
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Generic, Iterable, Iterator, TypeVar

T = TypeVar("T")
R = TypeVar("R")


@dataclass(frozen=True)
class QueueStats:
    size: int
    max_size: int
    enqueued: int
    dequeued: int
    dropped: int


class LowLatencyQueue(Generic[T]):
    """Bounded queue optimized for latest-state event delivery."""

    def __init__(self, max_size: int = 256, *, drop_oldest: bool = True) -> None:
        self.max_size = max(1, int(max_size))
        self.drop_oldest = drop_oldest
        self._items: Deque[T] = deque()
        self._cv = threading.Condition()
        self._enqueued = 0
        self._dequeued = 0
        self._dropped = 0

    def put(self, item: T) -> bool:
        with self._cv:
            if len(self._items) >= self.max_size:
                if not self.drop_oldest:
                    self._dropped += 1
                    return False
                self._items.popleft()
                self._dropped += 1
            self._items.append(item)
            self._enqueued += 1
            self._cv.notify()
            return True

    def get(self, *, timeout: float | None = None) -> T:
        with self._cv:
            end = None if timeout is None else time.monotonic() + max(0.0, timeout)
            while not self._items:
                if timeout is None:
                    self._cv.wait()
                    continue
                remaining = end - time.monotonic() if end is not None else 0.0
                if remaining <= 0:
                    raise queue.Empty
                self._cv.wait(remaining)
            self._dequeued += 1
            return self._items.popleft()

    def get_batch(self, *, max_items: int, timeout: float | None = None) -> list[T]:
        first = self.get(timeout=timeout)
        batch = [first]
        limit = max(1, int(max_items))
        with self._cv:
            while self._items and len(batch) < limit:
                batch.append(self._items.popleft())
                self._dequeued += 1
        return batch

    def qsize(self) -> int:
        with self._cv:
            return len(self._items)

    def clear(self) -> int:
        with self._cv:
            n = len(self._items)
            self._items.clear()
            return n

    def stats(self) -> QueueStats:
        with self._cv:
            return QueueStats(
                size=len(self._items),
                max_size=self.max_size,
                enqueued=self._enqueued,
                dequeued=self._dequeued,
                dropped=self._dropped,
            )


@dataclass(frozen=True)
class CacheStats:
    size: int
    max_entries: int
    hits: int
    misses: int
    evictions: int


class TTLCache(Generic[T]):
    """Thread-safe TTL + LRU cache for expensive local probes and summaries."""

    def __init__(self, *, ttl_seconds: float = 30.0, max_entries: int = 128) -> None:
        self.ttl_seconds = max(0.001, float(ttl_seconds))
        self.max_entries = max(1, int(max_entries))
        self._items: OrderedDict[str, tuple[float, T]] = OrderedDict()
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get(self, key: str) -> T | None:
        now = time.monotonic()
        with self._lock:
            item = self._items.get(key)
            if item is None:
                self._misses += 1
                return None
            expires_at, value = item
            if expires_at <= now:
                self._items.pop(key, None)
                self._misses += 1
                self._evictions += 1
                return None
            self._items.move_to_end(key)
            self._hits += 1
            return value

    def set(self, key: str, value: T, *, ttl_seconds: float | None = None) -> None:
        ttl = self.ttl_seconds if ttl_seconds is None else max(0.001, float(ttl_seconds))
        with self._lock:
            self._items[key] = (time.monotonic() + ttl, value)
            self._items.move_to_end(key)
            while len(self._items) > self.max_entries:
                self._items.popitem(last=False)
                self._evictions += 1

    def get_or_set(self, key: str, factory: Callable[[], T], *, ttl_seconds: float | None = None) -> T:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = factory()
        self.set(key, value, ttl_seconds=ttl_seconds)
        return value

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def stats(self) -> CacheStats:
        with self._lock:
            return CacheStats(
                size=len(self._items),
                max_entries=self.max_entries,
                hits=self._hits,
                misses=self._misses,
                evictions=self._evictions,
            )


@dataclass
class WorkHandle(Generic[R]):
    work_id: str
    workload: str
    _done: threading.Event = field(default_factory=threading.Event, repr=False)
    _result: R | None = field(default=None, repr=False)
    _error: BaseException | None = field(default=None, repr=False)

    def set_result(self, value: R) -> None:
        self._result = value
        self._done.set()

    def set_error(self, exc: BaseException) -> None:
        self._error = exc
        self._done.set()

    def result(self, timeout: float | None = None) -> R:
        if not self._done.wait(timeout=timeout):
            raise TimeoutError(f"work item {self.work_id} did not finish")
        if self._error is not None:
            raise self._error
        return self._result  # type: ignore[return-value]

    @property
    def done(self) -> bool:
        return self._done.is_set()


@dataclass
class _WorkItem(Generic[R]):
    handle: WorkHandle[R]
    fn: Callable[..., R]
    args: tuple[Any, ...]
    kwargs: dict[str, Any]


class BackgroundWorkerPool:
    """Bounded worker pool for non-critical background work."""

    def __init__(self, *, name: str, max_workers: int = 2, queue_size: int = 128) -> None:
        self.name = name
        self.max_workers = max(1, int(max_workers))
        self._queue: queue.Queue[_WorkItem[Any] | None] = queue.Queue(maxsize=max(1, queue_size))
        self._workers: list[threading.Thread] = []
        self._started = False
        self._lock = threading.Lock()
        self._submitted = 0
        self._completed = 0
        self._failed = 0

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self._started = True
            for idx in range(self.max_workers):
                worker = threading.Thread(
                    target=self._run_worker,
                    name=f"jarvis-worker-{self.name}-{idx}",
                    daemon=True,
                )
                worker.start()
                self._workers.append(worker)

    def stop(self, *, timeout: float = 2.0) -> None:
        with self._lock:
            if not self._started:
                return
            self._started = False
            workers = list(self._workers)
        for _ in workers:
            try:
                self._queue.put_nowait(None)
            except queue.Full:
                pass
        deadline = time.monotonic() + max(0.0, timeout)
        for worker in workers:
            remaining = max(0.0, deadline - time.monotonic())
            worker.join(timeout=remaining)
        with self._lock:
            self._workers = [w for w in self._workers if w.is_alive()]

    def submit(
        self,
        fn: Callable[..., R],
        *args: Any,
        workload: str = "background",
        **kwargs: Any,
    ) -> WorkHandle[R]:
        self.start()
        handle: WorkHandle[R] = WorkHandle(
            work_id=f"{workload}:{uuid.uuid4().hex[:10]}",
            workload=workload,
        )
        item = _WorkItem(handle=handle, fn=fn, args=args, kwargs=kwargs)
        try:
            self._queue.put_nowait(item)
            with self._lock:
                self._submitted += 1
        except queue.Full as exc:
            handle.set_error(RuntimeError(f"{self.name} worker queue full"))
        return handle

    def stats(self) -> dict[str, Any]:
        with self._lock:
            alive = sum(1 for w in self._workers if w.is_alive())
            return {
                "name": self.name,
                "max_workers": self.max_workers,
                "alive_workers": alive,
                "queue_size": self._queue.qsize(),
                "submitted": self._submitted,
                "completed": self._completed,
                "failed": self._failed,
            }

    def _run_worker(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                self._queue.task_done()
                return
            try:
                item.handle.set_result(item.fn(*item.args, **item.kwargs))
                with self._lock:
                    self._completed += 1
            except BaseException as exc:
                item.handle.set_error(exc)
                with self._lock:
                    self._failed += 1
            finally:
                self._queue.task_done()


class BatchProcessor(Generic[T, R]):
    """Collects items into bounded batches and flushes by size or age."""

    def __init__(
        self,
        processor: Callable[[list[T]], R],
        *,
        max_batch_size: int = 8,
        max_delay_seconds: float = 0.025,
    ) -> None:
        self.processor = processor
        self.max_batch_size = max(1, int(max_batch_size))
        self.max_delay_seconds = max(0.0, float(max_delay_seconds))
        self._items: list[T] = []
        self._first_at: float | None = None
        self._lock = threading.Lock()

    def add(self, item: T) -> R | None:
        with self._lock:
            if not self._items:
                self._first_at = time.monotonic()
            self._items.append(item)
            should_flush = len(self._items) >= self.max_batch_size
            if self._first_at is not None:
                should_flush = should_flush or (
                    time.monotonic() - self._first_at >= self.max_delay_seconds
                )
            if not should_flush:
                return None
            batch = self._take_locked()
        return self.processor(batch)

    def flush(self) -> R | None:
        with self._lock:
            if not self._items:
                return None
            batch = self._take_locked()
        return self.processor(batch)

    def _take_locked(self) -> list[T]:
        batch = list(self._items)
        self._items.clear()
        self._first_at = None
        return batch


class StreamChannel(Generic[T]):
    """Small streaming channel with stale-chunk shedding."""

    def __init__(self, *, max_size: int = 64) -> None:
        self._queue = LowLatencyQueue[T](max_size=max_size, drop_oldest=True)
        self._closed = threading.Event()

    def push(self, item: T) -> bool:
        if self._closed.is_set():
            return False
        return self._queue.put(item)

    def close(self) -> None:
        self._closed.set()

    def __iter__(self) -> Iterator[T]:
        while not self._closed.is_set() or self._queue.qsize() > 0:
            try:
                yield self._queue.get(timeout=0.05)
            except queue.Empty:
                continue

    def stats(self) -> QueueStats:
        return self._queue.stats()


class StreamingPipeline(Generic[T]):
    """Composable streaming transform pipeline."""

    def __init__(self) -> None:
        self._stages: list[Callable[[Any], Any]] = []

    def add_stage(self, stage: Callable[[Any], Any]) -> "StreamingPipeline[T]":
        self._stages.append(stage)
        return self

    def run(self, source: Iterable[T]) -> Iterator[Any]:
        for chunk in source:
            value: Any = chunk
            for stage in self._stages:
                value = stage(value)
                if value is None:
                    break
            if value is not None:
                yield value
