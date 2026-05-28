"""Bounded read-only project helpers (git, pytest, files)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from config import PROJECT_ROOT, TRADING_PROJECT_ROOT
from vision.redaction import redact_sensitive_text

_MAX_OUTPUT = 4000
_SUBPROCESS_TIMEOUT = 45


def resolve_project_root(explicit: str | None = None) -> Path:
    root = Path(explicit or PROJECT_ROOT).resolve()
    return root


def _under_allowed_root(path: Path) -> bool:
    path = path.resolve()
    for base in (PROJECT_ROOT.resolve(), Path(TRADING_PROJECT_ROOT).resolve()):
        try:
            if base in path.parents or path == base:
                return True
        except (OSError, ValueError):
            continue
    return False


def run_git_summary(project_root: Path | None = None, *, max_commits: int = 8) -> str:
    root = resolve_project_root(str(project_root) if project_root else None)
    if not _under_allowed_root(root):
        return "Project root not under allowed paths."
    if not (root / ".git").exists():
        return f"Not a git repository: {root}"
    try:
        log = subprocess.run(
            ["git", "-C", str(root), "log", f"-{max_commits}", "--oneline"],
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
            check=False,
        )
        stat = subprocess.run(
            ["git", "-C", str(root), "diff", "--stat", "HEAD~5..HEAD"],
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"Git summary failed: {exc}"
    parts = ["Recent commits:", redact_sensitive_text((log.stdout or log.stderr or "").strip())]
    diff_out = (stat.stdout or stat.stderr or "").strip()
    if diff_out:
        parts.append("\nDiff stat (last ~5 commits):\n" + redact_sensitive_text(diff_out))
    text = "\n".join(parts)
    return text[:_MAX_OUTPUT]


def run_pytest_summary(project_root: Path | None = None) -> str:
    if os.getenv("PYTEST_CURRENT_TEST"):
        return "pytest summary skipped during test run (avoid nested suite)."
    root = resolve_project_root(str(project_root) if project_root else None)
    if not _under_allowed_root(root):
        return "Project root not under allowed paths."
    tests_dir = root / "tests"
    target = str(tests_dir) if tests_dir.is_dir() else str(root)
    try:
        proc = subprocess.run(
            [
                "py",
                "-3",
                "-m",
                "pytest",
                target,
                "-q",
                "--tb=no",
                "--maxfail=3",
            ],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"pytest failed to run: {exc}"
    tail = (proc.stdout or "") + (proc.stderr or "")
    lines = tail.strip().splitlines()
    summary = "\n".join(lines[-25:]) if lines else "(no output)"
    header = f"pytest exit code: {proc.returncode}"
    return redact_sensitive_text(f"{header}\n{summary}")[:_MAX_OUTPUT]


def read_project_file(rel_path: str, project_root: Path | None = None, *, max_chars: int = 3000) -> str:
    root = resolve_project_root(str(project_root) if project_root else None)
    if not _under_allowed_root(root):
        return "Path outside allowed project roots."
    target = (root / rel_path).resolve()
    if not _under_allowed_root(target):
        return "File path escapes project root."
    if not target.is_file():
        return f"File not found: {rel_path}"
    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"Could not read file: {exc}"
    return redact_sensitive_text(text[:max_chars])
