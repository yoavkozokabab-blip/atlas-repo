"""Structured findings extracted from supervised task step outputs."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

# Trading-algo review categories (Phase 20)
TRADING_CATEGORIES = frozenset(
    {
        "ranking_mismatch",
        "backtest_vs_live_entry",
        "stale_prices",
        "rejected_skipped_reasons",
        "risk_gates",
        "delayed_entry_logic",
        "stop_loss_early_exit",
        "portfolio_capacity",
        "dashboard_paper_mismatch",
        "failed_tests",
        "dashboard_log_issues",
        "risk_entry_exit_refs",
        "suspicious_pattern",
        "general_evidence",
    }
)

_CATEGORY_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("ranking_mismatch", re.compile(r"rank(ing)?\s*mismatch|rank\s*score|sort\s*order", re.I), "high"),
    ("backtest_vs_live_entry", re.compile(r"backtest.*live|live.*backtest|paper.*entry|entry\s*condition", re.I), "high"),
    ("stale_prices", re.compile(r"stale\s*price|old\s*quote|price\s*age|outdated\s*tick", re.I), "medium"),
    ("rejected_skipped_reasons", re.compile(r"reject(ed)?|skipped|blocked\s*trade|refus", re.I), "medium"),
    ("risk_gates", re.compile(r"risk\s*gate|risk_per_trade|exposure|max_positions|kill\s*switch", re.I), "high"),
    ("delayed_entry_logic", re.compile(r"delayed\s*entry|delay_entry|entry\s*delay", re.I), "medium"),
    ("stop_loss_early_exit", re.compile(r"stop[- ]?loss|early\s*exit|take\s*profit|exit\s*signal", re.I), "medium"),
    ("portfolio_capacity", re.compile(r"capacity|position\s*limit|portfolio\s*full|slot", re.I), "medium"),
    ("dashboard_paper_mismatch", re.compile(r"dashboard.*(down|offline|mismatch)|8077|paper\s*state", re.I), "high"),
    ("failed_tests", re.compile(r"pytest.*fail|FAILED|exit\s*[1-9]|test\s*failed", re.I), "high"),
    ("dashboard_log_issues", re.compile(r"error|exception|traceback|health.*fail", re.I), "medium"),
]

_FILE_PATTERN = re.compile(
    r"([\w./\\-]+\.(?:py|ps1|json|md|yaml|yml|log))(?:\s*:\s*(\d+))?",
    re.I,
)


@dataclass
class TaskFinding:
    finding_id: str
    category: str
    title: str
    evidence: str
    likely_causes: list[str] = field(default_factory=list)
    severity: str = "medium"
    files_involved: list[str] = field(default_factory=list)
    suggested_next_checks: list[str] = field(default_factory=list)
    source_step_id: str = ""


def _is_trading_objective(objective: str) -> bool:
    lower = (objective or "").lower()
    return any(
        k in lower
        for k in (
            "algorithm",
            "trading",
            "backtest",
            "paper",
            "dashboard",
            "failure",
            "live",
        )
    )


def _extract_files(text: str) -> list[str]:
    found: list[str] = []
    for m in _FILE_PATTERN.finditer(text):
        path = m.group(1).replace("\\", "/")
        if path not in found:
            found.append(path)
    return found[:15]


def _infer_category(text: str, command_key: str) -> tuple[str, str]:
    blob = f"{text} {command_key}"
    for cat, pat, sev in _CATEGORY_PATTERNS:
        if pat.search(blob):
            return cat, sev
    if command_key == "pytest":
        return "failed_tests", "high"
    if command_key in ("diagnose_dashboard", "show_last_errors"):
        return "dashboard_log_issues", "medium"
    if command_key in ("find_function", "find_class", "search_code"):
        return "risk_entry_exit_refs", "low"
    return "general_evidence", "low"


def _likely_causes_for(category: str) -> list[str]:
    mapping = {
        "ranking_mismatch": ["Signal ranking differs between backtest and live paths"],
        "backtest_vs_live_entry": ["Entry filters not aligned across modes"],
        "stale_prices": ["Market data cache TTL or feed lag"],
        "rejected_skipped_reasons": ["Risk gate or validation rule firing"],
        "risk_gates": ["Exposure or per-trade limits reached"],
        "delayed_entry_logic": ["Timer/bar alignment between backtest and live"],
        "stop_loss_early_exit": ["Exit rules differ in paper vs backtest"],
        "portfolio_capacity": ["Max positions or capital allocation hit"],
        "dashboard_paper_mismatch": ["Dashboard offline or state file drift"],
        "failed_tests": ["Regression or environment mismatch"],
        "dashboard_log_issues": ["Service error or misconfiguration"],
    }
    return mapping.get(category, ["Needs manual verification"])


def _next_checks_for(category: str) -> list[str]:
    mapping = {
        "ranking_mismatch": ["run task step: search_code for rank", "compare backtest logs"],
        "backtest_vs_live_entry": ["inspect entry filter functions", "read_logs for entry events"],
        "stale_prices": ["find_config_key price TTL", "check feed timestamps in logs"],
        "failed_tests": ["run task step: pytest", "show_last_errors"],
        "dashboard_paper_mismatch": ["run diagnostics", "show_dashboard_health"],
    }
    return mapping.get(category, ["show_task_findings", "propose_task_patch"])


def extract_findings_from_step(
    *,
    objective: str,
    step_id: str,
    command_key: str,
    result_summary: str,
    success: bool,
) -> list[TaskFinding]:
    """Parse step output into structured findings (no file writes)."""
    text = (result_summary or "").strip()
    if not text:
        return []

    findings: list[TaskFinding] = []
    files = _extract_files(text)
    category, severity = _infer_category(text, command_key)
    if not success:
        severity = "high"
        category = "failed_tests" if command_key == "pytest" else category

    title = f"{category.replace('_', ' ').title()} from {step_id}"
    finding = TaskFinding(
        finding_id=f"f_{uuid.uuid4().hex[:8]}",
        category=category,
        title=title,
        evidence=text[:1200],
        likely_causes=_likely_causes_for(category),
        severity=severity,
        files_involved=files,
        suggested_next_checks=_next_checks_for(category),
        source_step_id=step_id,
    )
    findings.append(finding)

    if _is_trading_objective(objective):
        for cat, pat, sev in _CATEGORY_PATTERNS:
            if cat == category:
                continue
            if pat.search(text):
                findings.append(
                    TaskFinding(
                        finding_id=f"f_{uuid.uuid4().hex[:8]}",
                        category=cat,
                        title=f"Trading signal: {cat.replace('_', ' ')}",
                        evidence=pat.pattern[:80] + " matched in step output",
                        likely_causes=_likely_causes_for(cat),
                        severity=sev,
                        files_involved=files,
                        suggested_next_checks=_next_checks_for(cat),
                        source_step_id=step_id,
                    )
                )

    return findings


def merge_findings(session_findings: list[TaskFinding], new: list[TaskFinding]) -> None:
    seen = {(f.category, f.source_step_id, f.evidence[:80]) for f in session_findings}
    for f in new:
        key = (f.category, f.source_step_id, f.evidence[:80])
        if key not in seen:
            session_findings.append(f)
            seen.add(key)


def format_findings_grouped(findings: list[TaskFinding]) -> str:
    if not findings:
        return "No structured findings yet. Run task steps first."

    lines = ["Task findings (grouped)", ""]
    by_sev: dict[str, list[TaskFinding]] = {"high": [], "medium": [], "low": []}
    for f in findings:
        by_sev.setdefault(f.severity, []).append(f)

    for sev in ("high", "medium", "low"):
        group = by_sev.get(sev) or []
        if not group:
            continue
        lines.append(f"## Severity: {sev.upper()}")
        for f in group:
            lines.append(f"### {f.title} [{f.category}]")
            lines.append(f"- **Evidence:** {f.evidence[:400]}")
            if f.likely_causes:
                lines.append("- **Likely causes:**")
                lines.extend(f"  - {c}" for c in f.likely_causes)
            if f.files_involved:
                lines.append("- **Files involved:** " + ", ".join(f.files_involved[:8]))
            if f.suggested_next_checks:
                lines.append("- **Suggested next checks:**")
                lines.extend(f"  - {c}" for c in f.suggested_next_checks)
            lines.append("")
    return "\n".join(lines)
