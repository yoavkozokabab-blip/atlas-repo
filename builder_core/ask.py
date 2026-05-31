"""Question answering: ANSWER / EVIDENCE / SOURCES.

Classifies the question, then either aggregates risk signals or runs keyword
retrieval. Answers are extractive (assembled from real chunks), never
generated, so every claim traces to a source. No LLM required.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from . import repository_understanding, retrieval, risk

_RISK_RE = re.compile(
    r"\b(risk|risks|risky|danger|dangerous|debt|fragile|fragility|unsafe|"
    r"weak|weakness|hotspot|vulnerab\w*|problem area)\b",
    re.IGNORECASE,
)
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
_BUG_RE = re.compile(r"\b(bug|bugs|logic error|logic errors|analy[sz]e|review|wrong|broken)\b", re.IGNORECASE)


def classify(question: str) -> str:
    if _RISK_RE.search(question):
        return "risk"
    if retrieval.is_architecture_question(question):
        return "architecture"
    return "retrieval"


def _answer_risk(index: Dict[str, Any], limit: int = 5) -> Dict[str, Any]:
    signals = risk.compute_risks(index)
    if not signals:
        return {
            "mode": "risk",
            "answer": (
                "No high-confidence risk signals detected from the current index. "
                "The project has tests and no obvious churn/coverage gaps, or it is "
                "too small to assess. Re-run `init` after more history accrues."
            ),
            "findings": [],
            "evidence": [],
            "sources": [],
        }
    top = signals[:limit]
    lines = [
        f"The {len(top)} most significant risk signal(s) in this codebase:",
    ]
    evidence: List[str] = []
    sources: List[str] = []
    findings: List[str] = []
    for i, sig in enumerate(top, 1):
        lines.append(f"{i}. [{sig['severity'].upper()}] {sig['title']}")
        findings.append(f"[{sig['severity']}] {sig['title']}")
        evidence.append(f"[{sig['severity']}] {sig['title']} - {sig['detail']}")
        for src in sig.get("sources", []):
            if src not in sources:
                sources.append(src)
    return {
        "mode": "risk",
        "answer": "\n".join(lines),
        "findings": findings,
        "evidence": evidence,
        "sources": sources,
    }


def _answer_retrieval(index: Dict[str, Any], question: str, limit: int = 6) -> Dict[str, Any]:
    hits = retrieval.search(index, question, limit=limit)
    if not hits:
        return {
            "mode": "retrieval",
            "answer": (
                "I could not find indexed material matching that question. "
                "Try different keywords, or re-run `init` if the project changed."
            ),
            "findings": [],
            "evidence": [],
            "sources": [],
        }

    query_tokens = set(retrieval.tokenize(question))
    evidence: List[str] = []
    sources: List[str] = []
    answer_sentences: List[str] = []

    for chunk, _score in hits:
        path = chunk.get("path", "")
        text = chunk.get("text", "")
        evidence.append(f"{path}: {text}")
        if path not in sources:
            sources.append(path)
        # pull the most query-relevant sentence for the synthesized answer
        for sent in _SENT_SPLIT.split(text):
            tokens = set(retrieval.tokenize(sent))
            if tokens & query_tokens and sent.strip() not in answer_sentences:
                answer_sentences.append(sent.strip())
                break

    if answer_sentences:
        answer = (
            "Based on the indexed project, here is the most relevant material:\n"
            + " ".join(answer_sentences[:3])
        )
    else:
        # no sentence overlap; fall back to the single best chunk
        best_path, best_text = hits[0][0]["path"], hits[0][0]["text"]
        answer = (
            f"The most relevant material is in {best_path}:\n{best_text}"
        )

    return {
        "mode": "retrieval",
        "answer": answer,
        "findings": [],
        "evidence": evidence,
        "sources": sources,
    }


def _subsystem_line(subsystem: Dict[str, Any]) -> str:
    production_count = subsystem.get("role_counts", {}).get("production_code", 0)
    entries = ", ".join(subsystem.get("entry_files", [])[:3]) or "(no production entry file)"
    dependencies = ", ".join(subsystem.get("dependencies", [])) or "(none detected)"
    return (
        f"{subsystem['name']}: {production_count} production file(s); "
        f"entry files: {entries}; dependencies: {dependencies}"
    )


def _architecture_sources(
    hits: List[Any], subsystems: List[Dict[str, Any]], limit: int = 12
) -> List[str]:
    sources: List[str] = []
    for subsystem in subsystems:
        for path in subsystem.get("entry_files", []):
            if path not in sources:
                sources.append(path)
    for chunk, _score in hits:
        role = chunk.get("role") or repository_understanding.classify_file_role(
            chunk.get("path", "")
        )
        if role in {"benchmark", "dataset", "generated", "report_history"}:
            continue
        path = chunk.get("path", "")
        if path and path not in sources:
            sources.append(path)
    return sources[:limit]


def _answer_architecture(index: Dict[str, Any], question: str) -> Dict[str, Any]:
    subsystems = repository_understanding.production_subsystems(index)
    if not subsystems:
        return _answer_retrieval(index, question)

    lowered = question.lower()
    named = next(
        (
            subsystem for subsystem in subsystems
            if subsystem.get("name", "").lower() in lowered
        ),
        None,
    )
    if named is not None:
        selected = [named]
        answer = (
            f"The indexed {named['name']} subsystem is the primary production area "
            f"for this question. {_subsystem_line(named)}."
        )
    elif "production code" in lowered or "which folders" in lowered:
        selected = subsystems[:12]
        folders = ", ".join(
            f"{item['name']} ({item['role_counts'].get('production_code', 0)})"
            for item in selected
        )
        answer = f"Indexed folders containing production code: {folders}."
    else:
        selected = subsystems[:8]
        overview = " ".join(
            f"{position}. {_subsystem_line(item)}."
            for position, item in enumerate(selected, 1)
        )
        answer = f"The most important indexed production subsystems are: {overview}"

    hits = retrieval.search(index, question, limit=6)
    sources = _architecture_sources(hits, selected)
    evidence = [f"subsystem map: {_subsystem_line(item)}" for item in selected]
    for chunk, _score in hits[:3]:
        path = chunk.get("path", "")
        text = chunk.get("text", "")
        if path in sources:
            evidence.append(f"{path}: {text}")
    return {
        "mode": "architecture",
        "answer": answer,
        "findings": [],
        "evidence": evidence,
        "sources": sources,
    }


def _matching_python_analysis(index: Dict[str, Any], question: str) -> Dict[str, Any] | None:
    lowered = question.replace("\\", "/").lower()
    analyses = list(index.get("python_analysis", []))
    exact = [item for item in analyses if item.get("path", "").lower() in lowered]
    if exact:
        return max(exact, key=lambda item: len(item.get("path", "")))
    basenames = [
        item
        for item in analyses
        if item.get("path", "").replace("\\", "/").split("/")[-1].lower() in lowered
    ]
    return basenames[0] if len(basenames) == 1 else None


def _answer_python_analysis(analysis: Dict[str, Any]) -> Dict[str, Any]:
    path = analysis.get("path", "")
    findings = list(analysis.get("findings", []))
    functions = analysis.get("functions", [])
    semantic_findings = [
        item for item in findings if item.get("kind") == "semantic"
    ]
    if semantic_findings:
        answer = (
            f"Semantic analysis found an algorithm-invariant violation in {path}. "
            f"{semantic_findings[0]['message']}"
        )
    elif findings:
        answer = (
            f"Static analysis found {len(findings)} review lead(s) in {path}. "
            "These are deterministic AST signals, not automatic proof of a bug."
        )
    else:
        answer = (
            f"Static analysis found no obvious AST review leads in {path}. "
            "Manual review and tests are still required."
        )
    finding_lines = [
        f"[{item['severity']}] {item['rule']} line {item['line']}: {item['message']}"
        for item in findings
    ]
    evidence = [
        f"{path}:{item['line']}: {item.get('evidence') or item['message']}"
        for item in findings
    ]
    for expectation in analysis.get("test_expectations", []):
        evidence.append(
            f"{expectation['source']}: expected {expectation['type']} - {expectation['detail']}"
        )
    if functions:
        names = ", ".join(item["name"] for item in functions[:20])
        evidence.append(f"{path}: parsed functions: {names}")
    sources = [path] if path else []
    for expectation in analysis.get("test_expectations", []):
        if expectation["source"] not in sources:
            sources.append(expectation["source"])
    return {
        "mode": "python_analysis",
        "answer": answer,
        "findings": finding_lines,
        "evidence": evidence,
        "sources": sources,
    }


def answer(index: Dict[str, Any], question: str) -> Dict[str, Any]:
    """Return {mode, answer, evidence, sources} for a question against an index."""
    target = _matching_python_analysis(index, question)
    if target is not None and _BUG_RE.search(question):
        result = _answer_python_analysis(target)
    else:
        mode = classify(question)
        if mode == "risk":
            result = _answer_risk(index)
        elif mode == "architecture":
            result = _answer_architecture(index, question)
        else:
            result = _answer_retrieval(index, question)
    result["ask_quality"] = retrieval.source_distribution_for_sources(
        index, result["sources"]
    )
    return result
