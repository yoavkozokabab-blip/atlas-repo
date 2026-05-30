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
# All fact-backed / grounded finding kinds.
GROUNDED_KINDS = {"semantic", "data_flow", "value_flow", "security"}
# The algorithm-bug benchmarks (QuixBugs, holdout) measure logic/algorithm
# defect detection. Security taint findings are grounded but out of band for
# these corpora — they have their own benchmark (smoke_phase89). A medium-
# confidence taint review lead that fires identically on buggy and fixed (e.g.
# path_traversal on a file-open) is non-discriminative here, so the verdict
# excludes the security kind. This is detector routing, not a corpus-specific rule.
BENCHMARK_VERDICT_KINDS = {"semantic", "data_flow", "value_flow"}
SETUP_INSTRUCTION = legacy.SETUP_INSTRUCTION


def grounded_findings(result, *, grounded: bool = True, kinds=None) -> List[Any]:
    """Bug-class findings used for the verdict.

    grounded=True  -> only the verdict kinds (semantic + fact-backed flow), precise.
    grounded=False -> any bug-class finding (the naive decision, for comparison).
    ``kinds`` overrides the verdict kind set (defaults to BENCHMARK_VERDICT_KINDS).
    """
    allow = kinds if kinds is not None else BENCHMARK_VERDICT_KINDS
    out = []
    for f in result.findings:
        if f.category not in BUG_CATEGORIES:
            continue
        if grounded and f.kind not in allow:
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


# ---------------------------------------------------------------------------
# External holdout, measured through the unified engine (Phase 92A)
# ---------------------------------------------------------------------------
# Holdout pairs live under builder_core/benchmarks/holdout/pairs/<case_id>/
# with buggy.py and fixed.py. Discovery is replicated here (read-only) so the
# engine path has no dependency on the legacy external_benchmark module.
_HOLDOUT_ROOT = Path(__file__).resolve().parents[1] / "benchmarks" / "holdout"
_PAIRS_ROOT = _HOLDOUT_ROOT / "pairs"
_MANIFEST_PATH = _HOLDOUT_ROOT / "manifest.json"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def _load_manifest() -> Dict[str, Dict[str, Any]]:
    if not _MANIFEST_PATH.is_file():
        return {}
    import json
    try:
        items = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {item["case_id"]: item for item in items if "case_id" in item}


def evaluate_holdout_engine(*, pairs_root: Path | None = None) -> Dict[str, Any]:
    """Evaluate the out-of-domain holdout pairs through the unified engine.

    Verdict uses the same grounded-kind decision as the QuixBugs engine path:
    a case is flagged iff buggy.py / fixed.py yields >=1 grounded finding
    (semantic + fact-backed flow/taint). Read-only; no code is executed.
    """
    root = pairs_root or _PAIRS_ROOT
    if not root.is_dir():
        return {"available": False, "engine": "unified", "pairs_root": str(root),
                "setup_instruction": "Holdout pairs missing; see reports/phase84_external_benchmark_plan.md"}

    manifest = _load_manifest()
    case_dirs = sorted(p for p in root.iterdir() if p.is_dir())
    if not case_dirs:
        return {"available": False, "engine": "unified", "pairs_root": str(root),
                "setup_instruction": "No holdout pair directories found."}

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
        b_res = engine.analyze_source(_read_text(buggy_path), rel_buggy)
        c_res = engine.analyze_source(_read_text(fixed_path), rel_fixed)
        buggy_results.append({
            "case_id": case_id, "source": meta.get("source", "unknown"),
            "path": rel_buggy,
            "findings": _findings_payload(grounded_findings(b_res)),
        })
        correct_results.append({
            "case_id": case_id, "source": meta.get("source", "unknown"),
            "path": rel_fixed,
            "findings": _findings_payload(grounded_findings(c_res)),
        })

    tp = sum(1 for r in buggy_results if r["findings"])
    fp = sum(1 for r in correct_results if r["findings"])
    fn = len(buggy_results) - tp
    tn = len(correct_results) - fp
    return {
        "available": True,
        "engine": "unified",
        "pairs_root": str(root),
        "cases_analyzed": len(buggy_results),
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "true_negatives": tn,
        "precision": legacy._rate(tp, tp + fp),
        "recall": legacy._rate(tp, tp + fn),
        "accuracy": legacy._rate(tp + tn, len(buggy_results) + len(correct_results)),
        "buggy_results": buggy_results,
        "correct_results": correct_results,
        "manifest_cases": len(manifest),
    }


def format_holdout_report(report: Dict[str, Any]) -> str:
    if not report.get("available"):
        return "\n".join((
            "EXTERNAL HOLDOUT BENCHMARK [engine=unified]",
            "SKIP: holdout corpus not available.",
            f"Setup: {report.get('setup_instruction', '')}",
        ))
    lines = [
        "EXTERNAL HOLDOUT BENCHMARK [engine=unified]",
        "verdict signal: grounded findings (semantic + fact-backed flow/taint)",
        f"cases analyzed: {report['cases_analyzed']}",
        f"true positives: {report['true_positives']}",
        f"false positives: {report['false_positives']}",
        f"false negatives: {report['false_negatives']}",
        f"true negatives: {report['true_negatives']}",
        f"precision: {report['precision']:.4f}",
        f"recall: {report['recall']:.4f}",
        f"accuracy: {report['accuracy']:.4f}",
        "",
        "CASES WITH GROUNDED FINDINGS ON BUGGY",
    ]
    flagged = [r for r in report.get("buggy_results", []) if r["findings"]]
    if not flagged:
        lines.append("- (none)")
    else:
        for r in flagged:
            rules = ", ".join(f"{f['kind']}/{f['rule']}" for f in r["findings"])
            lines.append(f"- {r['case_id']} [{r.get('source', '?')}]: {rules}")
    lines.append("")
    lines.append("FALSE POSITIVES ON FIXED")
    fps = [r for r in report.get("correct_results", []) if r["findings"]]
    if not fps:
        lines.append("- (none)")
    else:
        for r in fps:
            rules = ", ".join(f"{f['kind']}/{f['rule']}" for f in r["findings"])
            lines.append(f"- {r['case_id']}: {rules}")
    return "\n".join(lines)
