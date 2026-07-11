"""Deterministic scoring helpers for pilot runs.

This is a conservative heuristic scorer. It is useful for automatic triage, but
publishable accuracy claims should be manually adjudicated or reviewed.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .io import read_json, write_json
from .models import Score
from .tasks import load_gold, load_tasks

_PATH_RE = re.compile(r"[\w./\\-]+\.(?:py|ts|tsx|js|json|md|yaml|yml|toml)")


def clamp_score(value: int) -> int:
    return max(0, min(5, value))


def _norm(text: str) -> str:
    return text.replace("\\", "/").lower()


def required_file_coverage(response: str, required_files: tuple[str, ...]) -> tuple[int, int]:
    normalized = _norm(response)
    hits = 0
    for file_path in required_files:
        candidate = _norm(file_path)
        if candidate in normalized or candidate.split("/")[-1] in normalized:
            hits += 1
    return hits, len(required_files)


def hallucination_hits(response: str, unacceptable: tuple[str, ...]) -> list[str]:
    normalized = _norm(response)
    hits: list[str] = []
    for item in unacceptable:
        quoted = re.findall(r"`([^`]+)`", item)
        probes = quoted or [item]
        for probe in probes:
            probe_norm = _norm(probe)
            if len(probe_norm) >= 8 and probe_norm in normalized:
                hits.append(item)
                break
    return hits


def section_score(response: str) -> int:
    required = ("summary", "evidence", "reasoning", "caveats", "confidence")
    normalized = response.lower()
    return clamp_score(sum(1 for heading in required if heading in normalized))


def score_response(task_id: str, response: str) -> Score:
    task = next(task for task in load_tasks([task_id]) if task.task_id == task_id)
    gold = load_gold(task)
    hits, total = required_file_coverage(response, gold.required_files)
    coverage = hits / max(1, total)
    hallu = hallucination_hits(response, gold.unacceptable_hallucinations)
    citation = clamp_score(round(coverage * 5))
    completeness = clamp_score(round(coverage * 4) + (1 if "caveat" in response.lower() else 0))
    correctness = clamp_score(round(coverage * 4) + (1 if not hallu else 0))
    evidence = clamp_score(round(coverage * 4) + (1 if "evidence" in response.lower() else 0))
    hallucination_avoidance = clamp_score(5 - len(hallu) * 2)
    actionability = section_score(response)
    total_score = correctness + completeness + citation + evidence + hallucination_avoidance + actionability
    strict_success = total_score >= 24 and citation >= 4 and hallucination_avoidance >= 4
    notes = (
        f"heuristic_v1 required_file_hits={hits}/{total}; "
        f"unacceptable_hallucination_hits={len(hallu)}"
    )
    if hallu:
        notes += "; hits=" + " | ".join(hallu)
    return Score(
        correctness=correctness,
        completeness=completeness,
        citation_accuracy=citation,
        evidence_quality=evidence,
        hallucination_avoidance=hallucination_avoidance,
        actionability=actionability,
        strict_success=strict_success,
        source="heuristic_v1",
        notes=notes,
    )


def apply_score_to_run(path: Path, *, manual_scores: dict[str, int] | None = None) -> dict[str, Any]:
    record = read_json(path)
    if record.get("status") != "completed":
        return record
    if manual_scores:
        score = Score(
            correctness=manual_scores["correctness"],
            completeness=manual_scores["completeness"],
            citation_accuracy=manual_scores["citation_accuracy"],
            evidence_quality=manual_scores["evidence_quality"],
            hallucination_avoidance=manual_scores["hallucination_avoidance"],
            actionability=manual_scores["actionability"],
            strict_success=bool(manual_scores.get("strict_success", False)),
            source="manual",
            notes=manual_scores.get("notes", ""),
        )
    else:
        score = score_response(record["task_id"], record.get("response_text", ""))
    record.setdefault("scores", {})[score.source] = score.to_dict()
    write_json(path, record)
    return record


def score_paths(paths: list[Path]) -> list[dict[str, Any]]:
    return [apply_score_to_run(path) for path in paths]


def score_file_or_glob(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return sorted(path for path in root.glob("*/*.json") if path.is_file())
