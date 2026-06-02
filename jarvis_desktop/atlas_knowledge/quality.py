"""Knowledge quality tiers for Atlas (Phase 128)."""

from __future__ import annotations

from typing import Dict, Optional

QUALITY_TIERS = (
    "generated_template",
    "curated_basic",
    "curated_deep",
    "source_backed",
)

QUALITY_RANK: Dict[str, int] = {
    "generated_template": 0,
    "curated_basic": 1,
    "curated_deep": 2,
    "source_backed": 3,
}

QUALITY_UI_LABEL: Dict[str, str] = {
    "generated_template": "Local generated",
    "curated_basic": "Curated",
    "curated_deep": "Curated",
    "source_backed": "Source-backed",
}


def normalize_quality(value: Optional[str]) -> str:
    v = (value or "generated_template").strip().lower()
    if v in QUALITY_RANK:
        return v
    return "generated_template"


def quality_rank(value: Optional[str]) -> int:
    return QUALITY_RANK.get(normalize_quality(value), 0)


def quality_ui_label(value: Optional[str]) -> str:
    return QUALITY_UI_LABEL.get(normalize_quality(value), "Local generated")


def quality_confidence_boost(value: Optional[str]) -> float:
    """Alias-score boost so curated/source-backed wins ties over pack templates."""
    return {0: 0.0, 1: 0.75, 2: 1.25, 3: 2.0}.get(quality_rank(value), 0.0)


def is_shallow_generated(value: Optional[str]) -> bool:
    return normalize_quality(value) == "generated_template"
