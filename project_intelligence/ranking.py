"""Keyword scoring and question-type detection for Project Intelligence."""

from __future__ import annotations

import re

_STOP_WORDS: frozenset[str] = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "if", "that", "this", "these", "those",
    "what", "which", "who", "how", "why", "when", "where", "it", "its",
    "they", "them", "their", "we", "our", "you", "your", "i", "my",
    "me", "us", "he", "she", "him", "her", "not", "no", "so", "yet",
    "both", "either", "neither", "as", "than", "up", "out", "about",
    "under", "after", "before", "during", "into", "through", "just",
    "also", "very", "such", "more", "most", "any", "all", "each", "every",
    "first", "last", "new", "please", "tell", "give", "need", "understand",
    "appear", "one", "two", "three", "words", "current", "summarize",
})

MAX_PASSAGE_CHARS = 600
MAX_PASSAGES_PER_FILE = 2


def extract_keywords(question: str) -> list[str]:
    words = re.findall(r"\b[a-zA-Z0-9_]+\b", question.lower())
    return [w for w in words if w not in _STOP_WORDS and len(w) >= 3]


def extract_phase_numbers(question: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r"\bphase[\s\-_]?(\d+[a-zA-Z]?)\b", question, re.IGNORECASE):
        key = match.group(1).lower()
        if key not in seen:
            seen.add(key)
            found.append(match.group(1))
    return found


def score_passage(passage: str, keywords: list[str]) -> float:
    if not keywords or not passage.strip():
        return 0.0
    lower = passage.lower()
    hits = sum(1 for kw in keywords if kw in lower)
    if hits == 0:
        return 0.0
    base = hits / len(keywords)
    bonus = 0.15 if hits >= 3 else 0.0
    return base + bonus


def extract_passages(text: str, keywords: list[str]) -> list[tuple[str, float]]:
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    scored: list[tuple[str, float]] = []
    for para in paragraphs:
        score = score_passage(para, keywords)
        if score <= 0.0:
            continue
        excerpt = para[:MAX_PASSAGE_CHARS]
        if len(para) > MAX_PASSAGE_CHARS:
            excerpt = excerpt.rstrip() + "…"
        scored.append((excerpt, score))
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:MAX_PASSAGES_PER_FILE]


def is_temporal(question: str) -> bool:
    lower = question.lower()
    return any(
        phrase in lower
        for phrase in (
            "last 30 days",
            "last 7 days",
            "last week",
            "last month",
            "recently",
            "what changed",
            "recent changes",
            "recent commits",
            "recent decisions",
            "past month",
            "past week",
        )
    )


def days_requested(question: str) -> int:
    match = re.search(r"last\s+(\d+)\s+days?", question, re.IGNORECASE)
    return int(match.group(1)) if match else 30


def is_architecture_question(keywords: list[str]) -> bool:
    arch = {
        "architecture",
        "architect",
        "architectural",
        "pipeline",
        "overview",
        "design",
        "system",
        "codebase",
        "structure",
        "module",
        "component",
        "brain",
        "router",
        "handler",
        "risk",
        "risks",
    }
    return bool(arch.intersection(set(keywords)))


def is_unrelated_question(question: str) -> bool:
    lower = question.lower()
    return "unrelated" in lower or "not related" in lower


def question_topic(question: str) -> str:
    lower = question.lower()
    if re.search(r"\bwhy\s+was\s+phase\b", lower):
        return "phase_why"
    if re.search(r"\bwhat\s+problem\s+does\s+phase\b", lower):
        return "phase_problem"
    if "architectural risk" in lower or "biggest" in lower and "risk" in lower:
        return "architecture_risks"
    if "built next" in lower:
        return "roadmap_next"
    if "current state" in lower or ("summarize" in lower and "project" in lower):
        return "project_state"
    if "unfinished" in lower:
        return "unfinished_phases"
    if is_temporal(question):
        return "recent_changes"
    if "decisions" in lower and ("recent" in lower or "future" in lower):
        return "recent_decisions"
    if "new developer" in lower:
        return "onboarding"
    if is_unrelated_question(question):
        return "unrelated_code"
    return "general"
