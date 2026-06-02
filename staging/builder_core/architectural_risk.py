"""Architectural risk ranking (Phase 102 / 102B).

Deterministic module-level ranking over the production-scoped dependency graph
(Phase 100G). Consumes depgraph + repository index signals; no LLM.

Phase 102B hardens trust: deduped import edges, canonical cycles, AST-backed
test references, separated evidence channels, LOC gated on blast-radius/safety
gaps, and per-module rank diagnostics.
"""

from __future__ import annotations

import ast
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from . import repository_understanding as ru

SCHEMA_VERSION = 2
ENGINE_VERSION = "phase102b-v1"

# Score weights (frozen for benchmark reproducibility).
WEIGHT_FAN_IN = 1.0
WEIGHT_FAN_OUT = 0.35
WEIGHT_CYCLE_MEMBER = 5.0
WEIGHT_LOC_BLOCK = 500  # +1 score per block, max LOC_SCORE_CAP
LOC_SCORE_CAP = 4.0
WEIGHT_UNTESTED = 3.0
WEIGHT_TEST_EVIDENCE = -1.5  # reduces risk when tests bind (negative component)
WEIGHT_CHURN_BLOCK = 5  # +0.5 per block, max CHURN_SCORE_CAP
CHURN_SCORE_CAP = 3.0
WEIGHT_CONTRACT_EXPLICIT = 1.5
WEIGHT_CONTRACT_INFERRED = 0.75
WEIGHT_CONTRACT_CAP = 4.0
WEIGHT_STATIC_HIGH = 1.25
WEIGHT_STATIC_MEDIUM = 0.75
WEIGHT_STATIC_LOW = 0.35
WEIGHT_STATIC_CAP = 4.0
WEIGHT_SUBSYSTEM_CROSS_FAN_IN = 2.0

# Blast-radius / safety-gap gate for LOC (isolated large files must not dominate).
MIN_FAN_IN_FOR_LOC = 1
MIN_FAN_OUT_FOR_LOC = 2

CONTRACT_FINDING_RULES = frozenset(
    {
        "wrong_return_shape",
        "inconsistent_return",
        "missing_return",
    }
)
STATIC_EXCLUDED_RULES = CONTRACT_FINDING_RULES | frozenset({"missing_test_reference"})

_QUALIFIED_REF_RE_CACHE: Dict[str, re.Pattern[str]] = {}


def _subsystem_name(path: str) -> str:
    parts = path.replace("\\", "/").split("/")
    return parts[0] if len(parts) > 1 else "(root)"


def _module_stem(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0].lower()


def _module_qual(path: str) -> str:
    return path.replace("\\", "/").removesuffix(".py").replace("/", ".")


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


def _canonical_cycle(cycle: Sequence[str]) -> Tuple[str, ...]:
    if not cycle:
        return tuple()
    nodes = list(cycle)
    if len(nodes) > 1 and nodes[0] == nodes[-1]:
        nodes = nodes[:-1]
    if not nodes:
        return tuple(cycle)
    rotations = [tuple(nodes[i:] + nodes[:i]) for i in range(len(nodes))]
    return min(rotations)


def _dedupe_import_edges(
    graph: Dict[str, Any],
) -> Tuple[Dict[str, int], Dict[str, int], Dict[Tuple[str, str], int]]:
    """Count fan-in/out using unique (importer, imported) module pairs."""
    fan_in: Dict[str, int] = {}
    fan_out: Dict[str, int] = {}
    pair_counts: Dict[Tuple[str, str], int] = {}
    seen: Set[Tuple[str, str]] = set()
    for edge in graph.get("edges", []):
        if edge.get("type") != "imports" or not edge.get("resolved"):
            continue
        from_id = edge.get("from", "")
        to_id = edge.get("to", "")
        if not from_id or not to_id:
            continue
        pair = (from_id, to_id)
        if pair in seen:
            continue
        seen.add(pair)
        pair_counts[pair] = pair_counts.get(pair, 0) + 1
        fan_in[to_id] = fan_in.get(to_id, 0) + 1
        fan_out[from_id] = fan_out.get(from_id, 0) + 1
    return fan_in, fan_out, pair_counts


def _canonical_import_cycles(graph: Dict[str, Any]) -> Tuple[Set[str], List[Tuple[str, ...]]]:
    cycle_modules: Set[str] = set()
    canonical: List[Tuple[str, ...]] = []
    seen: Set[Tuple[str, ...]] = set()
    for cycle in graph.get("statistics", {}).get("import_cycles", []):
        key = _canonical_cycle(cycle)
        if not key or key in seen:
            continue
        seen.add(key)
        canonical.append(key)
        cycle_modules.update(key)
    canonical.sort()
    return cycle_modules, canonical


