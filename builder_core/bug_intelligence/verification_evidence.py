"""Verification evidence overlay (Phase 97A).

Attaches typed, deterministic evidence atoms to findings for human review.
Does NOT promote findings, confirm defects, or change detector logic.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import callgraph, contract_facts
from .finding import Finding

VERIFICATION_EVIDENCE_ENABLED = True
EVIDENCE_PROMOTION_ENABLED = False
REVIEW_LEAD_TAG = "review_lead_only"

SCHEMA_VERSION = 1

EVIDENCE_TEST = "test_evidence"
EVIDENCE_ASSERTION = "assertion_evidence"
EVIDENCE_CONTRACT_VIOLATION = "contract_violation_evidence"
EVIDENCE_PATH_FEASIBILITY = "path_feasibility_evidence"
EVIDENCE_RUNTIME = "runtime_reproduction_evidence"

EVIDENCE_TYPES = (
    EVIDENCE_TEST,
    EVIDENCE_ASSERTION,
    EVIDENCE_CONTRACT_VIOLATION,
    EVIDENCE_PATH_FEASIBILITY,
    EVIDENCE_RUNTIME,
)

E0 = "E0"
E1 = "E1"
E2 = "E2"
E3 = "E3"
E4 = "E4"
STRENGTH_LEVELS = (E0, E1, E2, E3, E4)

POLARITY_SUPPORTS = "supports"
POLARITY_REFUTES = "refutes"
POLARITY_LIMITS = "limits"
POLARITY_UNKNOWN = "unknown"

STATUS_ENRICHED_LEAD = "enriched_lead"
STATUS_PROMOTION_CANDIDATE = "promotion_candidate"
STATUS_REFUTED = "refuted"
STATUS_BLOCKED = "blocked"
STATUS_UNKNOWN = "unknown"

SOURCE_REPOSITORY_AST = "repository_ast"
SOURCE_CONTRACT_FACT = "contract_fact"
SOURCE_APPROVED_HARNESS = "approved_harness"

_SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|secret|token|password|authorization)\s*[:=]\s*\S+"
)


def _qualname_for_finding(module_facts: Dict[str, Any], finding: Finding) -> str:
    interproc = module_facts.get("interproc") or {}
    cg = interproc.get("call_graph") or {}
    line_to_qual = {
        meta.get("line"): qual
        for qual, meta in (cg.get("functions") or {}).items()
    }
    qual = line_to_qual.get(finding.line)
    if qual:
        return qual
    for q, meta in (cg.get("functions") or {}).items():
        if meta.get("line") == finding.line:
            return q
    return finding.function or ""


def _fn_facts(module_facts: Dict[str, Any], qual: str, line: int) -> Dict[str, Any]:
    interproc = module_facts.get("interproc") or {}
    cg = interproc.get("call_graph") or {}
    fn_meta = (cg.get("functions") or {}).get(qual) or {}
    name = fn_meta.get("name") or qual.split(".")[-1]
    for fn in module_facts.get("functions") or []:
        if fn.get("line") == line or fn.get("name") == name:
            return fn
    return {}


def _stable_id(payload: Dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str)
    return "VE-" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def _atom(
    *,
    evidence_type: str,
    polarity: str,
    strength: str,
    claim: str,
    subject: Dict[str, Any],
    provenance: Dict[str, Any],
    binding: Dict[str, Any],
    limitations: Optional[List[str]] = None,
) -> Dict[str, Any]:
    base = {
        "evidence_type": evidence_type,
        "polarity": polarity,
        "strength": strength,
        "claim": claim,
        "subject": subject,
        "provenance": provenance,
        "binding": binding,
        "limitations": list(limitations or []),
    }
    base["evidence_id"] = _stable_id(base)
    return base


def _sanitize_text(text: str) -> str:
    return _SECRET_RE.sub(r"\1=<redacted>", text or "")


def _import_bindings(tree: ast.AST) -> Tuple[Dict[str, str], List[str]]:
    """Map local names to qualnames; collect unresolved reasons for star imports."""
    bindings: Dict[str, str] = {}
    unresolved: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                unresolved.append("relative_import")
                continue
            module = node.module or ""
            for alias in node.names:
                if alias.name == "*":
                    unresolved.append("star_import")
                    continue
                local = alias.asname or alias.name
                bindings[local] = f"{module}.{alias.name}" if module else alias.name
        elif isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".")[0]
                bindings[local] = alias.name
    return bindings, unresolved


def _resolve_call_name(node: ast.AST, bindings: Dict[str, str]) -> Tuple[Optional[str], List[str]]:
    reasons: List[str] = []
    if isinstance(node, ast.Name):
        if node.id in bindings:
            return bindings[node.id], reasons
        return node.id, reasons
    if isinstance(node, ast.Attribute):
        value = node.value
        if isinstance(value, ast.Name):
            base = bindings.get(value.id, value.id)
            return f"{base}.{node.attr}", reasons
        reasons.append("dynamic_lookup")
        return None, reasons
    reasons.append("dynamic_lookup")
    return None, reasons


def _assert_claim(test: ast.AST) -> Tuple[str, str]:
    if isinstance(test, ast.Compare):
        if len(test.ops) == 1 and isinstance(test.ops[0], ast.IsNot):
            if isinstance(test.comparators[0], ast.Constant) and test.comparators[0].value is None:
                return "return.non_none", "assert_is_not_none"
        if len(test.ops) == 1 and isinstance(test.ops[0], ast.Eq):
            return "return.shape_uniform", "assert_equals"
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        inner = test.operand
        if isinstance(inner, ast.Call):
            return "raises_or_falsy", "assert_not_call"
    return "assertion.observed", "assert_generic"


def _extract_test_evidence(
    subject_qual: str,
    subject_file: str,
    test_documents: Sequence[Dict[str, str]],
) -> List[Dict[str, Any]]:
    atoms: List[Dict[str, Any]] = []
    subject_name = subject_qual.split(".")[-1]
    for doc in test_documents:
        path = doc.get("path") or doc.get("file") or "tests/test_module.py"
        content = doc.get("content") or doc.get("text") or ""
        if not content.strip():
            continue
        try:
            tree = ast.parse(content)
        except SyntaxError:
            continue
        bindings, import_issues = _import_bindings(tree)
        for fn_node in tree.body:
            if not isinstance(fn_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not fn_node.name.startswith("test"):
                continue
            test_qual = f"{path}::{fn_node.name}"
            for node in ast.walk(fn_node):
                if not isinstance(node, ast.Assert):
                    continue
                test_expr = node.test
                call_node: Optional[ast.Call] = None
                if isinstance(test_expr, ast.Call):
                    call_node = test_expr
                elif isinstance(test_expr, ast.Compare) and isinstance(test_expr.left, ast.Call):
                    call_node = test_expr.left
                elif isinstance(test_expr, ast.UnaryOp) and isinstance(test_expr.operand, ast.Call):
                    call_node = test_expr.operand
                if call_node is None:
                    continue
                resolved_qual, call_reasons = _resolve_call_name(call_node.func, bindings)
                claim, claim_kind = _assert_claim(test_expr)
                reasons = list(import_issues) + call_reasons
                bound = (
                    resolved_qual == subject_qual
                    or resolved_qual == subject_name
                    or (resolved_qual and resolved_qual.endswith("." + subject_name))
                )
                if not bound:
                    continue
                if reasons:
                    strength = E1
                    polarity = POLARITY_LIMITS
                    resolved = False
                else:
                    strength = E2
                    polarity = POLARITY_SUPPORTS
                    resolved = True
                atoms.append(_atom(
                    evidence_type=EVIDENCE_TEST,
                    polarity=polarity,
                    strength=strength,
                    claim=claim,
                    subject={
                        "file": subject_file,
                        "qualname": subject_qual,
                        "line": node.lineno,
                        "slot": "test",
                    },
                    provenance={
                        "source_kind": SOURCE_REPOSITORY_AST,
                        "source_ref": f"{path}:{node.lineno}",
                        "test_function": test_qual,
                        "claim_kind": claim_kind,
                    },
                    binding={
                        "resolved": resolved,
                        "resolution_scope": "repository" if resolved else "external",
                        "unresolved_reasons": sorted(set(reasons)),
                    },
                    limitations=[
                        "Static test expectation only; observed execution not recorded."
                    ],
                ))
    return atoms


def _extract_assertion_evidence(
    module_facts: Dict[str, Any],
    subject_qual: str,
    subject_file: str,
    line: int,
) -> List[Dict[str, Any]]:
    atoms: List[Dict[str, Any]] = []
    contracts = module_facts.get("contracts") or {}
    for bucket in (
        "argument_contracts",
        "nullability_contracts",
        "return_contracts",
        "state_mutation_contracts",
    ):
        for rec in contracts.get(bucket) or []:
            subj = rec.get("subject") or {}
            if subj.get("qualname") != subject_qual:
                continue
            if contract_facts.SOURCE_ASSERT not in (rec.get("sources") or []):
                continue
            refs = rec.get("evidence_refs") or []
            ref_line = refs[0].get("line", line) if refs else line
            atoms.append(_atom(
                evidence_type=EVIDENCE_ASSERTION,
                polarity=POLARITY_SUPPORTS,
                strength=E2,
                claim=str(rec.get("obligation") or "assertion.obligation"),
                subject={
                    "file": subject_file,
                    "qualname": subject_qual,
                    "line": ref_line,
                    "slot": subj.get("slot") or "assertion",
                },
                provenance={
                    "source_kind": SOURCE_CONTRACT_FACT,
                    "source_ref": f"{subject_file}:{ref_line}",
                },
                binding={
                    "resolved": True,
                    "resolution_scope": "intra_file",
                    "unresolved_reasons": [],
                },
                limitations=[
                    "Production assertions may be disabled under optimized execution."
                ],
            ))
    return atoms


def _explicit_non_optional_contract(
    module_facts: Dict[str, Any],
    qual: str,
) -> Optional[Dict[str, Any]]:
    contracts = module_facts.get("contracts") or {}
    for rec in contracts.get("return_contracts") or []:
        subj = rec.get("subject") or {}
        if subj.get("qualname") != qual:
            continue
        if contract_facts.SOURCE_TYPE_HINT not in (rec.get("sources") or []):
            continue
        if rec.get("confidence") != contract_facts.CONFIDENCE_EXPLICIT:
            continue
        if rec.get("obligation") in ("return.non_none", "return.never_implicit_none"):
            return rec
    return None


def _optional_return_conflict(module_facts: Dict[str, Any], qual: str) -> bool:
    contracts = module_facts.get("contracts") or {}
    for rec in contracts.get("return_contracts") or []:
        subj = rec.get("subject") or {}
        if subj.get("qualname") != qual:
            continue
        if rec.get("obligation") == "return.optional":
            return True
    return False


def _extract_contract_violation_evidence(
    finding: Finding,
    module_facts: Dict[str, Any],
    qual: str,
    subject_file: str,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    atoms: List[Dict[str, Any]] = []
    blockers: List[str] = []
    fn = _fn_facts(module_facts, qual, finding.line)
    rs = fn.get("return_summary") or {}
    if not rs.get("can_fall_through"):
        return atoms, blockers
    if _optional_return_conflict(module_facts, qual):
        blockers.append("conflicting_optional_return_contract")
        return atoms, blockers
    obligation = _explicit_non_optional_contract(module_facts, qual)
    if obligation is None:
        blockers.append("missing_explicit_return_obligation")
        return atoms, blockers
    strength = E2
    atoms.append(_atom(
        evidence_type=EVIDENCE_CONTRACT_VIOLATION,
        polarity=POLARITY_SUPPORTS,
        strength=strength,
        claim="return.non_none violated by implicit_none_return",
        subject={
            "file": subject_file,
            "qualname": qual,
            "line": finding.line,
            "slot": "return",
        },
        provenance={
            "source_kind": SOURCE_CONTRACT_FACT,
            "source_ref": f"{subject_file}:{finding.line}",
            "obligation_source": "type_hint",
            "behavior_source": "return_summary",
        },
        binding={
            "resolved": True,
            "resolution_scope": "intra_file",
            "unresolved_reasons": [],
        },
        limitations=[
            "Derived violation only; promotion evaluators disabled in Phase 97A."
        ],
    ))
    return atoms, blockers


def _caller_usage(module_facts: Dict[str, Any], qual: str) -> Dict[str, Any]:
    interproc = module_facts.get("interproc") or {}
    cg = interproc.get("call_graph") or {}
    usage = (cg.get("usage_by_callee") or {}).get(qual) or {}
    return {
        "dereferenced": bool(usage.get("dereferenced")),
        "null_checked": bool(usage.get("null_checked")),
        "unresolved_callers": int(usage.get("unresolved_callers") or 0),
    }


def _extract_path_feasibility_evidence(
    finding: Finding,
    module_facts: Dict[str, Any],
    qual: str,
    subject_file: str,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    atoms: List[Dict[str, Any]] = []
    blockers: List[str] = []
    fn = _fn_facts(module_facts, qual, finding.line)
    rs = fn.get("return_summary") or {}
    usage = _caller_usage(module_facts, qual)

    if not rs.get("can_fall_through"):
        atoms.append(_atom(
            evidence_type=EVIDENCE_PATH_FEASIBILITY,
            polarity=POLARITY_REFUTES,
            strength=E2,
            claim="path.no_implicit_none_exit",
            subject={"file": subject_file, "qualname": qual, "line": finding.line, "slot": "branch"},
            provenance={"source_kind": SOURCE_REPOSITORY_AST, "source_ref": f"{subject_file}:{finding.line}"},
            binding={"resolved": True, "resolution_scope": "intra_file", "unresolved_reasons": []},
            limitations=[],
        ))
        return atoms, blockers

    if usage.get("null_checked") and not usage.get("dereferenced"):
        atoms.append(_atom(
            evidence_type=EVIDENCE_PATH_FEASIBILITY,
            polarity=POLARITY_REFUTES,
            strength=E2,
            claim="path.caller_null_check_blocks_consequence",
            subject={"file": subject_file, "qualname": qual, "line": finding.line, "slot": "call"},
            provenance={"source_kind": SOURCE_CONTRACT_FACT, "source_ref": f"{subject_file}:{finding.line}"},
            binding={"resolved": True, "resolution_scope": "intra_file", "unresolved_reasons": []},
            limitations=[],
        ))
        return atoms, blockers

    path_status = "partial"
    strength = E2
    polarity = POLARITY_LIMITS
    unresolved: List[str] = []
    if finding.kind == "value_flow" and usage.get("dereferenced") and not usage.get("null_checked"):
        path_status = "feasible"
        strength = E3
        polarity = POLARITY_SUPPORTS
    elif finding.kind == "pattern":
        path_status = "partial"
        unresolved.append("interprocedural_gate_not_met")
        blockers.append("interprocedural_promotion_gate_not_met")
    if usage.get("unresolved_callers"):
        unresolved.append("unresolved_callers")
        path_status = "partial"
        if STRENGTH_LEVELS.index(strength) > STRENGTH_LEVELS.index(E2):
            strength = E2

    atoms.append(_atom(
        evidence_type=EVIDENCE_PATH_FEASIBILITY,
        polarity=polarity,
        strength=strength,
        claim=f"path.{path_status}",
        subject={"file": subject_file, "qualname": qual, "line": finding.line, "slot": "path"},
        provenance={
            "source_kind": SOURCE_REPOSITORY_AST,
            "source_ref": f"{subject_file}:{finding.line}",
            "path_status": path_status,
        },
        binding={
            "resolved": path_status == "feasible",
            "resolution_scope": "intra_file",
            "unresolved_reasons": sorted(set(unresolved)),
        },
        limitations=["Static path witness only; no runtime trace imported."],
    ))
    return atoms, blockers


def parse_runtime_artifact(artifact: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Parse an imported runtime reproduction artifact into an evidence atom."""
    revision = artifact.get("revision") or artifact.get("pinned_revision") or ""
    command = _sanitize_text(str(artifact.get("command_fingerprint") or artifact.get("command") or ""))
    subject = artifact.get("subject") or {}
    determinism = artifact.get("determinism_result") or artifact.get("deterministic")
    exit_code = artifact.get("exit_code")
    strength = E1
    limitations = ["Runtime artifact present but not promotion-enabled in Phase 97A."]
    unresolved: List[str] = []
    if not revision:
        unresolved.append("missing_pinned_revision")
    if determinism not in (True, "deterministic", "pass"):
        unresolved.append("not_deterministic")
        strength = E1
    elif revision and determinism in (True, "deterministic", "pass"):
        strength = E2
        limitations.append("Observed failure recorded; E4 requires separate approval gate.")
    if exit_code in (0, None):
        unresolved.append("non_failure_exit_code")
        strength = E0
    return _atom(
        evidence_type=EVIDENCE_RUNTIME,
        polarity=POLARITY_SUPPORTS if exit_code not in (0, None) else POLARITY_UNKNOWN,
        strength=strength,
        claim=str(artifact.get("failure_class") or "runtime.failure_observed"),
        subject={
            "file": subject.get("file") or "",
            "qualname": subject.get("qualname") or "",
            "line": int(subject.get("line") or 0),
            "slot": "runtime",
        },
        provenance={
            "source_kind": SOURCE_APPROVED_HARNESS,
            "source_ref": _sanitize_text(str(artifact.get("artifact_ref") or "runtime_artifact")),
            "pinned_revision": revision,
            "command_fingerprint": command,
            "environment_fingerprint": _sanitize_text(str(artifact.get("environment_fingerprint") or "")),
        },
        binding={
            "resolved": not unresolved,
            "resolution_scope": "repository",
            "unresolved_reasons": unresolved,
        },
        limitations=limitations,
    )


