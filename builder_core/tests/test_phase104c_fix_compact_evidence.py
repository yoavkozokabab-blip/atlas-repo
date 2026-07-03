"""Phase 104C-Fix — compact packet evidence preservation regressions."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from builder_core import ask, indexer
from builder_core.benchmark_framework.compact_packets import (
    HARD_TOKEN_CAPS,
    build_compact_packet,
    compare_formats_enabled,
    format_atlas_context,
    measure_compact_corpus,
    packet_cap_compliant,
    resolve_packet_kind,
)
from builder_core.benchmark_framework.schema import BenchmarkTask, load_tasks
from builder_core.benchmark_framework.tokens import estimated_count

TASKS_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "benchmark_framework",
    "data",
    "benchmark_tasks_v1.json",
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _mini_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    _write(root / "config.py", "def load():\n    return {}\n")
    _write(root / "core" / "util.py", "def helper():\n    return 1\n")
    _write(
        root / "builder_core" / "bug_intelligence" / "contract_facts.py",
        "def enabled() -> bool:\n    assert True\n    return True\n",
    )
    _write(
        root / "typed.py",
        "def add(x: int) -> int:\n    assert x >= 0\n    return x + 1\n",
    )
    _write(root / "a.py", "from core.util import helper\n\ndef run():\n    return helper()\n")
    return root


def test_cap_enforcement_reserves_metadata(tmp_path):
    root = _mini_repo(tmp_path)
    index = indexer.build_index(str(root))
    task = BenchmarkTask(
        task_id="risk_local",
        repo_id="fixture",
        repo_path=str(root),
        task_type="architectural_risk",
        prompt="Rank architectural risk.",
        expected_answer="ranked",
        scoring_rubric=["ranked"],
        required_evidence=["core/util.py"],
        baseline_mode="read-only",
        atlas_mode="use atlas",
    )
    result = ask.answer(index, task.prompt)
    compact, expanded, kind = build_compact_packet(result, task, index)
    cap = HARD_TOKEN_CAPS[kind]
    assert expanded.get("cap_compliant") == (estimated_count(compact) <= cap)
    if expanded.get("truncated"):
        assert "TRUNCATED|EMITTED=" in compact
        assert "DETAIL|PATH=context_packet.expanded.json" in compact


def test_arch_risk_packet_keeps_references(tmp_path):
    root = _mini_repo(tmp_path)
    index = indexer.build_index(str(root))
    task = BenchmarkTask(
        task_id="risk01_ranking",
        repo_id="fixture",
        repo_path=str(root),
        task_type="architectural_risk",
        prompt="Rank modules by architectural risk.",
        expected_answer="ranked",
        scoring_rubric=["ranked"],
        required_evidence=["core/util.py"],
        baseline_mode="read-only",
        atlas_mode="use atlas",
    )
    result = ask.answer(index, task.prompt)
    compact, _expanded, kind = build_compact_packet(result, task, index)
    assert kind == "ARCH_RISK"
    assert compact.count("REF|") >= 1


def test_contract_packet_preserves_source_kinds(tmp_path):
    root = _mini_repo(tmp_path)
    index = indexer.build_index(str(root))
    task = BenchmarkTask(
        task_id="contract01_sources",
        repo_id="fixture",
        repo_path=str(root),
        task_type="contract_analysis",
        prompt="Which source kinds produce contract facts?",
        expected_answer="sources",
        scoring_rubric=["sources"],
        required_evidence=["typed.py", "builder_core/bug_intelligence/contract_facts.py"],
        baseline_mode="read-only",
        atlas_mode="use atlas",
    )
    result = ask.answer(index, task.prompt)
    compact, _expanded, kind = build_compact_packet(result, task, index)
    assert kind == "CONTRACT"
    assert "CONTRACT_STATUS|" in compact
    if "CONTRACT_SRC|" in compact:
        assert "ORIGIN=extracted" in compact
    assert "USAGE_CONTRACT_NOT_PROVEN" in compact
    assert "REF|" in compact


def test_defect_packet_includes_buggy_and_fixed_fixtures(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    pair_root = (
        repo_root
        / "builder_core"
        / "benchmarks"
        / "holdout"
        / "pairs"
        / "classic_wrong_operator"
    )
    rel = Path("builder_core/benchmarks/holdout/pairs/classic_wrong_operator")
    root = tmp_path / "repo"
    _write(root / rel / "buggy.py", (pair_root / "buggy.py").read_text(encoding="utf-8"))
    _write(root / rel / "fixed.py", (pair_root / "fixed.py").read_text(encoding="utf-8"))
    task = BenchmarkTask(
        task_id="defect01_wrong_operator",
        repo_id="fixture",
        repo_path=str(root),
        task_type="confirmed_defect_detection",
        prompt="Compare classic_wrong_operator/buggy.py with fixed.py.",
        expected_answer="operator defect",
        scoring_rubric=["diff"],
        required_evidence=[
            "classic_wrong_operator/buggy.py",
            "classic_wrong_operator/fixed.py",
        ],
        baseline_mode="read-only",
        atlas_mode="use atlas",
    )
    index = indexer.build_index(str(root))
    result = ask.answer(index, task.prompt)
    compact, expanded, kind = build_compact_packet(result, task, index)
    assert kind == "DEFECT_REVIEW"
    assert "FIXTURE|VARIANT=buggy" in compact
    assert "FIXTURE|VARIANT=fixed" in compact
    assert "classic_wrong_operator" in compact
    assert expanded.get("buggy_path")
    assert expanded.get("fixed_path")
    assert "DIFF|SUMMARY=" in compact


def test_impact_resolves_abbreviated_module_path(tmp_path):
    root = _mini_repo(tmp_path)
    index = indexer.build_index(str(root))
    task = BenchmarkTask(
        task_id="impact03_contract_facts",
        repo_id="fixture",
        repo_path=str(root),
        task_type="impact_analysis",
        prompt="Impact of changing contract_facts.py",
        expected_answer="impact",
        scoring_rubric=["impact"],
        required_evidence=["contract_facts.py"],
        baseline_mode="read-only",
        atlas_mode="use atlas",
    )
    result = ask.answer(index, task.prompt)
    compact, expanded, kind = build_compact_packet(result, task, index)
    assert kind == "IMPACT"
    assert "builder_core/bug_intelligence/contract_facts.py" in compact
    assert expanded.get("target_resolution") in {"exact", "resolved", "ambiguous"}


def test_verify_packet_excludes_corpus_paths(tmp_path):
    root = _mini_repo(tmp_path)
    index = indexer.build_index(str(root))
    task = BenchmarkTask(
        task_id="verify01_evidence_types",
        repo_id="fixture",
        repo_path=str(root),
        task_type="verification_evidence",
        prompt="What verification evidence types exist?",
        expected_answer="types",
        scoring_rubric=["types"],
        required_evidence=["test_evidence", "verification_evidence.py"],
        baseline_mode="read-only",
        atlas_mode="use atlas",
    )
    result = {
        "mode": "retrieval",
        "answer": "verification types",
        "evidence": [
            "data/real_repo_corpus/phase98a/attrs/docs/types.md:1: heading",
            "builder_core/bug_intelligence/verification_evidence.py:10: EVIDENCE_TYPES",
        ],
        "sources": [
            "data/real_repo_corpus/phase98a/attrs/docs/types.md",
            "builder_core/bug_intelligence/verification_evidence.py",
        ],
    }
    compact, _expanded, kind = build_compact_packet(result, task, index)
    assert kind == "VERIFY"
    assert "real_repo_corpus" not in compact
    assert "EVIDENCE_TYPE|" in compact


def test_task_specific_packets_differ_by_focus(tmp_path):
    root = _mini_repo(tmp_path)
    index = indexer.build_index(str(root))
    risk_task = BenchmarkTask(
        task_id="risk03_cycles",
        repo_id="fixture",
        repo_path=str(root),
        task_type="architectural_risk",
        prompt="Explain import cycles.",
        expected_answer="cycles",
        scoring_rubric=["cycles"],
        required_evidence=["builder_core/bug_intelligence/depgraph.py"],
        baseline_mode="read-only",
        atlas_mode="use atlas",
    )
    impact_task = BenchmarkTask(
        task_id="impact01_config",
        repo_id="fixture",
        repo_path=str(root),
        task_type="impact_analysis",
        prompt="Impact of config.py",
        expected_answer="impact",
        scoring_rubric=["impact"],
        required_evidence=["config.py"],
        baseline_mode="read-only",
        atlas_mode="use atlas",
    )
    risk_compact, _, _ = build_compact_packet(ask.answer(index, risk_task.prompt), risk_task, index)
    impact_compact, _, _ = build_compact_packet(ask.answer(index, impact_task.prompt), impact_task, index)
    assert "TASK|ID=risk03_cycles|FOCUS=import_cycles" in risk_compact
    assert "TASK|ID=impact01_config|FOCUS=" not in risk_compact or "subsystem" not in risk_compact
    assert "KIND=IMPACT" in impact_compact
    assert risk_compact != impact_compact


def test_prose_mode_skips_compact_comparison_by_default(tmp_path, monkeypatch):
    root = _mini_repo(tmp_path)
    monkeypatch.delenv("Atlas_CONTEXT_COMPARE_FORMATS", raising=False)
    index = indexer.build_index(str(root))
    task = BenchmarkTask(
        task_id="t1",
        repo_id="fixture",
        repo_path=str(root),
        task_type="repository_understanding",
        prompt="What subsystems exist?",
        expected_answer="subsystems",
        scoring_rubric=["subsystems"],
        required_evidence=["core/"],
        baseline_mode="read-only",
        atlas_mode="use atlas",
    )
    result = ask.answer(index, task.prompt)
    assert compare_formats_enabled("prose") is False
    _prose, meta = format_atlas_context(result, task, index, packet_format="prose")
    assert meta["comparison"].get("comparison_skipped") is True
    assert meta["comparison"].get("compact_tokens") is None


def test_frozen_corpus_cap_and_reduction_gates():
    from builder_core.store import load_index

    tasks = load_tasks(TASKS_PATH)
    repo_root = Path(__file__).resolve().parents[2]
    normalized = [
        BenchmarkTask(**{**task.to_dict(), "repo_path": str(repo_root)}) for task in tasks
    ]
    shared_index = load_index(str(repo_root))
    metrics = measure_compact_corpus(normalized, shared_index=shared_index)
    assert metrics["meets_forty_percent_reduction"] is True
    assert metrics["compact_tokens"] <= 6000
    assert metrics["cap_compliance_pass"] is True
    assert metrics["evidence_preservation_pass"] is True
    for row in metrics["tasks"]:
        assert row["cap_compliant"] is True
