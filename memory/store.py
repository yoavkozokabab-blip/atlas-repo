"""Structured personal memory store (data/memory_store.json)."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import MEMORY_ENABLED, MEMORY_STORE_PATH
from memory.redaction import UnsafeMemoryError, redact_text, validate_safe_text

VALID_CATEGORIES = frozenset(
    {
        "short_term",
        "user_preference",
        "project_context",
        "task_context",
        "temporary_fact",
        "preference",
        "project",
        "workflow",
        "trading",
        "study",
        "workspace",
        "session",
        "personal_note",
        "fact",  # legacy alias
    }
)

_CATEGORY_MAP = {
    "fact": "personal_note",
    "preference": "preference",
}


@dataclass
class MemoryEntry:
    entry_id: str
    category: str
    text: str
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    source: str = "user"
    hidden: bool = False
    importance: float = 0.5
    confidence: float = 0.7
    expires_at: str = ""
    sensitive: bool = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PersonalMemoryStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or MEMORY_STORE_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {"entries": []}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("entries"), list):
                return data
            return {"entries": []}
        except (OSError, json.JSONDecodeError):
            return {"entries": []}

    def _save(self, data: dict[str, Any]) -> bool:
        try:
            self.path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            return True
        except OSError:
            return False

    def remember(
        self,
        text: str,
        *,
        category: str = "personal_note",
        tags: list[str] | None = None,
        source: str = "user",
        importance: float = 0.5,
        confidence: float = 0.7,
        ttl_seconds: int | None = None,
        sensitive: bool = False,
    ) -> MemoryEntry:
        if not MEMORY_ENABLED:
            raise UnsafeMemoryError("Memory is disabled (MEMORY_ENABLED=false).")
        validate_safe_text(text)
        safe_text = redact_text(text.strip())
        if not safe_text:
            raise UnsafeMemoryError("Nothing to remember after redaction.")
        cat = _CATEGORY_MAP.get(category, category)
        if cat not in VALID_CATEGORIES:
            cat = "personal_note"
        entry = MemoryEntry(
            entry_id=f"mem_{uuid.uuid4().hex[:10]}",
            category=cat,
            text=safe_text,
            tags=[redact_text(t, max_len=80) for t in (tags or []) if t][:10],
            created_at=_now(),
            source=source[:80],
            hidden=False,
            importance=max(0.0, min(1.0, float(importance))),
            confidence=max(0.0, min(1.0, float(confidence))),
            expires_at=(
                datetime.fromtimestamp(
                    datetime.now(timezone.utc).timestamp() + max(1, int(ttl_seconds)),
                    tz=timezone.utc,
                ).isoformat()
                if ttl_seconds is not None
                else ""
            ),
            sensitive=bool(sensitive),
        )
        data = self._load()
        entries = data.setdefault("entries", [])
        entries.append(asdict(entry))
        self._save(data)
        try:
            from memory.semantic_runtime import upsert_entry

            task_tag = next((t for t in (tags or []) if str(t).startswith("task:")), "")
            upsert_entry(
                entry_id=entry.entry_id,
                text=entry.text,
                importance=entry.importance,
                confidence=entry.confidence,
                category=entry.category,
                task_id=task_tag.split(":", 1)[1] if task_tag else "",
            )
        except Exception:
            pass
        return entry

    def forget(self, query: str) -> int:
        """Soft-delete entries matching query (id, tag, or text). Returns count hidden."""
        q = (query or "").strip().lower()
        if not q:
            return 0
        data = self._load()
        count = 0
        for row in data.get("entries", []):
            if row.get("hidden"):
                continue
            eid = str(row.get("entry_id", "")).lower()
            text = str(row.get("text", "")).lower()
            tags = [str(t).lower() for t in row.get("tags", [])]
            if q == eid or q in text or any(q in t or t == q for t in tags):
                row["hidden"] = True
                count += 1
        if count:
            self._save(data)
        return count

    def list_visible(self, *, category: str | None = None, limit: int = 50) -> list[MemoryEntry]:
        out: list[MemoryEntry] = []
        now = datetime.now(timezone.utc)
        for row in self._load().get("entries", []):
            if row.get("hidden"):
                continue
            expires_at = str(row.get("expires_at", "") or "").strip()
            if expires_at:
                try:
                    if datetime.fromisoformat(expires_at) <= now:
                        continue
                except ValueError:
                    pass
            if category and row.get("category") != category:
                continue
            try:
                out.append(MemoryEntry(**row))
            except TypeError:
                continue
            if len(out) >= limit:
                break
        return out

    def format_summary(self, *, category: str | None = None) -> str:
        items = self.list_visible(category=category)
        if not items:
            return "No memory entries (hidden entries excluded)."
        lines = [f"Personal memory ({len(items)} entries):", ""]
        for item in items:
            tags = ", ".join(item.tags) if item.tags else "-"
            lines.append(
                f"- [{item.category}] {item.entry_id} | {item.text[:200]}"
            )
            lines.append(
                f"  tags: {tags} | source: {item.source} | importance={item.importance:.2f} "
                f"| confidence={item.confidence:.2f} | sensitive={'yes' if item.sensitive else 'no'}"
            )
        return "\n".join(lines)

    # Legacy brain.memory compatibility
    def add_memory(self, key: str, value: str, category: str = "fact") -> None:
        text = f"{key}: {value}" if key and value else (value or key)
        tags = [key] if key else []
        self.remember(text, category=category, tags=tags)

    def delete_memory(self, key: str) -> bool:
        return self.forget(key) > 0

    def list_memory(self, category: str | None = None) -> list[dict[str, Any]]:
        return [
            {
                "key": e.entry_id,
                "value": e.text,
                "category": e.category,
                "tags": e.tags,
                "created_at": e.created_at,
            }
            for e in self.list_visible(category=category)
        ]

    def search_memory(self, query: str) -> list[dict[str, Any]]:
        from memory.search import search_memory_entries

        return search_memory_entries(query, store=self)

    def semantic_search(self, query: str, *, limit: int = 8) -> list[dict[str, Any]]:
        try:
            from memory.semantic_runtime import semantic_search

            return [
                {"key": h.entry_id, "value": h.text, "score": round(h.score, 3)}
                for h in semantic_search(query, limit=limit)
            ]
        except Exception:
            return []


_store: PersonalMemoryStore | None = None


def get_personal_memory() -> PersonalMemoryStore:
    global _store
    if _store is None:
        _store = PersonalMemoryStore()
    return _store


def reset_personal_memory() -> None:
    global _store
    _store = None
    path = MEMORY_STORE_PATH
    if path.is_file():
        try:
            path.unlink()
        except OSError:
            try:
                path.write_text(
                    json.dumps({"entries": []}, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            except OSError:
                pass
