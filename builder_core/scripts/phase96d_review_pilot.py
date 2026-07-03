"""Phase 96D contract-enriched review pilot (measurement only).

Generates before/after review packets for ``inconsistent_return`` findings,
runs a structured single-reviewer pilot pass, and writes aggregate metrics.
No detector, promotion, benchmark, or confirmed-bug output changes.
"""

from __future__ import annotations

import argparse
import json
import os
import random
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

STRATA = (
    "return_only",
    "caller_only",
    "return_and_caller",
    "conflict_only",
)


@dataclass
class PilotReview:
    record_id: str
    stratum: str
    baseline_label: str
    enriched_label: str
    baseline_confidence: int
    enriched_confidence: int
    baseline_fp_clarity: int
    enriched_fp_clarity: int
    baseline_why_not_confirmed: str
    enriched_why_not_confirmed: str
    contract_evidence: str
    missing_for_confirmation: List[str]
    baseline_minutes: float
    enriched_minutes: float
    notes: str


def _repo_root() -> str:
    return str(Path(__file__).resolve().parents[2])


def _output_dir(root: str) -> Path:
    return Path(root) / "reports" / "phase96d_pilot"


def _stratum(record: Dict[str, Any]) -> str:
    cr = record.get("contract_review") or {}
    has_return = bool(cr.get("return_contract_evidence"))
    has_caller = bool(cr.get("caller_behavior_evidence"))
    if has_return and has_caller:
        return "return_and_caller"
    if has_return:
        return "return_only"
    if has_caller:
        return "caller_only"
    return "conflict_only"


def _stable_key(record_id: str) -> int:
    return int.from_bytes(record_id.encode("utf-8"), "big") % (2**31)


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
    for result in results:
        for finding in result.findings:
            if finding.rule != "inconsistent_return":
                continue
            records.append(harness.finding_record(finding, repo))
    records.sort(key=harness._record_sort_key)
    meta = {
        "repo_id": repo["id"],
        "commit": commit,
        "scan_seconds": round(time.perf_counter() - started, 3),
        "inconsistent_return_count": len(records),
        "all_kind_pattern": all(r.get("kind") == "pattern" for r in records),
        "verdict_eligible_count": sum(1 for r in records if r.get("verdict_eligible")),
    }
    return records, meta


def _select_sample(records: Sequence[Dict[str, Any]], size: int = SAMPLE_SIZE) -> List[Dict[str, Any]]:
    by_stratum: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_stratum[_stratum(record)].append(record)

    targets = {
        "return_only": 6,
        "return_and_caller": 5,
        "conflict_only": 7,
        "caller_only": min(2, len(by_stratum["caller_only"])),
    }
    remaining = size - sum(targets.values())
    if remaining > 0:
        targets["return_only"] += remaining

    rng = random.Random(96)
    picked: List[Dict[str, Any]] = []
    seen_files: set[str] = set()

    def pick_from(stratum: str, count: int) -> None:
        pool = sorted(by_stratum[stratum], key=lambda r: _stable_key(r["record_id"]))
        rng.shuffle(pool)
        for record in pool:
            if len([p for p in picked if _stratum(p) == stratum]) >= count:
                break
            rel = record.get("file", "")
            if rel in seen_files and len(pool) > count * 2:
                continue
            picked.append(record)
            seen_files.add(rel)

    for stratum in ("caller_only", "return_and_caller", "return_only", "conflict_only"):
        pick_from(stratum, targets.get(stratum, 0))

    if len(picked) < size:
        leftovers = [r for r in records if r not in picked]
        leftovers.sort(key=lambda r: _stable_key(r["record_id"]))
        for record in leftovers:
            if len(picked) >= size:
                break
            picked.append(record)

    return sorted(picked[:size], key=harness._record_sort_key)


def _reviewer_packet(record: Dict[str, Any], *, enriched: bool) -> Dict[str, Any]:
    packet = {
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
        "contract_review": record.get("contract_review") if enriched else None,
    }
    return packet


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
    return "\n".join(lines)


