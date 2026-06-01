"""Phase 104C — compact fact packets for benchmark JARVIS context."""

from __future__ import annotations

import hashlib
import json
import os
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Tuple

if TYPE_CHECKING:
    from .context_cache import BenchmarkContextSession

from .jarvis_packet import format_jarvis_packet
from .schema import BenchmarkTask
from .tokens import estimated_count

PACKET_VERSION = "1"
COMPACT_INSTRUMENTATION_VERSION = "phase104c-v1"

TASK_TO_KIND = {
    "repository_understanding": "REPO_MAP",
    "dependency_analysis": "DEPENDENCY",
    "impact_analysis": "IMPACT",
    "architectural_risk": "ARCH_RISK",
    "contract_analysis": "CONTRACT",
    "verification_evidence": "VERIFY",
    "confirmed_defect_detection": "DEFECT_REVIEW",
    "fix_planning": "PLAN_INPUT",
}

HARD_TOKEN_CAPS = {
    "REPO_MAP": 350,
    "DEPENDENCY": 325,
    "IMPACT": 275,
    "ARCH_RISK": 400,
    "CONTRACT": 300,
    "VERIFY": 350,
    "DEFECT_REVIEW": 300,
    "PLAN_INPUT": 275,
    "RETRIEVAL": 325,
}

_DATASET_PREFIXES = ("data/", "dataset/", "fixtures/", "samples/")
_CORPUS_MARKERS = ("real_repo_corpus",)


def packet_format_from_env() -> str:
    value = os.environ.get("JARVIS_CONTEXT_PACKET_FORMAT", "prose").strip().lower()
    return value if value in {"prose", "compact"} else "prose"


def escape_value(value: Any) -> str:
    text = str(value if value is not None else "")
    text = text.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "\\n").replace("\r", "")
    return text


def format_row(prefix: str, fields: Dict[str, Any]) -> str:
    parts = [f"{key}={escape_value(val)}" for key, val in fields.items()]
    return f"{prefix}|" + "|".join(parts)


def resolve_packet_kind(task: BenchmarkTask, result: Dict[str, Any]) -> str:
    """Task type drives packet family so unrelated tasks do not share identical packets."""
    kind = TASK_TO_KIND.get(task.task_type, "RETRIEVAL")
    mode = str(result.get("mode", ""))
    if task.task_type == "architectural_risk":
        return "ARCH_RISK"
    if task.task_type == "impact_analysis":
        return "IMPACT"
    if task.task_type == "dependency_analysis":
        return "DEPENDENCY"
    if task.task_type == "repository_understanding":
        return "REPO_MAP"
    if task.task_type == "contract_analysis":
        return "CONTRACT"
    if task.task_type == "verification_evidence":
        return "VERIFY"
    if task.task_type == "confirmed_defect_detection":
        return "DEFECT_REVIEW"
    if task.task_type == "fix_planning":
        return "PLAN_INPUT"
    if mode == "bottleneck":
        return "ARCH_RISK"
    if mode == "impact":
        return "IMPACT"
    if mode == "dependency":
        return "DEPENDENCY"
    if mode in {"architecture", "production_layout", "subsystem"}:
        return "REPO_MAP"
    if mode == "python_analysis":
        return "DEFECT_REVIEW"
    return kind if kind != "RETRIEVAL" else "RETRIEVAL"


def _srcq_row(quality: Dict[str, Any]) -> str:
    return format_row(
        "SRCQ",
        {
            "PROD": int(quality.get("production_percent", 0)),
            "ARCH": int(quality.get("architecture_percent", 0)),
            "REPORT": int(quality.get("reports_percent", 0)),
            "BENCH": int(quality.get("benchmark_percent", 0)),
        },
    )


def _is_product_subsystem(subsystem: Dict[str, Any]) -> bool:
    name = str(subsystem.get("name", "")).replace("\\", "/")
    if name in {"data", "dataset", "datasets", "fixtures", "samples"}:
        return False
    if any(name.startswith(prefix) for prefix in _DATASET_PREFIXES):
        return False
    if any(marker in name for marker in _CORPUS_MARKERS):
        return False
    for path in subsystem.get("entry_files", []):
        normalized = str(path).replace("\\", "/")
        if normalized.startswith("data/") or any(marker in normalized for marker in _CORPUS_MARKERS):
            return False
    return True


def _dedupe_refs(paths: Sequence[str]) -> List[Tuple[str, str]]:
    refs: List[Tuple[str, str]] = []
    seen: set[str] = set()
    for index, path in enumerate(paths, 1):
        if not path or path in seen:
            continue
        seen.add(path)
        refs.append((f"R{index}", path))
    return refs


