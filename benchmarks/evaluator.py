"""Phase 130 — Score Atlas outputs against benchmark ground truth."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from .schema import (
    BenchmarkScenario,
    EvidenceAuditItem,
    FailureRecord,
    ScenarioMetrics,
    ScenarioResult,
)


def _norm(path: str) -> str:
    return (path or "").replace("\\", "/").lower().strip()


def _path_matches(candidate: str, patterns: Iterable[str]) -> bool:
    c = _norm(candidate)
    for pat in patterns:
        p = _norm(pat)
        if not p:
            continue
        if p in c or c.endswith(p) or c.split("/")[-1] == p.split("/")[-1]:
            return True
    return False


def _match_count(items: Iterable[str], patterns: Iterable[str]) -> int:
    pats = list(patterns)
    if not pats:
        return 0
    return sum(1 for pat in pats if any(_path_matches(item, [pat]) for item in items))


def _collect_recommended_files(plan: Dict[str, Any]) -> List[str]:
    files: List[str] = []
    for key in (
        "files_to_inspect_first",
        "files_likely_to_change",
        "likely_affected_modules",
        "inspect_first",
        "likely_modules",
        "suggested_files_to_inspect",
    ):
        files.extend(plan.get(key) or [])
    dk = plan.get("domain_knowledge") or {}
    roles = dk.get("file_roles") or {}
    for role_key in ("must_inspect", "likely_modify", "verify_only"):
        files.extend(roles.get(role_key) or [])
    rev = plan.get("repository_evidence") or dk.get("repository_evidence") or {}
    if rev.get("recommended_insertion"):
        files.append(rev["recommended_insertion"])
    for fe in rev.get("file_evidences") or []:
        if fe.get("path"):
            files.append(fe["path"])
    sim = plan.get("simulation") or {}
    files.extend(sim.get("potentially_affected_modules") or [])
    if plan.get("target"):
        files.append(plan["target"])
    # dedupe preserve order
    seen: Set[str] = set()
    out: List[str] = []
    for f in files:
        n = _norm(f)
        if n and n not in seen:
            seen.add(n)
            out.append(f.replace("\\", "/"))
    return out


def _collect_risks(plan: Dict[str, Any]) -> List[str]:
    risks: List[str] = []
    risks.extend(plan.get("architectural_risks") or [])
    risks.extend(plan.get("risks_of_incorrect_fix") or [])
    dk = plan.get("domain_knowledge") or {}
    risks.extend(dk.get("risks") or dk.get("knowledge_risks") or [])
    return [str(r) for r in risks]


def _collect_tests(plan: Dict[str, Any]) -> List[str]:
    tests: List[str] = []
    for key in ("tests_likely_affected", "tests_required", "recommended_tests"):
        tests.extend(plan.get(key) or [])
    sim = plan.get("simulation") or {}
    tests.extend(sim.get("tests_likely_affected") or [])
    return [str(t) for t in tests]


def _collect_findings(plan: Dict[str, Any]) -> List[str]:
    findings: List[str] = []
    rev = plan.get("repository_evidence") or {}
    findings.extend(rev.get("found") or [])
    for hyp in plan.get("hypotheses") or []:
        findings.append(hyp.get("title") or "")
        findings.extend(hyp.get("evidence") or [])
    findings.extend(plan.get("evidence") or [])
    if plan.get("most_likely_root_cause"):
        findings.append(plan["most_likely_root_cause"])
    return [f for f in findings if f]


def _text_recall(actual: Iterable[str], expected: Iterable[str]) -> float:
    expected = [e for e in expected if e]
    if not expected:
        return 1.0
    blob = " ".join(actual).lower()
    hits = sum(1 for e in expected if e.lower() in blob)
    return hits / len(expected)


def _file_precision(recommended: List[str], expected: List[str]) -> float:
    if not recommended:
        return 0.0
    hits = sum(1 for r in recommended if _path_matches(r, expected))
    return hits / len(recommended)


def _file_recall(recommended: List[str], expected: List[str]) -> float:
    if not expected:
        return 1.0
    hits = sum(1 for e in expected if any(_path_matches(r, [e]) for r in recommended))
    return hits / len(expected)


def _insertion_correct(actual: str, expected: List[str]) -> bool:
    if not expected:
        return True
    if not actual:
        return False
    return _path_matches(actual, expected)


def _evidence_accuracy(plan: Dict[str, Any], scenario: BenchmarkScenario) -> float:
    rev = plan.get("repository_evidence") or (plan.get("domain_knowledge") or {}).get("repository_evidence") or {}
    if not rev:
        return 0.0
    score = float(rev.get("confidence_score") or 0) / 100.0
    found_blob = " ".join(rev.get("found") or []).lower()
    finding_hits = sum(1 for f in scenario.expected_findings if f.lower() in found_blob)
    finding_part = finding_hits / max(1, len(scenario.expected_findings)) if scenario.expected_findings else 0.5
    file_evidences = rev.get("file_evidences") or []
    symbol_part = 0.0
    if file_evidences:
        sym_blob = " ".join(
            s for fe in file_evidences for s in (fe.get("matching_symbols") or [])
        ).lower()
        symbol_part = min(1.0, len(sym_blob) / 40.0)
    return min(1.0, 0.4 * score + 0.35 * finding_part + 0.25 * symbol_part)


def _audit_evidence(scenario: BenchmarkScenario, plan: Dict[str, Any]) -> Tuple[List[EvidenceAuditItem], List[FailureRecord]]:
    audits: List[EvidenceAuditItem] = []
    failures: List[FailureRecord] = []
    rev = plan.get("repository_evidence") or {}
    if not rev:
        return audits, failures

    conf = float(rev.get("confidence_score") or 0)
    file_evidences = rev.get("file_evidences") or []
    found = rev.get("found") or []
    missing = rev.get("missing") or []
    insertion = rev.get("recommended_insertion") or ""

    if conf >= 70 and len(file_evidences) == 0 and not found:
        audits.append(
            EvidenceAuditItem(
                scenario.scenario_id,
                "high_confidence_weak_evidence",
                f"confidence={conf} but no file_evidences or found symbols",
            )
        )

    if conf <= 35 and (file_evidences or len(found) >= 2):
        audits.append(
            EvidenceAuditItem(
                scenario.scenario_id,
                "low_confidence_strong_evidence",
                f"confidence={conf} with {len(file_evidences)} file evidences",
            )
        )

    if found and missing and any(f.lower() in " ".join(missing).lower() for f in found):
        audits.append(
            EvidenceAuditItem(
                scenario.scenario_id,
                "evidence_contradiction",
                "found and missing lists overlap semantically",
            )
        )

    if insertion and scenario.expected_insertion_points and not _insertion_correct(insertion, scenario.expected_insertion_points):
        audits.append(
            EvidenceAuditItem(
                scenario.scenario_id,
                "incorrect_insertion_point",
                f"got `{insertion}` expected one of {scenario.expected_insertion_points}",
            )
        )
        failures.append(
            FailureRecord(
                scenario_id=scenario.scenario_id,
                reason="Incorrect insertion point",
                evidence_used=found[:6],
                expected_evidence=scenario.expected_findings[:6],
                missing_evidence=missing[:6],
            )
        )

    return audits, failures


def _score_breakdown(
    scenario: BenchmarkScenario,
    metrics: ScenarioMetrics,
) -> None:
    repo = (metrics.file_precision + metrics.file_recall) / 2.0
    if metrics.insertion_point_correct:
        repo = min(1.0, repo + 0.15)
    metrics.repository_understanding = round(repo * 100, 1)

    metrics.knowledge_understanding = round(100.0 if metrics.knowledge_correct else 0.0, 1)
    metrics.evidence_quality = round(metrics.evidence_accuracy * 100, 1)
    metrics.investigation_quality = round(
        (metrics.finding_recall * 0.6 + metrics.file_recall * 0.4) * 100, 1
    )
    metrics.impact_analysis_quality = round(
        (metrics.file_recall * 0.5 + metrics.risk_recall * 0.3 + metrics.test_recall * 0.2) * 100, 1
    )

    if scenario.category == "feature_addition":
        metrics.atlas_score = round(
            metrics.repository_understanding * 0.30
            + metrics.knowledge_understanding * 0.15
            + metrics.evidence_quality * 0.25
            + metrics.risk_recall * 100 * 0.10
            + metrics.test_recall * 100 * 0.10
            + (100.0 if metrics.insertion_point_correct else 0.0) * 0.10,
            1,
        )
    elif scenario.category == "bug_investigation":
        metrics.atlas_score = round(
            metrics.investigation_quality * 0.30
            + metrics.evidence_quality * 0.25
            + metrics.knowledge_understanding * 0.15
            + metrics.repository_understanding * 0.20
            + metrics.risk_recall * 100 * 0.10,
            1,
        )
    else:
        metrics.atlas_score = round(
            metrics.impact_analysis_quality * 0.40
            + metrics.repository_understanding * 0.25
            + metrics.risk_recall * 100 * 0.20
            + metrics.test_recall * 100 * 0.15,
            1,
        )


def evaluate_scenario(scenario: BenchmarkScenario, plan: Dict[str, Any], *, ok: bool = True, error: str = "") -> ScenarioResult:
    recommended = _collect_recommended_files(plan)
    actual_concept = (plan.get("domain_knowledge") or {}).get("concept_id") or plan.get("intent") or ""
    rev = plan.get("repository_evidence") or (plan.get("domain_knowledge") or {}).get("repository_evidence") or {}
    actual_insertion = rev.get("recommended_insertion") or (recommended[0] if recommended else "")
    actual_findings = _collect_findings(plan)

    metrics = ScenarioMetrics(
        file_precision=_file_precision(recommended, scenario.expected_files),
        file_recall=_file_recall(recommended, scenario.expected_files),
        insertion_point_correct=_insertion_correct(actual_insertion, scenario.expected_insertion_points),
        knowledge_correct=bool(
            not scenario.expected_concept_id
            or scenario.expected_concept_id == actual_concept
            or scenario.expected_concept_id in actual_concept
        ),
        evidence_accuracy=_evidence_accuracy(plan, scenario),
        risk_recall=_text_recall(_collect_risks(plan), scenario.expected_risks),
        test_recall=_text_recall(_collect_tests(plan), scenario.expected_tests),
        finding_recall=_text_recall(actual_findings, scenario.expected_findings),
    )
    _score_breakdown(scenario, metrics)

    audits, failures = _audit_evidence(scenario, plan)

    if metrics.file_recall < 0.5 and scenario.expected_files:
        failures.append(
            FailureRecord(
                scenario_id=scenario.scenario_id,
                reason="Low file recall",
                evidence_used=recommended[:8],
                expected_evidence=scenario.expected_files,
                missing_evidence=[e for e in scenario.expected_files if not any(_path_matches(r, [e]) for r in recommended)],
            )
        )
    if scenario.expected_concept_id and not metrics.knowledge_correct:
        failures.append(
            FailureRecord(
                scenario_id=scenario.scenario_id,
                reason="Wrong concept identified",
                evidence_used=[actual_concept],
                expected_evidence=[scenario.expected_concept_id],
                missing_evidence=[scenario.expected_concept_id],
            )
        )

    return ScenarioResult(
        scenario=scenario,
        ok=ok and not error,
        metrics=metrics,
        recommended_files=recommended,
        actual_concept_id=actual_concept,
        actual_insertion=actual_insertion,
        actual_findings=actual_findings,
        failures=failures,
        evidence_audits=audits,
        error=error,
    )
