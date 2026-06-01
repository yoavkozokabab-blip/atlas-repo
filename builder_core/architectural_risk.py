"""Architectural risk ranking (Phase 102).

Deterministic module-level ranking over the production-scoped dependency graph
(Phase 100G). Consumes depgraph + repository index signals; no LLM.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from . import risk as risk_mod
from . import repository_understanding as ru

SCHEMA_VERSION = 1
ENGINE_VERSION = "phase102-v1"

# Score weights (frozen for benchmark reproducibility).
WEIGHT_FAN_IN = 1.0
WEIGHT_FAN_OUT = 0.35
WEIGHT_CYCLE_MEMBER = 5.0
WEIGHT_COMPONENT_ROOT = 3.0
WEIGHT_LOC_BLOCK = 500  # +1 score per block, max LOC_SCORE_CAP
LOC_SCORE_CAP = 4.0
WEIGHT_UNTESTED = 3.0
WEIGHT_CHURN_BLOCK = 5  # +0.5 per block, max CHURN_SCORE_CAP
CHURN_SCORE_CAP = 3.0
WEIGHT_CONTRACT_HIGH = 2.0
WEIGHT_CONTRACT_MEDIUM = 1.0
WEIGHT_CONTRACT_LOW = 0.5
WEIGHT_SUBSYSTEM_CROSS_FAN_IN = 2.0  # subsystem is an import hub


def _subsystem_name(path: str) -> str:
    parts = path.replace("\\", "/").split("/")
    return parts[0] if len(parts) > 1 else "(root)"


def _module_stem(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0].lower()


def _index_file_maps(
    index: Dict[str, Any],
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    by_path = {item["path"]: item for item in index.get("files", []) if item.get("path")}
    analysis_by_path = {
        item["path"]: item for item in index.get("python_analysis", []) if item.get("path")
    }
    subsystem_by_name = {
        item["name"]: item for item in index.get("subsystems", []) if item.get("name")
    }
    return by_path, analysis_by_path, subsystem_by_name


def _graph_dependency_metrics(
    graph: Dict[str, Any],
) -> Tuple[
    Dict[str, int],
    Dict[str, int],
    Set[str],
    Set[str],
    List[List[str]],
]:
    nodes_by_id = {node["id"]: node for node in graph.get("nodes", [])}
    fan_in: Dict[str, int] = {}
    fan_out: Dict[str, int] = {}
    for edge in graph.get("edges", []):
        if edge.get("type") != "imports" or not edge.get("resolved"):
            continue
        to_id = edge.get("to", "")
        from_id = edge.get("from", "")
        if to_id:
            fan_in[to_id] = fan_in.get(to_id, 0) + 1
        if from_id:
            fan_out[from_id] = fan_out.get(from_id, 0) + 1

    cycle_modules: Set[str] = set()
    for cycle in graph.get("statistics", {}).get("import_cycles", []):
        cycle_modules.update(cycle)

    component_roots: Set[str] = set()
    for item in graph.get("statistics", {}).get("largest_components") or []:
        root = item.get("root")
        if root:
            component_roots.add(root)

    return fan_in, fan_out, cycle_modules, component_roots, list(
        graph.get("statistics", {}).get("import_cycles", [])
    )


def _subsystem_cross_fan_in(index: Dict[str, Any], graph: Dict[str, Any]) -> Dict[str, int]:
    """Cross-subsystem import fan-in counts (subsystem name -> importer count)."""
    nodes_by_id = {node["id"]: node for node in graph.get("nodes", [])}
    counts: Dict[str, int] = {}
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
        counts[to_sub] = counts.get(to_sub, 0) + 1
    return counts


def _contract_evidence_score(analysis: Optional[Dict[str, Any]]) -> Tuple[float, int]:
    if not analysis:
        return 0.0, 0
    findings = list(analysis.get("findings", []))
    score = 0.0
    for item in findings:
        severity = item.get("severity", "low")
        if severity == "high":
            score += WEIGHT_CONTRACT_HIGH
        elif severity == "medium":
            score += WEIGHT_CONTRACT_MEDIUM
        else:
            score += WEIGHT_CONTRACT_LOW
    return score, len(findings)


def _loc_score(line_count: int) -> float:
    if line_count <= 0:
        return 0.0
    return min(LOC_SCORE_CAP, line_count / WEIGHT_LOC_BLOCK)


def _churn_score(churn: int) -> float:
    if churn <= 0:
        return 0.0
    return min(CHURN_SCORE_CAP, (churn / WEIGHT_CHURN_BLOCK) * 0.5)


def rank_modules(
    index: Dict[str, Any],
    graph: Dict[str, Any],
    *,
    top: int = 12,
) -> Dict[str, Any]:
    """Return structured architectural-risk ranking for production-scoped modules."""
    files_by_path, analysis_by_path, subsystems_by_name = _index_file_maps(index)
    fan_in, fan_out, cycle_modules, component_roots, import_cycles = _graph_dependency_metrics(graph)
    subsystem_fan_in = _subsystem_cross_fan_in(index, graph)
    test_blob = risk_mod._test_corpus(index)
    churn_map = dict(index.get("churn") or {})

    module_nodes = [n for n in graph.get("nodes", []) if n.get("type") == "module"]
    ranked_rows: List[Dict[str, Any]] = []

    for node in module_nodes:
        module_id = node["id"]
        path = node.get("path") or ""
        label = node.get("dotted") or path or module_id
        subsystem = _subsystem_name(path)
        file_meta = files_by_path.get(path, {})
        role = file_meta.get("role") or ru.classify_file_role(
            path, ".py", project_root=index.get("project_root")
        )
        line_count = int(node.get("line_count") or file_meta.get("lines") or 0)
        stem = _module_stem(path)
        has_test = bool(stem) and stem in test_blob
        commits = int(churn_map.get(path, 0))

        fi = fan_in.get(module_id, 0)
        fo = fan_out.get(module_id, 0)
        in_cycle = module_id in cycle_modules
        is_component_root = module_id in component_roots
        contract_score, finding_count = _contract_evidence_score(analysis_by_path.get(path))
        loc_component = _loc_score(line_count)
        churn_component = _churn_score(commits)
        untested_component = WEIGHT_UNTESTED if not has_test else 0.0
        subsystem_component = (
            WEIGHT_SUBSYSTEM_CROSS_FAN_IN
            if subsystem_fan_in.get(subsystem, 0) >= 2
            else 0.0
        )

        breakdown = {
            "fan_in": round(fi * WEIGHT_FAN_IN, 2),
            "fan_out": round(fo * WEIGHT_FAN_OUT, 2),
            "import_cycle_member": round(WEIGHT_CYCLE_MEMBER if in_cycle else 0.0, 2),
            "component_root": round(WEIGHT_COMPONENT_ROOT if is_component_root else 0.0, 2),
            "module_size_loc": round(loc_component, 2),
            "untested_module": round(untested_component, 2),
            "churn_hotspot": round(churn_component, 2),
            "contract_evidence": round(contract_score, 2),
            "subsystem_import_hub": round(subsystem_component, 2),
        }
        total = round(sum(breakdown.values()), 2)

        signals: List[str] = []
        if fi:
            signals.append(f"import fan-in={fi}")
        if fo:
            signals.append(f"import fan-out={fo}")
        if in_cycle:
            signals.append("import-cycle member")
        if is_component_root:
            signals.append("large-component root")
        if line_count:
            signals.append(f"loc={line_count}")
        if not has_test:
            signals.append("no detectable test reference")
        elif finding_count:
            signals.append(f"static findings={finding_count}")
        if commits:
            signals.append(f"recent churn={commits}")
        if subsystem_fan_in.get(subsystem, 0) >= 2:
            signals.append(f"subsystem cross fan-in={subsystem_fan_in[subsystem]}")
        signals.append(f"file_role={role}")

        ranked_rows.append(
            {
                "module_id": module_id,
                "path": path,
                "label": label,
                "subsystem": subsystem,
                "subsystem_role": subsystems_by_name.get(subsystem, {}).get("role", role),
                "file_role": role,
                "total_score": total,
                "score_breakdown": breakdown,
                "signals": signals,
                "metrics": {
                    "fan_in": fi,
                    "fan_out": fo,
                    "line_count": line_count,
                    "has_test_reference": has_test,
                    "churn_commits": commits,
                    "finding_count": finding_count,
                    "in_import_cycle": in_cycle,
                },
            }
        )

    ranked_rows.sort(key=lambda row: (-row["total_score"], row["label"]))
    for position, row in enumerate(ranked_rows[: max(0, top)], 1):
        row["rank"] = position

    return {
        "schema_version": SCHEMA_VERSION,
        "engine_version": ENGINE_VERSION,
        "graph_scope": graph.get("graph_scope"),
        "scope_diagnostics": graph.get("scope_diagnostics"),
        "degraded": bool(graph.get("degraded")),
        "import_cycle_count": len(import_cycles),
        "modules_considered": len(module_nodes),
        "ranked_modules": ranked_rows[: max(0, top)],
    }


def format_ranking_answer(ranking: Dict[str, Any]) -> str:
    """Human-readable summary aligned with Phase 100G bottleneck prose."""
    if ranking.get("degraded"):
        return (
            "Dependency graph degraded — cannot compute architectural risk ranking "
            "on production scope."
        )
    modules = ranking.get("ranked_modules") or []
    if not modules:
        return "No production modules available for architectural risk ranking."

    lines = [
        "Architectural risk ranking (production dependency scope; score breakdown per module):",
    ]
    for item in modules:
        bd = item["score_breakdown"]
        lines.append(
            f"{item['rank']}. {item['label']}: total={item['total_score']} "
            f"(fan-in={bd['fan_in']}, fan-out={bd['fan_out']}, "
            f"cycles={bd['import_cycle_member']}, loc={bd['module_size_loc']}, "
            f"untested={bd['untested_module']}, contract={bd['contract_evidence']})"
        )
    return "\n".join(lines)


def format_ranking_evidence(ranking: Dict[str, Any]) -> List[str]:
    evidence: List[str] = []
    for item in ranking.get("ranked_modules") or []:
        evidence.append(
            f"rank {item['rank']}: {item['label']} total={item['total_score']} "
            f"breakdown={item['score_breakdown']}"
        )
    cycles = ranking.get("import_cycle_count", 0)
    if cycles:
        evidence.append(f"import cycles detected: {cycles}")
    return evidence
