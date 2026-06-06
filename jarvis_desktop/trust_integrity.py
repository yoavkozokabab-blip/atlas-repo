"""Phase 174B — trust integrity guards for stale/poisoned context.

Validates scan signatures, repository memory integrity, and export safety.
No intelligence changes — state/signature/memory/export path only.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

SIGNATURE_VERSION = 2

_STATE_LOCK = threading.RLock()

# Import scope helpers lazily to avoid circular imports at module load.
_SKIP_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", "node_modules", ".venv", "venv",
    "dist", "build", ".tox", ".pytest_cache", ".mypy_cache", "external_repos",
}


@contextmanager
def state_guard():
    """Minimal lock around shared product state mutations and reads."""
    _STATE_LOCK.acquire()
    try:
        yield
    finally:
        _STATE_LOCK.release()


def git_metadata(repo: str) -> Dict[str, Any]:
    """Best-effort git HEAD/branch/dirty without requiring git for non-repos."""
    meta: Dict[str, Any] = {"head": None, "branch": None, "dirty": None}
    git_dir = os.path.join(repo, ".git")
    if not os.path.isdir(git_dir):
        return meta
    try:
        with open(os.path.join(git_dir, "HEAD"), encoding="utf-8", errors="ignore") as fh:
            head = fh.read().strip()
        if head.startswith("ref: "):
            ref = head[5:].strip()
            meta["branch"] = ref.rsplit("/", 1)[-1]
            ref_path = os.path.join(git_dir, ref.replace("/", os.sep))
            if os.path.isfile(ref_path):
                with open(ref_path, encoding="utf-8", errors="ignore") as rf:
                    meta["head"] = rf.read().strip()
        else:
            meta["head"] = head
    except OSError:
        pass
    try:
        proc = subprocess.run(
            ["git", "-C", repo, "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        if proc.returncode == 0:
            meta["dirty"] = bool(proc.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return meta


def _content_hash(abs_path: str, max_bytes: int = 262_144) -> str:
    try:
        with open(abs_path, "rb") as fh:
            data = fh.read(max_bytes)
        return hashlib.sha256(data).hexdigest()[:16]
    except OSError:
        return ""


def _manifest_entries(
    root: str,
    scope: Dict[str, Any],
    indexed_files: Optional[List[Dict[str, Any]]] = None,
    *,
    include_content_hash: bool = False,
) -> Tuple[int, int, int, str]:
    """Return file_count, total_size, total_mtime, manifest_hash."""
    from . import api as _api  # local import — scope/file rules live in api

    entries: List[str] = []
    total_size = 0
    total_mtime = 0

    if indexed_files is not None:
        for f in sorted(indexed_files, key=lambda x: str(x.get("path") or "")):
            rel = str(f.get("path") or "").replace("\\", "/")
            if not rel:
                continue
            abs_path = os.path.join(root, rel.replace("/", os.sep))
            try:
                st = os.stat(abs_path)
                size = int(st.st_size)
                mtime = int(st.st_mtime)
            except OSError:
                size = int(f.get("size") or 0)
                mtime = 0
            total_size += size
            total_mtime += mtime
            part = f"{rel}:{size}:{mtime}"
            if include_content_hash:
                part += f":{_content_hash(abs_path)}"
            entries.append(part)
    else:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS)
            for name in sorted(filenames):
                abs_path = os.path.join(dirpath, name)
                rel = os.path.relpath(abs_path, root).replace("\\", "/")
                ext = os.path.splitext(name)[1].lower()
                if _api._is_binary_ext(ext) or ext in {".log", ".tmp", ".cache", ".lock"}:
                    continue
                if not _api._scope_allows(rel, ext, scope):
                    continue
                try:
                    st = os.stat(abs_path)
                except OSError:
                    continue
                size = int(st.st_size)
                mtime = int(st.st_mtime)
                total_size += size
                total_mtime += mtime
                part = f"{rel}:{size}:{mtime}"
                if include_content_hash:
                    part += f":{_content_hash(abs_path)}"
                entries.append(part)

    manifest_hash = hashlib.sha256("\n".join(entries).encode("utf-8", errors="ignore")).hexdigest()
    return len(entries), total_size, total_mtime, manifest_hash


def compute_signature_v2(
    root: str,
    scope: Dict[str, Any],
    *,
    indexed_files: Optional[List[Dict[str, Any]]] = None,
    include_content_hash: bool = False,
) -> Dict[str, Any]:
    """Signature v2 — git metadata + full indexed manifest + scope aggregates."""
    abspath = os.path.abspath(root)
    scope_norm = dict(scope or {})
    git = git_metadata(abspath)
    file_count, total_size, total_mtime, manifest_hash = _manifest_entries(
        abspath, scope_norm, indexed_files, include_content_hash=include_content_hash
    )
    payload = {
        "version": SIGNATURE_VERSION,
        "root": abspath,
        "scope": scope_norm,
        "git_head": git.get("head"),
        "git_branch": git.get("branch"),
        "git_dirty": git.get("dirty"),
        "file_count": file_count,
        "total_size": total_size,
        "total_mtime": total_mtime,
        "manifest_hash": manifest_hash,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8", errors="ignore")
    ).hexdigest()
    payload["signature"] = digest
    return payload


def stored_signature(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    scan = state.get("scan") or {}
    sig = scan.get("signature_v2")
    if isinstance(sig, dict) and sig.get("signature"):
        return sig
    legacy = (scan.get("cache") or {}).get("signature")
    if legacy:
        return {"signature": legacy, "version": 1}
    return None


def verify_scan_fresh(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return refusal dict when active scan no longer matches repository on disk."""
    scan = state.get("scan")
    path = state.get("path") or (scan or {}).get("repo_path")
    if not scan or not path:
        return {
            "ok": False,
            "status": "requires_rescan",
            "message": "No repository scanned yet.",
            "error": "No repository scanned yet.",
        }
    if os.path.abspath(str(scan.get("repo_path") or path)) != os.path.abspath(str(path)):
        return {
            "ok": False,
            "status": "stale_scan",
            "message": "Repository path changed since the last scan. Rescan before exporting context.",
            "error": "Repository path changed since the last scan.",
        }

    scope = scan.get("scope") or state.get("last_scope") or {"mode": "entire_repo"}
    index_files = (state.get("index") or {}).get("files")
    live = compute_signature_v2(
        str(path), scope, indexed_files=index_files, include_content_hash=bool(index_files)
    )
    prev = stored_signature(state)
    if not prev or live.get("signature") == prev.get("signature"):
        return None

    prev_git = (prev or {}).get("git_head") if isinstance(prev, dict) else None
    live_git = live.get("git_head")
    if prev_git and live_git and prev_git != live_git:
        status = "stale_git_head_changed"
        msg = "Git HEAD changed since the last scan. Rescan before exporting context."
    else:
        status = "stale_scan"
        msg = "Repository changed since the last scan. Rescan before exporting context."

    return {"ok": False, "status": status, "message": msg, "error": msg}


