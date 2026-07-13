"""Phase 134 — Classify unresolved import edges for graph health and risk scoring."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

CLASSIFICATIONS = (
    "external_dependency",
    "optional_dependency",
    "dynamic_import",
    "internal_missing",
    "relative_resolution_issue",
    "namespace_package",
    "test_or_dev_only",
)

# Stdlib / common third-party prefixes (not exhaustive — conservative external bucket).
_STDLIB_ROOTS = frozenset(
    {
        "abc", "argparse", "ast", "asyncio", "collections", "contextlib", "copy",
        "dataclasses", "datetime", "enum", "functools", "importlib", "inspect",
        "io", "itertools", "json", "logging", "math", "os", "pathlib", "re",
        "sys", "threading", "time", "typing", "unittest", "uuid", "warnings",
    }
)
_OPTIONAL_MARKERS = ("TYPE_CHECKING", "typing_extensions", "if TYPE_CHECKING")
_DYNAMIC_PATTERNS = re.compile(
    r"\b(importlib\.import_module|__import__|import_module\s*\()",
    re.MULTILINE,
)
_TEST_PATH_PARTS = frozenset(
    {"test", "tests", "__tests__", "testing", "pytest", "conftest", "benchmark", "scripts"}
)


def _norm(path: str) -> str:
    return (path or "").replace("\\", "/").strip()


def _module_roots(internal_modules: Set[str]) -> Set[str]:
    roots: Set[str] = set()
    for mod in internal_modules:
        if mod:
            roots.add(mod.split(".")[0])
    return roots


def _is_stdlib_or_external(target: str, internal_modules: Set[str]) -> bool:
    root = (target or "").split(".")[0]
    if root in _STDLIB_ROOTS:
        return True
    if target in internal_modules:
        return False
    if any(target.startswith(m + ".") for m in internal_modules):
        return False
    return True


def classify_unresolved_entry(
    entry: Dict[str, Any],
    *,
    internal_modules: Set[str],
    module_to_path: Dict[str, str],
    from_module_path: str = "",
    source_snippet: str = "",
) -> str:
    """Assign one classification label to a single unresolved import record."""
    target = (entry.get("target") or entry.get("target_module") or "").strip()
    reason = (entry.get("reason") or "").lower()
    from_path = _norm(entry.get("from_module") or from_module_path)
    parts = from_path.lower().split("/")

    if reason == "asset_import":
        return "external_dependency"

    if target.startswith("."):
        return "relative_resolution_issue"

    if any(p in _TEST_PATH_PARTS for p in parts):
        return "test_or_dev_only"

    if reason == "star_import":
        return "dynamic_import"

    if _DYNAMIC_PATTERNS.search(source_snippet or ""):
        return "dynamic_import"

    if reason in ("third_party_or_unknown_module",) and target:
        root = target.split(".")[0] if target else ""
        if root in _module_roots(internal_modules):
            if target.startswith("."):
                return "relative_resolution_issue"
            return "internal_missing"
        if _is_stdlib_or_external(target, internal_modules):
            if any(m in (source_snippet or "") for m in _OPTIONAL_MARKERS):
                return "optional_dependency"
            return "external_dependency"
        if target.startswith("."):
            return "relative_resolution_issue"
        return "namespace_package"

    return "external_dependency"


def classify_graph_unresolved(
    graph: Dict[str, Any],
    index: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Classify all unresolved import records on a depgraph payload."""
    internal_modules: Set[str] = set()
    module_to_path: Dict[str, str] = {}
    path_to_source: Dict[str, str] = {}

    for node in graph.get("nodes", []):
        if node.get("type") != "module":
            continue
        dotted = node.get("dotted") or ""
        path = _norm(node.get("path") or "")
        if dotted:
            internal_modules.add(dotted)
        if path and dotted:
            module_to_path[dotted] = path

    project_root = (index or {}).get("project_root") or graph.get("repository_root") or ""
    if index and project_root:
        import os

        for node in graph.get("nodes", []):
            if node.get("type") != "module":
                continue
            path = _norm(node.get("path") or "")
            if not path or path in path_to_source:
                continue
            full = os.path.join(project_root, path)
            try:
                with open(full, "r", encoding="utf-8-sig", errors="ignore") as fh:
                    path_to_source[path] = fh.read(4000)
            except OSError:
                path_to_source[path] = ""

    raw = list((graph.get("unresolved") or {}).get("imports_external") or [])
    classified: List[Dict[str, Any]] = []
    breakdown: Dict[str, int] = {k: 0 for k in CLASSIFICATIONS}

    for entry in raw:
        from_path = _norm(entry.get("from_module") or "")
        snippet = path_to_source.get(from_path, "")
        label = classify_unresolved_entry(
            entry,
            internal_modules=internal_modules,
            module_to_path=module_to_path,
            from_module_path=from_path,
            source_snippet=snippet,
        )
        breakdown[label] = breakdown.get(label, 0) + 1
        classified.append({**entry, "classification": label})

    internal_count = (
        breakdown.get("internal_missing", 0)
        + breakdown.get("relative_resolution_issue", 0)
    )
    health_penalty = internal_count + breakdown.get("dynamic_import", 0) * 0.25

    return {
        "total": len(raw),
        "breakdown": breakdown,
        "internal_unresolved_count": internal_count,
        "external_dependency_count": breakdown.get("external_dependency", 0),
        "dynamic_import_count": breakdown.get("dynamic_import", 0),
        "entries": classified[:500],
        "health_penalty": round(health_penalty, 2),
    }


def graph_health_from_unresolved(
    scan: Dict[str, Any],
    unresolved_breakdown: Dict[str, Any],
) -> Dict[str, Any]:
    """Refine graph health using classified unresolved imports (Phase 134)."""
    resolved = int(scan.get("resolved_imports", scan.get("dependency_edges", 0)) or 0)
    unresolved_total = int(unresolved_breakdown.get("total") or scan.get("unresolved_imports", 0) or 0)
    internal = int(unresolved_breakdown.get("internal_unresolved_count", 0) or 0)
    external = int(unresolved_breakdown.get("external_dependency_count", 0) or 0)
    total = resolved + unresolved_total
    ratio = round(unresolved_total / total, 4) if total else 0.0
    internal_ratio = round(internal / total, 4) if total else 0.0

    degraded = bool(scan.get("degraded"))
    if internal >= 50 or internal_ratio >= 0.02:
        label = "degraded"
        notice = (
            f"Internal unresolved imports detected ({internal} missing/relative). "
            "Architecture map may have gaps — prioritize fixing internal resolution."
        )
    elif internal >= 10:
        label = "watch"
        notice = f"{internal} internal unresolved imports — review relative imports and missing modules."
    elif unresolved_total >= 100 and ratio >= 0.35 and internal == 0:
        label = "partial"
        notice = (
            f"{external} external/stdlib imports ({ratio:.0%} of import statements). "
            "Normal for dependency-heavy apps; internal graph is still mapped."
        )
    elif scan.get("import_cycle_count", 0) > 4:
        label = "watch"
        notice = "Import cycles detected — review coupling hotspots."
    else:
        label = "healthy"
        notice = ""

    return {
        "label": label,
        "degraded": degraded or label == "degraded",
        "resolved_imports": resolved,
        "unresolved_imports": unresolved_total,
        "external_package_imports": external,
        "internal_unresolved_imports": internal,
        "unresolved_ratio": ratio,
        "internal_unresolved_ratio": internal_ratio,
        "unresolved_breakdown": unresolved_breakdown.get("breakdown", {}),
        "notice": notice,
        "reason": notice or "Graph health is based primarily on internal unresolved imports, not external packages.",
    }
