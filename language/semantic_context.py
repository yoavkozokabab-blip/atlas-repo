"""Gather local context for semantic command understanding."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SemanticContext:
    last_intent: str = ""
    last_command: str = ""
    workspace_mode: str = ""
    recent_suggestions: tuple[str, ...] = ()
    screen_summary: str = ""
    memory_hints: tuple[str, ...] = ()
    active_app: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


def build_semantic_context(session_context: object | None = None) -> SemanticContext:
    ctx = SemanticContext()
    if session_context is not None:
        try:
            ctx.last_intent = str(getattr(session_context, "last_intent", "") or "")
        except Exception:
            pass
        try:
            ctx.last_command = str(getattr(session_context, "last_command", "") or "")
        except Exception:
            pass
    try:
        from conversation.context_store import get_classify_context

        conv = get_classify_context() or {}
        if conv.get("last_intent"):
            ctx.last_intent = str(conv["last_intent"])
        if conv.get("last_command"):
            ctx.last_command = str(conv["last_command"])
        sug = conv.get("suggestions") or conv.get("recent_suggestions")
        if isinstance(sug, list):
            ctx.recent_suggestions = tuple(str(s)[:80] for s in sug[:5])
    except Exception:
        pass
    try:
        from operating.workspace_context import get_cached_mode

        ctx.workspace_mode = str(get_cached_mode() or "")
    except Exception:
        pass
    try:
        from operating.workspace_context import build_activity_snapshot

        snap = build_activity_snapshot()
        if snap.summary:
            ctx.screen_summary = str(snap.summary)[:300]
        if snap.window_title:
            ctx.active_app = str(snap.window_title)[:120]
        if snap.mode:
            ctx.workspace_mode = str(snap.mode)
    except Exception:
        pass
    try:
        from vision.active_window import get_active_window_metadata

        meta = get_active_window_metadata()
        if meta.title and not ctx.active_app:
            ctx.active_app = str(meta.title)[:120]
    except Exception:
        pass
    try:
        from brain.memory import safe_memory_summary

        mem = safe_memory_summary()
        if mem:
            ctx.memory_hints = (str(mem)[:200],)
    except Exception:
        pass
    try:
        from memory.graph_hints import recent_graph_hints

        hints = recent_graph_hints(limit=3)
        if hints:
            ctx.memory_hints = ctx.memory_hints + tuple(str(h)[:120] for h in hints)
    except Exception:
        pass
    title_low = ctx.active_app.lower()
    if "cursor" in title_low or "code" in title_low:
        ctx.extra["ide_active"] = True
    return ctx
