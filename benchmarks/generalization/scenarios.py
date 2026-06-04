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

# Phase 137 — the cross-cutting concepts that resolved at 0% coverage across ALL
# repositories in Phase 136 (HA-tuned resolver knew none of them). The generic
# concept resolver (impact_engine/concept_lexicon.py) targets exactly these.
# Added as explicit benchmark coverage so regressions here are caught; probed by
# the semantic probe and asserted by test_phase137_semantic_generalization.
PHASE137_ZERO_COVERAGE_CONCEPTS = [
    "the logging layer",
    "the event system",
    "background jobs",
    "scheduling",
    "state management",
    "the plugin system",
    "the api layer",
]

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
