"""Validated, non-destructive discovery of historical Atlas scan state."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from . import persistence

MIGRATION_NAME = "repository_state_v1"
REQUIRED_ARTIFACTS = (
    "latest.json",
    "scan_snapshot.json",
    "graph.json",
    "index.json",
    "risks.json",
    "evidence_store.json",
    "file_manifest.json",
    "memory_packet.json",
)


def _read_json(path: Path) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def _write_json_atomic(path: Path, value: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _timestamp(value: Any) -> float:
    text = str(value or "").strip()
    if not text:
        return 0.0
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except (ValueError, OverflowError):
        return 0.0


def _record_time(record: Dict[str, Any]) -> float:
    return max(
        _timestamp(record.get("created_at")),
        _timestamp(record.get("last_scan_at")),
    )


def _artifact_validation(
    source_root: Path, row: Dict[str, Any]
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    repo_id = str(row.get("repo_id") or "")
    scan_dir = source_root / "scans" / repo_id
    missing = [name for name in REQUIRED_ARTIFACTS if not (scan_dir / name).is_file()]
    evidence: Dict[str, Any] = {
        "repo_id": repo_id,
        "repo_path": str(row.get("repo_path") or ""),
        "artifact_dir": str(scan_dir),
        "missing_artifacts": missing,
    }
    if not repo_id or missing:
        evidence["status"] = "invalid_artifacts"
        return None, evidence
    artifact_hashes: Dict[str, str] = {}
    invalid_json: List[str] = []
    for name in REQUIRED_ARTIFACTS:
        path = scan_dir / name
        artifact_hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        try:
            _read_json(path)
        except (OSError, ValueError, json.JSONDecodeError):
            invalid_json.append(name)
    evidence["artifact_sha256"] = artifact_hashes
    if invalid_json:
        evidence["invalid_json_artifacts"] = invalid_json
        evidence["status"] = "invalid_artifacts"
        return None, evidence
    try:
        record = _read_json(scan_dir / "latest.json")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        evidence.update(status="invalid_latest", error=f"{type(exc).__name__}: {exc}")
        return None, evidence
    repo_path = str(record.get("repo_path") or row.get("repo_path") or "")
    evidence["repo_path"] = repo_path
    evidence["repo_path_exists"] = os.path.isdir(repo_path)
    if not evidence["repo_path_exists"]:
        evidence["status"] = "path_missing"
        return None, evidence
    validation = persistence.validate_scan_state(record, repo_path)
    evidence["scan_validation"] = validation.get("status")
    if validation.get("status") != "valid":
        evidence["status"] = str(validation.get("status") or "invalid")
        return None, evidence
    secret_path = source_root / "security" / "persistence_secret"
    if not secret_path.is_file():
        evidence["status"] = "missing_persistence_secret"
        return None, evidence
    try:
        memory = _read_json(scan_dir / "memory_packet.json")
        memory_validation = persistence.validate_memory_packet(
            record, memory, repo_path, data_dir=str(source_root)
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        evidence.update(status="invalid_memory", error=f"{type(exc).__name__}: {exc}")
        return None, evidence
    evidence["memory_validation"] = memory_validation.get("status")
    if not memory_validation.get("ok"):
        evidence["status"] = "invalid_memory"
        return None, evidence
    evidence["status"] = "valid"
    return record, evidence


def _canonical_records(canonical_root: Path) -> Dict[str, Dict[str, Any]]:
    registry = canonical_root / "scans" / "registry.json"
    if not registry.is_file():
        return {}
    try:
        value = _read_json(registry)
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    return {
        str(row.get("repo_id")): dict(row)
        for row in value.get("scans") or []
        if isinstance(row, dict) and row.get("repo_id")
    }


def _backup_existing(canonical_root: Path, stamp: str) -> List[str]:
    registry = canonical_root / "scans" / "registry.json"
    if not registry.is_file():
        return []
    backup = registry.with_name(f"registry.pre_migration.{stamp}.json")
    if not backup.exists():
        shutil.copy2(registry, backup)
    return [str(backup)]


def _copy_record(
    source_root: Path,
    canonical_root: Path,
    record: Dict[str, Any],
    stamp: str,
) -> List[str]:
    repo_id = str(record["repo_id"])
    source_dir = source_root / "scans" / repo_id
    scans_root = canonical_root / "scans"
    destination = scans_root / repo_id
    backups: List[str] = []
    scans_root.mkdir(parents=True, exist_ok=True)
    temporary = scans_root / f".migrating-{repo_id}"
    if temporary.exists():
        shutil.rmtree(temporary)
    shutil.copytree(source_dir, temporary)
    memory_path = temporary / "memory_packet.json"
    memory = _read_json(memory_path)
    signed = persistence.sign_memory_packet(memory, record, str(canonical_root))
    _write_json_atomic(memory_path, signed)
    if destination.exists():
        backup = scans_root / "backups" / f"{repo_id}.{stamp}"
        backup.parent.mkdir(parents=True, exist_ok=True)
        suffix = 1
        while backup.exists():
            backup = backup.with_name(f"{repo_id}.{stamp}.{suffix}")
            suffix += 1
        os.replace(destination, backup)
        backups.append(str(backup))
    os.replace(temporary, destination)
    return backups


def migrate_repository_state(
    *, canonical_root: str, source_roots: Iterable[str], force: bool = False
) -> Dict[str, Any]:
    """Copy only newer, live-valid scan bundles into the canonical user root."""
    canonical = Path(canonical_root).resolve()
    marker = canonical / "migrations" / f"{MIGRATION_NAME}.json"
    if marker.is_file() and not force:
        try:
            previous = _read_json(marker)
            previous["idempotent_reuse"] = True
            return previous
        except (OSError, ValueError, json.JSONDecodeError):
            pass

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    result: Dict[str, Any] = {
        "migration": MIGRATION_NAME,
        "status": "no_valid_state",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "canonical_root": str(canonical),
        "sources": [],
        "migrated_repo_ids": [],
        "backups": [],
    }
    existing = _canonical_records(canonical)
    selected: Dict[str, Tuple[Path, Dict[str, Any], Dict[str, Any]]] = {}
    canonical_key = os.path.normcase(str(canonical))
    for source_value in source_roots:
        source = Path(source_value).resolve()
        if os.path.normcase(str(source)) == canonical_key:
            continue
        source_result: Dict[str, Any] = {"root": str(source), "entries": []}
        result["sources"].append(source_result)
        registry = source / "scans" / "registry.json"
        if not registry.is_file():
            source_result["status"] = "registry_absent"
            continue
        try:
            registry_value = _read_json(registry)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            source_result.update(
                status="registry_invalid", error=f"{type(exc).__name__}: {exc}"
            )
            continue
        source_result["status"] = "inspected"
        for row in registry_value.get("scans") or []:
            if not isinstance(row, dict):
                continue
            record, evidence = _artifact_validation(source, row)
            source_result["entries"].append(evidence)
            if record is None:
                continue
            repo_id = str(record["repo_id"])
            current = existing.get(repo_id)
            if current and _record_time(current) >= _record_time(record):
                canonical_record, _ = _artifact_validation(canonical, current)
                if canonical_record is not None:
                    evidence["status"] = "skipped_canonical_newer_or_equal"
                    continue
            chosen = selected.get(repo_id)
            if chosen and _record_time(chosen[1]) >= _record_time(record):
                evidence["status"] = "skipped_newer_source_selected"
                continue
            selected[repo_id] = (source, record, evidence)

    if selected:
        result["backups"].extend(_backup_existing(canonical, stamp))
        for repo_id, (source, record, evidence) in selected.items():
            result["backups"].extend(
                _copy_record(source, canonical, record, stamp)
            )
            existing[repo_id] = record
            evidence["status"] = "migrated"
            result["migrated_repo_ids"].append(repo_id)
        ordered = sorted(existing.values(), key=_record_time, reverse=True)
        registry_value = {
            "active_repo_id": str(ordered[0].get("repo_id") or ""),
            "scans": ordered,
        }
        _write_json_atomic(canonical / "scans" / "registry.json", registry_value)
        result["status"] = "migrated"

    _write_json_atomic(marker, result)
    return result
