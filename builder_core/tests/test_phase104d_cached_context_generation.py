"""Phase 104D — cached benchmark context generation tests."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from builder_core import ask, indexer
from builder_core.benchmark_framework.compact_packets import build_compact_packet
from builder_core.benchmark_framework.context_cache import (
    BenchmarkContextSession,
    cache_enabled_from_env,
    cache_key,
)
from builder_core.benchmark_framework.context_profiling import profile_atlas_context
from builder_core.benchmark_framework.runner import (
    clear_benchmark_context_sessions,
    generate_run_package,
    get_benchmark_context_session,
)
from builder_core.benchmark_framework.schema import BenchmarkTask, load_json
from builder_core.tests.test_phase103_benchmark_framework import _task


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _mini_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    _write(root / "config.py", "def load():\n    return {}\n")
    _write(root / "core" / "util.py", "def helper():\n    return 1\n")
    _write(
        root / "a.py",
        "from core.util import helper\n\ndef run():\n    return helper()\n",
    )
    _write(
        root / "tests" / "test_core.py",
        "from core.util import helper\n\ndef test_helper():\n    assert helper()\n",
    )
    return root


@pytest.fixture(autouse=True)
def _reset_context_cache_state(monkeypatch):
    monkeypatch.delenv("Atlas_BENCHMARK_CONTEXT_CACHE", raising=False)
    clear_benchmark_context_sessions()
    cache_root_glob = ".atlas_builder/benchmark_context_cache"
    yield
    clear_benchmark_context_sessions()
    monkeypatch.delenv("Atlas_BENCHMARK_CONTEXT_CACHE", raising=False)


@pytest.fixture
def cache_on(monkeypatch):
    monkeypatch.setenv("Atlas_BENCHMARK_CONTEXT_CACHE", "1")
    assert cache_enabled_from_env()


def test_second_graph_load_uses_cache_hit(cache_on, tmp_path):
    root = _mini_repo(tmp_path)
    index = indexer.build_index(str(root))
    session = BenchmarkContextSession(str(root), index, enabled=True)
    session.get_dependency_graph()
    stages = session.diagnostics_dict()["stages"]["dependency_graph"]
    assert stages["misses"] == 1
    session.get_dependency_graph()
    stages = session.diagnostics_dict()["stages"]["dependency_graph"]
    assert stages["hits"] == 1


def test_file_change_invalidates_disk_cache(cache_on, tmp_path):
    root = _mini_repo(tmp_path)
    index = indexer.build_index(str(root))
    session = BenchmarkContextSession(str(root), index, enabled=True, packet_format="compact")
    session.get_dependency_graph()
    cache_dir = root / ".atlas_builder" / "benchmark_context_cache"
    assert cache_dir.is_dir()
    before = list(cache_dir.glob("*.json"))
    assert before

    target = root / "a.py"
    target.write_text(target.read_text(encoding="utf-8") + "\n# touched\n", encoding="utf-8")
    index2 = indexer.build_index(str(root))
    session2 = BenchmarkContextSession(str(root), index2, enabled=True, packet_format="compact")
    assert session2.fingerprint() != session.fingerprint()
    session2.get_dependency_graph()
    assert session2.diagnostics_dict()["stages"]["dependency_graph"]["misses"] == 1
    after = {path.name for path in cache_dir.glob("*.json")}
    assert len(after) >= len(before)


def test_compact_and_prose_use_separate_cache_artifacts(cache_on, tmp_path):
    root = _mini_repo(tmp_path)
    index = indexer.build_index(str(root))
    compact_session = BenchmarkContextSession(str(root), index, enabled=True, packet_format="compact")
    prose_session = BenchmarkContextSession(str(root), index, enabled=True, packet_format="prose")
    compact_session.get_dependency_graph()
    prose_session.get_dependency_graph()

    fingerprint = compact_session.fingerprint()
    compact_key = cache_key("dependency_graph", str(root), fingerprint, "compact")
    prose_key = cache_key("dependency_graph", str(root), fingerprint, "prose")
    assert compact_key != prose_key
    cache_dir = root / ".atlas_builder" / "benchmark_context_cache"
    assert (cache_dir / compact_key).is_file()
    assert (cache_dir / prose_key).is_file()


def test_context_profile_includes_cache_diagnostics(cache_on, tmp_path):
    root = _mini_repo(tmp_path)
    task = _task()
    task.repo_path = str(root)
    task.task_id = "cache_profile_task"
    out_dir = tmp_path / "runs"
    manifest = generate_run_package([task], str(out_dir), run_id="cache_run")
    profile_path = out_dir / "cache_run" / task.task_id / "context_profile.json"
    assert profile_path.is_file()
    payload = load_json(str(profile_path))
    cache = payload.get("cache", {})
    assert cache.get("enabled") is True
    assert "stages" in cache
    assert "dependency_graph" in cache["stages"]


def test_profile_atlas_context_writes_cache_block(cache_on, tmp_path):
    root = _mini_repo(tmp_path)
    index = indexer.build_index(str(root))
    task = BenchmarkTask(
        task_id="profile_cache",
        repo_id="fixture",
        repo_path=str(root),
        task_type="dependency_analysis",
        prompt="Summarize import relationships for config.py.",
        expected_answer="edges",
        scoring_rubric=["mentions imports"],
        required_evidence=["config.py"],
        baseline_mode="read-only",
        atlas_mode="use atlas",
    )
    profile = profile_atlas_context(task, index=index)
    payload = profile.to_dict()
    assert "cache" in payload
    assert payload["cache"]["enabled"] is True


def test_cached_second_compact_build_is_faster_or_hits(cache_on, tmp_path):
    root = _mini_repo(tmp_path)
    index = indexer.build_index(str(root))
    task = BenchmarkTask(
        task_id="arch_cache",
        repo_id="fixture",
        repo_path=str(root),
        task_type="architectural_risk",
        prompt="Rank architectural risk modules.",
        expected_answer="ranked",
        scoring_rubric=["fan-in"],
        required_evidence=["core/util.py"],
        baseline_mode="read-only",
        atlas_mode="use atlas",
    )
    result = ask.answer(index, task.prompt)
    session = get_benchmark_context_session(str(root), index, packet_format="compact")
    build_compact_packet(result, task, index, session=session)
    start = time.perf_counter()
    build_compact_packet(result, task, index, session=session)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    stats = session.diagnostics_dict()["stages"]["dependency_graph"]
    assert stats["hits"] >= 1 or elapsed_ms < 50.0
