"""Phase 100E — context compression benchmark execution.

Runs the Phase 100B protocol on architecture, impact, and repository-understanding
tasks. Compares Arm A (simulated Claude-only file/grep context) vs Arm B (Claude+JARVIS
deterministic tools). Measures token-equivalent context, wall-clock, cost, and
automated anchor-based quality. No detector or benchmark tuning.
"""

from __future__ import annotations

import hashlib
import json
import os
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from builder_core import ask as ask_mod
from builder_core import indexer, store

ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = ROOT / "data" / "benchmarks" / "phase100e"
OUTPUT_DIR = ROOT / "reports" / "phase100e_run"
REPORT_PATH = ROOT / "reports" / "phase100e_context_compression_execution.md"

ARM_CLAUDE_ONLY = "claude_only"
ARM_CLAUDE_JARVIS = "claude_plus_jarvis"

N_TRIALS = 3
RUBRIC_VERSION = "phase100b-v1"

# Frozen price table (USD per token) — Phase 100B §6.1 exemplar for Sonnet-class model.
PRICE_TABLE = {
    "model_id": "claude-sonnet-4-20250514 (token accounting proxy)",
    "input_usd_per_token": 3.0 / 1_000_000,
    "output_usd_per_token": 15.0 / 1_000_000,
}

SYSTEM_PROMPT_TOKENS = 520
TURN_OVERHEAD_TOKENS = 40

_GRAPH_CACHE: Dict[str, Any] = {}


def _cached_depgraph(project_root: str) -> Dict[str, Any]:
    if project_root not in _GRAPH_CACHE:
        from builder_core.bug_intelligence import depgraph

        _GRAPH_CACHE[project_root] = depgraph.build_graph(project_root)
    return _GRAPH_CACHE[project_root]


def _git_head() -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.stdout.strip() if proc.returncode == 0 else "unknown"
    except OSError:
        return "unknown"


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


def _read_project_file(rel_path: str) -> Tuple[str, int]:
    path = ROOT / rel_path.replace("/", os.sep)
    if not path.is_file():
        return "", 0
    text = path.read_text(encoding="utf-8", errors="replace")
    return text, len(text)


def _grep_simulate(pattern: str, globs: Sequence[str]) -> Tuple[str, int]:
    """Simulate grep tool result bytes for Arm A."""
    import re

    rx = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
    lines: List[str] = []
    for glob in globs:
        for path in ROOT.glob(glob):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rel = path.relative_to(ROOT).as_posix()
            for index, line in enumerate(text.splitlines(), 1):
                if rx.search(line):
                    lines.append(f"{rel}:{index}:{line[:200]}")
            if len(lines) > 200:
                break
        if len(lines) > 200:
            break
    body = "\n".join(lines[:200])
    return body, len(body)


@dataclass
class TaskSpec:
    task_id: str
    category: str
    prompt: str
    anchors: List[str]
    arm_a_reads: List[str] = field(default_factory=list)
    arm_a_grep: List[Tuple[str, str]] = field(default_factory=list)  # (pattern, glob)
    arm_b: Dict[str, Any] = field(default_factory=dict)
    control: bool = False
    trap: bool = False
    require_sources: bool = True
    trap_unresolved_ok: bool = False


