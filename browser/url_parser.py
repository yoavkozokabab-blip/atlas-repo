"""URL parsing utilities for browser intent routing."""

from __future__ import annotations

import re

_URL_RE = re.compile(r"(https?://[^\s]+|www\.[^\s]+)", re.I)


def extract_first_url(text: str) -> str:
    m = _URL_RE.search(text or "")
    if not m:
        return ""
    return m.group(1).strip()


def normalize_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    if raw.lower().startswith("http://") or raw.lower().startswith("https://"):
        return raw
    if raw.lower().startswith("www."):
        return f"https://{raw}"
    return raw


def is_probable_url(text: str) -> bool:
    raw = (text or "").strip().lower()
    if not raw:
        return False
    if raw.startswith("http://") or raw.startswith("https://") or raw.startswith("www."):
        return True
    return bool(re.search(r"\.[a-z]{2,}(/|$)", raw))

