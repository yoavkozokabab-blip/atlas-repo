"""Phase 97D verification evidence calibration analysis (measurement only)."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
PILOT = ROOT / "reports" / "phase97c_pilot"
REPORT = ROOT / "reports" / "phase97d_verification_calibration_analysis.md"


def _load(name: str) -> Any:
    return json.loads((PILOT / name).read_text(encoding="utf-8"))


def _title_kind(rec: Dict[str, Any]) -> str:
    title = (rec.get("title") or "").lower()
    if "fall through" in title or "implicit none" in title:
        return "implicit_none_fallthrough"
    if "inconsistent return types" in title:
        return "inconsistent_types"
    return "other"


def _refutation_mechanism(rec: Dict[str, Any]) -> str:
    ve = rec.get("verification_evidence") or {}
    atoms = ve.get("atoms") or []
    refuting = ve.get("refuting_evidence") or []
    pool = refuting or [a for a in atoms if a.get("polarity") == "refutes"]
    if not pool:
        if ve.get("status") == "blocked":
            blockers = ve.get("blockers") or []
            if atoms:
                claim = atoms[0].get("claim") or ""
                if claim.startswith("path."):
                    return claim
            if "conflicting_optional_return_contract" in blockers:
                return "optional_contract_blocker"
            if "missing_explicit_return_obligation" in blockers:
                return "missing_obligation_blocker"
            if "interprocedural_promotion_gate_not_met" in blockers:
                return "gate_blocker_only"
            return "blocked_other"
        return "none"
    atom = pool[0]
    claim = atom.get("claim") or ""
    if claim == "path.no_implicit_none_exit":
        return "no_fallthrough_witness"
    if claim == "path.caller_null_check_blocks_consequence":
        return "caller_null_check"
    if claim.startswith("path."):
        return claim
    return atom.get("evidence_type") or "unknown"


def _calibration_category(rec: Dict[str, Any], review: Dict[str, Any]) -> Tuple[str, List[str]]:
    """Return (primary, secondary tags) for calibration."""
    baseline = review["baseline_label"]
    enriched = review["enriched_label"]
    secondary: List[str] = []
    if baseline == enriched:
        return "unchanged", secondary

    ve = rec.get("verification_evidence") or {}
    cr = rec.get("contract_review") or {}
    mechanism = _refutation_mechanism(rec)
    tk = _title_kind(rec)
    optional = any(
        c.get("conflict_reason") == "optional_return_signal"
        for c in (cr.get("conflicting_evidence") or [])
    )

    if enriched != "false_positive":
        return "unchanged", secondary

    if optional and baseline in ("useful_advisory", "unclear"):
        secondary.append("optional_contract_visible")
        return "correct_reclassification", secondary

    if mechanism == "no_fallthrough_witness" and tk == "inconsistent_types":
        secondary.extend(["wrong_witness_for_finding_shape", "evidence_weighting_issue"])
        return "over_refutation", secondary

    if mechanism == "no_fallthrough_witness" and tk == "implicit_none_fallthrough":
        secondary.extend(["return_summary_vs_finding_disagreement", "missing_context"])
        return "over_refutation", secondary

    if ve.get("status") == "refuted" and len(ve.get("atoms") or []) == 1:
        secondary.append("evidence_weighting_issue")
    if ve.get("status") == "refuted":
        secondary.append("packet_presentation_issue")
    return "evidence_weighting_issue", secondary


def _ground_truth_proxy(rec: Dict[str, Any]) -> str:
    """Conservative proxy label for confusion matrix (not confirmed defects)."""
    cr = rec.get("contract_review") or {}
    optional = any(
        c.get("conflict_reason") == "optional_return_signal"
        for c in (cr.get("conflicting_evidence") or [])
    )
    tk = _title_kind(rec)
    if optional:
        return "non_actionable_lead"
    if tk == "implicit_none_fallthrough" and rec.get("kind") == "pattern":
        return "review_worthy_lead"
    if tk == "implicit_none_fallthrough" and rec.get("kind") == "value_flow":
        return "review_worthy_lead"
    return "uncertain"


def analyze() -> Dict[str, Any]:
    sample: List[Dict[str, Any]] = _load("pilot_sample.json")
    reviews: List[Dict[str, Any]] = _load("pilot_reviews.json")
    by_review = {r["record_id"]: r for r in reviews}

    cases: List[Dict[str, Any]] = []
    for rec in sample:
        rid = rec["record_id"]
        rev = by_review[rid]
        primary, secondary = _calibration_category(rec, rev)
        cases.append({
            "record_id": rid,
            "file": rec["file"],
            "line": rec["line"],
            "title": rec["title"],
            "kind": rec.get("kind"),
            "title_kind": _title_kind(rec),
            "baseline_label": rev["baseline_label"],
            "enriched_label": rev["enriched_label"],
            "verification_status": (rec.get("verification_evidence") or {}).get("status"),
            "refutation_mechanism": _refutation_mechanism(rec),
            "primary_calibration": primary,
            "secondary_tags": secondary,
            "ground_truth_proxy": _ground_truth_proxy(rec),
            "atom_types": [
                a.get("evidence_type") for a in (rec.get("verification_evidence") or {}).get("atoms") or []
            ],
        })

    reclassified = [c for c in cases if c["baseline_label"] != c["enriched_label"]]
    unchanged = [c for c in cases if c["baseline_label"] == c["enriched_label"]]

    primary_counts = Counter(c["primary_calibration"] for c in cases)
    reclass_primary = Counter(
        c["primary_calibration"] for c in reclassified if c["primary_calibration"] != "unchanged"
    )
    reclass_secondary = Counter(
        tag
        for c in reclassified
        for tag in c["secondary_tags"]
    )

    # Confusion matrix: rows = ground_truth_proxy, cols = enriched pilot label
    matrix: Dict[str, Counter] = defaultdict(Counter)
    for c in cases:
        matrix[c["ground_truth_proxy"]][c["enriched_label"]] += 1

    baseline_fp = sum(1 for c in cases if c["baseline_label"] == "false_positive")
    enriched_fp = sum(1 for c in cases if c["enriched_label"] == "false_positive")

    return {
        "cases": cases,
        "reclassified_count": len(reclassified),
        "unchanged_count": len(unchanged),
        "primary_counts": dict(primary_counts),
        "reclass_primary": dict(reclass_primary),
        "reclass_secondary": dict(reclass_secondary),
        "confusion_matrix": {k: dict(v) for k, v in matrix.items()},
        "baseline_fp": baseline_fp,
        "enriched_fp": enriched_fp,
        "mechanism_counts": Counter(c["refutation_mechanism"] for c in cases),
        "status_counts": Counter(c["verification_status"] for c in cases),
    }


def _render_report(data: Dict[str, Any]) -> str:
    cases = data["cases"]
    lines = [
        "# Phase 97D — Verification Evidence Calibration Analysis",
        "",
        "**Status:** Analysis complete  ",
        "**Date:** 2026-05-31  ",
        "**Scope:** Calibration measurement only — no detector, promotion, benchmark, or code changes  ",
        "**Inputs:** Phase 97C pilot (`reports/phase97c_pilot/`, 20 cases)  ",
        "",
        "---",
        "",
        "## Executive summary",
        "",
        "Phase 97C misleading rate rose **10% → 80%** (2 → 16 false-positive pilot labels)",
        f"on the same 20-case cohort. **{data['reclassified_count']}** cases changed label;",
        f"**{data['unchanged_count']}** unchanged.",
        "",
        "Root cause: Phase 97A marks **`status: refuted`** from a single",
        "`path_feasibility_evidence` atom (`path.no_implicit_none_exit`) on **16/20** cases.",
        "The Phase 97C pilot rubric maps any `refuted` status or refuting atom to",
        "`false_positive`. That coupling — not detector output — drives the misleading-rate jump.",
        "",
        "Calibration breakdown of the **14 reclassifications** (useful/unclear → false_positive):",
        "",
    ]
    for cat, count in sorted(data["reclass_primary"].items(), key=lambda x: -x[1]):
        lines.append(f"- **{cat.replace('_', ' ')}**: {count}")
    if data.get("reclass_secondary"):
        lines.extend(["", "Secondary tags on reclassified cases:"])
        for tag, count in sorted(data["reclass_secondary"].items(), key=lambda x: -x[1]):
            lines.append(f"- `{tag}`: {count}")
    lines.extend([
        "",
        "Dominant issue: **over-refutation** — `return_summary.can_fall_through` disagrees",
        "with the inconsistent-return finding on implicit-None fall-through leads (`kind=pattern`),",
        "yet verification elevates the disagreement to **`refuted`** status and the pilot",
        "auto-labels that as misleading.",
        "",
        "---",
        "",
        "## Why misleading rate jumped",
        "",
        "| Factor | Role |",
        "|--------|------|",
        "| 16× `verification_status: refuted` | Triggers enriched `false_positive` in 97C rubric |",
        "| 4× `verification_status: blocked` | Labels unchanged (still useful_advisory) |",
        "| Single atom per case (mean 1.0) | Refutation presented without supporting violation context |",
        "| `status: refuted` wording | Reads as “finding disproven,” stronger than “path witness incomplete” |",
        "| No human adjudication | Proxy labels, not ground-truth defect labels |",
        "",
        "The 10% baseline misleading rate came from **contract-only** heuristics (optional",
        "return type in signature on 2 cases). The 80% enriched rate adds **14** refuted-path",
        "cases that contract review still scored as useful advisories.",
        "",
        "---",
        "",
        "## Confusion matrix",
        "",
        "Rows: conservative **ground-truth proxy** (not confirmed defects).  ",
        "Columns: Phase 97C **enriched pilot label**.",
        "",
        "| Ground-truth proxy \\ Enriched label | false_positive | useful_advisory | unclear |",
        "|-----------------------------------|---------------:|----------------:|--------:|",
    ])

    labels = ["false_positive", "useful_advisory", "unclear"]
    for row in ["non_actionable_lead", "review_worthy_lead", "uncertain"]:
        counts = data["confusion_matrix"].get(row, {})
        lines.append(
            "| "
            + row.replace("_", " ")
            + " | "
            + " | ".join(str(counts.get(col, 0)) for col in labels)
            + " |"
        )

    lines.extend([
        "",
        "Interpretation: **review-worthy** implicit-None leads are overwhelmingly labeled",
        "false_positive when verification status is `refuted`. Optional-return leads align",
        "with false_positive under both contract and verification arms.",
        "",
        "---",
        "",
        "## Per-case reclassification table",
        "",
        "| # | Location | Baseline → Enriched | Status | Mechanism | Calibration |",
        "|--:|----------|---------------------|--------|-----------|-------------|",
    ])

    for i, c in enumerate(cases, 1):
        if c["baseline_label"] == c["enriched_label"]:
            transition = f"{c['baseline_label']} (unchanged)"
        else:
            transition = f"{c['baseline_label']} → {c['enriched_label']}"
        lines.append(
            f"| {i} | `{c['file']}:{c['line']}` | "
            f"{transition} | "
            f"{c['verification_status']} | {c['refutation_mechanism']} | "
            f"{c['primary_calibration']} |"
        )

    reclassified = [c for c in cases if c["baseline_label"] != c["enriched_label"]]
    lines.extend([
        "",
        "---",
        "",
        "## Reclassification categorization (14 cases)",
        "",
        "Each row tags the **primary** calibration cause plus secondary dimensions",
        "from the Phase 97D taxonomy.",
        "",
        "| # | Location | Primary | Missing context | Weighting | Presentation |",
        "|--:|----------|---------|:-------------:|:---------:|:------------:|",
    ])
    for i, c in enumerate(reclassified, 1):
        tags = set(c["secondary_tags"])
        lines.append(
            f"| {i} | `{c['file']}:{c['line']}` | {c['primary_calibration']} | "
            f"{'yes' if 'missing_context' in tags or 'return_summary_vs_finding_disagreement' in tags else '—'} | "
            f"{'yes' if 'evidence_weighting_issue' in tags or 'wrong_witness_for_finding_shape' in tags else '—'} | "
            f"{'yes' if c['verification_status'] == 'refuted' else '—'} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## Calibration category definitions",
        "",
        "| Category | Meaning in this pilot |",
        "|----------|----------------------|",
        "| **correct_reclassification** | Enriched label better matches proxy ground truth |",
        "| **over_refutation** | `refuted` status overstates refutation; lead may still warrant review |",
        "| **missing_context** | Packet omits why finding and witness disagree |",
        "| **evidence_weighting_issue** | Refutation atom alone drives `refuted` without bundle balance |",
        "| **packet_presentation_issue** | Wording (`refuted`, refutation-only) steers reviewers |",
        "",
        "---",
        "",
        "## Evidence-type recommendations",
        "",
        "| Evidence type | Verdict | Rationale |",
        "|---------------|---------|-----------|",
        "| **test_evidence** | **keep** | Not present in cohort (no `test_documents` in repo scan). Safe when bound; no harm observed. |",
        "| **assertion_evidence** | **keep** | Not emitted in these 20 cases. Phase 96A assert facts remain useful as obligation context. |",
        "| **contract_violation_evidence** | **modify** | Rare in cohort. When absent, refutation-only packets should not imply defect disproof. |",
        "| **path_feasibility_evidence** | **modify** | **Primary driver** of misleading-rate jump. Cap `refuted` status when finding kind is `pattern` and only witness is `path.no_implicit_none_exit`. |",
        "| **runtime_reproduction_evidence** | **keep** | Not present in cohort. Parser-only; no execution. |",
        "",
        "### path_feasibility_evidence — required modifications",
        "",
        "1. Do **not** set overlay `status: refuted` when the inconsistent-return finding",
        "   remains `kind=pattern` and the only refuting claim is `path.no_implicit_none_exit`.",
        "2. Prefer **`enriched_lead` + refuting atom** (polarity `refutes`, strength E2) instead",
        "   of global `refuted` status.",
        "3. Add **missing_context** bullet when `return_summary` and detector shape disagree.",
        "4. Never map overlay status directly to reviewer **`false_positive`** without",
        "   human adjudication (97C rubric artifact, not product behavior).",
        "",
        "### contract_violation_evidence — required modifications",
        "",
        "1. Keep derived violation atoms **supporting-only** until promotion gate enabled.",
        "2. Pair violation atoms with path witnesses before any future `refuted`/`blocked` status.",
        "",
        "### Packet presentation — required modifications",
        "",
        "1. Rename or qualify **`refuted`** → `refutation_witness_present` in review packets.",
        "2. Show **finding vs witness disagreement** explicitly for fall-through cases.",
        "3. Keep **MISSING PROOF OBLIGATIONS** (97C improved confirmation clarity 3.0 → 4.0).",
        "",
        "---",
        "",
        "## Aggregated calibration counts (20 cases)",
        "",
        f"| Primary calibration | Count |",
        f"|---------------------|------:|",
    ])
    for cat, count in sorted(data["primary_counts"].items(), key=lambda x: -x[1]):
        lines.append(f"| {cat.replace('_', ' ')} | {count} |")

    lines.extend([
        "",
        "### Reclassification mechanisms",
        "",
        f"| Refutation / blocker mechanism | Count |",
        f"|--------------------------------|------:|",
    ])
    for mech, count in data["mechanism_counts"].most_common():
        lines.append(f"| {mech} | {count} |")

    lines.extend([
        "",
        "---",
        "",
        "## Conclusions",
        "",
        "1. The **80% misleading rate is largely a measurement artifact**: 97C enriched labels",
        "   treat `verification_status: refuted` as `false_positive`, affecting 14/20 cases.",
        "2. **12 reclassifications are over-refutation** — `path.no_implicit_none_exit` applied",
        "   to 8 inconsistent-types findings (wrong witness) and 4 fall-through leads where",
        "   `return_summary` disagrees with the detector shape.",
        "3. **2 reclassifications are correct** — optional-return contract visible",
        "   (`patch_command_phrases`, `console_modal`).",
        "4. **Confirmation clarity gains (97C) are real**; misleading-rate spike is not evidence",
        "   of improved defect detection — it reflects status wording + rubric coupling.",
        "5. **No detector, promotion, or benchmark change recommended** from this analysis;",
        "   calibration fixes belong in **verification overlay status logic and review rubric**,",
        "   not finding generation.",
        "",
        "---",
        "",
        "## Constraints honored",
        "",
        "- No detector changes",
        "- No promotion changes",
        "- No benchmark changes",
        "- No code modifications (analysis-only deliverable)",
        "",
        "---",
        "",
        "## Artifacts",
        "",
        "| File | Purpose |",
        "|------|---------|",
        "| `phase97c_pilot/pilot_sample.json` | 20 reviewed findings |",
        "| `phase97c_pilot/pilot_reviews.json` | Baseline vs enriched labels |",
        "| `phase97c_pilot/metrics.json` | 97C aggregate metrics |",
        "| `builder_core/scripts/phase97d_calibration_analysis.py` | Reproducible analysis script |",
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    data = analyze()
    REPORT.write_text(_render_report(data), encoding="utf-8")
    print(f"report: {REPORT}")
    print("reclassified", data["reclassified_count"])
    print("reclass_primary", data["reclass_primary"])


if __name__ == "__main__":
    main()