def build_task_suite() -> List[TaskSpec]:
    """Phase 100B tasks: architecture (8) + impact (6) + repository understanding (6)."""
    return [
        # --- Architecture ---
        TaskSpec(
            "A1", "architecture",
            "What are the most important production subsystems in this repository?",
            ["voice", "actions", "builder_core", "brain", "core"],
            arm_a_reads=["builder_core/README.md"],
            arm_a_grep=[(r"subsystem|production", "**/*.md")],
            arm_b={"tool": "ask", "question": "What are the most important production subsystems?"},
        ),
        TaskSpec(
            "A2", "architecture",
            "Which directories have the highest concentration of production code?",
            ["production_code"],
            arm_a_reads=[],
            arm_b={"tool": "ask", "question": "Which directories have the highest concentration of production code?"},
        ),
        TaskSpec(
            "A3", "architecture",
            "Which subsystems are most central to the architecture?",
            ["core", "import", "fan"],
            arm_a_reads=[],
            arm_b={"tool": "ask", "question": "Which subsystems are most central to the architecture?"},
        ),
        TaskSpec(
            "A4", "architecture",
            "What happens when a user speaks a voice command?",
            ["voice"],
            arm_a_reads=["voice/voice_loop.py"],
            arm_a_grep=[(r"voice|command|listen", "voice/**/*.py")],
            arm_b={"tool": "ask", "question": "What happens when a user speaks a voice command?"},
        ),
        TaskSpec(
            "A5", "architecture",
            "What are the entry points of the system?",
            ["main.py", "cli.py", "voice_loop"],
            arm_a_grep=[
                (r"if __name__", "**/*.py"),
                (r"def main", "**/*.py"),
            ],
            arm_b={"tool": "ask", "question": "What are the entry points of the system?"},
        ),
        TaskSpec(
            "A6", "architecture",
            "List the top directories and their purpose.",
            ["subsystem", "production"],
            arm_a_reads=["builder_core/README.md"],
            arm_b={"tool": "ask", "question": "List the top directories and their purpose."},
        ),
        TaskSpec(
            "A7", "architecture",
            "How is the bug-intelligence engine structured?",
            ["builder_core/bug_intelligence/engine.py", "analyze"],
            arm_a_reads=["builder_core/bug_intelligence/engine.py"],
            arm_b={
                "tool": "ask",
                "question": "How is the bug-intelligence engine structured in builder_core/bug_intelligence/engine.py?",
            },
        ),
        TaskSpec(
            "A8", "architecture",
            "Which folders are production vs tests vs benchmarks?",
            ["production", "test", "benchmark"],
            arm_a_reads=[],
            arm_b={"tool": "ask", "question": "Which folders are production code vs tests vs benchmarks?"},
        ),
        # --- Impact ---
        TaskSpec(
            "I1", "impact",
            "What modules import builder_core/bug_intelligence/engine.py?",
            ["engine.py"],
            arm_a_grep=[(r"bug_intelligence\.engine|from builder_core\.bug_intelligence import engine", "**/*.py")],
            arm_b={"tool": "impact_file", "path": "builder_core/bug_intelligence/engine.py"},
        ),
        TaskSpec(
            "I2", "impact",
            "What breaks if the signature of analyze_source in builder_core/bug_intelligence/engine.py changes?",
            ["analyze_source", "engine.py"],
            arm_a_reads=["builder_core/bug_intelligence/engine.py"],
            arm_a_grep=[(r"analyze_source", "**/*.py")],
            arm_b={"tool": "impact_file", "path": "builder_core/bug_intelligence/engine.py", "transitive": True},
        ),
        TaskSpec(
            "I3", "impact",
            "Which modules have the highest incoming-dependency count?",
            ["import", "module"],
            arm_a_reads=[],
            arm_b={"tool": "graph_summary"},
        ),
        TaskSpec(
            "I4", "impact",
            "What is the blast radius of editing core/app.py?",
            ["core/app.py"],
            arm_a_reads=["core/app.py"],
            arm_a_grep=[(r"core\.app|from core", "**/*.py")],
            arm_b={"tool": "impact_file", "path": "core/app.py", "transitive": True},
        ),
        TaskSpec(
            "I5", "impact",
            "Are there import cycles, and where?",
            ["cycle"],
            arm_a_reads=[],
            arm_b={"tool": "graph_summary"},
        ),
        TaskSpec(
            "I6", "impact",
            "What depends on the voice subsystem?",
            ["voice"],
            arm_a_grep=[(r"import voice|from voice", "**/*.py")],
            arm_b={"tool": "impact_module", "module": "voice"},
        ),
        # --- Repository understanding ---
        TaskSpec(
            "C1", "repository_understanding",
            "What does indexer.build_index return (shape and key fields)?",
            ["index", "files", "chunks"],
            arm_a_reads=["builder_core/indexer.py"],
            arm_b={
                "tool": "ask",
                "question": "What does indexer.build_index return in builder_core/indexer.py?",
            },
        ),
        TaskSpec(
            "C2", "repository_understanding",
            "Explain the wakeword to command flow.",
            ["wakeword", "voice"],
            arm_a_reads=["voice/wakeword.py", "voice/voice_loop.py"],
            arm_b={"tool": "ask", "question": "Explain the wakeword to command flow."},
        ),
        TaskSpec(
            "C3", "repository_understanding",
            "Summarize the responsibilities of brain/router.py.",
            ["brain/router.py", "router"],
            arm_a_reads=["brain/router.py"],
            arm_b={"tool": "ask", "question": "Summarize the responsibilities of brain/router.py."},
        ),
        TaskSpec(
            "C4", "repository_understanding",
            "Explain the logic of the function schedule_formatting in "
            "builder_core/benchmarks/holdout/pairs/bugsinpy_black_executor/buggy.py.",
            ["schedule_formatting", "executor"],
            arm_a_reads=["builder_core/benchmarks/holdout/pairs/bugsinpy_black_executor/buggy.py"],
            arm_b={
                "tool": "ask",
                "question": "Explain schedule_formatting in "
                "builder_core/benchmarks/holdout/pairs/bugsinpy_black_executor/buggy.py",
            },
            control=True,
        ),
        TaskSpec(
            "C5", "repository_understanding",
            "What is the blast radius of a typo in builder_core/benchmarks/holdout/pairs/classic_is_identity/buggy.py?",
            ["classic_is_identity"],
            arm_a_reads=["builder_core/benchmarks/holdout/pairs/classic_is_identity/buggy.py"],
            arm_b={
                "tool": "impact_file",
                "path": "builder_core/benchmarks/holdout/pairs/classic_is_identity/buggy.py",
            },
            control=True,
        ),
        TaskSpec(
            "C6", "repository_understanding",
            "What code calls self.dispatch() in this repository (dynamic dispatch)?",
            ["unresolved", "dispatch"],
            arm_a_grep=[(r"self\.dispatch\(", "**/*.py")],
            arm_b={
                "tool": "impact_file",
                "path": "brain/router.py",
                "note": "dynamic dispatch honesty trap",
            },
            trap=True,
            trap_unresolved_ok=True,
            require_sources=False,
        ),
    ]


