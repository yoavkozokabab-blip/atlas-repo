"""Read-only code intelligence under TRADING_PROJECT_ROOT."""

from __future__ import annotations

import re
from pathlib import Path

from actions.base import BaseAction
from config import (
    CODE_SEARCH_EXCLUDED_DIRS,
    CODE_SEARCH_EXTENSIONS,
    CODE_SEARCH_MAX_RESULTS,
    TRADING_PROJECT_ROOT,
)
from core.results import result_failed, result_success
from core.types import CommandRequest, CommandResult, Intent


def _is_excluded(path: Path) -> bool:
    return any(part in CODE_SEARCH_EXCLUDED_DIRS for part in path.parts)


def _iter_search_files(root: Path) -> list[Path]:
    files: list[Path] = []
    if not root.is_dir():
        return files
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if _is_excluded(path):
            continue
        if path.suffix.lower() not in CODE_SEARCH_EXTENSIONS:
            continue
        if "reports" in path.parts and path.suffix.lower() not in {".json", ".md"}:
            continue
        files.append(path)
    return files


def _safe_root() -> Path:
    return TRADING_PROJECT_ROOT.resolve()


def _format_hits(hits: list[tuple[str, int, str]], label: str) -> CommandResult:
    if not hits:
        return result_failed(Intent.UNKNOWN, f"No {label} matches found.")
    lines = [f"{path}:{lineno}: {snippet}" for path, lineno, snippet in hits[:25]]
    summary = f"{label} ({len(hits)} matches):\n" + "\n".join(lines)
    return result_success(
        Intent.UNKNOWN,
        summary,
        data={"matches": [{"path": p, "line": n, "snippet": s} for p, n, s in hits[:25]]},
    )


def _search_lines(
    root: Path,
    pattern: re.Pattern[str],
    *,
    max_results: int = CODE_SEARCH_MAX_RESULTS,
) -> list[tuple[str, int, str]]:
    hits: list[tuple[str, int, str]] = []
    for path in _iter_search_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                rel = str(path.relative_to(root))
                hits.append((rel, i, line.strip()[:160]))
                if len(hits) >= max_results:
                    return hits
    return hits


class SearchProjectFileByNameAction(BaseAction):
    intent = Intent.SEARCH_PROJECT_FILE_BY_NAME.value

    def execute(self, request: CommandRequest) -> CommandResult:
        name = str(request.params.get("query") or request.raw_text).strip()
        if not name:
            return result_failed(Intent.SEARCH_PROJECT_FILE_BY_NAME, "Missing filename.")
        root = _safe_root()
        matches = [
            str(p.relative_to(root))
            for p in root.rglob("*")
            if p.is_file() and not _is_excluded(p) and name.lower() in p.name.lower()
        ][:30]
        if not matches:
            return result_failed(
                Intent.SEARCH_PROJECT_FILE_BY_NAME,
                f"No files matching '{name}'.",
            )
        return result_success(
            Intent.SEARCH_PROJECT_FILE_BY_NAME,
            "Matching files:\n" + "\n".join(matches),
            data={"paths": matches},
        )


class SearchCodeTextAction(BaseAction):
    intent = Intent.SEARCH_CODE_TEXT.value

    def execute(self, request: CommandRequest) -> CommandResult:
        query = str(request.params.get("query") or "").strip()
        if not query:
            return result_failed(Intent.SEARCH_CODE_TEXT, "Missing search text.")
        root = _safe_root()
        pat = re.compile(re.escape(query), re.IGNORECASE)
        hits = _search_lines(root, pat)
        if not hits:
            return result_failed(Intent.SEARCH_CODE_TEXT, f"No code matches for '{query}'.")
        r = _format_hits(hits, f"Code search '{query}'")
        r.intent = Intent.SEARCH_CODE_TEXT
        return r