def _refs_block(paths: Sequence[str], *, limit: int = 8) -> List[str]:
    return [format_row("REF", {"ID": ref_id, "PATH": path}) for ref_id, path in _dedupe_refs(paths)[:limit]]


def _caveat_rows(result: Dict[str, Any]) -> List[str]:
    rows: List[str] = []
    interpretation = result.get("interpretation") or {}
    support = interpretation.get("support_confidence", "")
    if support and support != "high":
        rows.append(format_row("CAVEAT", {"CODE": "SUPPORT_CONFIDENCE", "VALUE": support}))
    answer = str(result.get("answer", "")).lower()
    if "degraded" in answer:
        rows.append(format_row("CAVEAT", {"CODE": "GRAPH_DEGRADED", "VALUE": "yes"}))
    if "unavailable" in answer:
        rows.append(format_row("CAVEAT", {"CODE": "ANALYSIS_UNAVAILABLE", "VALUE": "yes"}))
    if "incomplete" in answer or "unverified" in answer:
        rows.append(format_row("CAVEAT", {"CODE": "IMPACT_INCOMPLETE", "VALUE": "yes"}))
    ranking = result.get("architectural_risk_ranking") or {}
    if ranking.get("degraded"):
        rows.append(format_row("CAVEAT", {"CODE": "GRAPH_DEGRADED", "VALUE": "yes"}))
    return rows


def _target_from_task(task: BenchmarkTask, index: Dict[str, Any]) -> Optional[str]:
    for item in task.required_evidence:
        if item.endswith(".py"):
            return item
    lowered = task.prompt.lower()
    for file_item in index.get("files", []):
        path = file_item.get("path", "")
        if path and path.lower() in lowered:
            return path
    match = re.search(r"[\w./-]+\.py", task.prompt)
    return match.group(0) if match else None


def _header(kind: str, mode: str, scope: str) -> str:
    return format_row(
        "PACKET",
        {"V": PACKET_VERSION, "KIND": kind, "MODE": mode, "SCOPE": scope},
    )


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _build_repo_map(
    result: Dict[str, Any],
    task: BenchmarkTask,
    index: Dict[str, Any],
    session: Optional["BenchmarkContextSession"] = None,
) -> Tuple[List[str], Dict[str, Any]]:
    rows = [_header("REPO_MAP", result.get("mode", "architecture"), "production")]
    if session is not None:
        subsystems = session.get_production_subsystems()
    else:
        from .. import repository_understanding as ru

        subsystems = [item for item in ru.production_subsystems(index) if _is_product_subsystem(item)]
    sources: List[str] = []
    for subsystem in subsystems[:10]:
        production = subsystem.get("role_counts", {}).get("production_code", 0)
        entry = (subsystem.get("entry_files") or [""])[0]
        deps = ",".join(subsystem.get("dependencies", [])[:6])
        rows.append(
            format_row(
                "SUBSYSTEM",
                {
                    "NAME": subsystem.get("name", ""),
                    "ROLE": "production_code",
                    "FILES": production,
                    "ENTRY": entry,
                    "DEPS": deps,
                },
            )
        )
        sources.extend(subsystem.get("entry_files", [])[:2])
    rows.extend(_caveat_rows(result))
    quality = result.get("ask_quality") or {}
    if quality:
        rows.append(_srcq_row(quality))
    rows.extend(_refs_block(sources + list(result.get("sources", []))))
    expanded = {
        "kind": "REPO_MAP",
        "task_id": task.task_id,
        "subsystems": subsystems[:20],
        "answer": result.get("answer", ""),
    }
    return rows, expanded


