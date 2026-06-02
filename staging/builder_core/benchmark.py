"""Local-only QuixBugs benchmark evaluation for semantic reasoning."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

from .python_analysis import analyze_python

SETUP_INSTRUCTION = r"git clone https://github.com/jkoppel/QuixBugs.git C:\Repos\QuixBugs"
NON_ALGORITHM_FILES = {"node.py"}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def _test_documents(project_root: Path) -> List[Dict[str, str]]:
    test_root = project_root / "python_testcases"
    if not test_root.is_dir():
        return []
    return [
        {
            "path": path.relative_to(project_root).as_posix(),
            "text": _read_text(path),
        }
        for path in sorted(test_root.rglob("*.py"))
        if path.is_file()
    ]


def _semantic_findings(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        finding
        for finding in analysis.get("findings", [])
        if finding.get("kind") == "semantic"
    ]


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _is_algorithm_pair(name: str) -> bool:
    return not name.endswith("_test.py") and name not in NON_ALGORITHM_FILES


def evaluate_quixbugs(project: str) -> Dict[str, Any]:
    """Evaluate semantic findings against local buggy/correct QuixBugs pairs."""
    root = Path(project).expanduser().resolve()
    buggy_root = root / "python_programs"
    correct_root = root / "correct_python_programs"
    if not buggy_root.is_dir() or not correct_root.is_dir():
        return {
            "available": False,
            "project": str(root),
            "setup_instruction": SETUP_INSTRUCTION,
        }

    tests = _test_documents(root)
    buggy_paths = {
        path.name: path for path in buggy_root.glob("*.py") if path.is_file()
    }
    correct_paths = {
        path.name: path for path in correct_root.glob("*.py") if path.is_file()
    }
    all_paired_names = sorted(set(buggy_paths) & set(correct_paths))
    paired_names = [name for name in all_paired_names if _is_algorithm_pair(name)]
    excluded_pairs = [name for name in all_paired_names if name not in paired_names]

    buggy_results: List[Dict[str, Any]] = []
    correct_results: List[Dict[str, Any]] = []
    for name in paired_names:
        buggy_path = buggy_paths[name]
        correct_path = correct_paths[name]
        buggy_rel = buggy_path.relative_to(root).as_posix()
        correct_rel = correct_path.relative_to(root).as_posix()
        buggy_analysis = analyze_python(buggy_rel, _read_text(buggy_path), test_documents=tests)
        correct_analysis = analyze_python(correct_rel, _read_text(correct_path), test_documents=tests)
        buggy_results.append(
            {
                "path": buggy_rel,
                "findings": _semantic_findings(buggy_analysis),
                "profiles": buggy_analysis.get("algorithm_profiles", []),
            }
        )
        correct_results.append(
            {
                "path": correct_rel,
                "findings": _semantic_findings(correct_analysis),
                "profiles": correct_analysis.get("algorithm_profiles", []),
            }
        )

    true_positive_files = [item for item in buggy_results if item["findings"]]
    false_positive_files = [item for item in correct_results if item["findings"]]
    true_positives = len(true_positive_files)
    false_positives = len(false_positive_files)
    false_negatives = len(buggy_results) - true_positives
    breadth_first_search = next(
        (
            item
            for item in buggy_results
            if os.path.basename(item["path"]) == "breadth_first_search.py"
        ),
        None,
    )
    return {
        "available": True,
        "project": str(root),
        "excluded_pairs": excluded_pairs,
        "buggy_files_analyzed": len(buggy_results),
        "correct_files_analyzed": len(correct_results),
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "precision": _rate(true_positives, true_positives + false_positives),
        "recall": _rate(true_positives, true_positives + false_negatives),
        "true_positive_rate": _rate(true_positives, len(buggy_results)),
        "false_positive_rate": _rate(false_positives, len(correct_results)),
        "breadth_first_search": breadth_first_search,
        "true_positive_files": true_positive_files,
        "false_positive_files": false_positive_files,
    }


def format_report(report: Dict[str, Any]) -> str:
    if not report.get("available"):
        return "\n".join(
            (
                "QUIXBUGS BENCHMARK",
                "SKIP: QuixBugs is not available locally.",
                f"Setup: {report.get('setup_instruction', SETUP_INSTRUCTION)}",
            )
        )
    lines = [
        "QUIXBUGS BENCHMARK",
        f"buggy files analyzed: {report['buggy_files_analyzed']}",
        f"correct files analyzed: {report['correct_files_analyzed']}",
        f"excluded support pairs: {len(report.get('excluded_pairs', []))}",
        f"true positives: {report['true_positives']}",
        f"false positives: {report['false_positives']}",
        f"precision: {report['precision']:.4f}",
        f"recall: {report['recall']:.4f}",
        f"true positive rate: {report['true_positive_rate']:.4f}",
        f"false positive rate: {report['false_positive_rate']:.4f}",
        "",
        "BREADTH_FIRST_SEARCH",
    ]
    bfs = report.get("breadth_first_search")
    if not bfs:
        lines.append("- not present")
    elif not bfs.get("findings"):
        lines.append("- no semantic finding")
    else:
        for finding in bfs["findings"]:
            lines.append(
                f"- [{finding['severity']}] {finding['rule']} line {finding['line']}: "
                f"{finding['message']}"
            )
    return "\n".join(lines)
