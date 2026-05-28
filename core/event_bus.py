"""In-process async event bus with bounded low-latency delivery."""

from __future__ import annotations

import asyncio
import inspect
import queue
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable

from config import (
    EVENT_BUS_BATCH_SIZE,
    EVENT_BUS_MAX_QUEUE_SIZE,
    EVENT_BUS_WORKER_COUNT,
)
from core.logger import setup_logger
from core.performance import LowLatencyQueue

logger = setup_logger("jarvis.core.event_bus")

EventHandler = Callable[..., Any]


@dataclass(frozen=True)
class Event:
    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_monotonic: float = field(default_factory=time.monotonic)


class EventBus:
    """Pub/sub bus with sync compatibility and async background dispatch."""

    def __init__(
        self,
        *,
        queue_size: int | None = None,
        batch_size: int | None = None,
        worker_count: int | None = None,
    ) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._lock = threading.RLock()
        self._queue: LowLatencyQueue[Event] = LowLatencyQueue(
            queue_size or EVENT_BUS_MAX_QUEUE_SIZE,
            drop_oldest=True,
        )
        self._batch_size = max(1, int(batch_size or EVENT_BUS_BATCH_SIZE))
        self._worker_count = max(1, int(worker_count or EVENT_BUS_WORKER_COUNT))
        self._stop = threading.Event()
        self._workers: list[threading.Thread] = []
        self._published = 0
        self._handled = 0
        self._failed = 0

    def subscribe(self, event: str, handler: EventHandler) -> None:
        with self._lock:
            if handler not in self._handlers[event]:
                self._handlers[event].append(handler)

    def unsubscribe(self, event: str, handler: EventHandler) -> None:
        with self._lock:
            handlers = self._handlers.get(event)
            if handlers and handler in handlers:
                handlers.remove(handler)

    def publish(self, event: str, **payload: Any) -> None:
        """Synchronous compatibility path: invoke handlers in the caller thread."""
        self._dispatch(Event(event, dict(payload)))

    def publish_nowait(self, event: str, **payload: Any) -> bool:
        self.start()
        queued = self._queue.put(Event(event, dict(payload)))
        with self._lock:
            self._published += 1
        try:
            from services.observability import get_observability

            get_observability().structured_log(
                "event_bus.publish",
                event=event,
                queued=queued,
                queue_size=self._queue.qsize(),
            )
        except Exception:
            pass
        return queued

    async def publish_async(self, event: str, **payload: Any) -> bool:
        """Async API for callers already inside an event loop."""
        return self.publish_nowait(event, **payload)

    def start(self) -> None:
        if self._workers and any(w.is_alive() for w in self._workers):
            return
        self._stop.clear()
        self._workers = []
        for idx in range(self._worker_count):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"jarvis-event-bus-{idx}",
                daemon=True,
            )
            worker.start()
            self._workers.append(worker)

    def stop(self, *, timeout: float = 2.0) -> None:
        self._stop.set()
        deadline = time.monotonic() + max(0.0, timeout)
        for worker in list(self._workers):
            remaining = max(0.0, deadline - time.monotonic())
            worker.join(timeout=remaining)
        self._workers = [w for w in self._workers if w.is_alive()]

    def stats(self) -> dict[str, Any]:
        q = self._queue.stats()
        with self._lock:
            return {
                "published": self._published,
                "handled": self._handled,
                "failed": self._failed,
                "queue": q.__dict__,
                "handlers": {name: len(items) for name, items in self._handlers.items()},
                "workers": sum(1 for w in self._workers if w.is_alive()),
                "batch_size": self._batch_size,
            }

    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            try:
                batch = self._queue.get_batch(max_items=self._batch_size, timeout=0.05)
            except queue.Empty:
                continue
            try:
                from services.runtime_monitor import get_runtime_monitor

                get_runtime_monitor().heartbeat("event_bus")
            except Exception:
                pass
            for event in batch:
                self._dispatch(event)

    def _dispatch(self, event: Event) -> None:
        with self._lock:
            handlers = list(self._handlers.get(event.name, ()))
            handlers.extend(self._handlers.get("*", ()))
        for handler in handlers:
            try:
                result = handler(**event.payload)
                if inspect.isawaitable(result):
                    asyncio.run(result)
                with self._lock:
                    self._handled += 1
            except Exception as exc:
                with self._lock:
                    self._failed += 1
                logger.debug("Event handler failed for %s: %s", event.name, exc)
                try:
                    from services.observability import get_observability

                    get_observability().record_failure(
                        component="event_bus",
                        error=exc,
                        context={"event": event.name, "event_id": event.event_id},
                    )
                except Exception:
                    pass


_event_bus = EventBus()


def get_event_bus() -> EventBus:
    return _event_bus


def reset_event_bus() -> None:
    global _event_bus
    _event_bus.stop()
    _event_bus = EventBus()
