"""Historical bug replay harness (Phase 99D).

Replays buggy/fixed revisions through the unified analysis pipeline with the
confirmed-defect gate enabled for measurement only. Read-only; no detector or
benchmark changes.
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from builder_core.bug_intelligence import confirmed_defect_gate as CDG
from builder_core.bug_intelligence import engine
from builder_core.bug_intelligence import verification_evidence as VE
from builder_core.bug_intelligence.finding import Finding

HISTORICAL_BUG_REPLAY_ENABLED = False

MANIFEST_SCHEMA_VERSION = 1
RESULT_SCHEMA_VERSION = 1

OUTPUT_DETECTED = "detected"
OUTPUT_STRONG_SUSPECT = "strong_suspect"
OUTPUT_REVIEW_LEAD = "review_lead"
OUTPUT_REFUTED = "refuted"
OUTPUT_UNKNOWN = "unknown"

OUTPUT_BUCKETS = (
    OUTPUT_DETECTED,
    OUTPUT_STRONG_SUSPECT,
    OUTPUT_REVIEW_LEAD,
    OUTPUT_REFUTED,
)

_GATE_TO_OUTPUT = {
    CDG.CLASS_CONFIRMED: OUTPUT_DETECTED,
    CDG.CLASS_STRONG_SUSPECT: OUTPUT_STRONG_SUSPECT,
    CDG.CLASS_REVIEW_LEAD: OUTPUT_REVIEW_LEAD,
    CDG.CLASS_REFUTED: OUTPUT_REFUTED,
}

_REQUIRED_CASE_FIELDS = ("id", "buggy_revision", "fixed_revision")


def write_json(path: str | Path, value: Any) -> None:
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _empty_bucket_counts() -> Dict[str, int]:
    counts = {bucket: 0 for bucket in OUTPUT_BUCKETS}
    counts[OUTPUT_UNKNOWN] = 0
    return counts


def _git_show(repo_path: str | Path, ref: str, file_path: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo_path), "show", f"{ref}:{file_path}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if proc.returncode != 0:
        raise ValueError(
            f"cannot read {file_path} at {ref}: {proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout


def _read_file(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8-sig", errors="ignore")


def _revision_label(revision: Dict[str, Any]) -> str:
    kind = revision.get("kind", "file")
    if kind == "git":
        return f"{revision.get('repo_path')}@{revision.get('ref')}"
    if kind == "inline":
        return str(revision.get("rel_path") or "<inline>")
    return str(revision.get("path") or revision.get("rel_path") or "<file>")


def _resolve_revision_sources(revision: Dict[str, Any]) -> Tuple[List[Tuple[str, str]], Dict[str, Any]]:
    kind = revision.get("kind", "file")
    if kind == "inline":
        rel = str(revision.get("rel_path") or "<source>")
        source = revision.get("source")
        if not isinstance(source, str):
            raise ValueError("inline revision requires string 'source'")
        return [(rel, source)], {"kind": "inline", "label": _revision_label(revision)}

    if kind == "file":
        path = Path(revision["path"])
        if not path.is_file():
            raise ValueError(f"revision file not found: {path}")
        rel = str(revision.get("rel_path") or path.name)
        return [(rel, _read_file(path))], {"kind": "file", "label": str(path.resolve())}

    if kind == "git":
        repo_path = Path(revision["repo_path"])
        ref = str(revision["ref"])
        files = revision.get("files")
        if not files:
            file_path = revision.get("file")
            if not file_path:
                raise ValueError("git revision requires 'file' or 'files'")
            files = [file_path]
        sources: List[Tuple[str, str]] = []
        for file_path in files:
            rel = str(file_path).replace("\\", "/")
            sources.append((rel, _git_show(repo_path, ref, rel)))
        return sources, {"kind": "git", "label": _revision_label(revision), "ref": ref}

    raise ValueError(f"unsupported revision kind: {kind}")


def validate_manifest(manifest: Dict[str, Any]) -> List[str]:
    issues: List[str] = []
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        issues.append(f"schema_version must be {MANIFEST_SCHEMA_VERSION}")
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        issues.append("'cases' must be a non-empty list")
        return issues
    seen: set[str] = set()
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            issues.append(f"cases[{index}] must be an object")
            continue
        normalized = _normalize_case(case)
        for field in _REQUIRED_CASE_FIELDS:
            if field not in normalized:
                issues.append(f"cases[{index}] missing required field '{field}'")
        case_id = case.get("id")
        if case_id in seen:
            issues.append(f"duplicate case id '{case_id}'")
        seen.add(str(case_id))
    return issues


def _normalize_case(case: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(case)
    if "pair_dir" in case and "buggy_revision" not in case:
        pair_dir = Path(case["pair_dir"])
        normalized["buggy_revision"] = {
            "kind": "file",
            "path": str(pair_dir / "buggy.py"),
            "rel_path": case.get("buggy_rel_path", "buggy.py"),
        }
        normalized["fixed_revision"] = {
            "kind": "file",
            "path": str(pair_dir / "fixed.py"),
            "rel_path": case.get("fixed_rel_path", "fixed.py"),
        }
    return normalized


@contextlib.contextmanager
def _confirmation_pipeline_enabled():
    old_gate = CDG.CONFIRMED_DEFECT_GATE_ENABLED
    old_promo = VE.EVIDENCE_PROMOTION_ENABLED
    CDG.CONFIRMED_DEFECT_GATE_ENABLED = True
    VE.EVIDENCE_PROMOTION_ENABLED = True
    try:
        yield
    finally:
        CDG.CONFIRMED_DEFECT_GATE_ENABLED = old_gate
        VE.EVIDENCE_PROMOTION_ENABLED = old_promo


def _output_bucket(finding: Finding) -> str:
    gate = finding.confirmed_defect_classification
    if not gate:
        return OUTPUT_REFUTED
    return _GATE_TO_OUTPUT.get(gate.get("classification"), OUTPUT_REFUTED)


def _finding_record(finding: Finding) -> Dict[str, Any]:
    gate = finding.confirmed_defect_classification or {}
    contract = finding.contract_review or {}
    verification = finding.verification_evidence or {}
    return {
        "id": finding.id,
        "rule": finding.rule,
        "kind": finding.kind,
        "file": finding.file,
        "line": finding.line,
        "function": finding.function,
        "severity": finding.severity,
        "confidence": finding.confidence,
        "classification": _output_bucket(finding),
        "gate": gate or None,
        "contract_review_status": contract.get("review_packet_status"),
        "verification_status": verification.get("status"),
    }


def _matches_target_files(record: Dict[str, Any], target_files: Sequence[str]) -> bool:
    if not target_files:
        return True
    file_name = os.path.basename(record["file"])
    normalized = {str(path).replace("\\", "/") for path in target_files}
    return record["file"] in normalized or file_name in normalized


def analyze_revision(
    revision: Dict[str, Any],
    *,
    test_documents: Optional[Sequence[Dict[str, str]]] = None,
    target_rules: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Run analysis + overlays + gate for one revision snapshot."""
    sources, meta = _resolve_revision_sources(revision)
    rules = set(target_rules or [])
    records: List[Dict[str, Any]] = []
    with _confirmation_pipeline_enabled():
        for rel_path, text in sources:
            result = engine.analyze_source(
                text,
                rel_path,
                test_documents=list(test_documents or []),
            )
            for finding in result.findings:
                if rules and finding.rule not in rules:
                    continue
                records.append(_finding_record(finding))

    records.sort(key=lambda item: (item["file"], item["line"], item["rule"], item["id"]))
    buckets = _empty_bucket_counts()
    for record in records:
        bucket = record["classification"]
        if bucket in buckets:
            buckets[bucket] += 1

    return {
        "revision": meta,
        "findings": records,
        "by_classification": buckets,
        "pipeline": {
            "analysis": True,
            "contract_review": True,
            "verification_evidence": True,
            "confirmed_defect_gate": True,
        },
    }


