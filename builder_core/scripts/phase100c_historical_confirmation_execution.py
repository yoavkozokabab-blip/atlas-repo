"""Phase 100C — historical confirmation execution (measurement only).

Materializes the Phase 100A first batch (cases 21–30), runs the Phase 99D replay
harness, and reports tier metrics, confusion matrix, and confirmed precision/recall.
No detector or benchmark changes.
"""

from __future__ import annotations

import json
import subprocess
import textwrap
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from builder_core.historical_bug_replay import harness as HBR

ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = ROOT / "data" / "historical_corpus" / "phase100c"
MANIFEST_PATH = CORPUS_DIR / "manifest.json"
EXPECTED_PATH = CORPUS_DIR / "expected_packets.json"
OUTPUT_DIR = ROOT / "reports" / "phase100c_run"
REPORT_PATH = ROOT / "reports" / "phase100c_historical_confirmation_execution.md"

HOLDOUT_PAIRS = ROOT / "builder_core" / "benchmarks" / "holdout" / "pairs"

TIER_DETECTED = HBR.OUTPUT_DETECTED
TIER_STRONG = HBR.OUTPUT_STRONG_SUSPECT
TIER_REVIEW = HBR.OUTPUT_REVIEW_LEAD
TIER_REFUTED = HBR.OUTPUT_REFUTED

TIER_ORDER = (TIER_DETECTED, TIER_STRONG, TIER_REVIEW, TIER_REFUTED)

TIER_ALIASES = {
    "confirmed_defect": TIER_DETECTED,
    "confirmed defect": TIER_DETECTED,
    "detected": TIER_DETECTED,
    "strong_suspect": TIER_STRONG,
    "strong suspect": TIER_STRONG,
    "review_lead": TIER_REVIEW,
    "review lead": TIER_REVIEW,
    "refuted": TIER_REFUTED,
    "refuted/not actionable": TIER_REFUTED,
    "not actionable": TIER_REFUTED,
}


def _git_head() -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.stdout.strip() if proc.returncode == 0 else "unknown"
    except OSError:
        return "unknown"