def _extract_runtime_evidence(
    module_facts: Dict[str, Any],
    subject_qual: str,
) -> List[Dict[str, Any]]:
    atoms: List[Dict[str, Any]] = []
    for artifact in module_facts.get("verification_artifacts") or []:
        subj = artifact.get("subject") or {}
        if subj.get("qualname") and subj.get("qualname") != subject_qual:
            continue
        atom = parse_runtime_artifact(artifact)
        if atom:
            atoms.append(atom)
    return atoms


def _bundle_indices(atoms: Sequence[Dict[str, Any]]) -> Dict[str, List[str]]:
    out = {
        "contract_atom_ids": [],
        "violation_atom_ids": [],
        "path_atom_ids": [],
        "consequence_atom_ids": [],
        "reproduction_atom_ids": [],
    }
    for atom in atoms:
        eid = atom["evidence_id"]
        etype = atom.get("evidence_type")
        if etype == EVIDENCE_ASSERTION:
            out["contract_atom_ids"].append(eid)
        elif etype == EVIDENCE_CONTRACT_VIOLATION:
            out["violation_atom_ids"].append(eid)
        elif etype == EVIDENCE_PATH_FEASIBILITY:
            out["path_atom_ids"].append(eid)
        elif etype == EVIDENCE_TEST:
            out["consequence_atom_ids"].append(eid)
        elif etype == EVIDENCE_RUNTIME:
            out["reproduction_atom_ids"].append(eid)
    return out