def replay_case(case: Dict[str, Any]) -> Dict[str, Any]:
    """Replay one buggy/fixed case and return structured results."""
    normalized = _normalize_case(case)
    test_documents = normalized.get("test_documents")
    target_rules = normalized.get("target_rules")
    target_files = normalized.get("fixed_files") or []

    buggy = analyze_revision(
        normalized["buggy_revision"],
        test_documents=test_documents,
        target_rules=target_rules,
    )
    fixed = analyze_revision(
        normalized["fixed_revision"],
        test_documents=test_documents,
        target_rules=target_rules,
    )

    def _target_detected(side: Dict[str, Any]) -> bool:
        for record in side["findings"]:
            if record["classification"] != OUTPUT_DETECTED:
                continue
            if _matches_target_files(record, target_files):
                return True
        return side["by_classification"].get(OUTPUT_DETECTED, 0) > 0 and not target_files

    buggy_detected = _target_detected(buggy)
    fixed_detected = _target_detected(fixed)

    return {
        "case_id": normalized["id"],
        "description": normalized.get("description", ""),
        "buggy_revision": _revision_label(normalized["buggy_revision"]),
        "fixed_revision": _revision_label(normalized["fixed_revision"]),
        "target_files": list(target_files),
        "target_rules": list(target_rules or []),
        "buggy": buggy,
        "fixed": fixed,
        "summary": {
            "detected_on_buggy": buggy_detected,
            "detected_on_fixed": fixed_detected,
            "detected_buggy_only": buggy_detected and not fixed_detected,
            "detected_both": buggy_detected and fixed_detected,
            "detected_neither": not buggy_detected and not fixed_detected,
        },
    }


