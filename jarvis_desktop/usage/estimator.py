"""Phase 137A — Atlas compute / token-equivalent estimation (not real OpenAI tokens)."""

from __future__ import annotations

from typing import Any, Dict


def _size_tier(files: int, modules: int) -> str:
    f = max(int(files or 0), 0)
    m = max(int(modules or 0), 0)
    if f >= 20000 or m >= 8000:
        return "huge"
    if f >= 3000 or m >= 1500:
        return "large"
    if f >= 500 or m >= 200:
        return "medium"
    return "small"


def estimate_repo_cost(
    files: int,
    modules: int,
    edges: int,
    symbols: int,
    duration: float,
) -> Dict[str, Any]:
    """Estimate Atlas compute units for a repository operation."""
    f = max(int(files or 0), 0)
    m = max(int(modules or 0), 0)
    e = max(int(edges or 0), 0)
    s = max(int(symbols or 0), 0)
    d = max(float(duration or 0.0), 0.0)

    scan_units = round(
        (f / 120.0)
        + (m / 40.0)
        + (e / 180.0)
        + (s / 250.0)
        + (d / 8.0),
        2,
    )
    token_equivalent = int(round(scan_units * 850))
    tier = _size_tier(f, m)

    if tier == "huge":
        recommended = "ENTERPRISE"
    elif tier == "large":
        recommended = "TEAM"
    elif tier == "medium":
        recommended = "PRO"
    else:
        recommended = "FREE"

    return {
        "scan_units": scan_units,
        "token_equivalent_estimate": token_equivalent,
        "token_equivalent_label": "Atlas compute units (token-equivalent estimate — not billed OpenAI tokens)",
        "size_tier": tier,
        "recommended_plan": recommended,
    }
