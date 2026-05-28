"""Token-level vocabulary correction for STT typos (no free-form rewriting)."""

from __future__ import annotations

import re
from functools import lru_cache

from config import VOCABULARY_CORRECTION_ENABLED, VOCABULARY_MAX_EDIT_DISTANCE
from core.logger import setup_logger

logger = setup_logger("jarvis.language.vocabulary")

_TOKEN_RE = re.compile(r"[a-z0-9']+", re.I)
_SKIP = frozenset(
    {
        "a",
        "i",
        "to",
        "the",
        "and",
        "or",
        "is",
        "it",
        "in",
        "on",
        "at",
        "me",
        "my",
        "we",
        "you",
        "what",
        "why",
        "how",
        "did",
        "do",
        "this",
        "that",
        "here",
        "there",
        "fail",
        "failed",
        "with",
        "for",
        "of",
    }
)
_MIN_TOKEN_LEN = 5


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            ins = cur[j - 1] + 1
            delete = prev[j] + 1
            sub = prev[j - 1] + (ca != cb)
            cur.append(min(ins, delete, sub))
        prev = cur
    return prev[-1]


@lru_cache(maxsize=1)
def _build_vocabulary() -> frozenset[str]:
    words: set[str] = set(_SKIP)
    try:
        from brain.command_grammar import list_grammar_phrases

        for phrase in list_grammar_phrases():
            words.update(_TOKEN_RE.findall(phrase.lower()))
    except Exception:
        pass
    try:
        from config import IMPLEMENTED_INTENTS

        for intent in IMPLEMENTED_INTENTS:
            words.update(intent.replace("_", " ").split())
    except Exception:
        pass
    # High-value command tokens (not “all English”)
    words.update(
        {
            "jarvis",
            "dashboard",
            "diagnostics",
            "diagnostic",
            "trading",
            "tradingview",
            "discord",
            "youtube",
            "chatgpt",
            "cursor",
            "workflow",
            "workflows",
            "capabilities",
            "memory",
            "graph",
            "screen",
            "window",
            "voice",
            "audio",
            "status",
            "health",
            "report",
            "reports",
            "failed",
            "failing",
            "tests",
            "error",
            "explain",
            "summarize",
            "session",
            "project",
            "open",
            "show",
            "run",
            "check",
            "dash",
            "board",
            "benchmark",
            "calibrate",
            "speaking",
            "stop",
        }
    )
    return frozenset(w for w in words if len(w) >= 2)


def correct_tokens(text: str) -> tuple[str, bool]:
    """
    Fix individual tokens via edit distance against a bounded vocabulary.
    Does not invent new phrases or reorder words.
    """
    if not VOCABULARY_CORRECTION_ENABLED or not (text or "").strip():
        return text, False
    vocab = _build_vocabulary()
    max_dist = max(0, int(VOCABULARY_MAX_EDIT_DISTANCE))
    changed = False
    parts: list[str] = []
    last = 0
    for m in _TOKEN_RE.finditer(text):
        parts.append(text[last : m.start()])
        token = m.group(0)
        low = token.lower()
        if low in _SKIP or low in vocab or len(low) < _MIN_TOKEN_LEN:
            parts.append(token)
        else:
            best = low
            best_d = max_dist + 1
            for word in vocab:
                if abs(len(word) - len(low)) > max_dist:
                    continue
                d = _levenshtein(low, word)
                if d < best_d:
                    best_d = d
                    best = word
            if best_d <= max_dist and best != low:
                parts.append(best if token.islower() else best)
                changed = True
            else:
                parts.append(token)
        last = m.end()
    parts.append(text[last:])
    return "".join(parts), changed
