"""Forward privacy-safe launch funnel events to the Atlas website /api/events."""

from __future__ import annotations

import json
import os
import re
import threading
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

_ALLOWED = frozenset({
    "desktop_opened",
    "desktop_installed",
    "desktop_login_started",
    "desktop_login_success",
    "desktop_login_failed",
    "desktop_me_success",
    "desktop_me_failed",
    "repo_connected",
    "first_context_generated",
    "agent_context_injected",
    "cursor_connected",
    "claude_connected",
    "codex_connected",
    "cursor_used",
    "claude_used",
    "codex_used",
    "atlas_session_started",
    "atlas_first_tool_call",
    "atlas_tool_call",
    "atlas_context_served",
    "atlas_context_used",
    "atlas_session_finished",
})

_ALLOWED_META = frozenset({
    "reason", "error_code", "page", "target", "agent", "duplicate", "mode", "ok", "first",
    "http_status", "packet", "installation_id", "tool", "session_sec", "source_kind",
})
_BLOCKED = re.compile(r"password|token|prompt|secret|hash|api[_-]?key|authorization|repo_path|source_code|email", re.I)

_EVENT_MAP = {
    "app_started": "desktop_opened",
    "scan_completed": "repo_connected",
    "export_created": "first_context_generated",
}


def _web_base() -> str:
    return os.environ.get("ATLAS_WEB_URL", "https://atlas-repo-chi.vercel.app").rstrip("/")


def _enabled() -> bool:
    flag = os.environ.get("ATLAS_CLOUD_ANALYTICS", "1").strip().lower()
    return flag not in {"0", "false", "no", "off"}


def _scrub_metadata(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, value in (raw or {}).items():
        if key not in _ALLOWED_META or _BLOCKED.search(key):
            continue
        if isinstance(value, (bool, int, float)):
            out[key] = value
        else:
            text = str(value)[:120]
            if _BLOCKED.search(text):
                continue
            out[key] = text
    return out


def _post(payload: Dict[str, Any]) -> None:
    if not _enabled():
        return
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{_web_base()}/api/events",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=4) as resp:  # noqa: S310 — configured website endpoint
        resp.read(256)


def track_cloud_event(
    event_name: str,
    *,
    source: str = "desktop",
    anonymous_id: Optional[str] = None,
    app_version: Optional[str] = None,
    platform: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Fire-and-forget cloud analytics. Never raises."""
    name = str(event_name or "").strip().lower()
    mapped = _EVENT_MAP.get(name, name)
    if mapped not in _ALLOWED:
        return {"ok": False, "skipped": True}
    meta = _scrub_metadata(metadata)
    if anonymous_id and "installation_id" not in meta:
        meta["installation_id"] = str(anonymous_id)[:64]
    payload = {
        "event_name": mapped,
        "source": source,
        "anonymous_id": anonymous_id,
        "app_version": app_version,
        "platform": platform,
        "metadata": meta,
    }

    def _send() -> None:
        try:
            _post(payload)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            pass

    threading.Thread(target=_send, daemon=True).start()
    return {"ok": True, "queued": True, "event_name": mapped}