def _subsystem_cross_fan_in(
    graph: Dict[str, Any],
    pair_counts: Dict[Tuple[str, str], int],
) -> Dict[str, int]:
    """Cross-subsystem import fan-in using deduped importer→imported pairs."""
    nodes_by_id = {node["id"]: node for node in graph.get("nodes", [])}
    counts: Dict[str, int] = {}
    seen_pairs: Set[Tuple[str, str, str, str]] = set()
    for (from_id, to_id), _ in sorted(pair_counts.items()):
        from_node = nodes_by_id.get(from_id, {})
        to_node = nodes_by_id.get(to_id, {})
        from_path = from_node.get("path") or ""
        to_path = to_node.get("path") or ""
        if not from_path or not to_path:
            continue
        to_sub = _subsystem_name(to_path)
        from_sub = _subsystem_name(from_path)
        if to_sub == from_sub:
            continue
        key = (from_sub, to_sub, from_id, to_id)
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        counts[to_sub] = counts.get(to_sub, 0) + 1
    return counts


def _test_documents(index: Dict[str, Any]) -> List[Dict[str, str]]:
    """Full test-file text when available (index chunks are often partial)."""
    docs: Dict[str, str] = {}
    project_root = index.get("project_root") or ""
    for entry in index.get("files", []):
        path = entry.get("path") or ""
        if entry.get("category") != "test" and entry.get("role") != "test":
            continue
        if project_root:
            full = os.path.join(project_root, path)
            try:
                with open(full, "r", encoding="utf-8-sig", errors="ignore") as fh:
                    docs[path] = fh.read()
                    continue
            except OSError:
                pass
    chunk_parts: Dict[str, List[str]] = {}
    for chunk in index.get("chunks", []):
        if chunk.get("category") != "test" and chunk.get("role") != "test":
            continue
        path = chunk.get("path")
        if not path or path in docs:
            continue
        chunk_parts.setdefault(path, []).append(chunk.get("text", ""))
    for path, parts in chunk_parts.items():
        docs[path] = "\n".join(parts)
    return [{"path": path, "text": text} for path, text in sorted(docs.items())]


def _import_bindings(tree: ast.AST) -> Dict[str, str]:
    bindings: Dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                target = alias.asname or alias.name.split(".")[0]
                bindings[target] = alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                if alias.name == "*":
                    continue
                target = alias.asname or alias.name
                bindings[target] = f"{module}.{alias.name}" if module else alias.name
    return bindings


def _attribute_chain(node: ast.AST) -> Optional[str]:
    parts: List[str] = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return ".".join(reversed(parts))
    return None


def _qualified_reference_pattern(module_qual: str) -> re.Pattern[str]:
    if module_qual not in _QUALIFIED_REF_RE_CACHE:
        _QUALIFIED_REF_RE_CACHE[module_qual] = re.compile(
            rf"\b{re.escape(module_qual)}\.[A-Za-z_]\w*"
        )
    return _QUALIFIED_REF_RE_CACHE[module_qual]


def _call_resolves_to_module(
    call: ast.Call,
    bindings: Dict[str, str],
    module_qual: str,
) -> bool:
    chain = _attribute_chain(call.func)
    if not chain:
        return False
    root = chain.split(".")[0]
    bound = bindings.get(root, root)
    if bound == module_qual or bound.startswith(module_qual + "."):
        return True
    if chain == module_qual or chain.startswith(module_qual + "."):
        return True
    return False


