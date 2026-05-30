"""Fact-consuming detectors for the unified engine (Phase 92B).

These detectors read the unified fact model (``facts.extract_module_facts``)
rather than re-walking the AST, and emit unified ``Finding`` objects. They are
name-agnostic: no function name, variable name, or corpus-specific name is used.

Promotion gate (``inconsistent_return``):
- The detector is *promoted* (kind ``value_flow``, counted in the grounded
  benchmark verdict) only if it produced **zero** false positives across the
  QuixBugs correct files and the holdout fixed files.
- Otherwise it is *quarantined* (kind ``pattern``, diagnostic only, excluded
  from the verdict). ``INCONSISTENT_RETURN_KIND`` records the decision.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .finding import Finding, LOGIC_BUG

# Set by the Phase 92B promotion gate (see reports/phase92b_inconsistent_return.md).
# "value_flow" = promoted (counts in verdict); "pattern" = quarantined (diagnostic).
#
# GATE RESULT: QUARANTINED. The detector produced 1 false positive on the
# QuixBugs correct file `next_permutation.py` (a correct algorithm that
# intentionally falls through to an implicit None when there is no next
# permutation). Per the precision-first gate, it is excluded from the benchmark
# verdict and remains a diagnostic only.
INCONSISTENT_RETURN_KIND = "pattern"


def detect_inconsistent_return(module_facts: Dict[str, Any], file: str) -> List[Finding]:
    """Fact-backed missing-return detector.

    Fires only when a function (1) has >=1 explicit non-None value return,
    (2) has no explicit None / bare return, and (3) can fall through to an
    implicit None. This is the genuine missing-return bug; it deliberately does
    NOT fire on value-or-None / value-or-False contracts (those acknowledge a
    non-value return) or on functions where every path returns.
    """
    out: List[Finding] = []
    for fn in module_facts.get("functions", []):
        rs = fn.get("return_summary") or {}
        if not (rs.get("has_value_return")
                and not rs.get("has_none_return")
                and rs.get("can_fall_through")):
            continue
        name = fn.get("name", "")
        out.append(Finding(
            category=LOGIC_BUG,
            kind=INCONSISTENT_RETURN_KIND,
            severity="medium",
            confidence="high",
            file=file,
            line=int(fn.get("line", 1)),
            function=name,
            title=f"'{name}' may fall through to an implicit None",
            explanation=(
                f"'{name}' returns a value on some paths but can also reach the end of "
                f"its body without returning, yielding None on that path. It never "
                f"explicitly returns None, so the implicit-None path is most likely a "
                f"missing return rather than an intended value-or-None contract."
            ),
            evidence="",
            why_might_be_wrong=(
                "The fall-through path may be unreachable in a way the intraprocedural "
                "control-flow approximation cannot see, or returning None on that path "
                "may be an unstated but intended outcome."
            ),
            next_verification_step=(
                "Confirm whether the no-return path is reachable; if so, add an explicit "
                "return value (or an explicit `return None` if None is intended)."
            ),
            rule="inconsistent_return",
            source_facts=[
                "return_summary: has_value_return && !has_none_return && can_fall_through",
            ],
        ))
    return out


def all_detectors(module_facts: Dict[str, Any], file: str) -> List[Finding]:
    """Run every fact-backed detector and return their unified findings."""
    return detect_inconsistent_return(module_facts, file)
