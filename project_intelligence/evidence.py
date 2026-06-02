"""Evidence records and JARVIS-only path safety for Project Intelligence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config import PROJECT_ROOT

JARVIS_ROOT: Path = PROJECT_ROOT

CONTAMINATION_FRAGMENTS: frozenset[str] = frozenset({
    "algo_trader",
    "FINAL_ALGO_TRADER",
    "live_paper",
    "scheduled_logs",
    "paper_trade",
})

META_EVIDENCE_FRAGMENTS: frozenset[str] = frozenset({
    "test_project_intelligence_questions.py",
    "phase80_project_intelligence.md",
    "phase80_sample_outputs.txt",
    "phase80_smoke_samples.json",
    "project_intelligence_actions.py",
    "gen_phase80_samples.py",
    "smoke_project_intelligence_questions.py",
})


@dataclass(frozen=True)
class Evidence:
    path: Path
    passage: str
    score: float
    source_kind: str = "file"


def is_contaminated(path: Path) -> bool:
    text = str(path)
    return any(frag in text for frag in CONTAMINATION_FRAGMENTS)


def is_meta_evidence(path: Path) -> bool:
    name = path.name.lower()
    return any(frag in name for frag in META_EVIDENCE_FRAGMENTS)


def is_within_jarvis(path: Path) -> bool:
    try:
        path.relative_to(JARVIS_ROOT)
    except ValueError:
        return False
    return not is_contaminated(path) and not is_meta_evidence(path)


def read_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def rel_path(path: Path) -> str:
    try:
        return str(path.relative_to(JARVIS_ROOT))
    except ValueError:
        return str(path)
