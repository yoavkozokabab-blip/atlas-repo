"""Notification throttling helpers for runtime truthfulness warnings."""

from __future__ import annotations

import hashlib
import time
from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass(frozen=True)
class NotificationThrottleResult:
    allowed: bool
    collapsed_count: int = 0
    reason: str = ""
    collapsed_suffix: str = ""


class NotificationThrottle:
    """Suppresses duplicate/noisy notifications while preserving severity signal."""

    def __init__(
        self,
        *,
        max_per_minute: int = 12,
        default_cooldown_seconds: float = 20.0,
        severity_cooldowns: dict[str, float] | None = None,
    ) -> None:
        self._max_per_minute = max(1, int(max_per_minute))
        self._default_cooldown = max(0.0, float(default_cooldown_seconds))
        self._severity_cooldowns = {
            "critical": 0.0,
            "error": 5.0,
            "warning": 20.0,
            "info": 30.0,
            **(severity_cooldowns or {}),
        }
        self._bucket_times: deque[float] = deque()
        self._last_seen_by_key: dict[str, float] = {}
        self._collapse_counts: defaultdict[str, int] = defaultdict(int)

    def should_emit(
        self,
        *,
        title: str,
        message: str,
        severity: str = "info",
        group: str = "",
    ) -> NotificationThrottleResult:
        now = time.monotonic()
        self._prune_bucket(now)
        if len(self._bucket_times) >= self._max_per_minute:
            key = self._key(title=title, message=message, severity=severity, group=group)
            self._collapse_counts[key] += 1
            return NotificationThrottleResult(
                allowed=False,
                collapsed_count=self._collapse_counts[key],
                reason="rate_limited",
            )

        key = self._key(title=title, message=message, severity=severity, group=group)
        cooldown = self._severity_cooldowns.get(severity.lower(), self._default_cooldown)
        last = self._last_seen_by_key.get(key, 0.0)
        if (now - last) < cooldown:
            self._collapse_counts[key] += 1
            return NotificationThrottleResult(
                allowed=False,
                collapsed_count=self._collapse_counts[key],
                reason="cooldown_duplicate",
            )

        collapsed = self._collapse_counts.pop(key, 0)
        self._last_seen_by_key[key] = now
        self._bucket_times.append(now)
        suffix = f" (repeated {collapsed}x while throttled)" if collapsed > 0 else ""
        return NotificationThrottleResult(
            allowed=True,
            collapsed_count=collapsed,
            collapsed_suffix=suffix,
        )

    def _prune_bucket(self, now: float) -> None:
        while self._bucket_times and (now - self._bucket_times[0]) > 60.0:
            self._bucket_times.popleft()

    @staticmethod
    def _key(*, title: str, message: str, severity: str, group: str) -> str:
        canonical = f"{group.lower()}|{severity.lower()}|{title.strip().lower()}|{message.strip().lower()}"
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

