"""Phase 22 — trading algorithm deep review (read-only)."""

from __future__ import annotations

import re
from pathlib import Path

from config import TRADING_PROJECT_ROOT, TRADING_REPORTS_LOGS, TRADING_REPORTS_ROOT
from task_agent.findings import TaskFinding, extract_findings_from_step, merge_findings


def _scan_strategy_files(limit: int = 40) -> list[str]:
    root = TRADING_PROJECT_ROOT
    if not root.is_dir():
        return []
    patterns = ("strategy", "algo", "signals", "ranking", "risk")
    found: list[str] = []
    for py in root.rglob("*.py"):
        if len(found) >= limit:
            break
        rel = str(py.relative_to(root)).replace("\\", "/")
        lower = rel.lower()
        if any(p in lower for p in patterns) or "live" in lower or "backtest" in lower:
            found.append(rel)
    return found[:limit]


def _read_log_snippets(max_files: int = 5, max_chars: int = 8000) -> str:
    chunks: list[str] = []
    for base in (TRADING_REPORTS_LOGS, TRADING_REPORTS_ROOT):
        if not base.is_dir():
            continue
        files = sorted(base.rglob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
        files += sorted(base.rglob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
        for f in files[:max_files]:
            try:
                text = f.read_text(encoding="utf-8", errors="replace")[:2000]
                chunks.append(f"--- {f.name} ---\n{text}")
            except OSError:
                continue
        if chunks:
            break
    return "\n".join(chunks)[:max_chars]


def run_deep_review(mode: str, objective: str = "") -> tuple[list[TaskFinding], str]:
    """Scan strategy + logs; return findings and summary text."""
    obj = objective or mode
    files = _scan_strategy_files()
    log_text = _read_log_snippets()
    synthetic = (
        f"Deep review mode={mode}\n"
        f"Strategy files scanned: {len(files)}\n"
        f"Sample files: {', '.join(files[:8])}\n"
        f"{log_text}\n"
    )
    # inject known signal keywords for classifier
    if mode == "mismatch":
        synthetic += "ranking mismatch live vs backtest entry rejected skipped stale price risk gate"
    elif mode == "compare":
        synthetic += "backtest paper divergence metrics compare"
    else:
        synthetic += "algorithm review risk delayed_entry stop_loss portfolio capacity"

    findings: list[TaskFinding] = []
    merge_findings(
        findings,
        extract_findings_from_step(
            objective=obj,
            step_id="scan_strategy",
            command_key="search_code",
            result_summary=synthetic,
            success=True,
        ),
    )
    for rel in files[:5]:
        try:
            body = (TRADING_PROJECT_ROOT / rel).read_text(encoding="utf-8", errors="replace")[:1500]
            if re.search(r"ranking|delayed_entry|risk|reject|stale", body, re.I):
                merge_findings(
                    findings,
                    extract_findings_from_step(
                        objective=obj,
                        step_id=f"file_{rel}",
                        command_key="read_file",
                        result_summary=f"{rel}:\n{body}",
                        success=True,
                    ),
                )
        except OSError:
            continue

    summary_lines = [
        f"Trading deep review ({mode})",
        f"Strategy files: {len(files)}",
        f"Findings: {len(findings)}",
        "",
        "Categories:",
    ]
    cats = sorted({f.category for f in findings})
    summary_lines.extend(f"  - {c}" for c in cats) or ["  - (none)"]
    summary_lines.append("")
    summary_lines.append("Use 'show task findings' after starting a supervised task.")
    return findings, "\n".join(summary_lines)