def require_fresh_context(state: Dict[str, Any], *, for_export: bool = False) -> Optional[Dict[str, Any]]:
    """Gate workflows/exports on path, signature, memory, and graph health."""
    refusal = verify_scan_fresh(state)
    if refusal:
        if for_export and refusal.get("status") in ("stale_scan", "stale_git_head_changed"):
            refusal["message"] = "Atlas needs a fresh scan before exporting this context."
            refusal["error"] = refusal["message"]
        return refusal

    scan = state.get("scan") or {}
    gh = scan.get("graph_health") or {}
    label = gh.get("label") if isinstance(gh, dict) else str(gh or "")
    if not label:
        return {
            "ok": False,
            "status": "requires_rescan",
            "message": "Atlas needs a fresh scan before exporting this context.",
            "error": "Graph health unknown — rescan required.",
        }

    mem = state.get("_current_memory") or {}
    if mem:
        from . import repository_memory as rm

        if not rm.verify_memory_record(mem, str(state.get("path") or scan.get("repo_path") or "")):
            return {
                "ok": False,
                "status": "memory_invalid",
                "message": "Atlas needs a fresh scan before exporting this context.",
                "error": "Repository memory failed integrity check.",
            }
        stored_sig = (stored_signature(state) or {}).get("signature")
        mem_sig = mem.get("scan_signature")
        if stored_sig and mem_sig and stored_sig != mem_sig:
            return {
                "ok": False,
                "status": "memory_stale",
                "message": "Atlas needs a fresh scan before exporting this context.",
                "error": "Repository memory does not match the active scan.",
            }

    if for_export and state.get("memory_persistence_status") == "failed":
        # Exports may proceed but must not claim durable cross-session memory.
        pass

    return None