def _missing_obligations(
    atoms: Sequence[Dict[str, Any]],
    blockers: Sequence[str],
) -> List[str]:
    missing: List[str] = []
    types = {a.get("evidence_type") for a in atoms}
    if EVIDENCE_CONTRACT_VIOLATION not in types:
        missing.append("exact contract violation atom")
    if not any(a.get("strength") in (E3, E4) for a in atoms if a.get("evidence_type") == EVIDENCE_PATH_FEASIBILITY):
        missing.append("promotion-grade feasible path witness")
    if EVIDENCE_RUNTIME not in types and EVIDENCE_TEST not in types:
        missing.append("repository test or runtime reproduction")
    if "interprocedural_promotion_gate_not_met" in blockers:
        missing.append("resolved caller dereference without null-check")
    if EVIDENCE_PROMOTION_ENABLED is False:
        missing.append("evidence promotion gate disabled")
    return missing


def _evaluate_status(
    atoms: Sequence[Dict[str, Any]],
    blockers: Sequence[str],
) -> str:
    if any(a.get("polarity") == POLARITY_REFUTES and a.get("strength") in (E2, E3, E4) for a in atoms):
        return STATUS_REFUTED
    if blockers and not atoms:
        return STATUS_BLOCKED
    if not atoms:
        return STATUS_UNKNOWN
    if EVIDENCE_PROMOTION_ENABLED:
        has_violation = any(a.get("evidence_type") == EVIDENCE_CONTRACT_VIOLATION for a in atoms)
        has_path = any(
            a.get("evidence_type") == EVIDENCE_PATH_FEASIBILITY
            and a.get("provenance", {}).get("path_status") == "feasible"
            for a in atoms
        )
        if has_violation and has_path and not blockers:
            return STATUS_PROMOTION_CANDIDATE
    if blockers:
        return STATUS_BLOCKED if len(blockers) >= 2 else STATUS_ENRICHED_LEAD
    return STATUS_ENRICHED_LEAD


