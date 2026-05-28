"""Shared utilities for log/report scanning."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from config import (
    LOG_SCAN_MAX_BYTES,
    LOG_SCAN_MAX_FILES,
    LOG_TAIL_LINES,
    TRADING_REPORTS_DUAL,
    TRADING_REPORTS_LOGS,
    TRADING_REPORTS_ROOT,
)

LOG_EXTENSIONS = {".log", ".txt", ".csv"}
ERROR_KEYWORDS = re.compile(
    r"error|exception|traceback|failed|rejected|skipped|blocked",
    re.IGNORECASE,
)
REJECTION_REASONS = (
    "entry_trigger_not_hit",
    "confirmation_failed",
    "delayed_entry_failed",
    "risk_check_failed",
    "max_positions_reached",
    "exposure_limit_reached",
    "already_in_position",
    "overlap_blocked",
    "market_closed",
    "insufficient_data",
)

HEBREW_LOG_ALIASES: dict[str, str] = {
    "שגיאות": "error exception traceback failed",
    "דחיות": "rejected skipped blocked",
    "סטופ": "stop",
    "כניסה": "entry",
}


def log_search_roots() -> list[Path]:
    roots = [TRADING_REPORTS_ROOT, TRADING_REPORTS_DUAL, TRADING_REPORTS_LOGS]
    return [r for r in roots if r.is_dir()]


def iter_recent_log_files(
    *,
    max_files: int = LOG_SCAN_MAX_FILES,
    extensions: set[str] | None = None,
) -> list[Path]:
    ext = extensions or LOG_EXTENSIONS
    found: list[Path] = []
    for root in log_search_roots():
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in ext:
                continue
            try:
                if path.stat().st_size > LOG_SCAN_MAX_BYTES:
                    continue
            except OSError:
                continue
            found.append(path)
    found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return found[:max_files]


def read_tail(path: Path, max_lines: int = LOG_TAIL_LINES) -> list[str]:
    try:
        size = path.stat().st_size
        if size > LOG_SCAN_MAX_BYTES:
            with path.open("rb") as f:
                f.seek(max(0, size - LOG_SCAN_MAX_BYTES))
                chunk = f.read().decode("utf-8", errors="replace")
            lines = chunk.splitlines()
            return lines[-max_lines:]
        text = path.read_text(encoding="utf-8", errors="replace")
        return text.splitlines()[-max_lines:]
    except OSError:
        return []


def latest_log_file() -> Path | None:
    files = iter_recent_log_files()
    return files[0] if files else None


def expand_log_query(query: str) -> str:
    q = query.strip().lower()
    for heb, eng in HEBREW_LOG_ALIASES.items():
        if heb in q:
            q = f"{q} {eng}"
    return q


def lines_matching(lines: list[str], pattern: re.Pattern[str] | str) -> list[str]:
    if isinstance(pattern, str):
        pat = re.compile(re.escape(pattern), re.IGNORECASE)
    else:
        pat = pattern
    return [ln for ln in lines if pat.search(ln)]


def aggregate_reason_counts(lines: list[str]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for reason in REJECTION_REASONS:
        c = sum(1 for ln in lines if reason in ln.lower())
        if c:
            counts[reason] = c
    return counts
