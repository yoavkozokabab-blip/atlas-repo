"""Persistent desktop operator memory (Phase 63)."""

from __future__ import annotations

import json
import time

from config import DATA_DIR

_PATH = DATA_DIR / "desktop_operator_memory.json"


def _empty() -> dict:
    return {
        "active_workflow": "",
        "current_task": "",
        "recent_screens": [],
        "ui_transitions": [],
    }


def _load() -> dict:
    if not _PATH.is_file():
        return _empty()
    try:
        return json.loads(_PATH.read_text(encoding="utf-8"))
    except Exception:
        return _empty()


def _save(payload: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def snapshot() -> dict:
    return _load()


def set_active_workflow(name: str) -> None:
    payload = _load()
    payload["active_workflow"] = (name or "").strip()[:200]
    _save(payload)


def set_current_task(task: str) -> None:
    payload = _load()
    payload["current_task"] = (task or "").strip()[:500]
    _save(payload)


def add_recent_screen(summary: str, screenshot: str = "", active_app: str = "") -> None:
    payload = _load()
    row = {
        "ts": int(time.time() * 1000),
        "summary": (summary or "").strip()[:2000],
        "screenshot": (screenshot or "").strip()[:500],
        "active_app": (active_app or "").strip()[:200],
    }
    payload.setdefault("recent_screens", []).append(row)
    payload["recent_screens"] = payload["recent_screens"][-120:]
    _save(payload)


def add_ui_transition(action: str, detail: str) -> None:
    payload = _load()
    row = {
        "ts": int(time.time() * 1000),
        "action": (action or "").strip()[:120],
        "detail": (detail or "").strip()[:500],
    }
    payload.setdefault("ui_transitions", []).append(row)
    payload["ui_transitions"] = payload["ui_transitions"][-300:]
    _save(payload)
