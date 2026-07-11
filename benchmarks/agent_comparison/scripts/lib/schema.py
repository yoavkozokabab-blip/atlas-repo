"""Agent comparison benchmark schemas."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[4]
BENCHMARK_ROOT = Path(__file__).resolve().parents[2]

CONDITIONS = (
    "codex_no_atlas",
    "codex_with_atlas",
    "cursor_no_atlas",
    "cursor_with_atlas",
)

WITH_ATLAS = frozenset({"codex_with_atlas", "cursor_with_atlas"})
AGENTS = ("codex", "cursor")


@dataclass
class TaskDef:
    task_id: str
    repo_id: str
    category: str
    difficulty: str
    prompt: str
    gold_file: str

    def repo_path(self, repos: Dict[str, Any]) -> Path:
        rel = repos[self.repo_id]["path"]
        return (ROOT / rel).resolve()

    def gold_path(self) -> Path:
        return (BENCHMARK_ROOT / self.gold_file).resolve()


@dataclass
class RunArtifact:
    run_id: str
    blind_id: str
    task_id: str
    condition: str
    agent: str
    atlas_enabled: bool
    repeat: int
    prompt: str
    repo_id: str
    repo_path: str
    repo_commit_sha: Optional[str]
    execution_backend: str
    model_tool_version: str
    started_at: str
    ended_at: str
    latency_seconds: float
    ok: bool
    error: str = ""
    response_text: str = ""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    atlas_tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    files_inspected: List[str] = field(default_factory=list)
    retries: int = 0
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TaskScore:
    run_id: str
    blind_id: str
    task_id: str
    condition: str
    correctness: float
    completeness: float
    citation_accuracy: float
    evidence_quality: float
    hallucination_avoidance: float
    actionability: float
    total_score: float
    task_success: bool
    required_files_hit: List[str] = field(default_factory=list)
    required_files_miss: List[str] = field(default_factory=list)
    hallucinations_found: List[str] = field(default_factory=list)
    scorer: str = "deterministic_v1"
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def load_repositories() -> Dict[str, Any]:
    data = load_json(BENCHMARK_ROOT / "repositories.json")
    return {item["id"]: item for item in data["repositories"]}


def load_tasks() -> List[TaskDef]:
    tasks_dir = BENCHMARK_ROOT / "tasks"
    out: List[TaskDef] = []
    for path in sorted(tasks_dir.glob("pilot_*.json")):
        raw = load_json(path)
        out.append(TaskDef(**raw))
    return out


def parse_gold(gold_path: Path) -> Dict[str, Any]:
    text = gold_path.read_text(encoding="utf-8")
    required: List[str] = []
    unacceptable: List[str] = []
    section = ""
    for line in text.splitlines():
        if line.startswith("## Required files"):
            section = "required"
            continue
        if line.startswith("## Unacceptable hallucinations"):
            section = "unacceptable"
            continue
        if line.startswith("## "):
            section = ""
            continue
        if section == "required" and line.strip().startswith("- `"):
            required.append(line.strip().strip("- ").strip("`"))
        if section == "unacceptable" and line.strip().startswith("- "):
            unacceptable.append(line.strip()[2:])
    core = ""
    if "## Expected core answer" in text:
        core = text.split("## Expected core answer", 1)[1].split("##", 1)[0].strip()
    is_negative = "negative_control" in gold_path.stem or "GraphQL" in text
    return {
        "core_answer": core,
        "required_files": required,
        "unacceptable_hallucinations": unacceptable,
        "is_negative_control": is_negative,
    }


def agent_from_condition(condition: str) -> str:
    if condition.startswith("codex"):
        return "codex"
    if condition.startswith("cursor"):
        return "cursor"
    raise ValueError(condition)
