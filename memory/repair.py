"""Memory store repair utility (Phase 65 Track B)."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import DATA_DIR, MEMORY_STORE_PATH


def _backup(path: Path) -> Path | None:
    if not path.is_file():
        return None
    backups = DATA_DIR / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dest = backups / f"{path.stem}_{stamp}{path.suffix}"
    shutil.copy2(path, dest)
    return dest


def _normalize_entry(row: dict[str, Any]) -> dict[str, Any] | None:
    text = str(row.get("text") or row.get("value") or "").strip()
    if not text:
        return None
    entry_id = str(row.get("entry_id") or row.get("key") or "").strip()
    if not entry_id:
        entry_id = f"mem_repair_{hash(text) & 0xFFFFFF:06x}"
    category = str(row.get("category") or "personal_note")
    return {
        "entry_id": entry_id,
        "category": category,
        "text": text[:2000],
        "tags": [str(t) for t in (row.get("tags") or []) if t][:10],
        "created_at": str(row.get("created_at") or datetime.now(timezone.utc).isoformat()),
        "source": str(row.get("source") or "repair")[:80],
        "hidden": bool(row.get("hidden", False)),
        "importance": float(row.get("importance", 0.5) or 0.5),
        "confidence": float(row.get("confidence", 0.7) or 0.7),
        "expires_at": str(row.get("expires_at") or ""),
        "sensitive": bool(row.get("sensitive", False)),
    }


def repair_memory_store() -> str:
    """Repair memory_store.json: backup, dedupe, fix schema, prune stale/hidden orphans."""
    path = MEMORY_STORE_PATH
    backup = _backup(path)
    raw: dict[str, Any]
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = {"entries": []}
    else:
        raw = {"entries": []}

    entries_in = raw.get("entries") if isinstance(raw.get("entries"), list) else []
    seen_text: set[str] = set()
    cleaned: list[dict[str, Any]] = []
    duplicates = 0
    dropped = 0
    for row in entries_in:
        if not isinstance(row, dict):
            dropped += 1
            continue
        norm = _normalize_entry(row)
        if norm is None:
            dropped += 1
            continue
        key = norm["text"].lower().strip()
        if key in seen_text and not norm.get("hidden"):
            duplicates += 1
            continue
        seen_text.add(key)
        cleaned.append(norm)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"entries": cleaned}, indent=2, ensure_ascii=False), encoding="utf-8")

    semantic = DATA_DIR / "semantic_memory.json"
    sem_backup = _backup(semantic) if semantic.is_file() else None
    if semantic.is_file():
        try:
            sem = json.loads(semantic.read_text(encoding="utf-8"))
            if not isinstance(sem, dict):
                sem = {"entries": {}, "graph": {"relations": [], "contradictions": []}, "tasks": {}}
            semantic.write_text(json.dumps(sem, indent=2, ensure_ascii=True), encoding="utf-8")
        except Exception:
            semantic.write_text(
                json.dumps({"entries": {}, "graph": {"relations": [], "contradictions": []}, "tasks": {}}, indent=2),
                encoding="utf-8",
            )

    lines = [
        "Memory store repair complete.",
        f"  entries_before: {len(entries_in)}",
        f"  entries_after: {len(cleaned)}",
        f"  duplicates_removed: {duplicates}",
        f"  invalid_dropped: {dropped}",
        f"  backup: {backup or 'none'}",
        f"  semantic_backup: {sem_backup or 'none'}",
    ]
    return "\n".join(lines)
