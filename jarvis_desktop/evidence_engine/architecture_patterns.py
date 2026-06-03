"""Phase 133 — Generalizable architecture pattern detection (async platforms, HA-style)."""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

# Pattern id -> (symbol names, path keywords, insertion path keywords)
ARCHITECTURE_PATTERNS: Dict[str, Dict[str, Tuple[str, ...]]] = {
    "event_bus": {
        "symbols": ("EventBus", "async_fire", "async_listen"),
        "paths": ("core.py", "helpers/event", "eventbus"),
        "insertion": ("core", "event"),
    },
    "websocket_api": {
        "symbols": ("websocket_api", "WebSocket", "websocket"),
        "paths": ("websocket_api", "components/websocket", "websocket"),
        "insertion": ("websocket", "http", "api"),
    },
    "config_entry": {
        "symbols": ("ConfigEntry", "async_setup_entry", "async_unload_entry"),
        "paths": ("config_entries", "config_entry"),
        "insertion": ("config", "setup", "loader"),
    },
    "auth": {
        "symbols": ("AuthStore", "auth_provider", "AuthProvider"),
        "paths": ("/auth/", "auth_store", "permissions"),
        "insertion": ("auth",),
    },
    "dispatcher": {
        "symbols": ("dispatcher_send", "dispatcher_connect"),
        "paths": ("helpers/dispatcher", "dispatcher"),
        "insertion": ("dispatcher", "helpers"),
    },
    "service_registry": {
        "symbols": ("ServiceRegistry", "async_register"),
        "paths": ("service", "services.yaml"),
        "insertion": ("service", "core"),
    },
    "state_machine": {
        "symbols": ("StateMachine",),
        "paths": ("core.py", "state_machine"),
        "insertion": ("core",),
    },
    "recorder": {
        "symbols": ("Recorder",),
        "paths": ("components/recorder", "/recorder/"),
        "insertion": ("recorder", "db"),
    },
    "automation": {
        "symbols": ("Automation",),
        "paths": ("components/automation", "/automation/"),
        "insertion": ("automation", "trigger"),
    },
}

RUNTIME_SYMPTOM_MARKERS: Tuple[str, ...] = (
    "duplicate",
    "websocket",
    "disconnect",
    "slow",
    "memory",
    "automation",
    "trigger",
    "auth",
    "session",
    "cache",
    "database",
    "recorder",
    "integration load",
    "event",
    "timing",
)

CONFIG_NOISE_FRAGMENTS: Tuple[str, ...] = (
    ".prettierrc",
    "prettier.config",
    "package.json",
    "pyproject.toml",
    "poetry.lock",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock",
    ".eslintrc",
    "eslint.config",
    "ruff.toml",
    ".flake8",
    "mypy.ini",
    "tsconfig.json",
    "babel.config",
    "webpack.config",
    "vite.config",
    "rollup.config",
    "/docs/",
    "/static/",
    ".md",
    ".svg",
    ".png",
    ".css",
    ".scss",
)


def is_runtime_symptom(symptom: str) -> bool:
    low = (symptom or "").lower()
    return any(m in low for m in RUNTIME_SYMPTOM_MARKERS)


def config_noise_penalty(path: str, symptom: str = "") -> float:
    """Heavy negative score for config/tooling paths during runtime investigations."""
    if symptom and not is_runtime_symptom(symptom):
        return 0.0
    pl = (path or "").replace("\\", "/").lower()
    base = pl.rsplit("/", 1)[-1]
    for frag in CONFIG_NOISE_FRAGMENTS:
        if frag in pl or frag in base:
            return -80.0
    return 0.0


def paths_for_pattern(pattern_id: str) -> Tuple[str, ...]:
    spec = ARCHITECTURE_PATTERNS.get(pattern_id) or {}
    return tuple(spec.get("paths") or ())


def match_patterns_in_path(path: str, pattern_ids: List[str]) -> int:
    pl = (path or "").replace("\\", "/").lower()
    hits = 0
    for pid in pattern_ids:
        for kw in paths_for_pattern(pid):
            if kw.lower() in pl:
                hits += 1
                break
    return hits


def symbol_hits_in_blob(blob: str, pattern_id: str) -> int:
    spec = ARCHITECTURE_PATTERNS.get(pattern_id) or {}
    return sum(1 for s in spec.get("symbols", ()) if s in blob)


def resolve_investigation_patterns(symptom: str) -> List[str]:
    """Map symptom text to architecture pattern ids for scoring boosts."""
    low = (symptom or "").lower()
    out: List[str] = []
    if any(k in low for k in ("duplicate", "event", "fire", "listen", "bus")):
        out.append("event_bus")
    if "websocket" in low or "disconnect" in low:
        out.append("websocket_api")
    if any(k in low for k in ("auth", "session", "login", "permission")):
        out.append("auth")
    if "automation" in low or "trigger" in low:
        out.append("automation")
    if any(k in low for k in ("database", "recorder", "storage", "sql")):
        out.append("recorder")
    if "config entry" in low or "integration" in low:
        out.append("config_entry")
    return list(dict.fromkeys(out))


BUILD_LOCALIZATION_PATTERNS: Dict[str, List[str]] = {
    "distributed_tracing": [
        "logging",
        "log",
        "middleware",
        "http",
        "websocket",
        "api",
        "request",
        "event",
        "service",
        "handler",
    ],
    "rate_limiting": [
        "auth",
        "websocket",
        "http",
        "api",
        "rate",
        "limit",
        "throttle",
        "client",
        "handler",
    ],
    "structured_logging": [
        "logging",
        "log",
        "middleware",
        "http",
        "websocket",
        "request",
    ],
}


def build_plan_path_boost(path: str, concept_id: str) -> float:
    """Extra score for build-plan file ranking by concept."""
    pl = (path or "").replace("\\", "/").lower()
    keywords = BUILD_LOCALIZATION_PATTERNS.get(concept_id) or []
    if not keywords:
        return 0.0
    hits = sum(1 for k in keywords if k in pl)
    penalty = config_noise_penalty(path)
    return hits * 12.0 + penalty
