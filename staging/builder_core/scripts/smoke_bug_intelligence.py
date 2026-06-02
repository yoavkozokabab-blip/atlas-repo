"""Smoke test for the Bug Intelligence subsystem (Phase 83).

Drives the real CLI via ``python -m builder_core.cli`` against:
  1. a synthetic repo containing canonical logic bugs, and
  2. the QuixBugs dataset at C:\\Repos\\QuixBugs, *if present* (never downloaded).

Writes nothing outside its own temp directory; never modifies QuixBugs.

Run:
    py -3 builder_core/scripts/smoke_bug_intelligence.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
QUIXBUGS_DEFAULT = r"C:\Repos\QuixBugs"


def _write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(textwrap.dedent(content))


def _build_synthetic_repo(root: str) -> None:
    # BFS that pops from the end of a list -> behaves depth-first
    _write(os.path.join(root, "python_programs", "breadth_first_search.py"), """
        def breadth_first_search(startnode, goalnode):
            queue = [startnode]
            nodesseen = set()
            nodesseen.add(startnode)
            while queue:
                node = queue.pop()
                if node is goalnode:
                    return True
                for successor in node.successors:
                    if successor not in nodesseen:
                        nodesseen.add(successor)
                        queue.append(successor)
            return False
    """)
    _write(os.path.join(root, "python_programs", "shortest_path.py"), """
        def shortest_path(graph, start, end):
            dist = {}
            for i in range(len(graph) + 1):
                dist[i] = 999999
            return dist
    """)
    _write(os.path.join(root, "python_programs", "graph_search.py"), """
        def graph_search(nodes):
            for n in nodes:
                if n.bad:
                    nodes.remove(n)
            return nodes
    """)
    _write(os.path.join(root, "python_programs", "safe_add.py"), """
        def safe_add(a, b):
            return a + b
    """)


def _run(root: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "builder_core.cli", *args],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )


def _section(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def main() -> int:
    failures = []

    with tempfile.TemporaryDirectory(prefix="bug_intel_smoke_") as tmp:
        root = os.path.join(tmp, "synthetic")
        os.makedirs(root)
        _build_synthetic_repo(root)
        print(f"Synthetic repo: {root}")

        # 1) analyze-file on the BFS bug
        _section("analyze-file python_programs/breadth_first_search.py")
        res = _run(root, "analyze-file", "--project", root,
                   "python_programs/breadth_first_search.py")
        print(res.stdout.strip())
        for token in ("SUMMARY", "FINDINGS", "EVIDENCE", "CONFIDENCE"):
            if token not in res.stdout:
                failures.append(f"analyze-file missing {token}")
        if "breadth" not in res.stdout.lower() and "stack" not in res.stdout.lower():
            failures.append("analyze-file did not explain BFS behavior")

        # 2) bug-scan
        _section("bug-scan")
        res = _run(root, "bug-scan", "--project", root, "--top", "10")
        print(res.stdout.strip())
        if "breadth_first_search.py" not in res.stdout:
            failures.append("bug-scan did not surface the BFS file")
        if "safe_add.py" in res.stdout:
            failures.append("bug-scan flagged the clean file")

        # 3) benchmark on the synthetic python_programs dir
        _section("benchmark-quixbugs (synthetic python_programs)")
        res = _run(root, "benchmark-quixbugs", "--project", root)
        print(res.stdout.strip())
        if "hit rate" not in res.stdout:
            failures.append("benchmark missing hit rate")

    # 4) Real QuixBugs, if present
    quixbugs = os.environ.get("QUIXBUGS_PATH", QUIXBUGS_DEFAULT)
    _section(f"QuixBugs dataset @ {quixbugs}")
    if os.path.isdir(quixbugs):
        res = _run(quixbugs, "benchmark-quixbugs", "--project", quixbugs)
        print(res.stdout.strip())
        if "hit rate" not in res.stdout:
            failures.append("quixbugs benchmark produced no hit rate")
    else:
        print("QuixBugs not found at this path — skipping (never auto-downloaded).")

    _section("RESULT")
    if failures:
        print("SMOKE FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("SMOKE PASSED — bug intelligence behaved correctly on all available targets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
