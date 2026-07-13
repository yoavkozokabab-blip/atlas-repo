"""Produce a complete, deterministic unresolved-import audit for an Atlas graph."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from builder_core import repository_understanding as ru
from builder_core.unresolved_imports import classify_unresolved_entry


def _language(path: str) -> str:
    ext = os.path.splitext(path.lower())[1]
    if ext == ".py":
        return "Python"
    if ext in {".ts", ".tsx"}:
        return "TypeScript"
    if ext in {".js", ".jsx", ".mjs", ".cjs"}:
        return "JavaScript"
    return ext.lstrip(".").upper() or "Unknown"


def _resolution_pattern(entry: dict, classification: str, generated: bool) -> str:
    target = str(entry.get("target") or entry.get("target_module") or "")
    if generated:
        return "generated_or_staged_copy"
    if classification == "relative_resolution_issue":
        return "relative_import_boundary"
    if entry.get("reason") == "star_import":
        return "star_import"
    if classification in {"internal_missing", "namespace_package"}:
        return "first_party_module_lookup"
    if classification == "test_or_dev_only":
        return "test_or_dev_import"
    if classification == "optional_dependency":
        return "optional_guarded_import"
    if target:
        return "external_or_stdlib_import"
    return "unclassified_import"


def analyze(graph_path: Path, index_path: Path | None = None) -> dict:
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path else {}
    root = Path(index.get("project_root") or graph.get("repository_root") or ".")
    nodes = [node for node in graph.get("nodes", []) if node.get("type") == "module"]
    internal_modules = {str(node.get("dotted")) for node in nodes if node.get("dotted")}
    module_to_path = {
        str(node.get("dotted")): str(node.get("path"))
        for node in nodes
        if node.get("dotted") and node.get("path")
    }
    source_cache: dict[str, str] = {}
    breakdown = Counter()
    languages = Counter()
    patterns = Counter()
    causes = Counter()
    dispositions = Counter()
    internal_rows = []
    raw = list((graph.get("unresolved") or {}).get("imports_external") or [])
    for entry in raw:
        from_path = str(entry.get("from_module") or "").replace("\\", "/")
        if from_path not in source_cache:
            try:
                source_cache[from_path] = (root / from_path).read_text(
                    encoding="utf-8-sig", errors="ignore"
                )[:4000]
            except OSError:
                source_cache[from_path] = ""
        classification = classify_unresolved_entry(
            entry,
            internal_modules=internal_modules,
            module_to_path=module_to_path,
            from_module_path=from_path,
            source_snippet=source_cache[from_path],
        )
        breakdown[classification] += 1
        if classification not in {"internal_missing", "relative_resolution_issue"}:
            continue
        generated = ru.is_generated_runtime_path(from_path)
        language = _language(from_path)
        pattern = _resolution_pattern(entry, classification, generated)
        if generated:
            cause = "generated runtime/staged payload admitted as production"
            disposition = "genuine resolver scope defect (fixed)"
        elif classification == "relative_resolution_issue":
            cause = "relative import crosses an unresolved package boundary"
            disposition = "review needed"
        else:
            cause = "first-party-looking target has no deterministic module match"
            disposition = "review needed; no edge invented"
        languages[language] += 1
        patterns[pattern] += 1
        causes[cause] += 1
        dispositions[disposition] += 1
        internal_rows.append(
            {
                **entry,
                "language": language,
                "classification": classification,
                "resolution_pattern": pattern,
                "root_cause": cause,
                "disposition": disposition,
            }
        )
    stats = graph.get("statistics") or {}
    node_counts = stats.get("node_counts") or {}
    edge_counts = stats.get("edge_counts") or {}
    return {
        "graph_path": str(graph_path),
        "repository_root": str(root),
        "files": len(nodes),
        "modules": int(node_counts.get("module") or len(nodes)),
        "import_edges": int(edge_counts.get("imports") or 0),
        "total_unresolved_imports": len(raw),
        "internal_unresolved_imports": len(internal_rows),
        "classification_breakdown": dict(sorted(breakdown.items())),
        "internal_language_breakdown": dict(sorted(languages.items())),
        "internal_resolution_pattern_breakdown": dict(sorted(patterns.items())),
        "internal_root_cause_breakdown": dict(sorted(causes.items())),
        "internal_disposition_breakdown": dict(sorted(dispositions.items())),
        "internal_entries": internal_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("graph", type=Path)
    parser.add_argument("--index", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.graph, args.index)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "internal_entries"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
