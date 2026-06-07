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


_store = _InMemoryStore()


def check_rate_limit(key: str, max_calls: int, window_seconds: int) -> bool:
    """Return True if allowed; False if rate-limited."""
    return _store.is_allowed(key, max_calls, window_seconds)
