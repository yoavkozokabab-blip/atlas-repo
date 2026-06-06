"""Phase 181B — scan and workflow history persistence (local disk only).

Restoring stale context is worse than rescanning — validation is strict.
Does not modify graph intelligence, impact algorithm, or repository memory semantics.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from . import repository_memory as _repo_memory
from .product_info import PRODUCT_VERSION

MAX_SCANS = 10
MAX_HISTORY_PER_REPO = 100
HISTORY_RETENTION_DAYS = 90
WORKFLOW_TYPES = ("build", "investigate", "impact")
VERSION_MISMATCH_MSG = "Rescan required after Atlas update"
_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")
_HISTORY_HASH_KEYS = (
    "history_id",
    "workflow_type",
    "request_text",
    "created_at",
    "repo_id",
    "scan_id",
    "scan_signature",
    "files_named",
    "confidence",
    "export_tokens",
    "export_mode",
    "summary_markdown",
    "result_json",
    "trust_status",
    "atlas_version",
)
_SOURCE_LIKE_KEYS = frozenset({
    "text", "content", "source", "source_code", "body", "file_content", "raw",
})
_MAX_STRING_LEN = 4000
_MAX_RESULT_DEPTH = 8


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _parse_version_tuple(version: str) -> Optional[Tuple[int, int, int]]:
    if not version:
        return None
    match = _VERSION_RE.search(str(version).strip())
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def validate_persistence_version(
    stored_version: str,
    current_version: Optional[str] = None,
) -> Dict[str, Any]:
    """Reject future, incompatible-major, or malformed persisted versions."""
    current = current_version or PRODUCT_VERSION
    if not str(stored_version or "").strip():
        return {
            "ok": False,
            "status": "version_malformed",
            "message": VERSION_MISMATCH_MSG,
        }
    stored = _parse_version_tuple(str(stored_version))
    live = _parse_version_tuple(str(current))
    if stored is None or live is None:
        return {
            "ok": False,
            "status": "version_malformed",
            "message": VERSION_MISMATCH_MSG,
        }
    if stored > live:
        return {
            "ok": False,
            "status": "version_future",
            "message": VERSION_MISMATCH_MSG,
        }
    if stored[0] != live[0]:
        return {
            "ok": False,
            "status": "version_incompatible",
            "message": VERSION_MISMATCH_MSG,
        }
    return {"ok": True, "status": "compatible"}


def _compute_history_integrity_hash(record: Dict[str, Any]) -> str:
    payload = {key: record.get(key) for key in _HISTORY_HASH_KEYS}
    blob = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _signatures_match(stored: str, other: str) -> bool:
    left = str(stored or "")
    right = str(other or "")
    if not left or not right:
        return True
    if left == right:
        return True
    if left.startswith(right) or right.startswith(left[:12]):
        return True
    return False


def _validate_history_row(row: Dict[str, Any], *, expected_repo_id: Optional[str] = None) -> bool:
    declared = str(row.get("integrity_hash") or "")
    if not declared:
        return False
    if declared != _compute_history_integrity_hash(row):
        return False
    rid = str(row.get("repo_id") or "")
    if not rid or not row.get("scan_id") or not row.get("scan_signature"):
        return False
    if expected_repo_id and rid != expected_repo_id:
        return False
    return bool(validate_persistence_version(str(row.get("atlas_version") or "")).get("ok"))


def validate_memory_packet(
    record: Dict[str, Any],
    memory_packet: Dict[str, Any],
    repo_path: str,
) -> Dict[str, Any]:
    """Ensure persisted memory sidecar matches scan metadata before restore/export."""
    if not memory_packet:
        return {"ok": True, "trusted": False, "status": "missing"}

    rid = str(record.get("repo_id") or "")
    scan_id = str(record.get("scan_id") or "")
    scan_sig = str(record.get("scan_signature") or "")
    graph_sig = str(record.get("graph_signature") or scan_sig)

    mode = str(memory_packet.get("mode") or "")
    if mode in {"MEMORY", "SESSION"} or "text" in memory_packet:
        pkt_scan = str(memory_packet.get("scan_id") or "")
        pkt_repo = str(memory_packet.get("repo_id") or "")
        pkt_sig = str(memory_packet.get("scan_signature") or "")
        if rid and pkt_repo and pkt_repo != rid:
            return {"ok": False, "trusted": False, "status": "memory_repo_mismatch"}
        if scan_id and pkt_scan and pkt_scan != scan_id:
            return {"ok": False, "trusted": False, "status": "memory_scan_mismatch"}
        if scan_sig and pkt_sig and not _signatures_match(scan_sig, pkt_sig):
            return {"ok": False, "trusted": False, "status": "memory_signature_mismatch"}
        if graph_sig and pkt_sig and not _signatures_match(graph_sig, pkt_sig):
            return {"ok": False, "trusted": False, "status": "memory_graph_signature_mismatch"}
        return {"ok": True, "trusted": True, "status": "trusted_packet"}

    if not _repo_memory.verify_memory_record(memory_packet, repo_path):
        return {"ok": False, "trusted": False, "status": "memory_integrity_failed"}
    if rid and str(memory_packet.get("repo_id") or "") != rid:
        return {"ok": False, "trusted": False, "status": "memory_repo_mismatch"}
    if scan_id and str(memory_packet.get("scan_id") or "") != scan_id:
        return {"ok": False, "trusted": False, "status": "memory_scan_mismatch"}
    mem_sig = str(memory_packet.get("scan_signature") or "")
    if scan_sig and mem_sig and scan_sig != mem_sig:
        return {"ok": False, "trusted": False, "status": "memory_signature_mismatch"}
    if graph_sig and mem_sig and graph_sig != mem_sig:
        return {"ok": False, "trusted": False, "status": "memory_graph_signature_mismatch"}
    return {"ok": True, "trusted": True, "status": "trusted_memory"}


def _parse_iso(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _scans_root(data_dir: str) -> str:
    path = os.path.join(data_dir, "scans")
    os.makedirs(path, exist_ok=True)
    return path


def _histories_root(data_dir: str) -> str:
    path = os.path.join(data_dir, "histories")
    os.makedirs(path, exist_ok=True)
    return path


def _scan_dir(data_dir: str, repo_id: str) -> str:
    path = os.path.join(_scans_root(data_dir), repo_id)
    os.makedirs(path, exist_ok=True)
    return path


def _history_dir(data_dir: str, repo_id: str) -> str:
    path = os.path.join(_histories_root(data_dir), repo_id)
    os.makedirs(path, exist_ok=True)
    return path


def _registry_path(data_dir: str) -> str:
    return os.path.join(_scans_root(data_dir), "registry.json")


def path_display(repo_path: str) -> str:
    norm = os.path.abspath(repo_path or "")
    home = os.path.expanduser("~")
    try:
        rel = os.path.relpath(norm, home)
        if not rel.startswith(".."):
            return "~/" + rel.replace("\\", "/")
    except ValueError:
        pass
    return norm.replace("\\", "/")


def _graph_health_label(scan: Dict[str, Any]) -> str:
    gh = scan.get("graph_health") or {}
    if isinstance(gh, dict):
        return str(gh.get("label") or gh.get("status") or "unknown")
    return str(gh or "unknown")


def _language_profile(scan: Dict[str, Any]) -> Dict[str, Any]:
    lb = scan.get("language_breakdown") or {}
    if isinstance(lb, dict):
        return {
            "primary": lb.get("primary_language") or lb.get("primary"),
            "languages": lb.get("languages") or lb.get("by_language") or {},
        }
    return {}


def _json_write(path: str, payload: Any) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, default=str)
    os.replace(tmp, path)


def _json_read(path: str) -> Any:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _strip_source_like(obj: Any, *, depth: int = 0) -> Any:
    if depth > _MAX_RESULT_DEPTH:
        return "[truncated]"
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for key, val in obj.items():
            lk = str(key).lower()
            if lk in _SOURCE_LIKE_KEYS:
                continue
            if lk in ("prompts", "export_full", "full_text"):
                continue
            out[key] = _strip_source_like(val, depth=depth + 1)
        return out
    if isinstance(obj, list):
        return [_strip_source_like(x, depth=depth + 1) for x in obj[:40]]
    if isinstance(obj, str):
        if len(obj) > _MAX_STRING_LEN:
            return obj[:_MAX_STRING_LEN] + "…"
        if obj.count("\n") > 40 and len(obj) > 500:
            return obj[:500] + "…"
        return obj
    return obj


def _sanitize_index(index: Dict[str, Any]) -> Dict[str, Any]:
    data = json.loads(json.dumps(index, default=str))
    for f in data.get("files") or []:
        f.pop("text", None)
        f.pop("content", None)
    data.pop("chunks", None)
    return data


def _build_scan_record(
    *,
    scan: Dict[str, Any],
    state: Dict[str, Any],
    atlas_version: str,
    trust_status: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    repo_path = str(state.get("path") or scan.get("repo_path") or "")
    rid = _repo_memory.repo_id(repo_path)
    mem = state.get("_current_memory") or {}
    sig = (scan.get("signature_v2") or {}).get("signature") or (scan.get("cache") or {}).get("signature") or ""
    return {
        "repo_path": repo_path,
        "repo_name": scan.get("repo_name") or os.path.basename(repo_path) or repo_path,
        "repo_id": rid,
        "scan_id": mem.get("scan_id") or scan.get("scan_id") or "",
        "scan_signature": sig,
        "graph_signature": sig,
        "file_count": int(scan.get("file_count") or 0),
        "module_count": int(scan.get("module_count") or 0),
        "edge_count": int(scan.get("dependency_edges") or 0),
        "graph_health": scan.get("graph_health"),
        "graph_health_label": _graph_health_label(scan),
        "language_profile": _language_profile(scan),
        "unresolved_import_count": int(scan.get("unresolved_imports") or 0),
        "scan_duration_seconds": scan.get("scan_duration_seconds"),
        "atlas_version": atlas_version,
        "created_at": scan.get("scanned_at") or _now_iso(),
        "memory_ref": mem.get("scan_id") or (state.get("repository_memory") or {}).get("scan_id") or "",
        "memory_hash": mem.get("memory_hash") or "",
        "trust_status": trust_status or {},
        "scope": scan.get("scope") or state.get("last_scope") or {},
        "demo_mode": bool(scan.get("demo_mode") or state.get("demo_mode")),
        "persisted_at": _now_iso(),
        "requires_refresh_before_export": False,
    }


def save_scan_state(
    data_dir: str,
    *,
    scan: Dict[str, Any],
    graph: Dict[str, Any],
    index: Dict[str, Any],
    evidence_store: Dict[str, Any],
    risks: Optional[Dict[str, Any]] = None,
    state: Optional[Dict[str, Any]] = None,
    atlas_version: str = "",
    trust_status: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Persist scan snapshot under .jarvis_desktop/scans/{repo_id}/."""
    state = state or {}
    record = _build_scan_record(
        scan=scan, state=state, atlas_version=atlas_version, trust_status=trust_status,
    )
    rid = record["repo_id"]
    if not rid or not record["repo_path"]:
        return {"ok": False, "error": "missing repo identity"}

    sdir = _scan_dir(data_dir, rid)
    safe_index = _sanitize_index(index or {})
    scan_snapshot = json.loads(json.dumps(scan, default=str))
    sidecars = {
        "scan_snapshot.json": scan_snapshot,
        "graph.json": graph or {},
        "index.json": safe_index,
        "risks.json": risks or {},
        "evidence_store.json": evidence_store or {},
        "file_manifest.json": state.get("file_manifest") or {},
    }
    written: List[str] = []
    partial = False
    for name, payload in sidecars.items():
        try:
            _json_write(os.path.join(sdir, name), payload)
            written.append(name)
        except (OSError, TypeError, ValueError):
            partial = True
    record["sidecars"] = written
    record["partial_restore"] = partial
    if partial:
        record["requires_refresh_before_export"] = True

    mem_packet = state.get("repository_memory") or state.get("session_export")
    if mem_packet:
        try:
            _json_write(os.path.join(sdir, "memory_packet.json"), mem_packet)
            written.append("memory_packet.json")
        except (OSError, TypeError, ValueError):
            partial = True

    _json_write(os.path.join(sdir, "latest.json"), record)
    _update_registry(data_dir, record)
    return {"ok": True, "repo_id": rid, "record": record, "partial": partial}