def _inline_case(
    case_id: str,
    buggy: str,
    fixed: str,
    *,
    description: str = "",
    test_documents: Optional[Sequence[Dict[str, str]]] = None,
    target_rules: Optional[Sequence[str]] = None,
    fixed_files: Optional[Sequence[str]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    case: Dict[str, Any] = {
        "id": case_id,
        "description": description,
        "buggy_revision": {"kind": "inline", "source": textwrap.dedent(buggy), "rel_path": "m.py"},
        "fixed_revision": {"kind": "inline", "source": textwrap.dedent(fixed), "rel_path": "m.py"},
    }
    if test_documents:
        case["test_documents"] = list(test_documents)
    if target_rules:
        case["target_rules"] = list(target_rules)
    if fixed_files:
        case["fixed_files"] = list(fixed_files)
    if extra:
        case.update(extra)
    return case


def _pair_case(
    case_id: str,
    pair_name: str,
    *,
    description: str = "",
    target_rules: Optional[Sequence[str]] = None,
    test_documents: Optional[Sequence[Dict[str, str]]] = None,
    fixed_files: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    case: Dict[str, Any] = {
        "id": case_id,
        "description": description,
        "pair_dir": str(HOLDOUT_PAIRS / pair_name),
    }
    if target_rules:
        case["target_rules"] = list(target_rules)
    if test_documents:
        case["test_documents"] = list(test_documents)
    if fixed_files:
        case["fixed_files"] = list(fixed_files)
    return case


def build_first_batch_cases() -> List[Dict[str, Any]]:
    """Phase 100A §3.2–3.4: zero-setup first batch (cases 21–30)."""
    ir_rules = ["inconsistent_return"]
    return [
        _pair_case(
            "hold_black_executor",
            "bugsinpy_black_executor",
            description="BugsInPy black executor return/contract pair (distilled holdout)",
            target_rules=ir_rules,
            fixed_files=["buggy.py"],
        ),
        _pair_case(
            "hold_pysnooper_encoding",
            "bugsinpy_pysnooper_encoding",
            description="BugsInPy PySnooper encoding pair (distilled holdout)",
            target_rules=ir_rules,
            fixed_files=["buggy.py"],
        ),
        _pair_case(
            "hold_tqdm_enumerate",
            "bugsinpy_tqdm_enumerate",
            description="BugsInPy tqdm enumerate pair (distilled holdout)",
            target_rules=ir_rules,
            fixed_files=["buggy.py"],
        ),
        _pair_case(
            "dist_off_by_one",
            "classic_off_by_one",
            description="Distractor: off-by-one (not inconsistent_return gate scope)",
            target_rules=ir_rules,
            fixed_files=["buggy.py"],
        ),
        _pair_case(
            "dist_wrong_operator",
            "classic_wrong_operator",
            description="Distractor: wrong operator (not inconsistent_return gate scope)",
            target_rules=ir_rules,
            fixed_files=["buggy.py"],
        ),
        _pair_case(
            "dist_missing_base_case",
            "classic_missing_base_case",
            description="Distractor: missing base case (not inconsistent_return gate scope)",
            target_rules=ir_rules,
            fixed_files=["buggy.py"],
        ),
        _inline_case(
            "neg_optional_by_design",
            """
            from typing import Optional

            def helper(x: int) -> Optional[str]:
                if x:
                    return "a"
                return None

            def caller():
                v = helper(1)
                if v is None:
                    return ""
                return v.upper()
            """,
            """
            from typing import Optional

            def helper(x: int) -> Optional[str]:
                if x:
                    return "a"
                return None

            def caller():
                v = helper(1)
                if v is None:
                    return ""
                return v.upper()
            """,
            description="Hard negative: optional-by-design with correct guard",
            target_rules=ir_rules,
        ),
        _inline_case(
            "neg_dominating_guard",
            """
            def helper(x) -> str:
                if x:
                    return "a"

            def guarded():
                v = helper(1)
                if v is None:
                    return ""
                return v
            """,
            """
            def helper(x) -> str:
                if x:
                    return "a"

            def guarded():
                v = helper(1)
                if v is None:
                    return ""
                return v
            """,
            description="Hard negative: dominating guard excludes implicit-None path",
            target_rules=ir_rules,
        ),
        _inline_case(
            "neg_raise_only_exit",
            """
            def helper(x) -> str:
                if not x:
                    raise ValueError("x required")
                return "a"

            def caller():
                return helper(1).upper()
            """,
            """
            def helper(x) -> str:
                if not x:
                    raise ValueError("x required")
                return "a"

            def caller():
                return helper(1).upper()
            """,
            description="Hard negative: non-value branch exits via raise",
            target_rules=ir_rules,
        ),
        _inline_case(
            "neg_expected_negative_test",
            """
            def helper(x) -> str | None:
                if x:
                    return "a"

            def test_helper_may_be_none():
                assert helper(0) is None
            """,
            """
            def helper(x) -> str | None:
                if x:
                    return "a"

            def test_helper_may_be_none():
                assert helper(0) is None
            """,
            description="Hard negative: expected-negative test (None is allowed)",
            target_rules=ir_rules,
            test_documents=[
                {
                    "path": "tests/test_m.py",
                    "content": textwrap.dedent("""
                        from m import helper

                        def test_helper_may_be_none():
                            assert helper(0) is None
                    """),
                }
            ],
        ),
    ]


def build_expected_packets() -> List[Dict[str, Any]]:
    """Preregistered answer keys for the first batch (Phase 100A §4.4)."""
    return [
        {
            "case_id": "hold_black_executor",
            "bug_class": "return-contract",
            "gate_eligible_rule": "inconsistent_return",
            "expected_tier": "review_lead",
            "detector_expected_to_fire": "yes",
            "confirmed_eligible": False,
            "slice": "return_positive",
        },
        {
            "case_id": "hold_pysnooper_encoding",
            "bug_class": "return-contract",
            "gate_eligible_rule": "inconsistent_return",
            "expected_tier": "review_lead",
            "detector_expected_to_fire": "no",
            "confirmed_eligible": False,
            "slice": "return_positive",
        },
        {
            "case_id": "hold_tqdm_enumerate",
            "bug_class": "return-contract",
            "gate_eligible_rule": "inconsistent_return",
            "expected_tier": "review_lead",
            "detector_expected_to_fire": "no",
            "confirmed_eligible": False,
            "slice": "return_positive",
        },
        {
            "case_id": "dist_off_by_one",
            "bug_class": "distractor",
            "gate_eligible_rule": "none",
            "expected_tier": "refuted",
            "detector_expected_to_fire": "no",
            "confirmed_eligible": False,
            "slice": "distractor",
        },
        {
            "case_id": "dist_wrong_operator",
            "bug_class": "distractor",
            "gate_eligible_rule": "none",
            "expected_tier": "refuted",
            "detector_expected_to_fire": "no",
            "confirmed_eligible": False,
            "slice": "distractor",
        },
        {
            "case_id": "dist_missing_base_case",
            "bug_class": "distractor",
            "gate_eligible_rule": "none",
            "expected_tier": "refuted",
            "detector_expected_to_fire": "no",
            "confirmed_eligible": False,
            "slice": "distractor",
        },
        {
            "case_id": "neg_optional_by_design",
            "bug_class": "negative",
            "gate_eligible_rule": "inconsistent_return",
            "expected_tier": "refuted",
            "detector_expected_to_fire": "yes",
            "confirmed_eligible": False,
            "slice": "hard_negative",
        },
        {
            "case_id": "neg_dominating_guard",
            "bug_class": "negative",
            "gate_eligible_rule": "inconsistent_return",
            "expected_tier": "refuted",
            "detector_expected_to_fire": "yes",
            "confirmed_eligible": False,
            "slice": "hard_negative",
        },
        {
            "case_id": "neg_raise_only_exit",
            "bug_class": "negative",
            "gate_eligible_rule": "inconsistent_return",
            "expected_tier": "refuted",
            "detector_expected_to_fire": "no",
            "confirmed_eligible": False,
            "slice": "hard_negative",
        },
        {
            "case_id": "neg_expected_negative_test",
            "bug_class": "negative",
            "gate_eligible_rule": "inconsistent_return",
            "expected_tier": "refuted",
            "detector_expected_to_fire": "yes",
            "confirmed_eligible": False,
            "slice": "hard_negative",
        },
    ]


def materialize_corpus() -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": HBR.MANIFEST_SCHEMA_VERSION,
        "program_id": "phase100c-first-batch",
        "description": "Phase 100A first executable batch (cases 21–30)",
        "cases": build_first_batch_cases(),
    }
    expected = build_expected_packets()
    HBR.write_json(MANIFEST_PATH, manifest)
    HBR.write_json(EXPECTED_PATH, expected)
    return manifest, expected


def normalize_tier(value: str) -> str:
    key = str(value or TIER_REFUTED).strip().lower()
    return TIER_ALIASES.get(key, key if key in TIER_ORDER else TIER_REFUTED)


def case_predicted_tier(side: Dict[str, Any]) -> str:
    counts = side.get("by_classification") or {}
    for tier in TIER_ORDER:
        if counts.get(tier, 0) > 0:
            return tier
    return TIER_REFUTED


def build_confusion_matrix(
    rows: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    matrix = {pred: {exp: 0 for exp in TIER_ORDER} for pred in TIER_ORDER}
    for row in rows:
        pred = row["predicted_tier"]
        exp = row["expected_tier"]
        matrix[pred][exp] = matrix[pred].get(exp, 0) + 1
    return matrix


def compute_evaluation(
    case_results: Sequence[Dict[str, Any]],
    expected_packets: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    expected_by_id = {item["case_id"]: item for item in expected_packets}
    per_case: List[Dict[str, Any]] = []
    tier_counts = {tier: 0 for tier in TIER_ORDER}

    for result in case_results:
        case_id = result["case_id"]
        answer = expected_by_id.get(case_id, {})
        predicted = case_predicted_tier(result["buggy"])
        expected = normalize_tier(str(answer.get("expected_tier", TIER_REFUTED)))
        tier_counts[predicted] += 1
        per_case.append(
            {
                "case_id": case_id,
                "slice": answer.get("slice"),
                "predicted_tier": predicted,
                "expected_tier": expected,
                "tier_match": predicted == expected,
                "detected_on_buggy": result["summary"]["detected_on_buggy"],
                "detected_on_fixed": result["summary"]["detected_on_fixed"],
                "detected_buggy_only": result["summary"]["detected_buggy_only"],
                "buggy_buckets": dict(result["buggy"]["by_classification"]),
                "fixed_buckets": dict(result["fixed"]["by_classification"]),
                "confirmed_eligible": bool(answer.get("confirmed_eligible")),
            }
        )

    confusion = build_confusion_matrix(per_case)

    predicted_confirmed = [row for row in per_case if row["predicted_tier"] == TIER_DETECTED]
    expected_confirmed = [row for row in per_case if row["expected_tier"] == TIER_DETECTED]
    expected_confirmed_eligible = [row for row in per_case if row["confirmed_eligible"]]

    tp = sum(
        1 for row in per_case
        if row["predicted_tier"] == TIER_DETECTED and row["expected_tier"] == TIER_DETECTED
    )
    fp = sum(
        1 for row in per_case
        if row["predicted_tier"] == TIER_DETECTED and row["expected_tier"] != TIER_DETECTED
    )
    fn = sum(
        1 for row in per_case
        if row["predicted_tier"] != TIER_DETECTED and row["expected_tier"] == TIER_DETECTED
    )

    fixed_fp = sum(1 for row in per_case if row["detected_on_fixed"])

    recall_denominator = len(expected_confirmed) if expected_confirmed else len(expected_confirmed_eligible)
    recall_numerator = tp if expected_confirmed else sum(
        1 for row in per_case
        if row["predicted_tier"] == TIER_DETECTED and row["confirmed_eligible"]
    )

    return {
        "per_case": per_case,
        "buggy_tier_counts": tier_counts,
        "confusion_matrix": confusion,
        "confirmed": {
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "predicted_count": len(predicted_confirmed),
            "expected_count": len(expected_confirmed),
            "confirmed_eligible_count": len(expected_confirmed_eligible),
            "precision": round(tp / (tp + fp), 4) if (tp + fp) else None,
            "recall": round(recall_numerator / recall_denominator, 4) if recall_denominator else None,
            "recall_denominator_note": (
                "expected_tier=confirmed_defect"
                if expected_confirmed
                else "confirmed_eligible positives (none with expected confirmed in this batch)"
            ),
            "fixed_version_confirmed_count": fixed_fp,
            "directional_purity_cases": sum(1 for row in per_case if row["detected_buggy_only"]),
        },
        "tier_accuracy": round(
            sum(1 for row in per_case if row["tier_match"]) / len(per_case), 4
        ) if per_case else None,
    }


def render_confusion_table(matrix: Dict[str, Any]) -> List[str]:
    header = "| Predicted \\ Expected | " + " | ".join(f"`{tier}`" for tier in TIER_ORDER) + " |"
    sep = "|---|" + "|".join("---:" for _ in TIER_ORDER) + "|"
    lines = [header, sep]
    for pred in TIER_ORDER:
        cells = " | ".join(str(matrix[pred].get(exp, 0)) for exp in TIER_ORDER)
        lines.append(f"| `{pred}` | {cells} |")
    return lines


def write_report(
    manifest: Dict[str, Any],
    evaluation: Dict[str, Any],
    metrics: Dict[str, Any],
    elapsed_s: float,
) -> None:
    confirmed = evaluation["confirmed"]
    tier_counts = evaluation["buggy_tier_counts"]
    lines = [
        "# Phase 100C — Historical Confirmation Execution",
        "",
        "**Status:** Execution complete",
        f"**Date:** {time.strftime('%Y-%m-%d')}",
        "**Scope:** Phase 100A first batch (cases 21–30) via Phase 99D replay harness",
        "**Constraints:** No detector or benchmark changes",
        "",
        "---",
        "",
        "## 1. Executive summary",
        "",
        f"| Item | Value |",
        f"|------|-------|",
        f"| Corpus | `{MANIFEST_PATH.relative_to(ROOT).as_posix()}` |",
        f"| Cases materialized | {len(manifest['cases'])} |",
        f"| Replay output | `{OUTPUT_DIR.relative_to(ROOT).as_posix()}/` |",
        f"| Builder Core commit | `{_git_head()}` |",
        f"| Elapsed | {elapsed_s:.1f}s |",
        "",
        "This run executes the **first zero-setup slice** of the Phase 100A corpus:",
        "3 in-repo return holdout pairs, 3 distractor pairs, and 4 curated hard negatives.",
        "BugsInPy git-backed positives (cases 1–20) are deferred to a later materialization pass.",
        "",
        "---",
        "",
        "## 2. Tier distribution (buggy revision, case-level)",
        "",
        "Each case receives one tier: the highest gate bucket present among target-rule findings.",
        "",
        "| Tier | Cases |",
        "|------|------:|",
    ]
    for tier in TIER_ORDER:
        lines.append(f"| `{tier}` | {tier_counts.get(tier, 0)} |")

    lines.extend([
        "",
        "### Aggregate finding counts (buggy / fixed)",
        "",
        "| Bucket | Buggy findings | Fixed findings |",
        "|--------|---------------:|---------------:|",
    ])
    for bucket in TIER_ORDER:
        lines.append(
            f"| `{bucket}` | {metrics['buggy'].get(bucket, 0)} | "
            f"{metrics['fixed'].get(bucket, 0)} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 3. Confusion matrix (predicted vs expected tier)",
        "",
        "Expected tiers are preregistered in `expected_packets.json` (Phase 100A §4.4).",
        "",
        *render_confusion_table(evaluation["confusion_matrix"]),
        "",
        f"**Tier accuracy:** {evaluation['tier_accuracy']}",
        "",
        "---",
        "",
        "## 4. Confirmed precision and recall",
        "",
        "| Metric | Value |",
        "|--------|------:|",
        f"| True positives (predicted confirmed ∧ expected confirmed) | {confirmed['true_positives']} |",
        f"| False positives (predicted confirmed ∧ expected ≠ confirmed) | {confirmed['false_positives']} |",
        f"| False negatives (expected confirmed ∧ not predicted confirmed) | {confirmed['false_negatives']} |",
        f"| Predicted confirmed (buggy, case-level) | {confirmed['predicted_count']} |",
        f"| Expected confirmed | {confirmed['expected_count']} |",
        f"| Confirmed-eligible positives in batch | {confirmed['confirmed_eligible_count']} |",
        f"| **Confirmed precision** | {confirmed['precision']} |",
        f"| **Confirmed recall** | {confirmed['recall']} |",
        f"| Recall denominator | {confirmed['recall_denominator_note']} |",
        f"| Confirmed on fixed revision (must be 0) | {confirmed['fixed_version_confirmed_count']} |",
        f"| Directional purity (buggy-only detected cases) | {confirmed['directional_purity_cases']} |",
        "",
        "**Interpretation:** This first batch contains **no confirmed-eligible positives**",
        "(no bound trigger tests on return holdout pairs). Confirmed recall is therefore",
        "not yet meaningful against the full 100A target (≥12 confirmed-eligible positives).",
        "Precision is reported as `null` when no confirmed predictions occur.",
        "",
        "---",
        "",
        "## 5. Per-case results",
        "",
        "| Case | Slice | Predicted | Expected | Match | Detected buggy | Detected fixed |",
        "|------|-------|-----------|----------|:-----:|:--------------:|:--------------:|",
    ])
    for row in evaluation["per_case"]:
        lines.append(
            f"| `{row['case_id']}` | {row.get('slice', '')} | `{row['predicted_tier']}` | "
            f"`{row['expected_tier']}` | {'yes' if row['tier_match'] else 'no'} | "
            f"{row['detected_on_buggy']} | {row['detected_on_fixed']} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 6. Artifacts",
        "",
        "| File | Description |",
        "|------|-------------|",
        f"| `{MANIFEST_PATH.relative_to(ROOT).as_posix()}` | Replay manifest |",
        f"| `{EXPECTED_PATH.relative_to(ROOT).as_posix()}` | Preregistered expected tiers |",
        f"| `{OUTPUT_DIR.relative_to(ROOT).as_posix()}/results.json` | Full replay output |",
        f"| `{OUTPUT_DIR.relative_to(ROOT).as_posix()}/metrics.json` | 99D aggregate metrics |",
        f"| `{OUTPUT_DIR.relative_to(ROOT).as_posix()}/evaluation.json` | Confusion matrix + precision/recall |",
        f"| `{OUTPUT_DIR.relative_to(ROOT).as_posix()}/report.md` | 99D harness report |",
        "",
        "---",
        "",
        "## 7. Safety and neutrality",
        "",
        "- Replay ran with `HISTORICAL_BUG_REPLAY_ENABLED` bypass via explicit enablement only.",
        "- Confirmed-defect gate and evidence promotion were enabled in-session only (99D).",
        "- No detector, benchmark, or finding-schema changes were made.",
        "- QuixBugs / holdout benchmark oracles were not modified.",
        "",
        "---",
        "",
        "## 8. Next steps",
        "",
        "1. Materialize BugsInPy git-backed cases (100A §3.1) with trigger tests for confirmed-eligible recall.",
        "2. Dual-review expected packets before expanding the frozen corpus.",
        "3. Re-run this script after corpus expansion; recall denominator requires ≥1 expected confirmed tier.",
        "",
    ])
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_execution() -> Dict[str, Any]:
    started = time.time()
    manifest, expected = materialize_corpus()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    program = HBR.run_replay(manifest, OUTPUT_DIR, enabled=True)
    metrics_payload = HBR.load_json(OUTPUT_DIR / "metrics.json")
    metrics = metrics_payload["metrics"]
    evaluation = compute_evaluation(program["cases"], expected)
    HBR.write_json(OUTPUT_DIR / "evaluation.json", evaluation)
    elapsed = time.time() - started
    write_report(manifest, evaluation, metrics, elapsed)
    return {
        "manifest": manifest,
        "metrics": metrics,
        "evaluation": evaluation,
        "elapsed_s": elapsed,
    }


def main() -> int:
    result = run_execution()
    print(f"Phase 100C complete in {result['elapsed_s']:.1f}s")
    print(f"Report: {REPORT_PATH}")
    print(f"Artifacts: {OUTPUT_DIR}")
    confirmed = result["evaluation"]["confirmed"]
    print(
        f"Confirmed precision={confirmed['precision']} recall={confirmed['recall']} "
        f"predicted={confirmed['predicted_count']} fixed_fp={confirmed['fixed_version_confirmed_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
