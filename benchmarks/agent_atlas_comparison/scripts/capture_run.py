"""Capture a completed manual benchmark run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmark_runner.capture import capture_record, load_existing_run, parse_csv, parse_json_list, save_capture


def ask(label: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or (default or "")


def read_response(args: argparse.Namespace) -> str:
    if args.response_file:
        return Path(args.response_file).read_text(encoding="utf-8")
    print("Paste the complete response. End with a single line containing only <<<END>>>.")
    lines: list[str] = []
    while True:
        line = input()
        if line == "<<<END>>>":
            break
        lines.append(line)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id")
    parser.add_argument("--existing-run-json", type=Path)
    parser.add_argument("--condition", help="Optional convenience field such as codex_with_atlas.")
    parser.add_argument("--task-id")
    parser.add_argument("--agent", choices=("codex", "cursor", "claude"))
    atlas = parser.add_mutually_exclusive_group()
    atlas.add_argument("--atlas-enabled", action="store_true")
    atlas.add_argument("--no-atlas", action="store_true")
    parser.add_argument("--model")
    parser.add_argument("--started-at")
    parser.add_argument("--ended-at")
    parser.add_argument("--elapsed-ms", type=int)
    parser.add_argument("--response-file")
    parser.add_argument("--files-opened", help="Comma-separated file list.")
    parser.add_argument("--tool-calls-json", help="JSON list of tool-call records.")
    parser.add_argument("--atlas-calls-json", help="JSON list of Atlas-call records.")
    parser.add_argument("--token-total", type=int)
    parser.add_argument("--output-tokens", type=int)
    parser.add_argument("--token-status", default="unavailable", choices=("exact", "estimated", "unavailable"))
    parser.add_argument("--cold-start", action="store_true")
    parser.add_argument("--warm-run", action="store_true")
    parser.add_argument("--condition-evidence-json", help="JSON object with screenshot/log references.")
    parser.add_argument("--notes", default="")
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args()

    existing = load_existing_run(args.existing_run_json, args.run_id)
    task_id = args.task_id or (existing or {}).get("task_id") or ask("Task ID")
    condition_agent = args.condition.split("_", 1)[0] if args.condition else None
    agent = args.agent or condition_agent or ((existing or {}).get("runner") or {}).get("agent") or ask("Agent", "codex")
    if args.atlas_enabled:
        atlas_enabled = True
    elif args.no_atlas:
        atlas_enabled = False
    elif args.condition:
        atlas_enabled = "_with_atlas" in args.condition
    elif existing:
        atlas_enabled = bool((existing.get("runner") or {}).get("atlas_enabled"))
    else:
        atlas_enabled = ask("Atlas enabled? true/false", "false").lower() in ("true", "1", "yes", "y")
    model = args.model or ((existing or {}).get("runner") or {}).get("model") or ask("Model", "")
    response_text = read_response(args)
    evidence = json.loads(args.condition_evidence_json) if args.condition_evidence_json else {}
    record = capture_record(
        task_id=task_id,
        agent=agent,
        atlas_enabled=atlas_enabled,
        model=model or None,
        response_text=response_text,
        run_id=args.run_id,
        existing=existing,
        started_at=args.started_at,
        ended_at=args.ended_at,
        elapsed_ms=args.elapsed_ms,
        files_opened=parse_csv(args.files_opened),
        tool_calls=parse_json_list(args.tool_calls_json),
        atlas_calls=parse_json_list(args.atlas_calls_json),
        notes=args.notes,
        token_total=args.token_total,
        output_tokens=args.output_tokens,
        token_status=args.token_status,
        cold_start=True if args.cold_start else (False if args.warm_run else None),
        condition_evidence=evidence,
    )
    path = save_capture(record, args.output_root)
    print(f"Saved completed run: {path}")
    print("Next: py -3 benchmarks\\agent_atlas_comparison\\scripts\\score_run.py --run-json " + str(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