def _update_registry(data_dir: str, record: Dict[str, Any]) -> None:
    reg_path = _registry_path(data_dir)
    try:
        reg = _json_read(reg_path) if os.path.isfile(reg_path) else {"scans": []}
    except (OSError, json.JSONDecodeError):
        reg = {"scans": []}
    scans = [s for s in reg.get("scans") or [] if s.get("repo_id") != record.get("repo_id")]
    scans.insert(0, {
        "repo_id": record.get("repo_id"),
        "repo_path": record.get("repo_path"),
        "repo_name": record.get("repo_name"),
        "path_display": path_display(record.get("repo_path", "")),
        "last_scan_at": record.get("created_at"),
        "file_count": record.get("file_count"),
        "module_count": record.get("module_count"),
        "graph_health": record.get("graph_health_label"),
        "graph_health_label": record.get("graph_health_label"),
        "freshness_status": (record.get("trust_status") or {}).get("status", "unknown"),
        "scan_signature": record.get("scan_signature"),
        "scan_id": record.get("scan_id"),
    })
    scans.sort(key=lambda s: s.get("last_scan_at") or "", reverse=True)
    reg["scans"] = scans[:MAX_SCANS]
    _json_write(reg_path, reg)


def list_recent_scans(data_dir: str) -> List[Dict[str, Any]]:
    reg_path = _registry_path(data_dir)
    if not os.path.isfile(reg_path):
        return []
    try:
        reg = _json_read(reg_path)
    except (OSError, json.JSONDecodeError):
        return []
    out: List[Dict[str, Any]] = []
    for row in reg.get("scans") or []:
        rid = row.get("repo_id")
        meta = row
        if rid and os.path.isfile(os.path.join(_scan_dir(data_dir, rid), "latest.json")):
            try:
                meta = _json_read(os.path.join(_scan_dir(data_dir, rid), "latest.json"))
            except (OSError, json.JSONDecodeError):
                pass
        validation = validate_scan_state(meta, meta.get("repo_path", ""))
        out.append({
            "repo_id": meta.get("repo_id") or rid,
            "repo_path": meta.get("repo_path") or row.get("repo_path"),
            "repo_name": meta.get("repo_name"),
            "path_display": path_display(meta.get("repo_path", "") or row.get("repo_path", "")),
            "last_scan_at": meta.get("created_at") or row.get("last_scan_at"),
            "file_count": meta.get("file_count"),
            "module_count": meta.get("module_count"),
            "graph_health": meta.get("graph_health_label") or _graph_health_label(meta),
            "freshness_status": validation.get("freshness_status", "unknown"),
            "validation_status": validation.get("status"),
            "can_resume": validation.get("status") == "valid",
        })
    return out


