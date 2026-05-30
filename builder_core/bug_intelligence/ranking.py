"""Ranking and benchmarking for Bug Intelligence.

Ranks files by an aggregate suspicion score (severity x confidence) and
provides the QuixBugs benchmark, which treats every file under
``python_programs/`` as a known-buggy ground-truth sample.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional

from .analyzer import FileReport, analyze_repository, analyze_source, collect_python_files, _read


def rank_reports(reports: List[FileReport], top: Optional[int] = None) -> List[FileReport]:
    """Most-suspicious first. Files with no findings are dropped."""
    flagged = [r for r in reports if r.findings]
    flagged.sort(key=lambda r: (-r.score, -len(r.findings), r.rel_path))
    if top is not None:
        return flagged[:max(0, top)]
    return flagged


# ---------------------------------------------------------------------------
# QuixBugs benchmark
# ---------------------------------------------------------------------------
@dataclass
class BenchmarkResult:
    analyzed: int
    flagged: int
    hit_rate: float
    positions: Dict[str, int]  # rel_path -> 1-based rank in the global ranking
    misses: List[str]
    ranked: List[FileReport]


def _quixbugs_program_dir(root: str) -> Optional[str]:
    for name in ("python_programs", "python_programs_buggy"):
        candidate = os.path.join(root, name)
        if os.path.isdir(candidate):
            return candidate
    # root itself may be the programs dir
    return root if os.path.isdir(root) else None


def benchmark(root: str) -> BenchmarkResult:
    """Run the QuixBugs-style benchmark.

    Ground truth: every .py file directly under python_programs/ has a bug.
    A 'hit' is a buggy file we flag with at least one finding.
    """
    root = os.path.abspath(root)
    programs_dir = _quixbugs_program_dir(root)

    ground_truth: List[str] = []
    reports: List[FileReport] = []
    if programs_dir and os.path.isdir(programs_dir):
        for fname in sorted(os.listdir(programs_dir)):
            if not fname.endswith(".py") or fname.startswith("__"):
                continue
            # QuixBugs ground truth is the buggy *algorithms*, not their test
            # harnesses or shared helpers.
            if fname.endswith("_test.py") or fname == "node.py":
                continue
            abs_path = os.path.join(programs_dir, fname)
            if not os.path.isfile(abs_path):
                continue
            text = _read(abs_path)
            if text is None:
                continue
            rel_path = os.path.relpath(abs_path, root).replace("\\", "/")
            ground_truth.append(rel_path)
            reports.append(analyze_source(
                rel_path, text, abs_path=abs_path, test_awareness=False,
            ))

    ranked = rank_reports(reports)
    positions: Dict[str, int] = {}
    for idx, report in enumerate(ranked, 1):
        positions[report.rel_path] = idx

    flagged_paths = {r.rel_path for r in reports if r.findings}
    misses = [p for p in ground_truth if p not in flagged_paths]
    analyzed = len(ground_truth)
    flagged = len(flagged_paths)
    hit_rate = (flagged / analyzed) if analyzed else 0.0

    return BenchmarkResult(
        analyzed=analyzed,
        flagged=flagged,
        hit_rate=hit_rate,
        positions=positions,
        misses=misses,
        ranked=ranked,
    )
