"""Deterministic builder-question routing (Phase 80).

Matched before semantic reformulation / follow-up expansion so builder questions
never become UNKNOWN when LLM or semantic layers are enabled.
"""

from __future__ import annotations

import re

from core.types import CommandRequest, Intent

_BUILDER_REGEXES: tuple[tuple[re.Pattern[str], float], ...] = (
    (re.compile(r"\bwhy\s+was\s+phase\b", re.I), 0.92),
    (re.compile(r"\bwhat\s+problem\s+does\s+phase\b", re.I), 0.92),
    (re.compile(r"\bwhat\s+did\s+phase\b", re.I), 0.90),
    (re.compile(r"\barchitectural\s+risks?\b", re.I), 0.91),
    (re.compile(r"\b(codebase|jarvis)\s+risks?\b", re.I), 0.89),
    (re.compile(r"\bwhat\s+should\s+be\s+built\s+next\b", re.I), 0.91),
    (re.compile(r"\bbuild\s+next\s+and\s+why\b", re.I), 0.91),
    (re.compile(r"\b(current\s+state|summarize).{0,40}\bproject\b", re.I), 0.90),
    (re.compile(r"\bstate\s+of\s+the\s+project\b", re.I), 0.90),
    (re.compile(r"\bunfinished\s+phases?\b", re.I), 0.91),
    (re.compile(r"\bmost\s+important\s+unfinished\b", re.I), 0.91),
    (re.compile(r"\bwhat\s+changed\s+in\s+the\s+last\b", re.I), 0.91),
    (re.compile(r"\blast\s+\d+\s+days\b", re.I), 0.88),
    (re.compile(r"\bdecisions?\s+(were\s+)?made\s+recent", re.I), 0.91),
    (re.compile(r"\bdecisions?\b.{0,40}\bfuture\s+architecture\b", re.I), 0.91),
    (re.compile(r"\bif\s+a\s+new\s+developer\b", re.I), 0.91),
    (re.compile(r"\bnew\s+developer\s+joined\b", re.I), 0.91),
    (re.compile(r"\bparts\s+of\s+the\s+codebase\s+appear\s+unrelated\b", re.I), 0.92),
    (re.compile(r"\bunrelated\s+to\s+jarvis\s+for\s+builders\b", re.I), 0.92),
    (re.compile(r"\bjarvis\s+for\s+builders\b", re.I), 0.89),
    (re.compile(r"\bproject\s+intelligence\b", re.I), 0.89),
    (re.compile(r"\bproject\s+historian\b", re.I), 0.88),
    (re.compile(r"\barchitecture\s+advisor\b", re.I), 0.88),
)

_BUILDER_PHRASES: tuple[tuple[str, float], ...] = (
    ("why was phase", 0.92),
    ("what problem does phase", 0.92),
    ("architectural risks in", 0.91),
    ("architectural risk in", 0.91),
    ("what should be built next", 0.91),
    ("current state of the project", 0.90),
    ("unfinished phases", 0.91),
    ("what changed in the last", 0.91),
    ("decisions were made recently", 0.91),
    ("decisions made recently", 0.91),
    ("decisions that could affect future", 0.91),
    ("if a new developer", 0.91),
    ("new developer joined", 0.91),
    ("parts of the codebase appear unrelated", 0.92),
    ("unrelated to jarvis for builders", 0.92),
)


def is_builder_question(text: str) -> bool:
    return match_builder_question(text) is not None


def match_builder_question(text: str) -> CommandRequest | None:
    raw = (text or "").strip()
    if not raw:
        return None

    lower = raw.lower()
    best_conf = 0.0
    for pattern, conf in _BUILDER_REGEXES:
        if pattern.search(lower) and conf > best_conf:
            best_conf = conf
    for phrase, conf in _BUILDER_PHRASES:
        if phrase in lower and conf > best_conf:
            best_conf = conf

    if best_conf < 0.88:
        return None

    return CommandRequest(
        raw_text=raw,
        intent=Intent.ANSWER_PROJECT_QUESTION,
        confidence=best_conf,
        params={"query": raw},
        language="en",
        classifier_source="builder_question",
    )