def validate_scan_state(
    scan_state: Dict[str, Any],
    current_repo_path: str,
    *,
    scope: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Validate persisted scan against a repo path and live signature."""
    version_check = validate_persistence_version(str(scan_state.get("atlas_version") or ""))
    if not version_check.get("ok"):
        return {
            "ok": False,
            "status": "version_mismatch",
            "freshness_status": "version_mismatch",
            "message": version_check.get("message") or VERSION_MISMATCH_MSG,
            "version_status": version_check.get("status"),
        }

    stored_path = str(scan_state.get("repo_path") or "")
    current = str(current_repo_path or stored_path or "")
    if not stored_path:
        return {"ok": False, "status": "missing", "freshness_status": "missing", "message": "No stored repository path."}
    if current and os.path.abspath(current).lower() != os.path.abspath(stored_path).lower():
        return {
            "ok": False,
            "status": "wrong_repo",
            "freshness_status": "wrong_repo",
            "message": "Stored scan belongs to a different repository path.",
        }
    if not os.path.isdir(stored_path):
        return {
            "ok": False,
            "status": "path_missing",
            "freshness_status": "path_missing",
            "message": "Repository folder no longer exists at the saved path.",
        }
    stored_sig = str(scan_state.get("scan_signature") or scan_state.get("graph_signature") or "")
    scope_data = scope or scan_state.get("scope") or {"mode": "entire_repo"}
    try:
        from . import trust_integrity as _ti

        live_sig = _ti.compute_signature_v2(
            stored_path,
            scope_data,
            include_content_hash=True,
        )
        live = str(live_sig.get("signature") or "")
    except Exception:
        live = ""
    if stored_sig and live and stored_sig != live:
        return {
            "ok": False,
            "status": "stale",
            "freshness_status": "stale",
            "message": "Repository changed since the last scan.",
            "scan_signature": stored_sig,
            "live_signature": live,
        }
    return {
        "ok": True,
        "status": "valid",
        "freshness_status": "fresh",
        "message": "Scan matches the repository.",
        "scan_signature": stored_sig,
        "live_signature": live,
    }


def load_scan_state(data_dir: str, repo_id: str) -> Optional[Dict[str, Any]]:
    sdir = _scan_dir(data_dir, repo_id)
    latest_path = os.path.join(sdir, "latest.json")
    if not os.path.isfile(latest_path):
        return None
    try:
        record = _json_read(latest_path)
    except (OSError, json.JSONDecodeError):
        return None

    def _load(name: str) -> Dict[str, Any]:
        p = os.path.join(sdir, name)
        if not os.path.isfile(p):
            return {}
        try:
            data = _json_read(p)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    graph = _load("graph.json")
    index = _load("index.json")
    risks = _load("risks.json")
    evidence_store = _load("evidence_store.json")
    file_manifest = _load("file_manifest.json")
    memory_packet = _load("memory_packet.json") if os.path.isfile(os.path.join(sdir, "memory_packet.json")) else {}
    scan_snapshot_path = os.path.join(sdir, "scan_snapshot.json")
    if os.path.isfile(scan_snapshot_path):
        try:
            scan_obj = _json_read(scan_snapshot_path)
            if not isinstance(scan_obj, dict):
                scan_obj = {**record, "ok": True}
        except (OSError, json.JSONDecodeError):
            scan_obj = {**record, "ok": True}
    else:
        scan_obj = {**record, "ok": True}

    if not graph or not index:
        record["requires_refresh_before_export"] = True

    return {
        "record": record,
        "scan": scan_obj,
        "graph": graph,
        "index": index,
        "risks": risks,
        "evidence_store": evidence_store,
        "file_manifest": file_manifest,
        "memory_packet": memory_packet,
        "repo_path": record.get("repo_path"),
        "repo_id": repo_id,
    }


def restore_into_state_with_memory(
    state: Dict[str, Any],
    bundle: Dict[str, Any],
    *,
    data_dir: str,
) -> Dict[str, Any]:
    record = bundle.get("record") or {}
    scan = bundle.get("scan") or record
    repo_path = str(bundle.get("repo_path") or record.get("repo_path") or "")
    state.update({
        "path": repo_path,
        "scan": scan,
        "graph": bundle.get("graph") or {},
        "index": bundle.get("index") or {},
        "risks": bundle.get("risks") or {},
        "evidence_store": bundle.get("evidence_store") or {},
        "demo_mode": bool(record.get("demo_mode")),
        "last_scope": record.get("scope") or {"mode": "entire_repo"},
        "file_manifest": bundle.get("file_manifest") or {},
        "refresh_generation": int(record.get("refresh_generation") or 0),
    })
    state.pop("repository_memory", None)
    state.pop("session_export", None)
    state.pop("_current_memory", None)
    state.pop("persistence_memory_rejected", None)

    mem_packet = bundle.get("memory_packet") or {}
    mem_check = validate_memory_packet(record, mem_packet, repo_path)
    if mem_packet and mem_check.get("trusted"):
        state["repository_memory"] = mem_packet
        state["session_export"] = mem_packet
    elif mem_packet:
        state["persistence_memory_rejected"] = True
        state["requires_refresh_before_export"] = True

    disk_mem = _repo_memory.load(repo_path, data_dir) if repo_path else None
    if disk_mem:
        disk_check = validate_memory_packet(record, disk_mem, repo_path)
        if disk_check.get("trusted"):
            state["_current_memory"] = disk_mem
        else:
            state["persistence_memory_rejected"] = True
            state["requires_refresh_before_export"] = True

    if not state.get("file_manifest"):
        try:
            from . import trust_integrity as _ti
            _ti.capture_file_manifest(state)
        except Exception:
            pass
    if record.get("requires_refresh_before_export"):
        state["persistence_partial"] = True
    return {
        "ok": True,
        "repo_id": record.get("repo_id"),
        "repo_name": record.get("repo_name"),
        "memory_trusted": not state.get("persistence_memory_rejected"),
        "memory_status": mem_check.get("status"),
    }


def delete_scan_state(data_dir: str, repo_id: str) -> Dict[str, Any]:
    import shutil
    sdir = _scan_dir(data_dir, repo_id)
    if os.path.isdir(sdir):
        shutil.rmtree(sdir, ignore_errors=True)
    reg_path = _registry_path(data_dir)
    if os.path.isfile(reg_path):
        try:
            reg = _json_read(reg_path)
            reg["scans"] = [s for s in reg.get("scans") or [] if s.get("repo_id") != repo_id]
            _json_write(reg_path, reg)
        except (OSError, json.JSONDecodeError):
            pass
    return {"ok": True, "repo_id": repo_id}


def cleanup_old_scans(data_dir: str) -> Dict[str, Any]:
    """Enforce retention: latest MAX_SCANS, history age/count limits."""
    removed_scans: List[str] = []
    reg_path = _registry_path(data_dir)
    if os.path.isfile(reg_path):
        try:
            reg = _json_read(reg_path)
            scans = reg.get("scans") or []
            keep_ids = {s.get("repo_id") for s in scans[:MAX_SCANS]}
            for s in scans[MAX_SCANS:]:
                rid = s.get("repo_id")
                if rid:
                    delete_scan_state(data_dir, rid)
                    removed_scans.append(rid)
            reg["scans"] = scans[:MAX_SCANS]
            _json_write(reg_path, reg)
        except (OSError, json.JSONDecodeError):
            pass

    removed_history = 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=HISTORY_RETENTION_DAYS)
    hist_root = _histories_root(data_dir)
    if os.path.isdir(hist_root):
        for rid in os.listdir(hist_root):
            hdir = os.path.join(hist_root, rid)
            if not os.path.isdir(hdir):
                continue
            for wf in WORKFLOW_TYPES:
                removed_history += _trim_history_file(os.path.join(hdir, f"{wf}.jsonl"), cutoff)

    return {"ok": True, "removed_scans": removed_scans, "removed_history_rows": removed_history}


def _trim_history_file(path: str, cutoff: datetime) -> int:
    if not os.path.isfile(path):
        return 0
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return 0
    kept: List[str] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = _parse_iso(str(row.get("created_at") or ""))
        if ts and ts < cutoff:
            continue
        kept.append(line)
    if len(kept) > MAX_HISTORY_PER_REPO:
        kept = kept[-MAX_HISTORY_PER_REPO:]
    removed = max(0, len(lines) - len(kept))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(kept) + ("\n" if kept else ""))
    return removed


def save_workflow_history(data_dir: str, record: Dict[str, Any]) -> Dict[str, Any]:
    rid = record.get("repo_id")
    wf = record.get("workflow_type")
    if not rid or wf not in WORKFLOW_TYPES:
        return {"ok": False, "error": "invalid history record"}
    record = dict(record)
    record.setdefault("history_id", uuid.uuid4().hex[:16])
    record.setdefault("created_at", _now_iso())
    record.setdefault("atlas_version", PRODUCT_VERSION)
    record["result_json"] = _strip_source_like(record.get("result_json") or {})
    record["summary_markdown"] = str(record.get("summary_markdown") or "")[:8000]
    if not record.get("scan_signature"):
        return {"ok": False, "error": "history record missing scan_signature"}
    record["integrity_hash"] = _compute_history_integrity_hash(record)
    path = os.path.join(_history_dir(data_dir, rid), f"{wf}.jsonl")
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, default=str) + "\n")
    cutoff = datetime.now(timezone.utc) - timedelta(days=HISTORY_RETENTION_DAYS)
    _trim_history_file(path, cutoff)
    return {"ok": True, "history_id": record["history_id"]}


def _read_history_lines(data_dir: str, repo_id: str, workflow_type: Optional[str] = None) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    types = (workflow_type,) if workflow_type in WORKFLOW_TYPES else WORKFLOW_TYPES
    for wf in types:
        path = os.path.join(_history_dir(data_dir, repo_id), f"{wf}.jsonl")
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not _validate_history_row(row, expected_repo_id=repo_id):
                        continue
                    rows.append(row)
        except OSError:
            continue
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return rows


def list_workflow_history(
    data_dir: str,
    repo_id: str,
    workflow_type: Optional[str] = None,
    *,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    rows = _read_history_lines(data_dir, repo_id, workflow_type)[:limit]
    return [_history_list_item(r) for r in rows]


def _history_list_item(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "history_id": row.get("history_id"),
        "workflow_type": row.get("workflow_type"),
        "request_text": row.get("request_text"),
        "created_at": row.get("created_at"),
        "repo_id": row.get("repo_id"),
        "scan_id": row.get("scan_id"),
        "scan_signature": row.get("scan_signature"),
        "files_named": row.get("files_named") or [],
        "confidence": row.get("confidence"),
        "export_tokens": row.get("export_tokens"),
        "export_mode": row.get("export_mode"),
        "trust_status": row.get("trust_status"),
        "integrity_verified": True,
        "export_allowed": False,
        "stale_reason": row.get("stale_reason"),
    }


def get_workflow_history_item(data_dir: str, history_id: str, *, state: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    hist_root = _histories_root(data_dir)
    if not os.path.isdir(hist_root):
        return None
    for rid in os.listdir(hist_root):
        for wf in WORKFLOW_TYPES:
            path = os.path.join(hist_root, rid, f"{wf}.jsonl")
            if not os.path.isfile(path):
                continue
            try:
                with open(path, encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            row = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if row.get("history_id") != history_id:
                            continue
                        if not _validate_history_row(row, expected_repo_id=rid):
                            return None
                        item = dict(row)
                        item.update(_evaluate_history_export(item, state))
                        return item
            except OSError:
                continue
    return None


def _evaluate_history_export(row: Dict[str, Any], state: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not _validate_history_row(row):
        return {
            "export_allowed": False,
            "integrity_verified": False,
            "stale_reason": "History record failed integrity verification.",
        }
    if not state:
        return {"export_allowed": False, "integrity_verified": True, "stale_reason": "No active session."}
    if state.get("persistence_memory_rejected") or state.get("requires_refresh_before_export"):
        return {
            "export_allowed": False,
            "integrity_verified": True,
            "stale_reason": "Refresh required before exporting restored context.",
        }
    scan = state.get("scan") or {}
    active_scan = str(scan.get("scan_id") or (state.get("_current_memory") or {}).get("scan_id") or "")
    row_scan = str(row.get("scan_id") or "")
    if active_scan and row_scan and active_scan != row_scan:
        return {
            "export_allowed": False,
            "integrity_verified": True,
            "stale_reason": "Scan changed since this result was saved.",
        }
    record_sig = str((state.get("scan") or {}).get("signature_v2", {}).get("signature") or "")
    if not record_sig:
        mem = state.get("_current_memory") or {}
        record_sig = str(mem.get("scan_signature") or "")
    row_sig = str(row.get("scan_signature") or "")
    if record_sig and row_sig and record_sig != row_sig:
        return {
            "export_allowed": False,
            "integrity_verified": True,
            "stale_reason": "Scan signature changed since this result was saved.",
        }
    try:
        from . import trust_integrity as _ti
        refusal = _ti.require_fresh_context(state, for_export=True)
        if refusal:
            return {"export_allowed": False, "stale_reason": refusal.get("message") or "Refresh required."}
    except Exception:
        pass
    return {"export_allowed": True, "integrity_verified": True, "stale_reason": ""}


def build_workflow_history_record(
    workflow_type: str,
    *,
    request_text: str,
    result: Dict[str, Any],
    state: Dict[str, Any],
) -> Dict[str, Any]:
    plan = result.get("plan") or {}
    export = result.get("export") or {}
    files: List[str] = []
    if workflow_type == "build":
        files = list(plan.get("files_to_inspect_first") or [])[:12]
    elif workflow_type == "investigate":
        for h in (plan.get("hypotheses") or [])[:3]:
            files.extend(h.get("files_involved") or [])
    elif workflow_type == "impact":
        files = list(result.get("direct_impact") or [])[:12]
    trust = {}
    export_allowed = True
    stale_reason = ""
    try:
        from . import trust_integrity as _ti
        trust = _ti.assess_staleness(state)
        refusal = _ti.require_fresh_context(state, for_export=True)
        if refusal:
            export_allowed = False
            stale_reason = refusal.get("message") or ""
    except Exception:
        pass
    mem = state.get("_current_memory") or {}
    scan = state.get("scan") or {}
    scan_sig = (
        (scan.get("signature_v2") or {}).get("signature")
        or (scan.get("cache") or {}).get("signature")
        or mem.get("scan_signature")
        or ""
    )
    return {
        "workflow_type": workflow_type,
        "request_text": request_text,
        "repo_id": _repo_memory.repo_id(str(state.get("path") or scan.get("repo_path") or "")),
        "scan_id": mem.get("scan_id") or scan.get("scan_id") or "",
        "scan_signature": str(scan_sig),
        "atlas_version": PRODUCT_VERSION,
        "files_named": files[:12],
        "confidence": plan.get("confidence") or result.get("confidence"),
        "export_tokens": export.get("tokens"),
        "export_mode": export.get("mode"),
        "summary_markdown": result.get("formatted") or export.get("minimal_text") or "",
        "result_json": _strip_source_like({
            "ok": result.get("ok"),
            "plan": plan,
            "target": result.get("target"),
            "direct_impact": (result.get("direct_impact") or [])[:12],
            "confidence": plan.get("confidence") or result.get("confidence"),
            "risk_level": result.get("risk_level"),
        }),
        "trust_status": trust,
        "export_allowed": export_allowed,
        "stale_reason": stale_reason,
    }


def restore_into_state(
    state: Dict[str, Any],
    bundle: Dict[str, Any],
    *,
    data_dir: str,
) -> Dict[str, Any]:
    return restore_into_state_with_memory(state, bundle, data_dir=data_dir)


def persistence_files_contain_source(data_dir: str) -> List[str]:
    """Test helper — return paths that appear to contain raw source blobs."""
    hits: List[str] = []
    for root, _dirs, files in os.walk(os.path.join(data_dir, "scans")):
        for name in files:
            if not name.endswith(".json"):
                continue
            path = os.path.join(root, name)
            try:
                blob = open(path, encoding="utf-8").read()
            except OSError:
                continue
            if re.search(r'"text"\s*:\s*"(?:[^"\\]|\\.){2000,}"', blob):
                hits.append(path)
    return hits