def aggregate_metrics(case_results: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    buggy_counts = _empty_bucket_counts()
    fixed_counts = _empty_bucket_counts()
    detected_on_buggy = 0
    detected_on_fixed = 0
    detected_buggy_only = 0

    for result in case_results:
        for bucket, count in result["buggy"]["by_classification"].items():
            buggy_counts[bucket] = buggy_counts.get(bucket, 0) + count
        for bucket, count in result["fixed"]["by_classification"].items():
            fixed_counts[bucket] = fixed_counts.get(bucket, 0) + count
        if result["summary"]["detected_on_buggy"]:
            detected_on_buggy += 1
        if result["summary"]["detected_on_fixed"]:
            detected_on_fixed += 1
        if result["summary"]["detected_buggy_only"]:
            detected_buggy_only += 1

    total = len(case_results)
    return {
        "cases_evaluated": total,
        "buggy": buggy_counts,
        "fixed": fixed_counts,
        "cases_with_detected_on_buggy": detected_on_buggy,
        "cases_with_detected_on_fixed": detected_on_fixed,
        "cases_with_detected_buggy_only": detected_buggy_only,
        "detected_case_recall": round(detected_on_buggy / total, 4) if total else None,
        "detected_case_false_positive_rate": round(detected_on_fixed / total, 4) if total else None,
        "detected_case_purity": round(detected_buggy_only / detected_on_buggy, 4)
        if detected_on_buggy
        else None,
    }


def run_replay(
    manifest: Dict[str, Any],
    output_dir: str | Path,
    *,
    enabled: Optional[bool] = None,
) -> Dict[str, Any]:
    """Execute replay for all manifest cases and write JSON artifacts."""
    if enabled is None:
        enabled = HISTORICAL_BUG_REPLAY_ENABLED
    if not enabled:
        raise ValueError("historical bug replay is disabled (HISTORICAL_BUG_REPLAY_ENABLED=False)")

    issues = validate_manifest(manifest)
    if issues:
        raise ValueError("invalid manifest: " + "; ".join(issues))

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    case_results = [replay_case(case) for case in manifest["cases"]]
    metrics = aggregate_metrics(case_results)
    program = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "program_id": manifest.get("program_id", "historical-bug-replay"),
        "replay_enabled": True,
        "cases": case_results,
    }
    metrics_payload = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "program_id": program["program_id"],
        "metrics": metrics,
    }

    write_json(output / "results.json", program)
    write_json(output / "metrics.json", metrics_payload)
    (output / "report.md").write_text(generate_report(program, metrics), encoding="utf-8")
    return program


def generate_report(program: Dict[str, Any], metrics: Dict[str, Any]) -> str:
    lines = [
        "# Historical Bug Replay Report",
        "",
        f"Program: {program.get('program_id')}",
        f"Cases: {metrics['cases_evaluated']}",
        "",
        "## Aggregate classifications",
        "",
        "| Bucket | Buggy revision | Fixed revision |",
        "|--------|---------------:|---------------:|",
    ]
    for bucket in (*OUTPUT_BUCKETS, OUTPUT_UNKNOWN):
        lines.append(
            f"| `{bucket}` | {metrics['buggy'].get(bucket, 0)} | "
            f"{metrics['fixed'].get(bucket, 0)} |"
        )
    lines.extend([
        "",
        "## Case-level detected summary",
        "",
        f"- cases with detected on buggy: {metrics['cases_with_detected_on_buggy']}",
        f"- cases with detected on fixed: {metrics['cases_with_detected_on_fixed']}",
        f"- cases with detected on buggy only: {metrics['cases_with_detected_buggy_only']}",
        f"- detected case recall: {metrics['detected_case_recall']}",
        f"- detected case false-positive rate: {metrics['detected_case_false_positive_rate']}",
        f"- detected case purity: {metrics['detected_case_purity']}",
        "",
        "## Per-case results",
        "",
    ])
    for case in program["cases"]:
        lines.append(
            f"- `{case['case_id']}`: buggy detected={case['summary']['detected_on_buggy']} "
            f"fixed detected={case['summary']['detected_on_fixed']}"
        )
    lines.append("")
    return "\n".join(lines)
