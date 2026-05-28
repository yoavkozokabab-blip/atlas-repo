"""User preferences store (data/preferences.json)."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import DATA_DIR, PREFERENCES_PATH
from brain.storage_safe import UnsafeStorageError, validate_safe_key, validate_safe_value
from core.logger import setup_logger

logger = setup_logger("jarvis.preferences")

BACKUPS_DIR = DATA_DIR / "backups"


def validate_preference_safe(key: str, value: str) -> None:
    validate_safe_key(key)
    validate_safe_value(key, value)


class PreferencesStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or PREFERENCES_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        BACKUPS_DIR.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not load preferences: %s", exc)
            return {}

    def _backup(self) -> None:
        if not self.path.is_file():
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = BACKUPS_DIR / f"preferences_{stamp}.json"
        try:
            shutil.copy2(self.path, dest)
        except OSError as exc:
            logger.warning("Preferences backup failed: %s", exc)

    def _save(self, data: dict[str, Any]) -> None:
        self._backup()
        self.path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def get_preference(self, key: str) -> Any | None:
        return self._load().get(key)

    def set_preference(self, key: str, value: str) -> None:
        validate_preference_safe(key, value)
        data = self._load()
        data[key] = {
            "value": value,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save(data)

    def delete_preference(self, key: str) -> bool:
        data = self._load()
        if key not in data:
            return False
        del data[key]
        self._save(data)
        return True

    def list_preferences(self) -> dict[str, Any]:
        return self._load()


_store: PreferencesStore | None = None


def get_preferences() -> PreferencesStore:
    global _store
    if _store is None:
        _store = PreferencesStore()
    return _store


def reset_preferences_store() -> None:
    global _store
    _store = None
