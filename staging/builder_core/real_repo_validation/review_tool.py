"""Phase 95D human review workflow helpers.

Read-only with respect to target repositories and the analysis engine. Operates on
Phase 95C artifact directories (packets, reviews.json, review_sample.json).
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import harness

REVIEW_TOOL_SCHEMA_VERSION = 1

DECISION_LABELS = frozenset({
    "true_positive",
    "false_positive",
    "unclear",
    "useful_advisory",
    "not_useful",
})

REVIEW_SLOTS = frozenset({"reviewer_a", "reviewer_b", "adjudication"})

LABEL_TO_HARNESS = {
    "true_positive": "confirmed_actionable",
    "false_positive": "misleading",
    "unclear": "undecidable",
    "useful_advisory": "useful_review_lead",
    "not_useful": "benign_or_intended",
}

HARNESS_TO_LABEL = {value: key for key, value in LABEL_TO_HARNESS.items()}

USEFULNESS_FROM_LABEL = {
    "true_positive": 4,
    "useful_advisory": 3,
    "unclear": 2,
    "not_useful": 1,
    "false_positive": 0,
}

_REQUIRED_PACKET_FIELDS = (
    "record_id",
    "repo_id",
    "file",
    "line",
    "rule",
    "kind",
    "severity",
    "confidence",
    "title",
    "explanation",
    "source_window",
)


@dataclass
class RunContext:
    run_dir: Path
    packets: List[Dict[str, Any]]
    review_sample: List[Dict[str, Any]]
    reviews: Dict[str, Any]
    packet_by_id: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    sample_ids: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.packet_by_id = {packet["record_id"]: packet for packet in self.packets}
        self.sample_ids = [record["record_id"] for record in self.review_sample]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def decisions_path(run_dir: Path, slot: str) -> Path:
    return run_dir / f"review_decisions.{slot}.json"


def load_run_context(run_dir: str | Path) -> RunContext:
    root = Path(run_dir).resolve()
    packets_path = root / "reviewer_a_packets.json"
    if not packets_path.is_file():
        raise ValueError(f"missing reviewer packets: {packets_path}")
    for required in ("review_sample.json", "reviews.json"):
        path = root / required
        if not path.is_file():
            raise ValueError(f"missing required artifact: {path}")
    packets = harness.load_json(packets_path)
    if not isinstance(packets, list):
        raise ValueError("reviewer packets must be a JSON list")
    review_sample = harness.load_json(root / "review_sample.json")
    if not isinstance(review_sample, list):
        raise ValueError("review_sample.json must be a JSON list")
    reviews = harness.load_reviews(root / "reviews.json")
    return RunContext(
        run_dir=root,
        packets=packets,
        review_sample=review_sample,
        reviews=reviews,
    )


def _slot_review(context: RunContext, record_id: str, slot: str) -> Dict[str, Any]:
    finding = context.reviews["findings"].get(record_id)
    if not isinstance(finding, dict):
        raise KeyError(f"unknown record_id '{record_id}'")
    review = finding.get(slot)
    if not isinstance(review, dict):
        raise KeyError(f"{record_id} missing slot '{slot}'")
    return review


def _is_reviewed(slot_review: Dict[str, Any]) -> bool:
    return slot_review.get("label") not in (None, "unreviewed")


def _validate_reviewer_name(reviewer: Optional[str]) -> List[str]:
    if reviewer is None or not str(reviewer).strip():
        return ["reviewer name is required (--reviewer)"]
    return []


def validate_packets(context: RunContext) -> List[str]:
    issues: List[str] = []
    packet_ids = set()
    for index, packet in enumerate(context.packets):
        if not isinstance(packet, dict):
            issues.append(f"packet[{index}] must be an object")
            continue
        for field_name in _REQUIRED_PACKET_FIELDS:
            if field_name not in packet:
                issues.append(f"packet[{index}] missing required field '{field_name}'")
        record_id = packet.get("record_id")
        if record_id in packet_ids:
            issues.append(f"duplicate packet record_id '{record_id}'")
        packet_ids.add(record_id)

    sample_ids = {record["record_id"] for record in context.review_sample}
    review_ids = set(context.reviews.get("findings", {}))
    missing_packets = sorted(sample_ids - packet_ids)
    missing_reviews = sorted(sample_ids - review_ids)
    extra_packets = sorted(packet_ids - sample_ids)
    if missing_packets:
        issues.append(f"review sample missing packets: {missing_packets[:5]}")
    if missing_reviews:
        issues.append(f"reviews.json missing sample ids: {missing_reviews[:5]}")
    if extra_packets:
        issues.append(f"packets not in review sample: {extra_packets[:5]}")
    if len(context.packets) != len(context.review_sample):
        issues.append(
            f"packet count {len(context.packets)} != review sample count "
            f"{len(context.review_sample)}"
        )
    return issues


def validate_decisions_file(path: Path) -> List[str]:
    if not path.is_file():
        return []
    try:
        payload = harness.load_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{path.name}: unreadable ({exc})"]
    issues: List[str] = []
    if payload.get("review_tool_schema_version") != REVIEW_TOOL_SCHEMA_VERSION:
        issues.append(f"{path.name}: review_tool_schema_version must be {REVIEW_TOOL_SCHEMA_VERSION}")
    decisions = payload.get("decisions")
    if not isinstance(decisions, dict):
        return issues + [f"{path.name}: missing 'decisions' object"]
    seen: set[str] = set()
    for record_id, decision in decisions.items():
        if record_id in seen:
            issues.append(f"{path.name}: duplicate decision for '{record_id}'")
        seen.add(record_id)
        if not isinstance(decision, dict):
            issues.append(f"{path.name}: decision for '{record_id}' must be an object")
            continue
        label = decision.get("label")
        if label not in DECISION_LABELS:
            issues.append(f"{path.name}: invalid label '{label}' for '{record_id}'")
    return issues


def validate_run_context(
    context: RunContext,
    *,
    slot: str = "reviewer_a",
    require_reviewer: Optional[str] = None,
) -> List[str]:
    issues = validate_packets(context)
    issues.extend(harness.validate_reviews(context.reviews))
    if slot not in REVIEW_SLOTS:
        issues.append(f"invalid slot '{slot}'")
    if require_reviewer is not None:
        issues.extend(_validate_reviewer_name(require_reviewer))
    issues.extend(validate_decisions_file(decisions_path(context.run_dir, slot)))
    return issues


def ordered_record_ids(context: RunContext) -> List[str]:
    return list(context.sample_ids)


def pending_record_ids(context: RunContext, slot: str) -> List[str]:
    pending: List[str] = []
    for record_id in ordered_record_ids(context):
        try:
            slot_review = _slot_review(context, record_id, slot)
        except KeyError:
            continue
        if not _is_reviewed(slot_review):
            pending.append(record_id)
    return pending


def reviewed_record_ids(context: RunContext, slot: str) -> List[str]:
    reviewed: List[str] = []
    for record_id in ordered_record_ids(context):
        try:
            slot_review = _slot_review(context, record_id, slot)
        except KeyError:
            continue
        if _is_reviewed(slot_review):
            reviewed.append(record_id)
    return reviewed


def next_pending_record_id(context: RunContext, slot: str) -> Optional[str]:
    pending = pending_record_ids(context, slot)
    return pending[0] if pending else None


def format_candidate(
    context: RunContext,
    record_id: str,
    *,
    slot: str = "reviewer_a",
) -> str:
    packet = context.packet_by_id.get(record_id)
    if packet is None:
        raise KeyError(f"unknown record_id '{record_id}'")
    reviewed = reviewed_record_ids(context, slot)
    pending = pending_record_ids(context, slot)
    position = reviewed.index(record_id) + 1 if record_id in reviewed else None
    if position is None and record_id in pending:
        position = len(reviewed) + pending.index(record_id) + 1
    total = len(context.sample_ids)
    lines = [
        f"ITEM {position}/{total}  record_id={record_id}",
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
    slot_review = _slot_review(context, record_id, slot)
    if _is_reviewed(slot_review):
        label = HARNESS_TO_LABEL.get(slot_review.get("label"), slot_review.get("label"))
        lines.extend([
            "",
            "CURRENT DECISION",
            f"label: {label}",
            f"notes: {slot_review.get('notes') or ''}",
        ])
    else:
        lines.extend(["", "CURRENT DECISION", "label: (pending)"])
    return "\n".join(lines)


def _compose_notes(notes: str, fp_reason: str, label: str) -> str:
    parts: List[str] = []
    if notes.strip():
        parts.append(notes.strip())
    if label == "false_positive" and fp_reason.strip():
        parts.append(f"fp_reason: {fp_reason.strip()}")
    return "\n".join(parts)


def _load_decisions_audit(context: RunContext, slot: str) -> Dict[str, Any]:
    path = decisions_path(context.run_dir, slot)
    if not path.is_file():
        return {
            "review_tool_schema_version": REVIEW_TOOL_SCHEMA_VERSION,
            "reviewer": "",
            "slot": slot,
            "run_dir": str(context.run_dir),
            "decisions": {},
        }
    payload = harness.load_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} must be a JSON object")
    payload.setdefault("decisions", {})
    return payload


def _write_decisions_audit(context: RunContext, slot: str, payload: Dict[str, Any]) -> None:
    path = decisions_path(context.run_dir, slot)
    harness.write_json(path, payload)


def apply_decision(
    context: RunContext,
    record_id: str,
    label: str,
    *,
    reviewer: str,
    slot: str = "reviewer_a",
    notes: str = "",
    fp_reason: str = "",
    review_minutes: Optional[float] = None,
    edit: bool = False,
) -> Dict[str, Any]:
    issues = _validate_reviewer_name(reviewer)
    if label not in DECISION_LABELS:
        issues.append(f"invalid label '{label}'; allowed: {sorted(DECISION_LABELS)}")
    if slot not in REVIEW_SLOTS:
        issues.append(f"invalid slot '{slot}'")
    if record_id not in context.packet_by_id:
        issues.append(f"unknown record_id '{record_id}'")
    if issues:
        raise ValueError("; ".join(issues))

    slot_review = _slot_review(context, record_id, slot)
    if _is_reviewed(slot_review) and not edit:
        raise ValueError(
            f"{record_id} already reviewed as '{slot_review.get('label')}' "
            f"(pass --edit to overwrite)"
        )

    harness_label = LABEL_TO_HARNESS[label]
    composed_notes = _compose_notes(notes, fp_reason, label)
    usefulness = USEFULNESS_FROM_LABEL[label]
    slot_review.update({
        "label": harness_label,
        "notes": composed_notes,
        "review_minutes": review_minutes,
        "usefulness": usefulness,
    })

    audit = _load_decisions_audit(context, slot)
    audit["reviewer"] = reviewer.strip()
    audit["slot"] = slot
    audit["run_dir"] = str(context.run_dir)
    audit["updated_at"] = _utc_now()
    audit["decisions"][record_id] = {
        "record_id": record_id,
        "label": label,
        "harness_label": harness_label,
        "notes": composed_notes,
        "fp_reason": fp_reason.strip(),
        "review_minutes": review_minutes,
        "usefulness": usefulness,
        "reviewed_at": _utc_now(),
    }
    _write_decisions_audit(context, slot, audit)
    harness.write_json(context.run_dir / "reviews.json", context.reviews)
    return audit["decisions"][record_id]


def export_decisions_csv(context: RunContext, slot: str) -> str:
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow([
        "record_id",
        "repo_id",
        "file",
        "line",
        "rule",
        "kind",
        "label",
        "harness_label",
        "usefulness",
        "notes",
        "fp_reason",
        "reviewed_at",
    ])
    audit = _load_decisions_audit(context, slot)
    for record_id in ordered_record_ids(context):
        decision = audit.get("decisions", {}).get(record_id)
        packet = context.packet_by_id[record_id]
        if decision:
            writer.writerow([
                record_id,
                packet.get("repo_id", ""),
                packet.get("file", ""),
                packet.get("line", ""),
                packet.get("rule", ""),
                packet.get("kind", ""),
                decision.get("label", ""),
                decision.get("harness_label", ""),
                decision.get("usefulness", ""),
                decision.get("notes", ""),
                decision.get("fp_reason", ""),
                decision.get("reviewed_at", ""),
            ])
        else:
            writer.writerow([
                record_id,
                packet.get("repo_id", ""),
                packet.get("file", ""),
                packet.get("line", ""),
                packet.get("rule", ""),
                packet.get("kind", ""),
                "",
                "",
                "",
                "",
                "",
                "",
            ])
    return output.getvalue()


def write_decisions_csv(context: RunContext, slot: str, path: str | Path) -> None:
    Path(path).write_text(export_decisions_csv(context, slot), encoding="utf-8", newline="\n")


def _decisions_for_metrics(context: RunContext, slot: str) -> List[Dict[str, Any]]:
    audit = _load_decisions_audit(context, slot)
    rows: List[Dict[str, Any]] = []
    for record_id in ordered_record_ids(context):
        decision = audit.get("decisions", {}).get(record_id)
        if not decision:
            continue
        packet = context.packet_by_id[record_id]
        rows.append({**packet, **decision})
    return rows


def estimate_progress(context: RunContext, slot: str) -> Dict[str, Any]:
    total = len(context.sample_ids)
    reviewed = len(reviewed_record_ids(context, slot))
    pending = total - reviewed
    decisions = _decisions_for_metrics(context, slot)
    label_counts = {label: 0 for label in sorted(DECISION_LABELS)}
    for row in decisions:
        label_counts[row.get("label", "")] = label_counts.get(row.get("label", ""), 0) + 1

    tp = label_counts["true_positive"]
    fp = label_counts["false_positive"]
    decisive = tp + fp
    precision_estimate = round(tp / decisive, 4) if decisive else None

    usefulness_values = [
        row["usefulness"] for row in decisions if isinstance(row.get("usefulness"), int)
    ]
    usefulness_estimate = (
        round(sum(usefulness_values) / len(usefulness_values), 4)
        if usefulness_values
        else None
    )

    fp_reasons: Dict[str, int] = {}
    for row in decisions:
        if row.get("label") != "false_positive":
            continue
        reason = (row.get("fp_reason") or row.get("notes") or "unspecified").strip()
        if reason.startswith("fp_reason:"):
            reason = reason.split(":", 1)[1].strip()
        fp_reasons[reason] = fp_reasons.get(reason, 0) + 1
    top_fp_reasons = sorted(fp_reasons.items(), key=lambda item: (-item[1], item[0]))[:10]

    harness_labeled = []
    for record in context.review_sample:
        merged = dict(record)
        slot_review = _slot_review(context, record["record_id"], slot)
        merged.update({
            "label": slot_review.get("label", "unreviewed"),
            "usefulness": slot_review.get("usefulness"),
            "needs_adjudication": False,
        })
        if _is_reviewed(slot_review):
            harness_labeled.append(merged)

    harness_precision = harness.measure_precision(harness_labeled) if harness_labeled else None

    return {
        "slot": slot,
        "total": total,
        "reviewed": reviewed,
        "pending": pending,
        "label_counts": label_counts,
        "precision_estimate": precision_estimate,
        "precision_decisive_count": decisive,
        "usefulness_estimate": usefulness_estimate,
        "usefulness_scored_count": len(usefulness_values),
        "top_fp_reasons": [{"reason": reason, "count": count} for reason, count in top_fp_reasons],
        "harness_strict_precision": (
            harness_precision["strict_precision"] if harness_precision else None
        ),
        "harness_reviewed_in_scope": (
            harness_precision["reviewed_in_scope"] if harness_precision else 0
        ),
    }


def format_progress_report(progress: Dict[str, Any]) -> str:
    lines = [
        "PHASE 95D REVIEW PROGRESS",
        f"slot: {progress['slot']}",
        f"reviewed: {progress['reviewed']}/{progress['total']}",
        f"pending: {progress['pending']}",
        "",
        "LABEL COUNTS",
    ]
    for label, count in progress["label_counts"].items():
        lines.append(f"- {label}: {count}")
    lines.extend([
        "",
        "ESTIMATES (slot-local; not final until adjudication completes)",
        f"- precision (TP / (TP+FP)): {progress['precision_estimate']}",
        f"- usefulness mean (0-4): {progress['usefulness_estimate']}",
        f"- harness strict precision (mapped labels): {progress['harness_strict_precision']}",
        f"- harness reviewed in scope: {progress['harness_reviewed_in_scope']}",
        "",
        "TOP FALSE-POSITIVE REASONS",
    ])
    if progress["top_fp_reasons"]:
        for item in progress["top_fp_reasons"]:
            lines.append(f"- ({item['count']}) {item['reason']}")
    else:
        lines.append("- (none yet)")
    return "\n".join(lines) + "\n"


def list_summary(context: RunContext, slot: str) -> Dict[str, Any]:
    return {
        "pending": pending_record_ids(context, slot),
        "reviewed": reviewed_record_ids(context, slot),
        "next": next_pending_record_id(context, slot),
    }
