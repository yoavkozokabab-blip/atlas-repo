"""Phase 104C — compact fact packet tests."""

from __future__ import annotations

import os
from pathlib import Path

from builder_core import ask, indexer
from builder_core.benchmark_framework.compact_packets import (
    build_compact_packet,
    compare_context_formats,
    format_jarvis_context,
    packet_format_from_env,
    resolve_packet_kind,
)
from builder_core.benchmark_framework.jarvis_packet import format_jarvis_packet
from builder_core.benchmark_framework.runner import build_prompt, generate_run_package
from builder_core.benchmark_framework.schema import BenchmarkTask, load_json
from builder_core.tests.test_phase103_benchmark_framework import _task


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _mini_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    _write(root / "config.py", "def load():\n    return {}\n")
    _write(root / "core" / "util.py", "def helper():\n    return 1\n")
    _write(root / "a.py", "from core.util import helper\n\ndef run():\n    return helper()\n")
    _write(root / "tests" / "test_core.py", "from core.util import helper\n\ndef test_helper():\n    assert helper()\n")
    return root


def test_compact_packet_is_smaller_than_verbose(tmp_path):
    root = _mini_repo(tmp_path)
    index = indexer.build_index(str(root))
    task = BenchmarkTask(
        task_id="risk_local",
        repo_id="fixture",
        repo_path=str(root),
        task_type="architectural_risk",
        prompt="Rank the top architectural risk modules using dependency graph fan-in and import cycles.",
        expected_answer="hub ranks high",
        scoring_rubric=["Uses fan-in"],
        required_evidence=["core/util.py"],
        baseline_mode="read-only",
        jarvis_mode="use jarvis",
    )
    result = ask.answer(index, task.prompt)
    comparison = compare_context_formats(result, task, index)
    assert comparison["compact_tokens"] < comparison["verbose_tokens"]
    assert comparison["reduction_percent"] >= 50.0


def test_uncertainty_caveats_preserved_in_compact(tmp_path):
    root = _mini_repo(tmp_path)
    index = indexer.build_index(str(root))
    task = _task()
    task.repo_path = str(root)
    result = ask.answer(index, task.prompt)
    compact, _expanded, _kind = build_compact_packet(result, task, index)
    assert "CAVEAT|" in compact or "MODE=" in compact


def test_impact_task_gets_impact_packet_not_arch_ranking(tmp_path):
    root = _mini_repo(tmp_path)
    index = indexer.build_index(str(root))
    task = BenchmarkTask(
        task_id="impact_config",
        repo_id="fixture",
        repo_path=str(root),
        task_type="impact_analysis",
        prompt="Assess the blast radius of changing config.py.",
        expected_answer="dependents listed",
        scoring_rubric=["names dependents"],
        required_evidence=["config.py"],
        baseline_mode="read-only",
        jarvis_mode="use jarvis",
    )
    result = ask.answer(index, task.prompt)
    kind = resolve_packet_kind(task, result)
    assert kind == "IMPACT"
    compact, _expanded, packet_kind = build_compact_packet(result, task, index)
    assert packet_kind == "IMPACT"
    assert "TARGET|PATH=config.py" in compact
    assert compact.count("MODULE|") <= 1


def test_task_specific_packet_kinds_differ(tmp_path):
    root = _mini_repo(tmp_path)
    index = indexer.build_index(str(root))
    risk_task = BenchmarkTask(
        task_id="risk_a",
        repo_id="fixture",
        repo_path=str(root),
        task_type="architectural_risk",
        prompt="Rank architectural risk modules by fan-in.",
        expected_answer="ranked",
        scoring_rubric=["ranked"],
        required_evidence=["core/util.py"],
        baseline_mode="read-only",
        jarvis_mode="use jarvis",
    )
    impact_task = BenchmarkTask(
        task_id="impact_a",
        repo_id="fixture",
        repo_path=str(root),
        task_type="impact_analysis",
        prompt="What breaks if config.py changes?",
        expected_answer="impact",
        scoring_rubric=["impact"],
        required_evidence=["config.py"],
        baseline_mode="read-only",
        jarvis_mode="use jarvis",
    )
    risk_result = ask.answer(index, risk_task.prompt)
    impact_result = ask.answer(index, impact_task.prompt)
    risk_compact, _, _ = build_compact_packet(risk_result, risk_task, index)
    impact_compact, _, _ = build_compact_packet(impact_result, impact_task, index)
    assert risk_compact != impact_compact
    assert "KIND=ARCH_RISK" in risk_compact
    assert "KIND=IMPACT" in impact_compact


def test_prose_fallback_via_env_and_runner(tmp_path, monkeypatch):
    from builder_core.benchmark_framework import runner

    root = _mini_repo(tmp_path)
    monkeypatch.delenv("JARVIS_CONTEXT_PACKET_FORMAT", raising=False)
    assert packet_format_from_env() == "prose"
    index = indexer.build_index(str(root))
    task = _task()
    task.repo_path = str(root)
    result = ask.answer(index, task.prompt)
    prose, meta = format_jarvis_context(result, task, index, packet_format="prose")
    assert prose.startswith("MODE:")
    assert meta["comparison"]["selected_format"] == "prose"
    assert "ANSWER:" in prose

    runner._INDEX_CACHE.clear()
    out = tmp_path / "benchmarks"
    generate_run_package([task], str(out), run_id="prose_run")
    comparison_path = out / "prose_run" / task.task_id / "context_token_comparison.json"
    assert comparison_path.is_file()


def test_compact_mode_writes_comparison_sidecar(tmp_path, monkeypatch):
    from builder_core.benchmark_framework import runner

    root = _mini_repo(tmp_path)
    task = _task()
    task.repo_path = str(root)
    monkeypatch.setenv("JARVIS_CONTEXT_PACKET_FORMAT", "compact")
    runner._INDEX_CACHE.clear()
    out = tmp_path / "benchmarks"
    generate_run_package([task], str(out), run_id="compact_run")
    task_root = out / "compact_run" / task.task_id
    comparison = load_json(str(task_root / "context_token_comparison.json"))
    assert comparison["compact_tokens"] < comparison["verbose_tokens"]
    prompt = (task_root / "jarvis_plus_codex.prompt.md").read_text(encoding="utf-8")
    assert "PACKET|V=1" in prompt
    context_block = prompt.split("## Precomputed JARVIS Context", 1)[-1]
    packet_body = context_block.split("```", 2)[1].strip()
    assert packet_body.startswith("PACKET|V=1")
    assert "```" not in packet_body
