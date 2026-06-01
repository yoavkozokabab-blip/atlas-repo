"""Deterministic question classification for RU-3 (design-only taxonomy).

``classify_question_detail`` exposes the fine-grained category. ``coarse_mode``
mirrors the legacy ``ask.classify()`` contract so public routing stays compatible.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from . import retrieval

QUESTION_UNDERSTANDING_ENABLED = True

MIN_SCORE = 2.0
MIN_MARGIN = 1.0

_RISK_RE = re.compile(
    r"\b(risk|risks|risky|danger|dangerous|debt|fragile|fragility|unsafe|"
    r"weak|weakness|hotspot|vulnerab\w*|problem area)\b",
    re.IGNORECASE,
)

# (pattern, category, weight, rule_id)
_TIER1: List[Tuple[re.Pattern[str], str, int, str]] = [
    (
        re.compile(
            r"\bconcentration of production\b|\bhighest concentration of production\b|"
            r"\bwhere is the production code\b|\bproduction vs test layout\b|"
            r"\bdensity\b.{0,20}\bproduction\b|\bproduction.{0,20}\bdensity\b",
            re.IGNORECASE,
        ),
        "production_layout",
        5,
        "anchor:production_layout",
    ),
    (
        re.compile(
            r"\bmost central\b|\bcentral according to the dependency graph\b|"
            r"\bdependency graph\b.{0,30}\bcentral\b|\bsubsystem centrality\b",
            re.IGNORECASE,
        ),
        "subsystem_centrality",
        4,
        "anchor:subsystem_centrality",
    ),
    (
        re.compile(
            r"\bincoming dependenc\w*\b|\bhighest number of incoming\b|"
            r"\bmost imported modules?\b|\btop imported modules?\b",
            re.IGNORECASE,
        ),
        "dependency_centrality",
        4,
        "anchor:dependency_centrality",
    ),
    (
        re.compile(
            r"\bbottlenecks?\b|\barchitectural bottlenecks?\b|\bcritical architectural\b|"
            r"\barchitectural risk\b|\barchitecture risk\b|\brisk modules?\b|"
            r"\briskiest modules?\b|\bblast radius\b|\bfan[\s-]?in\b|"
            r"\bimport cycles?\b|\bdependency cycles?\b|"
            r"\bcircular (?:imports?|dependenc\w+)\b|\bstructural fragility\b|"
            r"\b(?:highly|most) coupled\b|\bmost depended\b",
            re.IGNORECASE,
        ),
        "bottleneck",
        4,
        "anchor:bottleneck",
    ),
    (
        re.compile(
            r"\bexecution path\b|\bwhat happens when\b|\bflow when\b|\bpath .{0,20} reaches\b",
            re.IGNORECASE,
        ),
        "execution_path",
        5,
        "anchor:execution_path",
    ),
    (
        re.compile(
            r"\bwhat breaks\b|\bimpact of changing\b|\bwhat depends on\b|"
            r"\baffected if\b.{0,20}\bchange\b|\bsafe to change\b",
            re.IGNORECASE,
        ),
        "impact",
        5,
        "anchor:impact",
    ),
    (
        re.compile(
            r"\bentry point\b|\bentrypoint\b|\bwhere does .{0,30} start\b|"
            r"\bmain entry\b|\bhow is it launched\b",
            re.IGNORECASE,
        ),
        "entrypoint",
        5,
        "anchor:entrypoint",
    ),
    (
        re.compile(
            r"\bwho owns\b|\bwho maintains\b|\bowner of\b|\bmaintainer\b|\bcodeowners\b",
            re.IGNORECASE,
        ),
        "ownership",
        5,
        "anchor:ownership",
    ),
    (
        re.compile(
            r"\binjection\b|\btaint\b|\bsecurity risk\b|\bunsafe input\b|\bcwe\b",
            re.IGNORECASE,
        ),
        "security",
        4,
        "anchor:security",
    ),
    (
        re.compile(
            r"\bbug\b|\blogic error\b|\banaly[sz]e\b.{0,40}\bfile\b|\bis .{0,30} broken\b",
            re.IGNORECASE,
        ),
        "bug_analysis",
        4,
        "anchor:bug_analysis",
    ),
    (
        re.compile(
            r"\bdepends on\b|\bdependencies of\b|\bcoupled to\b|\bwhat does .{0,40} import\b",
            re.IGNORECASE,
        ),
        "dependency",
        3,
        "anchor:dependency",
    ),
    (
        re.compile(r"\bsubsystems?\b", re.IGNORECASE),
        "subsystem",
        3,
        "anchor:subsystem",
    ),
    (
        re.compile(
            r"\barchitectur\w*\b|\boverall structure\b|\bhigh level\b|\boverview of the system\b",
            re.IGNORECASE,
        ),
        "architecture",
        2,
        "anchor:architecture",
    ),
]

_WEAK_LEXICONS: Dict[str, Tuple[str, ...]] = {
    "production_layout": ("production", "folder", "directory", "layout", "density", "concentration"),
    "subsystem_centrality": ("central", "centrality", "subsystem", "important"),
    "dependency_centrality": ("incoming", "imported", "module", "dependency", "depend"),
    "bottleneck": ("bottleneck", "critical", "central", "hub", "fan", "cycle", "cycles", "coupled", "coupling", "blast"),
    "execution_path": ("execution", "path", "flow", "happens", "reach"),
    "impact": ("break", "impact", "change", "affect", "depend"),
    "architecture": ("architecture", "structure", "overview", "system"),
    "subsystem": ("subsystem", "module", "component"),
}

RU3_PUBLIC_MODES = {
    "production_layout": "production_layout",
    "dependency_centrality": "dependency",
    "subsystem_centrality": "subsystem",
    "bottleneck": "bottleneck",
    "impact": "impact",
}


def coarse_classify(question: str) -> str:
    """Legacy coarse classifier (must match ``ask.classify`` exactly)."""
    if _RISK_RE.search(question):
        return "risk"
    if retrieval.is_architecture_question(question):
        return "architecture"
    return "retrieval"


def public_answer_mode(question: str, detail: Dict[str, Any]) -> str:
    """Map fine category to ``answer()`` mode with RU-2 compatibility."""
    category = detail.get("category", "unknown")
    if category in RU3_PUBLIC_MODES:
        return RU3_PUBLIC_MODES[category]
    return coarse_classify(question)


def classify_question_detail(question: str) -> Dict[str, Any]:
    """Return fine-grained RU-3 classification metadata."""
    coarse = coarse_classify(question)
    matches: List[Tuple[int, str, str, re.Match[str]]] = []
    for pattern, category, weight, rule_id in _TIER1:
        match = pattern.search(question)
        if match:
            matches.append((weight, category, rule_id, match))

    if matches:
        matches.sort(key=lambda item: (-item[0], item[2]))
        top_weight, category, rule_id, _match = matches[0]
        alternatives = sorted({item[1] for item in matches[1:] if item[1] != category})
        confidence = "high" if top_weight >= 4 else "medium"
        if len(matches) > 1 and matches[1][0] == top_weight:
            confidence = "medium"
        return {
            "category": category,
            "confidence": confidence,
            "fired_rule": rule_id,
            "alternatives": alternatives,
            "coarse_mode": coarse,
        }

    tokens = set(retrieval.tokenize(question))
    scores: Dict[str, float] = {}
    for category, lexicon in _WEAK_LEXICONS.items():
        scores[category] = float(sum(1 for term in lexicon if term in tokens))

    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    if not ranked or ranked[0][1] < MIN_SCORE:
        return {
            "category": "unknown",
            "confidence": "unknown",
            "fired_rule": "tier2:none",
            "alternatives": [],
            "coarse_mode": coarse,
        }

    top_cat, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    if top_score - second_score < MIN_MARGIN:
        return {
            "category": "unknown",
            "confidence": "unknown",
            "fired_rule": "tier2:ambiguous",
            "alternatives": sorted({cat for cat, score in ranked[:2] if score > 0}),
            "coarse_mode": coarse,
        }

    confidence = "high" if top_score >= MIN_SCORE + 2 else "medium"
    alternatives = sorted(
        cat for cat, score in ranked[1:3] if score > 0 and cat != top_cat
    )
    return {
        "category": top_cat,
        "confidence": confidence,
        "fired_rule": f"tier2:{top_cat}",
        "alternatives": alternatives,
        "coarse_mode": coarse,
    }