def _extract_paths(text: str) -> List[str]:
    import re

    return re.findall(r"[\w./\\-]+\.py", text)


def _path_exists(rel: str) -> bool:
    clean = rel.replace("\\", "/").lstrip("./")
    return (ROOT / clean).is_file()


def score_quality(
    answer: str,
    sources: Sequence[str],
    task: TaskSpec,
) -> Tuple[int, Dict[str, Any]]:
    """Automated 0–4 rubric using ground-truth anchors (Phase 100B §4.1)."""
    lower = answer.lower()
    detail: Dict[str, Any] = {"anchors_hit": [], "anchors_miss": [], "fabricated_paths": []}

    for path in _extract_paths(answer):
        if path.endswith(".py") and not _path_exists(path):
            detail["fabricated_paths"].append(path)

    if detail["fabricated_paths"]:
        return 0, detail

    if task.trap_unresolved_ok and any(
        token in lower for token in ("unresolved", "unknown", "could not", "cannot determine", "dynamic")
    ):
        detail["trap_honesty"] = True
        return 4, detail

    hits = [anchor for anchor in task.anchors if anchor.lower() in lower]
    misses = [anchor for anchor in task.anchors if anchor.lower() not in lower]
    for src in sources:
        for anchor in task.anchors:
            if anchor.lower() in src.lower() and anchor not in hits:
                hits.append(anchor)
    detail["anchors_hit"] = hits
    detail["anchors_miss"] = [a for a in task.anchors if a not in hits]

    if len(hits) == len(task.anchors):
        if task.require_sources and not sources:
            return 2, detail
        return 4 if sources else 3, detail
    if hits:
        return 2, detail
    return 1, detail


@dataclass
class TrialResult:
    task_id: str
    arm: str
    trial: int
    answer: str
    sources: List[str]
    input_tokens: int
    output_tokens: int
    peak_context_tokens: int
    wall_clock_s: float
    cost_usd: float
    tool_calls: Dict[str, int]
    quality: int
    quality_detail: Dict[str, Any]


def run_arm_a(task: TaskSpec, trial: int) -> TrialResult:
    started = time.perf_counter()
    tool_calls: Dict[str, int] = {"read_file": 0, "grep": 0, "list_dir": 0}
    context_parts: List[str] = []
    excerpts: List[str] = []

    for rel in task.arm_a_reads:
        text, nbytes = _read_project_file(rel)
        tool_calls["read_file"] += 1
        header = f"=== read_file: {rel} ({nbytes} bytes) ===\n"
        context_parts.append(header + text[:120_000])
        excerpts.append(text[:4000])

    for pattern, glob in task.arm_a_grep:
        body, nbytes = _grep_simulate(pattern, [glob])
        tool_calls["grep"] += 1
        header = f"=== grep: {pattern!r} in {glob} ({nbytes} bytes) ===\n"
        context_parts.append(header + body)
        excerpts.append(body[:2000])

    tool_context = "\n\n".join(context_parts)
    task_prompt = task.prompt
    input_tokens = (
        SYSTEM_PROMPT_TOKENS
        + estimate_tokens(task_prompt)
        + estimate_tokens(tool_context)
        + TURN_OVERHEAD_TOKENS
    )
    peak_context_tokens = input_tokens

    answer = (
        f"Based on repository reads for task {task.task_id} (trial {trial}): "
        + " ".join(excerpts)[:6000]
    ).strip()
    sources = list(task.arm_a_reads)
    output_tokens = estimate_tokens(answer[:8000])

    elapsed = time.perf_counter() - started
    cost = (
        input_tokens * PRICE_TABLE["input_usd_per_token"]
        + output_tokens * PRICE_TABLE["output_usd_per_token"]
    )
    quality, qdetail = score_quality(answer, sources, task)
    return TrialResult(
        task_id=task.task_id,
        arm=ARM_CLAUDE_ONLY,
        trial=trial,
        answer=answer,
        sources=sources,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        peak_context_tokens=peak_context_tokens,
        wall_clock_s=elapsed,
        cost_usd=cost,
        tool_calls=tool_calls,
        quality=quality,
        quality_detail=qdetail,
    )


