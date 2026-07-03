"""Phase 104A — token accounting instrumentation tests."""

from __future__ import annotations

from pathlib import Path

from builder_core.benchmark_framework import cli
from builder_core.benchmark_framework.runner import build_prompt, generate_run_package
from builder_core.benchmark_framework.schema import RunLog, load_json, validate_run_log
from builder_core.benchmark_framework.summary import aggregate, render_markdown
from builder_core.benchmark_framework.tokens import (
    INSTRUMENTATION_VERSION,
    TokenBreakdown,
    attach_answer_to_breakdown,
    build_token_breakdown,
    estimate_tokens,
    prompt_metadata_comment,
)
from builder_core.tests.test_phase103_benchmark_framework import _log, _score, _task


def test_build_token_breakdown_labels_all_components():
    breakdown = build_token_breakdown(
        raw_prompt="Explain the repo.",
        atlas_context="MODE: bottleneck\nANSWER: hub",
        final_prompt_package="# Task\nExplain the repo.\n",
        answer_text="final answer text",
    )
    payload = breakdown.to_dict()
    assert payload["instrumentation_version"] == INSTRUMENTATION_VERSION
    assert payload["raw_prompt"]["estimated_tokens"] == estimate_tokens("Explain the repo.").estimated_tokens
    assert payload["atlas_context"]["estimated_tokens"] > 0
    assert payload["final_prompt_package"]["estimated_tokens"] > payload["raw_prompt"]["estimated_tokens"]
    assert payload["answer_text"]["estimated_tokens"] > 0


def test_prompt_metadata_comment_is_embedded_in_generated_package(tmp_path):
    task = _task()
    out = tmp_path / "benchmarks"
    generate_run_package([task], str(out), run_id="tok", atlas_context_fn=lambda _t: "CTX")
    task_root = out / "tok" / task.task_id
    for mode in ("codex_alone", "atlas_plus_codex"):
        prompt_text = (task_root / f"{mode}.prompt.md").read_text(encoding="utf-8")
        assert "token_estimate metadata" in prompt_text
        assert "raw_prompt_tokens:" in prompt_text
        assert "final_prompt_package_tokens:" in prompt_text
        if mode == "atlas_plus_codex":
            assert "atlas_context_tokens:" in prompt_text
            assert "CTX" in prompt_text
        breakdown = load_json(str(task_root / f"token_breakdown.{mode}.json"))
        assert breakdown["instrumentation_version"] == INSTRUMENTATION_VERSION
        log = RunLog.from_dict(load_json(str(task_root / f"run_log.{mode}.json")))
        assert log.token_breakdown["final_prompt_package"]["estimated_tokens"] == log.estimated_input_tokens
        assert validate_run_log(log.to_dict()) == []


def test_record_run_attaches_answer_tokens_without_changing_input(tmp_path):
    out = tmp_path / "benchmarks"
    generate_run_package([_task()], str(out), run_id="rec", atlas_context_fn=lambda _t: "CTX")
    run_dir = out / "rec"
    answer_file = tmp_path / "answer.txt"
    answer_file.write_text("structured answer with evidence", encoding="utf-8")
    log_before = RunLog.from_dict(load_json(str(run_dir / "ru_test" / "run_log.codex_alone.json")))
    input_before = log_before.estimated_input_tokens
    assert cli.main(
        [
            "record-run",
            "--run-dir",
            str(run_dir),
            "--task-id",
            "ru_test",
            "--mode",
            "codex_alone",
            "--model-tool-used",
            "Codex desktop",
            "--start-time",
            "2026-06-01T10:00:00",
            "--end-time",
            "2026-06-01T10:00:05",
            "--answer-file",
            str(answer_file),
        ]
    ) == 0
    log_after = RunLog.from_dict(load_json(str(run_dir / "ru_test" / "run_log.codex_alone.json")))
    assert log_after.estimated_input_tokens == input_before
    assert log_after.estimated_output_tokens > 0
    assert log_after.token_breakdown["answer_text"]["estimated_tokens"] == log_after.estimated_output_tokens
    breakdown_file = load_json(str(run_dir / "ru_test" / "token_breakdown.codex_alone.json"))
    assert breakdown_file["answer_text"]["estimated_tokens"] == log_after.estimated_output_tokens


def test_legacy_run_log_without_token_breakdown_still_validates():
    payload = _log("legacy", "codex_alone", 80, 4.0).to_dict()
    payload.pop("token_breakdown", None)
    assert validate_run_log(payload) == []
    restored = RunLog.from_dict(payload)
    assert restored.token_breakdown == {}


def test_summary_reports_average_input_output_and_reduction_by_mode():
    result = aggregate(
        [_log("one", "codex_alone", 200, 10), _log("one", "atlas_plus_codex", 100, 5)],
        [_score("one", "codex_alone"), _score("one", "atlas_plus_codex", 1)],
    )
    baseline = result["modes"]["codex_alone"]
    atlas = result["modes"]["atlas_plus_codex"]
    assert baseline["average_estimated_input_tokens"] == 190.0
    assert baseline["average_estimated_output_tokens"] == 10.0
    assert atlas["average_estimated_input_tokens"] == 90.0
    assert result["average_estimated_token_reduction_percent"] == 50.0
    markdown = render_markdown(result, run_id="sample")
    assert "Average estimated input tokens" in markdown
    assert "Average estimated output tokens" in markdown


def test_attach_answer_to_breakdown_preserves_existing_fields():
    base = build_token_breakdown(
        raw_prompt="q",
        atlas_context="",
        final_prompt_package="full",
    ).to_dict()
    updated = attach_answer_to_breakdown(base, "answer body")
    assert updated["raw_prompt"] == base["raw_prompt"]
    assert updated["answer_text"]["estimated_tokens"] > 0
    TokenBreakdown.from_dict(updated)
