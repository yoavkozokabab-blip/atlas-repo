"""Local fact memory (JSON) — read/write with safety checks."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import DATA_DIR, MEMORY_PATH
from brain.storage_safe import UnsafeStorageError, validate_safe_key, validate_safe_value
from core.logger import setup_logger

logger = setup_logger("jarvis.memory")

BACKUPS_DIR = DATA_DIR / "backups"


def validate_safe_memory(key: str, value: str) -> None:
    """Public validator for memory entries."""
    validate_safe_key(key)
    validate_safe_value(key, value)


class MemoryStore:
    """Persistent key/value facts in data/memory.json."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or MEMORY_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        BACKUPS_DIR.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {"entries": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "entries" in data:
                if isinstance(data["entries"], dict):
                    return data
            if isinstance(data, dict):
                return {"entries": data}
            logger.warning("memory.json invalid shape; resetting entries.")
            return {"entries": {}}
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not load memory: %s", exc)
            return {"entries": {}}

    def _backup(self) -> None:
        if not self.path.is_file():
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = BACKUPS_DIR / f"memory_{stamp}.json"
        try:
            shutil.copy2(self.path, dest)
        except OSError as exc:
            logger.warning("Memory backup failed: %s", exc)

    def _save(self, data: dict[str, Any]) -> None:
        self._backup()
        self.path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def add_memory(self, key: str, value: str, category: str = "fact") -> None:
        validate_safe_memory(key, value)
        data = self._load()
        entries: dict[str, Any] = data.setdefault("entries", {})
        now = datetime.now(timezone.utc).isoformat()
        entries[key] = {
            "value": value,
            "category": category,
            "created_at": entries.get(key, {}).get("created_at", now),
            "updated_at": now,
        }
        self._save(data)

    def update_memory(self, key: str, value: str) -> bool:
        validate_safe_memory(key, value)
        data = self._load()
        entries: dict[str, Any] = data.get("entries", {})
        if key not in entries:
            return False
        entries[key]["value"] = value
        entries[key]["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save(data)
        return True

    def delete_memory(self, key: str) -> bool:
        data = self._load()
        entries: dict[str, Any] = data.get("entries", {})
        if key not in entries:
            return False
        del entries[key]
        self._save(data)
        return True

    def list_memory(self, category: str | None = None) -> list[dict[str, Any]]:
        entries = self._load().get("entries", {})
        out: list[dict[str, Any]] = []
        for key, meta in sorted(entries.items()):
            if category and meta.get("category") != category:
                continue
            out.append({"key": key, **meta})
        return out

    def search_memory(self, query: str) -> list[dict[str, Any]]:
        q = query.lower()
        hits: list[dict[str, Any]] = []
        for item in self.list_memory():
            blob = f"{item['key']} {item.get('value', '')} {item.get('category', '')}".lower()
            if q in blob:
                hits.append(item)
        return hits

    def export_memory(self) -> dict[str, Any]:
        return self._load()

    def get(self, key: str) -> dict[str, Any] | None:
        return self._load().get("entries", {}).get(key)


_store: MemoryStore | None = None


def get_memory() -> MemoryStore:
    """Return memory backend (Phase 34 personal store when MEMORY_ENABLED)."""
    from config import MEMORY_ENABLED

    if MEMORY_ENABLED:
        from memory.store import get_personal_memory

        return get_personal_memory()  # type: ignore[return-value]
    global _store
    if _store is None:
        _store = MemoryStore()
    return _store


def reset_memory_store() -> None:
    global _store
    _store = None


def safe_memory_summary() -> dict[str, Any]:
    """Non-secret summary for LLM/session context."""
    mem = get_memory()
    prefs_keys: list[str] = []
    facts: list[str] = []
    for item in mem.list_memory():
        key = item["key"]
        cat = item.get("category", "fact")
        if cat == "preference":
            prefs_keys.append(key)
        else:
            val = str(item.get("value", ""))[:80]
            try:
                validate_safe_memory(key, val)
                facts.append(f"{key}={val}")
            except UnsafeStorageError:
                facts.append(f"{key}=[redacted]")
    return {"fact_summaries": facts[:15], "preference_keys": prefs_keys[:10]}
