"""Patch proposals — preview-only unified diffs (never auto-applied)."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from config import PROJECT_ROOT, TRADING_PROJECT_ROOT
from task_agent.findings import TaskFinding

BLOCKED_TARGET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(^|/)\.env$", re.I),
    re.compile(r"secret", re.I),
    re.compile(r"credential", re.I),
    re.compile(r"password", re.I),
    re.compile(r"token", re.I),
    re.compile(r"session_state\.json", re.I),
    re.compile(r"approved_(apps|websites)\.json", re.I),
    re.compile(r"memory\.json", re.I),
    re.compile(r"settings\.json", re.I),
]

BLOCKED_DIFF_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"enable\s*live\s*trad", re.I),
    re.compile(r"disable\s*kill\s*switch", re.I),
    re.compile(r"run_live_daily", re.I),
    re.compile(r"^\-\-\-\s*deleted", re.I),
    re.compile(r"^-\s*rm\s+", re.I),
]


@dataclass
class PatchProposal:
    proposal_id: str
    target_files: list[str] = field(default_factory=list)
    rationale: str = ""
    unified_diff: str = ""
    risk_level: str = "medium"
    tests_to_run: list[str] = field(default_factory=list)
    rollback_plan: str = ""
    status: str = "draft"  # draft | approved | rejected


def _allowed_roots() -> list[Path]:
    return [PROJECT_ROOT.resolve(), TRADING_PROJECT_ROOT.resolve()]


def validate_patch_target(path: str) -> tuple[bool, str]:
    p = (path or "").strip().replace("\\", "/")
    if not p:
        return False, "Empty target path."
    for pat in BLOCKED_TARGET_PATTERNS:
        if pat.search(p):
            return False, f"Target blocked by safety policy: {p}"
    if ".." in p:
        return False, "Path traversal not allowed."
    candidate = Path(p)
    if not candidate.is_absolute():
        for root in _allowed_roots():
            try:
                (root / p).resolve().relative_to(root)
                return True, ""
            except ValueError:
                continue
        return False, f"Target must be under project or trading root: {p}"
    for root in _allowed_roots():
        try:
            candidate.resolve().relative_to(root)
            return True, ""
        except ValueError:
            continue
    return False, f"Target outside allowed roots: {p}"


def validate_diff_text(diff: str) -> tuple[bool, str]:
    text = diff or ""
    for pat in BLOCKED_DIFF_PATTERNS:
        if pat.search(text):
            return False, "Diff contains blocked live-trading or delete patterns."
    if re.search(r"^\-\-\-\s+a/.*\.env", text, re.M | re.I):
        return False, "Cannot propose .env edits."
    return True, ""


def _pick_target_file(findings: list[TaskFinding], objective: str) -> str:
    for f in findings:
        for path in f.files_involved:
            ok, _ = validate_patch_target(path)
            if ok and path.endswith(".py"):
                return path
    lower = (objective or "").lower()
    if "trading" in lower or "algorithm" in lower:
        for candidate in ("strategy/risk_checks.py", "scripts/run_live_daily.ps1"):
            ok, _ = validate_patch_target(candidate)
            if ok:
                return candidate
    for candidate in ("task_agent/safety.py", "brain/router.py"):
        ok, _ = validate_patch_target(candidate)
        if ok:
            return candidate
    return "task_agent/safety.py"


def build_patch_proposal(
    *,
    objective: str,
    findings: list[TaskFinding],
) -> PatchProposal | None:
    """Create a preview-only patch proposal from findings (does not touch disk)."""
    if not findings:
        return None

    target = _pick_target_file(findings, objective)
    ok, reason = validate_patch_target(target)
    if not ok:
        return None

    top = findings[0]
    cats = sorted({f.category for f in findings})
    rationale = (
        f"Investigation proposal for: {objective[:200]}. "
        f"Categories: {', '.join(cats)}. "
        f"Primary evidence: {top.evidence[:300]}"
    )

    diff_lines = [
        f"--- a/{target}",
        f"+++ b/{target}",
        "@@ -1,6 +1,8 @@",
        " # JARVIS task-agent patch PREVIEW — NOT APPLIED",
        " # Review before any manual apply.",
        "+# TODO(investigation): align logic with findings",
        "+#   - see task report evidence section",
        " def _placeholder_guard():",
        "     pass",
    ]
    if "stale" in " ".join(cats):
        diff_lines.insert(
            6,
            "+# NOTE: add explicit stale-price guard (preview only)",
        )
    if "delayed_entry" in " ".join(cats):
        diff_lines.insert(
            6,
            "+# NOTE: verify delayed_entry bar alignment backtest vs live",
        )

    unified = "\n".join(diff_lines)
    ok, msg = validate_diff_text(unified)
    if not ok:
        return None

    risk = "high" if any(f.severity == "high" for f in findings) else "medium"
    return PatchProposal(
        proposal_id=f"patch_{uuid.uuid4().hex[:8]}",
        target_files=[target],
        rationale=rationale,
        unified_diff=unified,
        risk_level=risk,
        tests_to_run=["py -3 -m pytest -q", "py -3 -m compileall ."],
        rollback_plan="Do not apply this diff. If applied manually, revert with git checkout -- <file>.",
        status="draft",
    )


def format_patch_proposal(proposal: PatchProposal) -> str:
    lines = [
        f"Patch proposal: {proposal.proposal_id}",
        f"Status: {proposal.status}",
        f"Risk: {proposal.risk_level}",
        "",
        "Target files:",
    ]
    lines.extend(f"  - {t}" for t in proposal.target_files)
    lines.extend(["", "Rationale:", proposal.rationale, "", "Tests to run:"])
    lines.extend(f"  - {t}" for t in proposal.tests_to_run)
    lines.extend(["", "Rollback plan:", proposal.rollback_plan, "", "Unified diff (preview only):", "```diff"])
    lines.append(proposal.unified_diff)
    lines.append("```")
    lines.append("")
    lines.append("_This diff is NOT applied automatically._")
    return "\n".join(lines)


def approve_proposal(proposal: PatchProposal) -> None:
    proposal.status = "approved"


def reject_proposal(proposal: PatchProposal) -> None:
    proposal.status = "rejected"
