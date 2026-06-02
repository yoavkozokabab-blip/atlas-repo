"""Smoke test for the Phase 86 Data Flow Analysis fact layer.

Runs the fact extractor on C:\\Repos\\QuixBugs\\python_programs\\
breadth_first_search.py (if present) and prints:
  1. the extracted data-flow facts (JSON), and
  2. an explanation of why the BFS bug is representable WITHOUT name matching.

If QuixBugs is not present, it falls back to an embedded copy of the same buggy
function so the demonstration still runs. Read-only; nothing is modified.

Run:
    py -3 builder_core/scripts/smoke_phase86_dataflow.py
"""

from __future__ import annotations

import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from builder_core.bug_intelligence import dataflow  # noqa: E402

QUIXBUGS_BFS = r"C:\Repos\QuixBugs\python_programs\breadth_first_search.py"

# Embedded fallback: the QuixBugs buggy BFS (while True instead of while queue).
FALLBACK_SRC = '''
from collections import deque as Queue

def breadth_first_search(startnode, goalnode):
    queue = Queue()
    queue.append(startnode)

    nodesseen = set()
    nodesseen.add(startnode)

    while True:
        node = queue.popleft()

        if node is goalnode:
            return True
        else:
            queue.extend(node for node in node.successors if node not in nodesseen)
            nodesseen.update(node.successors)

    return False
'''


def _section(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def main() -> int:
    if os.path.isfile(QUIXBUGS_BFS):
        source_label = QUIXBUGS_BFS
        facts = dataflow.analyze_file(QUIXBUGS_BFS)
    else:
        source_label = "<embedded fallback copy of QuixBugs breadth_first_search>"
        facts = dataflow.analyze_source(FALLBACK_SRC, path="breadth_first_search.py")

    print(f"Source analyzed: {source_label}")

    _section("1. EXTRACTED DATA-FLOW FACTS")
    print(json.dumps(facts, indent=2))

    _section("2. WHY THE BFS BUG IS REPRESENTABLE WITHOUT NAME MATCHING")
    hits = dataflow.find_unguarded_consumption_loops(facts)

    print(
        "The detector below NEVER reads the function name. It queries only\n"
        "structural facts. The bug shape is the conjunction:\n"
        "   (a) a container is consumed inside a loop, AND\n"
        "   (b) the loop guard does not depend on that container, AND\n"
        "   (c) there is no explicit empty-container exit before consumption.\n"
    )

    if not hits:
        print("No unguarded-consumption loop found in this source.")
        # In QuixBugs the bug is present, so absence here is itself informative.
        ok = False
    else:
        ok = True
        for h in hits:
            print(f"- function '{h['function']}' loop @ line {h['loop_line']}:")
            for reason in h["reasons"]:
                print(f"    * {reason}")

    # Show the raw booleans that make the case, name-free.
    _section("3. THE NAME-FREE EVIDENCE (per while-loop)")
    for fn in facts.get("functions", []):
        for loop in fn.get("loops", []):
            if loop["type"] != "while":
                continue
            print(
                f"loop@{loop['line']}: guard={loop['guard']!r} "
                f"guard_vars={loop['guard_vars']} "
                f"consumes={loop['consumes']} "
                f"termination_depends_on_consumed_container="
                f"{loop['termination_depends_on_consumed_container']} "
                f"has_empty_guard_before_consume={loop['has_empty_guard_before_consume']} "
                f"=> unguarded_consumption={loop['unguarded_consumption']}"
            )

    _section("RESULT")
    if ok:
        print("SMOKE PASSED — BFS bug represented purely as data-flow facts, no names used.")
        return 0
    print("SMOKE FAILED — expected an unguarded-consumption loop in the BFS source.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
