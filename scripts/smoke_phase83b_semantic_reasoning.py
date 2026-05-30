"""Smoke Phase 83B semantic benchmark against a local QuixBugs checkout."""

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
        if (
            (candidate / "python_programs" / "breadth_first_search.py").is_file()
            and (candidate / "correct_python_programs" / "breadth_first_search.py").is_file()
        ):
            return candidate
    return None


def main() -> int:
    project = _find_quixbugs()
    if project is None:
        print("SKIP: QuixBugs is not available locally.")
        print(r"Setup: git clone https://github.com/jkoppel/QuixBugs.git C:\Repos\QuixBugs")
        print(r"Then run: py -3 scripts\smoke_phase83b_semantic_reasoning.py")
        return 0

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "builder_core.cli",
            "benchmark-quixbugs",
            "--project",
            str(project),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip(), file=sys.stderr)
    if result.returncode != 0:
        print(f"SMOKE FAILED: exit={result.returncode}")
        return result.returncode
    if "bfs_queue_exhaustion" not in result.stdout:
        print("SMOKE FAILED: semantic BFS finding missing")
        return 1
    print("SMOKE PASS phase83b_semantic_reasoning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
