"""Phase 103 offline benchmark framework tests."""

from __future__ import annotations

from pathlib import Path

from builder_core.benchmark_framework import cli
from builder_core.benchmark_framework.runner import build_prompt, generate_run_package
from builder_core.benchmark_framework.schema import (
    MODES,
    TASK_TYPES,
    BenchmarkTask,
    ManualScore,
    RunLog,
    load_json,
    load_tasks,
    validate_run_log,
    validate_task,
    validate_task_file,
)
from builder_core.benchmark_framework.scoring import aggregate_bug_accuracy, build_manual_score
from builder_core.benchmark_framework.summary import aggregate, render_markdown
from builder_core.benchmark_framework.tokens import estimate_tokens, estimated_count


def _task() -> BenchmarkTask:
    return BenchmarkTask(
        task_id="ru_test",
        repo_id="fixture",
        repo_path=".",
        task_type="repository_understanding",
        prompt="Explain the repository structure.",
        expected_answer="Names source and tests.",
        scoring_rubric=["Names source.", "Names tests."],
        required_evidence=["src/", "tests/"],
        baseline_mode="Use read-only tools.",
        atlas_mode="Verify Atlas evidence.",
    )


def _log(task_id: str, mode: str, tokens: int, elapsed: float) -> RunLog:
    return RunLog(
        task_id=task_id,
        mode=mode,
        model_tool_used="Codex desktop",
        start_time="2026-06-01T10:00:00",
        end_time="2026-06-01T10:00:10",
        elapsed_seconds=elapsed,
        estimated_input_tokens=tokens - 10,
        estimated_output_tokens=10,
        raw_answer_path=f"answers/{task_id}.{mode}.txt",
        score_path=f"score.{mode}.json",
    )


def _score(task_id: str, mode: str, total_bias: float = 0.0) -> ManualScore:
    return ManualScore(
        task_id=task_id,
        mode=mode,
        correctness=4.0 + total_bias,
        evidence_quality=4.0,
        completeness=4.0,
        hallucination_risk=1.0,
        task_success=True,
        true_positives=1,
    )


def test_sample_schema_has_twenty_local_tasks_and_all_task_types():
    failures = validate_task_file(cli.DEFAULT_TASKS)
    tasks = load_tasks(cli.DEFAULT_TASKS)
    assert failures == {}
    assert len(tasks) >= 20
    assert {task.repo_id for task in tasks} == {"local_atlas"}
    assert set(TASK_TYPES).issubset({task.task_type for task in tasks})


def test_schema_validation_rejects_missing_fields_and_bad_type():
    data = _task().to_dict()
    assert validate_task(data) == []
    data.pop("required_evidence")
    data["task_type"] = "not_real"
    assert "missing required field: required_evidence" in validate_task(data)
    assert any("task_type must be one of" in error for error in validate_task(data))


def test_prompt_generation_produces_distinct_offline_modes():
    task = _task()
    baseline = build_prompt(task, "codex_alone")
    atlas = build_prompt(task, "atlas_plus_codex", "LOCAL EVIDENCE")
    assert "Do not use precomputed Atlas output" in baseline
    assert "Precomputed Atlas Context" in atlas
    assert "LOCAL EVIDENCE" in atlas
    assert "API" not in baseline


def test_run_package_generation_is_deterministic(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    generate_run_package([_task()], str(first), run_id="stable", atlas_context_fn=lambda _task: "LOCAL")
    generate_run_package([_task()], str(second), run_id="stable", atlas_context_fn=lambda _task: "LOCAL")
    first_files = {
        path.relative_to(first / "stable"): path.read_text(encoding="utf-8")
        for path in (first / "stable").rglob("*")
        if path.is_file()
    }
    second_files = {
        path.relative_to(second / "stable"): path.read_text(encoding="utf-8")
        for path in (second / "stable").rglob("*")
        if path.is_file()
    }
    assert first_files == second_files
    assert set(MODES) == {"codex_alone", "atlas_plus_codex"}


def test_run_log_parsing_and_validation():
    log = _log("one", "codex_alone", 100, 8.5)
    payload = log.to_dict()
    assert validate_run_log(payload) == []
    assert RunLog.from_dict(payload).estimated_total_tokens == 100
    payload["mode"] = "claude_alone"
    assert validate_run_log(payload)


def test_token_estimator_is_labeled_and_supports_manual_override():
    estimate = estimate_tokens("abcdefgh")
    override = estimate_tokens("abcdefgh", manual_override=7)
    assert estimate.estimated_tokens == 2
    assert estimate.source == "chars_per_4_estimate"
    assert "Estimated" in estimate.note
    assert override.estimated_tokens == 7
    assert override.source == "manual_override"
    assert estimated_count("abcde") == 2


def test_manual_score_aggregation_includes_quality_and_bug_accuracy():
    score = build_manual_score(
        task_id="defect",
        mode="atlas_plus_codex",
        correctness=5,
        evidence_quality=4,
        completeness=3,
        hallucination_risk=1,
        task_success=True,
        true_positives=2,
        false_positives=1,
        false_negatives=1,
    )
    accuracy = aggregate_bug_accuracy([score])
    assert score.total_score == 80.0
    assert accuracy == {
        "true_positives": 2,
        "false_positives": 1,
        "false_negatives": 1,
        "precision": 0.6667,
        "recall": 0.6667,
    }


def test_summary_reports_reduction_speedup_quality_and_breakdown():
    result = aggregate(
        [_log("one", "codex_alone", 200, 10), _log("one", "atlas_plus_codex", 100, 5)],
        [_score("one", "codex_alone"), _score("one", "atlas_plus_codex", 1)],
    )
    markdown = render_markdown(result, run_id="sample")
    assert result["tasks_compared"] == 1
    assert result["win_loss_tie"]["atlas_plus_codex"] == 1
    assert result["average_estimated_token_reduction_percent"] == 50.0
    assert result["average_speedup"] == 2.0
    assert result["average_quality_delta_points"] == 5.0
    assert "All token numbers are estimates" in markdown
    assert "Answer completeness" in markdown
    assert "Bug-Finding Accuracy" in markdown
    assert "Per-task Breakdown" in markdown


def test_empty_summary_uses_na_not_none():
    markdown = render_markdown(aggregate([], []), run_id="empty")
    assert "None" not in markdown
    assert "n/a" in markdown


def test_cli_human_workflow_records_scores_and_writes_summary(tmp_path):
    out = tmp_path / "reports" / "benchmarks"
    generate_run_package([_task()], str(out), run_id="manual", atlas_context_fn=lambda _task: "LOCAL")
    run_dir = out / "manual"
    for mode, answer in (("codex_alone", "baseline answer"), ("atlas_plus_codex", "Atlas answer")):
        answer_file = tmp_path / f"{mode}.txt"
        answer_file.write_text(answer, encoding="utf-8")
        assert cli.main(
            [
                "record-run",
                "--run-dir",
                str(run_dir),
                "--task-id",
                "ru_test",
                "--mode",
                mode,
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
        assert cli.main(
            [
                "score",
                "--run-dir",
                str(run_dir),
                "--task-id",
                "ru_test",
                "--mode",
                mode,
                "--correctness",
                "4",
                "--evidence-quality",
                "4",
                "--completeness",
                "4",
                "--hallucination-risk",
                "1",
                "--task-success",
                "yes",
            ]
        ) == 0
    assert cli.main(["summary", "--run-dir", str(run_dir)]) == 0
    summary = load_json(str(run_dir / "summary.json"))
    assert summary["tasks_compared"] == 1
    assert (run_dir / "summary.md").is_file()
