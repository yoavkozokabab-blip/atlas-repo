"""Phase 104C-Fix2 — compact packet audit blocker regressions."""

from __future__ import annotations

import os
from pathlib import Path

from builder_core import ask, indexer
from builder_core.benchmark_framework.compact_packets import (
    HARD_TOKEN_CAPS,
    build_compact_packet,
    classify_evidence_ref,
    extract_facts_block,
    facts_fingerprint,
    measure_compact_corpus,
    packet_cap_compliant,
    REF_CLASS_CONCEPT,
    REF_CLASS_PATH,
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


def test_over_cap_packet_is_not_marked_compliant(tmp_path):
    root = _mini_repo(tmp_path)
    index = indexer.build_index(str(root))
    task = BenchmarkTask(
        task_id="plan02_verification",
        repo_id="fixture",
        repo_path=str(root),
        task_type="fix_planning",
        prompt="Plan a safe change to verification_evidence.py.",
        expected_answer="plan",
        scoring_rubric=["plan"],
        required_evidence=["verification_evidence.py", "confirmed_defect_gate.py"],
        baseline_mode="read-only",
        jarvis_mode="use jarvis",
    )
    result = ask.answer(index, task.prompt)
    compact, expanded, kind = build_compact_packet(result, task, index)
    cap = HARD_TOKEN_CAPS[kind]
    tokens = estimated_count(compact)
    if tokens > cap:
        assert expanded.get("cap_compliant") is False
        assert expanded.get("cap_overflow") is True
        assert "OVERFLOW|" in compact
        assert packet_cap_compliant(compact, kind) is False
    else:
        assert expanded.get("cap_compliant") is True
        assert packet_cap_compliant(compact, kind) is True


def test_contract_rows_not_synthesized_from_prompt_keywords(tmp_path):
    root = _mini_repo(tmp_path)
    index = indexer.build_index(str(root))
    task = BenchmarkTask(
        task_id="contract01_sources",
        repo_id="fixture",
        repo_path=str(root),
        task_type="contract_analysis",
        prompt="Which source kinds produce contract facts? Mention type_hint and assert in prose only.",
        expected_answer="sources",
        scoring_rubric=["sources"],
        required_evidence=["typed.py"],
        baseline_mode="read-only",
        jarvis_mode="use jarvis",
    )
    result = ask.answer(index, task.prompt)
    compact, expanded, kind = build_compact_packet(result, task, index)
    assert "CONTRACT_STATUS|" in compact
    if "CONTRACT_SRC|" in compact:
        assert "ORIGIN=extracted" in compact
        assert "TRUST=review_only" not in compact
    assert expanded.get("contract_status") in {"extracted", "none_extracted", "disabled"}
    assert "ORIGIN=analysis_finding" not in compact
    assert "TYPE=inconsistent_return" not in compact or "PROVENANCE=contract_facts" in compact


def test_risk01_and_risk02_packets_are_substantively_different(tmp_path):
    root = _mini_repo(tmp_path)
    index = indexer.build_index(str(root))
    risk01 = BenchmarkTask(
        task_id="risk01_ranking",
        repo_id="fixture",
        repo_path=str(root),
        task_type="architectural_risk",
        prompt="How does Builder Core rank architectural risk?",
        expected_answer="ranking",
        scoring_rubric=["ranking"],
        required_evidence=["builder_core/architectural_risk.py"],
        baseline_mode="read-only",
        jarvis_mode="use jarvis",
    )
    risk02 = BenchmarkTask(
        task_id="risk02_centrality_vs_risk",
        repo_id="fixture",
        repo_path=str(root),
        task_type="architectural_risk",
        prompt="Why is fan-in alone insufficient for architectural risk?",
        expected_answer="centrality",
        scoring_rubric=["centrality"],
        required_evidence=["fan-in", "LOC", "cycle"],
        baseline_mode="read-only",
        jarvis_mode="use jarvis",
    )
    compact01, _, _ = build_compact_packet(ask.answer(index, risk01.prompt), risk01, index)
    compact02, _, _ = build_compact_packet(ask.answer(index, risk02.prompt), risk02, index)
    assert "RANK_META|" in compact01
    assert "MODULE|" in compact01
    assert "CENTRALITY|" in compact02
    assert "LIMIT|CODE=FAN_IN_NOT_SUFFICIENT" in compact02
    assert "RANK_META|" not in compact02
    assert compact01 != compact02
    assert facts_fingerprint(compact01) != facts_fingerprint(compact02)


def test_missing_contract_facts_emit_none_extracted(tmp_path):
    root = tmp_path / "repo"
    _write(root / "empty.py", "x = 1\n")
    index = indexer.build_index(str(root))
    task = BenchmarkTask(
        task_id="contract_empty",
        repo_id="fixture",
        repo_path=str(root),
        task_type="contract_analysis",
        prompt="Contract facts for empty.py",
        expected_answer="none",
        scoring_rubric=["none"],
        required_evidence=["empty.py"],
        baseline_mode="read-only",
        jarvis_mode="use jarvis",
    )
    compact, expanded, _kind = build_compact_packet(ask.answer(index, task.prompt), task, index)
    assert "CONTRACT_STATUS|VALUE=none_extracted" in compact
    assert "PROVENANCE=contract_facts" not in compact
    assert expanded.get("contract_status") == "none_extracted"
    assert expanded.get("contract_row_count", 0) == 0


def test_concept_refs_do_not_resolve_to_silent_paths(tmp_path):
    root = _mini_repo(tmp_path)
    index = indexer.build_index(str(root))
    assert classify_evidence_ref("impact") == REF_CLASS_CONCEPT
    assert classify_evidence_ref("config.py") == REF_CLASS_PATH
    task = BenchmarkTask(
        task_id="impact_concept",
        repo_id="fixture",
        repo_path=str(root),
        task_type="impact_analysis",
        prompt="Blast radius using impact and depend concepts",
        expected_answer="impact",
        scoring_rubric=["impact"],
        required_evidence=["impact", "depend"],
        baseline_mode="read-only",
        jarvis_mode="use jarvis",
    )
    compact, _expanded, _kind = build_compact_packet(ask.answer(index, task.prompt), task, index)
    assert "CONCEPT_REF|REF=impact" in compact
    assert "CONCEPT_REF|REF=depend" in compact
    assert "TARGET|PATH=impact" not in compact


def test_distinct_subject_dependency_tasks_have_different_facts(tmp_path):
    tasks = load_tasks(TASKS_PATH)
    dep_ids = ("dep01_engine_edges", "dep02_ask_edges", "dep03_evidence_chain")
    repo_root = Path(__file__).resolve().parents[2]
    from builder_core.store import load_index

    index = load_index(str(repo_root))
    fingerprints: dict[str, str] = {}
    for task in tasks:
        if task.task_id not in dep_ids:
            continue
        normalized = BenchmarkTask(**{**task.to_dict(), "repo_path": str(repo_root)})
        compact, _, _ = build_compact_packet(ask.answer(index, normalized.prompt), normalized, index)
        fingerprints[task.task_id] = facts_fingerprint(compact)
        assert extract_facts_block(compact).strip()
    assert len({fingerprints[tid] for tid in dep_ids}) == 3


def test_ambiguous_required_evidence_emits_ambiguous_ref(tmp_path):
    root = tmp_path / "repo"
    _write(root / "alpha" / "config.py", "X = 1\n")
    _write(root / "beta" / "config.py", "Y = 2\n")
    index = indexer.build_index(str(root))
    task = BenchmarkTask(
        task_id="ambig_config",
        repo_id="fixture",
        repo_path=str(root),
        task_type="impact_analysis",
        prompt="Impact of config.py",
        expected_answer="impact",
        scoring_rubric=["impact"],
        required_evidence=["config.py"],
        baseline_mode="read-only",
        jarvis_mode="use jarvis",
    )
    result = ask.answer(index, task.prompt)
    compact, _expanded, kind = build_compact_packet(result, task, index)
    assert "AMBIGUOUS_REF|" in compact
    assert "alpha/config.py" in compact or "beta/config.py" in compact
    assert "TARGET|PATH=alpha/config.py" not in compact or "TARGET|PATH=beta/config.py" not in compact


def test_cap_compliant_requires_actual_estimate_within_cap(tmp_path):
    root = _mini_repo(tmp_path)
    index = indexer.build_index(str(root))
    task = BenchmarkTask(
        task_id="dep_local",
        repo_id="fixture",
        repo_path=str(root),
        task_type="dependency_analysis",
        prompt="Dependencies for config.py",
        expected_answer="deps",
        scoring_rubric=["deps"],
        required_evidence=["config.py"],
        baseline_mode="read-only",
        jarvis_mode="use jarvis",
    )
    result = ask.answer(index, task.prompt)
    compact, expanded, kind = build_compact_packet(result, task, index)
    cap = HARD_TOKEN_CAPS[kind]
    assert expanded.get("cap_compliant") == (estimated_count(compact) <= cap)
    assert packet_cap_compliant(compact, kind) == (estimated_count(compact) <= cap)


def test_frozen_corpus_fix2_gates():
    from builder_core.store import load_index

    tasks = load_tasks(TASKS_PATH)
    repo_root = Path(__file__).resolve().parents[2]
    normalized = [
        BenchmarkTask(**{**task.to_dict(), "repo_path": str(repo_root)}) for task in tasks
    ]
    metrics = measure_compact_corpus(normalized, shared_index=load_index(str(repo_root)))
    assert metrics["meets_forty_percent_reduction"] is True
    assert metrics["cap_compliance_pass"] is True
    assert metrics["evidence_preservation_pass"] is True
    for row in metrics["tasks"]:
        assert row["cap_compliant"] is True
        assert row["compact_tokens"] <= row["token_cap"]
    assert metrics["instrumentation_version"] == "phase104c-truth-v1"


def test_frozen_corpus_distinct_subject_facts_blocks():
    from builder_core.store import load_index

    tasks = load_tasks(TASKS_PATH)
    repo_root = Path(__file__).resolve().parents[2]
    index = load_index(str(repo_root))
    groups = [
        ("dep01_engine_edges", "dep02_ask_edges", "dep03_evidence_chain"),
        ("ru01_subsystems", "ru02_builder_core_map", "ru03_voice_path"),
        ("impact01_config", "impact02_engine", "impact03_contract_facts"),
        ("risk01_ranking", "risk02_centrality_vs_risk"),
    ]
    for group in groups:
        fingerprints = []
        for task in tasks:
            if task.task_id not in group:
                continue
            normalized = BenchmarkTask(**{**task.to_dict(), "repo_path": str(repo_root)})
            compact, _, _ = build_compact_packet(
                ask.answer(index, normalized.prompt), normalized, index
            )
            fingerprints.append(facts_fingerprint(compact))
        assert len(fingerprints) == len(group)
        assert len(set(fingerprints)) == len(group)