def _run_jarvis_tool(
    index: Dict[str, Any],
    spec: Dict[str, Any],
) -> Tuple[str, List[str], Dict[str, int], int]:
    tool_calls: Dict[str, int] = {}
    context_bytes = 0

    tool = spec.get("tool", "ask")
    if tool == "ask":
        tool_calls["ask"] = 1
        result = ask_mod.answer(index, spec["question"])
        payload = json.dumps(result, ensure_ascii=False, indent=2)
        context_bytes += len(payload)
        return result.get("answer", ""), list(result.get("sources", [])), tool_calls, context_bytes

    from builder_core.bug_intelligence import depgraph, impact

    project_root = index.get("project_root", str(ROOT))

    if tool == "graph_summary":
        tool_calls["graph_summary"] = 1
        graph = _cached_depgraph(project_root)
        summary = depgraph.format_summary(graph)
        context_bytes += len(summary)
        return summary, [project_root], tool_calls, context_bytes

    if tool == "impact_file":
        tool_calls["impact_file"] = 1
        graph = _cached_depgraph(project_root)
        result = impact.analyze_impact(
            graph,
            kind="file",
            file_path=spec["path"],
            project_root=project_root,
            include_transitive=bool(spec.get("transitive")),
        )
        buf = StringIO()
        buf.write(impact.format_summary(result, top=15))
        text = buf.getvalue()
        sources = [
            item.get("path", "")
            for item in result.get("questions", {}).get("files_dependent", [])
            if item.get("path")
        ]
        context_bytes += len(json.dumps(result, ensure_ascii=False)[:80_000])
        return text, sources[:12], tool_calls, context_bytes

    if tool == "impact_module":
        tool_calls["impact_module"] = 1
        graph = _cached_depgraph(project_root)
        result = impact.analyze_impact(
            graph,
            kind="module",
            module=spec["module"],
            project_root=project_root,
            include_transitive=True,
        )
        text = impact.format_summary(result, top=15)
        context_bytes += len(json.dumps(result, ensure_ascii=False)[:80_000])
        return text, [], tool_calls, context_bytes

    raise ValueError(f"unknown jarvis tool: {tool}")


def run_arm_b(task: TaskSpec, trial: int, index: Dict[str, Any]) -> TrialResult:
    started = time.perf_counter()
    answer, sources, tool_calls, jarvis_bytes = _run_jarvis_tool(index, task.arm_b)

    task_prompt = task.prompt
    input_tokens = (
        SYSTEM_PROMPT_TOKENS
        + estimate_tokens(task_prompt)
        + estimate_tokens("x" * jarvis_bytes)
        + TURN_OVERHEAD_TOKENS
    )
    peak_context_tokens = input_tokens
    output_tokens = estimate_tokens(answer[:8000])
    elapsed = time.perf_counter() - started
    cost = (
        input_tokens * PRICE_TABLE["input_usd_per_token"]
        + output_tokens * PRICE_TABLE["output_usd_per_token"]
    )
    quality, qdetail = score_quality(answer, sources, task)
    return TrialResult(
        task_id=task.task_id,
        arm=ARM_CLAUDE_JARVIS,
        trial=trial,
        answer=answer,
        sources=sources,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        peak_context_tokens=peak_context_tokens,
        wall_clock_s=elapsed,
        cost_usd=cost,
        tool_calls=tool_calls,
        quality=quality,
        quality_detail=qdetail,
    )


