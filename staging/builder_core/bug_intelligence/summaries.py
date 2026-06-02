"""Bounded function summaries + monotone worklist propagation (Phase 93A).

Each function gets a small, fixed-size summary:
- ``return_nullability`` in {definite_value, maybe_none, unknown}
- ``may_raise``          in {no_raise, may_raise, unknown}
- ``taint_signature``    {params_to_return: [...], reaches_sink: bool}

Each lattice is a short chain and the join only moves a value UP it, so
propagation is monotone and converges in bounded iterations. Ambiguity (an
unresolved callee, an unprovable cycle) widens UP the chain: nullability widens
to UNKNOWN; an unprovable raise widens no_raise -> UNKNOWN (a *proven* raise is
already the top of the may_raise chain and is never erased).

This is infrastructure: the summaries are attached to the fact model but no
detector consumes them in Phase 93A.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

# Lattices (index = height; join = the higher of two). Each is a 3-element chain
# so the max-join is monotone and converges in bounded iterations.
#  - nullability: TOP = unknown. An unresolved return-source widens to unknown
#    (we cannot prove the value is non-None).
#  - may_raise:   TOP = may_raise. A *proven* raise dominates; ambiguity only
#    widens the unprovable no_raise up to unknown, it cannot erase a proven raise.
_NULL = ["definite_value", "maybe_none", "unknown"]
_RAISE = ["no_raise", "unknown", "may_raise"]
_NULL_RANK = {v: i for i, v in enumerate(_NULL)}
_RAISE_RANK = {v: i for i, v in enumerate(_RAISE)}

_MAX_ITERS = 10000  # safety cap; monotone convergence is far faster


def _join_null(a: str, b: str) -> str:
    return _NULL[max(_NULL_RANK.get(a, 2), _NULL_RANK.get(b, 2))]


def _join_raise(a: str, b: str) -> str:
    return _RAISE[max(_RAISE_RANK.get(a, 2), _RAISE_RANK.get(b, 2))]


def _base_nullability(fn_facts: Dict[str, Any]) -> str:
    rs = fn_facts.get("return_summary", {}) or {}
    has_value = bool(rs.get("has_value_return"))
    can_none = bool(rs.get("has_none_return")) or bool(rs.get("can_fall_through"))
    if has_value and can_none:
        return "maybe_none"
    if has_value and not can_none:
        return "definite_value"
    if (not has_value) and can_none:
        return "maybe_none"
    return "unknown"


def _base_taint_signature(fn_facts: Dict[str, Any]) -> Dict[str, Any]:
    params = fn_facts.get("params", []) or []
    returns = fn_facts.get("returns", []) or []
    params_to_return = sorted({
        p for p in params
        for r in returns
        if p and re.search(rf"\b{re.escape(p)}\b", r.get("expr", "") or "")
    })
    sinks = fn_facts.get("taint_sinks", []) or []
    reaches_sink = any(s.get("tainted") for s in sinks)
    return {"params_to_return": params_to_return, "reaches_sink": reaches_sink}


def compute_summaries(module_facts: Dict[str, Any], call_graph: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    funcs = call_graph.get("functions", {})
    facts_by_line = {fn.get("line"): fn for fn in module_facts.get("functions", [])}

    # base summaries (intraprocedural)
    summaries: Dict[str, Dict[str, Any]] = {}
    for qual, meta in funcs.items():
        ff = facts_by_line.get(meta.get("line"), {})
        summaries[qual] = {
            "return_nullability": _base_nullability(ff),
            "may_raise": "may_raise" if meta.get("has_raise") else "no_raise",
            "taint_signature": _base_taint_signature(ff),
        }

    # outgoing calls (all) and return-position calls, per caller
    outgoing: Dict[str, List[Dict[str, Any]]] = {}
    for cs in call_graph.get("call_sites", []):
        outgoing.setdefault(cs["caller"], []).append(cs)
    return_calls = call_graph.get("return_calls", {})
    callers_of = call_graph.get("callers_of", {})

    def recompute(qual: str) -> Dict[str, Any]:
        cur = summaries[qual]
        null_v = cur["return_nullability"]
        # nullability flows from return-position calls
        for rc in return_calls.get(qual, []):
            if rc.get("resolved") and rc.get("callee") in summaries:
                null_v = _join_null(null_v, summaries[rc["callee"]]["return_nullability"])
            else:
                null_v = _join_null(null_v, "unknown")  # widen on unresolved
        # may_raise flows from every outgoing call
        raise_v = cur["may_raise"]
        for cs in outgoing.get(qual, []):
            if cs.get("resolved") and cs.get("callee") in summaries:
                raise_v = _join_raise(raise_v, summaries[cs["callee"]]["may_raise"])
            else:
                raise_v = _join_raise(raise_v, "unknown")  # widen on unresolved
        return {
            "return_nullability": null_v,
            "may_raise": raise_v,
            "taint_signature": cur["taint_signature"],  # base-only in 93A
        }

    # deterministic worklist; monotone joins guarantee termination
    work: List[str] = sorted(summaries)
    in_work = set(work)
    iters = 0
    while work and iters < _MAX_ITERS:
        qual = work.pop(0)
        in_work.discard(qual)
        iters += 1
        new = recompute(qual)
        if (new["return_nullability"] != summaries[qual]["return_nullability"]
                or new["may_raise"] != summaries[qual]["may_raise"]):
            summaries[qual] = new
            for caller in callers_of.get(qual, []):
                if caller not in in_work:
                    work.append(caller)
                    in_work.add(caller)

    return summaries
