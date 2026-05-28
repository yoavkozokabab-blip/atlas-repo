"""Deterministic spoken-command normalization (regex/rules only, no LLM)."""

from __future__ import annotations

import re

from voice.transcript_cleanup import _normalize_ws

# Exact phrase replacements after lowercasing.
_PHRASE_FIXES: tuple[tuple[str, str], ...] = (
    ("show job is status", "show jarvis status"),
    ("show jarvis star", "show jarvis status"),
    ("show jarv is status", "show jarvis status"),
    ("show jarvis stats", "show jarvis status"),
    ("show jarvis stat", "show jarvis status"),
    ("show jarvis stars", "show jarvis status"),
    ("show jarvis state", "show jarvis status"),
    ("show jarvis statuses", "show jarvis status"),
    ("show jarvis start", "show jarvis status"),
    ("show jarvis star status", "show jarvis status"),
    ("show jar is status", "show jarvis status"),
    ("show jarvis status", "show jarvis status"),
    ("show voice debug", "show voice debug"),
    ("show boys debug", "show voice debug"),
    ("show voice debunk", "show voice debug"),
    ("what did you hear", "show voice debug"),
    ("show what you heard", "show voice debug"),
    ("show audio state", "show audio status"),
    ("show speaker status", "show audio status"),
    ("voice output status", "show audio status"),
    ("try speaking", "test voice output"),
    ("say something", "test voice output"),
    ("test speech", "test voice output"),
    ("describe my screen", "describe screen"),
    ("describe the screener", "describe the screen"),
    ("read the screener", "read the screen"),
    ("analyze the screener", "analyze the screen"),
    ("what is on my screen", "what is on my screen"),
    ("open the trading view", "open tradingview"),
    ("open trading you", "open tradingview"),
    ("open trading view", "open tradingview"),
    ("open trading vue", "open tradingview"),
    ("open this cord", "open discord"),
    ("open the discord", "open discord"),
    ("open dish cord", "open discord"),
    ("open discord", "open discord"),
    ("open dash board", "open dashboard"),
    ("open the dashboard", "open dashboard"),
    ("go to dashboard", "open dashboard"),
    ("open the dash board", "open dashboard"),
    ("show dash board", "show dashboard"),
    ("show the dash board", "show dashboard"),
    ("run diagnostic", "run diagnostics"),
    ("run diagnose", "run diagnostics"),
    ("show me diagnostics", "show diagnostics"),
    ("show diagnostics", "show diagnostics"),
    ("startup health", "show startup health"),
    ("start up health", "show startup health"),
    ("voice performance", "show voice performance status"),
    ("show voice performance", "show voice performance status"),
    ("task queue", "show task queue status"),
    ("memory graph", "show memory graph"),
    ("screen analysis", "describe screen"),
    ("what's on my screen", "what is on my screen"),
    ("whats on my screen", "what is on my screen"),
    ("quiet mode", "toggle quiet mode"),
    ("toggle overlay", "toggle overlay"),
    ("test voice output", "test voice output"),
    ("show audio status", "show audio status"),
    ("validate patch safe", "validate patch safety"),
    ("validate patch", "validate patch safety"),
    ("replay validation", "replay after patch"),
    ("replay patch validation", "replay after patch"),
    ("compare pre and post patch", "compare pre post patch"),
    ("patch workflow status", "show patch workflow status"),
)

_REGEX_FIXES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^show\s+jarvis\s+sta\w*$"), "show jarvis status"),
    (re.compile(r"^show\s+job\s+is\s+sta\w*$"), "show jarvis status"),
    (re.compile(r"^open\s+trading\s+vi\w*$"), "open tradingview"),
    (re.compile(r"^open\s+dis\s*cord$"), "open discord"),
    (re.compile(r"\bdiagnostic\b"), "diagnostics"),
    (re.compile(r"\bdash\s+board\b"), "dashboard"),
    (re.compile(r"\btrading\s+view\b"), "tradingview"),
    (re.compile(r"\bdis\s+cord\b"), "discord"),
    (re.compile(r"\bjar\s+vis\b"), "jarvis"),
    (re.compile(r"\bover\s+lay\b"), "overlay"),
    (re.compile(r"\bquiet\s+mode\b"), "quiet mode"),
    (re.compile(r"\bthe\s+screener\b"), "the screen"),
    (re.compile(r"\bmy\s+screener\b"), "my screen"),
)


def normalize_spoken_command(text: str) -> str:
    """
    Fix common STT mis-hearings for JARVIS commands.
    Deterministic only — never invent unrelated commands.
    """
    cleaned = _normalize_ws(text or "")
    if not cleaned:
        return ""
    lower = cleaned.lower()
    for src, dst in _PHRASE_FIXES:
        if lower == src:
            return dst
    for pattern, repl in _REGEX_FIXES:
        if pattern.search(lower):
            lower = pattern.sub(repl, lower, count=1)
    return lower.strip() if lower != cleaned.lower() else cleaned


# Backward-compatible alias for wake path
normalize_wake_transcript = normalize_spoken_command
