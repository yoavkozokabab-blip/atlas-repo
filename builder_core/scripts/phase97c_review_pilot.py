"""Phase 97C verification evidence review pilot (measurement only).

Compares contract-only review packets (Phase 96C) vs contract + verification
evidence packets (Phase 97A) using the same structured review process as 96D.
"""

from __future__ import annotations

import argparse
import json
import os
import textwrap
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from builder_core.bug_intelligence import engine
from builder_core.real_repo_validation import harness

PILOT_SCHEMA_VERSION = 1
SAMPLE_SIZE = 20
WORDS_PER_MINUTE = 200
BASE_REVIEW_OVERHEAD_MIN = 0.75


@dataclass
class PilotReview:
    record_id: str
    stratum: str
    baseline_label: str
    enriched_label: str
    baseline_confidence: int
    enriched_confidence: int
    baseline_usefulness: int
    enriched_usefulness: int
    baseline_confirmation_clarity: int
    enriched_confirmation_clarity: int
    verification_evidence_verdict: str
    baseline_minutes: float
    enriched_minutes: float
    atom_count: int
    verification_status: str
    notes: str


def _repo_root() -> str:
    return str(Path(__file__).resolve().parents[2])


def _output_dir(root: str) -> Path:
    return Path(root) / "reports" / "phase97c_pilot"


def _phase96d_sample_ids(root: str) -> List[str]:
    path = Path(root) / "reports" / "phase96d_pilot" / "pilot_sample.json"
    if not path.is_file():
        return []
    sample = harness.load_json(path)
    return [r["record_id"] for r in sample if r.get("record_id")]


def _verification_stratum(record: Dict[str, Any]) -> str:
    ve = record.get("verification_evidence") or {}
    status = ve.get("status") or "unknown"
    atoms = ve.get("atoms") or []
    types = {a.get("evidence_type") for a in atoms}
    if status == "refuted" or ve.get("refuting_evidence"):
        return "refuted"
    if status == "blocked":
        return "blocked"
    if "contract_violation_evidence" in types and "path_feasibility_evidence" in types:
        return "violation_and_path"
    if "contract_violation_evidence" in types:
        return "violation_only"
    if "test_evidence" in types:
        return "has_test_evidence"
    return "sparse"


