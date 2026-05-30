"""Unified fact model for the Builder Intelligence Engine (Phase 90).

Merges the data-flow facts (``dataflow.py``: loops, container mutations,
unguarded-consumption) and the value-flow facts (``valueflow.py``: CFG,
reaching definitions, branches, returns, nullability, intervals, taint) into a
single per-function fact record, plus optional test expectations.

Detectors read these facts; they do not each re-walk the AST. The model is
intentionally a coherent superset, not a perfect one.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import dataflow, valueflow


def extract_module_facts(
    text: str,
    path: str = "<source>",
    *,
    test_documents: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """Return {'module', 'parse_error', 'functions': [unified per-fn facts]}."""
    vf = valueflow.analyze_source(text, path)
    if vf.get("parse_error"):
        return {"module": path, "parse_error": vf["parse_error"], "functions": []}
    df = dataflow.analyze_source(text, path)

    df_by_key = {(f.get("name"), f.get("line")): f for f in df.get("functions", [])}
    df_by_name: Dict[str, Dict[str, Any]] = {}
    for f in df.get("functions", []):
        df_by_name.setdefault(f.get("name"), f)

    test_expectations = _test_expectations(path, test_documents or [])

    functions: List[Dict[str, Any]] = []
    for vfn in vf.get("functions", []):
        key = (vfn.get("name"), vfn.get("line"))
        dfn = df_by_key.get(key) or df_by_name.get(vfn.get("name"), {})
        functions.append({
            "name": vfn.get("name"),
            "line": vfn.get("line"),
            "params": vfn.get("params", []),
            # control / data flow
            "cfg_blocks": vfn.get("cfg_blocks", []),
            "definitions": vfn.get("definitions", []),
            "uses": vfn.get("uses", []),
            "reaching_definitions": vfn.get("reaching_definitions", {}),
            "branches": vfn.get("branch_conditions", []),
            "returns": vfn.get("returns", []),
            "loops": dfn.get("loops", []),
            "calls": dfn.get("calls", []),
            "container_mutations": _container_mutations(dfn, vfn),
            "container_state": vfn.get("container_state", {}),
            # value lattices
            "nullability": vfn.get("nullability", {}),
            "intervals": vfn.get("intervals", {}),
            # taint / security
            "taint_sources": vfn.get("source_observations", []),
            "taint_sinks": vfn.get("sink_observations", []),
            "sanitizers": _sanitizers(vfn),
            "security_sensitive_calls": [
                s for s in vfn.get("sink_observations", [])
            ],
            # value-level findings already derived by valueflow (null deref)
            "value_findings": vfn.get("value_findings", []),
        })

    return {
        "module": path,
        "parse_error": "",
        "functions": functions,
        "test_expectations": test_expectations,
    }


def _container_mutations(dfn: Dict[str, Any], vfn: Dict[str, Any]) -> List[Dict[str, Any]]:
    muts: List[Dict[str, Any]] = []
    for c in dfn.get("containers", []) if dfn else []:
        for m in c.get("mutations", []):
            muts.append({"container": c.get("name"), **m})
    return muts


def _sanitizers(vfn: Dict[str, Any]) -> List[str]:
    # taint summary entries marked sanitized are the recognized sanitizer outputs
    summary = vfn.get("taint", {}).get("summary", {})
    return sorted([name for name, state in summary.items() if state == "sanitized"])


def _test_expectations(path: str, test_documents: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Best-effort: reuse the semantic layer's extractor when available."""
    if not test_documents:
        return []
    try:
        from .. import semantic_reasoning
        return semantic_reasoning.extract_test_expectations(path, test_documents)
    except Exception:
        return []
