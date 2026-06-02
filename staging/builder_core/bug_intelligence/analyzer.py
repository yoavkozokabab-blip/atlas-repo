"""Analyzer: parse files, run detectors, add test-awareness, build reports.

Operates directly on the filesystem so it works on any repository without
requiring `init` first. Read-only throughout.
"""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from . import patterns
from .findings import (
    Finding,
    confidence_breakdown,
    dedupe,
    overall_confidence,
    sort_findings,
)

# Directories we never descend into (mirror of the indexer's skip set).
SKIP_DIRS = {
    ".git", ".jarvis_builder", "__pycache__", "node_modules", ".venv", "venv",
    "env", "dist", "build", ".pytest_cache", ".mypy_cache", ".idea", ".vscode",
    "site-packages", ".tox", "target", "vendor", ".next", ".cache", "coverage",
    "htmlcov", ".gradle",
}
MAX_BYTES = 400_000


@dataclass
class FileReport:
    rel_path: str
    abs_path: str
    functions: List[str] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)
    referenced_by_tests: bool = True
    parse_error: str = ""
    complexity: int = 0

    @property
    def score(self) -> float:
        return round(sum(f.weight() for f in self.findings), 3)

    @property
    def confidence(self) -> str:
        return overall_confidence(self.findings)

    @property
    def top(self) -> Optional[Finding]:
        return self.findings[0] if self.findings else None


# ---------------------------------------------------------------------------
# File discovery / classification
# ---------------------------------------------------------------------------
def _is_test_path(rel_path: str) -> bool:
    parts = rel_path.replace("\\", "/").lower().split("/")
    name = parts[-1]
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or any(p in ("test", "tests", "__tests__", "spec") for p in parts[:-1])
    )


def collect_python_files(root: str) -> List[Tuple[str, str]]:
    """Return [(abs_path, rel_path), ...] for every .py file under root."""
    root = os.path.abspath(root)
    out: List[Tuple[str, str]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            abs_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(abs_path, root).replace("\\", "/")
            out.append((abs_path, rel_path))
    out.sort(key=lambda pair: pair[1])
    return out


def _read(path: str) -> Optional[str]:
    try:
        if os.path.getsize(path) > MAX_BYTES:
            return None
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except OSError:
        return None


def build_test_blob(root: str) -> str:
    """Concatenated lowercased text of all test files in the repo."""
    parts: List[str] = []
    for abs_path, rel_path in collect_python_files(root):
        if _is_test_path(rel_path):
            text = _read(abs_path)
            if text:
                parts.append(rel_path.lower())
                parts.append(text.lower())
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------
def _complexity(tree: ast.AST) -> int:
    branches = sum(isinstance(n, (ast.If, ast.IfExp, ast.Try, ast.Match)) for n in ast.walk(tree))
    loops = sum(isinstance(n, (ast.For, ast.AsyncFor, ast.While)) for n in ast.walk(tree))
    return 1 + branches + loops


def analyze_source(
    rel_path: str,
    text: str,
    *,
    abs_path: str = "",
    test_blob: str = "",
    test_awareness: bool = True,
) -> FileReport:
    """Analyze a single source file's text and return a FileReport."""
    stem = os.path.splitext(os.path.basename(rel_path))[0]
    lines = text.splitlines()

    try:
        tree = ast.parse(text, filename=rel_path)
    except SyntaxError as exc:
        lineno = int(exc.lineno or 1)
        f = Finding(
            rule="syntax_error",
            title="File does not parse",
            severity="high",
            confidence="high",
            line=lineno,
            message=f"The Python parser rejected this file: {exc.msg}.",
            evidence=(lines[lineno - 1].strip()[:240] if 1 <= lineno <= len(lines) else ""),
        )
        return FileReport(
            rel_path=rel_path, abs_path=abs_path, functions=[], findings=[f],
            referenced_by_tests=True, parse_error=type(exc).__name__, complexity=0,
        )

    findings = patterns.run_all(tree, lines, stem)
    func_nodes = [n for n in ast.walk(tree)
                  if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    func_names = [n.name for n in func_nodes]

    referenced = True
    if test_awareness and test_blob and not _is_test_path(rel_path):
        referenced = (stem.lower() in test_blob)
        if not referenced:
            findings.append(Finding(
                rule="untested_module",
                title=f"Module '{stem}' is not referenced by any test",
                severity="low",
                confidence="medium",
                line=1,
                message=(
                    f"No test file mentions '{stem}'. Logic bugs here would not be caught "
                    f"by the existing suite."
                ),
                evidence="",
            ))
        else:
            # function-level test gaps + complexity-vs-test asymmetry
            for fn in func_nodes:
                if fn.name.startswith("_"):
                    continue
                if fn.name.lower() not in test_blob:
                    findings.append(Finding(
                        rule="untested_function",
                        title=f"Function '{fn.name}' has no test reference",
                        severity="low",
                        confidence="low",
                        line=fn.lineno,
                        function=fn.name,
                        message=(
                            f"The module is tested but '{fn.name}' is never named in any "
                            f"test. Its specific edge cases may be unverified."
                        ),
                        evidence="",
                    ))

    findings = sort_findings(dedupe(findings))
    return FileReport(
        rel_path=rel_path,
        abs_path=abs_path,
        functions=func_names,
        findings=findings,
        referenced_by_tests=referenced,
        parse_error="",
        complexity=_complexity(tree),
    )


def analyze_file(root: str, file_arg: str, *, test_awareness: bool = True) -> Optional[FileReport]:
    """Analyze one file given the project root and a (possibly relative) path."""
    root = os.path.abspath(root)
    candidate = file_arg
    if not os.path.isabs(candidate):
        candidate = os.path.join(root, file_arg)
    candidate = os.path.normpath(candidate)
    if not os.path.isfile(candidate):
        return None
    text = _read(candidate)
    if text is None:
        return None
    rel_path = os.path.relpath(candidate, root).replace("\\", "/")
    test_blob = build_test_blob(root) if test_awareness else ""
    return analyze_source(
        rel_path, text, abs_path=candidate, test_blob=test_blob,
        test_awareness=test_awareness,
    )


def analyze_repository(
    root: str,
    *,
    include_tests: bool = False,
    test_awareness: bool = True,
) -> List[FileReport]:
    """Analyze every Python file under root; return a list of FileReports."""
    root = os.path.abspath(root)
    test_blob = build_test_blob(root) if test_awareness else ""
    reports: List[FileReport] = []
    for abs_path, rel_path in collect_python_files(root):
        if not include_tests and _is_test_path(rel_path):
            continue
        text = _read(abs_path)
        if text is None:
            continue
        reports.append(analyze_source(
            rel_path, text, abs_path=abs_path, test_blob=test_blob,
            test_awareness=test_awareness,
        ))
    return reports
