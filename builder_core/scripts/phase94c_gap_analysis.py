"""One-off Phase 94C resolution gap analysis (read-only)."""

from __future__ import annotations

import ast
import json
from collections import Counter, defaultdict
from typing import Any, Dict, List

from builder_core.bug_intelligence import callgraph, cross_file, depgraph, module_map

REQUESTED = (
    "method_calls",
    "inheritance",
    "dynamic_dispatch",
    "decorators",
    "imports",
    "shadowed",
    "symbol_not_found",
)

RECALL_ASSUMPTIONS = {
    "method_calls": 0.45,
    "inheritance": 0.70,
    "dynamic_dispatch": 0.05,
    "decorators": 0.60,
    "imports": 0.15,
    "shadowed": 0.00,
    "symbol_not_found": 0.35,
}


def _func_label(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return type(node).__name__


def analyze(root: str = ".") -> Dict[str, Any]:
    files = depgraph._collect_files(root)
    parsed: List[tuple[str, ast.AST]] = []
    for rel, text in files:
        try:
            parsed.append((rel, ast.parse(text)))
        except SyntaxError:
            continue

    graph = depgraph.build_graph_from_files(root, files)
    stats = graph["statistics"]
    unres = graph["unresolved"]
    project_context = cross_file.build_project_context(list(parsed)) or {}

    raw_calls = Counter(item.get("reason", "?") for item in unres["calls_unresolved"])
    raw_refs = Counter(
        f"{item.get('kind')}:{item.get('name', '')}"
        for item in unres["references_unresolved"]
    )
    raw_imports = Counter(item.get("reason", "?") for item in unres["imports_external"])

    intra_sites: Dict[str, set[int]] = defaultdict(set)
    for item in unres["calls_unresolved"]:
        if item.get("reason") == "intra_file_unresolved":
            intra_sites[item["file"]].add(int(item.get("line", 0)))

    intra_categories = Counter()
    intra_examples: Dict[str, List[str]] = defaultdict(list)

    for rel, tree in parsed:
        if rel not in intra_sites:
            continue
        target_lines = intra_sites[rel]
        callgraph._attach_parents(tree)
        qn = callgraph._compute_qualnames(tree)
        module_level: Dict[str, str] = {}
        for child in ast.iter_child_nodes(tree):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                module_level[child.name] = qn[child]
        for fn_node, caller_qual in qn.items():
            bound = callgraph._bound_names(fn_node)
            for node in callgraph._walk_local(fn_node):
                if not isinstance(node, ast.Call):
                    continue
                line = int(getattr(node, "lineno", 0))
                if line not in target_lines:
                    continue
                if isinstance(node.func, ast.Attribute):
                    cat = "method_calls"
                elif isinstance(node.func, ast.Name):
                    name = node.func.id
                    if name in bound:
                        cat = "shadowed"
                    elif name not in module_level:
                        cat = "symbol_not_found"
                    else:
                        cat = "other_intra_file"
                else:
                    cat = "dynamic_dispatch"
                intra_categories[cat] += 1
                if len(intra_examples[cat]) < 5:
                    intra_examples[cat].append(
                        f"{rel}:{line} caller={caller_qual} func={_func_label(node.func)}"
                    )

    xf_categories = Counter()
    xf_examples: Dict[str, List[str]] = defaultdict(list)
    for rel, data in (project_context.get("per_file") or {}).items():
        for item in data.get("unresolved", []):
            reason = item.get("reason", "?")
            line = int(item.get("line", 0))
            if reason == "dynamic_or_complex":
                cat = "dynamic_dispatch"
            elif reason == "shadowed":
                cat = "shadowed"
            elif reason == "symbol_not_found":
                cat = "symbol_not_found"
            elif reason in ("ambiguous_import", "star_import", "third_party_or_unknown_module"):
                cat = "imports"
            else:
                cat = reason
            xf_categories[cat] += 1
            if len(xf_examples[cat]) < 5:
                xf_examples[cat].append(f"{rel}:{line} reason={reason}")

    ref_categories = Counter()
    ref_examples: Dict[str, List[str]] = defaultdict(list)
    for item in unres["references_unresolved"]:
        kind = item.get("kind")
        if kind == "base_class":
            cat = "inheritance"
        elif kind == "decorator":
            cat = "decorators"
        else:
            cat = "other_reference"
        ref_categories[cat] += 1
        if len(ref_examples[cat]) < 5:
            ref_examples[cat].append(
                f"{item.get('file')}:{item.get('line')} kind={kind} name={item.get('name')}"
            )

    import_categories = Counter()
    for item in unres["imports_external"]:
        import_categories["imports"] += 1

    combined = Counter()
    combined.update(intra_categories)
    combined.update(xf_categories)
    combined.update(ref_categories)
    combined.update(import_categories)

    for key in REQUESTED:
        combined.setdefault(key, 0)

    resolved_calls = int(stats["edge_counts"].get("calls", 0))
    unresolved_calls = int(stats["unresolved_counts"].get("calls_unresolved", 0))
    total_sites = resolved_calls + unresolved_calls

    ranked = sorted(
        ((cat, combined[cat]) for cat in REQUESTED),
        key=lambda kv: (-kv[1], kv[0]),
    )

    recall_rows = []
    cumulative = resolved_calls
    for cat, count in ranked:
        gain = int(round(count * RECALL_ASSUMPTIONS.get(cat, 0.0)))
        cumulative += gain
        recall_rows.append({
            "category": cat,
            "count": count,
            "assumed_resolvable_fraction": RECALL_ASSUMPTIONS.get(cat, 0.0),
            "estimated_new_resolved_calls": gain,
            "estimated_resolved_total": cumulative,
            "estimated_resolved_rate": round(cumulative / total_sites, 4) if total_sites else 0.0,
        })

    return {
        "repository_root": graph.get("repository_root"),
        "resolved_calls": resolved_calls,
        "unresolved_calls": unresolved_calls,
        "total_call_sites": total_sites,
        "baseline_resolved_rate": round(resolved_calls / total_sites, 4) if total_sites else 0.0,
        "references_unresolved": int(stats["unresolved_counts"].get("references_unresolved", 0)),
        "imports_external": int(stats["unresolved_counts"].get("imports_external", 0)),
        "raw_call_reasons": dict(raw_calls.most_common()),
        "raw_reference_kinds": dict(raw_refs.most_common(10)),
        "raw_import_reasons": dict(raw_imports.most_common()),
        "intra_breakdown": dict(intra_categories.most_common()),
        "cross_file_breakdown": dict(xf_categories.most_common()),
        "reference_breakdown": dict(ref_categories.most_common()),
        "combined_taxonomy": {cat: combined[cat] for cat in REQUESTED},
        "combined_taxonomy_pct": {
            cat: round(combined[cat] / sum(combined.values()) * 100, 2)
            if sum(combined.values()) else 0.0
            for cat in REQUESTED
        },
        "ranked_causes": [{"category": c, "count": n, "share_pct": round(n / sum(combined.values()) * 100, 2)} for c, n in ranked],
        "examples": {
            "method_calls": intra_examples.get("method_calls", [])[:5],
            "shadowed": (intra_examples.get("shadowed", []) + xf_examples.get("shadowed", []))[:5],
            "symbol_not_found": (intra_examples.get("symbol_not_found", []) + xf_examples.get("symbol_not_found", []))[:5],
            "dynamic_dispatch": (intra_examples.get("dynamic_dispatch", []) + xf_examples.get("dynamic_dispatch", []))[:5],
            "inheritance": ref_examples.get("inheritance", [])[:5],
            "decorators": ref_examples.get("decorators", [])[:5],
            "imports": xf_examples.get("imports", [])[:5],
        },
        "recall_scenarios": recall_rows,
        "optimistic_total_resolved_if_all_safe_categories": int(
            resolved_calls + sum(combined[cat] * RECALL_ASSUMPTIONS.get(cat, 0.0) for cat in REQUESTED)
        ),
        "optimistic_resolved_rate": round(
            (resolved_calls + sum(combined[cat] * RECALL_ASSUMPTIONS.get(cat, 0.0) for cat in REQUESTED))
            / total_sites,
            4,
        ) if total_sites else 0.0,
    }


if __name__ == "__main__":
    print(json.dumps(analyze("."), indent=2, sort_keys=True))
