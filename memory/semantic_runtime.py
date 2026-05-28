"""Persistent semantic memory runtime for Phase 61 execution."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

from config import DATA_DIR

_STORE = DATA_DIR / "semantic_memory.json"


@dataclass(frozen=True)
class SemanticHit:
    entry_id: str
    score: float
    text: str


def _tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-zA-Z0-9_]+", (text or "").lower()) if len(t) > 1]


def _vec(text: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for tok in _tokenize(text):
        out[tok] = out.get(tok, 0.0) + 1.0
    return out


def _cos(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(v * b.get(k, 0.0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / (na * nb)


def _load() -> dict:
    if not _STORE.is_file():
        return {"entries": {}, "graph": {"relations": [], "contradictions": []}, "tasks": {}}
    try:
        return json.loads(_STORE.read_text(encoding="utf-8"))
    except Exception:
        return {"entries": {}, "graph": {"relations": [], "contradictions": []}, "tasks": {}}


def _save(payload: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _STORE.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def upsert_entry(
    *,
    entry_id: str,
    text: str,
    importance: float,
    confidence: float,
    category: str,
    task_id: str = "",
) -> None:
    payload = _load()
    vec = _vec(text)
    entries = payload.setdefault("entries", {})
    row = entries.get(entry_id, {})
    row.update(
        {
            "entry_id": entry_id,
            "text": text[:600],
            "vector": vec,
            "importance": float(importance),
            "confidence": float(confidence),
            "category": category,
            "long_term": bool(importance >= 0.8 and confidence >= 0.8),
        }
    )
    entries[entry_id] = row
    if task_id:
        tasks = payload.setdefault("tasks", {})
        task_rows = tasks.setdefault(task_id, [])
        if entry_id not in task_rows:
            task_rows.append(entry_id)
    _update_graph(payload)
    _save(payload)


def semantic_search(query: str, *, limit: int = 8) -> list[SemanticHit]:
    payload = _load()
    qv = _vec(query)
    hits: list[SemanticHit] = []
    for row in payload.get("entries", {}).values():
        vec = row.get("vector", {})
        score = _cos(qv, vec) * (0.6 + 0.4 * float(row.get("importance", 0.5)))
        if score <= 0:
            continue
        hits.append(
            SemanticHit(
                entry_id=str(row.get("entry_id", "")),
                score=float(score),
                text=str(row.get("text", "")),
            )
        )
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[: max(1, limit)]


def graph_snapshot() -> dict:
    payload = _load()
    return payload.get("graph", {})


def _update_graph(payload: dict) -> None:
    rows = list(payload.get("entries", {}).values())[-200:]
    relations: list[dict] = []
    contradictions: list[dict] = []
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            a = rows[i]
            b = rows[j]
            sim = _cos(a.get("vector", {}), b.get("vector", {}))
            if sim >= 0.62:
                relations.append({"a": a.get("entry_id"), "b": b.get("entry_id"), "score": round(sim, 3)})
            if _is_contradiction(str(a.get("text", "")), str(b.get("text", ""))):
                contradictions.append({"a": a.get("entry_id"), "b": b.get("entry_id"), "reason": "semantic_negation"})
    payload["graph"] = {"relations": relations[-500:], "contradictions": contradictions[-200:]}


def _is_contradiction(a: str, b: str) -> bool:
    a_l = a.lower()
    b_l = b.lower()
    neg = (" not ", " never ", " no ")
    return any(x in a_l for x in neg) and not any(x in b_l for x in neg) and _cos(_vec(a_l), _vec(b_l)) > 0.55

