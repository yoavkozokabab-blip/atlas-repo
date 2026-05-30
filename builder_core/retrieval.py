"""Keyword retrieval over indexed chunks.

No embeddings, no LLM. Tokenised keyword overlap with light boosts for path
matches and document category. Good enough to ground extractive answers.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

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


def tokenize(text: str) -> List[str]:
    return [
        t for t in _WORD_RE.findall(text.lower())
        if len(t) >= 3 and t not in STOPWORDS
    ]


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
    boost = CATEGORY_BOOST.get(chunk.get("category", "src"), 1.0)
    return score * boost


def search(index: Dict[str, Any], query: str, limit: int = 6) -> List[Tuple[Dict[str, str], float]]:
    query_tokens = tokenize(query)
    scored: List[Tuple[Dict[str, str], float]] = []
    for chunk in index.get("chunks", []):
        s = score_chunk(chunk, query_tokens)
        if s > 0:
            scored.append((chunk, s))
    # sort by score desc, then prefer shorter paths (more general) deterministically
    scored.sort(key=lambda cs: (-cs[1], len(cs[0].get("path", "")), cs[0].get("path", "")))
    return scored[:limit]
