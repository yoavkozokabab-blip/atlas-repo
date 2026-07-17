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
import time
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Set, Tuple

# v4: content hashes, not timestamps or Git worktree dirtiness, define identity.
# v3 remains readable so an in-place/silent update can restore an existing scan.
SIGNATURE_VERSION = 4
LEGACY_SIGNATURE_VERSION = 3

_STATE_LOCK = threading.RLock()

# Import scope helpers lazily to avoid circular imports at module load.
_SKIP_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", "node_modules", ".venv", "venv",
    "dist", "build", ".tox", ".pytest_cache", ".mypy_cache", "external_repos",
}
_GENERATED_DIR_PREFIXES = (
    ".checkpoint_", ".design_runtime", ".home_checkpoint_", ".manual_py_temp",
    ".phase", ".pytest_", ".redesign_", "pytest_",
)
_GENERATED_PATH_PREFIXES = (
    "packaging/installer/output/",
    "packaging/installer/staging/",
)
_GENERATED_FILES = {
    "packaging/installer/build_info.json",
    "packaging/installer/generated_version.iss",
}


def _ignored_generated_path(rel: str, *, is_dir: bool = False) -> bool:
    normalized = rel.replace("\\", "/").strip("/")
    parts = normalized.split("/") if normalized else []
    if any(part in _SKIP_DIRS for part in parts):
        return True
    if any(part.startswith(_GENERATED_DIR_PREFIXES) for part in parts):
        return True
    candidate = normalized + ("/" if is_dir and normalized else "")
    if any(candidate.startswith(prefix) for prefix in _GENERATED_PATH_PREFIXES):
        return True
    return normalized in _GENERATED_FILES


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


# Per-file details from the most recent content-hash signature walk, so
# capture_file_manifest() right after a scan reuses that walk's stat+hash work
# instead of re-reading every indexed file.
_WALK_DETAIL_TTL_SECONDS = 1800.0
_LAST_WALK_DETAIL: Dict[str, Any] = {"root": "", "at": 0.0, "files": {}}


def _remember_walk_detail(root: str, files: Dict[str, Dict[str, Any]]) -> None:
    _LAST_WALK_DETAIL.update({
        "root": os.path.abspath(root).lower(),
        "at": time.monotonic(),
        "files": files,
    })


def _recent_walk_detail(root: str) -> Dict[str, Dict[str, Any]]:
    if _LAST_WALK_DETAIL["root"] != os.path.abspath(root).lower():
        return {}
    if time.monotonic() - float(_LAST_WALK_DETAIL["at"]) > _WALK_DETAIL_TTL_SECONDS:
        return {}
    return _LAST_WALK_DETAIL["files"] or {}


def _manifest_entries(
    root: str,
    scope: Dict[str, Any],
    indexed_files: Optional[List[Dict[str, Any]]] = None,
    *,
    include_content_hash: bool = False,
    signature_version: int = SIGNATURE_VERSION,
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
            if include_content_hash and signature_version >= 4:
                part = f"{rel}:{size}:{_content_hash(abs_path)}"
            else:
                part = f"{rel}:{size}:{mtime}"
                if include_content_hash:
                    part += f":{_content_hash(abs_path)}"
            entries.append(part)
    else:
        walk_detail: Dict[str, Dict[str, Any]] = {}
        for dirpath, dirnames, filenames in os.walk(root):
            rel_dir = os.path.relpath(dirpath, root).replace("\\", "/")
            rel_dir = "" if rel_dir == "." else rel_dir
            if signature_version >= 4:
                dirnames[:] = sorted(
                    d for d in dirnames
                    if not _ignored_generated_path(
                        f"{rel_dir}/{d}" if rel_dir else d, is_dir=True
                    )
                )
            else:
                dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS)
            for name in sorted(filenames):
                abs_path = os.path.join(dirpath, name)
                rel = os.path.relpath(abs_path, root).replace("\\", "/")
                if signature_version >= 4 and _ignored_generated_path(rel):
                    continue
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
                content_hash = _content_hash(abs_path) if include_content_hash else ""
                if include_content_hash and signature_version >= 4:
                    part = f"{rel}:{size}:{content_hash}"
                else:
                    part = f"{rel}:{size}:{mtime}"
                    if include_content_hash:
                        part += f":{content_hash}"
                if include_content_hash:
                    walk_detail[rel] = {
                        "size": size,
                        "mtime": mtime,
                        "content_hash": content_hash,
                    }
                entries.append(part)
        if include_content_hash:
            _remember_walk_detail(root, walk_detail)

    # Sort the complete manifest before hashing so the signature depends only
    # on the file SET and per-file metadata — never on traversal order. This is
    # what lets a persisted signature match a fresh live walk of an unchanged
    # repository across process restarts.
    entries.sort()
    manifest_hash = hashlib.sha256("\n".join(entries).encode("utf-8", errors="ignore")).hexdigest()
    return len(entries), total_size, total_mtime, manifest_hash