def promotion_candidate_basis(
    atoms: Sequence[Dict[str, Any]],
    blockers: Sequence[str],
) -> bool:
    """True when contract violation + feasible path exist with no overlay blockers (C1 basis)."""
    if blockers:
        return False
    has_violation = any(a.get("evidence_type") == EVIDENCE_CONTRACT_VIOLATION for a in atoms)
    has_path = any(
        a.get("evidence_type") == EVIDENCE_PATH_FEASIBILITY
        and a.get("provenance", {}).get("path_status") == "feasible"
        for a in atoms
    )
    return bool(has_violation and has_path)


def _build_impact_context(
    module_facts: Dict[str, Any],
    qual: str,
) -> Dict[str, Any]:
    """Resolved consuming context from existing interprocedural usage facts (Phase 94B scope)."""
    usage = _caller_usage(module_facts, qual)
    blockers: List[str] = []
    contexts: List[Dict[str, Any]] = []
    resolved = False
    if usage.get("dereferenced") and not usage.get("null_checked"):
        resolved = True
        contexts.append(
            {
                "qualname": qual,
                "relationship": "dereferenced_without_null_check",
                "resolution": "resolved",
            }
        )
    elif not usage.get("dereferenced"):
        blockers.append("no_resolved_consuming_context")
    if usage.get("unresolved_callers"):
        blockers.append("unresolved_callers_on_consuming_edge")
    return {
        "resolved": resolved,
        "consuming_contexts": contexts,
        "caller_usage": dict(usage),
        "blockers": sorted(set(blockers)),
    }