def _build_dependency(
    result: Dict[str, Any],
    task: BenchmarkTask,
    index: Dict[str, Any],
    session: Optional["BenchmarkContextSession"] = None,
) -> Tuple[List[str], Dict[str, Any]]:
    if session is not None:
        graph = session.get_dependency_graph()
    else:
        from ..bug_intelligence import depgraph

        graph = depgraph.build_graph(index.get("project_root", task.repo_path))
    target = _target_from_task(task, index) or "builder_core/bug_intelligence/engine.py"
    rows = [_header("DEPENDENCY", result.get("mode", "dependency"), "production")]
    rows.append(format_row("TARGET", {"PATH": target}))
    edges: List[str] = []
    if graph and not graph.get("degraded"):
        nodes = {node["id"]: node for node in graph.get("nodes", [])}
        target_ids = {
            node_id
            for node_id, node in nodes.items()
            if node.get("path") == target or target in str(node.get("dotted", ""))
        }
        edge_count = 0
        for edge in graph.get("edges", []):
            if edge.get("type") != "imports" or not edge.get("resolved"):
                continue
            to_id = edge.get("to", "")
            from_id = edge.get("from", "")
            if to_id not in target_ids and from_id not in target_ids:
                continue
            from_node = nodes.get(from_id, {})
            to_node = nodes.get(to_id, {})
            edge_count += 1
            if edge_count <= 8:
                edges.append(
                    format_row(
                        "EDGE",
                        {
                            "ID": f"E{edge_count}",
                            "FROM": from_node.get("path", from_id),
                            "TO": to_node.get("path", to_id),
                            "LINE": int(edge.get("line", 0)),
                        },
                    )
                )
        unresolved = (graph.get("statistics") or {}).get("unresolved_counts", {})
        if unresolved:
            total_unresolved = sum(int(v) for v in unresolved.values())
            rows.append(format_row("UNRESOLVED", {"COUNT": total_unresolved}))
    else:
        rows.append(format_row("CAVEAT", {"CODE": "GRAPH_DEGRADED", "VALUE": "yes"}))
    rows.extend(edges)
    rows.extend(_caveat_rows(result))
    rows.extend(_refs_block([target] + list(result.get("sources", []))))
    expanded = {"kind": "DEPENDENCY", "task_id": task.task_id, "target": target, "graph_scope": graph.get("graph_scope") if graph else None}
    return rows, expanded


def _build_impact(
    result: Dict[str, Any],
    task: BenchmarkTask,
    index: Dict[str, Any],
    session: Optional["BenchmarkContextSession"] = None,
) -> Tuple[List[str], Dict[str, Any]]:
    from ..bug_intelligence import impact

    target = _target_from_task(task, index) or "config.py"
    if session is not None:
        graph = session.get_dependency_graph()
    else:
        from ..bug_intelligence import depgraph

        graph = depgraph.build_graph(index.get("project_root", task.repo_path))
    rows = [_header("IMPACT", "impact", "production")]
    rows.append(format_row("TARGET", {"PATH": target}))
    impact_payload: Dict[str, Any] = {}
    if graph and not graph.get("degraded"):
        impact_payload = impact.analyze_impact(
            graph,
            kind="file",
            file_path=target,
            project_root=index.get("project_root", task.repo_path),
        )
        may = impact_payload.get("questions", {}).get("may_break", {})
        risk = impact_payload.get("risk", {})
        confidence = impact_payload.get("confidence", {})
        rows.append(
            format_row(
                "IMPACT",
                {
                    "DIRECT": may.get("direct_count", 0),
                    "TRANSITIVE": may.get("transitive_count", 0),
                    "RISK": risk.get("bucket", "unknown"),
                    "CONFIDENCE": confidence.get("bucket", "unknown"),
                },
            )
        )
        dependents = impact_payload.get("questions", {}).get("files_dependent", [])[:6]
        for index_no, item in enumerate(dependents, 1):
            rows.append(
                format_row(
                    "DEPENDENT",
                    {
                        "ID": f"D{index_no}",
                        "PATH": item.get("path", ""),
                        "KIND": item.get("kind", "direct"),
                    },
                )
            )
        unverified = len(impact_payload.get("possible_additional_impact", []) or [])
        if unverified:
            rows.append(format_row("CAVEAT", {"CODE": "IMPACT_INCOMPLETE", "UNVERIFIED": unverified}))
    else:
        rows.append(format_row("CAVEAT", {"CODE": "GRAPH_DEGRADED", "VALUE": "yes"}))
    rows.extend(_caveat_rows(result))
    sources = [item.get("path", "") for item in impact_payload.get("questions", {}).get("files_dependent", []) if item.get("path")]
    rows.extend(_refs_block([target] + sources))
    expanded = {"kind": "IMPACT", "task_id": task.task_id, "target": target, "impact": impact_payload}
    return rows, expanded


