"""Question answering: ANSWER / EVIDENCE / SOURCES.

Classifies the question, then either aggregates risk signals or runs keyword
retrieval. Answers are extractive (assembled from real chunks), never
generated, so every claim traces to a source. No LLM required.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from . import question_understanding, repository_understanding, retrieval, risk

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
_BUG_RE = re.compile(r"\b(bug|bugs|logic error|logic errors|analy[sz]e|review|wrong|broken)\b", re.IGNORECASE)


def classify(question: str) -> str:
    return question_understanding.coarse_classify(question)


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


def _subsystem_name(path: str) -> str:
    parts = path.replace("\\", "/").split("/")
    return parts[0] if len(parts) > 1 else "(root)"


def _build_depgraph(index: Dict[str, Any]) -> Dict[str, Any] | None:
    root = index.get("project_root")
    if not root:
        return None
    from .bug_intelligence import depgraph

    return depgraph.build_graph(root)


def _graph_unavailable(index: Dict[str, Any], reason: str) -> Dict[str, Any]:
    return {
        "answer": reason,
        "findings": [],
        "evidence": [reason],
        "sources": [],
        "interpretation": {"support_confidence": "unknown"},
    }


def _answer_production_layout(index: Dict[str, Any]) -> Dict[str, Any]:
    subsystems = repository_understanding.production_subsystems(index)
    if not subsystems:
        payload = _graph_unavailable(index, "No production subsystems indexed.")
        payload["mode"] = "production_layout"
        return payload

    ranked: List[Dict[str, Any]] = []
    for subsystem in subsystems:
        production = subsystem.get("role_counts", {}).get("production_code", 0)
        total = subsystem.get("file_count", 0)
        density = round(production / total, 4) if total else 0.0
        ranked.append({
            "name": subsystem["name"],
            "production_count": production,
            "file_count": total,
            "density": density,
        })
    ranked.sort(key=lambda item: (-item["density"], -item["production_count"], item["name"]))

    lines = [
        "Directories ranked by production-code concentration (density, then count):",
    ]
    evidence: List[str] = []
    for position, item in enumerate(ranked[:12], 1):
        lines.append(
            f"{position}. {item['name']}: density={item['density']:.2f} "
            f"({item['production_count']}/{item['file_count']} production files)"
        )
        evidence.append(
            f"subsystem map: {item['name']} production={item['production_count']} "
            f"files={item['file_count']} density={item['density']}"
        )

    sources = []
    for subsystem in subsystems:
        for path in subsystem.get("entry_files", []):
            if path not in sources:
                sources.append(path)

    return {
        "mode": "production_layout",
        "answer": "\n".join(lines),
        "findings": [item["name"] for item in ranked[:12]],
        "evidence": evidence,
        "sources": sources[:12],
        "interpretation": {
            "category": "production_layout",
            "interpretation_confidence": "high",
            "support_confidence": "high",
        },
    }


def _answer_dependency_centrality(index: Dict[str, Any]) -> Dict[str, Any]:
    graph = _build_depgraph(index)
    if graph is None:
        payload = _graph_unavailable(index, "Project root missing; cannot build dependency graph.")
        payload["mode"] = "dependency"
        return payload
    if graph.get("degraded"):
        payload = _graph_unavailable(
            index,
            "Dependency graph degraded — cannot compute incoming dependency centrality.",
        )
        payload["mode"] = "dependency"
        return payload

    nodes_by_id = {node["id"]: node for node in graph.get("nodes", [])}
    reverse_counts: Dict[str, int] = {}
    evidence_edges: Dict[str, List[str]] = {}
    for edge in graph.get("edges", []):
        if edge.get("type") != "imports" or not edge.get("resolved"):
            continue
        target = edge.get("to")
        if not target:
            continue
        reverse_counts[target] = reverse_counts.get(target, 0) + 1
        source = edge.get("from")
        node = nodes_by_id.get(target, {})
        label = node.get("dotted") or node.get("path") or target
        evidence_edges.setdefault(label, [])
        src_node = nodes_by_id.get(source, {})
        src_label = src_node.get("dotted") or src_node.get("path") or source
        line = int(edge.get("line", 0))
        snippet = f"{src_label}:{line} imports {label}"
        if snippet not in evidence_edges[label]:
            evidence_edges[label].append(snippet)

    ranked = sorted(
        reverse_counts.items(),
        key=lambda kv: (-kv[1], kv[0]),
    )
    lines = ["Modules ranked by incoming import edges (dependency graph):"]
    sources: List[str] = []
    evidence: List[str] = []
    for position, (module_id, count) in enumerate(ranked[:12], 1):
        node = nodes_by_id.get(module_id, {})
        label = node.get("dotted") or node.get("path") or module_id
        path = node.get("path")
        if path and path not in sources:
            sources.append(path)
        lines.append(f"{position}. {label}: {count} incoming import edge(s)")
        for item in sorted(evidence_edges.get(label, []))[:3]:
            evidence.append(item)

    stats = graph.get("statistics", {}).get("top_imported_modules") or []
    if stats:
        top_stat = stats[0]
        stat_id = top_stat.get("id")
        if stat_id in reverse_counts:
            evidence.append(
                f"depgraph statistics cross-check: {top_stat.get('dotted') or stat_id} "
                f"count={top_stat.get('count')} matches reverse index "
                f"count={reverse_counts[stat_id]}"
            )

    return {
        "mode": "dependency",
        "answer": "\n".join(lines) if ranked else "No resolved import edges in the dependency graph.",
        "findings": [nodes_by_id.get(mid, {}).get("dotted") or mid for mid, _ in ranked[:12]],
        "evidence": evidence,
        "sources": sources[:12],
        "interpretation": {
            "category": "dependency_centrality",
            "interpretation_confidence": "high",
            "support_confidence": "high" if ranked else "unknown",
        },
    }


def _answer_subsystem_centrality(index: Dict[str, Any]) -> Dict[str, Any]:
    graph = _build_depgraph(index)
    if graph is None:
        payload = _graph_unavailable(index, "Project root missing; cannot build dependency graph.")
        payload["mode"] = "subsystem"
        return payload
    if graph.get("degraded"):
        payload = _graph_unavailable(
            index,
            "Dependency graph degraded — cannot compute subsystem centrality.",
        )
        payload["mode"] = "subsystem"
        return payload

    nodes_by_id = {node["id"]: node for node in graph.get("nodes", [])}
    fan_in: Dict[str, set[str]] = {}
    fan_out: Dict[str, set[str]] = {}
    evidence: List[str] = []

    for edge in graph.get("edges", []):
        if edge.get("type") != "imports" or not edge.get("resolved"):
            continue
        to_node = nodes_by_id.get(edge.get("to", ""), {})
        from_node = nodes_by_id.get(edge.get("from", ""), {})
        to_path = to_node.get("path") or ""
        from_path = from_node.get("path") or ""
        if not to_path or not from_path:
            continue
        to_sub = _subsystem_name(to_path)
        from_sub = _subsystem_name(from_path)
        if to_sub == from_sub:
            continue
        fan_in.setdefault(to_sub, set()).add(from_sub)
        fan_out.setdefault(from_sub, set()).add(to_sub)
        evidence.append(
            f"imports edge: {from_sub} -> {to_sub} "
            f"({from_node.get('dotted') or from_path}:{int(edge.get('line', 0))})"
        )

    ranked = sorted(
        fan_in.items(),
        key=lambda kv: (-len(kv[1]), len(fan_out.get(kv[0], set())), kv[0]),
    )
    lines = ["Production subsystems ranked by cross-subsystem import fan-in:"]
    sources: List[str] = []
    for position, (name, importers) in enumerate(ranked[:12], 1):
        importer_list = ", ".join(sorted(importers)) or "(none)"
        lines.append(f"{position}. {name}: fan-in={len(importers)} from [{importer_list}]")
        for subsystem in index.get("subsystems", []):
            if subsystem.get("name") != name:
                continue
            for path in subsystem.get("entry_files", []):
                if path not in sources:
                    sources.append(path)

    return {
        "mode": "subsystem",
        "answer": "\n".join(lines) if ranked else "No cross-subsystem import edges found.",
        "findings": [name for name, _ in ranked[:12]],
        "evidence": sorted(evidence)[:20],
        "sources": sources[:12],
        "interpretation": {
            "category": "subsystem_centrality",
            "interpretation_confidence": "high",
            "support_confidence": "high" if ranked else "medium",
        },
    }


def _answer_bottlenecks(index: Dict[str, Any]) -> Dict[str, Any]:
    graph = _build_depgraph(index)
    if graph is None:
        payload = _graph_unavailable(index, "Project root missing; cannot build dependency graph.")
        payload["mode"] = "bottleneck"
        return payload
    if graph.get("degraded"):
        payload = _graph_unavailable(
            index,
            "Dependency graph degraded — cannot compute architectural bottlenecks.",
        )
        payload["mode"] = "bottleneck"
        return payload

    stats = graph.get("statistics", {})
    nodes_by_id = {node["id"]: node for node in graph.get("nodes", [])}
    import_counts: Dict[str, int] = {}
    for edge in graph.get("edges", []):
        if edge.get("type") == "imports" and edge.get("resolved") and edge.get("to"):
            import_counts[edge["to"]] = import_counts.get(edge["to"], 0) + 1

    cycle_modules: set[str] = set()
    for cycle in stats.get("import_cycles", []):
        cycle_modules.update(cycle)

    components = stats.get("largest_components") or []
    large_roots = {item.get("root") for item in components[:5]}

    scored: Dict[str, Dict[str, Any]] = {}
    for module_id, count in import_counts.items():
        node = nodes_by_id.get(module_id, {})
        label = node.get("dotted") or node.get("path") or module_id
        score = count
        reasons: List[str] = [f"import fan-in={count}"]
        if module_id in cycle_modules:
            score += 5
            reasons.append("import-cycle member")
        if module_id in large_roots:
            score += 3
            reasons.append("large-component root")
        scored[label] = {
            "score": score,
            "reasons": reasons,
            "path": node.get("path"),
            "module_id": module_id,
        }

    ranked = sorted(scored.items(), key=lambda kv: (-kv[1]["score"], kv[0]))
    lines = ["Critical architectural bottlenecks (import fan-in, cycles, component roots):"]
    sources: List[str] = []
    evidence: List[str] = []
    for position, (label, item) in enumerate(ranked[:12], 1):
        lines.append(f"{position}. {label}: score={item['score']} ({', '.join(item['reasons'])})")
        path = item.get("path")
        if path and path not in sources:
            sources.append(path)
        evidence.append(f"bottleneck signal: {label} -> {', '.join(item['reasons'])}")

    if stats.get("import_cycles"):
        evidence.append(f"import cycles detected: {len(stats['import_cycles'])}")

    return {
        "mode": "bottleneck",
        "answer": "\n".join(lines) if ranked else "No bottleneck signals from the dependency graph.",
        "findings": [label for label, _ in ranked[:12]],
        "evidence": evidence,
        "sources": sources[:12],
        "interpretation": {
            "category": "bottleneck",
            "interpretation_confidence": "high",
            "support_confidence": "high" if ranked else "medium",
        },
    }


def _answer_impact(index: Dict[str, Any], question: str) -> Dict[str, Any]:
    from .bug_intelligence import impact

    graph = _build_depgraph(index)
    if graph is None:
        payload = _graph_unavailable(index, "Project root missing; cannot run impact analysis.")
        payload["mode"] = "impact"
        return payload

    lowered = question.lower()
    target_file = None
    for item in index.get("files", []):
        path = item.get("path", "")
        if path and path.lower() in lowered:
            target_file = path
            break
    if target_file is None:
        payload = _graph_unavailable(
            index,
            "Impact question requires a named file target; none found in the question.",
        )
        payload["mode"] = "impact"
        payload["interpretation"] = {
            "category": "impact",
            "interpretation_confidence": "medium",
            "support_confidence": "unknown",
        }
        return payload

    result = impact.analyze_impact(
        graph,
        kind="file",
        file_path=target_file,
        project_root=index.get("project_root", "."),
    )
    may = result.get("questions", {}).get("may_break", {})
    risk = result.get("risk", {})
    confidence = result.get("confidence", {})
    answer = (
        f"Impact analysis for {target_file}: direct={may.get('direct_count', 0)} "
        f"transitive={may.get('transitive_count', 0)} "
        f"risk={risk.get('bucket')} confidence={confidence.get('bucket')}."
    )
    if result.get("possible_additional_impact"):
        answer += (
            f" {len(result['possible_additional_impact'])} possible unverified item(s) — "
            "impact may be incomplete."
        )

    sources = [
        item.get("path")
        for item in result.get("questions", {}).get("files_dependent", [])
        if item.get("path")
    ]
    evidence = [
        f"{item.get('path')}:{item.get('evidence', [{}])[0].get('line', '?')}"
        for item in result.get("questions", {}).get("files_dependent", [])[:12]
        if item.get("evidence")
    ]

    return {
        "mode": "impact",
        "answer": answer,
        "findings": sources[:12],
        "evidence": evidence or [f"impact target: {target_file}"],
        "sources": sources[:12],
        "interpretation": {
            "category": "impact",
            "interpretation_confidence": "high",
            "support_confidence": confidence.get("bucket", "unknown"),
        },
    }


def _route_ru3_answer(
    index: Dict[str, Any], question: str, detail: Dict[str, Any]
) -> Dict[str, Any] | None:
    if not str(detail.get("fired_rule", "")).startswith("anchor:"):
        return None
    category = detail.get("category")
    if category == "production_layout":
        return _answer_production_layout(index)
    if category == "dependency_centrality":
        return _answer_dependency_centrality(index)
    if category == "subsystem_centrality":
        return _answer_subsystem_centrality(index)
    if category == "bottleneck":
        return _answer_bottlenecks(index)
    if category == "impact":
        return _answer_impact(index, question)
    return None


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
    elif question_understanding.QUESTION_UNDERSTANDING_ENABLED:
        detail = question_understanding.classify_question_detail(question)
        result = _route_ru3_answer(index, question, detail)
        if result is None:
            mode = question_understanding.public_answer_mode(question, detail)
            if mode == "risk":
                result = _answer_risk(index)
            elif mode == "architecture":
                result = _answer_architecture(index, question)
            else:
                result = _answer_retrieval(index, question)
        result["question_detail"] = detail
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
