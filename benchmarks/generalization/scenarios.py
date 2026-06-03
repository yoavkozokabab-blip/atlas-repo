"""Phase 136 — benchmark scenario definitions (generic across all repos).

These deliberately use generic, cross-framework prompts so the suite measures
GENERALIZATION, not Home-Assistant-specific tuning. Repo-relevant impact variants
come from ``RepoSpec.impact_concepts``.
"""

from __future__ import annotations

# 2 — Impact: generic concept prompts run on every repository.
GENERIC_IMPACT_CONCEPTS = [
    "authentication",
    "caching",
    "configuration",
    "the logging layer",
    "the database layer",
]

IMPACT_PROMPT_TEMPLATE = "what breaks if I remove {concept}"

# 3 — Investigation symptoms (runtime/system behavior).
INVESTIGATION_SYMPTOMS = [
    "duplicate events are being fired",
    "websocket connections keep disconnecting",
    "authentication fails intermittently",
    "memory keeps growing over time",
    "API requests are slow under load",
]

# 4 — Build plan requests.
BUILD_REQUESTS = [
    "add distributed tracing",
    "add rate limiting",
    "add audit logging",
    "add feature flags",
]
