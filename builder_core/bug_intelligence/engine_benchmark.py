"""QuixBugs benchmark measured through the unified engine (Phase 91).

This replaces the legacy semantic-path measurement with the unified engine while
preserving the exact pairing/exclusion logic of ``builder_core.benchmark`` so the
two paths are directly comparable.

The buggy/correct VERDICT counts only *grounded* findings — algorithm-invariant
violations (kind ``semantic``) and fact-backed flow/taint defects (kinds
``data_flow`` / ``value_flow`` / ``security``). The broad ``pattern``-kind code
smells (e.g. inconsistent-return) still run and appear in the product output, but
they are diagnostic aids, not binary defect verdicts, so they are excluded from
the benchmark decision. This is detector *routing*, not a QuixBugs-specific rule.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

from .. import benchmark as legacy
from . import engine
from .finding import ALGORITHM_BUG, LOGIC_BUG, SECURITY_RISK

BUG_CATEGORIES = {LOGIC_BUG, ALGORITHM_BUG, SECURITY_RISK}
GROUNDED_KINDS = {"semantic", "data_flow", "value_flow", "security"}
SETUP_INSTRUCTION = legacy.SETUP_INSTRUCTION


def grounded_findings(result, *, grounded: bool = True) -> List[Any]:
    """Bug-class findings used for the verdict.

    grounded=True  -> only semantic + fact-backed flow/taint (default, precise).
    grounded=False -> any bug-class finding (the naive decision, for comparison).
    """
    out = []
    for f in result.findings:
        if f.category not in BUG_CATEGORIES:
            continue
        if grounded and f.kind not in GROUNDED_KINDS:
            continue
        out.append(f)
    return out


def _findings_payload(findings) -> List[Dict[str, Any]]:
    return [
        {"rule": f.rule, "kind": f.kind, "category": f.category,
         "severity": f.severity, "confidence": f.confidence, "line": f.line,
         "message": f.title}
        for f in findings
    ]


def evaluate_quixbugs_engine(project: str, *, grounded: bool = True) -> Dict[str, Any]:
    root = Path(project).expanduser().resolve()
    buggy_root = root / "python_programs"
    correct_root = root / "correct_python_programs"
    if not buggy_root.is_dir() or not correct_root.is_dir():
        return {"available": False, "engine": "unified", "project": str(root),
                "setup_instruction": SETUP_INSTRUCTION}

    tests = legacy._test_documents(root)
    buggy_paths = {p.name: p for p in buggy_root.glob("*.py") if p.is_file()}
    correct_paths = {p.name: p for p in correct_root.glob("*.py") if p.is_file()}
    all_pairs = sorted(set(buggy_paths) & set(correct_paths))
    paired = [n for n in all_pairs if legacy._is_algorithm_pair(n)]
    excluded = [n for n in all_pairs if n not in paired]

    buggy_results: List[Dict[str, Any]] = []
    correct_results: List[Dict[str, Any]] = []
    for name in paired:
        b_rel = buggy_paths[name].relative_to(root).as_posix()
        c_rel = correct_paths[name].relative_to(root).as_posix()
        b_res = engine.analyze_source(legacy._read_text(buggy_paths[name]), b_rel,
                                      test_documents=tests)
        c_res = engine.analyze_source(legacy._read_text(correct_paths[name]), c_rel,
                                      test_documents=tests)
        buggy_results.append({"name": name, "path": b_rel,
                              "findings": _findings_payload(grounded_findings(b_res, grounded=grounded))})
        correct_results.append({"name": name, "path": c_rel,
                                "findings": _findings_payload(grounded_findings(c_res, grounded=grounded))})

    tp_files = [r for r in buggy_results if r["findings"]]
    fp_files = [r for r in correct_results if r["findings"]]
    tp, fp = len(tp_files), len(fp_files)
    fn = len(buggy_results) - tp
    bfs = next((r for r in buggy_results if os.path.basename(r["path"]) == "breadth_first_search.py"), None)

    return {
        "available": True,
        "engine": "unified",
        "grounded": grounded,
        "project": str(root),
        "excluded_pairs": excluded,
        "buggy_files_analyzed": len(buggy_results),
        "correct_files_analyzed": len(correct_results),
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": legacy._rate(tp, tp + fp),
        "recall": legacy._rate(tp, len(buggy_results)),
        "true_positive_rate": legacy._rate(tp, len(buggy_results)),
        "false_positive_rate": legacy._rate(fp, len(correct_results)),
        "breadth_first_search": bfs,
        "true_positive_files": tp_files,
        "false_positive_files": fp_files,
    }


def format_report(report: Dict[str, Any]) -> str:
    if not report.get("available"):
        return "\n".join((
            "QUIXBUGS BENCHMARK [engine=unified]",
            "SKIP: QuixBugs is not available locally.",
            f"Setup: {report.get('setup_instruction', SETUP_INSTRUCTION)}",
        ))
    lines = [
        "QUIXBUGS BENCHMARK [engine=unified]",
        f"verdict signal: grounded findings (semantic + fact-backed flow/taint)"
        if report.get("grounded", True) else "verdict signal: any bug-class finding (naive)",
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
        lines.append("- no grounded finding")
    else:
        for f in bfs["findings"]:
            lines.append(f"- [{f['severity']}] {f['kind']}/{f['rule']} line {f['line']}: {f['message']}")
    return "\n".join(lines)