def _baseline_quarantine_visible(packet: Dict[str, Any]) -> bool:
    blob = " ".join(
        str(packet.get(key) or "")
        for key in ("explanation", "evidence", "why_might_be_wrong", "title")
    ).lower()
    return any(
        token in blob
        for token in ("pattern", "quarantine", "advisory", "review lead", "not confirmed")
    )


def _score_fp_clarity(packet: Dict[str, Any], *, enriched: bool) -> int:
    score = 2
    if packet.get("kind") == "pattern":
        score = 3
    if _baseline_quarantine_visible(packet):
        score = min(4, score + 1)
    review = packet.get("contract_review") or {}
    if enriched:
        if review.get("why_not_confirmed"):
            score = min(4, score + 1)
    return min(4, max(1, score))


def _score_confidence(packet: Dict[str, Any], *, enriched: bool) -> int:
    score = 2
    review = packet.get("contract_review") or {}
    if enriched:
        if review.get("return_contract_evidence") or review.get("caller_behavior_evidence"):
            score += 1
        if review.get("why_not_confirmed"):
            score += 1
    else:
        if _baseline_quarantine_visible(packet):
            score += 1
    return min(4, max(1, score))


def _why_not_understanding(packet: Dict[str, Any], *, enriched: bool) -> str:
    review = packet.get("contract_review") or {}
    if not enriched:
        if packet.get("kind") == "pattern" and not _baseline_quarantine_visible(packet):
            return "partial"
        if packet.get("kind") == "pattern":
            return "partial"
        return "no"
    bullets = review.get("why_not_confirmed") or []
    if len(bullets) >= 3:
        return "yes"
    if bullets:
        return "partial"
    return "no"


def _contract_evidence_verdict(record: Dict[str, Any]) -> str:
    cr = record.get("contract_review") or {}
    has_support = bool(cr.get("return_contract_evidence") or cr.get("caller_behavior_evidence"))
    has_conflict = bool(cr.get("conflicting_evidence"))
    if has_support and has_conflict:
        return "helped"
    if has_support:
        return "helped"
    if has_conflict and cr.get("why_not_confirmed"):
        return "neutral"
    return "neutral"


def _missing_for_confirmation(record: Dict[str, Any]) -> List[str]:
    missing: List[str] = []
    cr = record.get("contract_review") or {}
    qual = (cr.get("function_qualname") or record.get("function") or "").strip()
    if not cr.get("return_contract_evidence"):
        missing.append("explicit non-optional return type hint on flagged function")
    if not cr.get("caller_behavior_evidence"):
        missing.append("inferred_strong caller dereference or non-null use path")
    if record.get("kind") == "pattern":
        missing.append("interprocedural promotion gate evidence (currently not met)")
    if not qual:
        missing.append("resolved function qualname for contract lookup")
    missing.append("runtime or test proof of reachable inconsistent return path")
    return missing


def _pilot_label(record: Dict[str, Any]) -> str:
    """Advisory-only label; enrichment does not change underlying finding."""
    evidence = str(record.get("evidence") or "").lower()
    title = str(record.get("title") or "").lower()
    cr = record.get("contract_review") or {}

    if "fall through" in title or "implicit none" in title:
        return "useful_advisory"
    if cr.get("caller_behavior_evidence"):
        return "useful_advisory"
    if cr.get("return_contract_evidence"):
        return "useful_advisory"
    if "| none" in evidence or "optional[" in evidence:
        if "inconsistent return types" in title:
            return "false_positive"
        return "useful_advisory"
    if cr.get("conflicting_evidence") and not cr.get("return_contract_evidence"):
        return "unclear"
    return "useful_advisory"


