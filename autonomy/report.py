"""Autonomous Agent Stack v1 — deterministic, extractive final report.

The report is built ONLY from observed page content (titles, headings, visible
text). It does not invent facts. Confidence is a transparent function of how
many planned sources succeeded and how many steps verified.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class SourceEvidence:
    url: str
    title: str
    facts: list[str] = field(default_factory=list)
    summary: str = ""


def extract_facts(visible_text: str, *, max_facts: int = 4) -> list[str]:
    """Pick a few substantial sentences/lines as evidence (extractive only)."""
    text = re.sub(r"[ \t]+", " ", (visible_text or "").replace("\r", " "))
    candidates = re.split(r"(?<=[.!?])\s+|\n", text)
    facts: list[str] = []
    seen: set[str] = set()
    for c in candidates:
        c = c.strip()
        if len(c) < 50 or len(c) > 300:
            continue
        key = c.lower()[:80]
        if key in seen:
            continue
        seen.add(key)
        facts.append(c)
        if len(facts) >= max_facts:
            break
    return facts


def compute_confidence(*, sources_collected: int, sources_planned: int,
                       steps_total: int, steps_verified: int) -> float:
    if sources_planned <= 0 or steps_total <= 0:
        return 0.0
    src_ratio = min(1.0, sources_collected / sources_planned)
    step_ratio = steps_verified / steps_total
    # Weighted; never claim high confidence with zero sources.
    conf = 0.6 * src_ratio + 0.4 * step_ratio
    if sources_collected == 0:
        return 0.0
    return round(min(0.95, conf), 3)


def _disagreements(sources: list[SourceEvidence]) -> list[str]:
    """Lightweight heuristic: flag sources whose titles share few keywords."""
    if len(sources) < 2:
        return []
    def toks(s: str) -> set[str]:
        return {t for t in re.split(r"\W+", (s or "").lower()) if len(t) > 3}
    base = toks(sources[0].title)
    notes: list[str] = []
    for s in sources[1:]:
        overlap = base & toks(s.title)
        if not overlap:
            notes.append(f"'{s.title[:60]}' covers a different angle than the top source.")
    return notes[:3]


def build_report(
    *,
    goal: str,
    mode: str,
    sources: list[SourceEvidence],
    attempted: list[str],
    failures: list[str],
    safety_skips: list[str],
    confidence: float,
) -> str:
    lines: list[str] = [f"# Autonomous research report", "", f"**Goal:** {goal}", f"**Mode:** {mode}", ""]

    # Direct answer
    lines.append("## Direct answer")
    if sources:
        top = sources[0]
        answer = top.facts[0] if top.facts else (top.summary[:240] or top.title)
        lines.append(answer or "(no direct extractive answer available)")
        lines.append(f"\n_Primary source: {top.title or top.url} — {top.url}_")
    else:
        lines.append("No sources could be opened and verified, so no answer is asserted.")
    lines.append("")

    # Key findings
    lines.append("## Key findings")
    if sources:
        for s in sources:
            for f in s.facts[:2]:
                lines.append(f"- {f}  _(source: {s.url})_")
    else:
        lines.append("- (none)")
    lines.append("")

    # Sources
    lines.append("## Sources")
    if sources:
        for i, s in enumerate(sources, 1):
            lines.append(f"{i}. {s.title or '(untitled)'} — {s.url}")
    else:
        lines.append("(none)")
    lines.append("")

    # Evidence summary
    lines.append("## Evidence summary")
    for s in sources:
        lines.append(f"### {s.title or s.url}")
        lines.append(s.summary[:600] or "(no summary)")
        lines.append("")

    # Disagreements
    dis = _disagreements(sources)
    lines.append("## Disagreements between sources")
    lines.extend([f"- {d}" for d in dis] or ["- None detected (note: automated detection is heuristic)."])
    lines.append("")

    # Confidence
    lines.append("## Uncertainty / confidence")
    lines.append(f"- confidence: {confidence:.2f} (sources collected: {len(sources)})")
    lines.append("- This report is extractive (verbatim page text), not generative; verify critical claims.")
    lines.append("")

    # Process transparency
    lines.append("## What JARVIS tried")
    lines.extend([f"- {a}" for a in attempted] or ["- (nothing)"])
    lines.append("")
    lines.append("## What failed")
    lines.extend([f"- {f}" for f in failures] or ["- (no failures)"])
    lines.append("")
    lines.append("## Skipped for safety")
    lines.extend([f"- {s}" for s in safety_skips] or ["- (nothing blocked during this run)"])
    lines.append("")
    lines.append("## Next recommended actions")
    if sources:
        lines.append("- Review the primary source directly for full context.")
        lines.append("- Run `compare sources for <goal>` to weigh multiple sources.")
    else:
        lines.append("- Retry with a more specific query, or check network/provider availability.")
    return "\n".join(lines)
