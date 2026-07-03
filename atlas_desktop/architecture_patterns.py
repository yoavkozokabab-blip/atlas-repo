"""Phase 134 — Architectural pattern detection (AST symbols + paths).

Deterministic heuristics for repository-map and impact analysis. No LLM.
"""

from __future__ import annotations

import ast
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

PATTERN_NAMES = (
    "god_module",
    "boundary_module",
    "adapter",
    "registry",
    "plugin_loader",
    "event_bus",
    "state_machine",
    "service_registry",
    "config_entry",
    "websocket_api",
    "recorder_database",
    "auth_boundary",
    "integration_component",
    "helper_module",
    "dynamic_import_zone",
)

_SYMBOL_HINTS: Dict[str, Tuple[str, ...]] = {
    "event_bus": ("EventBus", "async_fire", "async_listen", "async_listen_once"),
    "state_machine": ("StateMachine", "async_set", "async_available"),
    "service_registry": ("ServiceRegistry", "async_register", "async_call"),
    "config_entry": ("ConfigEntry", "ConfigEntries", "async_setup_entry", "async_unload_entry"),
    "websocket_api": ("WebSocketAPI", "websocket_api", "async_handle", "current_connection"),
    "recorder_database": ("Recorder", "async_setup", "get_instance", "purge"),
    "auth_boundary": ("AuthStore", "AuthProvider", "auth_provider", "async_validate_access_token"),
    "registry": ("Registry", "async_register", "async_get"),
    "plugin_loader": ("async_setup_component", "async_setup_platform", "IntegrationLoader"),
}

_PATH_HINTS: Dict[str, Tuple[str, ...]] = {
    "event_bus": ("/core.py", "helpers/event.py", "eventbus"),
    "state_machine": ("/core.py", "statemachine"),
    "websocket_api": ("components/websocket_api", "/websocket_api/"),
    "recorder_database": ("components/recorder", "/recorder/"),
    "auth_boundary": ("/auth/", "auth_store", "auth_provider"),
    "config_entry": ("config_entries.py", "config_entry"),
    "service_registry": ("/services.py", "service.py", "serviceregistry"),
    "plugin_loader": ("/loader.py", "bootstrap.py", "setup.py"),
    "integration_component": ("/components/", "/integrations/", "/plugins/"),
    "helper_module": ("/helpers/", "/util/"),
    "adapter": ("adapter", "client.py", "_client"),
    "registry": ("registry",),
    "dynamic_import_zone": ("importlib", "TYPE_CHECKING", "__import__"),
    "boundary_module": ("/http/", "websocket_api", "/api/"),
}


def _norm(path: str) -> str:
    return (path or "").replace("\\", "/").lower()


def _basename(path: str) -> str:
    return os.path.basename(_norm(path))


def _extract_symbols(source: str) -> Set[str]:
    names: Set[str] = set()
    if not source or len(source) > 200_000:
        return names
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return names
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.FunctionDef):
            names.add(node.name)
        elif isinstance(node, ast.AsyncFunctionDef):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
    return names


def _has_dynamic_import(source: str) -> bool:
    if not source:
        return False
    return bool(
        re.search(r"\b(importlib\.import_module|__import__)\s*\(", source)
        or "TYPE_CHECKING" in source
    )


def detect_patterns(
    path: str,
    *,
    source: Optional[str] = None,
    fan_in: int = 0,
    fan_out: int = 0,
    line_count: int = 0,
    subsystems_touched: int = 0,
    in_cycle: bool = False,
) -> List[str]:
    """Return architectural pattern tags for a module."""
    p = _norm(path)
    base = _basename(p)
    symbols = _extract_symbols(source or "")
    blob = " ".join(symbols)
    out: Set[str] = set()

    for name, hints in _PATH_HINTS.items():
        if any(h in p for h in hints):
            out.add(name)

    for name, hints in _SYMBOL_HINTS.items():
        if any(h in blob for h in hints):
            out.add(name)

    if re.search(r"/(components|integrations|plugins)/[^/]+/__init__\.py$", p):
        out.add("integration_component")

    if "/helpers/" in p or p.startswith("helpers/"):
        out.add("helper_module")

    if "adapter" in base or "client" in base:
        out.add("adapter")

    if fan_in >= 12 and fan_out >= 8 and line_count >= 400:
        out.add("god_module")
    elif fan_in >= 8 and line_count >= 250 and fan_out >= 4:
        out.add("god_module")

    if subsystems_touched >= 4 or (fan_in >= 6 and subsystems_touched >= 2):
        out.add("boundary_module")

    if _has_dynamic_import(source or ""):
        out.add("dynamic_import_zone")

    if in_cycle:
        out.discard("god_module")  # cycles are coupling, not god-module by size alone

    return sorted(out)


def architecture_summary_for_repo(
    module_paths: List[str],
    *,
    patterns_by_path: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, Any]:
    """High-level architecture summary for Repository Map API."""
    paths = [_norm(p) for p in module_paths if p]
    areas: Dict[str, int] = {
        "components": 0,
        "helpers": 0,
        "core": 0,
        "auth": 0,
        "config_entries": 0,
    }
    pattern_index: Dict[str, List[str]] = {k: [] for k in PATTERN_NAMES}

    for path in paths:
        if "components/" in path:
            areas["components"] += 1
        if "/helpers/" in path or path.startswith("helpers/"):
            areas["helpers"] += 1
        if path.endswith("/core.py") or "/core.py" in path:
            areas["core"] += 1
        if "/auth/" in path:
            areas["auth"] += 1
        if "config_entries" in path:
            areas["config_entries"] += 1
        for pat in (patterns_by_path or {}).get(path, []):
            if pat in pattern_index and len(pattern_index[pat]) < 8:
                pattern_index[pat].append(path)

    return {
        "areas": areas,
        "patterns": {k: v for k, v in pattern_index.items() if v},
        "has_components": areas["components"] > 0,
        "has_helpers": areas["helpers"] > 0,
        "has_core": areas["core"] > 0,
        "has_auth": areas["auth"] > 0,
        "has_config_entries": areas["config_entries"] > 0,
    }


def hub_vs_risk_classification(path: str, patterns: List[str], *, fan_in: int) -> Dict[str, str]:
    """Explain why a module is a hub vs an architectural risk (e.g. const.py)."""
    p = _norm(path)
    base = _basename(p)
    if base in ("const.py", "constants.py", "consts.py"):
            return {
                "hub_role": "config_constant_hub",
                "risk_role": "low_logic_risk",
                "note": (
                    f"High fan-in ({fan_in}) from shared constants/config — "
                    "blast radius is mostly import-time values, not runtime business logic."
                ),
            }
    if "god_module" in patterns:
        return {"hub_role": "dependency_hub", "risk_role": "high_change_risk", "note": "God module: many dependents and outbound deps."}
    if "event_bus" in patterns or "runtime_boundary" in patterns:
        return {"hub_role": "runtime_hub", "risk_role": "runtime_critical", "note": "Runtime boundary — changes affect live event/state flows."}
    return {"hub_role": "import_hub", "risk_role": "coupling_risk", "note": ""}
