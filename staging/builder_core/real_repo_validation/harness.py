"""Phase 95A real-repository validation harness.

This module measures the frozen unified engine. It does not execute target code,
change detectors, alter findings, or write inside a target repository.
"""

from __future__ import annotations

import hashlib
import json
import os
import statistics
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from builder_core.bug_intelligence import engine, engine_benchmark

MANIFEST_SCHEMA_VERSION = 1
EXPORT_SCHEMA_VERSION = 1
REVIEW_SCHEMA_VERSION = 1
REPORT_SCHEMA_VERSION = 1

LABELS = {
    "confirmed_actionable",
    "useful_review_lead",
    "benign_or_intended",
    "misleading",
    "undecidable",
    "out_of_scope",
    "unreviewed",
}
IN_SCOPE_LABELS = {
    "confirmed_actionable",
    "useful_review_lead",
    "benign_or_intended",
    "misleading",
    "undecidable",
}
USEFULNESS_MIN, USEFULNESS_MAX = 0, 4
REPO_USEFULNESS_MIN, REPO_USEFULNESS_MAX = 1, 5
SIZE_BANDS = {"small", "medium", "large", "stress"}
LANGUAGE_PROFILES = {
    "python_dominant",
    "python_centered_polyglot",
    "python_secondary",
}
OUTCOMES = {"success", "degraded", "failed", "unsafe", "unavailable"}
TRACKS = {"primary", "pilot", "stress"}

# Real-repository review includes every grounded product kind. The algorithm
# benchmark excludes security findings only because security is out of band for
# that paired algorithm corpus; Phase 95 must still review grounded security.
VERDICT_KINDS = set(engine_benchmark.GROUNDED_KINDS)
BUG_CATEGORIES = set(engine_benchmark.BUG_CATEGORIES)

_REQUIRED_REPO_FIELDS = (
    "id",
    "path",
    "commit",
    "license",
    "size_band",
    "language_profile",
    "project_shape",
    "selection_rationale",
)
_REQUIRED_HISTORICAL_FIELDS = (
    "id",
    "repo_id",
    "parent_commit",
    "fix_commit",
    "description",
    "fixed_files",
)
_SOURCE_WINDOW_RADIUS = 3
_MAX_SNAPSHOT_FILES = 100_000


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_json(path: str | Path, value: Any) -> None:
    Path(path).write_text(_stable_json(value), encoding="utf-8")


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _git(args: List[str], cwd: str) -> Optional[str]:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def candidate_record() -> Dict[str, Any]:
    """Record the frozen candidate without mutating configuration."""
    from builder_core.bug_intelligence import cross_file, fact_detectors

    repo_root = str(Path(__file__).resolve().parents[2])
    return {
        "builder_core_commit": _git(["rev-parse", "HEAD"], repo_root) or "unknown",
        "frozen_flags": {
            "CROSS_FILE_CONSUMPTION_ENABLED": fact_detectors.CROSS_FILE_CONSUMPTION_ENABLED,
            "CROSS_FILE_ENABLED": cross_file.CROSS_FILE_ENABLED,
            "INTERPROC_PROMOTION_ENABLED": fact_detectors.INTERPROC_PROMOTION_ENABLED,
        },
        "real_repo_verdict_kinds": sorted(VERDICT_KINDS),
    }


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------
def load_manifest(path: str | Path) -> Dict[str, Any]:
    return load_json(path)


def _repo_metadata(repo: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "track": repo.get("track", "primary"),
        "primary_eligible": repo.get("primary_eligible", True),
        "eligibility_note": repo.get("eligibility_note", ""),
        "size_band": repo.get("size_band"),
        "language_profile": repo.get("language_profile"),
        "project_shape": repo.get("project_shape"),
        "python_loc": repo.get("python_loc"),
        "python_files": repo.get("python_files"),
    }


