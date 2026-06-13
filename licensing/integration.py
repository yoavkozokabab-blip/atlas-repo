"""Glue between the desktop API and the licensing client.

Wiring into ``jarvis_desktop/api.py`` is intentionally **opt-in**: gating only
activates when ``ATLAS_LICENSING_ENABLED`` is truthy. This lets the feature
ship without changing existing behaviour (or tests) until a deployed backend
and a sign-in flow that supplies the user's email are in place.

Enable with::

    ATLAS_LICENSING_ENABLED=1
    ATLAS_SITE_URL=https://your-atlas-domain.com

Public helpers used by api.py:
  * ``require_feature(name)``   → None if allowed, else an "upgrade required" dict.
  * ``apply_scan_limit(files)`` → (files_to_scan, limit_notice_or_None).
  * ``record_repo_scanned(...)``→ best-effort repo_scanned analytics event.
"""

from __future__ import annotations

import os
from typing import Any, Iterable, Optional


def licensing_enabled() -> bool:
    return os.getenv("ATLAS_LICENSING_ENABLED", "").lower() in {"1", "true", "yes", "on"}


def _client():
    from . import licensing  # singleton

    return licensing


def require_feature(feature: str) -> Optional[dict[str, Any]]:
    """Return None when the feature is permitted, else a structured block dict.

    The block dict mirrors api.py's ``{"ok": False, ...}`` convention so callers
    can simply ``return`` it.
    """
    if not licensing_enabled():
        return None
    gate = _client().feature_gate(feature)
    if gate.allowed:
        return None
    return {
        "ok": False,
        "code": "upgrade_required",
        "error": gate.prompt,
        "message": gate.prompt,
        "feature": feature,
        "plan": gate.plan,
        "upgrade_url": f"{os.getenv('ATLAS_SITE_URL', 'https://atlas.dev').rstrip('/')}/pricing",
    }


def apply_scan_limit(files: Iterable[Any]):
    """Truncate the file list for Free users. Returns (files, notice|None)."""
    files = list(files)
    if not licensing_enabled():
        return files, None
    limited, allowed = _client().enforce_scan_limit(files)
    if not limited:
        return allowed, None
    cap = len(allowed)
    notice = {
        "code": "free_file_limit",
        "scanned": cap,
        "found": len(files),
        "message": (
            f"Free plan scans up to {cap} files per repo. "
            f"{len(files) - cap} more were skipped — upgrade to Pro for unlimited scanning."
        ),
        "upgrade_url": f"{os.getenv('ATLAS_SITE_URL', 'https://atlas.dev').rstrip('/')}/pricing",
    }
    return allowed, notice


def record_repo_scanned(file_count: int, language_breakdown: Optional[dict[str, Any]] = None) -> None:
    """Emit a repo_scanned analytics event (best-effort, no-op when disabled)."""
    if not licensing_enabled():
        return
    try:
        _client().track(
            "repo_scanned",
            {"file_count": int(file_count), "language_breakdown": language_breakdown or {}},
        )
    except Exception:
        pass
