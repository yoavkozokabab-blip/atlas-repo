"""Atlas usage session tracking for RC cloud analytics."""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional

_lock = threading.Lock()
_session_start: Optional[float] = None
_first_tool_call_sent = False
_session_started_sent = False


def _installation_meta() -> Dict[str, Any]:
    try:
        from . import operations as ops

        ident = ops.get_installation_identity(touch=False)
        iid = str(ident.get("installation_id") or "")
        return {"installation_id": iid} if iid else {}
    except Exception:
        return {}


def ensure_session_started() -> None:
    global _session_start, _session_started_sent
    with _lock:
        if _session_started_sent:
            return
        _session_start = time.time()
        _session_started_sent = True
    try:
        from . import cloud_analytics as ca

        ca.track_cloud_event("atlas_session_started", metadata=_installation_meta())
    except Exception:
        pass


def track_tool_call(tool_name: str) -> None:
    global _first_tool_call_sent
    ensure_session_started()
    meta = {"tool": str(tool_name or "")[:64], **_installation_meta()}
    try:
        from . import cloud_analytics as ca

        ca.track_cloud_event("atlas_tool_call", metadata=meta)
        with _lock:
            first = not _first_tool_call_sent
            if first:
                _first_tool_call_sent = True
        if first:
            ca.track_cloud_event("atlas_first_tool_call", metadata=meta)
    except Exception:
        pass


def track_context_served(source_kind: str = "mcp") -> None:
    ensure_session_started()
    meta = {"source_kind": str(source_kind or "mcp")[:32], **_installation_meta()}
    try:
        from . import cloud_analytics as ca

        ca.track_cloud_event("atlas_context_served", metadata=meta)
    except Exception:
        pass


def track_context_used(agent: str) -> None:
    agent = str(agent or "").lower()
    event = {"cursor": "cursor_used", "claude": "claude_used", "codex": "codex_used"}.get(agent)
    if not event:
        return
    ensure_session_started()
    meta = {"agent": agent, **_installation_meta()}
    try:
        from . import cloud_analytics as ca

        ca.track_cloud_event("atlas_context_used", metadata=meta)
        ca.track_cloud_event(event, metadata=meta)
    except Exception:
        pass


def track_agent_connected(agent: str) -> None:
    agent = str(agent or "").lower()
    event = {"cursor": "cursor_connected", "claude": "claude_connected", "codex": "codex_connected"}.get(agent)
    if not event:
        return
    meta = {"agent": agent, **_installation_meta()}
    try:
        from . import cloud_analytics as ca

        ca.track_cloud_event(event, metadata=meta)
        ca.track_cloud_event("agent_context_injected", metadata=meta)
    except Exception:
        pass


def finish_session() -> None:
    global _session_start, _first_tool_call_sent, _session_started_sent
    with _lock:
        if not _session_started_sent or _session_start is None:
            return
        elapsed = max(0, int(time.time() - _session_start))
        _session_start = None
        _first_tool_call_sent = False
        _session_started_sent = False
    meta = {"session_sec": elapsed, **_installation_meta()}
    try:
        from . import cloud_analytics as ca

        ca.track_cloud_event("atlas_session_finished", metadata=meta)
    except Exception:
        pass