def _build_arch_risk(
    result: Dict[str, Any],
    task: BenchmarkTask,
    index: Dict[str, Any],
    session: Optional["BenchmarkContextSession"] = None,
) -> Tuple[List[str], Dict[str, Any]]:
    from .. import architectural_risk

    if session is not None:
        graph = session.get_dependency_graph()
    else:
        from ..bug_intelligence import depgraph

        graph = depgraph.build_graph(index.get("project_root", task.repo_path))
    ranking = result.get("architectural_risk_ranking")
    if ranking is None and graph:
        if session is not None:
            ranking = session.get_architectural_risk_ranking(top=12)
        else:
            ranking = architectural_risk.rank_modules(index, graph, top=12)
    rows = [_header("ARCH_RISK", result.get("mode", "bottleneck"), "production")]
    modules = list((ranking or {}).get("ranked_modules", []))[:12]
    for item in modules:
        metrics = item.get("metrics", {})
        breakdown = item.get("score_breakdown", {})
        rows.append(
            format_row(
                "MODULE",
                {
                    "PATH": item.get("path", item.get("label", "")),
                    "RANK": item.get("rank", 0),
                    "SCORE": item.get("total_score", 0),
                    "FAN_IN": metrics.get("fan_in", 0),
                    "FAN_OUT": metrics.get("fan_out", 0),
                    "CYCLES": breakdown.get("import_cycle_member", 0),
                    "LOC": metrics.get("line_count", 0),
                    "TESTED": _yes_no(bool(metrics.get("has_test_reference"))),
                    "CONTRACT": breakdown.get("contract_evidence", 0),
                    "STATIC": breakdown.get("static_findings", 0),
                },
            )
        )
    if ranking:
        rows.append(
            format_row(
                "GRAPH",
                {
                    "MODULES": ranking.get("modules_considered", 0),
                    "PAIRS": ranking.get("deduped_import_pairs", 0),
                    "CYCLES": ranking.get("import_cycle_count", 0),
                    "DEGRADED": _yes_no(bool(ranking.get("degraded"))),
                },
            )
        )
    rows.extend(_caveat_rows(result))
    rows.extend(_refs_block([item.get("path", "") for item in modules if item.get("path")]))
    expanded = {"kind": "ARCH_RISK", "task_id": task.task_id, "ranking": ranking}
    return rows, expanded


def _build_contract(
    result: Dict[str, Any],
    task: BenchmarkTask,
    index: Dict[str, Any],
    session: Optional["BenchmarkContextSession"] = None,
) -> Tuple[List[str], Dict[str, Any]]:
    rows = [_header("CONTRACT", result.get("mode", "retrieval"), "production")]
    analysis = _matching_analysis(task, index)
    contract_rows = 0
    if analysis:
        rows.append(format_row("SYMBOL", {"PATH": analysis.get("path", "")}))
        for finding in analysis.get("findings", [])[:6]:
            if finding.get("rule") == "wrong_return_shape":
                contract_rows += 1
                rows.append(
                    format_row(
                        "CONTRACT",
                        {
                            "ID": f"C{contract_rows}",
                            "TYPE": "return_shape",
                            "RULE": finding.get("rule", ""),
                            "SEVERITY": finding.get("severity", "low"),
                            "LINE": finding.get("line", 0),
                        },
                    )
                )
        rows.append(format_row("CAVEAT", {"CODE": "USAGE_CONTRACT_NOT_PROVEN", "VALUE": "yes"}))
    rows.extend(_caveat_rows(result))
    rows.extend(_refs_block(list(result.get("sources", [])) + ([analysis.get("path")] if analysis else [])))
    expanded = {"kind": "CONTRACT", "task_id": task.task_id, "analysis": analysis}
    return rows, expanded


def _build_verify(
    result: Dict[str, Any],
    task: BenchmarkTask,
    index: Dict[str, Any],
    session: Optional["BenchmarkContextSession"] = None,
) -> Tuple[List[str], Dict[str, Any]]:
    rows = [_header("VERIFY", result.get("mode", "retrieval"), "finding")]
    rows.append(format_row("CAVEAT", {"CODE": "NON_PROMOTING_EVIDENCE", "VALUE": "yes"}))
    for index_no, item in enumerate(result.get("evidence", [])[:6], 1):
        rows.append(
            format_row(
                "EVIDENCE",
                {
                    "ID": f"V{index_no}",
                    "TYPE": "repository_fact",
                    "TEXT": str(item)[:120],
                },
            )
        )
    rows.extend(_caveat_rows(result))
    rows.extend(_refs_block(result.get("sources", [])))
    expanded = {"kind": "VERIFY", "task_id": task.task_id, "evidence": result.get("evidence", [])}
    return rows, expanded


