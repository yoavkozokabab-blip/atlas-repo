"""Confirmed-defect gate (Phase 99A / 99F design-compliant).

Deterministic classification over existing verification-evidence atoms and
impact context. Does NOT change detectors, benchmarks, or finding generation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import verification_evidence as VE
from .finding import Finding

CONFIRMED_DEFECT_GATE_ENABLED = False
CONFIRMED_DEFECT_SHADOW_MODE = False

SCHEMA_VERSION = 2
GATE_VERSION = "phase99f-v1"

CLASS_CONFIRMED = "confirmed_defect"
CLASS_STRONG_SUSPECT = "strong_suspect"
CLASS_REVIEW_LEAD = "review_lead"
CLASS_REFUTED = "refuted"

CLASSIFICATIONS = (
    CLASS_CONFIRMED,
    CLASS_STRONG_SUSPECT,
    CLASS_REVIEW_LEAD,
    CLASS_REFUTED,
)

REFUTE_STRENGTHS = {VE.E2, VE.E3, VE.E4}
EXECUTABLE_TYPES = {VE.EVIDENCE_TEST, VE.EVIDENCE_RUNTIME}


def _atom_by_type(atoms: Sequence[Dict[str, Any]], evidence_type: str) -> List[Dict[str, Any]]:
    return [atom for atom in atoms if atom.get("evidence_type") == evidence_type]


def _first_atom(
    atoms: Sequence[Dict[str, Any]],
    evidence_type: str,
    *,
    polarity: Optional[str] = None,
    path_status: Optional[str] = None,
    min_strength: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    for atom in atoms:
        if atom.get("evidence_type") != evidence_type:
            continue
        if polarity is not None and atom.get("polarity") != polarity:
            continue
        if path_status is not None and atom.get("provenance", {}).get("path_status") != path_status:
            continue
        if min_strength is not None:
            try:
                if VE.STRENGTH_LEVELS.index(atom.get("strength")) < VE.STRENGTH_LEVELS.index(min_strength):
                    continue
            except ValueError:
                continue
        return atom
    return None


def _is_calibrated_refuting_atom(finding: Finding, atom: Dict[str, Any]) -> bool:
    """97D calibration: weak pattern-only witnesses are not genuine refutes."""
    if (
        finding.kind == "pattern"
        and atom.get("evidence_type") == VE.EVIDENCE_PATH_FEASIBILITY
        and atom.get("claim") == "path.no_implicit_none_exit"
    ):
        return False
    return (
        atom.get("polarity") == VE.POLARITY_REFUTES
        and atom.get("strength") in REFUTE_STRENGTHS
    )


def _calibrated_refuting_atoms(finding: Finding, ve: Dict[str, Any]) -> List[Dict[str, Any]]:
    atoms = list(ve.get("refuting_evidence") or [])
    atoms.extend(
        atom for atom in (ve.get("atoms") or [])
        if atom.get("polarity") == VE.POLARITY_REFUTES
    )
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []
    for atom in atoms:
        atom_id = atom.get("evidence_id")
        if atom_id in seen:
            continue
        if _is_calibrated_refuting_atom(finding, atom):
            out.append(atom)
            if atom_id:
                seen.add(atom_id)
    return out


def _has_executable_witness(atoms: Sequence[Dict[str, Any]]) -> bool:
    """C3: bound failing test or runtime reproduction at E2+ (supports only)."""
    for atom in atoms:
        if atom.get("evidence_type") not in EXECUTABLE_TYPES:
            continue
        if atom.get("polarity") != VE.POLARITY_SUPPORTS:
            continue
        if atom.get("strength") not in REFUTE_STRENGTHS:
            continue
        return True
    return False


def _impact_consequence_resolved(ve: Dict[str, Any]) -> bool:
    """C4: resolved consuming context from impact scope."""
    impact = ve.get("impact_context")
    if not isinstance(impact, dict):
        return False
    if impact.get("blockers"):
        return False
    return bool(impact.get("resolved"))


def _design_blockers(finding: Finding, ve: Dict[str, Any], atoms: Sequence[Dict[str, Any]]) -> List[str]:
    """Hard blockers §3 mapped onto existing overlay signals."""
    blockers: List[str] = []
    overlay_blockers = list(ve.get("blockers") or [])
    if "interprocedural_promotion_gate_not_met" in overlay_blockers:
        blockers.append("unresolved_critical_edge")
    if any("unresolved" in blocker for blocker in overlay_blockers):
        blockers.append("unresolved_critical_edge")
    impact = ve.get("impact_context") or {}
    blockers.extend(impact.get("blockers") or [])

    if not _first_atom(atoms, VE.EVIDENCE_CONTRACT_VIOLATION, polarity=VE.POLARITY_SUPPORTS, min_strength=VE.E2):
        blockers.append("weak_contract_only")

    path_atom = _first_atom(atoms, VE.EVIDENCE_PATH_FEASIBILITY, polarity=VE.POLARITY_SUPPORTS)
    if path_atom and path_atom.get("provenance", {}).get("path_status") == "partial":
        blockers.append("path_feasibility_partial")

    if not _impact_consequence_resolved(ve):
        blockers.append("no_observable_consequence")

    if _calibrated_refuting_atoms(finding, ve):
        blockers.append("refuting_evidence")

    return sorted(set(blockers))


def _evaluate_criteria(finding: Finding, ve: Dict[str, Any]) -> Tuple[Dict[str, bool], List[str]]:
    atoms = list(ve.get("atoms") or [])
    failures: List[str] = []

    c1 = bool(ve.get("promotion_candidate_basis")) and ve.get("status") == VE.STATUS_PROMOTION_CANDIDATE
    if not c1:
        failures.append("c1_not_promotion_candidate")

    c2 = not _calibrated_refuting_atoms(finding, ve)
    if not c2:
        failures.append("c2_refuting_guard")

    c3 = _has_executable_witness(atoms)
    if not c3:
        failures.append("c3_no_executable_witness")

    c4 = _impact_consequence_resolved(ve)
    if not c4:
        failures.append("c4_unresolved_consequence")

    obligations = list(ve.get("missing_proof_obligations") or [])
    c5 = len(obligations) == 0
    if not c5:
        failures.append("c5_missing_proof_obligations")

    c6 = bool(CONFIRMED_DEFECT_GATE_ENABLED and VE.EVIDENCE_PROMOTION_ENABLED)
    if not c6:
        failures.append("c6_flags_not_enabled")

    criteria = {"c1": c1, "c2": c2, "c3": c3, "c4": c4, "c5": c5, "c6": c6}
    return criteria, failures


def _build_confirmation_bundle(finding: Finding, ve: Dict[str, Any]) -> Dict[str, Any]:
    atoms = list(ve.get("atoms") or [])
    violation = _first_atom(
        atoms, VE.EVIDENCE_CONTRACT_VIOLATION, polarity=VE.POLARITY_SUPPORTS, min_strength=VE.E2,
    )
    path = _first_atom(
        atoms,
        VE.EVIDENCE_PATH_FEASIBILITY,
        polarity=VE.POLARITY_SUPPORTS,
        path_status="feasible",
        min_strength=VE.E3,
    )
    executable = _first_atom(atoms, VE.EVIDENCE_TEST, polarity=VE.POLARITY_SUPPORTS, min_strength=VE.E2)
    if executable is None:
        executable = _first_atom(atoms, VE.EVIDENCE_RUNTIME, polarity=VE.POLARITY_SUPPORTS, min_strength=VE.E2)
    refuting = _calibrated_refuting_atoms(finding, ve)
    return {
        "finding": {
            "id": finding.id,
            "rule": finding.rule,
            "file": finding.file,
            "line": finding.line,
            "function": finding.function,
        },
        "expected_contract": violation,
        "feasible_path": path,
        "observable_consequence": ve.get("impact_context"),
        "executable_witness": executable,
        "refuting_evidence_considered": [
            {"evidence_id": atom.get("evidence_id"), "claim": atom.get("claim"), "strength": atom.get("strength")}
            for atom in refuting
        ],
        "blockers": [],
        "gate_version": GATE_VERSION,
        "evidence_schema_version": ve.get("schema_version"),
    }


def _bundle_complete(bundle: Dict[str, Any]) -> bool:
    required = (
        "finding",
        "expected_contract",
        "feasible_path",
        "observable_consequence",
        "executable_witness",
    )
    for key in required:
        value = bundle.get(key)
        if not value:
            return False
    impact = bundle.get("observable_consequence") or {}
    if not impact.get("resolved"):
        return False
    return True


def _why_not_confirmed(
    classification: str,
    criteria_failures: Sequence[str],
    design_blockers: Sequence[str],
) -> List[str]:
    if classification == CLASS_CONFIRMED:
        return []
    reasons = ["Confirmed defect requires C1–C6 and a complete confirmation bundle."]
    if criteria_failures:
        reasons.append("Criteria failures: " + ", ".join(criteria_failures) + ".")
    if design_blockers:
        reasons.append("Design blockers: " + ", ".join(design_blockers) + ".")
    if classification == CLASS_STRONG_SUSPECT:
        reasons.append("Promotion-candidate basis holds but confirmation proof is incomplete.")
    elif classification == CLASS_REVIEW_LEAD:
        reasons.append("Finding remains a review lead.")
    elif classification == CLASS_REFUTED:
        reasons.append("Finding is refuted or not actionable under overlay evidence.")
    return reasons


def _tier_from_overlay(finding: Finding, ve: Dict[str, Any]) -> str:
    """Map overlay status to design taxonomy before confirmation upgrade."""
    status = ve.get("status")
    overlay_blockers = list(ve.get("blockers") or [])
    refuting = _calibrated_refuting_atoms(finding, ve)

    if refuting or status == VE.STATUS_REFUTED:
        return CLASS_REFUTED
    if status == VE.STATUS_UNKNOWN:
        return CLASS_REFUTED
    if status == VE.STATUS_BLOCKED or len(overlay_blockers) >= 2:
        return CLASS_REFUTED
    if ve.get("promotion_candidate_basis") or status == VE.STATUS_PROMOTION_CANDIDATE:
        return CLASS_STRONG_SUSPECT
    return CLASS_REVIEW_LEAD


def classify_inconsistent_return(finding: Finding) -> Optional[Dict[str, Any]]:
    """Return a design-compliant gate packet for ``inconsistent_return`` findings."""
    if not CONFIRMED_DEFECT_GATE_ENABLED:
        return None
    if finding.rule != "inconsistent_return":
        return None

    ve = finding.verification_evidence
    if ve is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "classification": CLASS_REFUTED,
            "overlay_status": "missing",
            "promotion_candidate_basis": False,
            "criteria": {"c1": False, "c2": False, "c3": False, "c4": False, "c5": False, "c6": False},
            "criteria_failures": ["missing_verification_overlay"],
            "design_blockers": ["no_atoms"],
            "confirmation_bundle": None,
            "surfaced": False,
            "why_not_confirmed": _why_not_confirmed(CLASS_REFUTED, ["missing_verification_overlay"], ["no_atoms"]),
        }

    atoms = list(ve.get("atoms") or [])
    criteria, criteria_failures = _evaluate_criteria(finding, ve)
    design_blockers = _design_blockers(finding, ve, atoms)
    classification = _tier_from_overlay(finding, ve)
    bundle: Optional[Dict[str, Any]] = None
    surfaced = False

    if all(criteria.values()) and not design_blockers:
        bundle = _build_confirmation_bundle(finding, ve)
        if _bundle_complete(bundle):
            classification = CLASS_CONFIRMED
            surfaced = not CONFIRMED_DEFECT_SHADOW_MODE
        else:
            classification = CLASS_STRONG_SUSPECT
            criteria_failures = list(criteria_failures) + ["confirmation_bundle_incomplete"]

    return {
        "schema_version": SCHEMA_VERSION,
        "classification": classification,
        "overlay_status": ve.get("status"),
        "promotion_candidate_basis": bool(ve.get("promotion_candidate_basis")),
        "criteria": criteria,
        "criteria_failures": criteria_failures,
        "design_blockers": design_blockers,
        "confirmation_bundle": bundle,
        "surfaced": surfaced,
        "why_not_confirmed": _why_not_confirmed(classification, criteria_failures, design_blockers),
    }


def _copy_with_gate(finding: Finding, gate: Optional[Dict[str, Any]]) -> Finding:
    tags = list(finding.tags)
    tags = [
        tag for tag in tags
        if tag not in ("confirmed_bug", "confirmed_defect", "confirmed_actionable")
    ]
    if gate and gate.get("classification") == CLASS_CONFIRMED and gate.get("surfaced"):
        tags.append("confirmed_defect")
    return Finding(
        category=finding.category,
        kind=finding.kind,
        severity=finding.severity,
        confidence=finding.confidence,
        file=finding.file,
        line=finding.line,
        title=finding.title,
        explanation=finding.explanation,
        why_might_be_wrong=finding.why_might_be_wrong,
        next_verification_step=finding.next_verification_step,
        function=finding.function,
        evidence=finding.evidence,
        rule=finding.rule,
        source_facts=list(finding.source_facts),
        tags=tags,
        id=finding.id,
        contract_review=finding.contract_review,
        verification_evidence=finding.verification_evidence,
        confirmed_defect_classification=gate,
    )


def apply_gate(findings: List[Finding]) -> List[Finding]:
    if not CONFIRMED_DEFECT_GATE_ENABLED:
        return findings
    return [
        _copy_with_gate(f, classify_inconsistent_return(f))
        if f.rule == "inconsistent_return"
        else f
        for f in findings
    ]


def evaluate_enablement_gates(
    *,
    quixbugs_path: Optional[str] = None,
    holdout_pairs_root: Optional[str] = None,
) -> Dict[str, Any]:
    """Phase 99 §6 negative enablement gates (automated subset)."""
    from pathlib import Path

    from . import engine
    from . import engine_benchmark

    if not CONFIRMED_DEFECT_GATE_ENABLED or not VE.EVIDENCE_PROMOTION_ENABLED:
        return {
            "available": False,
            "reason": "both CONFIRMED_DEFECT_GATE_ENABLED and EVIDENCE_PROMOTION_ENABLED must be True",
            "gates": [],
        }

    def _classify_source(text: str, rel_path: str) -> List[Finding]:
        result = engine.analyze_source(text, rel_path)
        gated = apply_gate(result.findings)
        return [f for f in gated if f.rule == "inconsistent_return"]

    gates: List[Dict[str, Any]] = []

    qb_root = Path(quixbugs_path or r"C:\Repos\QuixBugs").expanduser()
    if qb_root.is_dir():
        correct_root = qb_root / "correct_python_programs"
        confirmed = 0
        for path in sorted(correct_root.glob("*.py")):
            rel = path.relative_to(qb_root).as_posix()
            confirmed += sum(
                1 for f in _classify_source(path.read_text(encoding="utf-8-sig", errors="ignore"), rel)
                if (f.confirmed_defect_classification or {}).get("surfaced")
            )
        gates.append(
            {
                "name": "quixbugs_correct_zero_confirmed",
                "passed": confirmed == 0,
                "detail": f"{confirmed} confirmed on correct variants",
            }
        )
    else:
        gates.append({"name": "quixbugs_correct_zero_confirmed", "passed": None, "detail": "QuixBugs absent"})

    pairs_root = Path(holdout_pairs_root) if holdout_pairs_root else engine_benchmark._PAIRS_ROOT
    if pairs_root.is_dir():
        confirmed = 0
        for case_dir in sorted(p for p in pairs_root.iterdir() if p.is_dir()):
            fixed = case_dir / "fixed.py"
            if not fixed.is_file():
                continue
            rel = f"holdout/{case_dir.name}/fixed.py"
            confirmed += sum(
                1 for f in _classify_source(fixed.read_text(encoding="utf-8-sig", errors="ignore"), rel)
                if (f.confirmed_defect_classification or {}).get("surfaced")
            )
        gates.append(
            {
                "name": "holdout_fixed_zero_confirmed",
                "passed": confirmed == 0,
                "detail": f"{confirmed} confirmed on fixed variants",
            }
        )
    else:
        gates.append({"name": "holdout_fixed_zero_confirmed", "passed": None, "detail": "holdout absent"})

    gates.append(
        {
            "name": "phase98a_human_review",
            "passed": None,
            "detail": "manual gate — requires blinded review before production enablement",
        }
    )
    gates.append(
        {
            "name": "phase95e_rejected_zero_confirmed",
            "passed": None,
            "detail": "manual gate — replay labeled 95E corpus with adjudicated labels",
        }
    )

    automated = [gate for gate in gates if gate["passed"] is not None]
    return {
        "available": True,
        "gates": gates,
        "automated_pass": all(gate["passed"] for gate in automated) if automated else None,
    }
