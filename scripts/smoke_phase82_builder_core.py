"""Smoke Phase 82 Builder Core against a local QuixBugs checkout if available."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATES = (
    Path(r"C:\Repos\QuixBugs"),
    Path(r"C:\QuixBugs"),
    Path(r"D:\Repos\QuixBugs"),
)


def _find_quixbugs() -> Path | None:
    configured = os.getenv("QUIXBUGS_PATH")
    candidates = (Path(configured), *DEFAULT_CANDIDATES) if configured else DEFAULT_CANDIDATES
    for candidate in candidates:
        if (candidate / "python_programs" / "breadth_first_search.py").is_file():
            return candidate
    return None


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "builder_core.cli", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )


def main() -> int:
    project = _find_quixbugs()
    if project is None:
        print("SKIP: QuixBugs is not available locally.")
        print(r"Setup: git clone https://github.com/jkoppel/QuixBugs.git C:\Repos\QuixBugs")
        print(
            r"Then run: py -3 scripts\smoke_phase82_builder_core.py"
        )
        return 0

    commands = (
        ("init", "--project", str(project)),
        (
            "ask",
            "--project",
            str(project),
            "Analyze python_programs/breadth_first_search.py for likely bugs and logic errors.",
        ),
        ("risk-report", "--project", str(project), "--top", "10"),
    )
    for command in commands:
        print(f"$ py -3 -m builder_core.cli {' '.join(command)}")
        result = _run(*command)
        if result.stdout:
            print(result.stdout.rstrip())
        if result.stderr:
            print(result.stderr.rstrip(), file=sys.stderr)
        if result.returncode != 0:
            print(f"SMOKE FAILED: exit={result.returncode}")
            return result.returncode

    print("SMOKE PASS phase82_builder_core")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
