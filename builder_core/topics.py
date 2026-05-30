"""Lightweight, deterministic topic inference for decisions and queries.

No ML. A keyword-to-topic table scored by match count. This is intentionally
small and high-precision; "general" is the honest default.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

# Ordered roughly by specificity. Each topic maps to trigger keywords.
TOPIC_KEYWORDS: Dict[str, List[str]] = {
    "database": [
        "database", "db", "postgres", "postgresql", "mysql", "sqlite",
        "mongo", "mongodb", "schema", "migration", "orm", "query", "sql",
        "index", "table",
    ],
    "authentication": [
        "auth", "authentication", "authorization", "login", "oauth", "jwt",
        "token", "session", "password", "credential", "sso", "permission",
    ],
    "api": [
        "api", "endpoint", "rest", "graphql", "grpc", "route", "handler",
        "request", "response", "webhook",
    ],
    "frontend": [
        "frontend", "ui", "react", "vue", "svelte", "css", "html",
        "component", "render", "browser-ui",
    ],
    "testing": [
        "test", "tests", "testing", "pytest", "unittest", "coverage",
        "mock", "fixture", "assertion",
    ],
    "infrastructure": [
        "infrastructure", "deploy", "deployment", "docker", "kubernetes",
        "k8s", "ci", "cd", "pipeline", "terraform", "cloud", "aws", "gcp",
        "azure", "hosting",
    ],
    "performance": [
        "performance", "latency", "throughput", "cache", "caching", "speed",
        "optimize", "optimization", "memory", "scalability", "scale",
    ],
    "security": [
        "security", "secure", "vulnerability", "encryption", "encrypt",
        "secret", "csrf", "xss", "injection", "sandbox",
    ],
    "architecture": [
        "architecture", "design", "pattern", "module", "layer", "coupling",
        "refactor", "boundary", "interface", "abstraction", "structure",
    ],
    "data": [
        "data", "pipeline", "etl", "ingest", "stream", "batch", "model",
        "embedding", "vector",
    ],
    "tooling": [
        "tooling", "build", "lint", "linter", "formatter", "dependency",
        "package", "bundler", "compiler",
    ],
}

_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> List[str]:
    return _WORD_RE.findall(text.lower())


def infer_topic(text: str) -> str:
    """Return the single best-matching topic, or 'general' if none match."""
    scored = score_topics(text)
    if not scored:
        return "general"
    best_topic, best_score = scored[0]
    return best_topic if best_score > 0 else "general"


def score_topics(text: str) -> List[Tuple[str, int]]:
    """Return [(topic, score), ...] sorted by descending score (score > 0)."""
    tokens = set(_tokens(text))
    if not tokens:
        return []
    scores: List[Tuple[str, int]] = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in tokens)
        if score > 0:
            scores.append((topic, score))
    scores.sort(key=lambda kv: (-kv[1], kv[0]))
    return scores
