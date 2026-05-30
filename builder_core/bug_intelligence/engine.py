"""Unified Builder Intelligence Engine (Phase 90).

One entry point that orchestrates the deterministic pipeline:

    Repository / file
      -> ParseAgent            (text -> AST)
      -> FactExtractionAgent    (data-flow + value-flow + test facts)
      -> LogicBugAgent          (logic / structure / maintainability / test-gap)
      -> SecurityAgent          (taint-based security + null-deref)
      -> AlgorithmAgent         (semantic algorithm-correctness, wrapped)
      -> FindingRankerAgent     (dedupe + rank)
      -> EvidenceFormatterAgent (unified CLI sections)

It is the primary analysis path for the CLI. The QuixBugs / holdout *benchmark*
harness deliberately remains on the legacy semantic path for measurement
stability (see reports/phase90_*). Read-only; local; deterministic; no network;
never executes analyzed code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from . import agents as A
from .finding import Finding, SECURITY_RISK

MAX_BYTES = 400_000
SKIP_DIRS = {
    ".git", ".jarvis_builder", "__pycache__", "node_modules", ".venv", "venv",
    "env", "dist", "build", ".pytest_cache", ".mypy_cache", ".idea", ".vscode",
    "site-packages", ".tox", "target", "vendor", ".next", ".cache", "coverage",
    "htmlcov", ".gradle",
}


@dataclass
class AnalysisResult:
    file: str
    functions: List[str] = field(default_factory=list)
    facts: Dict[str, Any] = field(default_factory=dict)
    findings: List[Finding] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def score(self) -> float:
        return round(sum(f.weight for f in self.findings), 3)

    @property
    def security_findings(self) -> List[Finding]:
        return [f for f in self.findings if f.category == SECURITY_RISK]


# Shared agent instances (stateless).
_parse = A.ParseAgent()
_facts = A.FactExtractionAgent()
_logic = A.LogicBugAgent()
_factlogic = A.FactLogicAgent()
_security = A.SecurityAgent()
_algorithm = A.AlgorithmAgent()
_ranker = A.FindingRankerAgent()
_formatter = A.EvidenceFormatterAgent()


def analyze_source(
    text: str,
    rel_path: str = "<source>",
    *,
    test_documents: Optional[List[Dict[str, str]]] = None,
    include_algorithm: bool = True,
) -> AnalysisResult:
    tree, errors = _parse.parse(text, rel_path)
    if tree is None:
        return AnalysisResult(file=rel_path, errors=errors,
                              metadata={"taint_sources": []})

    lines = text.splitlines()
    module_facts = _facts.extract(text, rel_path, test_documents=test_documents)
    function_names = [fn.get("name") for fn in module_facts.get("functions", [])]

    findings: List[Finding] = []
    findings.extend(_logic.run(tree, lines, rel_path))
    findings.extend(_factlogic.run(module_facts, rel_path))
    findings.extend(_security.run(text, rel_path))
    if include_algorithm:
        findings.extend(_algorithm.run(tree, text, rel_path, test_documents=test_documents))

    findings = _ranker.rank(findings)

    taint_sources = []
    for fn in module_facts.get("functions", []):
        for s in fn.get("taint_sources", []):
            label = f"line {s.get('line')}: {s.get('kind')} ({s.get('name')})"
            if label not in taint_sources:
                taint_sources.append(label)

    return AnalysisResult(
        file=rel_path,
        functions=[n for n in function_names if n],
        facts=module_facts,
        findings=findings,
        errors=errors,
        metadata={
            "taint_sources": taint_sources,
            "counts": _category_counts(findings),
            "score": round(sum(f.weight for f in findings), 3),
        },
    )


def _category_counts(findings: List[Finding]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for f in findings:
        out[f.category] = out.get(f.category, 0) + 1
    return out


def _read(path: str) -> Optional[str]:
    try:
        if os.path.getsize(path) > MAX_BYTES:
            return None
        with open(path, "r", encoding="utf-8-sig", errors="ignore") as fh:
            return fh.read()
    except OSError:
        return None


def analyze_file(path: str, project_root: Optional[str] = None,
                 index: Optional[Dict[str, Any]] = None,
                 *, include_algorithm: bool = True) -> Optional[AnalysisResult]:
    """Analyze one file. ``index`` may carry {'test_documents': [...]} ."""
    candidate = path
    if project_root and not os.path.isabs(candidate):
        candidate = os.path.join(project_root, path)
    candidate = os.path.normpath(candidate)
    if not os.path.isfile(candidate):
        return None
    text = _read(candidate)
    if text is None:
        return None
    rel = os.path.relpath(candidate, project_root).replace("\\", "/") if project_root else os.path.basename(candidate)
    test_docs = (index or {}).get("test_documents") if index else None
    return analyze_source(text, rel, test_documents=test_docs, include_algorithm=include_algorithm)


def _collect_python_files(root: str) -> List[tuple]:
    root = os.path.abspath(root)
    out: List[tuple] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            if fname.endswith(".py"):
                abs_path = os.path.join(dirpath, fname)
                rel = os.path.relpath(abs_path, root).replace("\\", "/")
                out.append((abs_path, rel))
    out.sort(key=lambda p: p[1])
    return out


def analyze_repository(root: str, *, include_algorithm: bool = True) -> List[AnalysisResult]:
    results: List[AnalysisResult] = []
    for abs_path, rel in _collect_python_files(root):
        text = _read(abs_path)
        if text is None:
            continue
        results.append(analyze_source(text, rel, include_algorithm=include_algorithm))
    return results


def rank_files(results: List[AnalysisResult], top: Optional[int] = None) -> List[AnalysisResult]:
    flagged = [r for r in results if r.findings]
    flagged.sort(key=lambda r: (-r.score, -len(r.findings), r.file))
    return flagged[:top] if top is not None else flagged


def security_findings(root: str, top: int = 20) -> List[Finding]:
    out: List[Finding] = []
    for r in analyze_repository(root, include_algorithm=False):
        out.extend(r.security_findings)
    out.sort(key=lambda f: (-f.weight, f.file, f.line))
    return out[: max(0, top)]


def format_result(result: AnalysisResult) -> str:
    return _formatter.format_file(result)
