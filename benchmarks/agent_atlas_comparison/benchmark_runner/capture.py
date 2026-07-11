"""Capture manually executed benchmark runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .io import read_json, write_json
from .models import Observations, RunRecord, RunnerInfo, TokenUsage, condition_name, now_iso, prompt_hash
from .paths import RUNS_DIR
from .tasks import load_repositories, load_tasks
from .tokens import estimated_token_metric, token_metric, unavailable_token_metric


def parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_json_list(value: str | None) -> list[dict[str, Any]]:
    if not value:
        return []
    parsed = json.loads(value)
    if not isinstance(parsed, list):
        raise ValueError("Expected a JSON list")
    return parsed


def load_existing_run(path: Path | None, run_id: str | None) -> dict[str, Any] | None:
    if path:
        return read_json(path)
    if not run_id:
        return None
    matches = list(RUNS_DIR.glob(f"*/*{run_id}*.json"))
    if len(matches) == 1:
        return read_json(matches[0])
    return None


def capture_record(
    *,
    task_id: str,
    agent: str,
    atlas_enabled: bool,
    model: str | None,
    response_text: str,
    run_id: str | None = None,
    existing: dict[str, Any] | None = None,
    started_at: str | None = None,
    ended_at: str | None = None,
    elapsed_ms: int | None = None,
    files_opened: list[str] | None = None,
    tool_calls: list[dict[str, Any]] | None = None,
    atlas_calls: list[dict[str, Any]] | None = None,
    notes: str = "",
    token_total: int | None = None,
    output_tokens: int | None = None,
    token_status: str = "unavailable",
    cold_start: bool | None = None,
    condition_evidence: dict[str, Any] | None = None,
) -> RunRecord:
    task = next(task for task in load_tasks([task_id]) if task.task_id == task_id)
    repo = load_repositories()[task.repository_id]
    condition = condition_name(agent, atlas_enabled)
    created_at = now_iso()
    effective_run_id = run_id or (existing or {}).get("run_id") or f"{task_id}_{condition}_{created_at.replace(':', '')}"
    obs = Observations(
        latency_ms=elapsed_ms,
        token_usage=TokenUsage(),
        tool_calls=tool_calls or [],
        atlas_calls=atlas_calls or [],
        files_opened=files_opened or [],
        errors=[],
        telemetry_quality={},
    )
    obs.token_usage.user_prompt_tokens = estimated_token_metric(task.prompt)
    obs.telemetry_quality["user_prompt_tokens"] = "estimated"
    if output_tokens is not None:
        obs.token_usage.output_tokens = token_metric(output_tokens, token_status)
    elif response_text:
        obs.token_usage.output_tokens = estimated_token_metric(response_text)
        obs.telemetry_quality["output_tokens"] = "estimated"
    else:
        obs.token_usage.output_tokens = unavailable_token_metric()
    if token_total is not None:
        obs.token_usage.total_tokens = token_metric(token_total, token_status)
    elif obs.token_usage.output_tokens.get("value") is not None:
        obs.token_usage.total_tokens = token_metric(
            obs.token_usage.user_prompt_tokens["value"] + obs.token_usage.output_tokens["value"],
            "estimated",
        )
        obs.telemetry_quality["total_tokens"] = "estimated"
    else:
        obs.token_usage.total_tokens = unavailable_token_metric()
    obs.telemetry_quality.update(
        {
            "latency": "exact" if elapsed_ms is not None else "unavailable",
            "tool_calls": "manual_exact" if tool_calls else "unavailable",
            "files_opened": "manual_exact" if files_opened else "unavailable",
            "atlas_calls": "manual_exact" if atlas_calls else "unavailable",
        }
    )
    return RunRecord(
        schema_version=2,
        run_id=effective_run_id,
        anonymous_id=(existing or {}).get("anonymous_id") or effective_run_id,
        run_set_id=(existing or {}).get("run_set_id"),
        created_at=(existing or {}).get("created_at") or created_at,
        started_at=started_at,
        ended_at=ended_at or created_at,
        status="completed",
        condition=condition,
        task_id=task.task_id,
        repository_id=task.repository_id,
        repository_commit_sha=repo.commit_sha,
        category=task.category,
        difficulty=task.difficulty,
        prompt_sha256=prompt_hash(task.prompt),
        prompt=task.prompt,
        runner=RunnerInfo(
            agent=agent,
            atlas_enabled=atlas_enabled,
            provider=agent,
            adapter="atlas" if atlas_enabled else "no_atlas",
            model=model,
        ),
        response_text=response_text,
        observations=obs,
        condition_evidence=condition_evidence or {},
        cold_start=cold_start,
        notes=notes,
    )


def save_capture(record: RunRecord, output_root: Path | None = None) -> Path:
    root = output_root or RUNS_DIR
    path = root / record.condition / f"{record.run_id}.json"
    write_json(path, record.to_dict())
    return path
