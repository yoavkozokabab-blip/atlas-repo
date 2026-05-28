"""Task agent safety — allowlists, limits, blocked operations."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from config import PROJECT_ROOT
from task_agent.models import StepKind, TaskStep

TASK_AGENT_MAX_STEPS = int(os.getenv("TASK_AGENT_MAX_STEPS", "12"))
TASK_AGENT_MAX_RUNTIME_SECONDS = float(os.getenv("TASK_AGENT_MAX_RUNTIME_SECONDS", "300"))

# Fixed allowlisted command keys → no user shell strings
READONLY_COMMAND_KEYS: frozenset[str] = frozenset(
    {
        "search_code",
        "find_function",
        "find_class",
        "read_logs",
        "show_last_errors",
        "run_diagnostics",
        "diagnose_dashboard",
        "diagnose_trading_loop",
        "diagnose_recent_errors",
        "pytest",
        "compileall",
        "summarize_findings",
    }
)

CONFIRM_COMMAND_KEYS: frozenset[str] = frozenset(
    {
        "create_branch",
        "write_patch",
        "edit_source",
        "run_long_backtest",
        "run_trading_loop",
    }
)

BLOCKED_COMMAND_KEYS: frozenset[str] = frozenset(
    {
        "delete_file",
        "delete_files",
        "move_money",
        "live_execution",
        "edit_env_secrets",
        "arbitrary_shell",
        "arbitrary_powershell",
        "browser_automation",
        "external_api",
    }
)

ALLOWED_SUBPROCESS_ARGV: dict[str, list[str]] = {
    "pytest": ["py", "-3", "-m", "pytest", "-q"],
    "compileall": ["py", "-3", "-m", "compileall", "."],
}

BLOCKED_PATH_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\.env$", re.I),
    re.compile(r"secrets?", re.I),
    re.compile(r"credentials", re.I),
]


@dataclass
class SafetyVerdict:
    ok: bool
    reason: str = ""
    kind: StepKind = StepKind.READONLY


def classify_command_key(command_key: str) -> StepKind:
    key = (command_key or "").strip().lower()
    if key in BLOCKED_COMMAND_KEYS:
        return StepKind.BLOCKED
    if key in CONFIRM_COMMAND_KEYS:
        return StepKind.CONFIRM_REQUIRED
    if key in READONLY_COMMAND_KEYS:
        return StepKind.READONLY
    return StepKind.BLOCKED


def validate_command_key(command_key: str) -> SafetyVerdict:
    key = (command_key or "").strip().lower()
    kind = classify_command_key(key)
    if kind == StepKind.BLOCKED:
        return SafetyVerdict(False, f"Command '{key}' is not allowlisted.", kind)
    return SafetyVerdict(True, kind=kind)


def validate_step(step: TaskStep) -> SafetyVerdict:
    verdict = validate_command_key(step.command_key)
    if not verdict.ok:
        step.kind = StepKind.BLOCKED
        step.status = step.status  # caller sets BLOCKED
        return verdict
    step.kind = verdict.kind
    if step.kind == StepKind.CONFIRM_REQUIRED:
        step.requires_separate_approval = True
    return verdict


def is_write_command(command_key: str) -> bool:
    return classify_command_key(command_key) == StepKind.CONFIRM_REQUIRED


def path_write_allowed(path: str) -> bool:
    p = (path or "").replace("\\", "/")
    for pat in BLOCKED_PATH_PATTERNS:
        if pat.search(p):
            return False
    resolved = (PROJECT_ROOT / p).resolve() if not os.path.isabs(p) else Path(p)
    try:
        resolved.relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        return False
    return True


def subprocess_argv_for(command_key: str) -> list[str] | None:
    """Return fixed argv only — never compose from user input."""
    return ALLOWED_SUBPROCESS_ARGV.get(command_key)
