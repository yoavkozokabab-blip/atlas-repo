"""Phase 137A — local JSONL usage persistence (no DB, no cloud)."""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, List, Optional

from .models import LocalUser, UsageEvent

_LOCK = threading.Lock()


def usage_data_dir() -> str:
    override = os.environ.get("ATLAS_USAGE_DATA_DIR", "").strip()
    if override:
        return os.path.abspath(override)
    legacy = os.environ.get("ATLAS_BILLING_DATA_DIR", "").strip()
    if legacy:
        return os.path.abspath(legacy)
    from jarvis_desktop.data_paths import desktop_data_dir

    return os.path.join(desktop_data_dir(), "usage")


class UsageStore:
    def __init__(self, directory: Optional[str] = None) -> None:
        self.dir = directory or usage_data_dir()

    @property
    def events_path(self) -> str:
        return os.path.join(self.dir, "usage_events.jsonl")

    @property
    def users_path(self) -> str:
        return os.path.join(self.dir, "users.json")

    def _append(self, path: str, row: Dict[str, Any]) -> bool:
        try:
            with _LOCK:
                os.makedirs(self.dir, exist_ok=True)
                with open(path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            return True
        except OSError:
            return False

    def _read_jsonl(self, path: str) -> List[Dict[str, Any]]:
        if not os.path.isfile(path):
            return []
        rows: List[Dict[str, Any]] = []
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        try:
                            rows.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except OSError:
            return []
        return rows

    def _read_json(self, path: str, default: Any) -> Any:
        if not os.path.isfile(path):
            return default
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError):
            return default

    def _write_json(self, path: str, doc: Any) -> bool:
        try:
            with _LOCK:
                os.makedirs(self.dir, exist_ok=True)
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(doc, fh, ensure_ascii=False, indent=2)
            return True
        except OSError:
            return False

    def record(self, event: UsageEvent) -> bool:
        return self._append(self.events_path, event.to_dict())

    def all_events(self) -> List[UsageEvent]:
        return [UsageEvent.from_dict(r) for r in self._read_jsonl(self.events_path)]

    def ensure_local_user(self) -> LocalUser:
        doc = self._read_json(self.users_path, {})
        raw = doc.get("local_owner")
        admin_flag = os.environ.get("ATLAS_ADMIN", "").strip().lower() in ("1", "true", "yes")
        if not raw:
            user = LocalUser(
                id="user_local_owner",
                role="admin" if admin_flag else "user",
                plan="FREE",
            )
            self._write_json(self.users_path, {"local_owner": user.to_dict()})
            return user
        user = LocalUser.from_dict(raw)
        if admin_flag:
            user.role = "admin"
        return user

    def reset(self) -> None:
        for p in (self.events_path, self.users_path):
            if os.path.isfile(p):
                try:
                    os.remove(p)
                except OSError:
                    pass


def default_store() -> UsageStore:
    return UsageStore(usage_data_dir())