class FindFunctionAction(BaseAction):
    intent = Intent.FIND_FUNCTION.value

    def execute(self, request: CommandRequest) -> CommandResult:
        name = str(request.params.get("name") or request.params.get("query") or "").strip()
        if not name:
            return result_failed(Intent.FIND_FUNCTION, "Missing function name.")
        root = _safe_root()
        patterns = [
            re.compile(rf"^\s*def\s+{re.escape(name)}\s*\(", re.MULTILINE),
            re.compile(rf"^\s*async\s+def\s+{re.escape(name)}\s*\(", re.MULTILINE),
            re.compile(rf"function\s+{re.escape(name)}\s*\(", re.IGNORECASE),
            re.compile(rf"const\s+{re.escape(name)}\s*=", re.IGNORECASE),
        ]
        hits: list[tuple[str, int, str]] = []
        for path in _iter_search_files(root):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for i, line in enumerate(text.splitlines(), start=1):
                if any(p.search(line) for p in patterns):
                    hits.append((str(path.relative_to(root)), i, line.strip()[:160]))
                    if len(hits) >= CODE_SEARCH_MAX_RESULTS:
                        break
        if not hits:
            return result_failed(Intent.FIND_FUNCTION, f"Function '{name}' not found.")
        r = _format_hits(hits, f"Function '{name}'")
        r.intent = Intent.FIND_FUNCTION
        return r


class FindClassAction(BaseAction):
    intent = Intent.FIND_CLASS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        name = str(request.params.get("name") or request.params.get("query") or "").strip()
        if not name:
            return result_failed(Intent.FIND_CLASS, "Missing class name.")
        root = _safe_root()
        pat = re.compile(rf"^\s*class\s+{re.escape(name)}\b")
        hits: list[tuple[str, int, str]] = []
        for path in _iter_search_files(root):
            if path.suffix.lower() != ".py":
                continue
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for i, line in enumerate(lines, start=1):
                if pat.search(line):
                    hits.append((str(path.relative_to(root)), i, line.strip()[:160]))
        if not hits:
            return result_failed(Intent.FIND_CLASS, f"Class '{name}' not found.")
        r = _format_hits(hits, f"Class '{name}'")
        r.intent = Intent.FIND_CLASS
        return r


class FindConfigKeyAction(BaseAction):
    intent = Intent.FIND_CONFIG_KEY.value

    def execute(self, request: CommandRequest) -> CommandResult:
        key = str(request.params.get("key") or request.params.get("query") or "").strip()
        if not key:
            return result_failed(Intent.FIND_CONFIG_KEY, "Missing config key.")
        root = _safe_root()
        pat = re.compile(re.escape(key))
        hits = _search_lines(root, pat)
        if not hits:
            return result_failed(Intent.FIND_CONFIG_KEY, f"Key '{key}' not found.")
        r = _format_hits(hits, f"Config key '{key}'")
        r.intent = Intent.FIND_CONFIG_KEY
        return r


class FindRiskUsageAction(BaseAction):
    intent = Intent.FIND_RISK_USAGE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        terms = [
            "risk_per_trade",
            "max_total_open_risk",
            "combined_max_total_risk",
            "max_position_pct",
            "portfolio_risk",
            "exposure_limit",
        ]
        return _find_grouped(Intent.FIND_RISK_USAGE, terms)


class FindDelayedEntryLogicAction(BaseAction):
    intent = Intent.FIND_DELAYED_ENTRY_LOGIC.value

    def execute(self, request: CommandRequest) -> CommandResult:
        terms = [
            "delayed_entry",
            "delayed_entry_failed",
            "entry_trigger_not_hit",
            "confirmation_failed",
            "breakout",
            "fib proximity",
        ]
        return _find_grouped(Intent.FIND_DELAYED_ENTRY_LOGIC, terms)


class FindExecutionEventsLogicAction(BaseAction):
    intent = Intent.FIND_EXECUTION_EVENTS_LOGIC.value

    def execute(self, request: CommandRequest) -> CommandResult:
        terms = [
            "execution_event",
            "place_order_attempt",
            "place_order_skipped",
            "place_order_rejected",
            "close_order_attempt",
            "reconcile_result",
        ]
        return _find_grouped(Intent.FIND_EXECUTION_EVENTS_LOGIC, terms)


def _find_grouped(intent: Intent, terms: list[str]) -> CommandResult:
    root = _safe_root()
    by_file: dict[str, list[str]] = {}
    for term in terms:
        pat = re.compile(re.escape(term), re.IGNORECASE)
        for path, lineno, snippet in _search_lines(root, pat, max_results=15):
            by_file.setdefault(path, []).append(f"  L{lineno}: {snippet}")
    if not by_file:
        return result_failed(intent, "No matches found.")
    lines = [f"{intent.value} summary:"]
    for path, snippets in sorted(by_file.items())[:20]:
        lines.append(path)
        lines.extend(snippets[:5])
    return result_success(intent, "\n".join(lines), data={"files": list(by_file.keys())})
