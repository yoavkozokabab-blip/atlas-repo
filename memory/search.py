"""Search personal memory and project index."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from memory.store import PersonalMemoryStore


def search_memory_entries(
    query: str,
    *,
    store: "PersonalMemoryStore | None" = None,
    category: str | None = None,
    tag: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    from memory.store import get_personal_memory

    mem = store or get_personal_memory()
    q = (query or "").strip().lower()
    hits: list[dict[str, Any]] = []
    for entry in mem.list_visible(category=category, limit=500):
        blob = f"{entry.text} {' '.join(entry.tags)} {entry.category}".lower()
        if tag and tag.lower() not in blob:
            continue
        if q and q not in blob and not any(q in t.lower() for t in entry.tags):
            continue
        hits.append(
            {
                "key": entry.entry_id,
                "value": entry.text,
                "category": entry.category,
                "tags": entry.tags,
            }
        )
        if len(hits) >= limit:
            break
    if q and len(hits) < limit and hasattr(mem, "semantic_search"):
        for row in mem.semantic_search(q, limit=limit):
            if any(h.get("key") == row.get("key") for h in hits):
                continue
            hits.append(
                {
                    "key": row.get("key", ""),
                    "value": row.get("value", ""),
                    "category": "semantic",
                    "tags": [f"score:{row.get('score', 0.0)}"],
                }
            )
            if len(hits) >= limit:
                break
    return hits


def search_project_index(
    query: str,
    *,
    limit: int = 15,
) -> list[dict[str, Any]]:
    from memory.project_indexer import load_project_index

    q = (query or "").strip().lower()
    if not q:
        return []
    index = load_project_index()
    hits: list[tuple[int, dict[str, Any]]] = []
    for proj_name, proj in index.get("projects", {}).items():
        if not isinstance(proj, dict):
            continue
        for row in proj.get("files", []):
            if not isinstance(row, dict):
                continue
            path = str(row.get("path", ""))
            summary = str(row.get("summary", ""))
            keywords = row.get("keywords", [])
            blob = f"{path} {summary} {' '.join(keywords)} {proj_name}".lower()
            score = 0
            if q in path:
                score += 3
            if q in summary:
                score += 2
            if any(q in str(k).lower() for k in keywords):
                score += 2
            if q in blob:
                score += 1
            if score > 0:
                hits.append((score, {**row, "project": proj_name}))
    hits.sort(key=lambda x: -x[0])
    return [h[1] for h in hits[:limit]]