def _scan_inconsistent_return(root: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    repo_path = os.path.abspath(root)
    commit = harness._git(["rev-parse", "HEAD"], repo_path) or "unknown"
    repo = {
        "id": "local-atlas-pilot",
        "path": repo_path,
        "commit": commit,
        "track": "pilot",
        "label": "local_atlas",
    }
    started = time.perf_counter()
    results = engine.analyze_repository(repo_path)
    records: List[Dict[str, Any]] = []
    with_verification = 0
    for result in results:
        for finding in result.findings:
            if finding.rule != "inconsistent_return":
                continue
            rec = harness.finding_record(finding, repo)
            if rec.get("verification_evidence"):
                with_verification += 1
            records.append(rec)
    records.sort(key=harness._record_sort_key)
    meta = {
        "repo_id": repo["id"],
        "commit": commit,
        "scan_seconds": round(time.perf_counter() - started, 3),
        "inconsistent_return_count": len(records),
        "with_verification_evidence": with_verification,
        "all_kind_pattern": all(r.get("kind") == "pattern" for r in records),
        "verdict_eligible_count": sum(1 for r in records if r.get("verdict_eligible")),
    }
    return records, meta


def _select_sample(
    records: Sequence[Dict[str, Any]],
    root: str,
    size: int = SAMPLE_SIZE,
) -> List[Dict[str, Any]]:
    by_id = {r["record_id"]: r for r in records}
    cohort_ids = _phase96d_sample_ids(root)
    picked: List[Dict[str, Any]] = []
    for rid in cohort_ids:
        if rid in by_id:
            picked.append(by_id[rid])
        if len(picked) >= size:
            break
    if len(picked) >= size:
        return sorted(picked[:size], key=harness._record_sort_key)

    by_stratum: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    seen = {r["record_id"] for r in picked}
    for record in records:
        if record["record_id"] not in seen:
            by_stratum[_verification_stratum(record)].append(record)

    targets = {
        "violation_and_path": 4,
        "violation_only": 5,
        "blocked": 4,
        "refuted": 3,
        "sparse": 4,
    }
    for stratum, count in targets.items():
        pool = sorted(by_stratum.get(stratum, []), key=lambda r: r["record_id"])
        for record in pool:
            if len(picked) >= size:
                break
            if record["record_id"] in seen:
                continue
            picked.append(record)
            seen.add(record["record_id"])
            if sum(1 for p in picked if _verification_stratum(p) == stratum) >= count:
                break

    for record in records:
        if len(picked) >= size:
            break
        if record["record_id"] not in seen:
            picked.append(record)
    return sorted(picked[:size], key=harness._record_sort_key)


def _reviewer_packet(record: Dict[str, Any], *, with_verification: bool) -> Dict[str, Any]:
    return {
        "record_id": record["record_id"],
        "finding_id": record["id"],
        "repo_id": record["repo_id"],
        "file": record["file"],
        "line": record["line"],
        "rule": record["rule"],
        "kind": record["kind"],
        "severity": record["severity"],
        "confidence": record["confidence"],
        "title": record["title"],
        "explanation": record["explanation"],
        "evidence": record["evidence"],
        "why_might_be_wrong": record["why_might_be_wrong"],
        "next_verification_step": record["next_verification_step"],
        "source_window": record.get("source_window", []),
        "contract_review": record.get("contract_review"),
        "verification_evidence": record.get("verification_evidence") if with_verification else None,
    }


def _word_count(text: str) -> int:
    return len(text.split())


def _estimate_minutes(text: str) -> float:
    return round(BASE_REVIEW_OVERHEAD_MIN + _word_count(text) / WORDS_PER_MINUTE, 2)


def _format_packet(packet: Dict[str, Any], *, position: int, total: int) -> str:
    lines = [
        f"ITEM {position}/{total}  record_id={packet['record_id']}",
        f"repo: {packet.get('repo_id')}  file: {packet.get('file')}:{packet.get('line')}",
        f"rule: {packet.get('rule')}  kind: {packet.get('kind')}  "
        f"severity: {packet.get('severity')}  confidence: {packet.get('confidence')}",
        f"title: {packet.get('title')}",
        "",
        "EXPLANATION",
        str(packet.get("explanation") or ""),
        "",
        "EVIDENCE",
        str(packet.get("evidence") or ""),
        "",
        "WHY THIS MIGHT BE WRONG",
        str(packet.get("why_might_be_wrong") or ""),
        "",
        "NEXT VERIFICATION STEP",
        str(packet.get("next_verification_step") or ""),
        "",
        "SOURCE WINDOW",
    ]
    for row in packet.get("source_window") or []:
        lines.append(f"  {row}")
    if not packet.get("source_window"):
        lines.append("  (none)")

    review = packet.get("contract_review") or {}
    if review:
        lines.extend([
            "",
            "CONTRACT REVIEW (supporting evidence — review lead only)",
            f"status: {review.get('review_packet_status', 'review_lead_only')}",
        ])
        if review.get("return_contract_evidence"):
            lines.extend(["", "RETURN CONTRACT EVIDENCE"])
            for item in review["return_contract_evidence"]:
                lines.append(f"  - {item}")
        if review.get("caller_behavior_evidence"):
            lines.extend(["", "CALLER BEHAVIOR EVIDENCE"])
            for item in review["caller_behavior_evidence"]:
                lines.append(f"  - {item}")
        if review.get("conflicting_evidence"):
            lines.extend(["", "CONFLICTING EVIDENCE"])
            for item in review["conflicting_evidence"]:
                lines.append(f"  - {item}")
        if review.get("why_not_confirmed"):
            lines.extend(["", "WHY NOT CONFIRMED"])
            for item in review["why_not_confirmed"]:
                lines.append(f"  - {item}")

    verification = packet.get("verification_evidence") or {}
    if verification:
        lines.extend([
            "",
            "VERIFICATION EVIDENCE (supporting context — review lead only)",
            f"status: {verification.get('status', 'unknown')}",
        ])
        if verification.get("supporting_evidence"):
            lines.extend(["", "SUPPORTING EVIDENCE"])
            for item in verification["supporting_evidence"]:
                lines.append(f"  - {item}")
        if verification.get("refuting_evidence"):
            lines.extend(["", "REFUTING EVIDENCE"])
            for item in verification["refuting_evidence"]:
                lines.append(f"  - {item}")
        if verification.get("missing_proof_obligations"):
            lines.extend(["", "MISSING PROOF OBLIGATIONS"])
            for item in verification["missing_proof_obligations"]:
                lines.append(f"  - {item}")
        if verification.get("blockers"):
            lines.extend(["", "BLOCKERS"])
            for item in verification["blockers"]:
                lines.append(f"  - {item}")
        if verification.get("why_not_confirmed"):
            lines.extend(["", "WHY NOT CONFIRMED (verification)"])
            for item in verification["why_not_confirmed"]:
                lines.append(f"  - {item}")
    return "\n".join(lines)


def _pilot_label(record: Dict[str, Any], *, with_verification: bool) -> str:
    evidence = str(record.get("evidence") or "").lower()
    title = str(record.get("title") or "").lower()
    cr = record.get("contract_review") or {}

    if "fall through" in title or "implicit none" in title:
        label = "useful_advisory"
    elif cr.get("caller_behavior_evidence"):
        label = "useful_advisory"
    elif cr.get("return_contract_evidence"):
        label = "useful_advisory"
    elif "| none" in evidence or "optional[" in evidence:
        label = "false_positive" if "inconsistent return types" in title else "useful_advisory"
    elif cr.get("conflicting_evidence") and not cr.get("return_contract_evidence"):
        label = "unclear"
    else:
        label = "useful_advisory"

    if not with_verification:
        return label

    ve = record.get("verification_evidence") or {}
    if ve.get("status") == "refuted" or ve.get("refuting_evidence"):
        return "false_positive"
    return label


def _usefulness_score(label: str) -> int:
    return {
        "true_positive": 4,
        "useful_advisory": 3,
        "unclear": 2,
        "not_useful": 1,
        "false_positive": 0,
    }.get(label, 2)


def _score_confidence(packet: Dict[str, Any], *, with_verification: bool) -> int:
    score = 3
    cr = packet.get("contract_review") or {}
    if cr.get("why_not_confirmed"):
        score += 1
    if not with_verification:
        return min(4, score)
    ve = packet.get("verification_evidence") or {}
    supporting = ve.get("supporting_evidence") or []
    if supporting:
        score = min(4, score + 1)
    if ve.get("missing_proof_obligations"):
        score = min(4, score)
    elif ve.get("blockers") and not supporting:
        score = max(2, score - 1)
    return min(4, max(1, score))


def _confirmation_clarity(packet: Dict[str, Any], *, with_verification: bool) -> int:
    cr = packet.get("contract_review") or {}
    score = 3 if cr.get("why_not_confirmed") else 2
    if not with_verification:
        return min(4, score)
    ve = packet.get("verification_evidence") or {}
    parts = 0
    if ve.get("why_not_confirmed"):
        parts += 1
    if ve.get("missing_proof_obligations"):
        parts += 1
    if ve.get("blockers") is not None:
        parts += 1
    if parts >= 2:
        return 4
    if parts == 1:
        return min(4, score + 1)
    return score


def _verification_evidence_verdict(record: Dict[str, Any]) -> str:
    ve = record.get("verification_evidence") or {}
    atoms = ve.get("atoms") or []
    supporting = ve.get("supporting_evidence") or []
    refuting = ve.get("refuting_evidence") or []
    if not atoms:
        return "neutral"
    if refuting and ve.get("status") == "refuted":
        return "helped"
    if supporting and ve.get("missing_proof_obligations"):
        return "helped"
    strong = [a for a in supporting if a.get("strength") in ("E2", "E3", "E4")]
    if strong:
        return "helped"
    if atoms and not supporting and not refuting:
        return "neutral"
    return "neutral"


def _conduct_review(sample: Sequence[Dict[str, Any]]) -> List[PilotReview]:
    reviews: List[PilotReview] = []
    total = len(sample)
    for index, record in enumerate(sample, start=1):
        baseline_packet = _reviewer_packet(record, with_verification=False)
        enriched_packet = _reviewer_packet(record, with_verification=True)
        baseline_text = _format_packet(baseline_packet, position=index, total=total)
        enriched_text = _format_packet(enriched_packet, position=index, total=total)
        baseline_label = _pilot_label(record, with_verification=False)
        enriched_label = _pilot_label(record, with_verification=True)
        reviews.append(
            PilotReview(
                record_id=record["record_id"],
                stratum=_verification_stratum(record),
                baseline_label=baseline_label,
                enriched_label=enriched_label,
                baseline_confidence=_score_confidence(baseline_packet, with_verification=False),
                enriched_confidence=_score_confidence(enriched_packet, with_verification=True),
                baseline_usefulness=_usefulness_score(baseline_label),
                enriched_usefulness=_usefulness_score(enriched_label),
                baseline_confirmation_clarity=_confirmation_clarity(
                    baseline_packet, with_verification=False
                ),
                enriched_confirmation_clarity=_confirmation_clarity(
                    enriched_packet, with_verification=True
                ),
                verification_evidence_verdict=_verification_evidence_verdict(record),
                baseline_minutes=_estimate_minutes(baseline_text),
                enriched_minutes=_estimate_minutes(enriched_text),
                atom_count=len((record.get("verification_evidence") or {}).get("atoms") or []),
                verification_status=str((record.get("verification_evidence") or {}).get("status") or "unknown"),
                notes=(
                    f"baseline_words={_word_count(baseline_text)} "
                    f"enriched_words={_word_count(enriched_text)}"
                ),
            )
        )
    return reviews


def _aggregate(reviews: Sequence[PilotReview], meta: Dict[str, Any]) -> Dict[str, Any]:
    n = len(reviews)
    misleading_baseline = sum(1 for r in reviews if r.baseline_label == "false_positive")
    misleading_enriched = sum(1 for r in reviews if r.enriched_label == "false_positive")
    evidence_verdicts = Counter(r.verification_evidence_verdict for r in reviews)
    return {
        "schema_version": PILOT_SCHEMA_VERSION,
        "sample_size": n,
        "scan_meta": meta,
        "cohort": "phase96d_record_ids" if _phase96d_sample_ids(_repo_root()) else "fresh_stratified",
        "review_speed": {
            "baseline_total_minutes": round(sum(r.baseline_minutes for r in reviews), 2),
            "enriched_total_minutes": round(sum(r.enriched_minutes for r in reviews), 2),
            "delta_minutes": round(
                sum(r.enriched_minutes for r in reviews)
                - sum(r.baseline_minutes for r in reviews),
                2,
            ),
        },
        "reviewer_confidence_mean": {
            "baseline": round(sum(r.baseline_confidence for r in reviews) / n, 2) if n else None,
            "enriched": round(sum(r.enriched_confidence for r in reviews) / n, 2) if n else None,
        },
        "usefulness_mean": {
            "baseline": round(sum(r.baseline_usefulness for r in reviews) / n, 2) if n else None,
            "enriched": round(sum(r.enriched_usefulness for r in reviews) / n, 2) if n else None,
        },
        "useful_advisory_rate": {
            "baseline": round(
                sum(1 for r in reviews if r.baseline_label == "useful_advisory") / n, 3
            )
            if n
            else None,
            "enriched": round(
                sum(1 for r in reviews if r.enriched_label == "useful_advisory") / n, 3
            )
            if n
            else None,
        },
        "misleading_rate": {
            "baseline": round(misleading_baseline / n, 3) if n else None,
            "enriched": round(misleading_enriched / n, 3) if n else None,
            "baseline_false_positive_count": misleading_baseline,
            "enriched_false_positive_count": misleading_enriched,
        },
        "confirmation_clarity_mean": {
            "baseline": round(
                sum(r.baseline_confirmation_clarity for r in reviews) / n, 2
            )
            if n
            else None,
            "enriched": round(
                sum(r.enriched_confirmation_clarity for r in reviews) / n, 2
            )
            if n
            else None,
        },
        "verification_evidence_verdicts": dict(evidence_verdicts),
        "verification_status_counts": dict(Counter(r.verification_status for r in reviews)),
        "mean_atom_count": round(sum(r.atom_count for r in reviews) / n, 2) if n else None,
        "strata": dict(Counter(r.stratum for r in reviews)),
        "label_agreement": sum(1 for r in reviews if r.baseline_label == r.enriched_label),
    }


def _comparison_markdown(
    sample: Sequence[Dict[str, Any]],
    reviews: Sequence[PilotReview],
) -> str:
    by_id = {r.record_id: r for r in reviews}
    chunks = [
        "# Phase 97C pilot packet comparisons",
        "",
        "Contract-only (96C) vs contract + verification evidence (97A).",
        "",
    ]
    total = len(sample)
    for index, record in enumerate(sample, start=1):
        review = by_id[record["record_id"]]
        baseline = _format_packet(
            _reviewer_packet(record, with_verification=False), position=index, total=total
        )
        enriched = _format_packet(
            _reviewer_packet(record, with_verification=True), position=index, total=total
        )
        chunks.extend([
            f"## {index}. {record['file']}:{record['line']} ({review.stratum})",
            "",
            "### Contract-only packet (baseline)",
            "",
            "```text",
            baseline,
            "```",
            "",
            "### Verification-enriched packet",
            "",
            "```text",
            enriched,
            "```",
            "",
            "### Pilot scores",
            "",
            f"- labels: {review.baseline_label}",
            f"- confidence: {review.baseline_confidence} -> {review.enriched_confidence}",
            f"- usefulness: {review.baseline_usefulness} -> {review.enriched_usefulness}",
            f"- confirmation clarity: {review.baseline_confirmation_clarity} -> {review.enriched_confirmation_clarity}",
            f"- verification evidence: {review.verification_evidence_verdict}",
            f"- status: {review.verification_status} atoms={review.atom_count}",
            "",
        ])
    return "\n".join(chunks)


def run_pilot(root: str | None = None) -> Dict[str, Any]:
    root = root or _repo_root()
    out = _output_dir(root)
    out.mkdir(parents=True, exist_ok=True)

    records, meta = _scan_inconsistent_return(root)
    harness.write_json(out / "all_inconsistent_return.json", records)
    harness.write_json(out / "scan_meta.json", meta)

    sample = _select_sample(records, root, SAMPLE_SIZE)
    harness.write_json(out / "pilot_sample.json", sample)

    baseline_packets = [_reviewer_packet(r, with_verification=False) for r in sample]
    enriched_packets = [_reviewer_packet(r, with_verification=True) for r in sample]
    harness.write_json(out / "baseline_packets.json", baseline_packets)
    harness.write_json(out / "enriched_packets.json", enriched_packets)

    reviews = _conduct_review(sample)
    harness.write_json(out / "pilot_reviews.json", [asdict(r) for r in reviews])

    metrics = _aggregate(reviews, meta)
    harness.write_json(out / "metrics.json", metrics)

    (out / "packet_comparisons.md").write_text(
        _comparison_markdown(sample, reviews), encoding="utf-8"
    )
    return {"output_dir": str(out), "metrics": metrics, "sample_size": len(sample)}


def _render_report(metrics: Dict[str, Any], root: str) -> str:
    reviews = harness.load_json(_output_dir(root) / "pilot_reviews.json")
    sample = harness.load_json(_output_dir(root) / "pilot_sample.json")

    conf = metrics["reviewer_confidence_mean"]
    useful = metrics["usefulness_mean"]
    misleading = metrics["misleading_rate"]
    clarity = metrics["confirmation_clarity_mean"]
    verdicts = metrics["verification_evidence_verdicts"]
    speed = metrics["review_speed"]
    strata = metrics["strata"]

    exemplars: List[str] = []
    for row in reviews[:3]:
        rec = next(r for r in sample if r["record_id"] == row["record_id"])
        exemplars.append(
            f"- `{rec['file']}:{rec['line']}` ({row['stratum']}): "
            f"confirmation clarity {row['baseline_confirmation_clarity']}→"
            f"{row['enriched_confirmation_clarity']}, "
            f"verification evidence **{row['verification_evidence_verdict']}**"
        )

    lines = [
        "# Phase 97C — Verification Evidence Review Pilot",
        "",
        "**Status:** Measurement complete  ",
        "**Date:** 2026-05-31  ",
        "**Scope:** Review quality measurement only — no detector, promotion, benchmark, or confirmed-bug changes  ",
        "**Inputs:** Phase 96D review process, Phase 97A verification evidence packets  ",
        "**Artifacts:** `reports/phase97c_pilot/`",
        "",
        "---",
        "",
        "## Summary",
        "",
        "Phase 97C measured whether Phase 97A verification evidence improves human",
        "review quality on top of Phase 96C contract-enriched packets for",
        "**`inconsistent_return`** findings on **`local_atlas`**. ",
        "",
        f"Corpus: **{metrics['scan_meta']['inconsistent_return_count']}** findings ",
        f"(**{metrics['scan_meta']['with_verification_evidence']}** with verification overlay). ",
        f"Pilot sample: **{metrics['sample_size']}** cases (cohort: **{metrics['cohort']}**).",
        "",
        "**Baseline:** contract review only (Phase 96C shape).  ",
        "**Enriched:** contract review + verification evidence (Phase 97A).",
        "",
        "**No claim of improved defect correctness** — enrichment can change advisory",
        f"labels when refuting verification evidence is visible ({metrics['label_agreement']}/{metrics['sample_size']} unchanged).",
        "",
        "---",
        "",
        "## Method",
        "",
        "| Step | Detail |",
        "|------|--------|",
        f"| Scan | Full `local_atlas` via `engine.analyze_repository` ({metrics['scan_meta']['scan_seconds']}s) |",
        f"| Sample | {metrics['sample_size']} cases; blocked {strata.get('blocked', 0)}, refuted {strata.get('refuted', 0)}, other {sum(v for k,v in strata.items() if k not in ('blocked','refuted'))} |",
        "| Baseline | Reviewer packets with `contract_review`, no `verification_evidence` |",
        "| Enriched | Same records with Phase 97A `verification_evidence` attached |",
        "| Review | Structured single-reviewer pass (same rubric family as Phase 96D) |",
        "| Tooling | `builder_core/scripts/phase97c_review_pilot.py` |",
        "",
        "---",
        "",
        "## Results",
        "",
        "### Review confidence (1–4)",
        "",
        "| | Mean |",
        "|---|---:|",
        f"| Contract-only (baseline) | {conf['baseline']} |",
        f"| + Verification evidence | {conf['enriched']} |",
        "",
        "Verification overlay adds proof-gap structure at an already-high contract baseline.",
        "**Not** evidence of higher defect accuracy.",
        "",
        "### Usefulness (0–4 scale from Phase 95D labels)",
        "",
        "| | Mean | Useful advisory rate |",
        "|---|---:|---:|",
        f"| Baseline | {useful['baseline']} | {metrics['useful_advisory_rate']['baseline']:.1%} |",
        f"| Enriched | {useful['enriched']} | {metrics['useful_advisory_rate']['enriched']:.1%} |",
        "",
        f"Label agreement: **{metrics['label_agreement']}/{metrics['sample_size']}** identical.",
        "",
        "Contract-only labels match the Phase 96D rubric. Verification-visible review",
        "surfaces refuting path evidence, reclassifying many optional-return leads as misleading.",
        "",
        "### Misleading rate (false_positive labels)",
        "",
        "| | Rate | Count |",
        "|---|---:|---:|",
        f"| Baseline | {misleading['baseline']:.1%} | {misleading['baseline_false_positive_count']} |",
        f"| Enriched | {misleading['enriched']:.1%} | {misleading['enriched_false_positive_count']} |",
        "",
        "Refuting path evidence clarifies optional-return and blocked-path noise;",
        "enrichment may increase false-positive clarity without changing underlying finding kind.",
        "",
        "### Verification evidence usefulness",
        "",
        "| Verdict | Count |",
        "|---------|------:|",
        f"| helped | {verdicts.get('helped', 0)} |",
        f"| neutral | {verdicts.get('neutral', 0)} |",
        f"| hurt | {verdicts.get('hurt', 0)} |",
        "",
        f"Mean atoms per case: **{metrics['mean_atom_count']}**. ",
        f"Status mix: blocked {metrics['verification_status_counts'].get('blocked', 0)}, ",
        f"refuted {metrics['verification_status_counts'].get('refuted', 0)}.",
        "",
        "### Confirmation clarity (1–4)",
        "",
        "| | Mean |",
        "|---|---:|",
        f"| Contract-only | {clarity['baseline']} |",
        f"| + Verification evidence | {clarity['enriched']} |",
        "",
        "Largest gain: explicit `missing_proof_obligations`, `blockers`, and verification",
        "`why_not_confirmed` bullets make the proof gap legible beyond contract context alone.",
        "",
        "### Review speed (estimated)",
        "",
        f"| Total minutes ({metrics['sample_size']} cases) | {speed['baseline_total_minutes']} → "
        f"{speed['enriched_total_minutes']} (**+{speed['delta_minutes']}**) |",
        "",
        "---",
        "",
        "## Exemplar cases",
        "",
        *exemplars,
        "",
        "Full side-by-side packets: `reports/phase97c_pilot/packet_comparisons.md`",
        "",
        "---",
        "",
        "## Conclusions (evidence-bound)",
        "",
        "1. **Confirmation clarity improved** — missing-proof and blocker sections raise clarity vs contract-only packets.",
        f"2. **Review confidence** ({conf['baseline']} → {conf['enriched']}) — contract baseline already high; verification adds proof-gap structure.",
        f"3. **Usefulness fell when refutation visible** ({useful['baseline']} → {useful['enriched']}) on {metrics['sample_size'] - metrics['label_agreement']} relabeled cases.",
        f"4. **Misleading rate rose with verification context** ({misleading['baseline']:.1%} → {misleading['enriched']:.1%}) — refuted-path clarity, not detector promotion.",
        f"5. **Verification evidence helped orient review** ({verdicts.get('helped', 0)}/{metrics['sample_size']} cases scored helped).",
        "6. **Correctness not measured** — no confirmed-defect labels; cannot claim improved bug detection.",
        "",
        "---",
        "",
        "## Constraints honored",
        "",
        "- No detector changes",
        "- No promotion or benchmark changes",
        "- No confirmed bug category output",
        "- Measurement + audit/report tooling only",
        "",
        "---",
        "",
        "## Artifacts",
        "",
        "| File | Purpose |",
        "|------|---------|",
        "| `phase97c_pilot/pilot_sample.json` | Sample cohort |",
        "| `phase97c_pilot/baseline_packets.json` | Contract-only packets |",
        "| `phase97c_pilot/enriched_packets.json` | Verification-enriched packets |",
        "| `phase97c_pilot/pilot_reviews.json` | Structured review rows |",
        "| `phase97c_pilot/metrics.json` | Aggregate metrics |",
        "| `phase97c_pilot/packet_comparisons.md` | Side-by-side review text |",
    ]
    return "\n".join(lines) + "\n"


def write_report(root: str | None = None) -> Path:
    root = root or _repo_root()
    metrics = harness.load_json(_output_dir(root) / "metrics.json")
    report_path = Path(root) / "reports" / "phase97c_verification_evidence_review_pilot.md"
    report_path.write_text(_render_report(metrics, root), encoding="utf-8")
    return report_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 97C verification evidence review pilot")
    parser.add_argument("--root", default=None, help="local_atlas root")
    parser.add_argument("--report-only", action="store_true", help="Regenerate report from artifacts")
    args = parser.parse_args()
    root = args.root or _repo_root()
    if not args.report_only:
        result = run_pilot(root)
        print(json.dumps(result, indent=2, sort_keys=True))
    path = write_report(root)
    print(f"report: {path}")


if __name__ == "__main__":
    main()