def _partition_atoms(atoms: Sequence[Dict[str, Any]]) -> Tuple[List[Dict], List[Dict]]:
    supporting = [a for a in atoms if a.get("polarity") in (POLARITY_SUPPORTS, POLARITY_LIMITS)]
    refuting = [a for a in atoms if a.get("polarity") == POLARITY_REFUTES]
    return supporting, refuting


def _build_overlay(
    finding: Finding,
    module_facts: Dict[str, Any],
    *,
    test_documents: Optional[Sequence[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    qual = _qualname_for_finding(module_facts, finding)
    subject_file = finding.file
    docs = list(test_documents or module_facts.get("test_documents") or [])

    atoms: List[Dict[str, Any]] = []
    blockers: List[str] = []

    atoms.extend(_extract_test_evidence(qual, subject_file, docs))
    atoms.extend(_extract_assertion_evidence(module_facts, qual, subject_file, finding.line))

    violation_atoms, violation_blockers = _extract_contract_violation_evidence(
        finding, module_facts, qual, subject_file
    )
    atoms.extend(violation_atoms)
    blockers.extend(violation_blockers)

    path_atoms, path_blockers = _extract_path_feasibility_evidence(
        finding, module_facts, qual, subject_file
    )
    atoms.extend(path_atoms)
    blockers.extend(path_blockers)

    atoms.extend(_extract_runtime_evidence(module_facts, qual))

    # deterministic ordering
    atoms.sort(key=lambda a: (a.get("evidence_type", ""), a.get("evidence_id", "")))
    blockers = sorted(set(blockers))
    promotion_basis = promotion_candidate_basis(atoms, blockers)
    impact_context = _build_impact_context(module_facts, qual)

    supporting, refuting = _partition_atoms(atoms)
    status = _evaluate_status(atoms, blockers)
    if status == STATUS_PROMOTION_CANDIDATE and not EVIDENCE_PROMOTION_ENABLED:
        status = STATUS_ENRICHED_LEAD
        blockers = sorted(set(blockers + ["promotion_candidate_output_disabled"]))

    return {
        "schema_version": SCHEMA_VERSION,
        "finding_id": finding.id,
        "status": status,
        "promotion_candidate_basis": promotion_basis,
        "review_packet_status": REVIEW_LEAD_TAG,
        "atoms": atoms,
        "bundle": _bundle_indices(atoms),
        "blockers": blockers,
        "supporting_evidence": supporting,
        "refuting_evidence": refuting,
        "missing_proof_obligations": _missing_obligations(atoms, blockers),
        "impact_context": impact_context,
        "why_not_confirmed": [
            "Verification evidence is supporting context only in Phase 97A.",
            "This finding remains review_lead_only — not a confirmed defect.",
            "Evidence promotion and confirmed-defect output are disabled.",
        ],
    }


def enrich_inconsistent_return_finding(
    finding: Finding,
    module_facts: Dict[str, Any],
    *,
    test_documents: Optional[Sequence[Dict[str, str]]] = None,
) -> Finding:
    if finding.rule != "inconsistent_return":
        return finding
    overlay = _build_overlay(finding, module_facts, test_documents=test_documents)
    tags = list(finding.tags)
    if REVIEW_LEAD_TAG not in tags:
        tags.append(REVIEW_LEAD_TAG)
    tags = [t for t in tags if t not in ("confirmed_bug", "confirmed_defect", "confirmed_actionable")]
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
        verification_evidence=overlay,
    )


def enrich_findings(
    findings: List[Finding],
    module_facts: Dict[str, Any],
    *,
    test_documents: Optional[Sequence[Dict[str, str]]] = None,
) -> List[Finding]:
    if not VERIFICATION_EVIDENCE_ENABLED:
        return findings
    return [
        enrich_inconsistent_return_finding(f, module_facts, test_documents=test_documents)
        if f.rule == "inconsistent_return"
        else f
        for f in findings
    ]