def _has_exact_file_evidence(plan: Dict[str, Any]) -> bool:
    files = plan.get("files_to_inspect_first") or plan.get("files_likely_to_modify") or []
    if not files:
        return False
    rev = plan.get("repository_evidence") or (plan.get("domain_knowledge") or {}).get("repository_evidence") or {}
    file_evs = rev.get("file_evidences") or []
    if file_evs:
        for fe in file_evs:
            if fe.get("path") in files and (fe.get("matching_symbols") or fe.get("evidence_score", 0) >= 50):
                return True
    # Exact path list without symbol panel still counts as file evidence.
    return bool(files)


def _has_exact_investigation_evidence(plan: Dict[str, Any]) -> bool:
    hyps = plan.get("hypotheses") or []
    for h in hyps[:3]:
        if h.get("files_involved") and (h.get("evidence") or h.get("verification_steps")):
            return True
    rev = plan.get("repository_evidence") or {}
    if rev.get("file_evidences"):
        return True
    return False


def gate_weak_graph_workflow(state: Dict[str, Any], result: Dict[str, Any], workflow: str) -> Dict[str, Any]:
    """Refuse ok=true on unsupported graphs unless exact file/symbol evidence exists."""
    if not result.get("ok"):
        return result
    scan = state.get("scan") or {}
    gh = scan.get("graph_health") or {}
    label = gh.get("label") if isinstance(gh, dict) else str(gh or "")
    if label != "unsupported_language_limited":
        return result

    plan = result.get("plan") or {}
    if workflow == "build" and _has_exact_file_evidence(plan):
        return result
    if workflow == "investigate" and _has_exact_investigation_evidence(plan):
        return result

    return {
        "ok": False,
        "status": "unsupported_language_limited",
        "insufficient_evidence": True,
        "error": (
            "Graph coverage is too limited for this repository language. "
            "Atlas needs exact file or symbol evidence — provide a file path and rescan."
        ),
        "message": (
            "Graph health is unsupported_language_limited and Atlas found no exact "
            "file/symbol evidence for this request."
        ),
        "graph_health": label,
        "confidence": "low",
    }


def trust_integrity_diagnostics(state: Dict[str, Any]) -> Dict[str, Any]:
    """Expose trust-integrity status for support bundles."""
    scan = state.get("scan") or {}
    live = None
    stale = None
    path = state.get("path") or scan.get("repo_path")
    if path and scan:
        scope = scan.get("scope") or state.get("last_scope") or {"mode": "entire_repo"}
        index_files = (state.get("index") or {}).get("files")
        try:
            live = compute_signature_v2(str(path), scope, indexed_files=index_files)
            stale = verify_scan_fresh(state)
        except Exception as exc:
            stale = {"ok": False, "status": "signature_error", "error": str(exc)}
    gh = scan.get("graph_health") or {}
    return {
        "signature_version": SIGNATURE_VERSION,
        "stored_signature": (stored_signature(state) or {}).get("signature"),
        "live_signature": (live or {}).get("signature"),
        "scan_stale": bool(stale),
        "stale_status": (stale or {}).get("status"),
        "memory_persistence_status": state.get("memory_persistence_status", "unknown"),
        "memory_persistence_error": state.get("memory_persistence_error"),
        "graph_health": gh.get("label") if isinstance(gh, dict) else gh,
        "state_lock": "threading.RLock",
    }
