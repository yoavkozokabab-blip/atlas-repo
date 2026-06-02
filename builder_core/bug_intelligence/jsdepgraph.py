"""TypeScript/JavaScript dependency graph (Phase 116 — additive, import-only).

Produces depgraph-compatible JSON: module nodes + resolved import edges.
Regex-based import extraction (no TS compiler). Python depgraph unchanged.
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from . import depgraph

GRAPH_SCHEMA_VERSION = depgraph.GRAPH_SCHEMA_VERSION
JS_EXTENSIONS = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")
RESOLVE_TRY = (
    "",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    "/index.ts",
    "/index.tsx",
    "/index.js",
    "/index.jsx",
)

SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", "env", "dist", "build",
    "out", "coverage", ".next", ".turbo", ".cache", "target", "vendor", ".gradle",
    "site-packages", ".tox", "htmlcov", ".idea", ".vscode", ".jarvis_builder",
    ".jarvis", "fixtures", "testdata", "__tests__",
}

TEST_SEGMENTS = frozenset({"test", "tests"})

IMPORT_SPEC_RE = re.compile(
    r"""(?:import|export)\s+(?:type\s+)?(?:[\w*{}\s,$]+\s+from\s+)?['"]([^'"]+)['"]""",
    re.MULTILINE,
)
EXPORT_FROM_RE = re.compile(
    r"""export\s+(?:type\s+)?(?:\*|\{[^}]*\})\s+from\s+['"]([^'"]+)['"]""",
    re.MULTILINE,
)
REQUIRE_RE = re.compile(r"""require\s*\(\s*['"]([^'"]+)['"]\s*\)""", re.MULTILINE)
DYNAMIC_IMPORT_RE = re.compile(
    r"""import\s*\(\s*['"]([^'"]+)['"]\s*\)""",
    re.MULTILINE,
)

MAX_FILE_BYTES = 400_000
# VS Code-scale monorepos exceed the Python depgraph cap; JS/TS uses a higher limit.
JS_MAX_FILES = 12_000


def _language_for_ext(ext: str) -> str:
    if ext in (".ts", ".tsx"):
        return "typescript"
    return "javascript"


def _is_test_path(rel_posix: str, filename: str) -> bool:
    parts = rel_posix.lower().split("/")
    if any(seg in TEST_SEGMENTS for seg in parts):
        return True
    lower = filename.lower()
    return bool(re.search(r"\.(test|spec)\.(tsx?|jsx?|mjs|cjs)$", lower))


def is_production_js_file(rel_posix: str) -> bool:
    parts = rel_posix.replace("\\", "/").split("/")
    if any(seg in SKIP_DIRS for seg in parts):
        return False
    filename = parts[-1] if parts else rel_posix
    return not _is_test_path(rel_posix, filename)


def collect_js_ts_files(root: str) -> List[Tuple[str, str]]:
    root_abs = os.path.abspath(root)
    out: List[Tuple[str, str]] = []
    for dirpath, dirnames, filenames in os.walk(root_abs):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            ext = os.path.splitext(name)[1].lower()
            if ext not in JS_EXTENSIONS:
                continue
            abs_path = os.path.join(dirpath, name)
            rel = os.path.relpath(abs_path, root_abs).replace("\\", "/")
            if is_production_js_file(rel):
                out.append((abs_path, rel))
    out.sort(key=lambda item: item[1])
    return out


def _module_key(rel: str) -> str:
    for ext in JS_EXTENSIONS:
        if rel.endswith(ext):
            return rel[: -len(ext)]
    return rel


def _module_id(rel: str) -> str:
    return depgraph.node_id("module", _module_key(rel))


def _line_count(text: str) -> int:
    return len(text.splitlines()) if text else 0


def _extract_import_specs(text: str) -> List[str]:
    specs: List[str] = []
    for pattern in (IMPORT_SPEC_RE, EXPORT_FROM_RE, REQUIRE_RE, DYNAMIC_IMPORT_RE):
        specs.extend(pattern.findall(text))
    return specs


def _load_tsconfig_paths(root: str) -> Tuple[str, Dict[str, List[str]]]:
    for name in ("tsconfig.json", "jsconfig.json"):
        path = os.path.join(root, name)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        compiler = data.get("compilerOptions") or data
        base = str(compiler.get("baseUrl") or ".").replace("\\", "/").strip("/")
        paths_raw = compiler.get("paths") or {}
        paths: Dict[str, List[str]] = {}
        for key, targets in paths_raw.items():
            if isinstance(targets, list):
                paths[str(key)] = [str(t).replace("\\", "/") for t in targets]
            elif isinstance(targets, str):
                paths[str(key)] = [targets.replace("\\", "/")]
        return base, paths
    return "", {}


def _resolve_alias(
    spec: str,
    *,
    base_url: str,
    paths_map: Dict[str, List[str]],
) -> Optional[str]:
    for pattern, targets in paths_map.items():
        if not targets:
            continue
        if pattern.endswith("/*"):
            prefix = pattern[:-2]
            if spec.startswith(prefix + "/"):
                suffix = spec[len(prefix) + 1 :]
                target = targets[0].replace("/*", "").rstrip("/")
                return f"{target}/{suffix}" if target else suffix
        elif spec == pattern or spec.startswith(pattern + "/"):
            return targets[0].replace("/*", "")
    if base_url and not spec.startswith((".", "/")):
        return f"{base_url}/{spec}" if base_url else spec
    return None


def _build_lookup(files: List[Tuple[str, str]]) -> Dict[str, str]:
    """Map module key -> canonical file rel path."""
    lookup: Dict[str, str] = {}
    for rel in files:
        key = _module_key(rel)
        lookup[key] = rel
        lookup[rel] = rel
    return lookup


def _resolve_spec(
    spec: str,
    importer_rel: str,
    lookup: Dict[str, str],
    *,
    base_url: str,
    paths_map: Dict[str, List[str]],
) -> Optional[str]:
    if spec.startswith("."):
        importer_dir = os.path.dirname(importer_rel.replace("\\", "/"))
        joined = os.path.normpath(os.path.join(importer_dir, spec)).replace("\\", "/")
        for suffix in RESOLVE_TRY:
            cand = joined + suffix
            key = _module_key(cand) if suffix else joined
            if key in lookup:
                return lookup[key]
            if cand in lookup:
                return lookup[cand]
        return None

    alias = _resolve_alias(spec, base_url=base_url, paths_map=paths_map)
    if alias:
        for suffix in RESOLVE_TRY:
            cand = alias + suffix
            key = _module_key(cand) if suffix else alias
            if key in lookup:
                return lookup[key]
    return None


def _is_external(spec: str) -> bool:
    return not spec.startswith(".") and not spec.startswith("/")


def build_graph_from_files(
    repository_root: str,
    files: List[Tuple[str, str]],
    *,
    deadline: Optional[float] = None,
    on_progress: Optional[Callable[[str, int, int], None]] = None,
) -> Dict[str, Any]:
    root = os.path.abspath(repository_root).replace("\\", "/")
    rels = [rel for rel, _ in files]
    lookup = _build_lookup(rels)
    base_url, paths_map = _load_tsconfig_paths(repository_root)

    nodes: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []
    unresolved_external: List[Dict[str, Any]] = []
    external_packages: Set[str] = set()

    repo_nid = depgraph.node_id("repository", root)
    nodes[repo_nid] = {
        "id": repo_nid,
        "type": "repository",
        "root": root,
        "javascript_files": len(files),
    }

    total = len(files)
    for idx, (rel, text) in enumerate(files):
        if deadline and time.monotonic() >= deadline:
            break
        if on_progress and idx % 250 == 0:
            on_progress("js_parse", idx, total)

        ext = os.path.splitext(rel)[1].lower()
        mod_nid = _module_id(rel)
        nodes[mod_nid] = {
            "id": mod_nid,
            "type": "module",
            "path": rel,
            "dotted": _module_key(rel).replace("/", "."),
            "language": _language_for_ext(ext),
            "extension": ext,
            "parse_ok": True,
            "line_count": _line_count(text),
            "is_package": os.path.basename(rel).startswith("index."),
        }
        edges.append({
            "type": "contains",
            "from": repo_nid,
            "to": mod_nid,
            "line": 1,
            "resolved": True,
        })

        seen_targets: Set[str] = set()
        for spec in _extract_import_specs(text):
            spec = spec.strip()
            if not spec or spec.startswith("node:"):
                continue

            target_rel = _resolve_spec(
                spec, rel, lookup, base_url=base_url, paths_map=paths_map,
            )
            if not target_rel:
                if _is_external(spec):
                    pkg = spec.split("/")[0]
                    if spec.startswith("@"):
                        parts = spec.split("/")
                        pkg = "/".join(parts[:2]) if len(parts) >= 2 else spec
                    external_packages.add(pkg)
                    unresolved_external.append({
                        "from_module": rel,
                        "target": spec,
                        "reason": "third_party_or_unknown_module",
                    })
                else:
                    unresolved_external.append({
                        "from_module": rel,
                        "target": spec,
                        "reason": "unresolved_relative_or_alias",
                    })
                continue

            tgt_nid = _module_id(target_rel)
            pair = (mod_nid, tgt_nid)
            if pair in seen_targets:
                continue
            seen_targets.add(pair)
            edges.append({
                "type": "imports",
                "from": mod_nid,
                "to": tgt_nid,
                "line": 1,
                "resolved": True,
                "target_module": spec,
            })

    edge_list = depgraph._dedupe_edges(edges)
    node_list = [nodes[k] for k in sorted(nodes)]
    stats = depgraph.compute_statistics(
        node_list,
        edge_list,
        {
            "imports_external": unresolved_external,
            "calls_unresolved": [],
            "references_unresolved": [],
        },
    )
    lang_counts: Dict[str, int] = {}
    for node in node_list:
        if node.get("type") == "module":
            lang = str(node.get("language", "javascript"))
            lang_counts[lang] = lang_counts.get(lang, 0) + 1

    out: Dict[str, Any] = {
        "schema_version": GRAPH_SCHEMA_VERSION,
        "repository_root": root,
        "nodes": node_list,
        "edges": edge_list,
        "unresolved": {
            "imports_external": unresolved_external,
            "calls_unresolved": [],
            "references_unresolved": [],
        },
        "statistics": stats,
        "parse_errors": [],
        "graph_detail": depgraph.DETAIL_IMPORTS,
        "graph_scope": depgraph.PRODUCTION_SCOPE,
        "js_graph": True,
        "language_counts": lang_counts,
        "external_package_count": len(external_packages),
        "unresolved_import_count": len(unresolved_external),
        "scope_diagnostics": {
            "requested_scope": "production",
            "files_kept": len(files),
            "graph_languages": sorted(lang_counts.keys()),
        },
    }
    if deadline and time.monotonic() >= deadline:
        out["jarvis_timed_out"] = True
        out["jarvis_partial"] = True
        out["degraded"] = True
        out["degraded_reason"] = "time_budget_exceeded"
    return out


def build_graph(
    repository_root: str,
    *,
    time_budget_sec: Optional[float] = None,
    on_progress: Optional[Callable[[str, int, int], None]] = None,
) -> Dict[str, Any]:
    root_abs = os.path.abspath(repository_root)
    candidates = collect_js_ts_files(root_abs)
    capped = False
    if len(candidates) > JS_MAX_FILES:
        candidates = candidates[:JS_MAX_FILES]
        capped = True

    deadline = (
        time.monotonic() + float(time_budget_sec)
        if time_budget_sec is not None and time_budget_sec > 0
        else None
    )
    file_pairs: List[Tuple[str, str]] = []
    for abs_path, rel in candidates:
        if deadline and time.monotonic() >= deadline:
            break
        try:
            if os.path.getsize(abs_path) > MAX_FILE_BYTES:
                continue
            with open(abs_path, encoding="utf-8", errors="ignore") as handle:
                file_pairs.append((rel, handle.read()))
        except OSError:
            continue

    graph = build_graph_from_files(
        repository_root,
        file_pairs,
        deadline=deadline,
        on_progress=on_progress,
    )
    if capped:
        graph["degraded"] = True
        graph["degraded_reason"] = "js_file_cap_applied"
        graph["degraded_count"] = len(candidates)
        graph.setdefault("scope_diagnostics", {})["files_capped"] = JS_MAX_FILES
    return graph


def count_js_ts_candidates(root: str) -> int:
    return len(collect_js_ts_files(root))
