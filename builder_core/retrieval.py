"""Keyword retrieval over indexed chunks.

No embeddings, no LLM. Tokenised keyword overlap with light boosts for path
matches and document category. Good enough to ground extractive answers.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Tuple

from . import repository_understanding

_WORD_RE = re.compile(r"[a-z0-9]+")

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is", "are",
    "was", "were", "be", "been", "being", "this", "that", "these", "those",
    "it", "its", "as", "at", "by", "with", "from", "into", "about", "what",
    "which", "who", "whom", "how", "why", "when", "where", "do", "does", "did",
    "can", "could", "should", "would", "will", "we", "our", "you", "your",
    "i", "me", "my", "they", "them", "their", "have", "has", "had", "not",
    "but", "if", "then", "than", "so", "such", "most", "more", "biggest",
    "code", "codebase", "project", "repo", "repository",
}

CATEGORY_BOOST = {"readme": 1.4, "docs": 1.3, "src": 1.0, "test": 0.7}
ROLE_BOOST = {
    "production_code": 1.4,
    "architecture_doc": 1.8,
    "general_doc": 1.0,
    "config": 0.8,
    "test": 0.5,
    "report_history": 0.2,
    "benchmark": 0.0,
    "dataset": 0.0,
    "generated": 0.0,
    "unknown": 0.5,
}
ARCHITECTURE_PREFIXES = (
    "core/",
    "voice/",
    "browser/",
    "autonomy/",
    "memory/",
    "conversation/",
    "project_intelligence/",
    "builder_core/",
)
_ARCHITECTURE_RE = re.compile(
    r"\b(architect\w*|component\w*|director(?:y|ies)|folder\w*|module\w*|"
    r"pipeline|production code|structure|subsystem\w*|voice command|speaks?)\b",
    re.IGNORECASE,
)


def tokenize(text: str) -> List[str]:
    return [
        t for t in _WORD_RE.findall(text.lower())
        if len(t) >= 3 and t not in STOPWORDS
    ]


def is_architecture_question(query: str) -> bool:
    return bool(_ARCHITECTURE_RE.search(query))


def _chunk_role(chunk: Dict[str, str]) -> str:
    return chunk.get("role") or repository_understanding.classify_file_role(
        chunk.get("path", "")
    )


def _architecture_bonus(path: str, query_tokens: List[str]) -> float:
    lowered = path.lower()
    if lowered == "readme_architecture.md":
        return 12.0
    if lowered == "readme.md":
        return 8.0
    if lowered == "main.py":
        return 6.0
    for position, prefix in enumerate(ARCHITECTURE_PREFIXES):
        if lowered.startswith(prefix):
            subsystem = prefix[:-1]
            return 10.0 if subsystem in query_tokens else max(1.0, 4.0 - (position * 0.25))
    return 0.0


def score_chunk(chunk: Dict[str, str], query_tokens: List[str]) -> float:
    if not query_tokens:
        return 0.0
    text = chunk.get("text", "").lower()
    path = chunk.get("path", "").lower()
    text_tokens = _WORD_RE.findall(text)
    text_set = set(text_tokens)
    score = 0.0
    for qt in query_tokens:
        # frequency in body
        score += text_tokens.count(qt)
        # presence boost so rare-but-present terms still count
        if qt in text_set:
            score += 0.5
        # path mention is a strong signal
        if qt in path:
            score += 1.5
    category_boost = CATEGORY_BOOST.get(chunk.get("category", "src"), 1.0)
    role_boost = ROLE_BOOST.get(_chunk_role(chunk), 0.5)
    return score * category_boost * role_boost


def _select_architecture_hits(
    scored: List[Tuple[Dict[str, str], float]], limit: int
) -> List[Tuple[Dict[str, str], float]]:
    allowed = [
        item for item in scored
        if _chunk_role(item[0]) not in {"benchmark", "dataset", "generated"}
    ]
    production_or_architecture = [
        item for item in allowed
        if _chunk_role(item[0]) in {"production_code", "architecture_doc"}
    ]
    report_cap = math.floor(limit * 0.20)
    preferred_minimum = math.ceil(limit * 0.50)
    selected: List[Tuple[Dict[str, str], float]] = []
    selected_ids = set()

    def add(item: Tuple[Dict[str, str], float]) -> None:
        identity = (item[0].get("path", ""), item[0].get("text", ""))
        if identity not in selected_ids and len(selected) < limit:
            selected.append(item)
            selected_ids.add(identity)

    for item in production_or_architecture[:preferred_minimum]:
        add(item)
    report_count = 0
    for item in allowed:
        if len(selected) >= limit:
            break
        role = _chunk_role(item[0])
        if role == "report_history":
            if report_count >= report_cap:
                continue
            report_count += 1
        add(item)
    return selected


def source_distribution_for_chunks(chunks: List[Dict[str, str]]) -> Dict[str, Any]:
    roles: Dict[str, int] = {}
    for chunk in chunks:
        role = _chunk_role(chunk)
        roles[role] = roles.get(role, 0) + 1
    return _source_distribution(roles)


def source_distribution_for_sources(index: Dict[str, Any], sources: List[str]) -> Dict[str, Any]:
    by_path = {item.get("path", ""): item.get("role") for item in index.get("files", [])}
    roles: Dict[str, int] = {}
    for source in dict.fromkeys(sources):
        role = by_path.get(source) or repository_understanding.classify_file_role(source)
        roles[role] = roles.get(role, 0) + 1
    return _source_distribution(roles)


def _source_distribution(roles: Dict[str, int]) -> Dict[str, Any]:
    total = sum(roles.values())

    def pct(role: str) -> float:
        return round((roles.get(role, 0) / total * 100.0), 2) if total else 0.0

    return {
        "total_sources": total,
        "source_distribution": dict(sorted(roles.items())),
        "production_percent": pct("production_code"),
        "architecture_percent": pct("architecture_doc"),
        "reports_percent": pct("report_history"),
        "benchmark_percent": pct("benchmark"),
    }


def search(index: Dict[str, Any], query: str, limit: int = 6) -> List[Tuple[Dict[str, str], float]]:
    query_tokens = tokenize(query)
    architecture = is_architecture_question(query)
    scored: List[Tuple[Dict[str, str], float]] = []
    for chunk in index.get("chunks", []):
        s = score_chunk(chunk, query_tokens)
        if s > 0:
            if architecture:
                s += _architecture_bonus(chunk.get("path", ""), query_tokens)
            scored.append((chunk, s))
    # sort by score desc, then prefer shorter paths (more general) deterministically
    scored.sort(key=lambda cs: (-cs[1], len(cs[0].get("path", "")), cs[0].get("path", "")))
    if architecture:
        return _select_architecture_hits(scored, limit)
    return scored[:limit]
