"""Generate deterministic, offline Phase 103 manual benchmark packages."""

from __future__ import annotations

import datetime as dt
import os
from typing import Any, Callable, Dict, Optional

from . import FRAMEWORK_VERSION, SCHEMA_VERSION
from .schema import BenchmarkTask, MODES, RunLog
from .compact_packets import format_jarvis_context, packet_format_from_env
from .jarvis_packet import format_jarvis_packet
from .schema import dump_json
from .tokens import (
    INSTRUMENTATION_VERSION,
    build_token_breakdown,
    prompt_metadata_comment,
)

JarvisContextFn = Callable[[BenchmarkTask], str]
_INDEX_CACHE: Dict[str, Any] = {}


def _default_run_id() -> str:
    return "run_" + dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def default_jarvis_context(task: BenchmarkTask) -> str:
    """Collect deterministic local Builder Core context without network access."""
    try:
        if not task.repo_path or not os.path.isdir(task.repo_path):
            return "[JARVIS context unavailable: repository path not found]"
        from .. import ask, indexer

        repo_path = os.path.abspath(task.repo_path)
        index = _INDEX_CACHE.get(repo_path)
        if index is None:
            index = indexer.build_index(repo_path)
            _INDEX_CACHE[repo_path] = index
        result = ask.answer(index, task.prompt)
        packet_format = packet_format_from_env()
        context, packet_meta = format_jarvis_context(
            result, task, index, packet_format=packet_format
        )
        packet_meta["comparison"]["ask_mode"] = result.get("mode")
        _INDEX_CACHE[f"{repo_path}__packet_meta__{task.task_id}"] = packet_meta
        return context
    except Exception as exc:  # pragma: no cover - guarded fallback is environment-specific
        return f"[JARVIS context unavailable: {type(exc).__name__}]"


def build_prompt(task: BenchmarkTask, mode: str, jarvis_context: str = "") -> str:
    if mode not in MODES:
        raise ValueError(f"unsupported benchmark mode: {mode}")
    if mode == "codex_alone":
        context = (
            "Explore the repository using ordinary read-only repository tools. "
            "Do not use precomputed JARVIS output."
        )
        mode_instructions = task.baseline_mode
    else:
        context = (
            "Use the deterministic JARVIS context below as the starting point. "
            "Use targeted read-only repository checks when evidence needs confirmation.\n\n"
            "## Precomputed JARVIS Context\n"
            "```\n"
            f"{jarvis_context}\n"
            "```"
        )
        mode_instructions = task.jarvis_mode
    return (
        f"# Phase 103 Benchmark Task: {task.task_id}\n\n"
        f"- Mode: `{mode}`\n"
        f"- Repository: `{task.repo_id}` at `{task.repo_path}`\n"
        f"- Task type: `{task.task_type}`\n\n"
        "## Mode Instructions\n"
        f"{context}\n"
        f"{mode_instructions}\n\n"
        "## Task\n"
        f"{task.prompt}\n\n"
        "## Required Answer Shape\n"
        "Give a direct answer, cite repository evidence, identify uncertainty, "
        "and avoid unsupported claims.\n"
    )