def measure_index_build() -> Dict[str, Any]:
    started = time.perf_counter()
    existing = store.load_index(str(ROOT))
    if existing is None:
        index = indexer.build_index(str(ROOT))
        store.save_index(str(ROOT), index)
    else:
        index = existing
    init_wall = time.perf_counter() - started

    from builder_core.bug_intelligence import depgraph

    g0 = time.perf_counter()
    graph = _cached_depgraph(str(ROOT))
    dep_wall = time.perf_counter() - g0
    graph_json = depgraph.export_json(graph)
    init_bytes = len(json.dumps(index, ensure_ascii=False)) + len(graph_json)
    init_tokens = estimate_tokens("x" * init_bytes)

    return {
        "wall_clock_s": round(init_wall + dep_wall, 3),
        "index_build_s": round(init_wall, 3),
        "depgraph_build_s": round(dep_wall, 3),
        "estimated_context_tokens": init_tokens,
        "depgraph_degraded": bool(graph.get("degraded")),
        "index_file_count": len(index.get("files", [])),
    }


def median_iqr(values: Sequence[float]) -> Tuple[float, float]:
    if not values:
        return 0.0, 0.0
    med = float(statistics.median(values))
    if len(values) < 2:
        return med, 0.0
    qs = statistics.quantiles(values, n=4, method="inclusive")
    return med, float(qs[2] - qs[0])


def aggregate_trials(trials: Sequence[TrialResult]) -> Dict[str, Any]:
    def med(field: str) -> float:
        return float(statistics.median([getattr(t, field) for t in trials]))

    return {
        "n_trials": len(trials),
        "input_tokens_median": med("input_tokens"),
        "output_tokens_median": med("output_tokens"),
        "total_tokens_median": med("input_tokens") + med("output_tokens"),
        "peak_context_median": med("peak_context_tokens"),
        "wall_clock_s_median": med("wall_clock_s"),
        "cost_usd_median": med("cost_usd"),
        "quality_median": med("quality"),
        "tool_calls_median": {
            key: float(statistics.median([t.tool_calls.get(key, 0) for t in trials]))
            for key in sorted({k for t in trials for k in t.tool_calls})
        },
    }


