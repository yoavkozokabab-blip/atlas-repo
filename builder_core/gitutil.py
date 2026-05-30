"""Read-only git helpers.

All functions are best-effort: if git is missing, the path is not a repo,
or any command fails, they return safe empty defaults instead of raising.
Nothing here ever writes to the repository.
"""

from __future__ import annotations

import subprocess
from typing import Dict, List, Optional

_TIMEOUT = 15


def _run(args: List[str], cwd: str) -> Optional[str]:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def is_repo(cwd: str) -> bool:
    out = _run(["rev-parse", "--is-inside-work-tree"], cwd)
    return out == "true"


def current_commit(cwd: str) -> Optional[str]:
    return _run(["rev-parse", "HEAD"], cwd)


def current_branch(cwd: str) -> Optional[str]:
    out = _run(["rev-parse", "--abbrev-ref", "HEAD"], cwd)
    return out or None


def recent_log(cwd: str, limit: int = 400) -> List[Dict[str, str]]:
    """Return recent commits as dicts: hash, author, date, subject."""
    fmt = "%H%x1f%an%x1f%ad%x1f%s"
    out = _run(
        ["log", f"-n{limit}", "--date=short", f"--pretty=format:{fmt}"], cwd
    )
    if not out:
        return []
    commits: List[Dict[str, str]] = []
    for line in out.splitlines():
        parts = line.split("\x1f")
        if len(parts) != 4:
            continue
        commits.append(
            {
                "hash": parts[0],
                "author": parts[1],
                "date": parts[2],
                "subject": parts[3],
            }
        )
    return commits


def churn_counts(cwd: str, limit: int = 400) -> Dict[str, int]:
    """Map of relative file path -> number of recent commits that touched it."""
    out = _run(
        ["log", f"-n{limit}", "--name-only", "--pretty=format:%x00"], cwd
    )
    if not out:
        return {}
    counts: Dict[str, int] = {}
    for raw in out.splitlines():
        line = raw.strip()
        if not line or line == "\x00":
            continue
        # normalise separators so it matches index paths
        path = line.replace("\\", "/")
        counts[path] = counts.get(path, 0) + 1
    return counts
