"""Phase 104B — context generation profiling tests."""

from __future__ import annotations

from pathlib import Path

from builder_core.benchmark_framework.context_profiling import (
    PROFILING_VERSION,
    STAGE_NAMES,
    aggregate_stage_measurements,
    profile_atlas_context,
    render_profile_report,
)
from builder_core.benchmark_framework.atlas_packet import format_atlas_packet
from builder_core.benchmark_framework.runner import default_atlas_context
from builder_core.tests.test_phase103_benchmark_framework import _task


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _mini_index_loader(root: str):
    from builder_core import indexer

    return indexer.build_index(root)


def test_profile_records_all_stages(tmp_path):
    root = tmp_path / "repo"
    _write(root / "core" / "util.py", "def helper():\n    return 1\n")
    _write(root / "a.py", "from core.util import helper\n\ndef run():\n    return helper()\n")
    _write(root / "README.md", "# sample\n")
    task = _task()
    task.repo_path = str(root)
    profile = profile_atlas_context(task, index_loader=_mini_index_loader)
    names = [stage.name for stage in profile.stages]
    assert names == list(STAGE_NAMES)
    payload = profile.to_dict()
    assert payload["profiling_version"] == PROFILING_VERSION
    total_percent = sum(stage.percent_of_total_tokens for stage in profile.stages)
    assert 99.0 <= total_percent <= 101.0 or total_percent == 0.0
    assert profile.packet_total_tokens > 0
    assert profile.ask_mode


def test_format_atlas_packet_matches_default_context_shape(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    _write(root / "m.py", "def f():\n    return 0\n")
    task = _task()
    task.repo_path = str(root)

    fake_result = {
        "mode": "retrieval",
        "answer": "sample answer",
        "evidence": ["m.py: evidence"],
        "sources": ["m.py"],
        "ask_quality": {"production_percent": 100},
    }

    monkeypatch.setattr("builder_core.ask.answer", lambda _index, _q: fake_result)
    monkeypatch.setattr("builder_core.benchmark_framework.runner._INDEX_CACHE", {})
    packet_via_runner = default_atlas_context(task)
    packet_via_formatter = format_atlas_packet(fake_result)
    assert packet_via_runner == packet_via_formatter


def test_render_profile_report_lists_top_contributors(tmp_path):
    root = tmp_path / "repo"
    _write(root / "m.py", "def f():\n    return 0\n")
    task = _task()
    task.repo_path = str(root)
    profile = profile_atlas_context(task, index_loader=_mini_index_loader)
    markdown = render_profile_report([profile], title="Test Profile")
    assert "Top 20 largest token contributors" in markdown
    assert "Top 20 slowest contributors" in markdown
    assert "index_loading" in markdown
    rows = aggregate_stage_measurements([profile])
    assert rows
    assert rows[0]["stage"] in STAGE_NAMES
