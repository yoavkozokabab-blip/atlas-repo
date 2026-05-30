"""Risk signal generation.

Deterministic, high-precision heuristics derived from the index. The goal is
to surface a small number of *defensible* risks ("this file has zero test
coverage and is a churn hotspot") rather than many speculative ones.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List

SEVERITY_WEIGHT = {"critical": 4, "high": 3, "medium": 2, "low": 1}

_WORD_RE = re.compile(r"[a-z0-9_]+")


def _module_stem(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0].lower()


def _test_corpus(index: Dict[str, Any]) -> str:
    """Concatenated lowercased text of all test chunks + test paths."""
    parts: List[str] = []
    for f in index.get("files", []):
        if f.get("category") == "test":
            parts.append(f.get("path", "").lower())
    for ch in index.get("chunks", []):
        if ch.get("category") == "test":
            parts.append(ch.get("text", "").lower())
    return "\n".join(parts)


def rank_suspicious_files(index: Dict[str, Any], top: int = 10) -> List[Dict[str, Any]]:
    """Rank Python files by AST findings for the read-only risk report."""
    ranked: List[Dict[str, Any]] = []
    for analysis in index.get("python_analysis", []):
        findings = list(analysis.get("findings", []))
        if not findings:
            continue
        score = sum(SEVERITY_WEIGHT.get(item.get("severity", "low"), 1) for item in findings)
        highest = max(
            findings,
            key=lambda item: SEVERITY_WEIGHT.get(item.get("severity", "low"), 1),
        )
        ranked.append(
            {
                "path": analysis.get("path", ""),
                "score": score,
                "severity": highest.get("severity", "low"),
                "findings": findings,
                "functions": analysis.get("functions", []),
                "complexity": analysis.get("complexity", {}),
            }
        )
    ranked.sort(key=lambda item: (-item["score"], item["path"]))
    return ranked[: max(0, top)]


def compute_risks(index: Dict[str, Any]) -> List[Dict[str, Any]]:
    files = index.get("files", [])
    stats = index.get("stats", {})
    churn = index.get("churn", {})
    signals: List[Dict[str, Any]] = []

    # --- Project-level signals -------------------------------------------
    if stats.get("readme", 0) == 0:
        signals.append(
            {
                "type": "no_readme",
                "severity": "medium",
                "title": "No README found",
                "detail": "The project has no README; onboarding context is missing.",
                "sources": [],
                "magnitude": 1,
            }
        )
    if stats.get("test", 0) == 0 and stats.get("src", 0) > 0:
        signals.append(
            {
                "type": "no_tests",
                "severity": "critical",
                "title": "No test files detected",
                "detail": (
                    f"{stats.get('src', 0)} source files and 0 tests. "
                    "Changes are unverified."
                ),
                "sources": [],
                "magnitude": stats.get("src", 0),
            }
        )

    test_blob = _test_corpus(index)
    src_files = [f for f in files if f.get("category") == "src"]

    for f in src_files:
        path = f["path"]
        stem = _module_stem(path)
        commits = churn.get(path, 0)
        lines = f.get("lines", 0)
        todos = f.get("todos", 0)
        has_test = bool(stem) and stem in test_blob

        # --- coverage gap on a churn hotspot -----------------------------
        if not has_test and commits >= 3:
            signals.append(
                {
                    "type": "untested_hotspot",
                    "severity": "high",
                    "title": f"Churned but untested: {path}",
                    "detail": (
                        f"Changed in {commits} recent commits with no detectable "
                        f"test referencing '{stem}'."
                    ),
                    "sources": [path],
                    "magnitude": commits,
                }
            )
        elif not has_test and lines >= 150:
            signals.append(
                {
                    "type": "coverage_gap",
                    "severity": "medium",
                    "title": f"Untested module: {path}",
                    "detail": (
                        f"{lines} lines with no detectable test referencing '{stem}'."
                    ),
                    "sources": [path],
                    "magnitude": lines,
                }
            )

        # --- complexity / large file ------------------------------------
        if lines >= 1200:
            sev = "high"
        elif lines >= 600:
            sev = "medium"
        else:
            sev = None
        if sev:
            signals.append(
                {
                    "type": "large_file",
                    "severity": sev,
                    "title": f"Large file: {path}",
                    "detail": f"{lines} lines - high cognitive load, refactor risk.",
                    "sources": [path],
                    "magnitude": lines,
                }
            )

        # --- TODO/FIXME density -----------------------------------------
        if todos >= 5:
            signals.append(
                {
                    "type": "todo_density",
                    "severity": "medium" if todos >= 10 else "low",
                    "title": f"Unfinished work markers: {path}",
                    "detail": f"{todos} TODO/FIXME/HACK markers.",
                    "sources": [path],
                    "magnitude": todos,
                }
            )

    for item in rank_suspicious_files(index, top=len(index.get("python_analysis", []))):
        findings = item["findings"]
        top_finding = findings[0]
        signals.append(
            {
                "type": "python_static_analysis",
                "severity": item["severity"],
                "title": f"Python review lead: {item['path']}",
                "detail": (
                    f"{len(findings)} static finding(s); highest signal: "
                    f"{top_finding['rule']} at line {top_finding['line']}."
                ),
                "sources": [item["path"]],
                "magnitude": item["score"],
            }
        )

    signals.sort(key=_rank_key, reverse=True)
    return signals


def _rank_key(sig: Dict[str, Any]):
    return (SEVERITY_WEIGHT.get(sig.get("severity", "low"), 0), sig.get("magnitude", 0))
