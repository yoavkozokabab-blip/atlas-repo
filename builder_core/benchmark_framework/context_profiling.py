"""Phase 104B — context generation profiling (instrumentation only)."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from .jarvis_packet import format_jarvis_packet
from .schema import BenchmarkTask, dump_json
from .tokens import estimated_count

PROFILING_VERSION = "phase104b-v1"

STAGE_NAMES = (
    "index_loading",
    "repository_understanding",
    "dependency_graph",
    "impact_analysis",
    "architectural_risk",
    "contract_facts",
    "verification_evidence",
    "serialization",
    "context_assembly",
)


@dataclass
class StageMeasurement:
    name: str
    elapsed_ms: float
    token_contribution: int
    artifact_preview: str = ""
    percent_of_total_tokens: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "elapsed_ms": round(self.elapsed_ms, 3),
            "token_contribution": self.token_contribution,
            "percent_of_total_tokens": self.percent_of_total_tokens,
            "artifact_preview": self.artifact_preview[:240],
        }


@dataclass
class ContextProfile:
    task_id: str
    task_type: str
    repo_path: str
    packet_text: str
    packet_total_tokens: int
    stages: List[StageMeasurement] = field(default_factory=list)
    total_profiled_elapsed_ms: float = 0.0
    ask_mode: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profiling_version": PROFILING_VERSION,
            "task_id": self.task_id,
            "task_type": self.task_type,
            "repo_path": self.repo_path,
            "ask_mode": self.ask_mode,
            "packet_total_tokens": self.packet_total_tokens,
            "total_profiled_elapsed_ms": round(self.total_profiled_elapsed_ms, 3),
            "stages": [stage.to_dict() for stage in self.stages],
        }


def _elapsed_ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000.0


def _stage(
    name: str,
    start: float,
    artifact: str,
    *,
    preview: Optional[str] = None,
) -> StageMeasurement:
    text = artifact or ""
    return StageMeasurement(
        name=name,
        elapsed_ms=_elapsed_ms(start),
        token_contribution=estimated_count(text),
        artifact_preview=preview or text[:240],
    )


def _subsystem_line(subsystem: Dict[str, Any]) -> str:
    production_count = subsystem.get("role_counts", {}).get("production_code", 0)
    entries = ", ".join(subsystem.get("entry_files", [])[:3]) or "(no production entry file)"
    dependencies = ", ".join(subsystem.get("dependencies", [])) or "(none detected)"
    return (
        f"{subsystem['name']}: {production_count} production file(s); "
        f"entry files: {entries}; dependencies: {dependencies}"
    )


def _graph_summary_text(graph: Optional[Dict[str, Any]]) -> str:
    if not graph:
        return "dependency graph unavailable"
    if graph.get("degraded"):
        return "dependency graph degraded on production scope"
    stats = graph.get("statistics") or {}
    top = stats.get("top_imported_modules") or []
    lines = [
        f"graph_scope={graph.get('graph_scope')}",
        f"import_cycles={len(stats.get('import_cycles') or [])}",
    ]
    for item in top[:8]:
        label = item.get("dotted") or item.get("path") or item.get("id")
        lines.append(f"fan-in {label}={item.get('count', 0)}")
    return "\n".join(lines)


def _pick_production_path(index: Dict[str, Any], preferred: str = "config.py") -> str:
    paths = [
        item["path"]
        for item in index.get("files", [])
        if item.get("role") == "production_code" and str(item.get("path", "")).endswith(".py")
    ]
    if preferred in paths:
        return preferred
    return paths[0] if paths else preferred


def _test_documents(index: Dict[str, Any]) -> List[Dict[str, str]]:
    docs: List[Dict[str, str]] = []
    project_root = index.get("project_root") or ""
    for entry in index.get("files", []):
        if entry.get("category") != "test" and entry.get("role") != "test":
            continue
        path = entry.get("path") or ""
        if not path or not project_root:
            continue
        full = os.path.join(project_root, path)
        try:
            with open(full, "r", encoding="utf-8-sig", errors="ignore") as handle:
                docs.append({"path": path, "text": handle.read()})
        except OSError:
            continue
    return docs


def _probe_contract_facts(index: Dict[str, Any]) -> str:
    from ..bug_intelligence import contract_facts

    if not contract_facts.CONTRACT_FACTS_ENABLED:
        return "contract_facts disabled"
    analysis = next(
        (item for item in index.get("python_analysis", []) if not item.get("parse_error")),
        None,
    )
    if not analysis:
        return "no python_analysis entry"
    path = analysis.get("path", "")
    project_root = index.get("project_root") or ""
    if not path or not project_root:
        return "missing path"
    full = os.path.join(project_root, path)
    try:
        with open(full, "r", encoding="utf-8-sig", errors="ignore") as handle:
            source = handle.read()
    except OSError:
        return "source unreadable"
    import ast

    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        return f"parse_error: {exc}"
    payload = contract_facts.extract_module_contracts({"parse_error": ""}, tree, path)
    return json.dumps(payload, ensure_ascii=True, sort_keys=True)


def _probe_verification_evidence(index: Dict[str, Any]) -> str:
    from ..bug_intelligence import verification_evidence
    from ..bug_intelligence.finding import Finding

    if not verification_evidence.VERIFICATION_EVIDENCE_ENABLED:
        return "verification_evidence disabled"
    analysis = next(
        (item for item in index.get("python_analysis", []) if item.get("findings")),
        None,
    )
    if not analysis:
        return "no findings to enrich"
    path = analysis.get("path", "")
    finding_data = analysis["findings"][0]
    finding = Finding(
        category="logic_bug",
        kind="semantic",
        severity=finding_data.get("severity", "medium"),
        confidence="medium",
        file=path,
        line=int(finding_data.get("line", 1)),
        title=finding_data.get("rule", "inconsistent_return"),
        explanation=finding_data.get("message", "probe"),
        why_might_be_wrong="profile probe",
        next_verification_step="inspect tests",
        rule="inconsistent_return",
    )
    module_facts = {"interproc": {"call_graph": {"functions": {}}}}
    enriched = verification_evidence.enrich_inconsistent_return_finding(
        finding,
        module_facts,
        test_documents=_test_documents(index),
    )
    overlay = enriched.verification_evidence or {}
    return json.dumps(overlay, ensure_ascii=True, sort_keys=True)


def _finalize_percentages(stages: List[StageMeasurement]) -> None:
    total = sum(stage.token_contribution for stage in stages)
    for stage in stages:
        if total:
            stage.percent_of_total_tokens = round(
                100.0 * stage.token_contribution / total, 2
            )
        else:
            stage.percent_of_total_tokens = 0.0


def profile_jarvis_context(
    task: BenchmarkTask,
    *,
    index: Optional[Dict[str, Any]] = None,
    index_loader: Optional[Callable[[str], Dict[str, Any]]] = None,
) -> ContextProfile:
    """Profile staged context generation for one benchmark task (read-only)."""
    loader = index_loader
    if loader is None:
        from .. import indexer

        loader = indexer.build_index

    stages: List[StageMeasurement] = []
    repo_path = os.path.abspath(task.repo_path)
    graph: Optional[Dict[str, Any]] = None

    start = time.perf_counter()
    if index is None:
        index = loader(repo_path)
    stages.append(_stage("index_loading", start, ""))

    start = time.perf_counter()
    from .. import repository_understanding as ru

    subsystems = ru.production_subsystems(index)
    ru_text = "\n".join(_subsystem_line(item) for item in subsystems[:12])
    stages.append(_stage("repository_understanding", start, ru_text))

    start = time.perf_counter()
    from ..bug_intelligence import depgraph

    graph = depgraph.build_graph(repo_path) if index.get("project_root") else None
    stages.append(_stage("dependency_graph", start, _graph_summary_text(graph)))

    start = time.perf_counter()
    from ..bug_intelligence import impact

    impact_text = "impact probe skipped"
    if graph and not graph.get("degraded"):
        target = _pick_production_path(index)
        probe = impact.analyze_impact(
            graph,
            kind="file",
            file_path=target,
            project_root=index.get("project_root", repo_path),
        )
        impact_text = json.dumps(
            {
                "target": target,
                "direct": probe.get("questions", {}).get("may_break", {}).get("direct_count", 0),
                "transitive": probe.get("questions", {}).get("may_break", {}).get("transitive_count", 0),
                "risk": probe.get("risk", {}),
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    stages.append(_stage("impact_analysis", start, impact_text))

    start = time.perf_counter()
    from .. import architectural_risk

    arch_text = "architectural risk skipped"
    if graph and not graph.get("degraded"):
        ranking = architectural_risk.rank_modules(index, graph, top=8)
        arch_text = architectural_risk.format_ranking_answer(ranking)
    stages.append(_stage("architectural_risk", start, arch_text))

    start = time.perf_counter()
    stages.append(_stage("contract_facts", start, _probe_contract_facts(index)))

    start = time.perf_counter()
    stages.append(_stage("verification_evidence", start, _probe_verification_evidence(index)))

    bundle = {
        "task_id": task.task_id,
        "stages": {
            stage.name: {
                "elapsed_ms": stage.elapsed_ms,
                "token_contribution": stage.token_contribution,
            }
            for stage in stages
        },
    }
    start = time.perf_counter()
    serialized = json.dumps(bundle, ensure_ascii=True, sort_keys=True)
    stages.append(_stage("serialization", start, serialized))

    start = time.perf_counter()
    from .. import ask

    ask_result = ask.answer(index, task.prompt)
    packet = format_jarvis_packet(ask_result)
    stages.append(_stage("context_assembly", start, packet))

    _finalize_percentages(stages)
    profile = ContextProfile(
        task_id=task.task_id,
        task_type=task.task_type,
        repo_path=repo_path,
        packet_text=packet,
        packet_total_tokens=estimated_count(packet),
        stages=stages,
        total_profiled_elapsed_ms=sum(stage.elapsed_ms for stage in stages),
        ask_mode=str(ask_result.get("mode", "")),
    )
    return profile


def aggregate_stage_measurements(
    profiles: Sequence[ContextProfile],
) -> List[Dict[str, Any]]:
    """Average elapsed ms and token contribution per stage across profiles."""
    buckets: Dict[str, Dict[str, List[float]]] = {
        name: {"elapsed_ms": [], "token_contribution": [], "percent": []}
        for name in STAGE_NAMES
    }
    for profile in profiles:
        for stage in profile.stages:
            bucket = buckets.get(stage.name)
            if not bucket:
                continue
            bucket["elapsed_ms"].append(stage.elapsed_ms)
            bucket["token_contribution"].append(float(stage.token_contribution))
            bucket["percent"].append(stage.percent_of_total_tokens)

    rows: List[Dict[str, Any]] = []
    for name in STAGE_NAMES:
        bucket = buckets[name]
        if not bucket["elapsed_ms"]:
            continue
        rows.append(
            {
                "stage": name,
                "samples": len(bucket["elapsed_ms"]),
                "average_elapsed_ms": round(
                    sum(bucket["elapsed_ms"]) / len(bucket["elapsed_ms"]), 3
                ),
                "average_token_contribution": round(
                    sum(bucket["token_contribution"]) / len(bucket["token_contribution"]),
                    3,
                ),
                "average_percent_of_total_tokens": round(
                    sum(bucket["percent"]) / len(bucket["percent"]), 3
                ),
            }
        )
    return rows


def render_profile_report(
    profiles: Sequence[ContextProfile],
    *,
    title: str = "Phase 104B Context Generation Profile",
) -> str:
    """Render markdown report with top contributors and slowest stages."""
    aggregated = aggregate_stage_measurements(profiles)
    by_tokens = sorted(
        aggregated, key=lambda row: row["average_token_contribution"], reverse=True
    )
    by_time = sorted(aggregated, key=lambda row: row["average_elapsed_ms"], reverse=True)
    top_token = by_tokens[:20]
    top_slow = by_time[:20]

    lines = [
        f"# {title}",
        "",
        f"**Profiling version:** `{PROFILING_VERSION}`",
        f"**Tasks profiled:** {len(profiles)}",
        "",
        "> Instrumentation only — no optimization, no scoring or ask-behavior changes.",
        "> Token figures use the Phase 104A chars/4 estimator on stage artifact text.",
        "",
        "## Method",
        "",
        "Each benchmark task is profiled by running read-only Builder Core stages ",
        "sequentially. `context_assembly` executes `ask.answer` and formats the offline ",
        "JARVIS packet. Other stages measure their artifact size and wall time even when ",
        "that artifact is not fully duplicated in the final packet.",
        "",
        "## Aggregate by stage",
        "",
        "| Stage | Samples | Avg elapsed (ms) | Avg tokens | Avg % of profiled tokens |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in aggregated:
        lines.append(
            f"| {row['stage']} | {row['samples']} | {row['average_elapsed_ms']} | "
            f"{row['average_token_contribution']} | {row['average_percent_of_total_tokens']} |"
        )

    lines.extend(
        [
            "",
            "## Top 20 largest token contributors",
            "",
            "| Rank | Stage | Avg tokens | Avg % of profiled tokens |",
            "|---:|---|---:|---:|",
        ]
    )
    for rank, row in enumerate(top_token, 1):
        lines.append(
            f"| {rank} | {row['stage']} | {row['average_token_contribution']} | "
            f"{row['average_percent_of_total_tokens']} |"
        )

    lines.extend(
        [
            "",
            "## Top 20 slowest contributors",
            "",
            "| Rank | Stage | Avg elapsed (ms) | Avg tokens |",
            "|---:|---|---:|---:|",
        ]
    )
    for rank, row in enumerate(top_slow, 1):
        lines.append(
            f"| {rank} | {row['stage']} | {row['average_elapsed_ms']} | "
            f"{row['average_token_contribution']} |"
        )

    if profiles:
        sample = profiles[0]
        lines.extend(
            [
                "",
                "## Sample packet record",
                "",
                f"- Task: `{sample.task_id}` (`{sample.task_type}`)",
                f"- Ask mode: `{sample.ask_mode}`",
                f"- Packet tokens: {sample.packet_total_tokens}",
                f"- Total profiled elapsed: {sample.total_profiled_elapsed_ms} ms",
                "",
                "| Stage | ms | tokens | % |",
                "|---|---:|---:|---:|",
            ]
        )
        for stage in sample.stages:
            lines.append(
                f"| {stage.name} | {stage.elapsed_ms:.3f} | {stage.token_contribution} | "
                f"{stage.percent_of_total_tokens} |"
            )

    lines.append("")
    return "\n".join(lines)


def write_profile_report(
    path: str,
    profiles: Sequence[ContextProfile],
    *,
    title: str = "Phase 104B Context Generation Profile",
) -> str:
    text = render_profile_report(profiles, title=title)
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return path


def attach_profile_to_run_package(
    run_root: str,
    task_id: str,
    profile: ContextProfile,
) -> str:
    """Write per-task context profile JSON beside a benchmark run package."""
    task_root = os.path.join(run_root, task_id)
    out_path = os.path.join(task_root, "context_profile.json")
    dump_json(profile.to_dict(), out_path)
    return out_path
