"""Autonomous Agent Stack v1 — bounded read-only research planner.

Planning is pure (no network, no browser). It builds a bounded, read-only plan
made only of allowed capabilities, with an expected verification and a recovery
strategy for every step, plus explicit limits and forbidden actions.

Approval semantics (documented):
  The plan is a *capability + limits envelope*. The exact result URLs are not
  known until SEARCH runs, so the approved hash covers: normalized goal, the
  ordered capability template, limits, allowed/forbidden actions, and (optional)
  allowed_domains. At runtime the executor may only open URLs surfaced by the
  approved SEARCH (or within allowed_domains) — never arbitrary navigation.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field

from autonomy.capabilities import (
    ALLOWED_CAPABILITIES,
    FORBIDDEN_CAPABILITIES,
    Capability,
    SafetyClass,
    classify_goal,
)
from autonomy.limits import RunLimits
from tooluse.contracts import ForbiddenGoalError


def normalize_goal(goal: str) -> str:
    return re.sub(r"\s+", " ", (goal or "").strip()).lower()


@dataclass(frozen=True)
class ResearchStep:
    index: int
    capability: Capability
    description: str
    expected_verification: str
    recovery_strategy: str
    params: tuple[tuple[str, str], ...] = ()   # hashable key/value pairs

    def param(self, key: str, default: str = "") -> str:
        for k, v in self.params:
            if k == key:
                return v
        return default

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "capability": self.capability.value,
            "description": self.description,
            "expected_verification": self.expected_verification,
            "recovery_strategy": self.recovery_strategy,
            "params": {k: v for k, v in self.params},
        }


@dataclass(frozen=True)
class AutonomousPlan:
    goal: str
    normalized_goal: str
    safety_class: SafetyClass
    mode: str                       # "research" | "compare"
    query: str
    steps: tuple[ResearchStep, ...]
    limits: RunLimits
    allowed_capabilities: tuple[str, ...]
    forbidden_actions: tuple[str, ...]
    allowed_domains: tuple[str, ...] = ()

    @property
    def is_dry_run(self) -> bool:
        return True

    def canonical(self) -> dict:
        return {
            "normalized_goal": self.normalized_goal,
            "mode": self.mode,
            "query": self.query,
            "steps": [s.to_dict() for s in self.steps],
            "limits": self.limits.as_dict(),
            "allowed_capabilities": sorted(self.allowed_capabilities),
            "forbidden_actions": sorted(self.forbidden_actions),
            "allowed_domains": sorted(self.allowed_domains),
        }

    @property
    def plan_hash(self) -> str:
        blob = json.dumps(self.canonical(), sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]

    def format(self) -> str:
        lines = [
            "Autonomous research plan (DRY RUN — nothing executed yet):",
            f"  goal: {self.goal}",
            f"  safety_class: {self.safety_class.value}",
            f"  mode: {self.mode}",
            f"  query: {self.query}",
            f"  limits: max_steps={self.limits.max_steps} max_sources={self.limits.max_sources} "
            f"max_runtime_seconds={self.limits.max_runtime_seconds}",
            f"  allowed_actions: {', '.join(self.allowed_capabilities)}",
            f"  blocked_actions: {', '.join(self.forbidden_actions[:10])} ...",
            f"  allowed_domains: {', '.join(self.allowed_domains) or '(any non-forbidden)'}",
            f"  plan_hash: {self.plan_hash}",
            "  steps:",
        ]
        for s in self.steps:
            lines.append(f"    {s.index}. [{s.capability.value}] {s.description}")
            lines.append(f"        verify: {s.expected_verification}")
            lines.append(f"        recover: {s.recovery_strategy}")
        return "\n".join(lines)


def _research_steps(mode: str, limits: RunLimits) -> tuple[ResearchStep, ...]:
    steps: list[ResearchStep] = [
        ResearchStep(1, Capability.SEARCH,
                     "Search the web for goal-relevant sources.",
                     "At least one organic (off-engine) result link is extracted.",
                     "Rewrite the query (bounded) and retry, then stop honestly."),
        ResearchStep(2, Capability.OPEN_RESULT,
                     "Open the most relevant non-ad result.",
                     "Navigated off the search engine; opened page has a title.",
                     "Skip broken/blocked pages; open the next candidate."),
        ResearchStep(3, Capability.EXTRACT_FACTS,
                     "Extract title and key textual facts from the page.",
                     "Non-trivial visible text / at least one fact extracted.",
                     "Re-observe once; if empty, skip source."),
        ResearchStep(4, Capability.SUMMARIZE,
                     f"Open and summarize up to {limits.max_sources} sources total.",
                     "Each opened source yields a usable summary.",
                     "Skip failing sources; reduce scope if too many fail."),
    ]
    if mode == "compare":
        steps.append(ResearchStep(5, Capability.COMPARE,
                                  "Compare evidence across the collected sources.",
                                  "At least two sources were collected to compare.",
                                  "If <2 sources, report partial comparison honestly."))
    steps.append(ResearchStep(len(steps) + 1, Capability.SYNTHESIZE,
                              "Synthesize a structured final report with sources and confidence.",
                              "A report with a direct answer and >=1 source is produced.",
                              "If no sources succeeded, report failure honestly."))
    return tuple(steps)


def build_research_plan(
    goal: str,
    *,
    mode: str = "research",
    limits: RunLimits | None = None,
    query: str | None = None,
    allowed_domains: tuple[str, ...] = (),
) -> AutonomousPlan:
    """Build a bounded read-only plan. Raises ForbiddenGoalError for unsafe goals."""
    goal = (goal or "").strip()
    if not goal:
        raise ValueError("goal must be non-empty")

    safety_class, forbidden_found = classify_goal(goal)
    if safety_class == SafetyClass.UNSAFE_FORBIDDEN:
        raise ForbiddenGoalError(
            "Goal rejected — implies a forbidden action "
            f"({', '.join(forbidden_found)}). The autonomous agent is read-only: "
            "no payments, orders, bookings, logins, submits, downloads, deletes, or sends."
        )

    if mode not in ("research", "compare"):
        mode = "research"
    lim = limits or RunLimits()
    steps = _research_steps(mode, lim)
    return AutonomousPlan(
        goal=goal,
        normalized_goal=normalize_goal(goal),
        safety_class=safety_class,
        mode=mode,
        query=(query or goal).strip(),
        steps=steps,
        limits=lim,
        allowed_capabilities=tuple(sorted(c.value for c in ALLOWED_CAPABILITIES)),
        forbidden_actions=tuple(FORBIDDEN_CAPABILITIES),
        allowed_domains=tuple(allowed_domains),
    )