def compute_signature_v2(
    root: str,
    scope: Dict[str, Any],
    *,
    indexed_files: Optional[List[Dict[str, Any]]] = None,
    include_content_hash: bool = False,
    signature_version: int = SIGNATURE_VERSION,
) -> Dict[str, Any]:
    """Signature v2 — git metadata + full indexed manifest + scope aggregates."""
    abspath = os.path.abspath(root)
    scope_norm = dict(scope or {})
    git = git_metadata(abspath)
    file_count, total_size, total_mtime, manifest_hash = _manifest_entries(
        abspath,
        scope_norm,
        indexed_files,
        include_content_hash=include_content_hash,
        signature_version=signature_version,
    )
    payload = {
        "version": signature_version,
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
    if signature_version >= 4:
        identity = {
            "version": signature_version,
            "root": abspath,
            "scope": scope_norm,
            "file_count": file_count,
            "total_size": total_size,
            "manifest_hash": manifest_hash,
        }
    else:
        identity = payload
    digest = hashlib.sha256(
        json.dumps(identity, sort_keys=True, default=str).encode("utf-8", errors="ignore")
    ).hexdigest()
    payload["signature"] = digest
    return payload


def _norm_path(path: str) -> str:
    return (path or "").replace("\\", "/").strip()


def capture_file_manifest(state: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Snapshot per-file size/mtime/content hash at scan time."""
    scan = state.get("scan") or {}
    path = state.get("path") or scan.get("repo_path")
    if not path:
        return {}
    root = os.path.abspath(str(path))
    walk_detail = _recent_walk_detail(root)
    manifest: Dict[str, Dict[str, Any]] = {}
    for f in (state.get("index") or {}).get("files") or []:
        rel = _norm_path(str(f.get("path") or ""))
        if not rel:
            continue
        known = walk_detail.get(rel)
        if known:
            manifest[rel] = dict(known)
            continue
        abs_path = os.path.join(root, rel.replace("/", os.sep))
        try:
            st = os.stat(abs_path)
            size = int(st.st_size)
            mtime = int(st.st_mtime)
        except OSError:
            size = int(f.get("size") or 0)
            mtime = 0
        manifest[rel] = {
            "size": size,
            "mtime": mtime,
            "content_hash": _content_hash(abs_path),
        }
    state["file_manifest"] = manifest
    return manifest


def update_file_manifest(state: Dict[str, Any], paths: List[str]) -> None:
    """Update manifest entries after targeted refresh."""
    scan = state.get("scan") or {}
    path = state.get("path") or scan.get("repo_path")
    if not path:
        return
    root = os.path.abspath(str(path))
    manifest = dict(state.get("file_manifest") or {})
    for rel in paths:
        rel = _norm_path(rel)
        abs_path = os.path.join(root, rel.replace("/", os.sep))
        try:
            st = os.stat(abs_path)
            manifest[rel] = {
                "size": int(st.st_size),
                "mtime": int(st.st_mtime),
                "content_hash": _content_hash(abs_path),
            }
        except OSError:
            manifest.pop(rel, None)
    state["file_manifest"] = manifest


def detect_changed_files(state: Dict[str, Any]) -> List[str]:
    """Return repo-relative paths that differ from the stored file manifest."""
    scan = state.get("scan") or {}
    path = state.get("path") or scan.get("repo_path")
    if not scan or not path:
        return []
    stored = state.get("file_manifest") or {}
    if not stored:
        capture_file_manifest(state)
        stored = state.get("file_manifest") or {}
    root = os.path.abspath(str(path))
    changed: List[str] = []
    seen: Set[str] = set(stored.keys())
    for rel, meta in stored.items():
        abs_path = os.path.join(root, rel.replace("/", os.sep))
        try:
            st = os.stat(abs_path)
            live = {
                "size": int(st.st_size),
                "mtime": int(st.st_mtime),
                "content_hash": _content_hash(abs_path),
            }
        except OSError:
            changed.append(rel)
            continue
        if (
            live.get("size") != meta.get("size")
            or live.get("content_hash") != meta.get("content_hash")
        ):
            changed.append(rel)
    for f in (state.get("index") or {}).get("files") or []:
        rel = _norm_path(str(f.get("path") or ""))
        if rel and rel not in seen:
            try:
                os.stat(os.path.join(root, rel.replace("/", os.sep)))
                changed.append(rel)
            except OSError:
                pass
    return sorted(set(changed))


def _recommended_file_set(ctx: Dict[str, Any]) -> Set[str]:
    paths: Set[str] = set()
    for key in ("recommended_files", "inspected_files", "likely_modified_files"):
        for p in ctx.get(key) or []:
            if p:
                paths.add(_norm_path(str(p)))
    return paths


def extract_workflow_files(workflow: str, plan_or_result: Dict[str, Any]) -> Dict[str, List[str]]:
    """Collect file paths Atlas recommended for change/inspection."""
    plan = plan_or_result.get("plan") or plan_or_result
    recommended: List[str] = []
    inspected: List[str] = []
    likely_modified: List[str] = []

    if workflow == "build":
        inspected = list(plan.get("files_to_inspect_first") or [])
        likely_modified = list(plan.get("files_likely_to_modify") or plan.get("likely_affected_modules") or [])
        recommended = _dedupe_paths(inspected + likely_modified)
    elif workflow == "investigate":
        for h in (plan.get("hypotheses") or [])[:3]:
            likely_modified.extend(h.get("files_involved") or [])
        likely_modified.extend(plan.get("likely_modules") or [])
        inspected = list(plan.get("recommended_files") or [])
        recommended = _dedupe_paths(inspected + likely_modified)
    elif workflow == "impact":
        target = _norm_path(str(plan_or_result.get("target") or ""))
        affected = list(plan_or_result.get("affected_files") or [])
        direct = list(plan_or_result.get("direct_impact") or [])
        if target:
            recommended = _dedupe_paths([target] + affected[:8] + direct[:8])
        else:
            recommended = _dedupe_paths(affected[:8] + direct[:8])
        likely_modified = list(recommended)
    return {
        "recommended_files": recommended,
        "inspected_files": _dedupe_paths(inspected),
        "likely_modified_files": _dedupe_paths(likely_modified),
    }


def _dedupe_paths(paths: List[str]) -> List[str]:
    out: List[str] = []
    seen: Set[str] = set()
    for p in paths:
        n = _norm_path(str(p))
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def record_workflow_context(
    state: Dict[str, Any],
    workflow: str,
    plan_or_result: Dict[str, Any],
    *,
    memory_ref: str = "",
) -> None:
    """Persist Atlas-recommended files for targeted refresh scoping."""
    files = extract_workflow_files(workflow, plan_or_result)
    scan = state.get("scan") or {}
    mem = state.get("_current_memory") or {}
    ctx = {
        "workflow": workflow,
        **files,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scan_id": mem.get("scan_id") or (state.get("repository_memory") or {}).get("scan_id") or "",
        "memory_ref": memory_ref or mem.get("scan_id") or "",
        "scan_signature": (stored_signature(state) or {}).get("signature"),
        "refresh_generation": int(state.get("refresh_generation") or 0),
        "superseded": False,
    }
    state["workflow_context"] = ctx
    state["active_memory_ref"] = ctx["memory_ref"]


def assess_staleness(
    state: Dict[str, Any], *, live_signature: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Classify repo changes vs last scan and Atlas plan scope."""
    scan = state.get("scan")
    path = state.get("path") or (scan or {}).get("repo_path")
    base = {
        "fresh": True,
        "targeted_refresh_available": False,
        "repo_changed_outside_plan": False,
        "changed_files": [],
        "changed_recommended_files": [],
        "changed_outside_plan_files": [],
        "status": "fresh",
        "message": "",
    }
    if not scan or not path:
        return {**base, "fresh": False, "status": "requires_rescan", "message": "No repository scanned yet."}

    if os.path.abspath(str(scan.get("repo_path") or path)) != os.path.abspath(str(path)):
        return {
            **base,
            "fresh": False,
            "repo_changed_outside_plan": True,
            "status": "stale_scan",
            "message": "Repository path changed since the last scan. Rescan before exporting context.",
        }

    scope = scan.get("scope") or state.get("last_scope") or {"mode": "entire_repo"}
    prev = stored_signature(state)
    signature_version = int((prev or {}).get("version") or LEGACY_SIGNATURE_VERSION)
    live = live_signature or compute_signature_v2(
        str(path), scope, include_content_hash=True, signature_version=signature_version
    )
    git_head_changed = False
    if prev:
        prev_git = prev.get("git_head")
        live_git = live.get("git_head")
        git_head_changed = bool(prev_git and live_git and prev_git != live_git)

    if not git_head_changed and prev and live.get("signature") == prev.get("signature"):
        return base

    changed = detect_changed_files(state)
    if (
        not changed
        and not git_head_changed
        and (not prev or live.get("signature") == prev.get("signature"))
    ):
        return base

    ctx = state.get("workflow_context") or {}
    recommended = _recommended_file_set(ctx) if ctx and not ctx.get("superseded") else set()
    changed_set = {_norm_path(c) for c in changed}
    inside = sorted(changed_set & recommended) if recommended else []
    outside = sorted(changed_set - recommended) if recommended else sorted(changed_set)

    if git_head_changed:
        outside = sorted(set(outside) | set(changed_set))

    if outside or not recommended:
        return {
            **base,
            "fresh": False,
            "repo_changed_outside_plan": True,
            "targeted_refresh_available": False,
            "changed_files": sorted(changed_set),
            "changed_recommended_files": inside,
            "changed_outside_plan_files": outside if outside else sorted(changed_set),
            "status": "stale_git_head_changed" if git_head_changed else "stale_outside_plan",
            "message": (
                "Repository changed outside the last Atlas plan. A full rescan may be required."
            ),
        }

    return {
        **base,
        "fresh": False,
        "targeted_refresh_available": True,
        "repo_changed_outside_plan": False,
        "changed_files": sorted(changed_set),
        "changed_recommended_files": inside,
        "changed_outside_plan_files": [],
        "status": "targeted_refresh_required",
        "message": (
            "Files from the last Atlas plan changed. Refresh those files before exporting new context."
        ),
    }


def attach_trust_status(result: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    """Attach trust/staleness flags without mutating ok for historical workflow views."""
    status = assess_staleness(state)
    result["trust_status"] = status
    result["targeted_refresh_available"] = status.get("targeted_refresh_available", False)
    result["repo_changed_outside_plan"] = status.get("repo_changed_outside_plan", False)
    if not status.get("fresh"):
        result["context_stale"] = True
    return result


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
    """Return refusal dict when context is stale (never triggers rescan)."""
    status = assess_staleness(state)
    if status.get("fresh"):
        return None
    st = status.get("status") or "stale_scan"
    msg = status.get("message") or "Repository changed since the last scan."
    return {
        "ok": False,
        "status": st,
        "message": msg,
        "error": msg,
        "trust_status": status,
        "targeted_refresh_available": status.get("targeted_refresh_available", False),
        "repo_changed_outside_plan": status.get("repo_changed_outside_plan", False),
        "changed_files": status.get("changed_files", []),
    }


_EXPORT_STALE_MSG = (
    "Atlas needs a refresh before exporting context. "
    "The repository changed after this plan was generated."
)


def require_fresh_context(state: Dict[str, Any], *, for_export: bool = False) -> Optional[Dict[str, Any]]:
    """Gate exports on freshness; workflows use attach_trust_status instead."""
    refusal = verify_scan_fresh(state)
    if refusal:
        if for_export:
            refusal["message"] = _EXPORT_STALE_MSG
            refusal["error"] = _EXPORT_STALE_MSG
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
                "message": _EXPORT_STALE_MSG if for_export else "Repository memory does not match the active scan.",
                "error": "Repository memory does not match the active scan.",
            }
        wf = state.get("workflow_context") or {}
        active_ref = state.get("active_memory_ref") or mem.get("scan_id")
        wf_ref = wf.get("memory_ref")
        if for_export and wf_ref and active_ref and wf_ref != active_ref:
            return {
                "ok": False,
                "status": "memory_ref_stale",
                "message": _EXPORT_STALE_MSG,
                "error": "Workflow memory_ref no longer matches after refresh.",
            }

    if for_export and state.get("memory_persistence_status") == "failed":
        # Exports may proceed but must not claim durable cross-session memory.
        pass

    return None


_UNSUPPORTED_PROD_EXTS = {
    ".go", ".rs", ".java", ".cs", ".kt", ".swift", ".rb", ".cpp", ".c", ".h", ".hpp",
}


def _shallow_unsupported_coverage(state: Dict[str, Any], scan: Dict[str, Any]) -> bool:
    """174C A7 — non-Python production dominates but graph is an incidental helper."""
    index = state.get("index") or {}
    non_py_prod = 0
    py_prod = 0
    for f in index.get("files") or []:
        ext = (f.get("ext") or "").lower()
        if (f.get("role") or "") != "production_code":
            continue
        if ext == ".py":
            py_prod += 1
        elif ext in _UNSUPPORTED_PROD_EXTS:
            non_py_prod += 1
    if non_py_prod == 0:
        return False
    modules = int(scan.get("module_count") or 0)
    edges = int(scan.get("dependency_edges") or 0)
    return non_py_prod >= py_prod and modules <= max(2, py_prod) and edges == 0


def weak_graph_gate_applies(state: Dict[str, Any], scan: Dict[str, Any]) -> Tuple[bool, str]:
    """Return (applies, status) for Build/Investigation weak-graph gate."""
    gh = scan.get("graph_health") or {}
    label = gh.get("label") if isinstance(gh, dict) else str(gh or "")
    modules = int(scan.get("module_count") or 0)
    files = int(scan.get("file_count") or 0)
    if label == "unsupported_language_limited":
        return True, "unsupported_language_limited"
    if files > 1000 and modules < 25:
        return True, "unsupported_language_limited"
    if _shallow_unsupported_coverage(state, scan):
        return True, "insufficient_evidence"
    return False, ""


def _file_in_graph(state: Dict[str, Any], path: str) -> bool:
    rel = _norm_path(path)
    for node in (state.get("graph") or {}).get("nodes") or []:
        if node.get("type") == "module" and _norm_path(str(node.get("path") or "")) == rel:
            return True
    return False


def _module_node_id(state: Dict[str, Any], path: str) -> Optional[str]:
    rel = _norm_path(path)
    for node in (state.get("graph") or {}).get("nodes") or []:
        if node.get("type") == "module" and _norm_path(str(node.get("path") or "")) == rel:
            return str(node.get("id") or "")
    return None


def _has_import_graph_evidence(state: Dict[str, Any], path: str) -> bool:
    """Real module import graph evidence — excludes repository contains edges (174F A7 bypass)."""
    rel = _norm_path(path)
    if not _file_in_graph(state, rel):
        return False
    mid = _module_node_id(state, rel)
    if not mid:
        return False
    for edge in (state.get("graph") or {}).get("edges") or []:
        if edge.get("type") != "imports":
            continue
        if not edge.get("resolved"):
            continue
        if edge.get("from") == mid or edge.get("to") == mid:
            return True
    return False


def _file_has_graph_symbol_evidence(state: Dict[str, Any], path: str) -> bool:
    """Symbol + import evidence for healthy graphs (non-weak-gate paths)."""
    rel = _norm_path(path)
    if not _file_in_graph(state, rel):
        return False
    store = state.get("evidence_store") or {}
    sym_files = (store.get("symbol_index") or {}).get("files") or {}
    fdata = sym_files.get(rel) or {}
    symbols = fdata.get("symbols") or []
    calls = fdata.get("calls") or []
    if not symbols:
        return False
    if _has_import_graph_evidence(state, rel):
        return True
    return bool(calls) and len(symbols) >= 1


def _plan_candidate_paths(plan: Dict[str, Any], workflow: str) -> List[str]:
    paths: List[str] = []
    if workflow == "build":
        paths.extend(plan.get("files_to_inspect_first") or [])
        paths.extend(plan.get("files_likely_to_modify") or [])
    else:
        for h in (plan.get("hypotheses") or [])[:3]:
            paths.extend(h.get("files_involved") or [])
        paths.extend(plan.get("likely_modules") or [])
        paths.extend(plan.get("recommended_files") or [])
    return _dedupe_paths([str(p) for p in paths if p])


def _weak_graph_evidence_allows(state: Dict[str, Any], plan: Dict[str, Any], workflow: str) -> bool:
    """174F — identical strict evidence rule for Build and Investigation."""
    candidates = _plan_candidate_paths(plan, workflow)
    rev = plan.get("repository_evidence") or (plan.get("domain_knowledge") or {}).get("repository_evidence") or {}
    for fe in rev.get("file_evidences") or []:
        path = _norm_path(str(fe.get("path") or ""))
        if not (fe.get("matching_symbols") or int(fe.get("evidence_score") or 0) >= 50):
            continue
        if _has_import_graph_evidence(state, path):
            return True
    for path in candidates:
        if _has_import_graph_evidence(state, path):
            return True
    return False


def _has_exact_file_evidence(state: Dict[str, Any], plan: Dict[str, Any]) -> bool:
    return _weak_graph_evidence_allows(state, plan, "build")


def _has_exact_investigation_evidence(state: Dict[str, Any], plan: Dict[str, Any]) -> bool:
    return _weak_graph_evidence_allows(state, plan, "investigate")


def gate_weak_graph_workflow(state: Dict[str, Any], result: Dict[str, Any], workflow: str) -> Dict[str, Any]:
    """Refuse ok=true on unsupported/shallow graphs unless import-graph evidence exists."""
    if not result.get("ok"):
        return result
    scan = state.get("scan") or {}
    applies, status = weak_graph_gate_applies(state, scan)
    if not applies:
        return result

    plan = result.get("plan") or {}
    if _weak_graph_evidence_allows(state, plan, workflow):
        return result

    gh = scan.get("graph_health") or {}
    label = gh.get("label") if isinstance(gh, dict) else str(gh or "unknown")
    return {
        "ok": False,
        "status": status,
        "insufficient_evidence": True,
        "error": (
            "Graph coverage is too limited for this repository language. "
            "Atlas needs exact file or symbol evidence — provide a file path and rescan."
        ),
        "message": (
            "Graph coverage is too shallow for Build/Investigation on this repository. "
            "Provide an exact file path with graph/symbol evidence or rescan after changes."
        ),
        "graph_health": label,
        "confidence": "low",
    }


def trust_integrity_diagnostics(
    state: Dict[str, Any],
    *,
    staleness: Optional[Dict[str, Any]] = None,
    live_signature: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Expose trust-integrity status for support bundles."""
    scan = state.get("scan") or {}
    live = live_signature
    stale = None
    path = state.get("path") or scan.get("repo_path")
    if staleness is None and path and scan:
        scope = scan.get("scope") or state.get("last_scope") or {"mode": "entire_repo"}
        try:
            prev = stored_signature(state) or {}
            live = compute_signature_v2(
                str(path),
                scope,
                include_content_hash=True,
                signature_version=int(prev.get("version") or LEGACY_SIGNATURE_VERSION),
            )
            staleness = assess_staleness(state, live_signature=live)
            if not staleness.get("fresh"):
                stale = {
                    "ok": False,
                    "status": staleness.get("status") or "stale_scan",
                    "trust_status": staleness,
                }
        except Exception as exc:
            stale = {"ok": False, "status": "signature_error", "error": str(exc)}
    gh = scan.get("graph_health") or {}
    if staleness is None:
        try:
            staleness = assess_staleness(state, live_signature=live)
        except Exception as exc:
            staleness = {"fresh": False, "status": "signature_error", "error": str(exc)}
    return {
        "signature_version": SIGNATURE_VERSION,
        "stored_signature": (stored_signature(state) or {}).get("signature"),
        "live_signature": staleness.get("live_signature") or (live or {}).get("signature"),
        "scan_stale": bool(stale or not staleness.get("fresh", False)),
        "stale_status": (stale or {}).get("status") or (
            None if staleness.get("fresh") else staleness.get("status")
        ),
        "targeted_refresh_available": staleness.get("targeted_refresh_available", False),
        "repo_changed_outside_plan": staleness.get("repo_changed_outside_plan", False),
        "changed_files": staleness.get("changed_files", []),
        "workflow_context": bool(state.get("workflow_context")),
        "refresh_generation": state.get("refresh_generation", 0),
        "memory_persistence_status": state.get("memory_persistence_status", "unknown"),
        "memory_persistence_error": state.get("memory_persistence_error"),
        "graph_health": gh.get("label") if isinstance(gh, dict) else gh,
        "state_lock": "threading.RLock",
    }
