"""Evaluate Builder Core semantic rules on external holdout pairs.

Holdout pairs live under builder_core/benchmarks/holdout/pairs/<case_id>/
with buggy.py and fixed.py. This mirrors the QuixBugs paired evaluation
methodology without requiring BugsInPy checkout or test execution.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from builder_core.python_analysis import analyze_python

HOLDOUT_ROOT = Path(__file__).resolve().parent / "benchmarks" / "holdout"
PAIRS_ROOT = HOLDOUT_ROOT / "pairs"
MANIFEST_PATH = HOLDOUT_ROOT / "manifest.json"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def _semantic_findings(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        finding
        for finding in analysis.get("findings", [])
        if finding.get("kind") == "semantic"
    ]


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _load_manifest() -> List[Dict[str, Any]]:
    if not MANIFEST_PATH.is_file():
        return []
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def evaluate_holdout(*, pairs_root: Path | None = None) -> Dict[str, Any]:
    root = pairs_root or PAIRS_ROOT
    if not root.is_dir():
        return {
            "available": False,
            "pairs_root": str(root),
            "setup_instruction": "Holdout pairs missing; see reports/phase84_external_benchmark_plan.md",
        }

    manifest = {item["case_id"]: item for item in _load_manifest()}
    case_dirs = sorted(p for p in root.iterdir() if p.is_dir())
    if not case_dirs:
        return {
            "available": False,
            "pairs_root": str(root),
            "setup_instruction": "No holdout pair directories found.",
        }

    buggy_results: List[Dict[str, Any]] = []
    correct_results: List[Dict[str, Any]] = []
    for case_dir in case_dirs:
        buggy_path = case_dir / "buggy.py"
        fixed_path = case_dir / "fixed.py"
        if not buggy_path.is_file() or not fixed_path.is_file():
            continue
        case_id = case_dir.name
        meta = manifest.get(case_id, {})
        rel_buggy = f"holdout/{case_id}/buggy.py"
        rel_fixed = f"holdout/{case_id}/fixed.py"
        buggy_analysis = analyze_python(rel_buggy, _read_text(buggy_path))
        fixed_analysis = analyze_python(rel_fixed, _read_text(fixed_path))
        buggy_results.append(
            {
                "case_id": case_id,
                "source": meta.get("source", "unknown"),
                "project": meta.get("project", ""),
                "bug_id": meta.get("bug_id", ""),
                "path": rel_buggy,
                "findings": _semantic_findings(buggy_analysis),
                "profiles": buggy_analysis.get("algorithm_profiles", []),
            }
        )
        correct_results.append(
            {
                "case_id": case_id,
                "source": meta.get("source", "unknown"),
                "path": rel_fixed,
                "findings": _semantic_findings(fixed_analysis),
                "profiles": fixed_analysis.get("algorithm_profiles", []),
            }
        )

    true_positives = sum(1 for item in buggy_results if item["findings"])
    false_positives = sum(1 for item in correct_results if item["findings"])
    false_negatives = len(buggy_results) - true_positives
    true_negatives = len(correct_results) - false_positives

    return {
        "available": True,
        "pairs_root": str(root),
        "cases_analyzed": len(buggy_results),
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "true_negatives": true_negatives,
        "precision": _rate(true_positives, true_positives + false_positives),
        "recall": _rate(true_positives, true_positives + false_negatives),
        "accuracy": _rate(
            true_positives + true_negatives,
            len(buggy_results) + len(correct_results),
        ),
        "buggy_results": buggy_results,
        "correct_results": correct_results,
        "manifest_cases": len(manifest),
    }


def format_holdout_report(report: Dict[str, Any]) -> str:
    if not report.get("available"):
        return "\n".join(
            (
                "EXTERNAL HOLDOUT BENCHMARK",
                "SKIP: holdout corpus not available.",
                f"Setup: {report.get('setup_instruction', '')}",
            )
        )
    lines = [
        "EXTERNAL HOLDOUT BENCHMARK",
        f"cases analyzed: {report['cases_analyzed']}",
        f"true positives: {report['true_positives']}",
        f"false positives: {report['false_positives']}",
        f"false negatives: {report['false_negatives']}",
        f"true negatives: {report['true_negatives']}",
        f"precision: {report['precision']:.4f}",
        f"recall: {report['recall']:.4f}",
        f"accuracy: {report['accuracy']:.4f}",
        "",
        "CASES WITH SEMANTIC FINDINGS ON BUGGY",
    ]
    flagged = [item for item in report.get("buggy_results", []) if item["findings"]]
    if not flagged:
        lines.append("- (none)")
    else:
        for item in flagged:
            rules = ", ".join(f["rule"] for f in item["findings"])
            lines.append(f"- {item['case_id']} [{item.get('source', '?')}]: {rules}")
    lines.append("")
    lines.append("FALSE POSITIVES ON FIXED")
    fps = [item for item in report.get("correct_results", []) if item["findings"]]
    if not fps:
        lines.append("- (none)")
    else:
        for item in fps:
            rules = ", ".join(f["rule"] for f in item["findings"])
            lines.append(f"- {item['case_id']}: {rules}")
    return "\n".join(lines)
