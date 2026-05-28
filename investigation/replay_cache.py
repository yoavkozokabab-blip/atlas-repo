"""Small in-memory cache for deterministic replay artifacts."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

_CACHE: "OrderedDict[str, Any]" = OrderedDict()
_MAX = 64


def get_cache(key: str) -> Any | None:
    if key not in _CACHE:
        return None
    value = _CACHE.pop(key)
    _CACHE[key] = value
    return value


def set_cache(key: str, value: Any) -> None:
    if key in _CACHE:
        _CACHE.pop(key)
    _CACHE[key] = value
    while len(_CACHE) >= _MAX:
        _CACHE.popitem(last=False)


def clear_cache() -> None:
    _CACHE.clear()


def cache_status() -> str:
    return f"Replay cache: entries={len(_CACHE)} max={_MAX}"
