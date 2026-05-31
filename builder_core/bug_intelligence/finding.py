"""Unified finding schema for the Builder Intelligence Engine (Phase 90).

One Finding type used by logic, algorithm, security, maintainability, and
test-gap detections. Adapters map the legacy finding shapes (pattern dataclass,
security Finding89, semantic dicts) onto this single schema so the engine has a
single output model.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List

# --- categories (the required, closed set) ---------------------------------
LOGIC_BUG = "logic_bug"
ALGORITHM_BUG = "algorithm_bug"
SECURITY_RISK = "security_risk"
MAINTAINABILITY = "maintainability"
TEST_GAP = "test_gap"
UNKNOWN = "unknown"

CATEGORIES = {LOGIC_BUG, ALGORITHM_BUG, SECURITY_RISK, MAINTAINABILITY, TEST_GAP, UNKNOWN}

SEVERITY_WEIGHT = {"critical": 4, "high": 3, "medium": 2, "low": 1}
CONFIDENCE_WEIGHT = {"high": 1.0, "medium": 0.6, "low": 0.3}
_CONF_ORDER = {"high": 3, "medium": 2, "low": 1}


@dataclass
class Finding:
    category: str
    kind: str                       # provenance/family: data_flow | value_flow | security | semantic | pattern
    severity: str                   # critical | high | medium | low
    confidence: str                 # high | medium | low
    file: str
    line: int
    title: str
    explanation: str
    why_might_be_wrong: str
    next_verification_step: str
    function: str = ""
    evidence: str = ""
    rule: str = ""
    source_facts: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    id: str = ""

    def __post_init__(self):
        if self.category not in CATEGORIES:
            self.category = UNKNOWN
        if not self.id:
            digest = hashlib.sha1(
                f"{self.category}|{self.rule}|{self.file}|{self.line}".encode("utf-8")
            ).hexdigest()[:8]
            self.id = f"BI-{self.category[:4].upper()}-{digest}"
        # always carry category/severity/kind as tags for filtering
        for t in (self.category, self.kind, self.severity, self.rule):
            if t and t not in self.tags:
                self.tags.append(t)

    @property
    def weight(self) -> float:
        return SEVERITY_WEIGHT.get(self.severity, 1) * CONFIDENCE_WEIGHT.get(self.confidence, 0.3)

    def key(self) -> tuple:
        # collapse the same rule reported at the same line by different detector
        # sources; fall back to title when a finding has no rule name.
        return (self.file, self.line, self.rule or self.title)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "category": self.category, "kind": self.kind,
            "severity": self.severity, "confidence": self.confidence,
            "file": self.file, "function": self.function, "line": self.line,
            "title": self.title, "explanation": self.explanation,
            "evidence": self.evidence, "source_facts": list(self.source_facts),
            "why_might_be_wrong": self.why_might_be_wrong,
            "next_verification_step": self.next_verification_step,
            "tags": list(self.tags), "rule": self.rule,
        }


def dedupe(findings: List[Finding]) -> List[Finding]:
    seen = set()
    out: List[Finding] = []
    for f in findings:
        if f.key() not in seen:
            out.append(f)
            seen.add(f.key())
    return out


def rank(findings: List[Finding]) -> List[Finding]:
    # Sort first (strongest first), THEN dedupe, so that when two detector
    # sources emit the same (file, line, rule) the higher-weight finding
    # survives (required once a fact-backed detector is promoted — Phase 93B).
    ordered = sorted(
        findings,
        key=lambda f: (-f.weight, -_CONF_ORDER.get(f.confidence, 0), f.file, f.line, f.rule),
    )
    return dedupe(ordered)


# ---------------------------------------------------------------------------
# Category mapping + guidance for migrated pattern rules
# ---------------------------------------------------------------------------
PATTERN_CATEGORY = {
    "unguarded_container_consumption": LOGIC_BUG,
    "inconsistent_return": LOGIC_BUG,
    "off_by_one": LOGIC_BUG,
    "mutation_while_iterating": LOGIC_BUG,
    "unreachable_code": LOGIC_BUG,
    "recursion_no_termination": LOGIC_BUG,
    "suspicious_conditional": LOGIC_BUG,
    "impossible_condition": LOGIC_BUG,
    "duplicated_branches": LOGIC_BUG,
    "reversed_comparison": LOGIC_BUG,
    "unused_result": LOGIC_BUG,
    "algorithm_mismatch": ALGORITHM_BUG,
    "unused_variable": MAINTAINABILITY,
    "shadowed_name": MAINTAINABILITY,
    "untested_module": TEST_GAP,
    "untested_function": TEST_GAP,
    "syntax_error": LOGIC_BUG,
}
FACT_BACKED_RULES = {"unguarded_container_consumption"}

_GENERIC_WHY = (
    "This is a deterministic static signal, not a proof; a guarantee the "
    "intraprocedural analysis cannot see (a caller invariant, a guard in another "
    "form) may make it safe."
)
_GENERIC_NEXT = (
    "Read the cited line in context and confirm against the function's tests "
    "whether the flagged condition can actually occur."
)
RULE_GUIDANCE = {
    "unguarded_container_consumption": (
        "The loop may be bounded by a condition the container-state facts did not model.",
        "Confirm the loop can exit when the container is empty; if not, guard on the container.",
    ),
    "inconsistent_return": (
        "Mixed return shapes can be intentional (e.g. value-or-None APIs).",
        "Check every return path and the callers' expectations for a consistent contract.",
    ),
    "off_by_one": (
        "Inclusive bounds against len() are sometimes correct (e.g. DP tables).",
        "Verify the index range against the indexed sequence's valid bounds.",
    ),
    "mutation_while_iterating": (
        "Some iterators tolerate mutation, or a copy may be iterated.",
        "Confirm the iterated object is the one being mutated; iterate a copy if so.",
    ),
    "unreachable_code": (
        "The preceding terminator may be conditional in a way not modeled.",
        "Confirm the statement is genuinely unreachable and remove or fix the control flow.",
    ),
    "recursion_no_termination": (
        "A base case may exist in a form not recognized (e.g. exception, external guard).",
        "Confirm a base case reduces the argument toward termination on every path.",
    ),
}


def from_pattern_finding(pf, file: str) -> Finding:
    rule = pf.rule
    category = PATTERN_CATEGORY.get(rule, UNKNOWN)
    why, nxt = RULE_GUIDANCE.get(rule, (_GENERIC_WHY, _GENERIC_NEXT))
    return Finding(
        category=category,
        kind="data_flow" if rule in FACT_BACKED_RULES else "pattern",
        severity=pf.severity, confidence=pf.confidence,
        file=file, line=pf.line, function=pf.function or "",
        title=pf.title, explanation=pf.message, evidence=pf.evidence,
        why_might_be_wrong=why, next_verification_step=nxt,
        rule=rule, source_facts=[f"{rule} @ line {pf.line}"],
    )


def from_security_finding(sf, file: str) -> Finding:
    is_value = getattr(sf, "kind", "security") == "value"
    return Finding(
        category=LOGIC_BUG if is_value else SECURITY_RISK,
        kind="value_flow" if is_value else "security",
        severity=sf.severity, confidence=sf.confidence,
        file=file, line=sf.line,
        title=sf.category.replace("_", " "),
        explanation=sf.explanation, evidence=sf.evidence,
        why_might_be_wrong=sf.why_might_be_wrong,
        next_verification_step=sf.next_verification_step,
        rule=sf.category,
        source_facts=(["nullability fact"] if is_value else ["taint source -> sensitive sink"]),
        tags=[sf.category, sf.id],
    )


def from_semantic_finding(d: Dict[str, Any], file: str) -> Finding:
    rule = d.get("rule", "semantic")
    return Finding(
        category=ALGORITHM_BUG, kind="semantic",
        severity=d.get("severity", "medium"), confidence="high",
        file=file, line=int(d.get("line", 1)),
        title=rule, explanation=d.get("message", ""),
        evidence=d.get("evidence", ""),
        why_might_be_wrong=(
            "Algorithm-profile reasoning matches structure/name; an unconventional but "
            "correct implementation can trip it."
        ),
        next_verification_step=(
            "Confirm the implementation against the algorithm's expected invariants and tests."
        ),
        rule=rule, source_facts=["algorithm profile + invariant check"],
        tags=[rule, "semantic"] + (["has_test_expectations"] if d.get("related_tests") else []),
    )