def evaluate_verdict(
    tasks: Sequence[TaskSpec],
    by_task: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    arch = [t for t in tasks if t.category == "architecture"]
    imp = [t for t in tasks if t.category == "impact"]
    ru = [t for t in tasks if t.category == "repository_understanding"]
    controls = [t for t in tasks if t.control]
    traps = [t for t in tasks if t.trap]

    def arm_medians(arm: str, field: str) -> List[float]:
        return [by_task[t.task_id][arm][field] for t in tasks]

    total_a = sum(by_task[t.task_id][ARM_CLAUDE_ONLY]["total_tokens_median"] for t in tasks)
    total_b = sum(by_task[t.task_id][ARM_CLAUDE_JARVIS]["total_tokens_median"] for t in tasks)
    compression = total_a / total_b if total_b else None

    peak_a = sum(by_task[t.task_id][ARM_CLAUDE_ONLY]["peak_context_median"] for t in tasks)
    peak_b = sum(by_task[t.task_id][ARM_CLAUDE_JARVIS]["peak_context_median"] for t in tasks)

    cost_a = sum(by_task[t.task_id][ARM_CLAUDE_ONLY]["cost_usd_median"] for t in tasks)
    cost_b = sum(by_task[t.task_id][ARM_CLAUDE_JARVIS]["cost_usd_median"] for t in tasks)

    time_a = sum(by_task[t.task_id][ARM_CLAUDE_ONLY]["wall_clock_s_median"] for t in tasks)
    time_b = sum(by_task[t.task_id][ARM_CLAUDE_JARVIS]["wall_clock_s_median"] for t in tasks)

    qual_a = statistics.mean([by_task[t.task_id][ARM_CLAUDE_ONLY]["quality_median"] for t in tasks])
    qual_b = statistics.mean([by_task[t.task_id][ARM_CLAUDE_JARVIS]["quality_median"] for t in tasks])

    def cat_compression(subset: Sequence[TaskSpec]) -> Optional[float]:
        a = sum(by_task[t.task_id][ARM_CLAUDE_ONLY]["total_tokens_median"] for t in subset)
        b = sum(by_task[t.task_id][ARM_CLAUDE_JARVIS]["total_tokens_median"] for t in subset)
        return round(a / b, 3) if b else None

    fabrication_b = sum(
        1 for t in tasks
        if by_task[t.task_id][ARM_CLAUDE_JARVIS]["quality_median"] == 0
        and by_task[t.task_id][ARM_CLAUDE_ONLY]["quality_median"] >= 3
    )

    gates = {
        "quality_non_inferiority": qual_b >= qual_a - 0.2 and qual_b >= 3.0,
        "no_fabrication_regression": fabrication_b == 0,
        "token_compression_2x": compression is not None and compression >= 2.0,
        "cost_reduction_40pct": cost_b <= cost_a * 0.6 if cost_a else False,
        "architecture_compression_3x": (cat_compression(arch) or 0) >= 3.0,
        "impact_compression_3x": (cat_compression(imp) or 0) >= 3.0,
    }

    if controls:
        gates["control_integrity"] = all(
            by_task[t.task_id][ARM_CLAUDE_JARVIS]["quality_median"]
            >= by_task[t.task_id][ARM_CLAUDE_ONLY]["quality_median"] - 0.2
            and by_task[t.task_id][ARM_CLAUDE_JARVIS]["total_tokens_median"]
            <= by_task[t.task_id][ARM_CLAUDE_ONLY]["total_tokens_median"] * 1.25
            for t in controls
        )
    if traps:
        gates["trap_honesty"] = all(
            by_task[t.task_id][ARM_CLAUDE_JARVIS]["quality_median"] >= 3 for t in traps
        )

    fail = (
        qual_b < qual_a - 0.5
        or (compression is not None and compression < 1.3)
        or (time_b > time_a and (compression or 0) < 1.3)
    )
    success = all(gates.values()) and not fail
    verdict = "SUCCESS" if success else ("FAIL" if fail else "PARTIAL")

    return {
        "verdict": verdict,
        "gates": gates,
        "suite_compression_ratio": round(compression, 3) if compression else None,
        "context_reduction_ratio": round(peak_a / peak_b, 3) if peak_b else None,
        "cost_reduction": round(1 - cost_b / cost_a, 4) if cost_a else None,
        "time_reduction": round(1 - time_b / time_a, 4) if time_a else None,
        "mean_quality_a": round(qual_a, 3),
        "mean_quality_b": round(qual_b, 3),
        "quality_delta": round(qual_b - qual_a, 3),
        "category_compression": {
            "architecture": cat_compression(arch),
            "impact": cat_compression(imp),
            "repository_understanding": cat_compression(ru),
        },
        "break_even_queries": None,
    }


def write_report(
    manifest: Dict[str, Any],
    raw_trials: List[Dict[str, Any]],
    by_task: Dict[str, Dict[str, Any]],
    verdict: Dict[str, Any],
    index_build: Dict[str, Any],
    elapsed_s: float,
) -> None:
    tasks = build_task_suite()
    lines = [
        "# Phase 100E — Context Compression Benchmark Execution",
        "",
        "**Status:** Execution complete",
        f"**Date:** {time.strftime('%Y-%m-%d')}",
        "**Protocol:** `phase100b_context_compression_benchmark_design.md`",
        "**Constraints:** No detector changes; no benchmark tuning",
        "",
        "---",
        "",
        "## 1. Executive summary",
        "",
        "| Item | Value |",
        "|------|-------|",
        f"| Tasks | {len(tasks)} (architecture 8, impact 6, repository understanding 6) |",
        f"| Trials per task × arm | {N_TRIALS} |",
        f"| Repository | `{ROOT}` |",
        f"| Commit | `{manifest['repo_commit']}` |",
        f"| Model (token pricing proxy) | `{PRICE_TABLE['model_id']}` |",
        f"| **Verdict** | **{verdict['verdict']}** |",
        f"| Suite compression ratio (A/B tokens) | {verdict['suite_compression_ratio']}× |",
        f"| Mean quality Claude Only → +JARVIS | {verdict['mean_quality_a']} → {verdict['mean_quality_b']} (Δ {verdict['quality_delta']}) |",
        f"| Elapsed | {elapsed_s:.1f}s |",
        "",
        "**Execution mode:** Deterministic harness measuring **tool-result context** for each arm.",
        "Arm A simulates Claude-only `read_file`/`grep` paths preregistered per task; Arm B invokes",
        "live JARVIS `ask` / `graph summary` / `impact-*` tools. Token counts use chars÷4 (Phase 100B §3).",
        "Quality uses automated anchor matching (0–4); blinded human scoring is recommended before product claims.",
        "",
        "---",
        "",
        "## 2. Summary table (suite medians)",
        "",
        "| Metric | Claude Only (A) | Claude + JARVIS (B) | Δ / ratio |",
        "|--------|----------------:|--------------------:|-----------|",
        f"| Total input tokens (sum of task medians) | {sum(by_task[t.task_id][ARM_CLAUDE_ONLY]['input_tokens_median'] for t in tasks):,.0f} | {sum(by_task[t.task_id][ARM_CLAUDE_JARVIS]['input_tokens_median'] for t in tasks):,.0f} | {verdict['suite_compression_ratio']}× |",
        f"| Peak context tokens (sum of medians) | {sum(by_task[t.task_id][ARM_CLAUDE_ONLY]['peak_context_median'] for t in tasks):,.0f} | {sum(by_task[t.task_id][ARM_CLAUDE_JARVIS]['peak_context_median'] for t in tasks):,.0f} | {verdict['context_reduction_ratio']}× |",
        f"| Wall-clock (sum of medians, s) | {sum(by_task[t.task_id][ARM_CLAUDE_ONLY]['wall_clock_s_median'] for t in tasks):.2f} | {sum(by_task[t.task_id][ARM_CLAUDE_JARVIS]['wall_clock_s_median'] for t in tasks):.2f} | {verdict['time_reduction']:.1%} reduction |",
        f"| Cost USD (sum of medians) | ${sum(by_task[t.task_id][ARM_CLAUDE_ONLY]['cost_usd_median'] for t in tasks):.4f} | ${sum(by_task[t.task_id][ARM_CLAUDE_JARVIS]['cost_usd_median'] for t in tasks):.4f} | {verdict['cost_reduction']:.1%} reduction |",
        f"| Mean answer quality (0–4) | {verdict['mean_quality_a']} | {verdict['mean_quality_b']} | {verdict['quality_delta']:+.2f} |",
        "",
        "### Index build (Arm B, amortized separately)",
        "",
        f"| Index + depgraph build | {index_build['wall_clock_s']}s | ~{index_build['estimated_context_tokens']:,} token-equivalent |",
        f"| Depgraph degraded | {index_build['depgraph_degraded']} |",
        "",
        "---",
        "",
        "## 3. Tier metrics by category",
        "",
        "| Category | Tasks | Compression A/B | Mean quality A | Mean quality B |",
        "|----------|------:|------------------:|---------------:|---------------:|",
    ]
    for cat in ("architecture", "impact", "repository_understanding"):
        subset = [t for t in tasks if t.category == cat]
        qa = statistics.mean([by_task[t.task_id][ARM_CLAUDE_ONLY]["quality_median"] for t in subset])
        qb = statistics.mean([by_task[t.task_id][ARM_CLAUDE_JARVIS]["quality_median"] for t in subset])
        comp = verdict["category_compression"].get(cat)
        lines.append(f"| {cat} | {len(subset)} | {comp}× | {qa:.2f} | {qb:.2f} |")

    lines.extend([
        "",
        "---",
        "",
        "## 4. Success gates (Phase 100B §5)",
        "",
        "Per-task **answer quality** (0–4, anchor-based) substitutes for blinded human scoring.",
        f"**Break-even** (index amortized): ~{verdict.get('break_even_queries')} tasks at current savings.",
        "",
        "| Gate (Phase 100B §5) | Pass |",
        "|----------------------|:----:|",
    ])
    for name, passed in verdict["gates"].items():
        lines.append(f"| {name} | {'yes' if passed else 'no'} |")

    lines.extend([
        "",
        "---",
        "",
        "## 5. Per-task results",
        "",
        "| ID | Category | Arm A tokens | Arm B tokens | Ratio | Q(A) | Q(B) |",
        "|----|----------|-------------:|-------------:|------:|-----:|-----:|",
    ])
    for task in tasks:
        a = by_task[task.task_id][ARM_CLAUDE_ONLY]
        b = by_task[task.task_id][ARM_CLAUDE_JARVIS]
        ratio = (
            round(a["total_tokens_median"] / b["total_tokens_median"], 2)
            if b["total_tokens_median"]
            else None
        )
        lines.append(
            f"| {task.task_id} | {task.category} | {a['total_tokens_median']:,.0f} | "
            f"{b['total_tokens_median']:,.0f} | {ratio}× | {a['quality_median']:.0f} | {b['quality_median']:.0f} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 6. Artifacts",
        "",
        "| File | Description |",
        "|------|-------------|",
        f"| `{CORPUS_DIR.relative_to(ROOT).as_posix()}/manifest.json` | Frozen run manifest |",
        f"| `{OUTPUT_DIR.relative_to(ROOT).as_posix()}/raw_trials.json` | Per trial metrics |",
        f"| `{OUTPUT_DIR.relative_to(ROOT).as_posix()}/task_summary.json` | Medians per task × arm |",
        f"| `{OUTPUT_DIR.relative_to(ROOT).as_posix()}/verdict.json` | Suite gates + verdict |",
        "",
        "---",
        "",
        "## 7. Honest limitations",
        "",
        "- No live Claude API calls were made; arms differ only in **context delivered** to the agent.",
        "- Automated quality is anchor-based; product claims should add blinded human scoring (100B §6.2).",
        "- Single-repo (`local_jarvis`); generalization requires re-pinning the manifest on other repos.",
        "- Index-build cost is excluded from per-task steady-state medians but reported separately.",
        "",
    ])
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_execution() -> Dict[str, Any]:
    started = time.time()
    tasks = build_task_suite()
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    index_build = measure_index_build()
    index = store.load_index(str(ROOT))
    if index is None:
        raise RuntimeError("index missing after init")

    manifest = {
        "schema_version": 1,
        "program_id": "phase100e-context-compression",
        "rubric_version": RUBRIC_VERSION,
        "repo_root": str(ROOT),
        "repo_commit": _git_head(),
        "price_table": PRICE_TABLE,
        "n_trials": N_TRIALS,
        "arms": [ARM_CLAUDE_ONLY, ARM_CLAUDE_JARVIS],
        "task_ids": [t.task_id for t in tasks],
        "task_suite_hash": hashlib.sha256(
            json.dumps([t.task_id for t in tasks]).encode()
        ).hexdigest()[:16],
    }
    (CORPUS_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    raw_trials: List[Dict[str, Any]] = []
    by_task: Dict[str, Dict[str, Any]] = {}

    for task in tasks:
        trials_a: List[TrialResult] = []
        trials_b: List[TrialResult] = []
        for trial in range(1, N_TRIALS + 1):
            trials_a.append(run_arm_a(task, trial))
            trials_b.append(run_arm_b(task, trial, index))
        for trial in trials_a + trials_b:
            raw_trials.append({
                "task_id": trial.task_id,
                "arm": trial.arm,
                "trial": trial.trial,
                "input_tokens": trial.input_tokens,
                "output_tokens": trial.output_tokens,
                "total_tokens": trial.input_tokens + trial.output_tokens,
                "peak_context_tokens": trial.peak_context_tokens,
                "wall_clock_s": round(trial.wall_clock_s, 4),
                "cost_usd": round(trial.cost_usd, 6),
                "tool_calls": trial.tool_calls,
                "quality": trial.quality,
                "quality_detail": trial.quality_detail,
                "answer_preview": trial.answer[:500],
            })
        by_task[task.task_id] = {
            ARM_CLAUDE_ONLY: aggregate_trials(trials_a),
            ARM_CLAUDE_JARVIS: aggregate_trials(trials_b),
        }

    verdict = evaluate_verdict(tasks, by_task)
    init_tokens = index_build["estimated_context_tokens"]
    steady_b = sum(by_task[t.task_id][ARM_CLAUDE_JARVIS]["total_tokens_median"] for t in tasks)
    steady_a = sum(by_task[t.task_id][ARM_CLAUDE_ONLY]["total_tokens_median"] for t in tasks)
    per_task_save = (steady_a - steady_b) / len(tasks) if len(tasks) else 0
    verdict["break_even_queries"] = (
        round(init_tokens / per_task_save, 1) if per_task_save > 0 else None
    )

    (OUTPUT_DIR / "raw_trials.json").write_text(
        json.dumps(raw_trials, indent=2) + "\n", encoding="utf-8"
    )
    (OUTPUT_DIR / "task_summary.json").write_text(
        json.dumps(by_task, indent=2) + "\n", encoding="utf-8"
    )
    (OUTPUT_DIR / "verdict.json").write_text(
        json.dumps({"verdict": verdict, "index_build": index_build}, indent=2) + "\n",
        encoding="utf-8",
    )

    elapsed = time.time() - started
    write_report(manifest, raw_trials, by_task, verdict, index_build, elapsed)
    return {"verdict": verdict, "by_task": by_task, "elapsed_s": elapsed}


def main() -> int:
    result = run_execution()
    print(f"Phase 100E complete — verdict: {result['verdict']['verdict']}")
    print(f"Compression: {result['verdict']['suite_compression_ratio']}×")
    print(f"Report: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
