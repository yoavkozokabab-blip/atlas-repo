"""Read-only workspace / activity awareness (no execution)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import (
    PROJECT_ROOT,
    TRADING_PROJECT_ROOT,
    WORKSPACE_AWARENESS_ENABLED,
    WORKSPACE_CONTEXT_PATH,
)
from core.logger import setup_logger
from core.session import SessionState
from vision.active_window import ActiveWindowMeta, get_active_window_metadata
from vision.redaction import redact_sensitive_text

logger = setup_logger("jarvis.operating.workspace")

VALID_MODES = frozenset({"coding", "trading", "studying", "focus", "idle"})

_CODING_PROCESSES = (
    "cursor",
    "code",
    "devenv",
    "pycharm",
    "idea",
    "cmd",
    "powershell",
    "windowsterminal",
    "wt.exe",
)
_CODING_TITLE = (
    "jarvis",
    "local_jarvis",
    "visual studio",
    ".py",
    "github",
)
_TRADING_TITLE = (
    "trading",
    "dashboard",
    "tradingview",
    "algo",
    "paper",
    "8077",
)
_STUDY_TITLE = (
    "chatgpt",
    "youtube",
    "coursera",
    "google",
    "study",
    "notion",
)


@dataclass
class ActivitySnapshot:
    mode: str = "idle"
    active_app: str = ""
    window_title: str = ""
    project_root: str = ""
    summary: str = ""
    updated_at: str = ""
    suggestions: list[str] = field(default_factory=list)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def infer_workspace_mode(
    *,
    process_name: str = "",
    window_title: str = "",
    project_root: str = "",
    session_mode: str = "",
) -> str:
    if session_mode in VALID_MODES and session_mode not in ("idle", ""):
        return session_mode
    proc = (process_name or "").lower()
    title = (window_title or "").lower()
    root = (project_root or "").lower().replace("\\", "/")

    if any(p in proc for p in _CODING_PROCESSES) or any(k in title for k in _CODING_TITLE):
        return "coding"
    if "final_algo" in root or any(k in title for k in _TRADING_TITLE):
        return "trading"
    if any(k in title for k in _STUDY_TITLE):
        return "studying"
    if proc in ("chrome.exe", "chrome", "msedge", "firefox", "brave"):
        if any(k in title for k in _TRADING_TITLE):
            return "trading"
        if any(k in title for k in _STUDY_TITLE):
            return "studying"
    return "idle"


def _window_summary(meta: ActiveWindowMeta) -> tuple[str, str, str]:
    if meta.error:
        return "", "", f"Window unavailable: {meta.error}"
    app = redact_sensitive_text((meta.process_name or "unknown").strip())[:80]
    title = redact_sensitive_text((meta.title or "").strip())[:120]
    if meta.is_blocked:
        return app, title, "Active window blocked for privacy."
    if not title and not app:
        return "", "", "No active window detected."
    return app, title, f"{app}: {title}" if title else app


def build_activity_snapshot(session: SessionState | None = None) -> ActivitySnapshot:
    sess = session or SessionState.load()
    meta = get_active_window_metadata()
    app, title, summary = _window_summary(meta)
    root = sess.current_project_root or str(TRADING_PROJECT_ROOT)
    mode = infer_workspace_mode(
        process_name=app,
        window_title=title,
        project_root=root,
        session_mode=sess.activity_mode or "",
    )
    from conversation.suggestion_engine import build_workspace_suggestions

    suggestions = build_workspace_suggestions(mode)
    return ActivitySnapshot(
        mode=mode,
        active_app=app,
        window_title=title,
        project_root=root,
        summary=summary,
        updated_at=_now(),
        suggestions=suggestions,
    )


def format_activity_report(snap: ActivitySnapshot) -> str:
    proj_name = Path(snap.project_root).name if snap.project_root else "n/a"
    lines = [
        "Current activity",
        f"  Mode: {snap.mode}",
        f"  Active app: {snap.active_app or 'n/a'}",
        f"  Window: {snap.window_title or 'n/a'}",
        f"  Project: {proj_name}",
        f"  Summary: {snap.summary}",
        "  Suggested next commands:",
    ]
    if snap.suggestions:
        for s in snap.suggestions[:4]:
            lines.append(f"    - {s}")
    else:
        lines.append("    - show jarvis status")
        lines.append("    - run diagnostics")
    return "\n".join(lines)


def persist_workspace_context(snap: ActivitySnapshot) -> None:
    path = Path(WORKSPACE_CONTEXT_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "mode": snap.mode,
        "active_app": snap.active_app,
        "window_title": snap.window_title,
        "project_root": snap.project_root,
        "summary": snap.summary,
        "updated_at": snap.updated_at,
    }
    try:
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.warning("Could not persist workspace context: %s", exc)


def load_workspace_context() -> dict[str, Any]:
    path = Path(WORKSPACE_CONTEXT_PATH)
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def get_cached_mode() -> str:
    ctx = load_workspace_context()
    mode = str(ctx.get("mode", "idle") or "idle")
    return mode if mode in VALID_MODES else "idle"


def refresh_workspace_context(session: SessionState | None = None) -> ActivitySnapshot | None:
    if not WORKSPACE_AWARENESS_ENABLED:
        return None
    try:
        snap = build_activity_snapshot(session)
        persist_workspace_context(snap)
        return snap
    except Exception as exc:
        logger.debug("refresh_workspace_context failed: %s", exc)
        return None


def reset_workspace_context_file() -> None:
    path = Path(WORKSPACE_CONTEXT_PATH)
    if path.is_file():
        try:
            path.unlink()
        except OSError:
            pass
