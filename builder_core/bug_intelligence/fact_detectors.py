"""Fact-consuming detectors for the unified engine (Phase 92B / 93B).

These detectors read the unified fact model (``facts.extract_module_facts``,
including the Phase 93A ``interproc`` section) rather than re-walking the AST, and
emit unified ``Finding`` objects. They are name-agnostic.

``inconsistent_return`` promotion (Phase 93B):
A function matching the Phase 92B missing-return shape is *promoted* to the
verdict-eligible ``value_flow`` kind **only** when interprocedural evidence is
unambiguous:
- at least one resolved same-file caller **dereferences** the result, AND
- no resolved caller **null-checks** the result.
Mixed evidence (some deref + some null-check), no deref evidence, or no resolved
caller (unresolved) -> the finding stays a quarantined ``pattern`` diagnostic and
does not enter the benchmark verdict.

``INTERPROC_PROMOTION_ENABLED`` is the global kill-switch set by the measurement
gate: if promotion ever produces a false positive on QuixBugs correct / holdout
fixed, it is set to False (fully quarantined) and the reason is reported.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .finding import Finding, LOGIC_BUG

QUARANTINE_KIND = "pattern"     # diagnostic only; excluded from the verdict
PROMOTED_KIND = "value_flow"    # verdict-eligible

# GATE RESULT (Phase 93B): intra-file promotion ENABLED — measured 0 false
# positives on QuixBugs correct files and holdout fixed files. See
# reports/phase93b_inconsistent_return_promotion.md.
INTERPROC_PROMOTION_ENABLED = True

# Phase 93D — cross-file consumption, shipped DISABLED by default. When False the
# detector behaves EXACTLY as Phase 93B (intra-file evidence only). It may be set
# True only after the resolution-precision and 0-FP real-repo gates pass; that
# enablement is deliberately NOT done here. See
# reports/phase93d_cross_file_consumer_gate_design.md.
CROSS_FILE_CONSUMPTION_ENABLED = False


def _merge_usage(qualname, intra: Dict[str, Any], cross) -> Dict[str, bool] | None:
    """Merge intra-file and (optionally) cross-file call-site usage for ``qualname``.

    Returns the OR-merged {uses_return, null_checked, dereferenced}, or None when
    neither source has a resolved caller. ``cross`` is None unless cross-file
    consumption is enabled and the facts are present (so flag-off == 93B exactly).
    """
    if qualname is None:
        return None
    sources = [intra.get(qualname)]
    if cross is not None:
        sources.append(cross.get(qualname))
    sources = [s for s in sources if s]
    if not sources:                       # no resolved caller anywhere -> unresolved
        return None
    merged = {"uses_return": False, "null_checked": False, "dereferenced": False}
    for s in sources:
        merged["uses_return"] = merged["uses_return"] or bool(s.get("uses_return"))
        merged["null_checked"] = merged["null_checked"] or bool(s.get("null_checked"))
        merged["dereferenced"] = merged["dereferenced"] or bool(s.get("dereferenced"))
    return merged


def _promote_from_usage(merged: Dict[str, bool] | None) -> bool:
    """Promote iff >=1 caller dereferences and NO caller null-checks (any null-check
    or unresolved-only evidence vetoes)."""
    if merged is None:
        return False
    if merged["null_checked"]:            # any null-check -> contract / mixed -> quarantine
        return False
    return bool(merged["dereferenced"])


def detect_inconsistent_return(module_facts: Dict[str, Any], file: str) -> List[Finding]:
    """Fact-backed missing-return detector with interprocedural promotion.

    Intraprocedural trigger (Phase 92B): function has >=1 explicit non-None value
    return, no explicit None / bare return, and can fall through to implicit None.
    The kind (promoted vs quarantined) is decided per function from the Phase 93A
    interprocedural call-site usage facts.
    """
    interproc = module_facts.get("interproc", {}) or {}
    cg = interproc.get("call_graph", {}) or {}
    intra_usage = cg.get("usage_by_callee", {}) or {}
    line_to_qual = {
        meta.get("line"): qual
        for qual, meta in (cg.get("functions", {}) or {}).items()
    }

    # Cross-file usage is read ONLY when consumption is enabled AND the facts are
    # present. Absent / disabled -> None -> exact Phase 93B (intra-file) behavior.
    cross_usage = None
    if CROSS_FILE_CONSUMPTION_ENABLED:
        cross_usage = (interproc.get("cross_file", {}) or {}).get("usage_by_callee")

    out: List[Finding] = []
    for fn in module_facts.get("functions", []):
        rs = fn.get("return_summary") or {}
        if not (rs.get("has_value_return")
                and not rs.get("has_none_return")
                and rs.get("can_fall_through")):
            continue

        name = fn.get("name", "")
        qual = line_to_qual.get(fn.get("line"))
        merged = _merge_usage(qual, intra_usage, cross_usage)
        promoted = INTERPROC_PROMOTION_ENABLED and _promote_from_usage(merged)
        used_cross = bool(cross_usage and qual in cross_usage)

        if promoted:
            kind, confidence = PROMOTED_KIND, "high"
            scope = "a caller (intra- or cross-file)" if used_cross else "a caller in this file"
            explanation = (
                f"'{name}' returns a value on some paths but can fall through to an "
                f"implicit None, and {scope} dereferences the result without a None "
                f"check (and no caller null-checks it). The implicit-None path will "
                f"therefore crash a caller — a missing return."
            )
            source_facts = [
                "return_summary: has_value_return && !has_none_return && can_fall_through",
                ("interproc: a resolved caller dereferences the result; none null-checks it"
                 + (" (cross-file evidence used)" if used_cross else "")),
            ]
        else:
            kind, confidence = QUARANTINE_KIND, "medium"
            explanation = (
                f"'{name}' returns a value on some paths but can also reach the end of its "
                f"body without returning, yielding None. Interprocedural evidence is "
                f"insufficient to confirm this is a bug (callers null-check it, do not "
                f"dereference it, or are unresolved), so this is a diagnostic only."
            )
            source_facts = [
                "return_summary: has_value_return && !has_none_return && can_fall_through",
                "interproc: no unambiguous deref-without-null-check caller (quarantined)",
            ]

        out.append(Finding(
            category=LOGIC_BUG,
            kind=kind,
            severity="medium",
            confidence=confidence,
            file=file,
            line=int(fn.get("line", 1)),
            function=name,
            title=f"'{name}' may fall through to an implicit None",
            explanation=explanation,
            evidence="",
            why_might_be_wrong=(
                "The fall-through path may be unreachable in a way the intraprocedural "
                "control-flow approximation cannot see, or returning None on that path "
                "may be an unstated but intended outcome that callers tolerate."
            ),
            next_verification_step=(
                "Confirm whether the no-return path is reachable; if so, add an explicit "
                "return value (or an explicit `return None` if None is intended)."
            ),
            rule="inconsistent_return",
            source_facts=source_facts,
        ))
    return out


def all_detectors(module_facts: Dict[str, Any], file: str) -> List[Finding]:
    """Run every fact-backed detector and return their unified findings."""
    return detect_inconsistent_return(module_facts, file)
