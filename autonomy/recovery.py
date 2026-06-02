"""Autonomous Agent Stack v1 — bounded recovery engine.

All recovery is read-only and non-escalating: rewrite the search query, open
the next candidate result, skip broken/blocked pages, re-observe, restart the
(reversible) session once, or stop honestly when exhausted. Every recovery
decision is returned to the executor, which logs it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

# Low-value tokens to drop when rewriting a failed query.
_STOPWORDS = {"the", "a", "an", "of", "for", "to", "in", "on", "and", "deeply",
              "best", "options", "compare", "vs", "versus", "across", "multiple", "sources"}


class RecoveryKind(str, Enum):
    NONE = "none"
    REWRITE_QUERY = "rewrite_query"
    NEXT_CANDIDATE = "next_candidate"
    SKIP_SOURCE = "skip_source"
    REOBSERVE = "reobserve"
    RESTART_SESSION = "restart_session"
    REDUCE_SCOPE = "reduce_scope"


@dataclass(frozen=True)
class RecoveryDecision:
    kind: RecoveryKind
    should_retry: bool
    reason: str
    new_query: str = ""


def rewrite_query(query: str, attempt: int) -> str:
    """Deterministic bounded query rewrite: drop stopwords, then keep head terms."""
    tokens = [t for t in re.split(r"\s+", (query or "").strip()) if t]
    core = [t for t in tokens if t.lower() not in _STOPWORDS] or tokens
    if attempt <= 0:
        return " ".join(core)
    # Progressive narrowing: keep the first (len - attempt) core terms.
    keep = max(1, len(core) - attempt)
    return " ".join(core[:keep])


def plan_search_recovery(query: str, attempt: int, *, max_attempts: int) -> RecoveryDecision:
    if attempt >= max_attempts:
        return RecoveryDecision(RecoveryKind.NONE, False, "search recovery exhausted")
    new_q = rewrite_query(query, attempt)
    if new_q and new_q.lower() != (query or "").lower():
        return RecoveryDecision(RecoveryKind.REWRITE_QUERY, True,
                                f"rewrite query -> {new_q!r}", new_query=new_q)
    return RecoveryDecision(RecoveryKind.NONE, False, "no useful query rewrite available")


def plan_open_recovery(remaining_candidates: int, attempt: int, *, max_attempts: int) -> RecoveryDecision:
    if remaining_candidates <= 0:
        return RecoveryDecision(RecoveryKind.NONE, False, "no more candidate results")
    if attempt >= max_attempts:
        return RecoveryDecision(RecoveryKind.SKIP_SOURCE, False, "open recovery exhausted; skip source")
    return RecoveryDecision(RecoveryKind.NEXT_CANDIDATE, True, "navigation failed; try next result")


def plan_extract_recovery(attempt: int, *, max_attempts: int) -> RecoveryDecision:
    if attempt >= max_attempts:
        return RecoveryDecision(RecoveryKind.SKIP_SOURCE, False, "no text after re-observe; skip source")
    return RecoveryDecision(RecoveryKind.REOBSERVE, True, "no text yet; re-observe")