def _ast_test_reference(
    tree: ast.AST,
    text: str,
    module_qual: str,
) -> List[str]:
    reasons: List[str] = []
    bindings = _import_bindings(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == module_qual or mod.startswith(module_qual + "."):
                reasons.append(f"import-from {mod}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name == module_qual or name.startswith(module_qual + "."):
                    reasons.append(f"import {name}")
        elif isinstance(node, ast.Call) and _call_resolves_to_module(node, bindings, module_qual):
            reasons.append("explicit call")
    if _qualified_reference_pattern(module_qual).search(text):
        if not reasons:
            reasons.append(f"qualified reference to {module_qual}")
    return reasons


def _build_test_reference_index(
    index: Dict[str, Any],
    module_paths: Sequence[str],
) -> Dict[str, List[str]]:
    """Map module path → test-reference reasons (one AST pass per test file)."""
    refs: Dict[str, List[str]] = {path: [] for path in module_paths}
    qual_to_path = {_module_qual(path): path for path in module_paths}
    known_quals = set(qual_to_path)
    for document in _test_documents(index):
        text = document.get("text") or ""
        if not text.strip():
            continue
        try:
            tree = ast.parse(text, filename=document["path"])
        except SyntaxError:
            continue
        candidates: Set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if mod in known_quals:
                    candidates.add(mod)
                else:
                    for qual in known_quals:
                        if mod and mod.startswith(qual + "."):
                            candidates.add(qual)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    if name in known_quals:
                        candidates.add(name)
                    else:
                        for qual in known_quals:
                            if name.startswith(qual + "."):
                                candidates.add(qual)
        for qual in sorted(candidates):
            hits = _ast_test_reference(tree, text, qual)
            if hits:
                refs[qual_to_path[qual]].extend(
                    f"{document['path']}: {hit}" for hit in hits
                )
    return refs


def _test_reference_evidence(
    module_path: str,
    test_index: Dict[str, List[str]],
) -> Tuple[bool, float, List[str]]:
    reasons = list(test_index.get(module_path, []))
    if reasons:
        return True, WEIGHT_TEST_EVIDENCE, reasons
    return False, 0.0, []


def _read_module_source(index: Dict[str, Any], path: str) -> Optional[str]:
    project_root = index.get("project_root")
    if not project_root:
        return None
    full = os.path.join(project_root, path)
    try:
        with open(full, "r", encoding="utf-8-sig", errors="ignore") as fh:
            return fh.read()
    except OSError:
        return None


def _contract_evidence_score(
    index: Dict[str, Any],
    path: str,
    analysis: Optional[Dict[str, Any]],
    *,
    contract_cache: Optional[Dict[str, Tuple[float, int, List[str]]]] = None,
) -> Tuple[float, int, List[str]]:
    if contract_cache is not None and path in contract_cache:
        return contract_cache[path]

    reasons: List[str] = []
    finding_score = 0.0
    finding_count = 0
    contract_rules_hit = False
    for item in list((analysis or {}).get("findings", [])):
        rule = item.get("rule", "")
        if rule not in CONTRACT_FINDING_RULES:
            continue
        contract_rules_hit = True
        finding_count += 1
        severity = item.get("severity", "low")
        if severity == "high":
            finding_score += WEIGHT_CONTRACT_EXPLICIT
        elif severity == "medium":
            finding_score += WEIGHT_CONTRACT_INFERRED
        else:
            finding_score += WEIGHT_CONTRACT_INFERRED * 0.5
        reasons.append(f"contract finding {rule} ({severity})")

    # Only run contract_facts when contract-shaped findings exist (avoid parsing every file).
    if contract_rules_hit:
        text = _read_module_source(index, path)
        if text and not (analysis or {}).get("parse_error"):
            try:
                from .bug_intelligence import contract_facts

                if contract_facts.CONTRACT_FACTS_ENABLED:
                    tree = ast.parse(text, filename=path)
                    module_facts = {"parse_error": ""}
                    payload = contract_facts.extract_module_contracts(module_facts, tree, path)
                    explicit = 0
                    inferred = 0
                    for bucket in (
                        "return_contracts",
                        "argument_contracts",
                        "nullability_contracts",
                        "exception_contracts",
                        "state_mutation_contracts",
                    ):
                        for record in payload.get(bucket) or []:
                            conf = record.get("confidence", "")
                            if conf == contract_facts.CONFIDENCE_EXPLICIT:
                                explicit += 1
                            elif conf in (
                                contract_facts.CONFIDENCE_INFERRED_STRONG,
                                contract_facts.CONFIDENCE_INFERRED_WEAK,
                            ):
                                inferred += 1
                    if explicit:
                        reasons.append(f"contract facts explicit={explicit}")
                    if inferred:
                        reasons.append(f"contract facts inferred={inferred}")
                    finding_score += (
                        explicit * WEIGHT_CONTRACT_EXPLICIT
                        + inferred * WEIGHT_CONTRACT_INFERRED
                    )
                    finding_count += explicit + inferred
            except SyntaxError:
                pass

    score = min(WEIGHT_CONTRACT_CAP, finding_score)
    result = (score, finding_count, reasons)
    if contract_cache is not None:
        contract_cache[path] = result
    return result


def _static_findings_score(analysis: Optional[Dict[str, Any]]) -> Tuple[float, int, List[str]]:
    if not analysis:
        return 0.0, 0, []
    score = 0.0
    count = 0
    reasons: List[str] = []
    for item in analysis.get("findings", []):
        rule = item.get("rule", "")
        if rule in STATIC_EXCLUDED_RULES:
            continue
        count += 1
        severity = item.get("severity", "low")
        if severity == "high":
            score += WEIGHT_STATIC_HIGH
        elif severity == "medium":
            score += WEIGHT_STATIC_MEDIUM
        else:
            score += WEIGHT_STATIC_LOW
        if len(reasons) < 4:
            reasons.append(f"{rule} ({severity})")
    return min(WEIGHT_STATIC_CAP, score), count, reasons


def _loc_score(line_count: int, *, eligible: bool) -> float:
    if not eligible or line_count <= 0:
        return 0.0
    return min(LOC_SCORE_CAP, line_count / WEIGHT_LOC_BLOCK)


def _churn_score(churn: int) -> float:
    if churn <= 0:
        return 0.0
    return min(CHURN_SCORE_CAP, (churn / WEIGHT_CHURN_BLOCK) * 0.5)


def _blast_radius_or_safety_gap(
    *,
    fan_in: int,
    fan_out: int,
    in_cycle: bool,
    has_test_reference: bool,
    subsystem_cross_fan_in: int,
    contract_score: float,
    static_score: float,
) -> bool:
    return bool(
        fan_in >= MIN_FAN_IN_FOR_LOC
        or fan_out >= MIN_FAN_OUT_FOR_LOC
        or in_cycle
        or not has_test_reference
        or subsystem_cross_fan_in >= 2
        or contract_score > 0
        or static_score > 0
    )


def _build_rank_diagnostics(
    *,
    breakdown: Dict[str, float],
    metrics: Dict[str, Any],
    reasons_by_channel: Dict[str, List[str]],
) -> List[str]:
    lines: List[str] = []
    if metrics.get("fan_in"):
        lines.append(
            f"fan-in={metrics['fan_in']} unique importers → +{breakdown['fan_in']}"
        )
    if metrics.get("fan_out"):
        lines.append(
            f"fan-out={metrics['fan_out']} unique imports → +{breakdown['fan_out']}"
        )
    if breakdown.get("import_cycle_member"):
        lines.append(f"import-cycle member → +{breakdown['import_cycle_member']}")
    if breakdown.get("module_size_loc"):
        lines.append(
            f"module size loc={metrics.get('line_count', 0)} (blast-radius/safety gated) "
            f"→ +{breakdown['module_size_loc']}"
        )
    elif metrics.get("line_count", 0) >= WEIGHT_LOC_BLOCK:
        lines.append(
            f"module size loc={metrics['line_count']} suppressed (isolated file, no hub/safety signals)"
        )
    if breakdown.get("untested_module"):
        lines.append(f"no AST test reference → +{breakdown['untested_module']}")
    if breakdown.get("test_evidence"):
        lines.append(f"test reference binds → {breakdown['test_evidence']}")
    if breakdown.get("contract_evidence"):
        lines.append(f"contract evidence → +{breakdown['contract_evidence']}")
    if breakdown.get("static_findings"):
        lines.append(f"static findings → +{breakdown['static_findings']}")
    if breakdown.get("churn_hotspot"):
        lines.append(f"recent churn → +{breakdown['churn_hotspot']}")
    if breakdown.get("subsystem_import_hub"):
        lines.append(f"subsystem import hub → +{breakdown['subsystem_import_hub']}")
    for channel, items in reasons_by_channel.items():
        for item in items[:2]:
            lines.append(f"{channel}: {item}")
    if not lines:
        lines.append("no material risk signals; ranked by tie-break label")
    return lines


def rank_modules(
    index: Dict[str, Any],
    graph: Dict[str, Any],
    *,
    top: int = 12,
) -> Dict[str, Any]:
    """Return structured architectural-risk ranking for production-scoped modules."""
    files_by_path, analysis_by_path, subsystems_by_name = _index_file_maps(index)
    fan_in, fan_out, pair_counts = _dedupe_import_edges(graph)
    cycle_modules, import_cycles = _canonical_import_cycles(graph)
    subsystem_fan_in = _subsystem_cross_fan_in(graph, pair_counts)
    churn_map = dict(index.get("churn") or {})

    module_nodes = [n for n in graph.get("nodes", []) if n.get("type") == "module"]
    module_paths = [n.get("path") or "" for n in module_nodes if n.get("path")]
    test_index = _build_test_reference_index(index, module_paths)
    contract_cache: Dict[str, Tuple[float, int, List[str]]] = {}
    ranked_rows: List[Dict[str, Any]] = []

    for node in module_nodes:
        module_id = node["id"]
        path = node.get("path") or ""
        label = node.get("dotted") or path or module_id
        subsystem = _subsystem_name(path)
        file_meta = files_by_path.get(path, {})
        analysis = analysis_by_path.get(path)
        role = file_meta.get("role") or ru.classify_file_role(
            path, ".py", project_root=index.get("project_root")
        )
        line_count = int(node.get("line_count") or file_meta.get("lines") or 0)
        commits = int(churn_map.get(path, 0))

        fi = fan_in.get(module_id, 0)
        fo = fan_out.get(module_id, 0)
        in_cycle = module_id in cycle_modules
        has_test, test_component, test_reasons = _test_reference_evidence(path, test_index)
        contract_score, contract_count, contract_reasons = _contract_evidence_score(
            index, path, analysis, contract_cache=contract_cache
        )
        static_score, static_count, static_reasons = _static_findings_score(analysis)
        loc_eligible = _blast_radius_or_safety_gap(
            fan_in=fi,
            fan_out=fo,
            in_cycle=in_cycle,
            has_test_reference=has_test,
            subsystem_cross_fan_in=subsystem_fan_in.get(subsystem, 0),
            contract_score=contract_score,
            static_score=static_score,
        )
        loc_component = _loc_score(line_count, eligible=loc_eligible)
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
            "module_size_loc": round(loc_component, 2),
            "untested_module": round(untested_component, 2),
            "test_evidence": round(test_component, 2),
            "churn_hotspot": round(churn_component, 2),
            "contract_evidence": round(contract_score, 2),
            "static_findings": round(static_score, 2),
            "subsystem_import_hub": round(subsystem_component, 2),
        }
        total = round(sum(breakdown.values()), 2)

        reasons_by_channel = {
            "test": test_reasons,
            "contract": contract_reasons,
            "static": static_reasons,
        }
        diagnostics = _build_rank_diagnostics(
            breakdown=breakdown,
            metrics={
                "fan_in": fi,
                "fan_out": fo,
                "line_count": line_count,
            },
            reasons_by_channel=reasons_by_channel,
        )

        signals: List[str] = []
        if fi:
            signals.append(f"import fan-in={fi} (deduped importers)")
        if fo:
            signals.append(f"import fan-out={fo} (deduped targets)")
        if in_cycle:
            signals.append("import-cycle member")
        if line_count and loc_component:
            signals.append(f"loc={line_count} (gated)")
        elif line_count and not loc_eligible:
            signals.append(f"loc={line_count} (suppressed-isolated)")
        if not has_test:
            signals.append("no AST test import/call reference")
        else:
            signals.append("test reference binds")
        if contract_count:
            signals.append(f"contract evidence items={contract_count}")
        if static_count:
            signals.append(f"static findings={static_count}")
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
                "rank_diagnostics": diagnostics,
                "signals": signals,
                "metrics": {
                    "fan_in": fi,
                    "fan_out": fo,
                    "line_count": line_count,
                    "has_test_reference": has_test,
                    "churn_commits": commits,
                    "contract_evidence_count": contract_count,
                    "static_finding_count": static_count,
                    "in_import_cycle": in_cycle,
                    "loc_risk_eligible": loc_eligible,
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
        "import_cycles_canonical": [list(cycle) for cycle in import_cycles],
        "deduped_import_pairs": len(pair_counts),
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
            f"untested={bd['untested_module']}, test={bd['test_evidence']}, "
            f"contract={bd['contract_evidence']}, static={bd['static_findings']})"
        )
    return "\n".join(lines)


def format_ranking_evidence(ranking: Dict[str, Any]) -> List[str]:
    evidence: List[str] = []
    for item in ranking.get("ranked_modules") or []:
        evidence.append(
            f"rank {item['rank']}: {item['label']} total={item['total_score']} "
            f"breakdown={item['score_breakdown']}"
        )
        for line in item.get("rank_diagnostics") or []:
            evidence.append(f"  {line}")
    cycles = ranking.get("import_cycle_count", 0)
    if cycles:
        evidence.append(f"import cycles detected (canonical): {cycles}")
    pairs = ranking.get("deduped_import_pairs")
    if pairs is not None:
        evidence.append(f"deduped import pairs: {pairs}")
    return evidence