def _build_defect_review(
    result: Dict[str, Any],
    task: BenchmarkTask,
    index: Dict[str, Any],
    session: Optional["BenchmarkContextSession"] = None,
) -> Tuple[List[str], Dict[str, Any]]:
    target = _target_from_task(task, index)
    analysis = _matching_analysis(task, index)
    rows = [_header("DEFECT_REVIEW", result.get("mode", "python_analysis"), "fixture" if target and "python_programs" in target else "production")]
    if target:
        rows.append(format_row("TARGET", {"PATH": target}))
    if analysis:
        for index_no, finding in enumerate(analysis.get("findings", [])[:6], 1):
            rows.append(
                format_row(
                    "FINDING",
                    {
                        "ID": f"F{index_no}",
                        "RULE": finding.get("rule", ""),
                        "SEVERITY": finding.get("severity", "low"),
                        "LINE": finding.get("line", 0),
                        "STATUS": "review_lead",
                    },
                )
            )
        for expectation in analysis.get("test_expectations", [])[:3]:
            rows.append(
                format_row(
                    "EXPECT",
                    {
                        "TYPE": expectation.get("type", ""),
                        "DETAIL": str(expectation.get("detail", ""))[:80],
                        "SOURCE": expectation.get("source", ""),
                    },
                )
            )
    rows.append(format_row("CAVEAT", {"CODE": "REVIEW_LEAD_NOT_CONFIRMED", "VALUE": "yes"}))
    rows.extend(_caveat_rows(result))
    ref_paths = ([target] if target else []) + list(result.get("sources", []))
    rows.extend(_refs_block(ref_paths))
    expanded = {"kind": "DEFECT_REVIEW", "task_id": task.task_id, "analysis": analysis}
    return rows, expanded


def _build_plan_input(
    result: Dict[str, Any],
    task: BenchmarkTask,
    index: Dict[str, Any],
    session: Optional["BenchmarkContextSession"] = None,
) -> Tuple[List[str], Dict[str, Any]]:
    impact_rows, impact_expanded = _build_impact(result, task, index, session=session)
    rows = [_header("PLAN_INPUT", result.get("mode", "impact"), "production")]
    for row in impact_rows[1:]:
        if row.startswith("TARGET|") or row.startswith("IMPACT|") or row.startswith("DEPENDENT|") or row.startswith("CAVEAT|"):
            rows.append(row)
    rows.append(format_row("CONSTRAINT", {"TYPE": "preserve_public_contract", "VALUE": "yes"}))
    rows.append(format_row("VERIFY", {"TYPE": "targeted_tests", "VALUE": "required"}))
    rows.extend(_refs_block(result.get("sources", [])))
    expanded = {"kind": "PLAN_INPUT", "task_id": task.task_id, "impact": impact_expanded.get("impact")}
    return rows, expanded


def _build_retrieval(
    result: Dict[str, Any],
    task: BenchmarkTask,
    index: Dict[str, Any],
    session: Optional["BenchmarkContextSession"] = None,
) -> Tuple[List[str], Dict[str, Any]]:
    rows = [_header("RETRIEVAL", result.get("mode", "retrieval"), "repository")]
    query = task.prompt[:120]
    rows.append(format_row("QUERY", {"TEXT": query}))
    excerpt_chars = 0
    for index_no, item in enumerate(result.get("evidence", [])[:5], 1):
        text = str(item)
        if len(text) > 160:
            text = text[:157] + "..."
        excerpt_chars += len(text)
        if excerpt_chars > 500:
            break
        path = text.split(":", 1)[0] if ":" in text else ""
        rows.append(
            format_row(
                "HIT",
                {
                    "ID": f"H{index_no}",
                    "REF": f"R{index_no}",
                    "EXCERPT": text[:160],
                },
            )
        )
    rows.append(format_row("CAVEAT", {"CODE": "NO_SPECIALIZED_PACKET", "VALUE": "yes"}))
    rows.extend(_caveat_rows(result))
    quality = result.get("ask_quality") or {}
    if quality:
        rows.append(_srcq_row(quality))
    rows.extend(_refs_block(result.get("sources", [])))
    expanded = {"kind": "RETRIEVAL", "task_id": task.task_id, "answer": result.get("answer", "")}
    return rows, expanded


