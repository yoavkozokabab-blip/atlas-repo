"""Offline CLI for Phase 103: Codex Alone vs JARVIS + Codex."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from typing import Any, List

from .runner import generate_run_package
from .schema import (
    MODES,
    ManualScore,
    RunLog,
    dump_json,
    load_json,
    load_tasks,
    parse_timestamp,
    validate_manual_score,
    validate_run_log,
    validate_task_file,
)
from .scoring import build_manual_score
from .summary import aggregate, render_markdown
from .tokens import attach_answer_to_breakdown, estimated_count

DEFAULT_TASKS = os.path.join(os.path.dirname(__file__), "data", "benchmark_tasks_v1.json")
DEFAULT_OUT = os.path.join("reports", "benchmarks")


def _task_root(run_dir: str, task_id: str) -> str:
    task_root = os.path.abspath(os.path.join(run_dir, task_id))
    run_root = os.path.abspath(run_dir)
    if os.path.commonpath([task_root, run_root]) != run_root:
        raise ValueError("task_id escapes run directory")
    if not os.path.isfile(os.path.join(task_root, "task.json")):
        raise FileNotFoundError(f"task not found in run package: {task_id}")
    return task_root


def _iter_task_roots(run_dir: str) -> List[str]:
    return [
        os.path.join(run_dir, name)
        for name in sorted(os.listdir(run_dir))
        if os.path.isfile(os.path.join(run_dir, name, "task.json"))
    ]


def _cmd_validate(tasks_path: str) -> int:
    failures = validate_task_file(tasks_path)
    task_count = len(load_tasks(tasks_path))
    print(f"Validated {task_count} benchmark task(s): {tasks_path}")
    for task_id, errors in failures.items():
        for error in errors:
            print(f"FAIL {task_id}: {error}")
    if not failures:
        print("All tasks valid.")
    return 1 if failures else 0


def _cmd_generate(tasks_path: str, out_dir: str, run_id: str | None, skip_context: bool) -> int:
    context_fn = (lambda _task: "[JARVIS context intentionally omitted]") if skip_context else None
    manifest = generate_run_package(load_tasks(tasks_path), out_dir, run_id=run_id, jarvis_context_fn=context_fn)
    print(f"Generated offline run package: {os.path.join(out_dir, manifest['run_id'])}")
    print(f"Tasks: {manifest['task_count']}; modes: {', '.join(manifest['modes'])}")
    print("Token numbers are estimates unless manually overridden.")
    return 0


def _cmd_record_run(args: argparse.Namespace) -> int:
    task_root = _task_root(args.run_dir, args.task_id)
    log_path = os.path.join(task_root, f"run_log.{args.mode}.json")
    log = RunLog.from_dict(load_json(log_path))
    answer_target = os.path.join(task_root, log.raw_answer_path)
    os.makedirs(os.path.dirname(answer_target), exist_ok=True)
    if os.path.abspath(args.answer_file) != os.path.abspath(answer_target):
        shutil.copyfile(args.answer_file, answer_target)
    with open(answer_target, "r", encoding="utf-8", errors="ignore") as handle:
        answer = handle.read()
    elapsed = args.elapsed_seconds
    if elapsed is None:
        elapsed = (parse_timestamp(args.end_time) - parse_timestamp(args.start_time)).total_seconds()
    log.model_tool_used = args.model_tool_used
    log.start_time = args.start_time
    log.end_time = args.end_time
    log.elapsed_seconds = max(0.0, float(elapsed))
    if args.estimated_input_tokens is not None:
        log.estimated_input_tokens = args.estimated_input_tokens
    log.estimated_output_tokens = estimated_count(answer, manual_override=args.estimated_output_tokens)
    if log.token_breakdown:
        log.token_breakdown = attach_answer_to_breakdown(
            log.token_breakdown,
            answer,
            manual_override=args.estimated_output_tokens,
        )
        dump_json(log.token_breakdown, os.path.join(task_root, f"token_breakdown.{args.mode}.json"))
    log.notes = args.notes
    dump_json(log.to_dict(), log_path)
    print(f"Recorded {args.task_id} / {args.mode}: {log_path}")
    print("Token numbers are estimates unless manually overridden.")
    return 0


def _cmd_score(args: argparse.Namespace) -> int:
    task_root = _task_root(args.run_dir, args.task_id)
    score = build_manual_score(
        task_id=args.task_id,
        mode=args.mode,
        correctness=args.correctness,
        evidence_quality=args.evidence_quality,
        completeness=args.completeness,
        hallucination_risk=args.hallucination_risk,
        task_success=args.task_success,
        true_positives=args.true_positives,
        false_positives=args.false_positives,
        false_negatives=args.false_negatives,
        notes=args.notes,
    )
    score_path = os.path.join(task_root, f"score.{args.mode}.json")
    dump_json(score.to_dict(), score_path)
    print(f"Saved manual score: {score_path}")
    print(f"Total score: {score.total_score}")
    return 0


def _cmd_summary(run_dir: str) -> int:
    logs: List[RunLog] = []
    scores: List[ManualScore] = []
    skipped_logs = 0
    skipped_scores = 0
    for task_root in _iter_task_roots(run_dir):
        for mode in MODES:
            log_path = os.path.join(task_root, f"run_log.{mode}.json")
            score_path = os.path.join(task_root, f"score.{mode}.json")
            log_data = load_json(log_path)
            score_data = load_json(score_path)
            if validate_run_log(log_data):
                skipped_logs += 1
            else:
                logs.append(RunLog.from_dict(log_data))
            if validate_manual_score(score_data):
                skipped_scores += 1
            else:
                scores.append(ManualScore.from_dict(score_data))
    result = aggregate(logs, scores)
    dump_json(result, os.path.join(run_dir, "summary.json"))
    with open(os.path.join(run_dir, "summary.md"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(render_markdown(result, run_id=os.path.basename(os.path.abspath(run_dir))))
    print(f"Summary written: {os.path.join(run_dir, 'summary.md')}")
    print(
        f"Compared tasks: {result['tasks_compared']}; "
        f"skipped incomplete logs: {skipped_logs}; skipped incomplete scores: {skipped_scores}"
    )
    return 0


def _yes_no(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"yes", "true", "1"}:
        return True
    if normalized in {"no", "false", "0"}:
        return False
    raise argparse.ArgumentTypeError("expected yes/no")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="builder_core.benchmark_framework")
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="Validate a task corpus.")
    validate.add_argument("--tasks", default=DEFAULT_TASKS)

    generate = commands.add_parser("generate", help="Generate an offline manual run package.")
    generate.add_argument("--tasks", default=DEFAULT_TASKS)
    generate.add_argument("--out", default=DEFAULT_OUT)
    generate.add_argument("--run-id")
    generate.add_argument("--skip-jarvis-context", action="store_true")

    record = commands.add_parser("record-run", help="Record one completed manual run.")
    record.add_argument("--run-dir", required=True)
    record.add_argument("--task-id", required=True)
    record.add_argument("--mode", required=True, choices=MODES)
    record.add_argument("--model-tool-used", required=True)
    record.add_argument("--start-time", required=True)
    record.add_argument("--end-time", required=True)
    record.add_argument("--elapsed-seconds", type=float)
    record.add_argument("--estimated-input-tokens", type=int)
    record.add_argument("--estimated-output-tokens", type=int)
    record.add_argument("--answer-file", required=True)
    record.add_argument("--notes", default="")

    score = commands.add_parser("score", help="Save a human score for one answer.")
    score.add_argument("--run-dir", required=True)
    score.add_argument("--task-id", required=True)
    score.add_argument("--mode", required=True, choices=MODES)
    score.add_argument("--correctness", required=True, type=float)
    score.add_argument("--evidence-quality", required=True, type=float)
    score.add_argument("--completeness", required=True, type=float)
    score.add_argument("--hallucination-risk", required=True, type=float)
    score.add_argument("--task-success", required=True, type=_yes_no)
    score.add_argument("--true-positives", type=int, default=0)
    score.add_argument("--false-positives", type=int, default=0)
    score.add_argument("--false-negatives", type=int, default=0)
    score.add_argument("--notes", default="")

    summary = commands.add_parser("summary", help="Aggregate logged and manually scored runs.")
    summary.add_argument("--run-dir", required=True)
    return parser


def main(argv: List[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "validate":
        return _cmd_validate(args.tasks)
    if args.command == "generate":
        return _cmd_generate(args.tasks, args.out, args.run_id, args.skip_jarvis_context)
    if args.command == "record-run":
        return _cmd_record_run(args)
    if args.command == "score":
        return _cmd_score(args)
    if args.command == "summary":
        return _cmd_summary(args.run_dir)
    return 2


if __name__ == "__main__":
    sys.exit(main())
