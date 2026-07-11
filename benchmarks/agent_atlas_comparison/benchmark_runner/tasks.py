"""Task, repository, and gold-answer loading."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .paths import GOLD_DIR, REPOSITORIES_PATH, TASKS_DIR


@dataclass(frozen=True)
class BenchmarkTask:
    task_id: str
    title: str
    repository_id: str
    category: str
    difficulty: str
    prompt: str
    gold_file: str
    condition_order: tuple[str, ...]
    metadata: dict[str, Any]

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> "BenchmarkTask":
        return cls(
            task_id=raw["task_id"],
            title=raw["title"],
            repository_id=raw["repository_id"],
            category=raw["category"],
            difficulty=raw["difficulty"],
            prompt=raw["prompt"],
            gold_file=raw["gold_file"],
            condition_order=tuple(raw.get("condition_order") or ()),
            metadata=dict(raw.get("metadata") or {}),
        )

    @property
    def gold_path(self) -> Path:
        return GOLD_DIR / Path(self.gold_file).name


@dataclass(frozen=True)
class RepositorySpec:
    repo_id: str
    role: str
    source: str
    commit_sha: str
    path: str | None
    remote_url: str | None
    branch: str | None
    observed_tree_file_count: int | None

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> "RepositorySpec":
        return cls(
            repo_id=raw["id"],
            role=raw.get("role", ""),
            source=raw.get("source", ""),
            commit_sha=raw.get("commit_sha", ""),
            path=raw.get("path"),
            remote_url=raw.get("remote_url"),
            branch=raw.get("branch"),
            observed_tree_file_count=raw.get("observed_tree_file_count"),
        )


@dataclass(frozen=True)
class GoldSpec:
    task_id: str
    required_files: tuple[str, ...]
    optional_files: tuple[str, ...]
    unacceptable_hallucinations: tuple[str, ...]
    raw_text: str


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_tasks(task_ids: list[str] | None = None) -> list[BenchmarkTask]:
    wanted = set(task_ids or [])
    tasks = [BenchmarkTask.from_json(load_json(path)) for path in sorted(TASKS_DIR.glob("task_*.json"))]
    if wanted:
        tasks = [task for task in tasks if task.task_id in wanted]
    return tasks


def load_repositories() -> dict[str, RepositorySpec]:
    raw = load_json(REPOSITORIES_PATH)
    return {item["id"]: RepositorySpec.from_json(item) for item in raw.get("repositories", [])}


def _section(text: str, heading: str) -> str:
    pattern = rf"^## {re.escape(heading)}\s*$"
    match = re.search(pattern, text, re.MULTILINE)
    if not match:
        return ""
    start = match.end()
    next_heading = re.search(r"^## ", text[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(text)
    return text[start:end].strip()


def _bullet_items(section: str) -> tuple[str, ...]:
    items: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        item = stripped[2:].strip()
        if item.startswith("`") and "`" in item[1:]:
            item = item.split("`", 2)[1]
        items.append(item)
    return tuple(items)


def load_gold(task: BenchmarkTask) -> GoldSpec:
    text = task.gold_path.read_text(encoding="utf-8")
    required = _bullet_items(_section(text, "Required Files"))
    if not required:
        required = _bullet_items(_section(text, "Required Files Or Absence Checks"))
    optional = _bullet_items(_section(text, "Optional Supporting Files"))
    if not optional:
        optional = _bullet_items(_section(text, "Optional Supporting Evidence"))
    unacceptable = _bullet_items(_section(text, "Unacceptable Hallucinations"))
    return GoldSpec(
        task_id=task.task_id,
        required_files=required,
        optional_files=optional,
        unacceptable_hallucinations=unacceptable,
        raw_text=text,
    )