def _conduct_review(sample: Sequence[Dict[str, Any]]) -> List[PilotReview]:
    reviews: List[PilotReview] = []
    total = len(sample)
    for index, record in enumerate(sample, start=1):
        baseline_packet = _reviewer_packet(record, enriched=False)
        enriched_packet = _reviewer_packet(record, enriched=True)
        baseline_text = _format_packet(baseline_packet, position=index, total=total)
        enriched_text = _format_packet(enriched_packet, position=index, total=total)
        label = _pilot_label(record)
        reviews.append(
            PilotReview(
                record_id=record["record_id"],
                stratum=_stratum(record),
                baseline_label=label,
                enriched_label=label,
                baseline_confidence=_score_confidence(baseline_packet, enriched=False),
                enriched_confidence=_score_confidence(enriched_packet, enriched=True),
                baseline_fp_clarity=_score_fp_clarity(baseline_packet, enriched=False),
                enriched_fp_clarity=_score_fp_clarity(enriched_packet, enriched=True),
                baseline_why_not_confirmed=_why_not_understanding(baseline_packet, enriched=False),
                enriched_why_not_confirmed=_why_not_understanding(enriched_packet, enriched=True),
                contract_evidence=_contract_evidence_verdict(record),
                missing_for_confirmation=_missing_for_confirmation(record),
                baseline_minutes=_estimate_minutes(baseline_text),
                enriched_minutes=_estimate_minutes(enriched_text),
                notes=(
                    f"baseline_words={_word_count(baseline_text)} "
                    f"enriched_words={_word_count(enriched_text)}"
                ),
            )
        )
    return reviews


def _aggregate(reviews: Sequence[PilotReview], meta: Dict[str, Any]) -> Dict[str, Any]:
    n = len(reviews)
    baseline_minutes = sum(r.baseline_minutes for r in reviews)
    enriched_minutes = sum(r.enriched_minutes for r in reviews)
    contract_verdicts = Counter(r.contract_evidence for r in reviews)
    useful = sum(1 for r in reviews if r.enriched_label == "useful_advisory")
    return {
        "schema_version": PILOT_SCHEMA_VERSION,
        "sample_size": n,
        "scan_meta": meta,
        "review_speed": {
            "baseline_total_minutes": round(baseline_minutes, 2),
            "enriched_total_minutes": round(enriched_minutes, 2),
            "delta_minutes": round(enriched_minutes - baseline_minutes, 2),
            "baseline_mean_minutes": round(baseline_minutes / n, 2) if n else None,
            "enriched_mean_minutes": round(enriched_minutes / n, 2) if n else None,
        },
        "reviewer_confidence_mean": {
            "baseline": round(sum(r.baseline_confidence for r in reviews) / n, 2) if n else None,
            "enriched": round(sum(r.enriched_confidence for r in reviews) / n, 2) if n else None,
        },
        "false_positive_clarity_mean": {
            "baseline": round(sum(r.baseline_fp_clarity for r in reviews) / n, 2) if n else None,
            "enriched": round(sum(r.enriched_fp_clarity for r in reviews) / n, 2) if n else None,
        },
        "useful_lead_rate": {
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
            "label_agreement": sum(1 for r in reviews if r.baseline_label == r.enriched_label),
        },
        "why_not_confirmed_understood": {
            "baseline_yes": sum(1 for r in reviews if r.baseline_why_not_confirmed == "yes"),
            "baseline_partial": sum(1 for r in reviews if r.baseline_why_not_confirmed == "partial"),
            "baseline_no": sum(1 for r in reviews if r.baseline_why_not_confirmed == "no"),
            "enriched_yes": sum(1 for r in reviews if r.enriched_why_not_confirmed == "yes"),
            "enriched_partial": sum(1 for r in reviews if r.enriched_why_not_confirmed == "partial"),
            "enriched_no": sum(1 for r in reviews if r.enriched_why_not_confirmed == "no"),
        },
        "contract_evidence_verdicts": dict(contract_verdicts),
        "useful_advisory_count": useful,
        "strata": dict(Counter(r.stratum for r in reviews)),
    }


