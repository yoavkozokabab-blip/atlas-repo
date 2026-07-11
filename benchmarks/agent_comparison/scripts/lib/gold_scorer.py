"""Deterministic gold-standard scoring."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .schema import RunArtifact, TaskDef, TaskScore, parse_gold


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/").lower().strip()


def _mentioned_files(text: str) -> List[str]:
    patterns = [
        r"`([^`]+\.py)`",
        r"\b([\w./-]+\.py)\b",
        r"\b(auth/[\w./-]+)\b",
        r"\b(api/[\w./-]+)\b",
        r"\b(trading/[\w./-]+)\b",
        r"\b(src/requests/[\w./-]+)\b",
    ]
    found: List[str] = []
    for pat in patterns:
        for match in re.findall(pat, text, flags=re.IGNORECASE):
            found.append(_normalize_path(match))
    return list(dict.fromkeys(found))


def _file_hit(required: str, mentioned: List[str]) -> bool:
    req = _normalize_path(required)
    return any(req in m or m.endswith(req) for m in mentioned)


def score_run(
    task: TaskDef,
    gold: Dict[str, Any],
    artifact: RunArtifact,
) -> TaskScore:
    text = artifact.response_text or ""
    mentioned = _mentioned_files(text)
    required = gold.get("required_files") or []
    unacceptable = gold.get("unacceptable_hallucinations") or []
    is_negative = bool(gold.get("is_negative_control"))

    required_hit = [f for f in required if _file_hit(f, mentioned)]
    required_miss = [f for f in required if f not in required_hit]

    hallucinations: List[str] = []
    lower = text.lower()
    for rule in unacceptable:
        rule_lower = rule.lower()
        if "inventing" in rule_lower or "claiming" in rule_lower:
            # heuristic: fake path patterns
            for fake in ("graphql.py", "oauth.py", "retry.py", "jwt.py"):
                if fake in lower and not any(fake in _normalize_path(r) for r in required):
                    if is_negative and fake == "graphql.py":
                        continue
                    hallucinations.append(f"mentioned_{fake}")
        if "graphql" in rule_lower and is_negative:
            if re.search(r"\byes\b.*graphql|\bimplements graphql\b|\bgraphql server is\b", lower):
                hallucinations.append("false_graphql_yes")

    if is_negative:
        if re.search(r"\bno graphql\b|\bdoes not implement\b|\bnot implement\b|\bno\b.*\bgraphql\b", lower):
            correctness = 5.0 if not hallucinations else 2.0
        elif re.search(r"\byes\b.*graphql|\bimplements graphql\b|\bgraphql server is\b", lower):
            correctness = 0.0
            hallucinations.append("claimed_graphql_exists")
        else:
            correctness = 2.0
        completeness = 4.0 if "search" in lower or "file" in lower else 2.0
    else:
        core_keywords = []
        if task.task_id == "pilot_001":
            core_keywords = ["auth/", "login", "session", "middleware"]
        elif task.task_id == "pilot_002":
            core_keywords = ["adapters.py", "urllib3", "retry"]
        elif task.task_id == "pilot_003":
            core_keywords = ["routes", "middleware", "order", "execution"]
        elif task.task_id == "pilot_004":
            core_keywords = ["login", "session"]
        elif task.task_id == "pilot_005":
            core_keywords = ["middleware", "headers", "authorization"]
        kw_hit = sum(1 for k in core_keywords if k.lower() in lower)
        correctness = min(5.0, 1.0 + kw_hit * 1.2)
        completeness = min(5.0, len(required_hit) * 1.5 + (1.0 if kw_hit >= 2 else 0))

    if required:
        citation_accuracy = min(5.0, (len(required_hit) / len(required)) * 5.0)
    else:
        citation_accuracy = 5.0 if is_negative and not hallucinations else 3.0

    evidence_quality = 3.0
    if "```" in text or "Tool:" in text:
        evidence_quality += 1.0
    if artifact.files_inspected:
        evidence_quality = min(5.0, evidence_quality + 0.5)
    if artifact.atlas_tool_calls:
        evidence_quality = min(5.0, evidence_quality + 1.0)

    hallucination_avoidance = 5.0 - min(5.0, len(hallucinations) * 2.0)
    actionability = min(5.0, citation_accuracy * 0.6 + correctness * 0.4)

    dims = [
        correctness,
        completeness,
        citation_accuracy,
        evidence_quality,
        hallucination_avoidance,
        actionability,
    ]
    total = round(sum(dims), 2)
    task_success = total >= 18.0 and hallucination_avoidance >= 3.0

    return TaskScore(
        run_id=artifact.run_id,
        blind_id=artifact.blind_id,
        task_id=artifact.task_id,
        condition=artifact.condition,
        correctness=round(correctness, 2),
        completeness=round(completeness, 2),
        citation_accuracy=round(citation_accuracy, 2),
        evidence_quality=round(evidence_quality, 2),
        hallucination_avoidance=round(hallucination_avoidance, 2),
        actionability=round(actionability, 2),
        total_score=total,
        task_success=task_success,
        required_files_hit=required_hit,
        required_files_miss=required_miss,
        hallucinations_found=hallucinations,
        notes="deterministic_v1; human review recommended",
    )