def validate_manifest(manifest: Dict[str, Any]) -> List[str]:
    issues: List[str] = []
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        issues.append(f"schema_version must be {MANIFEST_SCHEMA_VERSION}")
    if not manifest.get("program_id"):
        issues.append("manifest missing required field 'program_id'")
    candidate = manifest.get("candidate")
    if not isinstance(candidate, dict):
        issues.append("manifest missing required 'candidate' object")
    else:
        if not candidate.get("builder_core_commit"):
            issues.append("candidate missing required field 'builder_core_commit'")
        if not isinstance(candidate.get("frozen_flags"), dict):
            issues.append("candidate missing required 'frozen_flags' object")
    repos = manifest.get("repositories")
    if not isinstance(repos, list) or not repos:
        issues.append("manifest has no non-empty 'repositories' list")
        return issues

    seen = set()
    for index, repo in enumerate(repos):
        if not isinstance(repo, dict):
            issues.append(f"repository[{index}] must be an object")
            continue
        for field in _REQUIRED_REPO_FIELDS:
            if not repo.get(field):
                issues.append(f"repository[{index}] missing required field '{field}'")
        repo_id = repo.get("id")
        if repo_id in seen:
            issues.append(f"duplicate repository id '{repo_id}'")
        seen.add(repo_id)
        if repo.get("size_band") not in SIZE_BANDS:
            issues.append(f"repository[{index}] has invalid size_band '{repo.get('size_band')}'")
        if repo.get("language_profile") not in LANGUAGE_PROFILES:
            issues.append(
                f"repository[{index}] has invalid language_profile "
                f"'{repo.get('language_profile')}'"
            )
        if repo.get("track", "primary") not in TRACKS:
            issues.append(f"repository[{index}] has invalid track '{repo.get('track')}'")
        if not isinstance(repo.get("primary_eligible", True), bool):
            issues.append(f"repository[{index}] primary_eligible must be true or false")
    historical = manifest.get("historical_bugs", [])
    if not isinstance(historical, list):
        issues.append("'historical_bugs' must be a list when present")
    else:
        repo_ids = {repo.get("id") for repo in repos if isinstance(repo, dict)}
        historical_ids = set()
        for index, case in enumerate(historical):
            if not isinstance(case, dict):
                issues.append(f"historical_bugs[{index}] must be an object")
                continue
            for field in _REQUIRED_HISTORICAL_FIELDS:
                if not case.get(field):
                    issues.append(f"historical_bugs[{index}] missing required field '{field}'")
            if case.get("id") in historical_ids:
                issues.append(f"duplicate historical bug id '{case.get('id')}'")
            historical_ids.add(case.get("id"))
            if case.get("repo_id") not in repo_ids:
                issues.append(
                    f"historical_bugs[{index}] references unknown repo_id '{case.get('repo_id')}'"
                )
    return issues


def _normalized_manifest(manifest: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(manifest)
    normalized["repositories"] = sorted(
        [dict(repo) for repo in manifest["repositories"]], key=lambda repo: repo["id"]
    )
    normalized["historical_bugs"] = sorted(
        [dict(case) for case in manifest.get("historical_bugs", [])],
        key=lambda case: case["id"],
    )
    normalized["sampling_seed"] = str(manifest.get("sampling_seed", "phase95"))
    return normalized


# ---------------------------------------------------------------------------
# Read-only safety snapshots
# ---------------------------------------------------------------------------
def _tracked_files(root: str) -> Optional[List[str]]:
    raw = _git(["ls-files", "-z"], root)
    if raw is None:
        return None
    return sorted(item for item in raw.split("\0") if item)


def _fallback_files(root: str) -> List[str]:
    files: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in engine.SKIP_DIRS)
        for filename in sorted(filenames):
            path = os.path.join(dirpath, filename)
            files.append(os.path.relpath(path, root).replace("\\", "/"))
            if len(files) >= _MAX_SNAPSHOT_FILES:
                return files
    return files


def _hash_files(root: str, paths: Iterable[str]) -> Dict[str, str]:
    hashes: Dict[str, str] = {}
    for rel in list(paths)[:_MAX_SNAPSHOT_FILES]:
        path = os.path.join(root, rel.replace("/", os.sep))
        try:
            with open(path, "rb") as handle:
                hashes[rel] = hashlib.sha256(handle.read()).hexdigest()
        except OSError:
            hashes[rel] = "<unreadable>"
    return hashes


def snapshot_repo(root: str) -> Dict[str, Any]:
    tracked = _tracked_files(root)
    source = "git_tracked" if tracked is not None else "filesystem_fallback"
    paths = tracked if tracked is not None else _fallback_files(root)
    return {
        "git_status": _git(["status", "--short"], root),
        "snapshot_source": source,
        "snapshot_file_count": len(paths),
        "snapshot_truncated": len(paths) >= _MAX_SNAPSHOT_FILES,
        "file_hashes": _hash_files(root, paths),
    }


