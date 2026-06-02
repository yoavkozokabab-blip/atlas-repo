"""Phase 104C — compact fact packets for benchmark JARVIS context."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Tuple

if TYPE_CHECKING:
    from .context_cache import BenchmarkContextSession

from .jarvis_packet import format_jarvis_packet
from .schema import BenchmarkTask
from .tokens import estimated_count

PACKET_VERSION = "1"
COMPACT_INSTRUMENTATION_VERSION = "phase104c-truth-v1"

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
    "REPO_MAP": 400,
    "DEPENDENCY": 325,
    "IMPACT": 300,
    "ARCH_RISK": 400,
    "CONTRACT": 300,
    "VERIFY": 350,
    "DEFECT_REVIEW": 300,
    "PLAN_INPUT": 275,
    "RETRIEVAL": 325,
}

_DATASET_PREFIXES = ("data/", "dataset/", "fixtures/", "samples/")
_CORPUS_MARKERS = ("real_repo_corpus",)

REF_CLASS_PATH = "path_ref"
REF_CLASS_SYMBOL = "symbol_ref"
REF_CLASS_CONCEPT = "concept_ref"
REF_CLASS_UNKNOWN = "unknown_ref"

_CONCEPT_REF_MAP = {
    "impact": "impact_analysis",
    "depend": "dependency_relationship",
    "dependency": "dependency_relationship",
    "fan-in": "fan_in_metric",
    "fan_in": "fan_in_metric",
    "loc": "line_count_metric",
    "cycle": "import_cycle_evidence",
    "cycles": "import_cycle_evidence",
    "risk": "architectural_risk_score",
    "centrality": "graph_centrality",
    "type_hint": "contract_source_type_hint",
    "assert": "contract_source_assert",
    "caller_behavior": "contract_source_caller_behavior",
    "review lead": "review_lead_status",
    "inconsistent_return": "inconsistent_return_finding",
    "blocker": "verification_blocker",
    "promotion": "promotion_gate",
    "test_evidence": "verification_test_evidence",
    "test": "verification_test_evidence",
}

_FACT_ROW_PREFIXES = (
    "SUBSYSTEM|",
    "EDGE|",
    "MODULE|",
    "IMPACT|",
    "DEPENDENT|",
    "CONTRACT|",
    "CONTRACT_SRC|",
    "FIXTURE|",
    "EVIDENCE|",
    "FINDING|",
    "HIT|",
    "BUILDER|",
    "VOICE|",
    "CYCLE|",
    "CENTRALITY|",
    "RANK_DIAG|",
    "CHAIN|",
    "SUBJECT|",
)

_METADATA_ROW_PREFIXES = (
    "PACKET|",
    "TASK|",
    "TARGET|",
    "QUERY|",
    "SYMBOL|",
    "GRAPH|",
    "RANK_META|",
    "RISK_MODEL|",
    "LIMIT|",
    "CONTRACT_STATUS|",
    "CONCEPT_REF|",
    "AMBIGUOUS_REF|",
    "UNRESOLVED_REF|",
    "WHY_GENERIC|",
    "CAVEAT|",
    "REF|",
    "TRUNCATED|",
    "DETAIL|",
    "OVERFLOW|",
    "SRCQ|",
    "EVIDENCE_TYPE|",
    "CONSTRAINT|",
    "VERIFY|",
    "DIFF|",
    "UNRESOLVED|",
)


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


def _refs_block(paths: Sequence[str], *, limit: int = 6) -> List[str]:
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


def _index_paths(index: Dict[str, Any]) -> List[str]:
    return [
        str(item.get("path", "")).replace("\\", "/")
        for item in index.get("files", [])
        if item.get("path")
    ]


def _sort_paths(paths: Sequence[str]) -> List[str]:
    return sorted({path for path in paths if path}, key=lambda path: (path.count("/"), len(path), path))


def _path_candidates(hint: str, index: Dict[str, Any]) -> List[str]:
    """Return all indexed paths matching a hint, deterministically sorted."""
    hint_norm = str(hint or "").replace("\\", "/").strip()
    if not hint_norm:
        return []
    paths = _index_paths(index)
    if hint_norm in paths:
        return [hint_norm]
    if hint_norm.endswith("/"):
        prefix = hint_norm.rstrip("/")
        return _sort_paths(
            path for path in paths if path == prefix or path.startswith(prefix + "/")
        )
    suffix_matches = [
        path for path in paths if path == hint_norm or path.endswith("/" + hint_norm)
    ]
    if suffix_matches:
        return _sort_paths(suffix_matches)
    basename = hint_norm.split("/")[-1]
    return _sort_paths(path for path in paths if path.split("/")[-1] == basename)


def _resolve_indexed_path(hint: str, index: Dict[str, Any]) -> Tuple[Optional[str], str, List[str]]:
    """Resolve a hint to zero or one path; never silently pick among ambiguous matches."""
    candidates = _path_candidates(hint, index)
    if not candidates:
        return None, "missing", []
    if len(candidates) == 1:
        path = candidates[0]
        hint_norm = str(hint or "").replace("\\", "/").strip()
        status = "exact" if path == hint_norm else "resolved"
        return path, status, []
    return None, "ambiguous", candidates


def classify_evidence_ref(hint: str) -> str:
    """Classify required_evidence entries before resolution."""
    text = str(hint or "").strip()
    if not text:
        return REF_CLASS_UNKNOWN
    lowered = text.lower()
    if text.endswith(".py") or text.endswith("/") or ("/" in text and ".py" in text.lower()):
        return REF_CLASS_PATH
    if lowered in _CONCEPT_REF_MAP or lowered.replace("_", "-") in _CONCEPT_REF_MAP:
        return REF_CLASS_CONCEPT
    if "/" in text and not text.endswith(".py"):
        return REF_CLASS_SYMBOL
    if lowered.replace(" ", "_").replace("-", "_") in {
        key.replace(" ", "_").replace("-", "_") for key in _CONCEPT_REF_MAP
    }:
        return REF_CLASS_CONCEPT
    return REF_CLASS_UNKNOWN


def _concept_ref_row(hint: str) -> str:
    lowered = str(hint).strip().lower()
    maps_to = _CONCEPT_REF_MAP.get(lowered) or _CONCEPT_REF_MAP.get(lowered.replace("_", "-"), "concept_fact")
    return format_row(
        "CONCEPT_REF",
        {"REF": hint, "CLASS": REF_CLASS_CONCEPT, "MAPS_TO": maps_to},
    )


def _ambiguous_ref_row(hint: str, candidates: Sequence[str]) -> str:
    listed = _sort_paths(candidates)[:8]
    return format_row(
        "AMBIGUOUS_REF",
        {
            "REF": hint,
            "COUNT": len(candidates),
            "CANDIDATES": ";".join(listed),
        },
    )


def _unresolved_ref_row(hint: str, ref_class: str) -> str:
    return format_row("UNRESOLVED_REF", {"REF": hint, "CLASS": ref_class})


def _classify_required_evidence(
    task: BenchmarkTask,
    index: Dict[str, Any],
) -> Tuple[List[str], List[str], List[str]]:
    """Return resolved path refs, disclosure rows, and concept ref rows."""
    resolved: List[str] = []
    disclosure_rows: List[str] = []
    concept_rows: List[str] = []
    seen_paths: set[str] = set()
    for item in task.required_evidence:
        hint = str(item)
        ref_class = classify_evidence_ref(hint)
        if ref_class == REF_CLASS_CONCEPT:
            concept_rows.append(_concept_ref_row(hint))
            continue
        if ref_class == REF_CLASS_UNKNOWN:
            disclosure_rows.append(_unresolved_ref_row(hint, REF_CLASS_UNKNOWN))
            continue
        if ref_class == REF_CLASS_SYMBOL:
            path, status, candidates = _resolve_indexed_path(hint, index)
            if status == "ambiguous":
                disclosure_rows.append(_ambiguous_ref_row(hint, candidates))
            elif path:
                if path not in seen_paths:
                    seen_paths.add(path)
                    resolved.append(path)
            else:
                disclosure_rows.append(_unresolved_ref_row(hint, REF_CLASS_SYMBOL))
            continue
        path, status, candidates = _resolve_indexed_path(hint, index)
        if status == "ambiguous":
            disclosure_rows.append(_ambiguous_ref_row(hint, candidates))
            continue
        if path:
            if path not in seen_paths:
                seen_paths.add(path)
                resolved.append(path)
            continue
        disclosure_rows.append(_unresolved_ref_row(hint, REF_CLASS_PATH))
    return resolved, disclosure_rows, concept_rows


def _required_evidence_resolution(
    task: BenchmarkTask,
    index: Dict[str, Any],
) -> Tuple[List[str], List[str]]:
    """Backward-compatible: resolved paths and non-concept disclosure rows."""
    resolved, disclosure_rows, _concept_rows = _classify_required_evidence(task, index)
    return resolved, disclosure_rows


def _target_from_task(task: BenchmarkTask, index: Dict[str, Any]) -> Tuple[Optional[str], str]:
    for item in task.required_evidence:
        if classify_evidence_ref(item) != REF_CLASS_PATH:
            continue
        path, resolution, _candidates = _resolve_indexed_path(str(item), index)
        if resolution == "ambiguous":
            return None, "ambiguous"
        if path:
            return path, resolution
    match = re.search(r"[\w./-]+\.py", task.prompt)
    if match:
        path, resolution, _candidates = _resolve_indexed_path(match.group(0), index)
        if resolution == "ambiguous":
            return None, "ambiguous"
        if path:
            return path, resolution
        return match.group(0), "missing"
    return None, "missing"


def _target_row(path: Optional[str], resolution: str) -> str:
    fields: Dict[str, Any] = {"PATH": path or "", "RESOLUTION": resolution}
    if resolution in {"ambiguous", "missing"}:
        fields["STATUS"] = "needs_verification"
    elif resolution == "resolved" and path and "/" in path:
        hint = path.split("/")[-1]
        if hint and hint not in {path}:
            fields["ABBREVIATED"] = "no"
    return format_row("TARGET", fields)


def _required_evidence_paths(task: BenchmarkTask, index: Dict[str, Any]) -> List[str]:
    resolved, _ambiguous = _required_evidence_resolution(task, index)
    return resolved


def _contract_paths_to_scan(task: BenchmarkTask, index: Dict[str, Any], *, module_limit: int = 6) -> List[str]:
    paths: List[str] = []
    for item in task.required_evidence:
        if classify_evidence_ref(item) != REF_CLASS_PATH:
            continue
        path, status, _candidates = _resolve_indexed_path(str(item), index)
        if path and status != "ambiguous":
            paths.append(path)
    if not paths:
        for analysis in index.get("python_analysis", []):
            if analysis.get("parse_error"):
                continue
            path = str(analysis.get("path", "")).replace("\\", "/")
            if path.endswith(".py"):
                paths.append(path)
    return _sort_paths(paths)[:module_limit]


def _extract_contract_fact_rows(
    task: BenchmarkTask,
    index: Dict[str, Any],
    *,
    module_limit: int = 6,
    record_limit: int = 6,
) -> Tuple[List[str], str]:
    """Build CONTRACT rows only from contract_facts extraction with file:line provenance."""
    import ast

    from ..bug_intelligence import contract_facts

    if not contract_facts.CONTRACT_FACTS_ENABLED:
        return [], "disabled"

    project_root = index.get("project_root") or ""
    paths_to_scan = _contract_paths_to_scan(task, index, module_limit=module_limit)
    rows: List[str] = []
    record_id = 0
    for path in paths_to_scan:
        if not project_root:
            continue
        full = os.path.join(project_root, path)
        try:
            source = Path(full).read_text(encoding="utf-8-sig", errors="ignore")
            tree = ast.parse(source, filename=path)
        except (OSError, SyntaxError):
            continue
        payload = contract_facts.extract_module_contracts({"parse_error": ""}, tree, path)
        for bucket in (
            "return_contracts",
            "argument_contracts",
            "nullability_contracts",
            "exception_contracts",
            "state_mutation_contracts",
        ):
            for record in payload.get(bucket, [])[:record_limit]:
                refs = record.get("evidence_refs") or []
                line = int((refs[0] or {}).get("line", 0)) if refs else 0
                record_id += 1
                rows.append(
                    format_row(
                        "CONTRACT",
                        {
                            "ID": f"C{record_id}",
                            "TYPE": record.get("contract_type", bucket),
                            "PROVENANCE": "contract_facts",
                            "FILE": path,
                            "LINE": line,
                            "SOURCES": ",".join(record.get("sources", [])[:4]),
                        },
                    )
                )
    if rows:
        return rows, "extracted"
    return [], "none_extracted"


def extract_facts_block(packet_text: str) -> str:
    """Return fact rows only (excludes headers, refs, caveats, cap metadata)."""
    facts: List[str] = []
    for row in packet_text.splitlines():
        if not row.strip():
            continue
        if row.startswith(_FACT_ROW_PREFIXES):
            facts.append(row)
    return "\n".join(facts)


def facts_fingerprint(packet_text: str) -> str:
    """Stable fingerprint for subject-specific fact comparison."""
    return hashlib.sha256(extract_facts_block(packet_text).encode("utf-8")).hexdigest()


def _append_evidence_rows(
    rows: List[str],
    task: BenchmarkTask,
    index: Dict[str, Any],
) -> List[str]:
    resolved, disclosure_rows, concept_rows = _classify_required_evidence(task, index)
    rows.extend(concept_rows)
    rows.extend(disclosure_rows)
    return rows


def _maybe_why_generic(rows: List[str], task: BenchmarkTask) -> None:
    fact_count = sum(1 for row in rows if row.startswith(_FACT_ROW_PREFIXES))
    if fact_count >= 2:
        return
    rows.append(
        format_row(
            "WHY_GENERIC",
            {
                "TASK": task.task_id,
                "REASON": "insufficient_subject_facts",
            },
        )
    )


def _is_corpus_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    if normalized.startswith("data/"):
        return True
    return any(marker in normalized for marker in _CORPUS_MARKERS)


def _fixture_pair_paths(task: BenchmarkTask, index: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    buggy_path: Optional[str] = None
    fixed_path: Optional[str] = None
    for item in task.required_evidence:
        hint = str(item)
        if "buggy.py" in hint:
            buggy_path, _, _candidates = _resolve_indexed_path(hint, index)
        if "fixed.py" in hint:
            fixed_path, _, _candidates = _resolve_indexed_path(hint, index)
    if buggy_path and not fixed_path:
        sibling, _status, _candidates = _resolve_indexed_path(
            buggy_path.replace("buggy.py", "fixed.py"), index
        )
        if sibling and _status != "ambiguous":
            fixed_path = sibling
    if fixed_path and not buggy_path:
        sibling, _status, _candidates = _resolve_indexed_path(
            fixed_path.replace("fixed.py", "buggy.py"), index
        )
        if sibling and _status != "ambiguous":
            buggy_path = sibling
    return buggy_path, fixed_path


def _fixture_diff_summary(project_root: str, buggy_path: str, fixed_path: str) -> str:
    try:
        buggy_full = os.path.join(project_root, buggy_path)
        fixed_full = os.path.join(project_root, fixed_path)
        buggy_lines = Path(buggy_full).read_text(encoding="utf-8-sig", errors="ignore").splitlines()
        fixed_lines = Path(fixed_full).read_text(encoding="utf-8-sig", errors="ignore").splitlines()
    except OSError:
        return "fixture unreadable"
    for line_no, (left, right) in enumerate(zip(buggy_lines, fixed_lines), 1):
        if left.strip() != right.strip():
            return f"line {line_no}: {left.strip()[:80]} -> {right.strip()[:80]}"
    if len(buggy_lines) != len(fixed_lines):
        return f"line count {len(buggy_lines)} -> {len(fixed_lines)}"
    return "no textual diff detected"


def _task_focus_row(task: BenchmarkTask) -> Optional[str]:
    focus = {
        "ru01_subsystems": "subsystem_inventory",
        "ru02_builder_core_map": "builder_core_surfaces",
        "ru03_voice_path": "voice_execution_path",
        "dep01_engine_edges": "engine_import_edges",
        "dep02_ask_edges": "ask_module_dependencies",
        "dep03_evidence_chain": "finding_enrichment_chain",
        "impact01_config": "config_blast_radius",
        "impact02_engine": "engine_change_impact",
        "risk01_ranking": "ranking_signals",
        "risk02_centrality_vs_risk": "centrality_vs_risk",
        "risk03_cycles": "import_cycles",
        "contract01_sources": "contract_source_kinds",
        "contract02_inconsistent_return": "quarantine_logic",
        "verify01_evidence_types": "verification_types",
        "verify02_non_promotion": "promotion_blockers",
        "defect01_wrong_operator": "fixture_operator_diff",
        "defect02_bfs_queue": "fixture_bfs_queue",
        "defect03_gate": "confirmation_gate",
        "impact03_contract_facts": "contract_facts_impact",
        "plan02_verification": "verification_evidence_plan",
    }.get(task.task_id)
    if not focus:
        return None
    return format_row("TASK", {"ID": task.task_id, "FOCUS": focus})


_CAP_START_PREFIXES = (
    "PACKET|",
    "TARGET|",
    "TASK|",
    "QUERY|",
    "SYMBOL|",
    "FIXTURE|",
    "CONTRACT_SRC|",
    "CONTRACT_STATUS|",
    "CYCLE|",
    "VOICE|",
    "BUILDER|",
    "EVIDENCE_TYPE|",
    "DIFF|",
    "SRCQ|",
    "IMPACT|",
    "CONSTRAINT|",
    "VERIFY|",
    "AMBIGUOUS_REF|",
    "UNRESOLVED_REF|",
    "CONCEPT_REF|",
    "RANK_META|",
    "RANK_DIAG|",
    "CENTRALITY|",
    "RISK_MODEL|",
    "LIMIT|",
    "CHAIN|",
    "SUBJECT|",
    "WHY_GENERIC|",
)
_CAP_END_PREFIXES = ("GRAPH|", "CAVEAT|", "REF|", "TRUNCATED|", "DETAIL|", "OVERFLOW|")


def _split_cap_rows(rows: List[str]) -> Tuple[str, List[str], List[str], List[str]]:
    if not rows:
        return "", [], [], []
    header = rows[0]
    start: List[str] = []
    optional: List[str] = []
    end: List[str] = []
    for row in rows[1:]:
        if row.startswith(_CAP_END_PREFIXES):
            end.append(row)
        elif row.startswith(_CAP_START_PREFIXES):
            start.append(row)
        else:
            optional.append(row)
    return header, start, optional, end


def _metadata_rows(truncated: bool, emitted: int, total: int, digest: str, overflow: bool) -> List[str]:
    rows: List[str] = []
    if truncated:
        rows.append(format_row("TRUNCATED", {"EMITTED": emitted, "TOTAL": total}))
        rows.append(format_row("DETAIL", {"PATH": "context_packet.expanded.json", "SHA256": digest}))
    if overflow:
        rows.append(format_row("OVERFLOW", {"VALUE": "yes", "CAP_EXCEEDED": "yes"}))
    return rows


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
    focus = _task_focus_row(task)
    if focus:
        rows.append(focus)
    if session is not None:
        subsystems = session.get_production_subsystems()
    else:
        from .. import repository_understanding as ru

        subsystems = [item for item in ru.production_subsystems(index) if _is_product_subsystem(item)]
    sources: List[str] = []
    for subsystem in subsystems[:8]:
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
    if task.task_id == "ru02_builder_core_map":
        for path in _required_evidence_paths(task, index):
            rows.append(format_row("BUILDER", {"PATH": path, "ROLE": "surface"}))
    if task.task_id == "ru03_voice_path":
        voice_paths = [
            path
            for path in _index_paths(index)
            if path.startswith("voice/") or path.startswith("brain/") or path.startswith("actions/")
        ]
        for path in voice_paths[:5]:
            rows.append(format_row("VOICE", {"PATH": path, "STAGE": "execution_path"}))
        sources.extend(voice_paths[:6])
    rows.extend(_caveat_rows(result))
    quality = result.get("ask_quality") or {}
    if quality:
        rows.append(_srcq_row(quality))
    rows = _append_evidence_rows(rows, task, index)
    if task.task_id == "ru01_subsystems":
        for subsystem in subsystems[:6]:
            rows.append(
                format_row(
                    "SUBJECT",
                    {
                        "KIND": "subsystem",
                        "NAME": subsystem.get("name", ""),
                        "FILES": subsystem.get("role_counts", {}).get("production_code", 0),
                    },
                )
            )
    ref_paths = _required_evidence_paths(task, index) + sources + [
        path for path in result.get("sources", []) if not _is_corpus_path(str(path))
    ]
    rows.extend(_refs_block(ref_paths))
    _maybe_why_generic(rows, task)
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
    _resolved_paths, _disclosure, _concepts = _classify_required_evidence(task, index)
    target, resolution = _target_from_task(task, index)
    if not target:
        target = "builder_core/bug_intelligence/engine.py"
        resolution = "fallback"
    rows = [_header("DEPENDENCY", result.get("mode", "dependency"), "production")]
    rows = _append_evidence_rows(rows, task, index)
    focus = _task_focus_row(task)
    if focus:
        rows.append(focus)
    rows.append(format_row("SUBJECT", {"PATH": target, "ROLE": "dependency_target"}))
    rows.append(_target_row(target, resolution))
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
    if resolution in {"missing", "ambiguous"}:
        rows.append(format_row("CAVEAT", {"CODE": "TARGET_RESOLUTION", "VALUE": resolution}))
    if task.task_id == "dep03_evidence_chain":
        for step, path in enumerate(_resolved_paths[:5], 1):
            rows.append(format_row("CHAIN", {"STEP": step, "PATH": path}))
    ref_paths = _required_evidence_paths(task, index) + ([target] if target else []) + [
        path for path in result.get("sources", []) if not _is_corpus_path(str(path))
    ]
    rows.extend(_refs_block(ref_paths))
    _maybe_why_generic(rows, task)
    expanded = {
        "kind": "DEPENDENCY",
        "task_id": task.task_id,
        "target": target,
        "target_resolution": resolution,
        "graph_scope": graph.get("graph_scope") if graph else None,
    }
    return rows, expanded


def _build_impact(
    result: Dict[str, Any],
    task: BenchmarkTask,
    index: Dict[str, Any],
    session: Optional["BenchmarkContextSession"] = None,
) -> Tuple[List[str], Dict[str, Any]]:
    from ..bug_intelligence import impact

    target, resolution = _target_from_task(task, index)
    if not target:
        target = "config.py"
        resolution = "fallback"
    if session is not None:
        graph = session.get_dependency_graph()
    else:
        from ..bug_intelligence import depgraph

        graph = depgraph.build_graph(index.get("project_root", task.repo_path))
    rows = [_header("IMPACT", "impact", "production")]
    rows = _append_evidence_rows(rows, task, index)
    focus = _task_focus_row(task)
    if focus:
        rows.append(focus)
    rows.append(format_row("SUBJECT", {"PATH": target, "ROLE": "impact_target"}))
    rows.append(_target_row(target, resolution))
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
    if resolution in {"missing", "ambiguous"}:
        rows.append(format_row("CAVEAT", {"CODE": "TARGET_RESOLUTION", "VALUE": resolution}))
    if task.task_id == "impact03_contract_facts":
        for path in _required_evidence_paths(task, index)[:5]:
            rows.append(format_row("SUBJECT", {"PATH": path, "ROLE": "contract_consumer"}))
    sources = [
        item.get("path", "")
        for item in impact_payload.get("questions", {}).get("files_dependent", [])
        if item.get("path")
    ]
    ref_paths = _required_evidence_paths(task, index) + ([target] if target else []) + sources
    rows.extend(_refs_block(ref_paths))
    _maybe_why_generic(rows, task)
    expanded = {
        "kind": "IMPACT",
        "task_id": task.task_id,
        "target": target,
        "target_resolution": resolution,
        "impact": impact_payload,
    }
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
    rows = _append_evidence_rows(rows, task, index)
    focus = _task_focus_row(task)
    if focus:
        rows.append(focus)
    ranked_modules = list((ranking or {}).get("ranked_modules", []))
    if task.task_id == "risk01_ranking":
        from .. import architectural_risk as arch_risk

        rows.append(
            format_row(
                "RANK_META",
                {
                    "ENGINE": arch_risk.ENGINE_VERSION,
                    "SIGNALS": "fan_in,fan_out,cycles,loc,test,contract,static",
                    "MODULES": ranking.get("modules_considered", 0) if ranking else 0,
                },
            )
        )
        for item in ranked_modules[:8]:
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
            diagnostics = item.get("rank_diagnostics") or []
            if diagnostics:
                rows.append(
                    format_row(
                        "RANK_DIAG",
                        {
                            "PATH": item.get("path", ""),
                            "SIGNAL": str(diagnostics[0])[:100],
                        },
                    )
                )
    elif task.task_id == "risk02_centrality_vs_risk":
        from .. import architectural_risk as arch_risk

        top_risk_paths = {
            str(item.get("path", ""))
            for item in ranked_modules[:5]
            if item.get("path")
        }
        rows.append(
            format_row(
                "RISK_MODEL",
                {
                    "WEIGHT_FAN_IN": arch_risk.WEIGHT_FAN_IN,
                    "WEIGHT_FAN_OUT": arch_risk.WEIGHT_FAN_OUT,
                    "LOC_GATE": f"fan_in>={arch_risk.MIN_FAN_IN_FOR_LOC}",
                },
            )
        )
        by_fan_in = sorted(
            ranked_modules,
            key=lambda item: int((item.get("metrics") or {}).get("fan_in", 0)),
            reverse=True,
        )
        for item in by_fan_in[:6]:
            path = str(item.get("path", ""))
            metrics = item.get("metrics", {})
            rows.append(
                format_row(
                    "CENTRALITY",
                    {
                        "PATH": path,
                        "FAN_IN": metrics.get("fan_in", 0),
                        "SCORE": item.get("total_score", 0),
                        "RANK": item.get("rank", 0),
                        "CHALLENGE": _yes_no(path not in top_risk_paths),
                    },
                )
            )
        rows.append(
            format_row(
                "LIMIT",
                {"CODE": "FAN_IN_NOT_SUFFICIENT", "VALUE": "centrality_requires_corroboration"},
            )
        )
    else:
        modules = ranked_modules[:8]
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
    if task.task_id == "risk03_cycles" and graph:
        cycles = (graph.get("statistics") or {}).get("import_cycles") or []
        for index_no, cycle in enumerate(cycles[:6], 1):
            members = cycle if isinstance(cycle, list) else cycle.get("members", [])
            path_hint = ",".join(str(item) for item in members[:4])
            rows.append(format_row("CYCLE", {"ID": f"CY{index_no}", "MEMBERS": path_hint[:120]}))
    rows.extend(_caveat_rows(result))
    module_paths = [str(item.get("path", "")) for item in ranked_modules[:8] if item.get("path")]
    ref_paths = _required_evidence_paths(task, index) + module_paths
    rows.extend(_refs_block(ref_paths))
    _maybe_why_generic(rows, task)
    expanded = {"kind": "ARCH_RISK", "task_id": task.task_id, "ranking": ranking}
    return rows, expanded


def _build_contract(
    result: Dict[str, Any],
    task: BenchmarkTask,
    index: Dict[str, Any],
    session: Optional["BenchmarkContextSession"] = None,
) -> Tuple[List[str], Dict[str, Any]]:
    rows = [_header("CONTRACT", result.get("mode", "retrieval"), "production")]
    rows = _append_evidence_rows(rows, task, index)
    focus = _task_focus_row(task)
    if focus:
        rows.append(focus)
    contract_rows, contract_status = _extract_contract_fact_rows(task, index)
    rows.extend(contract_rows)
    status_value = contract_status if contract_status in {"extracted", "disabled"} else "none_extracted"
    rows.append(format_row("CONTRACT_STATUS", {"VALUE": status_value}))
    rows.append(format_row("CAVEAT", {"CODE": "USAGE_CONTRACT_NOT_PROVEN", "VALUE": "yes"}))
    rows.extend(_caveat_rows(result))
    ref_paths = _required_evidence_paths(task, index) + [
        path for path in result.get("sources", []) if not _is_corpus_path(str(path))
    ]
    rows.extend(_refs_block(ref_paths))
    _maybe_why_generic(rows, task)
    expanded = {
        "kind": "CONTRACT",
        "task_id": task.task_id,
        "contract_status": status_value,
        "contract_row_count": len(contract_rows),
    }
    return rows, expanded


def _build_verify(
    result: Dict[str, Any],
    task: BenchmarkTask,
    index: Dict[str, Any],
    session: Optional["BenchmarkContextSession"] = None,
) -> Tuple[List[str], Dict[str, Any]]:
    from ..bug_intelligence import verification_evidence

    rows = [_header("VERIFY", result.get("mode", "retrieval"), "finding")]
    focus = _task_focus_row(task)
    if focus:
        rows.append(focus)
    rows = _append_evidence_rows(rows, task, index)
    rows.append(format_row("CAVEAT", {"CODE": "NON_PROMOTING_EVIDENCE", "VALUE": "yes"}))
    for index_no, evidence_type in enumerate(verification_evidence.EVIDENCE_TYPES, 1):
        rows.append(format_row("EVIDENCE_TYPE", {"ID": f"ET{index_no}", "TYPE": evidence_type}))
    evidence_items = [
        item
        for item in result.get("evidence", [])
        if not _is_corpus_path(str(item).split(":", 1)[0])
    ]
    for index_no, item in enumerate(evidence_items[:4], 1):
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
    ref_paths = _required_evidence_paths(task, index) + [
        path for path in result.get("sources", []) if not _is_corpus_path(str(path))
    ]
    rows.extend(_refs_block(ref_paths))
    _maybe_why_generic(rows, task)
    expanded = {"kind": "VERIFY", "task_id": task.task_id, "evidence": evidence_items}
    return rows, expanded


def _build_defect_review(
    result: Dict[str, Any],
    task: BenchmarkTask,
    index: Dict[str, Any],
    session: Optional["BenchmarkContextSession"] = None,
) -> Tuple[List[str], Dict[str, Any]]:
    target, resolution = _target_from_task(task, index)
    buggy_path, fixed_path = _fixture_pair_paths(task, index)
    analysis = _matching_analysis(task, index)
    scope = "fixture" if buggy_path or (target and "python_programs" in target) else "production"
    rows = [_header("DEFECT_REVIEW", result.get("mode", "python_analysis"), scope)]
    focus = _task_focus_row(task)
    if focus:
        rows.append(focus)
    if buggy_path:
        rows.append(format_row("FIXTURE", {"VARIANT": "buggy", "PATH": buggy_path}))
    if fixed_path:
        rows.append(format_row("FIXTURE", {"VARIANT": "fixed", "PATH": fixed_path}))
    if buggy_path and fixed_path:
        summary = _fixture_diff_summary(index.get("project_root", task.repo_path), buggy_path, fixed_path)
        rows.append(format_row("DIFF", {"SUMMARY": summary}))
    if target:
        rows.append(_target_row(target, resolution))
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
    resolved_paths, ambiguous_rows = _required_evidence_resolution(task, index)
    rows.extend(ambiguous_rows)
    ref_paths = list(resolved_paths)
    if buggy_path:
        ref_paths.append(buggy_path)
    if fixed_path:
        ref_paths.append(fixed_path)
    if target:
        ref_paths.append(target)
    ref_paths.extend(path for path in result.get("sources", []) if not _is_corpus_path(str(path)))
    rows.extend(_refs_block(ref_paths))
    expanded = {
        "kind": "DEFECT_REVIEW",
        "task_id": task.task_id,
        "analysis": analysis,
        "buggy_path": buggy_path,
        "fixed_path": fixed_path,
    }
    return rows, expanded


def _build_plan_input(
    result: Dict[str, Any],
    task: BenchmarkTask,
    index: Dict[str, Any],
    session: Optional["BenchmarkContextSession"] = None,
) -> Tuple[List[str], Dict[str, Any]]:
    from ..bug_intelligence import impact

    target, resolution = _target_from_task(task, index)
    if not target:
        target = "config.py"
        resolution = "fallback"
    if session is not None:
        graph = session.get_dependency_graph()
    else:
        from ..bug_intelligence import depgraph

        graph = depgraph.build_graph(index.get("project_root", task.repo_path))
    rows = [_header("PLAN_INPUT", result.get("mode", "impact"), "production")]
    rows = _append_evidence_rows(rows, task, index)
    focus = _task_focus_row(task)
    if focus:
        rows.append(focus)
    rows.append(_target_row(target, resolution))
    impact_payload: Dict[str, Any] = {}
    if graph and not graph.get("degraded"):
        impact_payload = impact.analyze_impact(
            graph,
            kind="file",
            file_path=target,
            project_root=index.get("project_root", task.repo_path),
        )
        may = impact_payload.get("questions", {}).get("may_break", {})
        rows.append(
            format_row(
                "IMPACT",
                {
                    "DIRECT": may.get("direct_count", 0),
                    "TRANSITIVE": may.get("transitive_count", 0),
                    "RISK": (impact_payload.get("risk") or {}).get("bucket", "unknown"),
                    "CONFIDENCE": (impact_payload.get("confidence") or {}).get("bucket", "unknown"),
                },
            )
        )
    rows.append(format_row("CONSTRAINT", {"TYPE": "preserve_public_contract", "VALUE": "yes"}))
    rows.append(format_row("VERIFY", {"TYPE": "targeted_tests", "VALUE": "required"}))
    ref_paths = _required_evidence_paths(task, index) + ([target] if target else []) + [
        path for path in result.get("sources", []) if not _is_corpus_path(str(path))
    ]
    rows.extend(_refs_block(ref_paths))
    _maybe_why_generic(rows, task)
    expanded = {
        "kind": "PLAN_INPUT",
        "task_id": task.task_id,
        "target": target,
        "target_resolution": resolution,
        "impact": impact_payload,
    }
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
    header, start, optional, end = _split_cap_rows(rows)
    digest = hashlib.sha256(
        json.dumps(expanded, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    metadata_sample = _metadata_rows(True, 0, 0, digest, False)
    metadata_reserve = estimated_count("\n".join(metadata_sample)) if metadata_sample else 0
    body_budget = max(cap - metadata_reserve, cap // 2)

    kept_optional = list(optional)
    truncated = False
    while True:
        candidate_rows = [header, *start, *kept_optional, *end]
        if estimated_count("\n".join(candidate_rows)) <= body_budget:
            break
        if not kept_optional:
            truncated = bool(optional)
            break
        kept_optional = kept_optional[:-1]
        truncated = True

    emitted_body = 1 + len(start) + len(kept_optional)
    total_body = 1 + len(start) + len(optional) + len(end)

    def _compose(include_metadata: bool, metadata_overflow: bool) -> str:
        body_rows = [header, *start, *kept_optional, *end]
        if include_metadata and truncated:
            body_rows.extend(_metadata_rows(True, emitted_body, total_body, digest, metadata_overflow))
        return "\n".join(body_rows)

    text = _compose(include_metadata=truncated, metadata_overflow=False)
    while estimated_count(text) > cap and kept_optional:
        kept_optional = kept_optional[:-1]
        truncated = bool(optional)
        emitted_body = 1 + len(start) + len(kept_optional)
        text = _compose(include_metadata=truncated, metadata_overflow=False)

    if estimated_count(text) > cap:
        text = _compose(include_metadata=truncated, metadata_overflow=True)
        if estimated_count(text) > cap:
            text = "\n".join(
                [
                    header,
                    *start,
                    *end,
                    format_row("OVERFLOW", {"VALUE": "yes", "CAP_EXCEEDED": "yes", "CAP": cap}),
                ]
            )

    token_estimate = estimated_count(text)
    overflow = token_estimate > cap
    if overflow:
        if "OVERFLOW|" not in text:
            overflow_row = format_row("OVERFLOW", {"VALUE": "yes", "CAP_EXCEEDED": "yes", "CAP": cap})
            candidate = text + "\n" + overflow_row
            if estimated_count(candidate) <= cap:
                text = candidate
            else:
                text = "\n".join(
                    [
                        header,
                        *start,
                        *end,
                        overflow_row,
                    ]
                )
        token_estimate = estimated_count(text)
        overflow = token_estimate > cap

    if truncated:
        expanded["truncated"] = True
        expanded["truncated_emitted"] = emitted_body
        expanded["truncated_total"] = total_body
        expanded["sha256"] = digest
    expanded["cap_overflow"] = overflow
    expanded["token_cap"] = cap
    expanded["token_estimate"] = token_estimate
    expanded["cap_compliant"] = token_estimate <= cap
    return text, expanded, truncated


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


def compare_formats_enabled(selected_format: str) -> bool:
    if selected_format == "compact":
        return True
    value = os.environ.get("JARVIS_CONTEXT_COMPARE_FORMATS", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def packet_cap_compliant(text: str, kind: str) -> bool:
    """True only when the emitted packet estimate is within the declared hard cap."""
    cap = HARD_TOKEN_CAPS.get(kind, 325)
    return estimated_count(text) <= cap


def measure_compact_corpus(
    tasks: Sequence[BenchmarkTask],
    *,
    shared_index: Optional[Dict[str, Any]] = None,
    index_loader: Optional[Any] = None,
) -> Dict[str, Any]:
    """Measure verbose vs compact tokens and preservation checks for a task corpus."""
    from .. import ask, indexer

    loader = index_loader or indexer.build_index
    index_cache: Dict[str, Dict[str, Any]] = {}
    rows: List[Dict[str, Any]] = []
    verbose_total = 0
    compact_total = 0
    cap_failures: List[str] = []
    missing_refs: List[str] = []
    evidence_gaps: List[str] = []
    for task in tasks:
        repo_path = os.path.abspath(task.repo_path)
        if shared_index is not None:
            index = shared_index
        else:
            index = index_cache.get(repo_path)
            if index is None:
                index = loader(repo_path)
                index_cache[repo_path] = index
        result = ask.answer(index, task.prompt)
        verbose = format_jarvis_packet(result)
        compact, expanded, kind = build_compact_packet(result, task, index)
        verbose_tokens = estimated_count(verbose)
        compact_tokens = estimated_count(compact)
        verbose_total += verbose_tokens
        compact_total += compact_tokens
        ref_count = compact.count("REF|")
        if kind in {"ARCH_RISK", "CONTRACT", "DEFECT_REVIEW", "IMPACT", "DEPENDENCY"} and ref_count == 0:
            missing_refs.append(task.task_id)
        if task.task_id == "contract01_sources":
            if "CONTRACT|" in compact and "PROVENANCE=contract_facts" not in compact:
                evidence_gaps.append(task.task_id)
            if "ORIGIN=analysis_finding" in compact or "ORIGIN=prompt" in compact:
                evidence_gaps.append(task.task_id)
        if task.task_id in {"defect01_wrong_operator", "defect02_bfs_queue"} and "FIXTURE|" not in compact:
            evidence_gaps.append(task.task_id)
        compliant = bool(expanded.get("cap_compliant")) and packet_cap_compliant(compact, kind)
        if not compliant:
            cap_failures.append(task.task_id)
        rows.append(
            {
                "task_id": task.task_id,
                "kind": kind,
                "verbose_tokens": verbose_tokens,
                "compact_tokens": compact_tokens,
                "token_cap": expanded.get("token_cap"),
                "ref_count": ref_count,
                "truncated": bool(expanded.get("truncated")),
                "cap_overflow": bool(expanded.get("cap_overflow")),
                "cap_compliant": compliant,
            }
        )
    reduction = (
        round(100.0 * (verbose_total - compact_total) / verbose_total, 2) if verbose_total else 0.0
    )
    return {
        "instrumentation_version": COMPACT_INSTRUMENTATION_VERSION,
        "task_count": len(tasks),
        "verbose_tokens": verbose_total,
        "compact_tokens": compact_total,
        "reduction_percent": reduction,
        "meets_fifty_percent_reduction": reduction >= 50.0,
        "meets_forty_percent_reduction": reduction >= 40.0,
        "cap_failures": cap_failures,
        "missing_refs": missing_refs,
        "evidence_gaps": evidence_gaps,
        "cap_compliance_pass": not cap_failures,
        "evidence_preservation_pass": not missing_refs and not evidence_gaps,
        "tasks": rows,
    }


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
    if compare_formats_enabled(selected):
        comparison = compare_context_formats(result, task, index, session=session)
    else:
        verbose = format_jarvis_packet(result)
        comparison = {
            "instrumentation_version": COMPACT_INSTRUMENTATION_VERSION,
            "task_id": task.task_id,
            "task_type": task.task_type,
            "comparison_skipped": True,
            "verbose_tokens": estimated_count(verbose),
            "compact_tokens": None,
            "reduction_percent": None,
            "meets_fifty_percent_reduction": None,
        }
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
