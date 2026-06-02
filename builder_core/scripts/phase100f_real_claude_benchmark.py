"""Phase 100F — real Claude API context-compression benchmark.

Repeats Phase 100E (same tasks, same anchor scoring) with live Anthropic Messages API
calls for both arms. Reports real input/output tokens, latency, and API cost.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "reports" / "phase100f_run"
REPORT_PATH = ROOT / "reports" / "phase100f_real_claude_benchmark.md"
CORPUS_DIR = ROOT / "data" / "benchmarks" / "phase100f"

MAX_TURNS = 10
MAX_READ_CHARS = 80_000
MAX_GREP_LINES = 200
MAX_LIST_ENTRIES = 200

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
PRICE_TABLE = {
    "model_id": DEFAULT_MODEL,
    "input_usd_per_token": 3.0 / 1_000_000,
    "output_usd_per_token": 15.0 / 1_000_000,
}


def _load_phase100e():
    path = ROOT / "builder_core" / "scripts" / "phase100e_context_compression_execution.py"
    spec = importlib.util.spec_from_file_location("phase100e", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_env_files() -> None:
    for env_path in (ROOT / ".env", ROOT.parent / ".env"):
        if not env_path.is_file():
            continue
        for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _git_head() -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.stdout.strip() if proc.returncode == 0 else "unknown"
    except OSError:
        return "unknown"


def _safe_rel_path(rel: str) -> Path:
    clean = rel.replace("\\", "/").lstrip("/")
    resolved = (ROOT / clean).resolve()
    root_resolved = ROOT.resolve()
    if os.path.commonpath([str(resolved), str(root_resolved)]) != str(root_resolved):
        raise ValueError(f"path escapes repository: {rel}")
    return resolved


def _tool_read_file(path: str) -> str:
    target = _safe_rel_path(path)
    if not target.is_file():
        return f"ERROR: file not found: {path}"
    text = target.read_text(encoding="utf-8", errors="replace")
    if len(text) > MAX_READ_CHARS:
        return text[:MAX_READ_CHARS] + f"\n... truncated ({len(text)} chars total)"
    return text


def _tool_grep(pattern: str, path_glob: str = "**/*.py") -> str:
    import fnmatch

    rx = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
    lines: List[str] = []
    for file_path in ROOT.glob(path_glob):
        if not file_path.is_file():
            continue
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = file_path.relative_to(ROOT).as_posix()
        if not fnmatch.fnmatch(rel, path_glob.replace("**/", "")) and "**" not in path_glob:
            pass
        for index, line in enumerate(text.splitlines(), 1):
            if rx.search(line):
                lines.append(f"{rel}:{index}:{line[:200]}")
        if len(lines) >= MAX_GREP_LINES:
            break
    return "\n".join(lines[:MAX_GREP_LINES]) or "(no matches)"


def _tool_list_dir(path: str = ".") -> str:
    target = _safe_rel_path(path or ".")
    if not target.is_dir():
        return f"ERROR: not a directory: {path}"
    entries = sorted(target.iterdir(), key=lambda p: p.name.lower())[:MAX_LIST_ENTRIES]
    lines = []
    for entry in entries:
        kind = "dir" if entry.is_dir() else "file"
        try:
            rel = entry.relative_to(ROOT).as_posix()
        except ValueError:
            rel = str(entry)
        lines.append(f"{kind}\t{rel}")
    return "\n".join(lines)


def _tool_glob(pattern: str) -> str:
    paths = sorted(p.relative_to(ROOT).as_posix() for p in ROOT.glob(pattern) if p.is_file())
    return "\n".join(paths[:MAX_LIST_ENTRIES]) or "(no matches)"


BASE_TOOLS = [
    {
        "name": "read_file",
        "description": "Read a UTF-8 text file relative to the repository root.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "grep",
        "description": "Search file contents under the repo by regex pattern.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "path_glob": {"type": "string", "description": "e.g. **/*.py"},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "list_dir",
        "description": "List files and directories at a repo-relative path.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
        },
    },
    {
        "name": "glob",
        "description": "List repo-relative file paths matching a glob.",
        "input_schema": {
            "type": "object",
            "properties": {"pattern": {"type": "string"}},
            "required": ["pattern"],
        },
    },
    {
        "name": "submit_answer",
        "description": "Submit the final answer and end the task. Cite real file paths.",
        "input_schema": {
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
                "sources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Repo-relative source paths used",
                },
            },
            "required": ["answer"],
        },
    },
]

JARVIS_TOOLS = [
    {
        "name": "jarvis_ask",
        "description": "Query JARVIS repository intelligence (architecture, layout, risk).",
        "input_schema": {
            "type": "object",
            "properties": {"question": {"type": "string"}},
            "required": ["question"],
        },
    },
    {
        "name": "jarvis_graph_summary",
        "description": "Dependency graph summary (cycles, top imported modules).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "jarvis_impact_file",
        "description": "Impact analysis for a repo-relative file path.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "transitive": {"type": "boolean"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "jarvis_impact_module",
        "description": "Impact analysis for a top-level subsystem/module name.",
        "input_schema": {
            "type": "object",
            "properties": {"module": {"type": "string"}},
            "required": ["module"],
        },
    },
]


def _system_prompt(arm: str, repo_root: str) -> str:
    base = (
        f"You are analyzing the repository at `{repo_root}`. "
        "Answer the user's question using only evidence from this repository. "
        "Cite real file paths that exist. Do not invent modules or dependencies. "
        "When uncertain, say so. Call submit_answer when finished."
    )
    if arm == "claude_plus_jarvis":
        return (
            base + " JARVIS tools (jarvis_ask, jarvis_graph_summary, jarvis_impact_*) "
            "return precomputed deterministic intelligence — prefer them over reading large files."
        )
    return base + " Use read_file, grep, list_dir, and glob to gather evidence."


def _execute_generic(name: str, inputs: Dict[str, Any], e100: Any, index: Dict[str, Any]) -> str:
    if name == "read_file":
        return _tool_read_file(str(inputs["path"]))
    if name == "grep":
        return _tool_grep(str(inputs["pattern"]), str(inputs.get("path_glob", "**/*.py")))
    if name == "list_dir":
        return _tool_list_dir(str(inputs.get("path", ".")))
    if name == "glob":
        return _tool_glob(str(inputs["pattern"]))
    if name == "jarvis_ask":
        result = e100.ask_mod.answer(index, str(inputs["question"]))
        return json.dumps(result, ensure_ascii=False, indent=2)
    if name == "jarvis_graph_summary":
        from builder_core.bug_intelligence import depgraph

        graph = e100._cached_depgraph(str(ROOT))
        return depgraph.format_summary(graph)
    if name == "jarvis_impact_file":
        from builder_core.bug_intelligence import depgraph, impact

        graph = e100._cached_depgraph(str(ROOT))
        result = impact.analyze_impact(
            graph,
            kind="file",
            file_path=str(inputs["path"]),
            project_root=str(ROOT),
            include_transitive=bool(inputs.get("transitive")),
        )
        return impact.format_summary(result, top=20)
    if name == "jarvis_impact_module":
        from builder_core.bug_intelligence import depgraph, impact

        graph = e100._cached_depgraph(str(ROOT))
        result = impact.analyze_impact(
            graph,
            kind="module",
            module=str(inputs["module"]),
            project_root=str(ROOT),
            include_transitive=True,
        )
        return impact.format_summary(result, top=20)
    return f"ERROR: unknown tool {name}"


def run_claude_task(
    client: Any,
    *,
    model: str,
    arm: str,
    task_prompt: str,
    e100: Any,
    index: Dict[str, Any],
) -> Dict[str, Any]:
    tools = BASE_TOOLS + (JARVIS_TOOLS if arm == e100.ARM_CLAUDE_JARVIS else [])
    messages: List[Dict[str, Any]] = [{"role": "user", "content": task_prompt}]
    tool_calls: Dict[str, int] = {}
    input_tokens = 0
    output_tokens = 0
    peak_context = 0
    sources: List[str] = []
    answer = ""
    started = time.perf_counter()

    for _turn in range(MAX_TURNS):
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            temperature=0,
            system=_system_prompt(arm, str(ROOT)),
            messages=messages,
            tools=tools,
        )
        input_tokens += getattr(response.usage, "input_tokens", 0) or 0
        output_tokens += getattr(response.usage, "output_tokens", 0) or 0
        peak_context = max(peak_context, getattr(response.usage, "input_tokens", 0) or 0)

        assistant_content: List[Dict[str, Any]] = []
        tool_results: List[Dict[str, Any]] = []
        finished = False

        for block in response.content:
            if block.type == "text":
                assistant_content.append({"type": "text", "text": block.text})
                if response.stop_reason == "end_turn" and not finished:
                    answer = block.text
            elif block.type == "tool_use":
                assistant_content.append(
                    {
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    }
                )
                tool_calls[block.name] = tool_calls.get(block.name, 0) + 1
                if block.name == "submit_answer":
                    payload = block.input if isinstance(block.input, dict) else {}
                    answer = str(payload.get("answer", ""))
                    sources = list(payload.get("sources") or [])
                    finished = True
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": "Answer recorded.",
                        }
                    )
                else:
                    try:
                        result_text = _execute_generic(block.name, block.input or {}, e100, index)
                    except Exception as exc:
                        result_text = f"ERROR: {exc}"
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_text[:MAX_READ_CHARS],
                        }
                    )

        messages.append({"role": "assistant", "content": assistant_content})
        if tool_results:
            messages.append({"role": "user", "content": tool_results})
        if finished:
            break
        if response.stop_reason == "end_turn":
            break

    elapsed = time.perf_counter() - started
    if not answer:
        for msg in reversed(messages):
            if msg.get("role") != "assistant":
                continue
            for block in msg.get("content", []):
                if isinstance(block, dict) and block.get("type") == "text":
                    answer = block.get("text", "")
                    break
            if answer:
                break

    cost = (
        input_tokens * PRICE_TABLE["input_usd_per_token"]
        + output_tokens * PRICE_TABLE["output_usd_per_token"]
    )
    return {
        "answer": answer,
        "sources": sources,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "peak_context_tokens": peak_context,
        "wall_clock_s": round(elapsed, 3),
        "latency_s": round(elapsed, 3),
        "cost_usd": round(cost, 6),
        "tool_calls": tool_calls,
    }


def run_execution(
    *,
    trials: int,
    task_ids: Optional[Sequence[str]],
    model: str,
) -> Dict[str, Any]:
    _load_env_files()
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Export it or add it to local_jarvis/.env before running."
        )

    import anthropic

    e100 = _load_phase100e()
    from builder_core import store

    index = store.load_index(str(ROOT))
    if index is None:
        raise RuntimeError("repository index missing; run: py -3 -m builder_core.cli init --project .")

    e100._cached_depgraph(str(ROOT))

    client = anthropic.Anthropic(api_key=api_key)
    tasks = e100.build_task_suite()
    if task_ids:
        allowed = set(task_ids)
        tasks = [t for t in tasks if t.task_id in allowed]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)

    raw_trials: List[Dict[str, Any]] = []
    by_task: Dict[str, Dict[str, Any]] = {}
    started_suite = time.time()

    for task in tasks:
        trials_a = []
        trials_b = []
        for trial in range(1, trials + 1):
            run_a = run_claude_task(
                client,
                model=model,
                arm=e100.ARM_CLAUDE_ONLY,
                task_prompt=task.prompt,
                e100=e100,
                index=index,
            )
            qa, qda = e100.score_quality(run_a["answer"], run_a["sources"], task)
            trials_a.append({**run_a, "quality": qa, "quality_detail": qda, "trial": trial})

            run_b = run_claude_task(
                client,
                model=model,
                arm=e100.ARM_CLAUDE_JARVIS,
                task_prompt=task.prompt,
                e100=e100,
                index=index,
            )
            qb, qdb = e100.score_quality(run_b["answer"], run_b["sources"], task)
            trials_b.append({**run_b, "quality": qb, "quality_detail": qdb, "trial": trial})

            for payload, arm in ((run_a, e100.ARM_CLAUDE_ONLY), (run_b, e100.ARM_CLAUDE_JARVIS)):
                raw_trials.append(
                    {
                        "task_id": task.task_id,
                        "category": task.category,
                        "arm": arm,
                        "trial": trial,
                        "model": model,
                        **payload,
                    }
                )

        def _to_trial_result(arm: str, rows: List[Dict[str, Any]]) -> List[e100.TrialResult]:
            out = []
            for row in rows:
                out.append(
                    e100.TrialResult(
                        task_id=task.task_id,
                        arm=arm,
                        trial=row["trial"],
                        answer=row["answer"],
                        sources=row["sources"],
                        input_tokens=row["input_tokens"],
                        output_tokens=row["output_tokens"],
                        peak_context_tokens=row["peak_context_tokens"],
                        wall_clock_s=row["wall_clock_s"],
                        cost_usd=row["cost_usd"],
                        tool_calls=row["tool_calls"],
                        quality=row["quality"],
                        quality_detail=row["quality_detail"],
                    )
                )
            return out

        by_task[task.task_id] = {
            e100.ARM_CLAUDE_ONLY: e100.aggregate_trials(_to_trial_result(e100.ARM_CLAUDE_ONLY, trials_a)),
            e100.ARM_CLAUDE_JARVIS: e100.aggregate_trials(
                _to_trial_result(e100.ARM_CLAUDE_JARVIS, trials_b)
            ),
        }

    verdict = e100.evaluate_verdict(tasks, by_task)
    elapsed = time.time() - started_suite

    manifest = {
        "schema_version": 1,
        "program_id": "phase100f-real-claude",
        "model": model,
        "repo_commit": _git_head(),
        "trials": trials,
        "task_ids": [t.task_id for t in tasks],
        "price_table": PRICE_TABLE,
    }
    (CORPUS_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (OUTPUT_DIR / "raw_trials.json").write_text(json.dumps(raw_trials, indent=2) + "\n", encoding="utf-8")
    (OUTPUT_DIR / "task_summary.json").write_text(json.dumps(by_task, indent=2) + "\n", encoding="utf-8")
    (OUTPUT_DIR / "verdict.json").write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")

    write_report(tasks, by_task, verdict, raw_trials, manifest, elapsed, e100)
    return {"verdict": verdict, "by_task": by_task, "elapsed_s": elapsed}


def write_report(
    tasks: Sequence[Any],
    by_task: Dict[str, Dict[str, Any]],
    verdict: Dict[str, Any],
    raw_trials: Sequence[Dict[str, Any]],
    manifest: Dict[str, Any],
    elapsed_s: float,
    e100: Any,
) -> None:
    a_arm = e100.ARM_CLAUDE_ONLY
    b_arm = e100.ARM_CLAUDE_JARVIS

    sum_in_a = sum(by_task[t.task_id][a_arm]["input_tokens_median"] for t in tasks)
    sum_in_b = sum(by_task[t.task_id][b_arm]["input_tokens_median"] for t in tasks)
    sum_out_a = sum(by_task[t.task_id][a_arm].get("output_tokens_median", 0) for t in tasks)
    sum_out_b = sum(by_task[t.task_id][b_arm].get("output_tokens_median", 0) for t in tasks)
    sum_cost_a = sum(by_task[t.task_id][a_arm]["cost_usd_median"] for t in tasks)
    sum_cost_b = sum(by_task[t.task_id][b_arm]["cost_usd_median"] for t in tasks)
    sum_lat_a = sum(by_task[t.task_id][a_arm]["wall_clock_s_median"] for t in tasks)
    sum_lat_b = sum(by_task[t.task_id][b_arm]["wall_clock_s_median"] for t in tasks)

    lines = [
        "# Phase 100F — Real Claude API Benchmark",
        "",
        "**Status:** Execution complete",
        f"**Date:** {time.strftime('%Y-%m-%d')}",
        "**Protocol:** Phase 100E task suite + Phase 100B scoring (live Anthropic API)",
        "",
        "---",
        "",
        "## 1. Executive summary",
        "",
        "| Item | Value |",
        "|------|-------|",
        f"| Model | `{manifest['model']}` |",
        f"| Tasks | {len(tasks)} |",
        f"| Trials per task × arm | {manifest['trials']} |",
        f"| API calls (approx) | {len(raw_trials)} task runs |",
        f"| Commit | `{manifest['repo_commit']}` |",
        f"| **Verdict** | **{verdict['verdict']}** |",
        f"| Compression (total tokens A/B) | {verdict.get('suite_compression_ratio')}× |",
        f"| Mean quality A → B | {verdict['mean_quality_a']} → {verdict['mean_quality_b']} |",
        f"| Wall-clock (suite) | {elapsed_s:.1f}s |",
        "",
        "---",
        "",
        "## 2. Summary table (API-measured medians)",
        "",
        "| Metric | Claude Only | Claude + JARVIS |",
        "|--------|------------:|----------------:|",
        f"| **Input tokens** | {sum_in_a:,.0f} | {sum_in_b:,.0f} |",
        f"| **Output tokens** | {sum_out_a:,.0f} | {sum_out_b:,.0f} |",
        f"| **Total tokens** | {sum_in_a + sum_out_a:,.0f} | {sum_in_b + sum_out_b:,.0f} |",
        f"| **Latency** (sum of medians, s) | {sum_lat_a:.2f} | {sum_lat_b:.2f} |",
        f"| **API cost** (USD) | ${sum_cost_a:.4f} | ${sum_cost_b:.4f} |",
        f"| **Quality** (0–4, anchors) | {verdict['mean_quality_a']} | {verdict['mean_quality_b']} |",
        "",
        "---",
        "",
        "## 3. Per-task results",
        "",
        "| ID | Category | In (A) | In (B) | Out (A) | Out (B) | Latency A | Latency B | Cost A | Cost B | Q(A) | Q(B) |",
        "|----|----------|-------:|-------:|--------:|--------:|----------:|----------:|-------:|-------:|-----:|-----:|",
    ]
    for task in tasks:
        a = by_task[task.task_id][a_arm]
        b = by_task[task.task_id][b_arm]
        lines.append(
            f"| {task.task_id} | {task.category} | {a['input_tokens_median']:,.0f} | "
            f"{b['input_tokens_median']:,.0f} | {a.get('output_tokens_median', 0):,.0f} | "
            f"{b.get('output_tokens_median', 0):,.0f} | {a['wall_clock_s_median']:.2f}s | "
            f"{b['wall_clock_s_median']:.2f}s | ${a['cost_usd_median']:.4f} | "
            f"${b['cost_usd_median']:.4f} | {a['quality_median']:.0f} | {b['quality_median']:.0f} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 4. Gates (Phase 100B §5)",
        "",
        "| Gate | Pass |",
        "|------|:----:|",
    ])
    for name, passed in verdict.get("gates", {}).items():
        lines.append(f"| {name} | {'yes' if passed else 'no'} |")

    lines.extend([
        "",
        "---",
        "",
        "## 5. Artifacts",
        "",
        f"| `{OUTPUT_DIR.relative_to(ROOT).as_posix()}/raw_trials.json` | Per-run API usage |",
        f"| `{OUTPUT_DIR.relative_to(ROOT).as_posix()}/task_summary.json` | Medians per task |",
        f"| `{OUTPUT_DIR.relative_to(ROOT).as_posix()}/verdict.json` | Suite verdict |",
        "",
        "---",
        "",
        "## 6. Comparison to Phase 100E",
        "",
        "Phase 100E used deterministic context simulation (no API). This run uses **real**",
        "`usage.input_tokens` / `usage.output_tokens` from Anthropic and wall-clock latency per task.",
        "",
    ])
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_blocked_report(reason: str) -> None:
    lines = [
        "# Phase 100F — Real Claude API Benchmark",
        "",
        "**Status:** Blocked — API key required",
        f"**Date:** {time.strftime('%Y-%m-%d')}",
        "",
        "## Blocker",
        "",
        reason,
        "",
        "## How to run",
        "",
        "1. Set `ANTHROPIC_API_KEY` in the environment or `local_jarvis/.env`.",
        "2. Ensure index exists: `py -3 -m builder_core.cli init --project .`",
        "3. Run:",
        "",
        "```bash",
        "cd local_jarvis",
        "py -3 -m builder_core.scripts.phase100f_real_claude_benchmark --trials 1",
        "```",
        "",
        "Use `--trials 3` for full Phase 100E parity. Use `--task-ids A1,C6` for a smoke subset.",
        "",
        "## Harness",
        "",
        "Script: `builder_core/scripts/phase100f_real_claude_benchmark.py`",
        "",
        "- Same 20 tasks and anchor scoring as Phase 100E",
        "- Arm A: `read_file`, `grep`, `list_dir`, `glob`",
        "- Arm B: generic tools + `jarvis_ask`, `jarvis_graph_summary`, `jarvis_impact_*`",
        "- Real tokens, latency, and cost from Anthropic API responses",
        "",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "status.json").write_text(
        json.dumps({"status": "blocked", "reason": reason}, indent=2) + "\n",
        encoding="utf-8",
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 100F real Claude API benchmark")
    parser.add_argument("--trials", type=int, default=1, help="Trials per task per arm (100E uses 3)")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--task-ids", nargs="*", help="Subset of task IDs, e.g. A1 C6")
    args = parser.parse_args(argv)

    _load_env_files()
    if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
        write_blocked_report(
            "`ANTHROPIC_API_KEY` was not found in the environment or `.env` files."
        )
        print(f"BLOCKED: set ANTHROPIC_API_KEY. Report: {REPORT_PATH}", file=sys.stderr)
        return 2

    result = run_execution(trials=max(1, args.trials), task_ids=args.task_ids, model=args.model)
    print(f"Phase 100F complete — verdict: {result['verdict']['verdict']}")
    print(f"Report: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