def generate_run_package(
    tasks: list[BenchmarkTask],
    out_dir: str,
    *,
    run_id: Optional[str] = None,
    jarvis_context_fn: Optional[JarvisContextFn] = None,
) -> Dict[str, Any]:
    """Write prompts and editable run templates below reports/benchmarks."""
    package_id = run_id or _default_run_id()
    context_fn = jarvis_context_fn or default_jarvis_context
    run_root = os.path.join(out_dir, package_id)
    os.makedirs(run_root, exist_ok=True)
    repo_paths: Dict[str, str] = {}

    for task in sorted(tasks, key=lambda item: item.task_id):
        repo_paths[task.repo_id] = task.repo_path
        task_root = os.path.join(run_root, task.task_id)
        os.makedirs(os.path.join(task_root, "answers"), exist_ok=True)
        jarvis_context = context_fn(task)
        repo_key = os.path.abspath(task.repo_path)
        packet_meta = _INDEX_CACHE.pop(f"{repo_key}__packet_meta__{task.task_id}", {})
        if packet_meta:
            dump_json(
                packet_meta.get("comparison", {}),
                os.path.join(task_root, "context_token_comparison.json"),
            )
            if packet_meta.get("compact_text"):
                _write_text(
                    os.path.join(task_root, "context_packet.compact.txt"),
                    packet_meta["compact_text"],
                )
            dump_json(
                packet_meta.get("expanded", {}),
                os.path.join(task_root, "context_packet.expanded.json"),
            )
        dump_json(task.to_dict(), os.path.join(task_root, "task.json"))
        for mode in MODES:
            prompt = build_prompt(task, mode, jarvis_context)
            context_for_mode = jarvis_context if mode == "jarvis_plus_codex" else ""
            breakdown = build_token_breakdown(
                raw_prompt=task.prompt,
                jarvis_context=context_for_mode,
                final_prompt_package=prompt,
            )
            prompt_name = f"{mode}.prompt.md"
            _write_text(
                os.path.join(task_root, prompt_name),
                prompt_metadata_comment(breakdown) + prompt,
            )
            score_path = f"score.{mode}.json"
            answer_path = f"answers/{task.task_id}.{mode}.txt"
            log = RunLog(
                task_id=task.task_id,
                mode=mode,
                estimated_input_tokens=breakdown.final_prompt_package.estimated_tokens,
                raw_answer_path=answer_path,
                score_path=score_path,
                token_breakdown=breakdown.to_dict(),
            )
            log_path = os.path.join(task_root, f"run_log.{mode}.json")
            dump_json(log.to_dict(), log_path)
            dump_json(breakdown.to_dict(), os.path.join(task_root, f"token_breakdown.{mode}.json"))
            dump_json(_score_template(task.task_id, mode), os.path.join(task_root, score_path))

    manifest = {
        "framework_version": FRAMEWORK_VERSION,
        "schema_version": SCHEMA_VERSION,
        "run_id": package_id,
        "modes": list(MODES),
        "task_count": len(tasks),
        "task_ids": sorted(task.task_id for task in tasks),
        "repositories": dict(sorted(repo_paths.items())),
        "deterministic_generation": True,
        "token_numbers_are_estimates": True,
        "token_instrumentation": {
            "version": INSTRUMENTATION_VERSION,
            "estimator": "chars_per_4_estimate",
            "fields": [
                "raw_prompt",
                "jarvis_context",
                "final_prompt_package",
                "answer_text",
            ],
        },
        "context_packet_format": packet_format_from_env(),
    }
    dump_json(manifest, os.path.join(run_root, "manifest.json"))
    _write_text(os.path.join(run_root, "README.md"), _readme(manifest))
    return manifest


def _score_template(task_id: str, mode: str) -> Dict[str, Any]:
    return {
        "task_id": task_id,
        "mode": mode,
        "correctness": None,
        "evidence_quality": None,
        "completeness": None,
        "hallucination_risk": None,
        "task_success": None,
        "true_positives": 0,
        "false_positives": 0,
        "false_negatives": 0,
        "notes": "",
    }


def _readme(manifest: Dict[str, Any]) -> str:
    return (
        f"# Phase 103 Benchmark Run: {manifest['run_id']}\n\n"
        "This package compares Codex Alone with JARVIS + Codex. It is fully offline "
        "and requires no API key.\n\n"
        "> Token numbers are estimates. Replace them with manual overrides when a "
        "trusted tool UI provides better counts.\n\n"
        "## Manual Workflow\n\n"
        "For each task directory:\n\n"
        "1. Run `codex_alone.prompt.md` in a fresh Codex session and save the answer "
        "under `answers/`.\n"
        "2. Record timing, model/tool, estimated token counts, and notes with "
        "`record-run` or by editing `run_log.codex_alone.json`.\n"
        "3. Repeat with `jarvis_plus_codex.prompt.md` in a fresh session.\n"
        "4. Score both answers with `score` or by editing the score JSON templates.\n"
        "5. Run `summary` to create `summary.json` and `summary.md`.\n\n"
        "```powershell\n"
        "py -3 -m builder_core.benchmark_framework.cli summary --run-dir <run-dir>\n"
        "```\n"
    )


def _write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