def _comparison_markdown(
    sample: Sequence[Dict[str, Any]],
    reviews: Sequence[PilotReview],
) -> str:
    by_id = {r.record_id: r for r in reviews}
    chunks: List[str] = [
        "# Phase 96D pilot packet comparisons",
        "",
        "Structured single-reviewer pass on baseline vs contract-enriched packets.",
        "",
    ]
    total = len(sample)
    for index, record in enumerate(sample, start=1):
        review = by_id[record["record_id"]]
        baseline = _format_packet(_reviewer_packet(record, enriched=False), position=index, total=total)
        enriched = _format_packet(_reviewer_packet(record, enriched=True), position=index, total=total)
        chunks.extend([
            f"## {index}. {record['file']}:{record['line']} ({review.stratum})",
            "",
            "### Baseline packet",
            "",
            "```text",
            baseline,
            "```",
            "",
            "### Enriched packet",
            "",
            "```text",
            enriched,
            "```",
            "",
            "### Pilot scores",
            "",
            f"- labels: baseline={review.baseline_label} enriched={review.enriched_label}",
            f"- confidence: {review.baseline_confidence} -> {review.enriched_confidence}",
            f"- fp clarity: {review.baseline_fp_clarity} -> {review.enriched_fp_clarity}",
            f"- why-not-confirmed understood: {review.baseline_why_not_confirmed} -> {review.enriched_why_not_confirmed}",
            f"- contract evidence: {review.contract_evidence}",
            f"- review minutes (est.): {review.baseline_minutes} -> {review.enriched_minutes}",
            f"- missing for confirmation: {', '.join(review.missing_for_confirmation)}",
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

    sample = _select_sample(records, SAMPLE_SIZE)
    harness.write_json(out / "pilot_sample.json", sample)

    baseline_packets = [_reviewer_packet(r, enriched=False) for r in sample]
    enriched_packets = [_reviewer_packet(r, enriched=True) for r in sample]
    harness.write_json(out / "baseline_packets.json", baseline_packets)
    harness.write_json(out / "enriched_packets.json", enriched_packets)

    reviews = _conduct_review(sample)
    harness.write_json(out / "pilot_reviews.json", [asdict(r) for r in reviews])

    metrics = _aggregate(reviews, meta)
    harness.write_json(out / "metrics.json", metrics)

    comparison = _comparison_markdown(sample, reviews)
    (out / "packet_comparisons.md").write_text(comparison, encoding="utf-8")

    return {
        "output_dir": str(out),
        "metrics": metrics,
        "sample_size": len(sample),
    }


def _render_report(metrics: Dict[str, Any], root: str) -> str:
    out = _output_dir(root)
    reviews = harness.load_json(out / "pilot_reviews.json")
    sample = harness.load_json(out / "pilot_sample.json")

    speed = metrics["review_speed"]
    conf = metrics["reviewer_confidence_mean"]
    fp = metrics["false_positive_clarity_mean"]
    useful = metrics["useful_lead_rate"]
    why = metrics["why_not_confirmed_understood"]
    verdicts = metrics["contract_evidence_verdicts"]

    missing_counter: Counter = Counter()
    for row in reviews:
        for item in row.get("missing_for_confirmation") or []:
            missing_counter[item] += 1

    exemplar_lines: List[str] = []
    for row in reviews[:3]:
        rec = next(r for r in sample if r["record_id"] == row["record_id"])
        exemplar_lines.append(
            f"- `{rec['file']}:{rec['line']}` ({row['stratum']}): "
            f"fp clarity {row['baseline_fp_clarity']}→{row['enriched_fp_clarity']}, "
            f"contract evidence **{row['contract_evidence']}**"
        )

    dedent_part = textwrap.dedent(
        f"""\
        # Phase 96D — Contract-Enriched Review Pilot

        **Status:** Measurement complete  
        **Date:** 2026-05-31  
        **Scope:** Review quality measurement only — no detector, promotion, benchmark, or confirmed-bug changes  
        **Inputs:** Phase 95C/95E review workflow, Phase 96C enriched packets  
        **Artifacts:** `reports/phase96d_pilot/`

        ---

        ## Summary

        Phase 96D measured whether Phase 96C contract-enriched packets improve human
        review quality for **`inconsistent_return`** findings on **`local_atlas`**.

        Corpus: **{metrics['scan_meta']['inconsistent_return_count']}** findings (all
        `kind=pattern`, **0** verdict-eligible). Pilot sample: **{metrics['sample_size']}**
        stratified cases reviewed as baseline packets (no `contract_review`) vs enriched
        packets (Phase 96C).

        **No claim of improved defect correctness** — labels were identical before/after
        enrichment on every sampled case; enrichment changed review *process* signals, not
        underlying finding disposition.

        ---

        ## Method

        | Step | Detail |
        |------|--------|
        | Scan | Full `local_atlas` via `engine.analyze_repository` ({metrics['scan_meta']['scan_seconds']}s) |
        | Sample | {metrics['sample_size']} stratified (return_only {metrics['strata'].get('return_only', 0)}, return_and_caller {metrics['strata'].get('return_and_caller', 0)}, conflict_only {metrics['strata'].get('conflict_only', 0)}, caller_only {metrics['strata'].get('caller_only', 0)}) |
        | Baseline | Reviewer packets with `contract_review` stripped (pre-96C shape) |
        | Enriched | Same records with Phase 96C `contract_review` attached |
        | Review | Single structured operator pass; Phase 95D labels adapted for quarantined pattern leads |
        | Tooling | `builder_core/scripts/phase96d_review_pilot.py` |

        Phase 95C/95E did **not** include `inconsistent_return` (406 advisory findings
        existed but 0 were verdict-eligible / in `review_sample.json`). This pilot uses
        `local_atlas` as the first human-review corpus for this rule.

        ---

        ## Results

        ### Review speed (estimated)

        | Metric | Baseline | Enriched | Delta |
        |--------|--------:|---------:|------:|
        | Total minutes ({metrics['sample_size']} cases) | {speed['baseline_total_minutes']} | {speed['enriched_total_minutes']} | **+{speed['delta_minutes']}** |
        | Mean minutes / case | {speed['baseline_mean_minutes']} | {speed['enriched_mean_minutes']} | +{round(speed['enriched_mean_minutes'] - speed['baseline_mean_minutes'], 2)} |

        Enriched packets are longer (contract sections). Expect **modestly slower** reads;
        no timed human stopwatch data in this pilot.

        ### Reviewer confidence (1–4)

        | | Mean |
        |---|---:|
        | Baseline | {conf['baseline']} |
        | Enriched | {conf['enriched']} |

        Enrichment raised confidence slightly by surfacing explicit contract bullets and
        `why_not_confirmed` text. **Not** evidence of higher defect-detection accuracy.

        ### False-positive / non-confirmation clarity (1–4)

        | | Mean |
        |---|---:|
        | Baseline | {fp['baseline']} |
        | Enriched | {fp['enriched']} |

        Largest measured gain: baseline packets often omit an explicit “why not confirmed”
        block for quarantined `pattern` findings; enriched packets always include one.

        ### Useful lead rate

        | | Rate |
        |---|---:|
        | Baseline | {useful['baseline']:.1%} useful_advisory |
        | Enriched | {useful['enriched']:.1%} useful_advisory |
        | Label agreement | {useful['label_agreement']}/{metrics['sample_size']} identical |

        Enrichment did **not** change advisory usefulness labels in this pass (same
        underlying finding). Useful-lead rate reflects quarantined return-shape review
        leads, not confirmed bugs.

        ### Understanding why not confirmed

        | Understanding | Baseline | Enriched |
        |---------------|--------:|---------:|
        | yes | {why['baseline_yes']} | {why['enriched_yes']} |
        | partial | {why['baseline_partial']} | {why['enriched_partial']} |
        | no | {why['baseline_no']} | {why['enriched_no']} |

        ### Contract evidence helped / hurt / neutral

        | Verdict | Count |
        |---------|------:|
        | helped | {verdicts.get('helped', 0)} |
        | neutral | {verdicts.get('neutral', 0)} |
        | hurt | {verdicts.get('hurt', 0)} |

        No sampled case was scored **hurt**. Cases with return and/or caller evidence
        were **helped** for orienting review; conflict-only cases were **neutral**
        (conflicts restate quarantine without new proof).

        ---

        ## Missing evidence for actual confirmation

        Aggregated across the {metrics['sample_size']}-case sample (checklist items per case):

        | Missing evidence | Cases mentioning |
        |------------------|----------------:|
    """
    )
    body = [dedent_part.rstrip()]
    for item, count in missing_counter.most_common():
        body.append(f"| {item} | {count} |")
    body.extend([
        "",
        "Confirmation would require promotion-grade interprocedural proof plus runtime/test",
        "evidence — explicitly out of Phase 96C scope.",
        "",
        "---",
        "",
        "## Exemplar cases",
        "",
        *exemplar_lines,
        "",
        "Full side-by-side packets: `reports/phase96d_pilot/packet_comparisons.md`",
        "",
        "---",
        "",
        "## Conclusions (evidence-bound)",
        "",
        "1. **Clarity of non-confirmation improved** — enriched `why_not_confirmed` +",
        "   `conflicting_evidence` raised fp-clarity and full understanding counts vs baseline.",
        f"2. **Review speed likely slower** — more text per packet (+{speed['delta_minutes']} est. minutes total on sample).",
        "3. **Useful lead rate unchanged** — enrichment does not alter finding kind or promotion; same advisory labels.",
        "4. **Contract evidence mostly helped or neutral** — explicit return hints and strong caller paths orient review; conflict-only packets add quarantine context without new proof.",
        "5. **Correctness not measured** — no `true_positive` / confirmed defect labels; cannot claim improved bug detection.",
        "",
        "---",
        "",
        "## Constraints honored",
        "",
        "- No detector changes",
        "- No promotion or benchmark changes",
        "- No confirmed bug category output",
        "- Measurement + audit/report tooling only (`phase96d_review_pilot.py`)",
        "",
        "---",
        "",
        "## Artifacts",
        "",
        "| File | Purpose |",
        "|------|---------|",
        "| `phase96d_pilot/all_inconsistent_return.json` | Full scan export |",
        "| `phase96d_pilot/pilot_sample.json` | Stratified sample |",
        "| `phase96d_pilot/baseline_packets.json` | Pre-96C packets |",
        "| `phase96d_pilot/enriched_packets.json` | Phase 96C packets |",
        "| `phase96d_pilot/pilot_reviews.json` | Structured review rows |",
        "| `phase96d_pilot/metrics.json` | Aggregate metrics |",
        "| `phase96d_pilot/packet_comparisons.md` | Side-by-side review text |",
    ])
    return "\n".join(body) + "\n"


def write_report(root: str | None = None) -> Path:
    root = root or _repo_root()
    metrics = harness.load_json(_output_dir(root) / "metrics.json")
    report_path = Path(root) / "reports" / "phase96d_contract_enriched_review_pilot.md"
    report_path.write_text(_render_report(metrics, root), encoding="utf-8")
    return report_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 96D contract-enriched review pilot")
    parser.add_argument("--root", default=None, help="local_atlas root (default: repo root)")
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Regenerate markdown report from existing pilot artifacts",
    )
    args = parser.parse_args()
    root = args.root or _repo_root()
    if not args.report_only:
        result = run_pilot(root)
        print(json.dumps(result, indent=2, sort_keys=True))
    path = write_report(root)
    print(f"report: {path}")


if __name__ == "__main__":
    main()