def _matching_analysis(task: BenchmarkTask, index: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    lowered = task.prompt.lower()
    for item in index.get("python_analysis", []):
        path = item.get("path", "")
        if path and path.lower() in lowered:
            return item
        base = path.replace("\\", "/").split("/")[-1].lower()
        if base and base in lowered:
            return item
    return None


_BUILDERS = {
    "REPO_MAP": _build_repo_map,
    "DEPENDENCY": _build_dependency,
    "IMPACT": _build_impact,
    "ARCH_RISK": _build_arch_risk,
    "CONTRACT": _build_contract,
    "VERIFY": _build_verify,
    "DEFECT_REVIEW": _build_defect_review,
    "PLAN_INPUT": _build_plan_input,
    "RETRIEVAL": _build_retrieval,
}


def _apply_cap(
    rows: List[str],
    kind: str,
    expanded: Dict[str, Any],
) -> Tuple[str, Dict[str, Any], bool]:
    cap = HARD_TOKEN_CAPS.get(kind, 325)
    text = "\n".join(rows)
    if estimated_count(text) <= cap:
        return text, expanded, False
    header = rows[0]
    kept = [header]
    body = rows[1:]
    truncated = False
    while body:
        candidate = "\n".join(kept + body)
        if estimated_count(candidate) <= cap:
            kept.extend(body)
            break
        body = body[:-1]
        truncated = True
    if truncated:
        digest = hashlib.sha256(json.dumps(expanded, sort_keys=True, ensure_ascii=True).encode("utf-8")).hexdigest()
        kept.append(format_row("TRUNCATED", {"ROWS": f"{len(kept)-1}/{len(rows)-1}"}))
        kept.append(format_row("DETAIL", {"PATH": "context_packet.expanded.json", "SHA256": digest}))
        expanded["truncated"] = True
        expanded["sha256"] = digest
    return "\n".join(kept), expanded, truncated


def build_compact_packet(
    result: Dict[str, Any],
    task: BenchmarkTask,
    index: Dict[str, Any],
    *,
    session: Optional["BenchmarkContextSession"] = None,
) -> Tuple[str, Dict[str, Any], str]:
    """Return compact packet text, expanded sidecar payload, and packet kind."""
    kind = resolve_packet_kind(task, result)
    builder = _BUILDERS.get(kind, _build_retrieval)
    rows, expanded = builder(result, task, index, session=session)
    text, expanded, _ = _apply_cap(rows, kind, expanded)
    expanded["packet_format"] = "compact"
    expanded["packet_kind"] = kind
    expanded["ask_mode"] = result.get("mode")
    expanded["prose_answer"] = result.get("answer", "")
    return text, expanded, kind


def compare_context_formats(
    result: Dict[str, Any],
    task: BenchmarkTask,
    index: Dict[str, Any],
    *,
    session: Optional["BenchmarkContextSession"] = None,
) -> Dict[str, Any]:
    """Token accounting for verbose vs compact JARVIS context."""
    verbose = format_jarvis_packet(result)
    compact, _expanded, kind = build_compact_packet(result, task, index, session=session)
    verbose_tokens = estimated_count(verbose)
    compact_tokens = estimated_count(compact)
    reduction = (
        round(100.0 * (verbose_tokens - compact_tokens) / verbose_tokens, 2)
        if verbose_tokens
        else 0.0
    )
    return {
        "instrumentation_version": COMPACT_INSTRUMENTATION_VERSION,
        "task_id": task.task_id,
        "task_type": task.task_type,
        "packet_kind": kind,
        "verbose_tokens": verbose_tokens,
        "compact_tokens": compact_tokens,
        "reduction_percent": reduction,
        "meets_fifty_percent_reduction": reduction >= 50.0,
    }


def format_jarvis_context(
    result: Dict[str, Any],
    task: BenchmarkTask,
    index: Dict[str, Any],
    *,
    packet_format: Optional[str] = None,
    session: Optional["BenchmarkContextSession"] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Format JARVIS context using prose (default) or compact fact packets."""
    selected = (packet_format or packet_format_from_env()).lower()
    comparison = compare_context_formats(result, task, index, session=session)
    if selected == "compact":
        compact, expanded, kind = build_compact_packet(result, task, index, session=session)
        comparison["selected_format"] = "compact"
        comparison["packet_kind"] = kind
        meta: Dict[str, Any] = {
            "comparison": comparison,
            "expanded": expanded,
            "compact_text": compact,
        }
        if session is not None:
            meta["cache_diagnostics"] = session.diagnostics_dict()
        return compact, meta
    prose = format_jarvis_packet(result)
    comparison["selected_format"] = "prose"
    meta = {"comparison": comparison, "expanded": {"packet_format": "prose", "ask_mode": result.get("mode")}}
    if session is not None:
        meta["cache_diagnostics"] = session.diagnostics_dict()
    return prose, meta
