"""Persistent session state for follow-up commands."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from config import TRADING_PROJECT_ROOT
from core.logger import setup_logger
from core.persistent_json import atomic_write_json, load_json

logger = setup_logger("jarvis.session")


def _session_path() -> Path:
    from config import SESSION_STATE_PATH

    return Path(SESSION_STATE_PATH)


class SessionState(BaseModel):
    """Safe, non-secret session context."""

    current_project_root: str = ""
    last_command_text: str = ""
    last_intent: str = ""
    last_result_summary: str = ""
    last_opened_file: str = ""
    last_opened_log: str = ""
    last_report_path: str = ""
    last_error_search: str = ""
    pending_confirmation_id: str = ""
    pending_confirmation_action: str = ""
    activity_mode: str = ""
    last_workspace_snapshot: str = ""
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def load(cls) -> SessionState:
        path = _session_path()

        def _validate(raw: Any) -> dict[str, Any] | None:
            if not isinstance(raw, dict):
                return None
            return raw

        data = load_json(path, default={}, validator=_validate)
        if not data:
            state = cls._fresh()
            state.save()
            return state
        try:
            state = cls.model_validate(data)
            if not state.current_project_root:
                state.current_project_root = str(TRADING_PROJECT_ROOT)
            return state
        except ValueError as exc:
            logger.warning("Session schema invalid; starting fresh: %s", exc)
            state = cls._fresh()
            state.save()
            return state

    @classmethod
    def _fresh(cls) -> SessionState:
        now = datetime.now(timezone.utc).isoformat()
        return cls(
            current_project_root=str(TRADING_PROJECT_ROOT),
            created_at=now,
            updated_at=now,
        )

    def save(self) -> None:
        self.updated_at = datetime.now(timezone.utc).isoformat()
        path = _session_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            payload = json.loads(self.model_dump_json())
            atomic_write_json(path, payload)
        except (OSError, ValueError) as exc:
            logger.warning("Failed to save session state: %s", exc)

    def set_pending_confirmation(self, confirmation_id: str, action_name: str) -> None:
        self.pending_confirmation_id = confirmation_id
        self.pending_confirmation_action = action_name

    def clear_pending_confirmation(self) -> None:
        self.pending_confirmation_id = ""
        self.pending_confirmation_action = ""

    def update_from_result(
        self,
        *,
        raw_text: str,
        intent: str,
        summary: str,
        data: dict[str, Any],
    ) -> None:
        self.last_command_text = raw_text
        self.last_intent = intent
        self.last_result_summary = summary[:500]

        path = data.get("path") or data.get("file_path") or ""
        if path:
            self._assign_path(str(path), intent)

        if data.get("search_query"):
            self.last_error_search = str(data["search_query"])

        if data.get("activity_mode"):
            self.activity_mode = str(data["activity_mode"])[:32]
        if data.get("workspace_mode"):
            self.activity_mode = str(data["workspace_mode"])[:32]
        if data.get("last_workspace_snapshot"):
            self.last_workspace_snapshot = str(data["last_workspace_snapshot"])[:200]

    def _assign_path(self, path: str, intent: str) -> None:
        p = Path(path)
        suffix = p.suffix.lower()
        if suffix in {".log", ".txt"} or "log" in intent:
            self.last_opened_log = path
        elif "report" in intent:
            self.last_report_path = path
        else:
            self.last_opened_file = path
        if suffix in {".log", ".txt"}:
            self.last_opened_log = path

    def safe_path(self, field: str) -> Path | None:
        """Return path from session field if under project root."""
        value = getattr(self, field, "") or ""
        if not value:
            return None
        try:
            resolved = Path(value).resolve()
            root = Path(self.current_project_root or TRADING_PROJECT_ROOT).resolve()
            if root not in resolved.parents and resolved != root:
                return None
            return resolved
        except (OSError, ValueError):
            return None
