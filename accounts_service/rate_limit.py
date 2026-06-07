"""Atlas Accounts Service — simple in-memory rate limiter (dev/single-process).

In production, replace the store with a Redis backend. The interface is
identical — swap `_InMemoryStore` for a `_RedisStore` without changing callers.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock
from typing import Deque, Dict


class _InMemoryStore:
    """Sliding-window rate limiter backed by an in-process deque."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._windows: Dict[str, Deque[float]] = defaultdict(deque)

    def is_allowed(self, key: str, max_calls: int, window_seconds: int) -> bool:
        """Return True if the call is allowed; False if rate-limited."""
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            dq = self._windows[key]
            # Evict expired entries
            while dq and dq[0] < cutoff:
                dq.popleft()
            if len(dq) >= max_calls:
                return False
            dq.append(now)
            return True

    def prune_stale_keys(self, max_idle_seconds: int) -> int:
        """Drop keys whose last event is older than max_idle_seconds."""
        now = time.monotonic()
        cutoff = now - max_idle_seconds
        removed = 0
        with self._lock:
            stale = [
                key for key, dq in self._windows.items()
                if not dq or dq[-1] < cutoff
            ]
            for key in stale:
                del self._windows[key]
                removed += 1
        return removed


_store = _InMemoryStore()
_prune_counter = 0


def check_rate_limit(key: str, max_calls: int, window_seconds: int) -> bool:
    """Return True if allowed; False if rate-limited."""
    global _prune_counter
    allowed = _store.is_allowed(key, max_calls, window_seconds)
    _prune_counter += 1
    if _prune_counter % 32 == 0:
        _store.prune_stale_keys(max(window_seconds * 4, 3600))
    return allowed


def prune_rate_limit_keys(max_idle_seconds: int = 3600) -> int:
    """Explicit prune hook for tests and maintenance."""
    return _store.prune_stale_keys(max_idle_seconds)


def reset_rate_limit_store() -> None:
    """Clear all rate-limit windows (tests only)."""
    global _prune_counter
    with _store._lock:
        _store._windows.clear()
    _prune_counter = 0