def compare_snapshots(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    before_hashes = before["file_hashes"]
    after_hashes = after["file_hashes"]
    modified = sorted(
        path
        for path in set(before_hashes) | set(after_hashes)
        if before_hashes.get(path) != after_hashes.get(path)
    )
    git_changed = before.get("git_status") != after.get("git_status")
    complete = not before.get("snapshot_truncated") and not after.get("snapshot_truncated")
    return {
        "complete": complete,
        "git_status_changed": git_changed,
        "modified_tracked_files": modified,
        "safe": complete and not git_changed and not modified,
    }


# ---------------------------------------------------------------------------
# Finding export
# ---------------------------------------------------------------------------
def _is_verdict_eligible(finding: Any) -> bool:
    return finding.category in BUG_CATEGORIES and finding.kind in VERDICT_KINDS


def _record_id(repo_id: str, finding: Any) -> str:
    payload = "|".join(
        (repo_id, finding.id, finding.file, str(finding.line), finding.rule, finding.kind)
    )
    return "RR-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _source_window(repo_path: str, rel_path: str, line: int) -> List[str]:
    path = os.path.join(repo_path, rel_path.replace("/", os.sep))
    try:
        lines = Path(path).read_text(encoding="utf-8-sig", errors="ignore").splitlines()
    except OSError:
        return []
    low = max(0, line - 1 - _SOURCE_WINDOW_RADIUS)
    high = min(len(lines), line + _SOURCE_WINDOW_RADIUS)
    return [f"{index + 1}: {lines[index]}" for index in range(low, high)]


def finding_record(finding: Any, repo: Dict[str, Any]) -> Dict[str, Any]:
    record = finding.to_dict()
    record.update(
        {
            "export_schema_version": EXPORT_SCHEMA_VERSION,
            "record_id": _record_id(repo["id"], finding),
            "repo_id": repo["id"],
            "sampling_probability": 1.0,
            "source_window": _source_window(repo["path"], finding.file, finding.line),
            "verdict_eligible": _is_verdict_eligible(finding),
            **_repo_metadata(repo),
        }
    )
    return record


def _record_sort_key(record: Dict[str, Any]) -> tuple:
    return (
        record.get("repo_id", ""),
        record.get("file", ""),
        int(record.get("line", 0)),
        record.get("rule", ""),
        record.get("record_id", ""),
    )


def export_findings(records: List[Dict[str, Any]], path: str | Path) -> None:
    write_json(path, sorted(records, key=_record_sort_key))


# ---------------------------------------------------------------------------
# Evaluation runner
# ---------------------------------------------------------------------------
def _base_scan(repo: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "repo_id": repo["id"],
        "path": os.path.abspath(repo["path"]),
        "expected_commit": repo["commit"],
        "metadata": _repo_metadata(repo),
        "records": [],
        "errors": [],
        "advisory_count": 0,
        "files_with_parse_errors": 0,
        "verdict_eligible_count": 0,
    }


def scan_repository(repo: Dict[str, Any]) -> Dict[str, Any]:
    scan = _base_scan(repo)
    path = scan["path"]
    if not os.path.isdir(path):
        scan.update({"outcome": "unavailable", "errors": ["repository path not found"]})
        return scan

    actual_commit = _git(["rev-parse", "HEAD"], path)
    scan["actual_commit"] = actual_commit
    if actual_commit != repo["commit"]:
        scan.update(
            {
                "outcome": "failed",
                "errors": ["checkout commit does not match manifest commit"],
            }
        )
        return scan

    before = snapshot_repo(path)
    started = time.perf_counter()
    try:
        results = engine.analyze_repository(path)
        outcome = "success"
    except Exception as exc:  # isolate one repository without leaking exception text
        results = []
        outcome = "failed"
        scan["errors"].append(f"analysis failed: {type(exc).__name__}")
    scan["duration_seconds"] = round(time.perf_counter() - started, 3)
    after = snapshot_repo(path)
    safety = compare_snapshots(before, after)

    records: List[Dict[str, Any]] = []
    parse_errors = 0
    for result in results:
        parse_errors += bool(result.errors)
        records.extend(finding_record(finding, repo) for finding in result.findings)
    records.sort(key=_record_sort_key)

    if not safety["safe"]:
        outcome = "unsafe"
    elif outcome == "success" and (parse_errors or not safety["complete"]):
        outcome = "degraded"

    scan.update(
        {
            "outcome": outcome,
            "safety": safety,
            "records": records,
            "files_with_parse_errors": parse_errors,
            "verdict_eligible_count": sum(r["verdict_eligible"] for r in records),
            "advisory_count": sum(not r["verdict_eligible"] for r in records),
        }
    )
    return scan


def run_program(manifest: Dict[str, Any]) -> Dict[str, Any]:
    issues = validate_manifest(manifest)
    if issues:
        raise ValueError("invalid manifest: " + "; ".join(issues))
    current_candidate = candidate_record()
    expected_candidate = manifest["candidate"]
    if expected_candidate["builder_core_commit"] != current_candidate["builder_core_commit"]:
        raise ValueError("frozen Builder Core commit does not match manifest candidate")
    if expected_candidate["frozen_flags"] != current_candidate["frozen_flags"]:
        raise ValueError("frozen Builder Core flags do not match manifest candidate")
    scans = [scan_repository(repo) for repo in _normalized_manifest(manifest)["repositories"]]
    return {
        "program_schema_version": EXPORT_SCHEMA_VERSION,
        "program_id": manifest["program_id"],
        "candidate": current_candidate,
        "repositories_in_manifest": len(scans),
        "scans": scans,
    }


def all_records(program: Dict[str, Any]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for scan in program["scans"]:
        records.extend(scan.get("records", []))
    return sorted(records, key=_record_sort_key)


def finding_inventory(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    verdict = [record for record in records if record["verdict_eligible"]]
    advisory = [record for record in records if not record["verdict_eligible"]]

    def _counts(key: str, items: List[Dict[str, Any]]) -> Dict[str, int]:
        values: Dict[str, int] = {}
        for item in items:
            value = str(item.get(key) or "unknown")
            values[value] = values.get(value, 0) + 1
        return dict(sorted(values.items()))

    return {
        "total_findings": len(records),
        "verdict_eligible_findings": len(verdict),
        "advisory_findings": len(advisory),
        "verdict_by_kind": _counts("kind", verdict),
        "advisory_by_kind": _counts("kind", advisory),
    }


def corpus_summary(manifest: Dict[str, Any], program: Dict[str, Any]) -> Dict[str, Any]:
    repos = _normalized_manifest(manifest)["repositories"]
    primary = [
        repo for repo in repos
        if repo.get("track", "primary") == "primary" and repo.get("primary_eligible", True)
    ]

    def _counts(key: str, items: List[Dict[str, Any]]) -> Dict[str, int]:
        values: Dict[str, int] = {}
        for item in items:
            value = str(item.get(key) or "unknown")
            values[value] = values.get(value, 0) + 1
        return dict(sorted(values.items()))

    outcomes: Dict[str, int] = {}
    for scan in program["scans"]:
        outcomes[scan["outcome"]] = outcomes.get(scan["outcome"], 0) + 1
    return {
        "repositories_scanned": len(repos),
        "primary_eligible_repositories": len(primary),
        "tracks": _counts("track", repos),
        "primary_size_bands": _counts("size_band", primary),
        "primary_language_profiles": _counts("language_profile", primary),
        "primary_project_shapes": _counts("project_shape", primary),
        "historical_bug_cases": len(manifest.get("historical_bugs", [])),
        "historical_bug_repositories": len({
            case["repo_id"] for case in manifest.get("historical_bugs", [])
        }),
        "outcomes": dict(sorted(outcomes.items())),
    }


def _ensure_output_outside_targets(output_dir: str | Path, manifest: Dict[str, Any]) -> Path:
    output = Path(output_dir).resolve()
    for repo in manifest["repositories"]:
        target = Path(repo["path"]).resolve()
        if output == target or target in output.parents:
            raise ValueError(f"output directory must be outside target repository: {target}")
    output.mkdir(parents=True, exist_ok=True)
    return output


# ---------------------------------------------------------------------------
# Review workflow
# ---------------------------------------------------------------------------
def _blank_review() -> Dict[str, Any]:
    return {"label": "unreviewed", "notes": "", "review_minutes": None, "usefulness": None}


def export_review_template(records: List[Dict[str, Any]], path: str | Path) -> None:
    findings = {}
    for record in sorted(records, key=_record_sort_key):
        findings[record["record_id"]] = {
            "finding_id": record["id"],
            "repo_id": record["repo_id"],
            "reviewer_a": _blank_review(),
            "reviewer_b": _blank_review(),
            "adjudication": _blank_review(),
        }
    write_json(path, {"review_schema_version": REVIEW_SCHEMA_VERSION, "findings": findings})


def export_repo_score_template(repositories: List[Dict[str, Any]], path: str | Path) -> None:
    scores = {}
    for repo in sorted(repositories, key=lambda item: item["id"]):
        scores[repo["id"]] = {
            "usefulness": None,
            "would_use_again": None,
            "reason": "",
        }
    write_json(path, {"review_schema_version": REVIEW_SCHEMA_VERSION, "repositories": scores})


def _stable_rank(seed: str, value: str) -> str:
    return hashlib.sha256(f"{seed}|{value}".encode("utf-8")).hexdigest()


def select_review_sample(
    records: List[Dict[str, Any]], *, seed: str = "phase95", max_findings: int = 300
) -> List[Dict[str, Any]]:
    """Select grounded findings for review without hiding inconvenient strata."""
    verdict = [dict(record) for record in records if record["verdict_eligible"]]
    verdict.sort(key=_record_sort_key)
    if len(verdict) <= max_findings:
        return verdict

    repo_counts: Dict[str, int] = {}
    for record in verdict:
        repo_counts[record["repo_id"]] = repo_counts.get(record["repo_id"], 0) + 1
    mandatory = {
        record["record_id"]
        for record in verdict
        if record.get("severity") in {"critical", "high"}
        or repo_counts[record["repo_id"]] <= 10
    }
    for rule in sorted({record.get("rule", "") for record in verdict}):
        rule_records = [record for record in verdict if record.get("rule", "") == rule]
        rule_records.sort(key=lambda record: _stable_rank(seed, record["record_id"]))
        mandatory.update(record["record_id"] for record in rule_records[:25])

    selected = [record for record in verdict if record["record_id"] in mandatory]
    remaining = [record for record in verdict if record["record_id"] not in mandatory]
    slots = max(0, max_findings - len(selected))
    remaining.sort(key=lambda record: _stable_rank(seed, record["record_id"]))
    probability = round(min(1.0, slots / len(remaining)), 6) if remaining else 1.0
    for record in remaining[:slots]:
        record["sampling_probability"] = probability
        selected.append(record)
    return sorted(selected, key=_record_sort_key)


def export_reviewer_packets(records: List[Dict[str, Any]], output_dir: str | Path) -> None:
    output = Path(output_dir)
    shared = [
        {
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
            "verification_evidence": record.get("verification_evidence"),
        }
        for record in sorted(records, key=_record_sort_key)
    ]
    write_json(output / "reviewer_a_packets.json", shared)
    write_json(output / "reviewer_b_packets.json", shared)
    write_json(output / "adjudication_packets.json", shared)


def select_negative_file_sample(
    manifest: Dict[str, Any], program: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Choose up to three unflagged Python files per scanned repository."""
    by_repo = {repo["id"]: repo for repo in manifest["repositories"]}
    sample: List[Dict[str, Any]] = []
    for scan in sorted(program["scans"], key=lambda item: item["repo_id"]):
        if scan["outcome"] not in {"success", "degraded"}:
            continue
        flagged = {
            record["file"] for record in scan["records"] if record["verdict_eligible"]
        }
        candidates = []
        for abs_path, rel_path in engine._collect_python_files(scan["path"]):
            if rel_path in flagged:
                continue
            try:
                size = os.path.getsize(abs_path)
            except OSError:
                continue
            candidates.append((size, rel_path))
        candidates.sort(key=lambda item: (item[0], item[1]))
        if not candidates:
            continue
        indexes = sorted({0, len(candidates) // 2, len(candidates) - 1})
        repo = by_repo[scan["repo_id"]]
        for index in indexes:
            size, rel_path = candidates[index]
            sample.append({
                "repo_id": scan["repo_id"],
                "file": rel_path,
                "bytes": size,
                "track": repo.get("track", "primary"),
                "review": {
                    "obvious_actionable_issue": None,
                    "notes": "",
                    "review_minutes": None,
                },
            })
    return sorted(sample, key=lambda item: (item["repo_id"], item["bytes"], item["file"]))


def export_historical_review_template(manifest: Dict[str, Any], path: str | Path) -> None:
    cases = []
    for case in sorted(manifest.get("historical_bugs", []), key=lambda item: item["id"]):
        cases.append({
            **case,
            "relevant_emitted_finding": None,
            "notes": "",
            "review_minutes": None,
        })
    write_json(path, {"historical_bug_reviews": cases})


def load_reviews(path: str | Path) -> Dict[str, Any]:
    return load_json(path)


def load_repo_scores(path: str | Path) -> Dict[str, Any]:
    return load_json(path)


def _validate_review_slot(prefix: str, slot: Dict[str, Any], issues: List[str]) -> None:
    label = slot.get("label", "unreviewed")
    if label not in LABELS:
        issues.append(f"{prefix}: invalid label '{label}'")
    usefulness = slot.get("usefulness")
    if usefulness is not None and not (
        isinstance(usefulness, int) and USEFULNESS_MIN <= usefulness <= USEFULNESS_MAX
    ):
        issues.append(f"{prefix}: usefulness must be {USEFULNESS_MIN}-{USEFULNESS_MAX} or null")
    minutes = slot.get("review_minutes")
    if minutes is not None and not isinstance(minutes, (int, float)):
        issues.append(f"{prefix}: review_minutes must be numeric or null")


def validate_reviews(reviews: Dict[str, Any]) -> List[str]:
    issues: List[str] = []
    if reviews.get("review_schema_version") != REVIEW_SCHEMA_VERSION:
        issues.append(f"review_schema_version must be {REVIEW_SCHEMA_VERSION}")
    findings = reviews.get("findings")
    if not isinstance(findings, dict):
        return issues + ["reviews missing 'findings' object"]
    for record_id, review in findings.items():
        for slot_name in ("reviewer_a", "reviewer_b", "adjudication"):
            slot = review.get(slot_name)
            if not isinstance(slot, dict):
                issues.append(f"{record_id}: missing '{slot_name}' review")
            else:
                _validate_review_slot(f"{record_id}.{slot_name}", slot, issues)
    return issues


def validate_repo_scores(scores: Dict[str, Any]) -> List[str]:
    issues: List[str] = []
    if scores.get("review_schema_version") != REVIEW_SCHEMA_VERSION:
        issues.append(f"review_schema_version must be {REVIEW_SCHEMA_VERSION}")
    repos = scores.get("repositories")
    if not isinstance(repos, dict):
        return issues + ["repository scores missing 'repositories' object"]
    for repo_id, score in repos.items():
        usefulness = score.get("usefulness")
        if usefulness is not None and not (
            isinstance(usefulness, int)
            and REPO_USEFULNESS_MIN <= usefulness <= REPO_USEFULNESS_MAX
        ):
            issues.append(
                f"{repo_id}: usefulness must be {REPO_USEFULNESS_MIN}-"
                f"{REPO_USEFULNESS_MAX} or null"
            )
        again = score.get("would_use_again")
        if again is not None and not isinstance(again, bool):
            issues.append(f"{repo_id}: would_use_again must be true, false, or null")
    return issues


def _resolved_review(review: Dict[str, Any]) -> Dict[str, Any]:
    adjudication = review["adjudication"]
    if adjudication.get("label") != "unreviewed":
        return {**adjudication, "review_resolution": "adjudicated", "needs_adjudication": False}
    first, second = review["reviewer_a"], review["reviewer_b"]
    labels = (first.get("label"), second.get("label"))
    if labels[0] != "unreviewed" and labels[0] == labels[1]:
        scores = [s.get("usefulness") for s in (first, second) if isinstance(s.get("usefulness"), int)]
        usefulness = round(sum(scores) / len(scores), 2) if scores else None
        return {
            "label": labels[0],
            "notes": "",
            "review_minutes": sum(
                s.get("review_minutes") or 0 for s in (first, second)
            ),
            "usefulness": usefulness,
            "review_resolution": "reviewer_agreement",
            "needs_adjudication": False,
        }
    return {
        **_blank_review(),
        "review_resolution": "pending",
        "needs_adjudication": labels[0] != labels[1] and "unreviewed" not in labels,
    }


def merge_reviews(records: List[Dict[str, Any]], reviews: Dict[str, Any]) -> List[Dict[str, Any]]:
    issues = validate_reviews(reviews)
    if issues:
        raise ValueError("invalid reviews: " + "; ".join(issues))
    review_map = reviews["findings"]
    labeled: List[Dict[str, Any]] = []
    for record in records:
        merged = dict(record)
        merged.update(_resolved_review(review_map.get(record["record_id"], {
            "reviewer_a": _blank_review(),
            "reviewer_b": _blank_review(),
            "adjudication": _blank_review(),
        })))
        labeled.append(merged)
    return sorted(labeled, key=_record_sort_key)


# ---------------------------------------------------------------------------
# Precision and usefulness
# ---------------------------------------------------------------------------
def _rate(numerator: float, denominator: float) -> Optional[float]:
    return round(numerator / denominator, 4) if denominator else None


def _count(records: List[Dict[str, Any]], label: str) -> int:
    return sum(record.get("label") == label for record in records)


def _breakdown(in_scope: List[Dict[str, Any]], key: str) -> Dict[str, Any]:
    groups: Dict[str, Dict[str, int]] = {}
    for record in in_scope:
        value = str(record.get(key) or "unknown")
        group = groups.setdefault(value, {"confirmed": 0, "in_scope": 0})
        group["in_scope"] += 1
        group["confirmed"] += record.get("label") == "confirmed_actionable"
    return {
        group: {**values, "precision": _rate(values["confirmed"], values["in_scope"])}
        for group, values in sorted(groups.items())
    }


def measure_precision(labeled: List[Dict[str, Any]]) -> Dict[str, Any]:
    verdict = [record for record in labeled if record["verdict_eligible"]]
    advisory = [record for record in labeled if not record["verdict_eligible"]]
    in_scope = [record for record in verdict if record.get("label") in IN_SCOPE_LABELS]
    confirmed = _count(in_scope, "confirmed_actionable")
    lead = _count(in_scope, "useful_review_lead")
    benign = _count(in_scope, "benign_or_intended")
    misleading = _count(in_scope, "misleading")
    undecidable = _count(in_scope, "undecidable")
    weighted_total = sum(1 / record.get("sampling_probability", 1.0) for record in in_scope)
    weighted_confirmed = sum(
        1 / record.get("sampling_probability", 1.0)
        for record in in_scope
        if record.get("label") == "confirmed_actionable"
    )
    return {
        "verdict_eligible_total": len(verdict),
        "reviewed_in_scope": len(in_scope),
        "unreviewed": _count(verdict, "unreviewed"),
        "needs_adjudication": sum(record.get("needs_adjudication", False) for record in verdict),
        "out_of_scope": _count(verdict, "out_of_scope"),
        "counts": {
            "benign_or_intended": benign,
            "confirmed_actionable": confirmed,
            "misleading": misleading,
            "undecidable": undecidable,
            "useful_review_lead": lead,
        },
        "strict_precision": _rate(confirmed, len(in_scope)),
        "weighted_strict_precision": _rate(weighted_confirmed, weighted_total),
        "review_lead_rate": _rate(confirmed + lead, len(in_scope)),
        "misleading_rate": _rate(misleading, len(in_scope)),
        "undecidable_rate": _rate(undecidable, len(in_scope)),
        "by_rule": _breakdown(in_scope, "rule"),
        "by_kind": _breakdown(in_scope, "kind"),
        "by_severity": _breakdown(in_scope, "severity"),
        "by_size_band": _breakdown(in_scope, "size_band"),
        "by_language_profile": _breakdown(in_scope, "language_profile"),
        "advisory_separate": {
            "reviewed": sum(record.get("label") not in (None, "unreviewed") for record in advisory),
            "total": len(advisory),
        },
    }


def score_usefulness(
    labeled: List[Dict[str, Any]], repo_scores: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    repo_scores = repo_scores or {"repositories": {}}
    repos = repo_scores.get("repositories", repo_scores)
    scored = [
        record
        for record in labeled
        if record["verdict_eligible"] and isinstance(record.get("usefulness"), (int, float))
    ]
    distribution = {
        str(score): sum(record["usefulness"] == score for record in scored)
        for score in sorted({record["usefulness"] for record in scored})
    }
    repo_values = [
        score["usefulness"]
        for score in repos.values()
        if isinstance(score.get("usefulness"), int)
    ]
    again = [
        score["would_use_again"]
        for score in repos.values()
        if isinstance(score.get("would_use_again"), bool)
    ]
    return {
        "per_finding": {
            "distribution": distribution,
            "mean_usefulness": round(statistics.mean(r["usefulness"] for r in scored), 4)
            if scored
            else None,
            "scored_findings": len(scored),
        },
        "repositories_with_score3plus_finding": sorted(
            {record["repo_id"] for record in scored if record["usefulness"] >= 3}
        ),
        "per_repository": {
            "median_repo_usefulness": round(statistics.median(repo_values), 4)
            if repo_values
            else None,
            "scored_repositories": len(repo_values),
            "would_use_again_rate": _rate(sum(again), len(again)),
            "would_use_again_total": len(again),
            "would_use_again_true": sum(again),
        },
    }


def _gate(name: str, passed: bool, detail: str) -> Dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def evaluate_readiness(
    manifest: Dict[str, Any],
    program: Dict[str, Any],
    precision: Dict[str, Any],
    usefulness: Dict[str, Any],
) -> Dict[str, Any]:
    """Apply Phase 95B external-alpha gates without tuning the engine."""
    summary = corpus_summary(manifest, program)
    scans = program["scans"]
    unsafe = [scan["repo_id"] for scan in scans if scan["outcome"] == "unsafe"]
    completed = [
        scan for scan in scans if scan["outcome"] in {"success", "degraded"}
    ]
    primary_count = summary["primary_eligible_repositories"]
    crash_free_rate = _rate(len(completed), len(scans)) or 0.0
    historical_count = summary["historical_bug_cases"]
    historical_repos = summary["historical_bug_repositories"]
    scored_repos = usefulness["per_repository"]["scored_repositories"]
    repo_usefulness = usefulness["per_repository"]["median_repo_usefulness"]
    would_again = usefulness["per_repository"]["would_use_again_rate"]
    reviewed = precision["reviewed_in_scope"]

    gates = [
        _gate("unsafe_outcomes", not unsafe, f"{len(unsafe)} unsafe: {unsafe}"),
        _gate(
            "crash_free_completion",
            crash_free_rate >= 0.95,
            f"{len(completed)}/{len(scans)} completed ({crash_free_rate})",
        ),
        _gate("primary_repository_count", primary_count >= 24, f"{primary_count}/24"),
        _gate(
            "historical_bug_cases",
            historical_count >= 20 and historical_repos >= 10,
            f"{historical_count} cases across {historical_repos} repositories",
        ),
        _gate("review_completion", precision["unreviewed"] == 0, f"{precision['unreviewed']} unreviewed"),
        _gate(
            "adjudication_completion",
            precision["needs_adjudication"] == 0,
            f"{precision['needs_adjudication']} need adjudication",
        ),
        _gate(
            "strict_precision",
            reviewed > 0 and (precision["strict_precision"] or 0.0) >= 0.90,
            f"{precision['strict_precision']} from {reviewed} reviewed findings",
        ),
        _gate(
            "misleading_rate",
            reviewed > 0 and (precision["misleading_rate"] or 0.0) <= 0.05,
            f"{precision['misleading_rate']} from {reviewed} reviewed findings",
        ),
        _gate(
            "repository_usefulness",
            scored_repos >= primary_count > 0 and (repo_usefulness or 0.0) >= 3.0,
            f"median {repo_usefulness}; {scored_repos}/{primary_count} primary repositories scored",
        ),
        _gate(
            "would_use_again",
            would_again is not None and would_again >= 0.70,
            f"{would_again}",
        ),
        _gate(
            "review_lead_rate",
            reviewed > 0 and (precision["review_lead_rate"] or 0.0) >= 0.60,
            f"{precision['review_lead_rate']}",
        ),
    ]
    verdict = "FAIL" if unsafe else ("PASS" if all(g["passed"] for g in gates) else "HOLD")
    return {"verdict": verdict, "corpus": summary, "gates": gates}


# ---------------------------------------------------------------------------
# Deterministic artifacts and report
# ---------------------------------------------------------------------------
def generate_report(
    program: Dict[str, Any],
    precision: Dict[str, Any],
    usefulness: Dict[str, Any],
    readiness: Optional[Dict[str, Any]] = None,
    inventory: Optional[Dict[str, Any]] = None,
) -> str:
    candidate = program["candidate"]
    lines = [
        "# Real Repository Validation Report",
        "",
        f"Report schema: {REPORT_SCHEMA_VERSION}",
        "",
        "## Frozen Candidate",
        f"- commit: {candidate['builder_core_commit']}",
        f"- flags: {json.dumps(candidate['frozen_flags'], sort_keys=True)}",
        f"- real-repository verdict kinds: {candidate['real_repo_verdict_kinds']}",
    ]
    if readiness is not None:
        corpus = readiness["corpus"]
        lines.extend([
            "",
            "## External Alpha Verdict",
            f"**{readiness['verdict']}**",
            "",
            "## Corpus Composition",
            f"- repositories scanned: {corpus['repositories_scanned']}",
            f"- primary eligible repositories: {corpus['primary_eligible_repositories']}/24",
            f"- tracks: {corpus['tracks']}",
            f"- historical bug cases: {corpus['historical_bug_cases']} "
            f"across {corpus['historical_bug_repositories']} repositories",
            "",
            "## Readiness Gates",
            "| gate | pass | detail |",
            "| --- | --- | --- |",
        ])
        for gate in readiness["gates"]:
            lines.append(f"| {gate['name']} | {gate['passed']} | {gate['detail']} |")
    lines.extend([
        "",
        "## Operational Safety",
        "| repo | outcome | parse errors | modified tracked files | duration s |",
        "| --- | --- | ---: | ---: | ---: |",
    ])
    for scan in sorted(program["scans"], key=lambda item: item["repo_id"]):
        safety = scan.get("safety", {})
        lines.append(
            f"| {scan['repo_id']} | {scan['outcome']} | "
            f"{scan.get('files_with_parse_errors', 0)} | "
            f"{len(safety.get('modified_tracked_files', []))} | "
            f"{scan.get('duration_seconds', '-')} |"
        )
    counts = precision["counts"]
    if inventory is not None:
        lines.extend([
            "",
            "## Finding Inventory",
            f"- total findings: {inventory['total_findings']}",
            f"- grounded verdict-eligible findings: {inventory['verdict_eligible_findings']}",
            f"- advisory findings: {inventory['advisory_findings']}",
            f"- grounded kinds: {inventory['verdict_by_kind']}",
            f"- advisory kinds: {inventory['advisory_by_kind']}",
        ])
    lines.extend(
        [
            "",
            "## Precision",
            f"- reviewed in scope: {precision['reviewed_in_scope']}",
            f"- unreviewed: {precision['unreviewed']}",
            f"- needs adjudication: {precision['needs_adjudication']}",
            f"- confirmed actionable: {counts['confirmed_actionable']}",
            f"- useful review lead: {counts['useful_review_lead']}",
            f"- benign or intended: {counts['benign_or_intended']}",
            f"- misleading: {counts['misleading']}",
            f"- undecidable: {counts['undecidable']}",
            f"- strict precision: {precision['strict_precision']}",
            f"- weighted strict precision: {precision['weighted_strict_precision']}",
            f"- review-lead rate: {precision['review_lead_rate']}",
            f"- misleading rate: {precision['misleading_rate']}",
            "",
            "### Precision By Rule",
            "| rule | confirmed | in scope | precision |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for rule, values in precision["by_rule"].items():
        lines.append(
            f"| {rule} | {values['confirmed']} | {values['in_scope']} | "
            f"{values['precision']} |"
        )
    per_finding = usefulness["per_finding"]
    per_repo = usefulness["per_repository"]
    lines.extend(
        [
            "",
            f"_Advisory findings are separate from precision: "
            f"{precision['advisory_separate']['total']} total._",
            "",
            "## Usefulness",
            f"- scored findings: {per_finding['scored_findings']}",
            f"- mean finding usefulness: {per_finding['mean_usefulness']}",
            f"- median repository usefulness: {per_repo['median_repo_usefulness']}",
            f"- would use again: {per_repo['would_use_again_true']}/"
            f"{per_repo['would_use_again_total']}",
            "",
            "> QuixBugs and holdout results remain separate regression gates. "
            "They are not blended into real-repository precision.",
        ]
    )
    return "\n".join(lines) + "\n"


def run_to_directory(manifest: Dict[str, Any], output_dir: str | Path) -> Dict[str, Any]:
    issues = validate_manifest(manifest)
    if issues:
        raise ValueError("invalid manifest: " + "; ".join(issues))
    output = _ensure_output_outside_targets(output_dir, manifest)
    program = run_program(manifest)
    records = all_records(program)
    write_json(output / "manifest.normalized.json", _normalized_manifest(manifest))
    write_json(output / "program.json", program)
    export_findings(records, output / "findings.json")
    review_sample = select_review_sample(
        records, seed=str(manifest.get("sampling_seed", "phase95"))
    )
    write_json(output / "review_sample.json", review_sample)
    export_review_template(review_sample, output / "reviews.json")
    export_reviewer_packets(review_sample, output)
    export_repo_score_template(manifest["repositories"], output / "repository_scores.json")
    write_json(output / "negative_file_sample.json", select_negative_file_sample(manifest, program))
    export_historical_review_template(manifest, output / "historical_bug_reviews.json")
    write_report_from_directory(output)
    return program


def write_report_from_directory(output_dir: str | Path) -> str:
    output = Path(output_dir)
    manifest = load_json(output / "manifest.normalized.json")
    program = load_json(output / "program.json")
    all_exported_records = load_json(output / "findings.json")
    records = load_json(output / "review_sample.json")
    reviews = load_reviews(output / "reviews.json")
    scores = load_repo_scores(output / "repository_scores.json")
    review_issues = validate_reviews(reviews)
    score_issues = validate_repo_scores(scores)
    if review_issues or score_issues:
        raise ValueError("invalid review data: " + "; ".join(review_issues + score_issues))
    labeled = merge_reviews(records, reviews)
    precision = measure_precision(labeled)
    usefulness = score_usefulness(labeled, scores)
    inventory = finding_inventory(all_exported_records)
    precision["verdict_eligible_total"] = inventory["verdict_eligible_findings"]
    precision["advisory_separate"]["total"] = inventory["advisory_findings"]
    readiness = evaluate_readiness(manifest, program, precision, usefulness)
    write_json(output / "findings.reviewed.json", labeled)
    write_json(
        output / "metrics.json",
        {
            "finding_inventory": inventory,
            "precision": precision,
            "readiness": readiness,
            "usefulness": usefulness,
        },
    )
    report = generate_report(program, precision, usefulness, readiness, inventory)
    (output / "report.md").write_text(report, encoding="utf-8")
    return report
