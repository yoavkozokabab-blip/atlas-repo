"""Trading log intelligence (read-only)."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from actions.base import BaseAction
from actions.log_utils import (
    ERROR_KEYWORDS,
    REJECTION_REASONS,
    aggregate_reason_counts,
    expand_log_query,
    iter_recent_log_files,
    latest_log_file,
    lines_matching,
    read_tail,
)
from core.results import result_failed, result_success
from core.types import CommandRequest, CommandResult, Intent


def _collect_error_lines(max_files: int = 10) -> tuple[list[str], Path | None]:
    all_lines: list[str] = []
    source: Path | None = None
    for path in iter_recent_log_files(max_files=max_files):
        lines = read_tail(path, max_lines=500)
        hits = lines_matching(lines, ERROR_KEYWORDS)
        if hits:
            if source is None:
                source = path
            all_lines.extend(f"[{path.name}] {ln}" for ln in hits[-15:])
    return all_lines[-40:], source


class ShowLastErrorsAction(BaseAction):
    intent = Intent.SHOW_LAST_ERRORS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        path = request.params.get("path")
        if path:
            lines = read_tail(Path(path))
            hits = lines_matching(lines, ERROR_KEYWORDS)[-30:]
            if not hits:
                return result_failed(
                    Intent.SHOW_LAST_ERRORS,
                    f"No error lines in {path}.",
                )
            summary = "\n".join(hits)
            return result_success(
                Intent.SHOW_LAST_ERRORS,
                f"Errors in {Path(path).name}:\n{summary}",
                data={"path": str(path), "lines": hits},
            )

        hits, source = _collect_error_lines()
        if not hits:
            return result_failed(
                Intent.SHOW_LAST_ERRORS,
                "No recent error lines found in trading logs.",
            )
        summary = "\n".join(hits)
        data = {"lines": hits}
        if source:
            data["path"] = str(source)
        return result_success(
            Intent.SHOW_LAST_ERRORS,
            f"Recent errors ({len(hits)} lines):\n{summary}",
            data=data,
        )


class SummarizeLatestLogAction(BaseAction):
    intent = Intent.SUMMARIZE_LATEST_LOG.value

    def execute(self, request: CommandRequest) -> CommandResult:
        override = request.params.get("path")
        path = Path(override) if override else latest_log_file()
        if path is None or not path.is_file():
            return result_failed(
                Intent.SUMMARIZE_LATEST_LOG,
                "No log file found to summarize.",
            )

        lines = read_tail(path)
        errors = lines_matching(lines, ERROR_KEYWORDS)
        warnings = [ln for ln in lines if re.search(r"warning", ln, re.I)]
        reasons = aggregate_reason_counts(lines)

        parts = [
            f"File: {path}",
            f"Modified: {path.stat().st_mtime:.0f}",
            f"Lines scanned (tail): {len(lines)}",
            f"Error-like lines: {len(errors)}",
            f"Warning lines: {len(warnings)}",
        ]
        if reasons:
            parts.append("Top rejection/block reasons:")
            for reason, count in reasons.most_common(8):
                parts.append(f"  - {reason}: {count}")
        parts.append("Last meaningful lines:")
        meaningful = [ln for ln in lines if ln.strip()][-20:]
        parts.extend(meaningful)

        summary = "\n".join(parts)
        return result_success(
            Intent.SUMMARIZE_LATEST_LOG,
            summary,
            data={"path": str(path), "error_count": len(errors)},
        )


class SearchTradingLogsAction(BaseAction):
    intent = Intent.SEARCH_TRADING_LOGS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        query = (
            request.params.get("query")
            or request.raw_text
        )
        query = expand_log_query(str(query))
        if not query.strip():
            return result_failed(Intent.SEARCH_TRADING_LOGS, "Missing search query.")

        pat = re.compile(re.escape(query.split()[0]) if " " not in query else query, re.I)
        # Search each token if multi-word from expansion
        tokens = [t for t in query.split() if len(t) > 2]
        if not tokens:
            tokens = [query]

        matches: list[str] = []
        for path in iter_recent_log_files():
            for line in read_tail(path, max_lines=300):
                if any(t.lower() in line.lower() for t in tokens):
                    matches.append(f"{path.name}: {line.strip()}")
            if len(matches) >= 50:
                break

        if not matches:
            return result_failed(
                Intent.SEARCH_TRADING_LOGS,
                f"No matches for '{query}' in recent logs.",
                data={"search_query": query},
            )
        summary = "\n".join(matches[:40])
        return result_success(
            Intent.SEARCH_TRADING_LOGS,
            f"Log search '{query}' ({len(matches)} hits):\n{summary}",
            data={"search_query": query, "match_count": len(matches)},
        )


class ShowRejectionReasonsAction(BaseAction):
    intent = Intent.SHOW_REJECTION_REASONS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        combined: Counter[str] = Counter()
        samples: list[str] = []
        for path in iter_recent_log_files():
            lines = read_tail(path)
            combined.update(aggregate_reason_counts(lines))
            for reason in REJECTION_REASONS:
                for ln in lines:
                    if reason in ln.lower():
                        samples.append(f"{path.name}: {ln.strip()}")
                        break

        if not combined:
            return result_failed(
                Intent.SHOW_REJECTION_REASONS,
                "No rejection reason patterns found in recent logs.",
            )
        lines_out = ["Rejection/block reason counts:"]
        for reason, count in combined.most_common():
            lines_out.append(f"  {reason}: {count}")
        if samples:
            lines_out.append("Samples:")
            lines_out.extend(samples[:10])
        summary = "\n".join(lines_out)
        return result_success(
            Intent.SHOW_REJECTION_REASONS,
            summary,
            data={"counts": dict(combined)},
        )


class ShowBlockedTradesAction(BaseAction):
    intent = Intent.SHOW_BLOCKED_TRADES.value

    def execute(self, request: CommandRequest) -> CommandResult:
        pattern = re.compile(
            r"blocked|rejected|skipped",
            re.IGNORECASE,
        )
        symbol_pat = re.compile(r"\b[A-Z]{1,5}\b")
        hits: list[str] = []
        for path in iter_recent_log_files():
            for line in read_tail(path, max_lines=400):
                if pattern.search(line):
                    sym = symbol_pat.search(line)
                    tag = f" [{sym.group()}]" if sym else ""
                    hits.append(f"{path.name}{tag}: {line.strip()}")
            if len(hits) >= 35:
                break

        if not hits:
            return result_failed(
                Intent.SHOW_BLOCKED_TRADES,
                "No blocked/rejected/skipped trade lines in recent logs.",
            )
        summary = "\n".join(hits[:35])
        return result_success(
            Intent.SHOW_BLOCKED_TRADES,
            f"Blocked/skipped trades ({len(hits)} lines):\n{summary}",
            data={"line_count": len(hits)},
        )


class ShowRecentTradingHistoryAction(BaseAction):
    intent = Intent.SHOW_RECENT_TRADING_HISTORY.value

    def execute(self, request: CommandRequest) -> CommandResult:
        trade_pat = re.compile(
            r"trade|filled|order|position|symbol",
            re.IGNORECASE,
        )
        hits: list[str] = []
        for path in iter_recent_log_files():
            for line in read_tail(path, max_lines=250):
                if trade_pat.search(line):
                    hits.append(f"{path.name}: {line.strip()}")
            if len(hits) >= 30:
                break

        if not hits:
            return result_failed(
                Intent.SHOW_RECENT_TRADING_HISTORY,
                "No recent trading history lines found.",
            )
        return result_success(
            Intent.SHOW_RECENT_TRADING_HISTORY,
            "Recent trading history:\n" + "\n".join(hits[:30]),
            data={"line_count": len(hits)},
        )
