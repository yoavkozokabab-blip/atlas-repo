"""Generate sample outputs for Phase 80 report (dev utility)."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from project_intelligence.engine import answer_question

QUESTIONS = [
    "Why was Phase 73A built?",
    "What problem does Phase 79 solve?",
    "What are the biggest architectural risks in the current JARVIS codebase?",
    "What should be built next and why?",
    "Summarize the current state of the project in under 500 words.",
    "What are the most important unfinished phases?",
    "What changed in the last 30 days?",
    "What decisions were made recently that could affect future architecture?",
    "If a new developer joined today, what would they need to understand first?",
    "What parts of the codebase appear unrelated to Jarvis for Builders?",
]

root = Path(__file__).resolve().parents[1]
out_path = root / "reports" / "phase80_sample_outputs.txt"
lines: list[str] = []
for index, question in enumerate(QUESTIONS, start=1):
    result = answer_question(question)
    summary = result.summary or ""
    lines.append("=" * 72)
    lines.append(f"Q{index}: {question}")
    lines.append("-" * 72)
    lines.append(summary[:1200])
    lines.append("")
out_path.write_text("\n".join(lines), encoding="utf-8")
print(f"wrote {out_path}")
