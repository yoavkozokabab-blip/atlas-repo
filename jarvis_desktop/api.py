"""Framework-agnostic product API core for JARVIS Desktop.

Pure functions returning JSON-able dicts, wrapping the existing Builder Core
engine (indexer roles, production-scope dependency graph, architectural risk
ranking). No web framework, no network, no external APIs — so it is fully unit
testable and the desktop server is a thin adapter over this module.

Where a real Builder Core surface is wired it is used directly. Where a surface
is not yet wired (deep bug semantics), a clearly-marked heuristic/mock is used.
Search ``MOCK``/``TODO`` for those spots.
"""

from __future__ import annotations

import base64
import fnmatch
import hashlib
import io
import json as _json
import math
import os
import re
import time
import zipfile
from typing import Any, Dict, List, Optional, Set, Tuple

from builder_core import architectural_risk, repository_understanding
from builder_core.bug_intelligence import depgraph

from . import analytics
from . import graph_build
from . import planning_engine
from . import reliability
from .evidence_engine import build_evidence_store
from . import usage as usage_tracking

PRODUCT_VERSION = "phase146b-true-beta-blocker-fixes"
CHARS_PER_TOKEN = 4.0
GRAPH_DISPLAY_CAP = 5000
GRAPH_DEFAULT_HIERARCHY_THRESHOLD = 1000
RISK_RANK_TOP = 5000
MODULE_VISUAL_SIZE_MIN = 5.5
MODULE_VISUAL_SIZE_MAX = 28.0
MODULE_HUB_FAN_IN_MIN = 8

ARCHITECTURE_CLUSTER_PATTERNS: List[Tuple[str, Tuple[str, ...]]] = [
    ("Event Bus", ("/core.py", "homeassistant/core", "helpers/event", "eventbus")),
    ("WebSocket", ("websocket_api", "components/websocket", "/websocket")),
    ("Auth", ("homeassistant/auth", "/auth/", "auth_store", "auth_provider")),
    ("Automations", ("components/automation", "/automation/")),
    ("Recorder", ("components/recorder", "/recorder/")),
    ("Config Entries", ("config_entries", "config_entry")),
    ("HTTP API", ("components/http", "components/api", "/http/")),
    ("Components", ("homeassistant/components/", "components/")),
    ("Helpers", ("homeassistant/helpers/", "/helpers/")),
    ("Core", ("/core/", "homeassistant/core", "foundation", "kernel")),
    ("Platform", ("platform", "base/common")),
    ("Workbench", ("workbench",)),
    ("Editor", ("editor", "monaco", "vs/editor")),
    ("Extension Host", ("extension", "extensions", "ext_host", "extensionhost")),
    ("Services", ("services", "service")),
    ("Terminal", ("terminal", "xterm", "pty")),
    ("Testing", ("testing", "test/", "/test")),
    ("Debug", ("debug", "debugger")),
    ("Shared", ("shared", "util", "utils")),
]
UNRESOLVED_IMPORT_PARTIAL_MIN = 100
UNRESOLVED_IMPORT_PARTIAL_RATIO = 0.35
MASSIVE_FILES_THRESHOLD = 20_000
MASSIVE_MODULES_THRESHOLD = 5_000
MASSIVE_SIZE_THRESHOLD_BYTES = 1_000_000_000

_CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".cs", ".rb",
    ".cpp", ".c", ".h", ".hpp", ".swift", ".kt", ".scala", ".php", ".vue",
}
_DEMO_ROOT = os.path.join(os.path.dirname(__file__), "demo")
_DEMO_PACKS: Dict[str, Dict[str, Any]] = {
    "small": {
        "id": "small",
        "label": "Small demo",
        "description": "Quick wow moment — 6 modules, one import cycle.",
        "path": os.path.join(_DEMO_ROOT, "small_repo"),
        "fallback": os.path.join(_DEMO_ROOT, "sample_repo"),
    },
    "medium": {
        "id": "medium",
        "label": "Medium demo",
        "description": "Multi-subsystem app — ~18 modules, cross-service edges.",
        "path": os.path.join(_DEMO_ROOT, "medium_repo"),
        "fallback": None,
    },
    "large": {
        "id": "large",
        "label": "Large demo",
        "description": "Galaxy-scale graph — ~40 modules across six subsystems.",
        "path": os.path.join(_DEMO_ROOT, "large_repo"),
        "fallback": None,
    },
}

# Directories pruned from the light index walk (keeps scans fast + excludes the
# vendored data corpus, mirroring the depgraph production scope).
_SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", "env", ".env",
    "dist", "build", ".pytest_cache", ".mypy_cache", ".idea", ".vscode",
    "site-packages", ".tox", "target", "vendor", ".next", ".cache", "coverage",
    "htmlcov", ".gradle", ".pytest_tmp", "tests_tmp", "backups", "data",
    ".jarvis_builder", ".jarvis",
}

# Single-repo product state (one repository open at a time).
_STATE: Dict[str, Any] = {
    "path": None,
    "scan": None,
    "graph": None,
    "index": None,
    "risks": None,
    "demo_mode": False,
    "last_scope": {"mode": "entire_repo"},
    "scan_cache": {},
    "scan_job": {"id": None, "cancelled": False, "stage": "idle"},
    "scan_perf": None,
    "scan_perf_live": None,
    "workflow_perf": {},
    "graph_detail_level": None,
    "full_graph_pending": False,
}


def _record_workflow_timing(name: str, started: float) -> None:
    """Phase 139 — last-run timings for beta performance dashboard."""
    _STATE.setdefault("workflow_perf", {})[name] = {
        "duration_ms": int(round((time.time() - started) * 1000)),
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def _evidence_coverage() -> Dict[str, Any]:
    store = _STATE.get("evidence_store") or {}
    sym = store.get("symbol_index") or {}
    return {
        "symbol_count": int(sym.get("symbol_count") or 0),
        "files_with_symbols": len(sym.get("files") or {}),
        "call_graph_edges": len((store.get("call_graph") or {}).get("edges") or []),
    }

# Backend stage → (progress %, UI label) for real scan progress reporting.
_SCAN_STAGE_PROGRESS: Dict[str, Tuple[int, str]] = {
    "discovering_files": (8, "Indexing repository"),
    "building_graph": (42, "Building dependency graph"),
    "indexing_modules": (52, "Indexing repository"),
    "ranking_risks": (68, "Detecting architectural risks"),
    "extracting_architecture": (76, "Extracting architecture"),
    "extracting_contracts": (82, "Extracting contracts"),
    "generating_evidence": (86, "Generating verification evidence"),
    "generating_summary": (92, "Building AI context packets"),
    "completed": (100, "Complete"),
    "cancel_requested": (0, "Cancelling"),
    "idle": (0, "Idle"),
}


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def estimate_tokens(text: str) -> int:
    return max(0, round(len(text or "") / CHARS_PER_TOKEN))


_JS_TS_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")


def _annotate_multilang_risk_signals(risks: Dict[str, Any]) -> Dict[str, Any]:
    """Mark Python-only risk channels unavailable for JS/TS modules (not zero)."""
    for row in risks.get("ranked_modules", []):
        path = str(row.get("path") or "")
        if any(path.endswith(ext) for ext in _JS_TS_EXTS):
            row["signal_availability"] = {
                "contract_evidence": "unavailable",
                "static_findings": "unavailable",
                "test_evidence": "unavailable",
            }
    return risks


def _safe_rss_bytes() -> Optional[int]:
    try:
        import resource  # type: ignore

        rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        # Linux reports KiB, macOS bytes. Use a conservative heuristic.
        return rss * 1024 if rss < 10_000_000 else rss
    except Exception:
        return None


class _StageRecorder:
    """Lightweight stage timing recorder for scan diagnostics."""

    def __init__(self, *, repo_path: str, scope: Dict[str, Any], cache_hit: bool) -> None:
        self.started_at = time.time()
        self.repo_path = repo_path
        self.scope = scope
        self.cache_hit = cache_hit
        self.events: List[Dict[str, Any]] = []

    def mark(self, stage: str, start_ts: float, end_ts: float, **meta: Any) -> None:
        payload = {
            "stage": stage,
            "start_time": start_ts,
            "end_time": end_ts,
            "duration_ms": int(round((end_ts - start_ts) * 1000)),
            "memory_rss_bytes": _safe_rss_bytes(),
            "cache_hit": self.cache_hit,
        }
        payload.update(meta)
        self.events.append(payload)
        _STATE["scan_perf_live"] = {
            "repo_path": self.repo_path,
            "scope": self.scope,
            "cache_hit": self.cache_hit,
            "started_at": self.started_at,
            "events": list(self.events),
        }

    def snapshot(self) -> Dict[str, Any]:
        finished = time.time()
        return {
            "repo_path": self.repo_path,
            "scope": self.scope,
            "cache_hit": self.cache_hit,
            "started_at": self.started_at,
            "finished_at": finished,
            "total_duration_ms": int(round((finished - self.started_at) * 1000)),
            "events": self.events,
        }


def _read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8-sig", errors="ignore") as fh:
            return fh.read()
    except OSError:
        return ""


def _light_index(root: str, scope: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Fast index: file roles + subsystem map, WITHOUT the slow per-file analysis.

    Sufficient for ``architectural_risk.rank_modules`` (which tolerates empty
    ``python_analysis``/``churn``) and the product summary.
    """
    root = os.path.abspath(root)
    scope = _scope_from_input(scope)
    files: List[Dict[str, Any]] = []
    py_docs: List[Dict[str, str]] = []
    role_counts: Dict[str, int] = {}
    excluded_count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS)
        for name in sorted(filenames):
            abs_path = os.path.join(dirpath, name)
            rel = os.path.relpath(abs_path, root).replace("\\", "/")
            ext = os.path.splitext(name)[1].lower()
            if _is_binary_ext(ext) or ext in {".log", ".tmp", ".cache", ".lock"}:
                excluded_count += 1
                continue
            if not _scope_allows(rel, ext, scope):
                excluded_count += 1
                continue
            role = repository_understanding.classify_file_role(rel, ext, project_root=root)
            try:
                size = os.path.getsize(abs_path)
            except OSError:
                continue
            text = _read(abs_path) if ext == ".py" and size < 400_000 else ""
            files.append({
                "path": rel,
                "role": role,
                "category": repository_understanding.legacy_category(role, rel),
                "ext": ext,
                "size": size,
                "lines": (text.count("\n") + 1) if text else 0,
            })
            role_counts[role] = role_counts.get(role, 0) + 1
            if role == "production_code" and text:
                py_docs.append({"path": rel, "text": text})
    subsystems = repository_understanding.discover_subsystems(files, py_docs)
    return {
        "project_root": root,
        "files": files,
        "subsystems": subsystems,
        "python_analysis": [],   # skipped for speed; rank_modules tolerates this
        "churn": {},
        "chunks": [],
        "stats": {"files": len(files), "roles": role_counts},
        "excluded_files": excluded_count,
        "scope": scope,
    }


def _short(node_id: str) -> str:
    return node_id.split(":", 1)[1] if ":" in node_id else node_id


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------
def health() -> Dict[str, Any]:
    scan = _STATE.get("scan") or {}
    telemetry = analytics.status_snapshot()
    return {
        "ok": True,
        "status": "ok",
        "product": "ATLAS",
        "tagline": "Repository Intelligence Platform",
        "version": PRODUCT_VERSION,
        "repository_open": bool(scan),
        "demo_mode": bool(_STATE.get("demo_mode")),
        "repo_name": scan.get("repo_name"),
        "billing_ui_enabled": usage_tracking.billing_ui_enabled(),
        "usage_enforcement_enabled": usage_tracking.enforcement_enabled(),
        **telemetry,
    }


def _usage_symbols_count() -> int:
    store = _STATE.get("evidence_store") or {}
    return int((store.get("symbol_index") or {}).get("symbol_count") or 0)


def _record_usage(event_type: str, **meta: Any) -> None:
    """Best-effort usage telemetry — never raises."""
    try:
        scan = _STATE.get("scan") or {}
        usage_tracking.record_from_scan(
            event_type,
            scan,
            repo_path=_STATE.get("path") or scan.get("repo_path") or "",
            symbols_count=_usage_symbols_count(),
            meta=meta or None,
        )
    except Exception:
        pass


def usage_me() -> Dict[str, Any]:
    return usage_tracking.usage_me_summary()


def usage_admin() -> Dict[str, Any]:
    ctx = usage_tracking.current_context()
    admin = ctx.get("is_admin") or os.environ.get("ATLAS_ADMIN", "").strip().lower() in ("1", "true", "yes")
    return usage_tracking.usage_admin_summary(is_admin=admin)


def usage_plans() -> Dict[str, Any]:
    return usage_tracking.plans_api()


def usage_pricing() -> Dict[str, Any]:
    return usage_tracking.pricing_api()


def usage_post_event(body: Dict[str, Any]) -> Dict[str, Any]:
    event_type = str(body.get("event_type") or body.get("event") or "")
    scan = _STATE.get("scan") or {}
    return usage_tracking.record_from_scan(
        event_type,
        scan,
        repo_path=str(body.get("repo_path") or _STATE.get("path") or scan.get("repo_path") or ""),
        symbols_count=int(body.get("symbols_count") or _usage_symbols_count()),
        meta={k: v for k, v in body.items() if k not in ("event_type", "event")},
    )


def demo_repo_path(pack: str = "small") -> str:
    """Resolve bundled demo repository path for a pack id."""
    key = (pack or "small").strip().lower()
    meta = _DEMO_PACKS.get(key) or _DEMO_PACKS["small"]
    primary = os.path.abspath(meta["path"])
    if os.path.isdir(primary):
        return primary
    fallback = meta.get("fallback")
    if fallback and os.path.isdir(fallback):
        return os.path.abspath(fallback)
    return primary


def list_demo_packs() -> Dict[str, Any]:
    packs = []
    for meta in _DEMO_PACKS.values():
        path = demo_repo_path(meta["id"])
        packs.append(
            {
                "id": meta["id"],
                "label": meta["label"],
                "description": meta["description"],
                "available": os.path.isdir(path),
                "path": path,
            }
        )
    return {"ok": True, "packs": packs, "default": "small"}


def track_analytics_event(event: str, **properties: Any) -> Dict[str, Any]:
    return analytics.track_event(event, product=PRODUCT_VERSION, **properties)


def _attach_analytics_status(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Merge telemetry status into API payloads without affecting scan success."""
    snap = analytics.status_snapshot()
    payload["analytics_status"] = snap["analytics_status"]
    if snap["analytics_status"] == "degraded":
        warning = snap["telemetry_warning"]
        payload["telemetry_warning"] = warning
        warnings = list(payload.get("warnings") or [])
        if warning and warning not in warnings:
            warnings.append(warning)
        payload["warnings"] = warnings
    return payload


def analytics_overview() -> Dict[str, Any]:
    return analytics.analytics_summary()

def _count_code_files(root: str) -> Tuple[int, int]:
    """Return (total_files, code_files) under root, skipping vendor dirs."""
    total = 0
    code = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS)
        for name in filenames:
            total += 1
            ext = os.path.splitext(name)[1].lower()
            if ext in _CODE_EXTENSIONS:
                code += 1
    return total, code


def _infer_bucket(path: str) -> str:
    p = path.replace("\\", "/").lower()
    if any(token in p for token in ("/frontend/", "/web/", "/ui/", "/client/")):
        return "frontend"
    if any(token in p for token in ("/backend/", "/api/", "/server/", "/services/")):
        return "backend"
    return "other"


def _is_binary_ext(ext: str) -> bool:
    return ext in {
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp", ".pdf", ".zip",
        ".tar", ".gz", ".7z", ".exe", ".dll", ".so", ".dylib", ".o", ".a", ".class",
        ".jar", ".mp4", ".mov", ".avi", ".mp3", ".wav", ".bin",
    }


def _scan_signature(root: str, scope: Dict[str, Any]) -> str:
    hasher = hashlib.sha256()
    hasher.update(os.path.abspath(root).encode("utf-8", errors="ignore"))
    hasher.update(_json.dumps(scope, sort_keys=True).encode("utf-8", errors="ignore"))
    sample = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS)
        for name in sorted(filenames):
            if sample >= 2500:
                break
            path = os.path.join(dirpath, name)
            try:
                st = os.stat(path)
            except OSError:
                continue
            hasher.update(str(st.st_size).encode())
            hasher.update(str(int(st.st_mtime)).encode())
            sample += 1
        if sample >= 2500:
            break
    return hasher.hexdigest()


def _scope_from_input(scope: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    scope = scope or {}
    mode = str(scope.get("mode", "entire_repo")).strip().lower()
    if mode not in {"entire_repo", "folder", "python_only", "backend", "frontend", "custom"}:
        mode = "entire_repo"
    return {
        "mode": mode,
        "folder": str(scope.get("folder", "")).strip().replace("\\", "/"),
        "include_patterns": [str(x).strip() for x in (scope.get("include_patterns") or []) if str(x).strip()],
        "exclude_patterns": [str(x).strip() for x in (scope.get("exclude_patterns") or []) if str(x).strip()],
        "manual_massive_mode": bool(scope.get("manual_massive_mode", False)),
    }


def _scope_allows(path: str, ext: str, scope: Dict[str, Any]) -> bool:
    rel = path.replace("\\", "/")
    mode = scope.get("mode", "entire_repo")
    if mode == "folder":
        folder = (scope.get("folder") or "").strip("/")
        if folder and not (rel == folder or rel.startswith(folder + "/")):
            return False
    elif mode == "python_only":
        if ext != ".py":
            return False
    elif mode == "backend":
        if _infer_bucket("/" + rel) != "backend":
            return False
    elif mode == "frontend":
        if _infer_bucket("/" + rel) != "frontend":
            return False
    elif mode == "custom":
        includes = scope.get("include_patterns") or []
        excludes = scope.get("exclude_patterns") or []
        if includes and not any(fnmatch.fnmatch(rel, pat) for pat in includes):
            return False
        if excludes and any(fnmatch.fnmatch(rel, pat) for pat in excludes):
            return False
    return True


def validate_repository_path(path: str) -> Dict[str, Any]:
    """Validate a repository path before scan (exists, readable, contains code)."""
    raw = (path or "").strip()
    if not raw:
        return {
            "ok": False,
            "code": "empty_path",
            "error": "Enter a folder path to scan.",
            "warnings": [],
        }
    abspath = os.path.abspath(os.path.expanduser(raw))
    if not os.path.exists(abspath):
        return {
            "ok": False,
            "code": "not_found",
            "error": f"Path does not exist: {abspath}",
            "path": abspath,
            "warnings": [],
        }
    if not os.path.isdir(abspath):
        return {
            "ok": False,
            "code": "not_directory",
            "error": f"Path is not a folder: {abspath}",
            "path": abspath,
            "warnings": [],
        }
    if not os.access(abspath, os.R_OK | os.X_OK):
        return {
            "ok": False,
            "code": "permission_denied",
            "error": f"Cannot read folder (check permissions): {abspath}",
            "path": abspath,
            "warnings": [],
        }
    total_files, code_files = _count_code_files(abspath)
    warnings: List[str] = []
    if code_files == 0:
        return {
            "ok": False,
            "code": "no_code_files",
            "error": "No source code files found in this folder (.py, .js, .ts, .go, …).",
            "path": abspath,
            "name": os.path.basename(abspath) or abspath,
            "total_files": total_files,
            "code_files": code_files,
            "warnings": ["Choose a project root that contains source files."],
        }
    if total_files < 3:
        warnings.append("Very small folder — scan results may be limited.")
    return {
        "ok": True,
        "path": abspath,
        "name": os.path.basename(abspath) or abspath,
        "total_files": total_files,
        "code_files": code_files,
        "warnings": warnings,
        "broad_warnings": broad_folder_warnings(abspath, total_files=total_files),
    }


# Folders that almost never correspond to a single project root.
_BROAD_DESKTOP_LIKE = {"desktop", "downloads", "documents", "onedrive"}
# Large-file threshold above which a single scan is likely to be slow/noisy.
_BROAD_FILE_COUNT = 20000


def broad_folder_warnings(
    path: str,
    *,
    total_files: Optional[int] = None,
    child_names: Optional[List[str]] = None,
    nested_git_count: Optional[int] = None,
) -> List[str]:
    """Plain-language warnings when a chosen folder looks too broad to scan.

    Pure and dependency-free so it is easy to test. The filesystem is only
    consulted when ``child_names`` / ``nested_git_count`` are not supplied.
    """
    warnings: List[str] = []
    raw = (path or "").strip()
    if not raw:
        return warnings
    abspath = os.path.abspath(os.path.expanduser(raw))
    norm = abspath.replace("\\", "/").rstrip("/")
    base = os.path.basename(norm).lower()

    # Drive root (C:\, D:\) or filesystem root (/).
    drive, tail = os.path.splitdrive(abspath)
    is_drive_root = abspath in ("/", os.sep) or (bool(drive) and tail in ("", "/", "\\", os.sep))
    if is_drive_root:
        warnings.append(
            "This is a drive root. Scanning an entire drive is very slow — choose your project folder instead."
        )

    if base in _BROAD_DESKTOP_LIKE:
        warnings.append(
            f"This looks like your {base.capitalize()} folder, which usually mixes many unrelated files. "
            "Pick a single project folder."
        )

    if "external_repos" in [seg.lower() for seg in norm.split("/")]:
        warnings.append(
            "external_repos holds many unrelated projects. Scan one project at a time for clean results."
        )

    if child_names is None:
        try:
            child_names = os.listdir(abspath)
        except OSError:
            child_names = []
    lower_children = {str(c).lower() for c in (child_names or [])}

    if "node_modules" in lower_children:
        warnings.append(
            "This folder contains node_modules. Atlas skips it, but confirm you selected your project root "
            "and not an install tree."
        )

    if nested_git_count is None:
        nested_git_count = _count_nested_git_projects(abspath, child_names)
    if (nested_git_count or 0) >= 2:
        warnings.append(
            "This folder contains several sub-projects with their own .git history. "
            "Scan one project at a time instead of the whole workspace."
        )

    if total_files is not None and total_files >= _BROAD_FILE_COUNT:
        warnings.append(
            f"Very large file count (~{total_files:,} files). Scanning may be slow — "
            "consider a subfolder or a narrower scan scope."
        )

    return warnings


def _count_nested_git_projects(abspath: str, child_names: Optional[List[str]]) -> int:
    """Count immediate sub-folders that look like their own git repository."""
    count = 0
    for name in child_names or []:
        sub = os.path.join(abspath, str(name))
        try:
            if os.path.isdir(sub) and os.path.isdir(os.path.join(sub, ".git")):
                count += 1
        except OSError:
            continue
    return count


def pre_scan_estimate(path: str, scope: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    validation = validate_repository_path(path)
    if not validation.get("ok"):
        return validation
    root = validation["path"]
    scope_data = _scope_from_input(scope)
    total_files = 0
    code_files = 0
    bytes_total = 0
    languages: Dict[str, int] = {}
    ignored_dirs = sorted(_SKIP_DIRS)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS)
        for name in filenames:
            total_files += 1
            abs_path = os.path.join(dirpath, name)
            rel = os.path.relpath(abs_path, root).replace("\\", "/")
            ext = os.path.splitext(name)[1].lower()
            try:
                size = os.path.getsize(abs_path)
            except OSError:
                size = 0
            bytes_total += size
            if _is_binary_ext(ext) or not _scope_allows(rel, ext, scope_data):
                continue
            if ext in _CODE_EXTENSIONS:
                code_files += 1
                languages[ext or "(none)"] = languages.get(ext or "(none)", 0) + 1
    likely_seconds = max(2, int(code_files / 120) + int(total_files / 4000))
    suggested_scopes = ["entire_repo", "backend", "frontend", "python_only"]
    if total_files > MASSIVE_FILES_THRESHOLD or bytes_total > MASSIVE_SIZE_THRESHOLD_BYTES:
        suggested_scopes = ["backend", "frontend", "python_only", "folder", "custom"]
    estimated_modules = max(1, int(code_files * 0.65))
    massive_auto = (
        total_files > MASSIVE_FILES_THRESHOLD
        or estimated_modules > MASSIVE_MODULES_THRESHOLD
        or bytes_total > MASSIVE_SIZE_THRESHOLD_BYTES
    )
    return {
        "ok": True,
        "path": root,
        "scope": scope_data,
        "total_files": total_files,
        "code_files": code_files,
        "estimated_modules": estimated_modules,
        "repo_size_bytes": bytes_total,
        "repo_size_mb": round(bytes_total / (1024 * 1024), 2),
        "languages": dict(sorted(languages.items(), key=lambda item: (-item[1], item[0]))[:12]),
        "ignored_folders": ignored_dirs,
        "likely_scan_time_seconds": likely_seconds,
        "suggested_scopes": suggested_scopes,
        "massive_mode_auto": massive_auto,
    }


def _scan_next_actions(scan: Dict[str, Any]) -> List[str]:
    actions = [
        "Explore the dependency graph in Command Center",
        "Ask Copilot: What does this repository do?",
        "Ask Copilot: What are the top architectural risks?",
    ]
    if scan.get("top_hubs"):
        hub = scan["top_hubs"][0].get("path") or scan["top_hubs"][0].get("module")
        if hub:
            actions.append(f"Ask Copilot: What breaks if I change {hub}?")
    if scan.get("import_cycle_count"):
        actions.append("Ask Copilot: Show import cycles")
    actions.append("Export a compact Claude/Codex/Cursor context packet")
    return actions


def select_repository(path: str) -> Dict[str, Any]:
    validation = validate_repository_path(path)
    if not validation.get("ok"):
        return {
            "ok": False,
            "error": validation.get("error", "Invalid path"),
            "code": validation.get("code", "invalid"),
            "warnings": validation.get("warnings", []),
        }
    abspath = validation["path"]
    _STATE["path"] = abspath
    _STATE["demo_mode"] = False
    return {
        "ok": True,
        "path": abspath,
        "name": validation["name"],
        "code_files": validation.get("code_files", 0),
        "warnings": validation.get("warnings", []),
    }


def _is_demo_path(path: str) -> bool:
    abspath = os.path.abspath(path)
    for meta in _DEMO_PACKS.values():
        if abspath == os.path.abspath(meta["path"]):
            return True
        fallback = meta.get("fallback")
        if fallback and abspath == os.path.abspath(fallback):
            return True
    return False


def load_demo_mode(pack: str = "small") -> Dict[str, Any]:
    """Load bundled demo repository into product state (clearly labeled demo)."""
    pack_id = (pack or "small").strip().lower()
    meta = _DEMO_PACKS.get(pack_id)
    if not meta:
        return {"ok": False, "error": f"Unknown demo pack: {pack_id}", "code": "demo_unknown_pack"}
    demo_path = demo_repo_path(pack_id)
    if not os.path.isdir(demo_path):
        return {
            "ok": False,
            "error": f"Bundled demo repository is missing: {pack_id}",
            "code": "demo_missing",
            "pack": pack_id,
        }
    _STATE["demo_mode"] = False
    result = scan_repository(demo_path)
    if not result.get("ok"):
        return result
    label = meta["label"]
    _STATE["demo_mode"] = True
    result["demo_mode"] = True
    result["demo_pack"] = pack_id
    result["repo_name"] = f"Atlas Demo — {label}"
    result["repo_path"] = demo_path
    _STATE["scan"]["demo_mode"] = True
    _STATE["scan"]["demo_pack"] = pack_id
    _STATE["scan"]["repo_name"] = result["repo_name"]
    _STATE["scan"]["repo_path"] = demo_path
    track_analytics_event("demo_loaded", pack=pack_id, modules=result.get("module_count", 0))
    return _attach_analytics_status(result)


def _build_evidence_store_for_scan(repo: str) -> Dict[str, Any]:
    """AST symbol index + call graph for evidence-backed planning (Phase 129)."""
    graph = _STATE.get("graph")
    index = _STATE.get("index")
    if not graph and not index:
        return {}
    try:
        store = build_evidence_store(repo, graph, index)
        return store.to_dict()
    except Exception:
        return {}


def scan_repository(path: Optional[str] = None, scope: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run the real Builder Core scan (graph + light index + risk ranking)."""
    repo = os.path.abspath(path or _STATE.get("path") or ".")
    scope_data = _scope_from_input(scope)
    t_validate_start = time.time()
    validation = validate_repository_path(repo)
    t_validate_end = time.time()
    if not validation.get("ok"):
        return {
            "ok": False,
            "error": validation.get("error", "Invalid repository path"),
            "code": validation.get("code", "invalid"),
            "warnings": validation.get("warnings", []),
        }
    repo = validation["path"]
    _STATE["demo_mode"] = _is_demo_path(repo)
    _STATE["last_scope"] = scope_data
    t_estimate_start = time.time()
    estimate = pre_scan_estimate(repo, scope_data)
    t_estimate_end = time.time()
    scan_job = _STATE.get("scan_job") or {"id": None, "cancelled": False, "stage": "idle"}
    previous_stage = scan_job.get("stage", "idle")
    if previous_stage in {"idle", "completed"}:
        scan_job["cancelled"] = False
    scan_job.update({"id": f"scan-{int(time.time()*1000)}", "stage": "discovering_files"})
    _STATE["scan_job"] = scan_job

    signature = _scan_signature(repo, scope_data)
    cache = _STATE.setdefault("scan_cache", {})
    cached = cache.get(signature)
    recorder = _StageRecorder(repo_path=repo, scope=scope_data, cache_hit=bool(cached))
    recorder.mark(
        "pre_scan_estimate",
        t_estimate_start,
        t_estimate_end,
        files_seen=estimate.get("total_files", 0),
        code_files=estimate.get("code_files", 0),
        modules=estimate.get("estimated_modules", 0),
        edges=0,
        output_size_bytes=len(_json.dumps(estimate, default=str)),
    )
    recorder.mark(
        "validate_repository_path",
        t_validate_start,
        t_validate_end,
        files_seen=validation.get("total_files", 0),
        code_files=validation.get("code_files", 0),
        modules=0,
        edges=0,
        output_size_bytes=len(_json.dumps(validation, default=str)),
    )
    if cached:
        _STATE.update(
            {
                "path": repo,
                "scan": _json.loads(_json.dumps(cached["scan"])),
                "graph": cached["graph"],
                "index": cached["index"],
                "risks": cached["risks"],
                "evidence_store": cached.get("evidence_store") or {},
            }
        )
        _STATE["scan"]["cache"] = {"hit": True, "signature": signature}
        _STATE["scan_job"]["stage"] = "completed"
        recorder.mark(
            "cache_restore",
            time.time(),
            time.time(),
            files_seen=_STATE["scan"].get("file_count", 0),
            code_files=_STATE["scan"].get("file_count", 0),
            modules=_STATE["scan"].get("module_count", 0),
            edges=_STATE["scan"].get("dependency_edges", 0),
            output_size_bytes=len(_json.dumps(_STATE["scan"], default=str)),
        )
        _STATE["scan_perf"] = recorder.snapshot()
        track_analytics_event("scan_completed", demo=bool(_STATE.get("demo_mode")), cache_hit=True)
        _record_usage("scan_completed", cache_hit=True)
        return _attach_analytics_status(_STATE["scan"])
    started = time.time()
    usage_tracking.record_event(
        "scan_started",
        repo_path=repo,
        repo_name=os.path.basename(repo) or repo,
    )

    if _STATE["scan_job"].get("cancelled"):
        return {"ok": False, "error": "Scan cancelled.", "code": "scan_cancelled"}
    _STATE["scan_job"]["stage"] = "building_graph"
    massive_mode_pre = bool(scope_data.get("manual_massive_mode")) or bool(estimate.get("massive_mode_auto"))

    def _on_graph_progress(phase: str, current: int, total: int) -> None:
        job = _STATE.get("scan_job") or {}
        job["graph_phase"] = phase
        job["graph_progress"] = {"current": current, "total": max(total, 1)}
        _STATE["scan_job"] = job

    t_graph_start = time.time()
    graph = graph_build.build_scan_graph(
        repo,
        massive_mode=massive_mode_pre,
        code_files=int(estimate.get("code_files", 0)),
        estimated_modules=int(estimate.get("estimated_modules", 0)),
        on_progress=_on_graph_progress,
    )
    t_graph_end = time.time()
    build_meta = graph.get("jarvis_graph_build") or {}
    _STATE["graph_detail_level"] = graph.get("graph_detail") or build_meta.get("detail")
    _STATE["full_graph_pending"] = bool(build_meta.get("lazy_full"))
    graph_nodes = [n for n in graph.get("nodes", []) if n.get("type") == "module"]
    graph_edges = [e for e in graph.get("edges", []) if e.get("type") == "imports" and e.get("resolved")]
    # Phase 140 — safe transient retry. A massive-mode build that yields 0 modules
    # from a large file set is a known cold-cache flake (observed on VS Code). One
    # rebuild is side-effect-free (re-reads the same files) and recovers it.
    _STATE.pop("scan_retry", None)
    if not graph_nodes and int(estimate.get("code_files", 0)) > 500 and not _STATE["scan_job"].get("cancelled"):
        graph = graph_build.build_scan_graph(
            repo,
            massive_mode=massive_mode_pre,
            code_files=int(estimate.get("code_files", 0)),
            estimated_modules=int(estimate.get("estimated_modules", 0)),
            on_progress=_on_graph_progress,
        )
        t_graph_end = time.time()
        build_meta = graph.get("jarvis_graph_build") or {}
        _STATE["graph_detail_level"] = graph.get("graph_detail") or build_meta.get("detail")
        _STATE["full_graph_pending"] = bool(build_meta.get("lazy_full"))
        graph_nodes = [n for n in graph.get("nodes", []) if n.get("type") == "module"]
        graph_edges = [e for e in graph.get("edges", []) if e.get("type") == "imports" and e.get("resolved")]
        _STATE["scan_retry"] = {"reason": "zero_module_scan", "recovered": bool(graph_nodes)}
    recorder.mark(
        "building_dependency_graph",
        t_graph_start,
        t_graph_end,
        files_seen=estimate.get("total_files", 0),
        code_files=estimate.get("code_files", 0),
        modules=len(graph_nodes),
        edges=len(graph_edges),
        output_size_bytes=len(_json.dumps(graph, default=str)),
        graph_detail=graph.get("graph_detail"),
        graph_tier=build_meta.get("tier"),
        graph_timed_out=bool(graph.get("jarvis_timed_out")),
        graph_partial=bool(graph.get("jarvis_partial")),
    )
    if _STATE["scan_job"].get("cancelled"):
        return {"ok": False, "error": "Scan cancelled.", "code": "scan_cancelled"}
    _STATE["scan_job"]["stage"] = "indexing_modules"
    t_index_start = time.time()
    index = _light_index(repo, scope_data)
    t_index_end = time.time()
    recorder.mark(
        "indexing_repository",
        t_index_start,
        t_index_end,
        files_seen=len(index.get("files", [])),
        code_files=len(index.get("files", [])),
        modules=len(graph_nodes),
        edges=len(graph_edges),
        output_size_bytes=len(_json.dumps(index.get("stats", {}), default=str)),
    )
    module_nodes = [n for n in graph.get("nodes", []) if n.get("type") == "module"]
    module_count = len(module_nodes)
    _STATE["scan_job"]["stage"] = "extracting_architecture"
    _STATE["scan_job"]["stage"] = "ranking_risks"
    try:
        t_risk_start = time.time()
        risks = architectural_risk.rank_modules(
            index,
            graph,
            top=min(RISK_RANK_TOP, max(module_count, 12)),
        )
        risks = _annotate_multilang_risk_signals(risks)
        t_risk_end = time.time()
        recorder.mark(
            "detecting_architectural_risks",
            t_risk_start,
            t_risk_end,
            files_seen=len(index.get("files", [])),
            code_files=len(index.get("files", [])),
            modules=module_count,
            edges=len(graph_edges),
            output_size_bytes=len(_json.dumps(risks, default=str)),
        )
    except Exception as exc:  # never crash the product on a risk-engine edge case
        risks = {"ranked_modules": [], "error": f"{type(exc).__name__}: {exc}"}
        recorder.mark(
            "detecting_architectural_risks",
            time.time(),
            time.time(),
            files_seen=len(index.get("files", [])),
            code_files=len(index.get("files", [])),
            modules=module_count,
            edges=len(graph_edges),
            output_size_bytes=len(_json.dumps(risks, default=str)),
            error=str(exc),
        )

    stats = graph.get("statistics", {})
    diag = graph.get("scope_diagnostics", {})
    import_edges = [e for e in graph.get("edges", []) if e.get("type") == "imports" and e.get("resolved")]
    unresolved = stats.get("unresolved_counts", {})

    top_hubs = risks.get("top_hubs") or [
        {"module": h.get("dotted") or h.get("path"), "fan_in": h.get("count", 0), "path": h.get("path")}
        for h in stats.get("top_imported_modules", [])[:8]
    ]
    top_risks = risks.get("top_risks") or [
        {
            "module": r.get("label"),
            "path": r.get("path"),
            "score": r.get("risk_score", r.get("total_score")),
            "reasons": r.get("risk_reasons", r.get("signals", []))[:4],
            "risk_components": r.get("risk_components", {}),
            "subsystem": r.get("subsystem"),
        }
        for r in (risks.get("ranked_modules") or [])[:6]
    ]

    duration = round(time.time() - started, 2)
    top_risk = top_risks[0] if top_risks else {}
    language_breakdown = graph.get("language_breakdown") or graph_build._language_breakdown(graph)
    scan = {
        "ok": True,
        "repo_path": repo,
        "repo_name": os.path.basename(repo) or repo,
        "demo_mode": bool(_STATE.get("demo_mode")),
        "file_count": len(index["files"]),
        "files_discovered": diag.get("total_candidate_files", len(module_nodes)),
        "module_count": len(module_nodes),
        "subsystem_count": len(index["subsystems"]),
        "dependency_edges": len(import_edges),
        "resolved_imports": language_breakdown.get("resolved_imports", len(import_edges)),
        "unresolved_imports": unresolved.get("imports_external", 0),
        "external_package_imports": language_breakdown.get("external_package_imports", 0),
        "unresolved_ratio": language_breakdown.get("unresolved_ratio", 0.0),
        "unresolved_calls": unresolved.get("calls_unresolved", 0),
        "graph_scope": graph.get("graph_scope"),
        "graph_detail": graph.get("graph_detail") or build_meta.get("detail"),
        "graph_build": build_meta,
        "full_graph_pending": bool(build_meta.get("lazy_full")),
        "language_breakdown": language_breakdown,
        "degraded": bool(graph.get("degraded")),
        "import_cycle_count": stats.get("import_cycles") and len(stats["import_cycles"]) or 0,
        "top_hubs": top_hubs,
        "top_risks": top_risks,
        "top_risk_module": top_risk.get("module") or top_risk.get("path") or "",
        "top_risk_score": top_risk.get("score", 0),
        "role_counts": index["stats"]["roles"],
        "scan_duration_seconds": duration,
        "scanned_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "validation_warnings": validation.get("warnings", []),
        "suggested_next_actions": [],
        "scope": scope_data,
        "cache": {"hit": False, "signature": signature},
    }
    # Phase 140 — reliability assessment + immediate degraded-scan warnings.
    _assessment = reliability.classify_scan(scan)
    if _STATE.get("scan_retry"):
        _assessment["retried"] = True
        _assessment["retry_recovered"] = bool(_STATE["scan_retry"].get("recovered"))
    scan["reliability"] = _assessment
    scan["health_warnings"] = _assessment.get("warnings", [])
    scan["suggested_next_actions"] = _scan_next_actions(scan)
    recorder.mark(
        "extracting_architecture",
        time.time(),
        time.time(),
        files_seen=len(index.get("files", [])),
        code_files=len(index.get("files", [])),
        modules=module_count,
        edges=len(import_edges),
        output_size_bytes=len(_json.dumps({"top_hubs": top_hubs, "top_risks": top_risks}, default=str)),
    )
    recorder.mark(
        "extracting_contracts",
        time.time(),
        time.time(),
        files_seen=len(index.get("files", [])),
        code_files=len(index.get("files", [])),
        modules=module_count,
        edges=len(import_edges),
        output_size_bytes=0,
        note="desktop stage marker (no dedicated backend contract extraction step)",
    )
    recorder.mark(
        "generating_verification_evidence",
        time.time(),
        time.time(),
        files_seen=len(index.get("files", [])),
        code_files=len(index.get("files", [])),
        modules=module_count,
        edges=len(import_edges),
        output_size_bytes=0,
        note="building AST symbol index and call graph for evidence engine",
    )
    _STATE.update({"path": repo, "scan": scan, "graph": graph, "index": index, "risks": risks})
    _merge_phase134_scan_fields(scan, graph, index, risks)
    t_evidence_start = time.time()
    evidence_store = _build_evidence_store_for_scan(repo)
    _STATE["evidence_store"] = evidence_store
    t_evidence_end = time.time()
    recorder.mark(
        "building_evidence_index",
        t_evidence_start,
        t_evidence_end,
        files_seen=len(index.get("files", [])),
        code_files=len(index.get("files", [])),
        modules=module_count,
        edges=len(import_edges),
        output_size_bytes=len(_json.dumps(evidence_store, default=str)) if evidence_store else 0,
        symbol_count=(evidence_store.get("symbol_index") or {}).get("symbol_count", 0),
    )
    _STATE["scan_job"]["stage"] = "generating_summary"
    t_packet_all_start = time.time()
    packet_stats: List[Dict[str, Any]] = []
    for target, packet in (("claude", "compact"), ("claude", "verbose"), ("codex", "compact"), ("cursor", "compact")):
        t_packet_start = time.time()
        text = _render_context(target, packet)
        tokens = estimate_tokens(text)
        t_packet_end = time.time()
        packet_stats.append(
            {
                "target": target,
                "packet": packet,
                "duration_ms": int(round((t_packet_end - t_packet_start) * 1000)),
                "estimated_tokens": tokens,
                "text_size_bytes": len(text.encode("utf-8", errors="ignore")),
            }
        )
        if target == "claude" and packet == "compact":
            scan["compact_token_estimate"] = tokens
        if target == "claude" and packet == "verbose":
            scan["verbose_token_estimate"] = tokens
    t_packet_all_end = time.time()
    slowest_packet = max(packet_stats, key=lambda item: item["duration_ms"]) if packet_stats else None
    recorder.mark(
        "building_ai_context_packets",
        t_packet_all_start,
        t_packet_all_end,
        files_seen=len(index.get("files", [])),
        code_files=len(index.get("files", [])),
        modules=module_count,
        edges=len(import_edges),
        output_size_bytes=sum(item["text_size_bytes"] for item in packet_stats),
        packet_count=len(packet_stats),
        packet_stats=packet_stats,
        slowest_packet=slowest_packet,
        serial_generation=True,
    )
    _STATE["scan"]["compact_token_estimate"] = scan["compact_token_estimate"]
    massive_mode = bool(scope_data.get("manual_massive_mode")) or bool(estimate.get("massive_mode_auto"))
    _STATE["scan"]["massive_mode"] = massive_mode
    _STATE["scan"]["massive_reason"] = {
        "files": estimate.get("total_files", 0) > MASSIVE_FILES_THRESHOLD,
        "modules": scan["module_count"] > MASSIVE_MODULES_THRESHOLD,
        "size": estimate.get("repo_size_bytes", 0) > MASSIVE_SIZE_THRESHOLD_BYTES,
        "manual": bool(scope_data.get("manual_massive_mode")),
    }
    _STATE["scan"]["estimate"] = estimate
    t_summary_start = time.time()
    summary_snapshot = current_summary()
    t_summary_end = time.time()
    recorder.mark(
        "final_summary_serialization",
        t_summary_start,
        t_summary_end,
        files_seen=scan.get("file_count", 0),
        code_files=scan.get("file_count", 0),
        modules=scan.get("module_count", 0),
        edges=scan.get("dependency_edges", 0),
        output_size_bytes=len(_json.dumps(summary_snapshot, default=str)),
    )
    t_graph_payload_start = time.time()
    graph_snapshot = current_graph("subsystem")
    t_graph_payload_end = time.time()
    recorder.mark(
        "graph_payload_preparation",
        t_graph_payload_start,
        t_graph_payload_end,
        files_seen=scan.get("file_count", 0),
        code_files=scan.get("file_count", 0),
        modules=graph_snapshot.get("total_modules", 0),
        edges=graph_snapshot.get("total_edges", 0),
        output_size_bytes=len(_json.dumps(graph_snapshot, default=str)),
    )
    cache[signature] = {
        "scan": _STATE["scan"],
        "graph": graph,
        "index": index,
        "risks": risks,
        "evidence_store": _STATE.get("evidence_store") or {},
        "cached_at": time.time(),
    }
    _STATE["scan_job"]["stage"] = "completed"
    _STATE["scan_perf"] = recorder.snapshot()
    track_analytics_event(
        "scan_completed",
        demo=bool(_STATE.get("demo_mode")),
        modules=scan["module_count"],
        edges=scan["dependency_edges"],
        cache_hit=False,
        massive_mode=massive_mode,
    )
    _record_usage("scan_completed", cache_hit=False, massive_mode=massive_mode)
    return _attach_analytics_status(scan)


def _merge_phase134_scan_fields(
    scan: Dict[str, Any],
    graph: Dict[str, Any],
    index: Dict[str, Any],
    risks: Dict[str, Any],
) -> None:
    """Populate Repository Map fields from architecture + risk engines."""
    try:
        from . import architecture as _arch

        arch = _arch.analyze(graph, index=index, risks=risks)
    except Exception:
        arch = {"ok": False}
    _STATE["architecture"] = {**arch, "_sig": id(graph)}
    if arch.get("ok"):
        scan["top_hubs"] = arch.get("top_hubs", scan.get("top_hubs"))[:8]
        scan["top_risks"] = arch.get("top_risks", scan.get("top_risks"))[:8]
        scan["top_boundaries"] = arch.get("top_boundaries", [])[:8]
        scan["top_cycles"] = arch.get("top_cycles", arch.get("cycles", []))[:8]
        scan["unresolved_breakdown"] = (arch.get("unresolved") or {}).get("buckets", {})
        scan["graph_health_reason"] = arch.get("graph_health_reason", "")
        scan["architecture_summary"] = arch.get("architecture_summary", {})
        top_risk = scan["top_risks"][0] if scan.get("top_risks") else {}
        scan["top_risk_module"] = top_risk.get("module") or top_risk.get("path") or ""
        scan["top_risk_score"] = top_risk.get("score", 0)
    if risks.get("ranked_modules"):
        scan["risk_components_sample"] = (risks["ranked_modules"][0].get("risk_components") or {})


def _architecture_analysis() -> Dict[str, Any]:
    """Compute (and cache on _STATE) the architectural intelligence analysis."""
    cached = _STATE.get("architecture")
    if cached and cached.get("_sig") == id(_STATE.get("graph")):
        return cached
    graph = _STATE.get("graph")
    if not graph:
        return {"ok": False}
    try:
        from . import architecture as _arch

        result = _arch.analyze(graph, index=_STATE.get("index"), risks=_STATE.get("risks"))
    except Exception as exc:  # never break the summary on an analysis edge case
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    result["_sig"] = id(graph)
    _STATE["architecture"] = result
    return result


def current_summary() -> Dict[str, Any]:
    scan = _STATE.get("scan")
    if not scan:
        return {"ok": False, "error": "No repository scanned yet."}
    index = _STATE["index"]
    subsystems = sorted(
        index["subsystems"],
        key=lambda s: (-s.get("role_counts", {}).get("production_code", 0), s.get("name", "")),
    )
    prod = [s for s in subsystems if s.get("role_counts", {}).get("production_code", 0) > 0]
    entry_points: List[str] = []
    for s in prod[:8]:
        for ef in s.get("entry_files", [])[:2]:
            if ef not in entry_points:
                entry_points.append(ef)
    arch = _architecture_analysis()
    arch_ok = bool(arch.get("ok"))
    # Phase 134 — Top Hubs (depended-on) vs Top Risks (dangerous-to-change) come
    # from the architecture analyzer and are separated by construction.
    top_hubs = arch["top_hubs"][:8] if arch_ok else scan["top_hubs"]
    top_risks = arch["top_risks"][:8] if arch_ok else scan["top_risks"]
    return {
        "ok": True,
        "repo_name": scan["repo_name"],
        "repo_path": scan["repo_path"],
        "demo_mode": bool(scan.get("demo_mode")),
        "file_count": scan["file_count"],
        "module_count": scan["module_count"],
        "subsystem_count": scan["subsystem_count"],
        "dependency_edges": scan["dependency_edges"],
        "graph_scope": scan["graph_scope"],
        "degraded": scan["degraded"],
        "risk_score": _repo_risk_score(),
        "graph_health": _graph_health(scan, arch if arch_ok else None),
        "architecture": _architecture_summary(arch) if arch_ok else {"ok": False},
        **analytics.status_snapshot(),
        "token_savings": _token_savings(scan),
        "subsystems": [
            {
                "name": s["name"],
                "production_files": s.get("role_counts", {}).get("production_code", 0),
                "entry_files": s.get("entry_files", [])[:3],
                "dependencies": s.get("dependencies", []),
            }
            for s in prod[:14]
        ],
        "entry_points": entry_points,
        "top_hubs": top_hubs,
        "top_risks": top_risks,
        "top_boundaries": (scan.get("top_boundaries") or arch.get("top_boundaries", []))[:8] if arch_ok else [],
        "top_cycles": (scan.get("top_cycles") or arch.get("top_cycles", []))[:8] if arch_ok else [],
        "unresolved_breakdown": scan.get("unresolved_breakdown") or (
            (arch.get("unresolved") or {}).get("buckets", {}) if arch_ok else {}
        ),
        "graph_health_reason": scan.get("graph_health_reason") or arch.get("graph_health_reason", ""),
        "architecture_summary": scan.get("architecture_summary") or arch.get("architecture_summary", {}),
        "explanation": _plain_english(scan, prod, entry_points),
        "recommended_questions": _recommended_questions(scan),
        "massive_mode": bool(scan.get("massive_mode")),
        "massive_reason": scan.get("massive_reason", {}),
        "scope": scan.get("scope", {"mode": "entire_repo"}),
        "cache": scan.get("cache", {"hit": False}),
        "language_breakdown": scan.get("language_breakdown", {}),
        "scan_duration_seconds": scan.get("scan_duration_seconds"),
        "evidence_coverage": _evidence_coverage(),
    }


def startup_status() -> Dict[str, Any]:
    """Phase 143 — environment checks for launcher / support UI."""
    from .install_support import environment_status

    return environment_status()


def installer_self_test() -> Dict[str, Any]:
    """Phase 157 — verify the install (binary, assets, shortcuts, browser)."""
    from .install_support import installer_self_test as _self_test

    return _self_test()


def clear_scan_cache() -> Dict[str, Any]:
    from .install_support import clear_scan_cache as _clear

    return _clear()


def rebuild_repository_index(*, rescan: bool = True) -> Dict[str, Any]:
    from .install_support import rebuild_index

    return rebuild_index(rescan=rescan)


def export_support_bundle() -> Dict[str, Any]:
    """Phase 143 — zip diagnostics + scan metadata + logs (no source code)."""
    from .install_support import export_support_bundle as _export

    return _export()


def beta_diagnostics() -> Dict[str, Any]:
    """Phase 141 — support bundle: version, scan stats, repository size."""
    scan = _STATE.get("scan") or {}
    summary = current_summary()
    gh = (summary.get("graph_health") or {}) if summary.get("ok") else {}
    perf = _STATE.get("scan_perf") or {}
    return {
        "ok": True,
        "product": "ATLAS",
        "version": PRODUCT_VERSION,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "repository": {
            "name": scan.get("repo_name"),
            "path": _STATE.get("path"),
            "demo_mode": bool(_STATE.get("demo_mode")),
            "demo_pack": scan.get("demo_pack"),
            "size_mb": scan.get("repo_size_mb"),
            "massive_mode": bool(scan.get("massive_mode")),
        },
        "scan_statistics": {
            "file_count": int(scan.get("file_count") or 0),
            "module_count": int(scan.get("module_count") or 0),
            "dependency_edges": int(scan.get("dependency_edges") or 0),
            "subsystem_count": int(scan.get("subsystem_count") or 0),
            "scan_duration_seconds": scan.get("scan_duration_seconds"),
            "graph_quality": gh.get("label"),
            "unresolved_internal": gh.get("unresolved_internal") or gh.get("unresolved_imports"),
            "import_cycles": gh.get("import_cycles"),
            "cache_hit": bool((scan.get("cache") or {}).get("hit")),
        },
        "evidence_coverage": summary.get("evidence_coverage") or _evidence_coverage(),
        "scan_performance_ms": perf.get("total_duration_ms"),
        "workflow_performance": dict(_STATE.get("workflow_perf") or {}),
        "scope": scan.get("scope") or _STATE.get("last_scope"),
        "reliability": scan.get("reliability") or {},
        "data_dir": _desktop_data_dir_for_diagnostics(),
    }


def _desktop_data_dir_for_diagnostics() -> Dict[str, Any]:
    try:
        from .install_support import data_dir, data_dir_diagnostics

        return {"path": data_dir(), **data_dir_diagnostics()}
    except Exception:
        return {"path": "", "fallback": None, "override_env": False}


def beta_system_health() -> Dict[str, Any]:
    """Phase 139 — consolidated system health for the beta dashboard."""
    summary = current_summary()
    if not summary.get("ok"):
        return {"ok": False, "error": summary.get("error") or "No repository scanned yet."}
    gh = summary.get("graph_health") or {}
    ev = summary.get("evidence_coverage") or {}
    perf = _STATE.get("scan_perf") or {}
    return {
        "ok": True,
        "repo_name": summary.get("repo_name"),
        "demo_mode": summary.get("demo_mode"),
        "indexed_files": summary.get("file_count"),
        "modules": summary.get("module_count"),
        "edges": summary.get("dependency_edges"),
        "unresolved_imports": gh.get("unresolved_internal") or gh.get("unresolved_imports") or 0,
        "scan_duration_seconds": summary.get("scan_duration_seconds"),
        "graph_quality": gh.get("label") or "unknown",
        "graph_health": gh,
        "evidence_coverage": ev,
        "scan_performance": perf,
        "workflow_performance": dict(_STATE.get("workflow_perf") or {}),
        "degraded": summary.get("degraded"),
        "reliability": (_STATE.get("scan") or {}).get("reliability") or {},
        "massive_mode": summary.get("massive_mode"),
    }


def scan_status() -> Dict[str, Any]:
    job = dict(_STATE.get("scan_job") or {"id": None, "cancelled": False, "stage": "idle"})
    perf = _STATE.get("scan_perf")
    stage = str(job.get("stage") or "idle")
    pct, label = _SCAN_STAGE_PROGRESS.get(stage, (0, stage.replace("_", " ").title()))
    if stage == "building_graph" and job.get("graph_progress"):
        gp = job["graph_progress"]
        total = max(int(gp.get("total") or 1), 1)
        current = int(gp.get("current") or 0)
        sub = min(1.0, current / total)
        pct = int(18 + sub * 30)
        phase = str(job.get("graph_phase") or "")
        if phase:
            label = f"Building dependency graph ({phase})"
    return {
        "ok": True,
        "job": job,
        "stage": stage,
        "stage_label": label,
        "progress_pct": pct,
        "perf_available": bool(perf),
        "scan_complete": stage == "completed",
        "graph_detail_level": _STATE.get("graph_detail_level"),
        "full_graph_pending": bool(_STATE.get("full_graph_pending")),
    }


def build_full_module_graph() -> Dict[str, Any]:
    """Lazy full module graph build (massive repos start with import-only graph)."""
    repo = _STATE.get("path")
    scan = _STATE.get("scan")
    if not repo or not scan:
        return {"ok": False, "error": "No repository scanned yet."}
    if not _STATE.get("full_graph_pending") and _STATE.get("graph_detail_level") == depgraph.DETAIL_FULL:
        return {"ok": True, "already_full": True, "graph_detail": depgraph.DETAIL_FULL}

    def _on_graph_progress(phase: str, current: int, total: int) -> None:
        job = _STATE.setdefault("scan_job", {"id": None, "cancelled": False, "stage": "idle"})
        job["stage"] = "building_graph"
        job["graph_phase"] = phase
        job["graph_progress"] = {"current": current, "total": max(total, 1)}

    started = time.time()
    graph = graph_build.build_full_module_graph(repo, on_progress=_on_graph_progress)
    elapsed = round(time.time() - started, 2)
    _STATE["graph"] = graph
    _STATE["graph_detail_level"] = graph.get("graph_detail", depgraph.DETAIL_FULL)
    _STATE["full_graph_pending"] = False
    if scan.get("ok"):
        module_nodes = [n for n in graph.get("nodes", []) if n.get("type") == "module"]
        import_edges = [e for e in graph.get("edges", []) if e.get("type") == "imports" and e.get("resolved")]
        scan["module_count"] = len(module_nodes)
        scan["dependency_edges"] = len(import_edges)
        scan["graph_scope"] = graph.get("graph_scope")
        scan["degraded"] = bool(graph.get("degraded"))
        scan["full_graph_pending"] = False
        scan["graph_detail"] = _STATE["graph_detail_level"]
        scan["graph_build_full_elapsed_sec"] = elapsed
    return {
        "ok": True,
        "graph_detail": _STATE["graph_detail_level"],
        "degraded": bool(graph.get("degraded")),
        "jarvis_timed_out": bool(graph.get("jarvis_timed_out")),
        "elapsed_sec": elapsed,
        "module_count": len([n for n in graph.get("nodes", []) if n.get("type") == "module"]),
    }


def cancel_scan() -> Dict[str, Any]:
    job = _STATE.setdefault("scan_job", {"id": None, "cancelled": False, "stage": "idle"})
    job["cancelled"] = True
    if job.get("stage") != "completed":
        job["stage"] = "cancel_requested"
    return {"ok": True, "cancelled": True, "job": job}


def current_scan_performance() -> Dict[str, Any]:
    perf = _STATE.get("scan_perf")
    if not perf:
        return {"ok": False, "error": "No scan performance data available yet."}
    return {"ok": True, "performance": perf}


def run_scan_diagnostic(
    repo_path: str,
    *,
    scope: Optional[Dict[str, Any]] = None,
    output_path: Optional[str] = None,
    timeout_sec: Optional[float] = None,
) -> Dict[str, Any]:
    """One-shot scan diagnostic that emits a performance JSON report."""
    import threading

    output_path = output_path or os.path.join("reports", "phase115a_django_scan_performance_metrics.json")
    holder: Dict[str, Any] = {"result": None, "error": None}

    def _run() -> None:
        try:
            holder["result"] = scan_repository(repo_path, scope)
        except Exception as exc:  # pragma: no cover - diagnostic guard
            holder["error"] = f"{type(exc).__name__}: {exc}"

    worker = threading.Thread(target=_run, name="scan-diagnostic", daemon=True)
    worker.start()
    if timeout_sec and timeout_sec > 0:
        worker.join(timeout=timeout_sec)
    else:
        worker.join()

    timed_out = worker.is_alive()
    result = holder["result"] if isinstance(holder.get("result"), dict) else {"ok": False, "error": holder.get("error") or "scan did not complete"}
    status = scan_status()
    payload = {
        "ok": bool(result.get("ok")),
        "timed_out": timed_out,
        "timeout_sec": timeout_sec,
        "repo_path": os.path.abspath(repo_path),
        "scan_result": result,
        "scan_status": status,
        "performance": _STATE.get("scan_perf"),
        "performance_live": _STATE.get("scan_perf_live"),
    }
    abs_output = output_path
    if not os.path.isabs(abs_output):
        abs_output = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", output_path))
    os.makedirs(os.path.dirname(abs_output), exist_ok=True)
    with open(abs_output, "w", encoding="utf-8") as fh:
        _json.dump(payload, fh, indent=2, ensure_ascii=False)
    return {"ok": True, "output_path": abs_output, "scan_ok": bool(result.get("ok")), "timed_out": timed_out}


def _subsystem_for_path(path: str, index: Dict[str, Any]) -> str:
    """Map a module path to a discovered subsystem name (never fabricated)."""
    if not path:
        return "(root)"
    normalized = path.replace("\\", "/")
    best = ""
    for sub in index.get("subsystems", []):
        name = str(sub.get("name", "")).replace("\\", "/")
        if not name:
            continue
        if normalized == name or normalized.startswith(name + "/"):
            if len(name) > len(best):
                best = name
        for entry in sub.get("entry_files", []):
            entry_norm = str(entry).replace("\\", "/")
            if normalized == entry_norm or normalized.startswith(entry_norm.rsplit("/", 1)[0] + "/"):
                if len(name) > len(best):
                    best = name
    if best:
        return best
    parts = normalized.split("/")
    if len(parts) >= 3 and parts[0] == "homeassistant" and parts[1] == "components":
        return "/".join(parts[:3])
    if len(parts) >= 2 and parts[0] == "homeassistant":
        return "/".join(parts[:2])
    return parts[0] if parts else "(root)"


def _risk_lookup(risks: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {str(r.get("path", "")): r for r in (risks or {}).get("ranked_modules", []) if r.get("path")}


def _risk_tier(
    *,
    score: float,
    rank: Optional[int],
    max_score: float,
    in_cycle: bool,
) -> str:
    if in_cycle:
        return "cycle"
    if rank and rank <= 5:
        return "top"
    if max_score > 0 and score >= max_score * 0.55:
        return "top"
    if score >= 25 or (max_score > 0 and score >= max_score * 0.3):
        return "elevated"
    return "normal"


def _module_visual_metrics(
    fan_in: int,
    fan_out: int,
    *,
    risk_score: float = 0.0,
    rank: Optional[int] = None,
) -> Dict[str, Any]:
    """Log-scaled module presence for 3D graph (Phase 121B)."""
    connectivity = math.log1p(max(0, fan_in) + max(0, fan_out) + 1)
    visual = 6.0 + connectivity * 2.85
    visual = max(MODULE_VISUAL_SIZE_MIN, min(MODULE_VISUAL_SIZE_MAX, visual))
    is_hub = fan_in >= MODULE_HUB_FAN_IN_MIN or (rank is not None and rank <= 12)
    hub_scale = 1.0
    if is_hub:
        hub_scale = min(3.4, 1.35 + connectivity * 0.38)
    return {
        "size": round(visual, 2),
        "visual_size": round(visual, 2),
        "hub_scale": round(hub_scale, 2),
        "is_hub": is_hub,
    }


def _architecture_pattern_matches(pattern: str, path_or_sub: str) -> bool:
    """Match cluster patterns on path segments, not naive substrings (avoids 'core' in unrelated names)."""
    low = str(path_or_sub or "").lower().replace("\\", "/")
    pat = pattern.lower()
    if pat.startswith("/"):
        return pat in low or low.endswith(pat.rstrip("/"))
    if "/" in pat:
        return pat in low
    segments = [s for s in low.split("/") if s]
    return any(seg == pat or seg.startswith(pat + "_") for seg in segments)


def _subsystem_view_use_architecture_clusters(
    scan: Dict[str, Any],
    index: Dict[str, Any],
    total_modules: int,
    *,
    mode: str,
    is_massive: bool,
    graph: Optional[Dict[str, Any]] = None,
) -> bool:
    """Mega-clusters for large repos unless the index has HA-style component subsystems."""
    if mode != "subsystem":
        return is_massive or total_modules >= GRAPH_DEFAULT_HIERARCHY_THRESHOLD
    subs = (index or {}).get("subsystems") or []
    component_subs = sum(
        1
        for s in subs
        if str(s.get("name", "")).replace("\\", "/").startswith("homeassistant/components/")
    )
    # Home Assistant: keep per-integration subsystems (hundreds of nodes), not 5 mega-buckets.
    if component_subs >= 15:
        return False
    unique_labels: Set[str] = set()
    for s in subs:
        name = str(s.get("name", "")).replace("\\", "/")
        if name:
            unique_labels.add(name)
    if graph:
        for node in graph.get("nodes", []):
            if node.get("type") == "module" and node.get("path"):
                unique_labels.add(_subsystem_for_path(node["path"], index))
    label_count = len(unique_labels)
    if is_massive or total_modules >= GRAPH_DEFAULT_HIERARCHY_THRESHOLD:
        return True
    if label_count > 35:
        return True
    return False


def _architecture_cluster_name(subsystem: str) -> str:
    low = str(subsystem or "(root)").lower().replace("\\", "/")
    for label, patterns in ARCHITECTURE_CLUSTER_PATTERNS:
        if any(_architecture_pattern_matches(pat, low) for pat in patterns):
            return label
    parts = [p for p in low.split("/") if p and p not in {"(root)", "root"}]
    if len(parts) >= 3:
        return parts[-1].replace("_", " ").title()
    if len(parts) >= 2:
        return parts[-1].replace("_", " ").title()
    segment = parts[0] if parts else ""
    if segment:
        return segment.replace("_", " ").title()
    return subsystem or "(root)"


def _graph_recommended_view(total_modules: int) -> str:
    if total_modules >= GRAPH_DEFAULT_HIERARCHY_THRESHOLD:
        return "hierarchy"
    return "module"


def _apply_galaxy_layout(nodes: List[Dict[str, Any]], links: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Galaxy layout: subsystem anchor hubs with modules orbiting; leaves on outer rings."""
    clusters: Dict[str, List[Dict[str, Any]]] = {}
    for node in nodes:
        sub = str(node.get("subsystem") or "(root)")
        clusters.setdefault(sub, []).append(node)

    cluster_names = sorted(clusters.keys(), key=lambda name: (-len(clusters[name]), name))
    cluster_meta: List[Dict[str, Any]] = []
    n_clusters = max(len(cluster_names), 1)
    orbit_radius = 120.0 + min(160.0, n_clusters * 8.5)

    for index, name in enumerate(cluster_names):
        members = sorted(
            clusters[name],
            key=lambda item: (-item.get("fan_in", 0), -item.get("risk_score", 0), item.get("label", "")),
        )
        angle = (2.0 * math.pi * index) / n_clusters
        cx = orbit_radius * math.cos(angle)
        cy = orbit_radius * math.sin(angle)
        cz = ((index % 3) - 1) * 32.0

        for node in members:
            node["is_hub"] = False

        hub = members[0]
        hub["is_hub"] = True
        hub["hub_scale"] = round(max(hub.get("hub_scale", 1.0), 2.4 + min(3.2, len(members) * 0.05)), 2)

        inner_radius = 14.0 + min(56.0, math.sqrt(len(members)) * 6.5)
        n_members = max(len(members), 1)
        for j, node in enumerate(members):
            if j == 0:
                ring_radius = 0.0
                ring_angle = 0.0
            else:
                ring = 1 + (j - 1) // max(1, n_members // 5)
                ring_radius = inner_radius * (1.0 + ring * 0.62)
                ring_angle = (2.0 * math.pi * (j - 1)) / max(n_members - 1, 1)
            depth = ((j % 5) - 2) * 6.5
            node["cluster_id"] = name
            node["galaxy_role"] = "hub" if j == 0 else ("leaf" if j >= n_members * 0.75 else "orbit")
            node["galaxy_x"] = round(cx + ring_radius * math.cos(ring_angle), 2)
            node["galaxy_y"] = round(cy + ring_radius * math.sin(ring_angle), 2)
            node["galaxy_z"] = round(cz + depth, 2)

        cluster_meta.append(
            {
                "id": name,
                "label": name,
                "module_count": len(members),
                "center_x": round(cx, 2),
                "center_y": round(cy, 2),
                "center_z": round(cz, 2),
                "hub_node_id": hub["id"],
            }
        )

    node_subsystem = {n["id"]: str(n.get("subsystem") or "(root)") for n in nodes}
    bridge_count = 0
    for link in links:
        src = link["source"] if isinstance(link["source"], str) else link["source"]
        tgt = link["target"] if isinstance(link["target"], str) else link["target"]
        src_sub = node_subsystem.get(str(src), "")
        tgt_sub = node_subsystem.get(str(tgt), "")
        if src_sub and tgt_sub and src_sub != tgt_sub:
            link["bridge"] = True
            bridge_count += 1
            link["opacity"] = round(min(0.92, max(float(link.get("opacity", 0.18)), 0.42)), 3)

    return {
        "layout": "galaxy",
        "cluster_count": len(cluster_meta),
        "bridge_link_count": bridge_count,
        "clusters": cluster_meta,
    }


def _subsystem_visual_size(module_count: int, risk_score: float = 0.0, *, top_risk: bool = False) -> Dict[str, float]:
    """Log-scaled, clamped sizes for subsystem hubs (readable, never giant blobs)."""
    base = 4.0
    log_part = math.log1p(max(0, int(module_count)))
    visual = base + log_part * 1.35
    visual = max(5.0, min(14.0, visual))
    hub_scale = max(1.15, min(2.5, 1.1 + log_part * 0.2))
    if top_risk:
        hub_scale = min(2.5, hub_scale + 0.12)
    return {
        "size": round(visual, 2),
        "visual_size": round(visual, 2),
        "hub_scale": round(hub_scale, 2),
    }


def _apply_subsystem_galaxy_layout(nodes: List[Dict[str, Any]], links: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Galaxy ring for collapsed subsystem view."""
    n_nodes = max(len(nodes), 1)
    radius = 90.0 + min(110.0, n_nodes * 6.5)
    for index, node in enumerate(sorted(nodes, key=lambda item: (-item.get("module_count", 0), item.get("label", "")))):
        angle = (2.0 * math.pi * index) / n_nodes
        node["is_hub"] = True
        vis = _subsystem_visual_size(
            int(node.get("module_count") or 0),
            float(node.get("risk_score") or 0),
            top_risk=str(node.get("risk_tier", "")) in {"critical", "high"},
        )
        node["size"] = vis["size"]
        node["visual_size"] = vis["visual_size"]
        node["hub_scale"] = vis["hub_scale"]
        node["cluster_id"] = node.get("subsystem") or node.get("label")
        node["galaxy_x"] = round(radius * math.cos(angle), 2)
        node["galaxy_y"] = round(radius * math.sin(angle), 2)
        node["galaxy_z"] = round(((index % 3) - 1) * 18.0, 2)

    bridge_count = sum(1 for link in links if link.get("edge_count", 0) > 0)
    for link in links:
        if int(link.get("edge_count") or 0) >= 3:
            link["bridge"] = True
            link["opacity"] = round(min(0.9, max(float(link.get("opacity", 0.2)), 0.5)), 3)

    return {
        "layout": "galaxy",
        "cluster_count": len(nodes),
        "bridge_link_count": bridge_count,
        "clusters": [
            {
                "id": node["id"],
                "label": node["label"],
                "module_count": node.get("module_count", 0),
                "center_x": node["galaxy_x"],
                "center_y": node["galaxy_y"],
                "center_z": node["galaxy_z"],
                "hub_node_id": node["id"],
            }
            for node in nodes
        ],
    }


def _build_tour_stops(
    nodes: List[Dict[str, Any]],
    links: List[Dict[str, Any]],
    scan: Dict[str, Any],
    index: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Deterministic camera tour stops derived from real scan/graph data."""
    if not nodes:
        return []

    by_subsystem: Dict[str, List[Dict[str, Any]]] = {}
    for node in nodes:
        by_subsystem.setdefault(str(node.get("subsystem") or "(root)"), []).append(node)

    largest_sub = max(by_subsystem.items(), key=lambda item: len(item[1]))[0]
    largest_nodes = by_subsystem[largest_sub]
    largest_hub = max(largest_nodes, key=lambda item: item.get("fan_in", 0))

    hubs = sorted(nodes, key=lambda item: (-item.get("fan_in", 0), -item.get("risk_score", 0)))[:5]
    cycle_nodes = [n for n in nodes if n.get("in_cycle")]
    top_risks = sorted(nodes, key=lambda item: (-item.get("risk_score", 0), -item.get("fan_in", 0)))[:5]

    entry_paths: List[str] = []
    for sub in index.get("subsystems", []):
        for ef in sub.get("entry_files", [])[:2]:
            if ef not in entry_paths:
                entry_paths.append(str(ef))
    entry_nodes: List[Dict[str, Any]] = []
    for path in entry_paths[:6]:
        match = next((n for n in nodes if n.get("path") == path), None)
        if match:
            entry_nodes.append(match)

    if not entry_nodes:
        entry_nodes = sorted(nodes, key=lambda item: -item.get("fan_out", 0))[:3]

    def _stop(step: str, title: str, narration: str, focus: List[Dict[str, Any]]) -> Dict[str, Any]:
        ids = [n["id"] for n in focus if n.get("id")]
        anchor = focus[0] if focus else nodes[0]
        return {
            "step": step,
            "title": title,
            "narration": narration,
            "focus_node_ids": ids[:12],
            "anchor_node_id": anchor.get("id"),
            "look_at": {
                "x": anchor.get("galaxy_x", 0),
                "y": anchor.get("galaxy_y", 0),
                "z": anchor.get("galaxy_z", 0),
            },
        }

    stops = [
        _stop(
            "largest_subsystem",
            f"Galaxy: {largest_sub}",
            f"The `{largest_sub}` subsystem contains {len(largest_nodes)} modules — the largest architectural cluster in this repository.",
            [largest_hub] + largest_nodes[:4],
        ),
        _stop(
            "critical_hubs",
            "Critical import hubs",
            "These modules have the highest fan-in. Many dependents route through them — changes here ripple widely.",
            hubs,
        ),
        _stop(
            "import_cycles",
            "Import cycles",
            "Circular imports increase coupling and test fragility. Purple halos mark cycle members.",
            cycle_nodes[:8] if cycle_nodes else hubs[:2],
        ),
        _stop(
            "highest_risks",
            "Highest architectural risk",
            "Risk scores combine fan-in, coupling signals, and structural evidence from Builder Core ranking.",
            top_risks,
        ),
        _stop(
            "entry_points",
            "Entry points",
            "Suggested runtime entry files and high fan-out modules where execution likely begins.",
            entry_nodes,
        ),
    ]
    return stops

def _module_graph_payload(
    graph: Dict[str, Any],
    index: Dict[str, Any],
    risks: Dict[str, Any],
) -> Dict[str, Any]:
    """Build module-level force-graph payload from real depgraph + risk ranking."""
    risk_by_path = _risk_lookup(risks)
    max_score = max((float(r.get("total_score", 0)) for r in risk_by_path.values()), default=0.0)

    fan_in: Dict[str, int] = {}
    fan_out: Dict[str, int] = {}
    for edge in graph.get("edges", []):
        if edge.get("type") != "imports" or not edge.get("resolved"):
            continue
        fan_in[edge["to"]] = fan_in.get(edge["to"], 0) + 1
        fan_out[edge["from"]] = fan_out.get(edge["from"], 0) + 1

    cycle_nodes: set[str] = set()
    for cycle in graph.get("statistics", {}).get("import_cycles", []):
        cycle_nodes.update(cycle)

    nodes: List[Dict[str, Any]] = []
    for node in graph.get("nodes", []):
        if node.get("type") != "module":
            continue
        nid = node["id"]
        path = node.get("path", "")
        risk = risk_by_path.get(path, {})
        score = float(risk.get("total_score", 0))
        rank = risk.get("rank")
        fi = fan_in.get(nid, 0)
        fo = fan_out.get(nid, 0)
        in_cycle = nid in cycle_nodes
        tier = _risk_tier(score=score, rank=rank, max_score=max_score, in_cycle=in_cycle)
        nodes.append(
            {
                "id": nid,
                "label": node.get("dotted") or path,
                "path": path,
                "subsystem": _subsystem_for_path(path, index),
                "fan_in": fi,
                "fan_out": fo,
                "importers_count": fi,
                "imported_modules_count": fo,
                "loc": int(node.get("line_count") or 0),
                "risk_score": round(score, 2),
                "risk_rank": rank,
                "risk_tier": tier,
                "in_cycle": in_cycle,
                **_module_visual_metrics(fi, fo, risk_score=score, rank=rank),
            }
        )

    node_ids = {n["id"] for n in nodes}
    links: List[Dict[str, Any]] = []
    for edge in graph.get("edges", []):
        if edge.get("type") != "imports" or not edge.get("resolved"):
            continue
        source, target = edge["from"], edge["to"]
        if source not in node_ids or target not in node_ids:
            continue
        target_fi = fan_in.get(target, 0)
        links.append(
            {
                "source": source,
                "target": target,
                "weight": round(1.0 + min(6.0, target_fi * 0.12), 2),
                "opacity": round(min(0.82, 0.1 + target_fi * 0.025), 3),
            }
        )

    total_modules = len(nodes)
    if total_modules > GRAPH_DISPLAY_CAP:
        nodes.sort(key=lambda item: (-item["risk_score"], -item["fan_in"], item["label"]))
        keep_ids = {n["id"] for n in nodes[:GRAPH_DISPLAY_CAP]}
        nodes = nodes[:GRAPH_DISPLAY_CAP]
        links = [link for link in links if link["source"] in keep_ids and link["target"] in keep_ids]

    layout = _apply_galaxy_layout(nodes, links)
    return {
        "view": "module",
        "node_count": len(nodes),
        "link_count": len(links),
        "total_modules": total_modules,
        "total_edges": len(
            [e for e in graph.get("edges", []) if e.get("type") == "imports" and e.get("resolved")]
        ),
        "nodes": nodes,
        "links": links,
        **layout,
    }


def _subsystem_graph_payload(
    graph: Dict[str, Any],
    index: Dict[str, Any],
    risks: Dict[str, Any],
    *,
    architecture_clusters: bool = False,
) -> Dict[str, Any]:
    """Collapse modules into subsystem hubs using real cross-subsystem import edges."""
    module_payload = _module_graph_payload(graph, index, risks)
    module_by_id = {n["id"]: n for n in module_payload["nodes"]}

    subsystem_nodes: Dict[str, Dict[str, Any]] = {}
    for node in module_payload["nodes"]:
        sub = node["subsystem"]
        group_key = _architecture_cluster_name(sub) if architecture_clusters else sub
        bucket = subsystem_nodes.setdefault(
            group_key,
            {
                "id": f"subsystem:{group_key}",
                "label": group_key,
                "path": group_key,
                "subsystem": group_key,
                "fan_in": 0,
                "fan_out": 0,
                "importers_count": 0,
                "imported_modules_count": 0,
                "loc": 0,
                "risk_score": 0.0,
                "risk_rank": None,
                "risk_tier": "normal",
                "in_cycle": False,
                "module_count": 0,
                "size": 4.0,
            },
        )
        bucket["module_count"] += 1
        bucket["loc"] += node["loc"]
        bucket["fan_in"] += node["fan_in"]
        bucket["fan_out"] += node["fan_out"]
        bucket["risk_score"] = max(bucket["risk_score"], node["risk_score"])
        bucket["in_cycle"] = bucket["in_cycle"] or node["in_cycle"]
        if architecture_clusters:
            subs = bucket.setdefault("member_subsystems", set())
            if isinstance(subs, set):
                subs.add(sub)

    max_score = max((n["risk_score"] for n in subsystem_nodes.values()), default=0.0)
    ranked_subs = sorted(subsystem_nodes.values(), key=lambda s: (-s["risk_score"], s["label"]))
    for rank, sub in enumerate(ranked_subs, 1):
        sub["risk_rank"] = rank
        sub["risk_tier"] = _risk_tier(
            score=sub["risk_score"],
            rank=rank,
            max_score=max_score,
            in_cycle=sub["in_cycle"],
        )
        vis = _subsystem_visual_size(
            int(sub["module_count"]),
            float(sub["risk_score"]),
            top_risk=rank <= 3,
        )
        sub["size"] = vis["size"]
        sub["visual_size"] = vis["visual_size"]
        sub["hub_scale"] = vis["hub_scale"]
        sub["graph_view"] = "subsystem"
        sub["importers_count"] = sub["fan_in"]
        sub["imported_modules_count"] = sub["fan_out"]
        if architecture_clusters and isinstance(sub.get("member_subsystems"), set):
            sub["member_subsystems"] = sorted(sub["member_subsystems"])
            sub["expandable"] = True
            sub["overview_hint"] = "Click to drill into packages and modules"

    edge_weights: Dict[tuple[str, str], int] = {}
    for edge in graph.get("edges", []):
        if edge.get("type") != "imports" or not edge.get("resolved"):
            continue
        src = module_by_id.get(edge["from"])
        dst = module_by_id.get(edge["to"])
        if not src or not dst:
            continue
        src_sub = _architecture_cluster_name(src["subsystem"]) if architecture_clusters else src["subsystem"]
        dst_sub = _architecture_cluster_name(dst["subsystem"]) if architecture_clusters else dst["subsystem"]
        if src_sub == dst_sub:
            continue
        key = (src_sub, dst_sub)
        edge_weights[key] = edge_weights.get(key, 0) + 1

    nodes = list(subsystem_nodes.values())
    links = [
        {
            "source": f"subsystem:{src}",
            "target": f"subsystem:{dst}",
            "weight": round(1.0 + min(8.0, count * 0.35), 2),
            "opacity": round(min(0.85, 0.14 + count * 0.04), 3),
            "edge_count": count,
        }
        for (src, dst), count in sorted(edge_weights.items(), key=lambda item: (-item[1], item[0]))
    ]
    for node in nodes:
        node.setdefault("graph_view", "subsystem")
    layout = _apply_subsystem_galaxy_layout(nodes, links)
    return {
        "view": "subsystem",
        "graph_view": "subsystem",
        "architecture_clusters": architecture_clusters,
        "node_count": len(nodes),
        "link_count": len(links),
        "total_modules": module_payload["total_modules"],
        "total_edges": module_payload["total_edges"],
        "nodes": nodes,
        "links": links,
        **layout,
    }


def current_graph(view: str = "module", force_module: bool = False) -> Dict[str, Any]:
    """Graph payload shaped for a 3D force graph (nodes + links)."""
    graph = _STATE.get("graph")
    if not graph:
        return {"ok": False, "error": "No repository scanned yet.", "nodes": [], "links": []}
    index = _STATE.get("index") or {}
    risks = _STATE.get("risks") or {}
    mode = (view or "module").strip().lower()
    scan = _STATE.get("scan") or {}
    is_massive = bool(scan.get("massive_mode"))
    total_modules = sum(1 for n in graph.get("nodes", []) if n.get("type") == "module")
    recommended = _graph_recommended_view(total_modules)
    cluster_overview = _subsystem_view_use_architecture_clusters(
        scan, index, total_modules, mode=mode, is_massive=is_massive, graph=graph
    )
    if mode == "subsystem":
        payload = _subsystem_graph_payload(
            graph, index, risks, architecture_clusters=cluster_overview
        )
    else:
        payload = _module_graph_payload(graph, index, risks)
    tour_stops = _build_tour_stops(payload["nodes"], payload["links"], scan, index)
    render_warning = ""
    if payload.get("total_modules", 0) > GRAPH_DISPLAY_CAP and payload["view"] == "module":
        render_warning = (
            f"Showing top {GRAPH_DISPLAY_CAP:,} modules by risk (of {payload['total_modules']:,}). "
            "Use Hierarchy or Architecture overview to explore the full repository."
        )
    elif total_modules >= GRAPH_DEFAULT_HIERARCHY_THRESHOLD and mode == "module" and not force_module:
        render_warning = (
            f"Large repository ({total_modules:,} modules) — Hierarchy view is recommended; "
            "use Module graph here for the full codebase."
        )
    return {
        "ok": True,
        "graph_scope": graph.get("graph_scope"),
        "degraded": bool(graph.get("degraded")),
        "view": payload["view"],
        "layout": payload.get("layout", "galaxy"),
        "cluster_count": payload.get("cluster_count", 0),
        "bridge_link_count": payload.get("bridge_link_count", 0),
        "clusters": payload.get("clusters", []),
        "tour_stops": tour_stops,
        "node_count": payload["node_count"],
        "link_count": payload["link_count"],
        "total_modules": payload["total_modules"],
        "total_edges": payload["total_edges"],
        "display_cap": GRAPH_DISPLAY_CAP,
        "massive_mode": is_massive,
        "recommended_view": recommended,
        "render_warning": render_warning,
        "defaulted_to_subsystem": False,
        "architecture_clusters": bool(payload.get("architecture_clusters")),
        "nodes": payload["nodes"],
        "links": payload["links"],
    }


def current_risks() -> Dict[str, Any]:
    risks = _STATE.get("risks")
    if not risks:
        return {"ok": False, "error": "No repository scanned yet.", "ranked_modules": []}
    return {
        "ok": True,
        "graph_scope": _STATE["scan"]["graph_scope"],
        "import_cycles": _STATE["scan"].get("import_cycle_count", 0),
        "ranked_modules": risks.get("ranked_modules", []),
    }


def current_timeline() -> Dict[str, Any]:
    """Architecture timeline hooks — current scan snapshot; history persisted in future phases."""
    scan = _STATE.get("scan")
    if not scan:
        return {"ok": False, "error": "No repository scanned yet.", "snapshots": []}
    snapshot = {
        "timestamp": scan.get("completed_at") or scan.get("started_at") or time.time(),
        "module_count": scan.get("module_count", 0),
        "dependency_count": scan.get("dependency_edges", 0),
        "risk_score": _repo_risk_score(),
        "cycle_count": scan.get("import_cycle_count", 0),
        "graph_health": _graph_health(scan).get("label", "unknown"),
        "source": "current_scan",
    }
    return {
        "ok": True,
        "history_available": False,
        "note": "Single-scan baseline; multi-scan history persistence is a future hook.",
        "snapshots": [snapshot],
        "latest": snapshot,
    }


def current_tour(view: str = "module") -> Dict[str, Any]:
    graph_payload = current_graph(view)
    if not graph_payload.get("ok"):
        return graph_payload
    return {
        "ok": True,
        "view": graph_payload.get("view", view),
        "stop_count": len(graph_payload.get("tour_stops") or []),
        "stops": graph_payload.get("tour_stops") or [],
    }


def module_inspector(target: str) -> Dict[str, Any]:
    """Rich module panel payload from existing scan artifacts (no new analysis)."""
    graph = _STATE.get("graph")
    scan = _STATE.get("scan")
    if not graph or not scan:
        return {"ok": False, "error": "No repository scanned yet."}
    target = (target or "").strip().replace("\\", "/")
    if not target:
        return {"ok": False, "error": "Module id or path required."}

    index = _STATE.get("index") or {}
    risks = _STATE.get("risks") or {}
    risk_by_path = _risk_lookup(risks)
    module_nodes = {n["id"]: n for n in graph.get("nodes", []) if n.get("type") == "module"}

    match_id = None
    match_node = None
    if target in module_nodes:
        match_id, match_node = target, module_nodes[target]
    else:
        for nid, node in module_nodes.items():
            path = node.get("path", "")
            if path == target or path.endswith("/" + target) or node.get("dotted") == target:
                match_id, match_node = nid, node
                break

    if not match_node:
        return {"ok": False, "error": f"Module not found: {target}"}

    path = match_node.get("path", "")
    importers: List[str] = []
    imports: List[str] = []
    for edge in graph.get("edges", []):
        if edge.get("type") != "imports" or not edge.get("resolved"):
            continue
        if edge.get("to") == match_id and edge.get("from") in module_nodes:
            importers.append(module_nodes[edge["from"]].get("path", edge["from"]))
        if edge.get("from") == match_id and edge.get("to") in module_nodes:
            imports.append(module_nodes[edge["to"]].get("path", edge["to"]))

    cycle_members: List[str] = []
    for cycle in (graph.get("statistics") or {}).get("import_cycles", []):
        members = cycle if isinstance(cycle, list) else cycle.get("members", [])
        if match_id in members or path in members:
            cycle_members = [str(item).split(":", 1)[-1] for item in members]

    risk = risk_by_path.get(path, {})
    impact_payload = impact(path)
    return {
        "ok": True,
        "node_id": match_id,
        "path": path,
        "label": match_node.get("dotted") or path,
        "subsystem": _subsystem_for_path(path, index),
        "risk_score": round(float(risk.get("total_score", 0)), 2),
        "risk_rank": risk.get("rank"),
        "risk_tier": _risk_tier(
            score=float(risk.get("total_score", 0)),
            rank=risk.get("rank"),
            max_score=max((float(r.get("total_score", 0)) for r in risk_by_path.values()), default=0.0),
            in_cycle=bool(cycle_members),
        ),
        "loc": int(match_node.get("line_count") or 0),
        "fan_in": len(importers),
        "fan_out": len(imports),
        "importers": sorted(set(importers))[:40],
        "imports": sorted(set(imports))[:40],
        "in_cycle": bool(cycle_members),
        "cycle_members": cycle_members[:12],
        "evidence": (risk.get("signals") or [])[:8],
        "blast_radius": impact_payload.get("affected_file_count", 0),
        "affected_node_ids": impact_payload.get("affected_node_ids", []),
    }


def current_hierarchy_graph(level: str = "subsystem", parent: str = "") -> Dict[str, Any]:
    """Hierarchical graph for massive repositories: subsystem -> package -> module."""
    graph = _STATE.get("graph")
    index = _STATE.get("index") or {}
    if not graph:
        return {"ok": False, "error": "No repository scanned yet.", "nodes": [], "links": []}
    level = (level or "subsystem").strip().lower()
    def _hotspots(nodes: List[Dict[str, Any]]) -> int:
        return sum(1 for n in nodes if str(n.get("risk_tier", "")) in {"top", "elevated", "cycle"} or float(n.get("risk_score", 0)) >= 20)

    if level == "subsystem":
        payload = _subsystem_graph_payload(graph, index, _STATE.get("risks") or {})
        return {
            "ok": True,
            "level": "subsystem",
            "parent": "",
            "counts": {
                "files": len(index.get("files") or []),
                "modules": payload.get("total_modules", 0),
                "edges": payload.get("total_edges", 0),
                "risk_hotspots": _hotspots(payload.get("nodes") or []),
            },
            **payload,
        }

    module_payload = _module_graph_payload(graph, index, _STATE.get("risks") or {})
    modules = module_payload["nodes"]
    parent = (parent or "").strip()
    if level == "package":
        package_nodes: Dict[str, Dict[str, Any]] = {}
        package_edges: Dict[tuple[str, str], int] = {}
        module_by_id = {n["id"]: n for n in modules}
        for node in modules:
            subsystem = node.get("subsystem", "(root)")
            if parent and subsystem != parent:
                continue
            pkg = (node.get("path", "") or "").rsplit("/", 1)[0] or "(root)"
            bid = f"package:{pkg}"
            bucket = package_nodes.setdefault(
                bid,
                {
                    "id": bid,
                    "label": pkg,
                    "subsystem": subsystem,
                    "module_count": 0,
                    "file_count": 0,
                    "edge_count": 0,
                    "risk_score": 0.0,
                    "risk_tier": node.get("risk_tier", "normal"),
                    "size": 4.0,
                },
            )
            bucket["module_count"] += 1
            bucket["file_count"] += 1
            bucket["risk_score"] = max(bucket["risk_score"], node.get("risk_score", 0))
            if str(node.get("risk_tier")) in {"top", "cycle"}:
                bucket["risk_tier"] = node.get("risk_tier")
            bucket["size"] = round(4 + min(20, bucket["module_count"] * 0.4), 2)
        for link in module_payload["links"]:
            src = module_by_id.get(link["source"])
            dst = module_by_id.get(link["target"])
            if not src or not dst:
                continue
            if parent and (src.get("subsystem") != parent or dst.get("subsystem") != parent):
                continue
            src_pkg = (src.get("path", "") or "").rsplit("/", 1)[0] or "(root)"
            dst_pkg = (dst.get("path", "") or "").rsplit("/", 1)[0] or "(root)"
            key = (src_pkg, dst_pkg)
            package_edges[key] = package_edges.get(key, 0) + 1
        links = []
        for (src_pkg, dst_pkg), count in package_edges.items():
            sid = f"package:{src_pkg}"
            tid = f"package:{dst_pkg}"
            if sid not in package_nodes or tid not in package_nodes:
                continue
            links.append({"source": sid, "target": tid, "weight": 1 + min(6, count * 0.2), "opacity": 0.28})
            package_nodes[sid]["edge_count"] = package_nodes[sid].get("edge_count", 0) + count
            package_nodes[tid]["edge_count"] = package_nodes[tid].get("edge_count", 0) + count
        nodes = sorted(package_nodes.values(), key=lambda n: (-n["module_count"], n["label"]))
        return {
            "ok": True,
            "level": "package",
            "parent": parent,
            "counts": {
                "files": sum(int(n.get("file_count", 0)) for n in nodes),
                "modules": sum(int(n.get("module_count", 0)) for n in nodes),
                "edges": sum(int(n.get("edge_count", 0)) for n in nodes),
                "risk_hotspots": _hotspots(nodes),
            },
            "nodes": nodes,
            "links": links,
        }

    if level == "module":
        selected = [n for n in modules if (not parent or n.get("path", "").startswith(parent.strip("/") + "/") or n.get("subsystem") == parent)]
        ids = {n["id"] for n in selected}
        links = [l for l in module_payload["links"] if l["source"] in ids and l["target"] in ids]
        return {
            "ok": True,
            "level": "module",
            "parent": parent,
            "counts": {
                "files": len(selected),
                "modules": len(selected),
                "edges": len(links),
                "risk_hotspots": _hotspots(selected),
            },
            "nodes": selected,
            "links": links,
        }

    return {"ok": False, "error": f"Unsupported hierarchy level: {level}"}


def impact(target: str) -> Dict[str, Any]:
    """Reverse-dependency impact from the real graph (mock fallback if unresolved)."""
    graph = _STATE.get("graph")
    if not graph or not target:
        return _impact_mock(target, reason="No scan / no target")
    target = target.strip().replace("\\", "/")
    nodes = {n["id"]: n for n in graph.get("nodes", []) if n.get("type") == "module"}
    match = None
    for nid, n in nodes.items():
        p = n.get("path", "")
        if p == target or p.endswith("/" + target) or (n.get("dotted") == target):
            match = (nid, n)
            break
    if match is None:
        return _impact_mock(target, reason="Target not found in production graph")
    nid, node = match
    importers = [e["from"] for e in graph.get("edges", [])
                 if e.get("type") == "imports" and e.get("resolved") and e.get("to") == nid]
    affected_files = sorted({nodes[i]["path"] for i in importers if i in nodes})
    affected_subsystems = sorted({(p.split("/")[0] if "/" in p else "(root)") for p in affected_files})
    risk = next((r for r in (_STATE.get("risks") or {}).get("ranked_modules", []) if r.get("path") == node["path"]), {})
    fan_in = len(importers)
    level = "high" if fan_in >= 25 else "medium" if fan_in >= 6 else "low"
    affected_node_ids = sorted(importers)
    return {
        "ok": True,
        "target": node.get("path"),
        "target_node_id": nid,
        "fan_in": fan_in,
        "risk_level": level,
        "risk_score": risk.get("total_score", 0),
        "affected_files": affected_files[:40],
        "affected_file_count": len(affected_files),
        "affected_node_ids": affected_node_ids,
        "affected_subsystems": affected_subsystems,
        "recommended_tests": _recommended_tests(node.get("path", ""), affected_subsystems),
        "recommended_prompt": _impact_prompt(node.get("path", ""), fan_in, affected_subsystems),
        "impact_scope": "direct_only",
        "transitive_available": False,
        "note": "Direct importers only (resolved import edges). Transitive blast radius is not computed in this release.",
    }


def _impact_mock(target: str, reason: str) -> Dict[str, Any]:
    # P161 — Impact hardening: never fake success or a blast radius when the
    # target is not resolved. Return ok=False with an honest, actionable status
    # instead of a mock=True payload that looks like a real result.
    return {
        "ok": False,
        "mock": False,
        "status": "target_not_resolved",
        "unresolved": True,
        "target": target,
        "reason": reason,
        "error": f"Unable to resolve target: {target}. {reason}",
        "risk_level": "unknown",
        "affected_files": [],
        "affected_subsystems": [],
        "next_steps": [
            "Use an exact file or module path from the Codebase Map.",
            "Re-scan the repository if the file was added recently.",
        ],
    }


def _planning_context() -> Dict[str, Any]:
    ctx = planning_engine.repository_context_from_state(_STATE)
    if _STATE.get("scan"):
        summary = current_summary()
        if summary.get("ok"):
            ctx["summary"] = summary
            ctx["entry_points"] = summary.get("entry_points") or ctx.get("entry_points")
            ctx["subsystems"] = summary.get("subsystems") or ctx.get("subsystems")
            ctx["explanation"] = summary.get("explanation") or ctx.get("explanation")
    return ctx


def plan_change(request: str) -> Dict[str, Any]:
    """Generate a grounded change plan and implementation prompts (no code generation)."""
    t0 = time.time()
    result = planning_engine.plan_change(request, _planning_context())
    _record_workflow_timing("build_plan", t0)
    if result.get("ok"):
        plan = result["plan"]
        result["formatted"] = planning_engine.format_change_plan_markdown(plan)
        track_analytics_event("change_plan_created", intent=plan.get("intent"), confidence=plan.get("confidence"))
        _record_usage("build_plan_created", intent=plan.get("intent"))
    return result


def investigate_symptom(symptom: str) -> Dict[str, Any]:
    """Symptom-based investigation plan (natural language, not trace-only)."""
    t0 = time.time()
    result = planning_engine.investigate_symptom(symptom, _planning_context())
    _record_workflow_timing("investigation", t0)
    if result.get("ok"):
        plan = result["plan"]
        result["formatted"] = planning_engine.format_investigation_plan_markdown(plan)
        track_analytics_event("investigation_plan_created", intent=plan.get("intent"), confidence=plan.get("confidence"))
        _record_usage("investigation_created", intent=plan.get("intent"))
    return result


def change_impact_simulation(target: str) -> Dict[str, Any]:
    """Phase 132 — full impact analysis (transitive reverse deps + subsystem
    coupling + tests + risk classification), via the dedicated impact engine."""
    from . import impact_engine

    summary = current_summary() if _STATE.get("scan") else {}
    t0 = time.time()
    res = impact_engine.analyze_impact(target, _STATE, summary=summary if summary.get("ok") else None)
    _record_workflow_timing("impact", t0)
    if not res.get("ok"):
        return res
    # Backward-compatible `simulation` block (UI + evaluator + graph highlight).
    res["simulation"] = {
        "potentially_affected_modules": res.get("affected_files", []),
        "potentially_affected_subsystems": res.get("affected_subsystems", []),
        "resolved_modules": res.get("resolved_modules", []),
        "resolved_symbols": res.get("resolved_symbols", []),
        "semantic_concept": res.get("semantic_concept", ""),
        "semantic_label": res.get("semantic_label", ""),
        "architectural_blast_radius": res.get("architectural_blast_radius"),
        "risk_level": res.get("risk_level", "unknown"),
        "recommended_verification": res.get("recommended_verification", []),
        "tests_likely_affected": res.get("tests_likely_affected", []),
        "direct_impact": res.get("direct_impact", []),
        "indirect_impact": res.get("indirect_impact", []),
        "what_may_break": res.get("what_may_break", []),
        "what_probably_wont_break": res.get("what_probably_wont_break", []),
    }
    res["limitations"] = [
        res.get("note", "Static reverse-import impact (resolved edges only)."),
        "Dynamic dispatch and string-based imports are not modeled.",
    ]
    _augment_impact_with_architecture(res)
    track_analytics_event("impact_analyzed", risk_level=res.get("risk_level"), confidence=res.get("confidence"))
    _record_usage("impact_created", target=target, risk_level=res.get("risk_level"))
    return res


def _augment_impact_with_architecture(res: Dict[str, Any]) -> None:
    """Phase 134 — add architectural blast-radius reasoning to an impact result."""
    arch = _architecture_analysis()
    if not arch.get("ok"):
        return
    mbp = arch.get("modules_by_path", {})
    tinfo = mbp.get(res.get("target") or "", {})
    affected = res.get("affected_files", []) or []
    direct = res.get("direct_impact", []) or []
    indirect = res.get("indirect_impact", []) or []

    def _layer(p: str) -> str:
        n = (p or "").replace("\\", "/")
        parts = n.split("/")
        if len(parts) >= 3 and parts[1] in ("components", "integrations", "plugins"):
            return "/".join(parts[:3])
        return "/".join(parts[:2]) if len(parts) >= 2 else (parts[0] if parts else "")

    layers = sorted({_layer(p) for p in affected if p})
    risky = [p for p in affected
             if mbp.get(p, {}).get("is_runtime_boundary") or (mbp.get(p, {}).get("risk_score", 0) >= 45)]
    runtime_crit = bool(tinfo.get("is_runtime_boundary"))
    is_config = bool(tinfo.get("is_config"))

    if runtime_crit:
        conf_expl = ("Target is on a runtime boundary (event/state/request/auth path); "
                     "changes can alter live behavior across many subsystems.")
    elif is_config:
        conf_expl = ("Target is a config/constants hub: blast radius is mostly recompiles, "
                     "imports and tests — direct runtime-logic breakage is unlikely unless "
                     "specific constant values are depended on.")
    else:
        conf_expl = (f"{len(direct)} direct + {len(indirect)} transitive importer(s) across "
                     f"{len(layers)} subsystem(s); behavioral risk scales with that coupling.")

    res["architecture"] = {
        "architectural_blast_radius": len(set(direct) | set(indirect)),
        "boundary_crossing_subsystems": len(layers),
        "subsystems_impacted": layers[:12],
        "runtime_criticality": runtime_crit,
        "target_patterns": tinfo.get("patterns", []),
        "target_risk_score": tinfo.get("risk_score"),
        "target_risk_components": tinfo.get("risk_components", {}),
        "is_config_hub": is_config,
        "risky_areas": risky[:10],
        "safe_areas": res.get("what_probably_wont_break", []),
        "confidence_explanation": conf_expl,
    }
    # Also expose at top level for consumers that read them directly.
    res["risky_areas"] = risky[:10]
    res["safe_areas"] = res.get("what_probably_wont_break", [])
    res["architectural_blast_radius"] = len(set(direct) | set(indirect))
    res["confidence_explanation"] = conf_expl
    if is_config:
        res.setdefault("risks_of_incorrect_fix", [])
        msg = ("High fan-in config/constants module — many tests affected, but behavioral "
               "breakage is unlikely unless specific constant values are relied on.")
        if msg not in res["risks_of_incorrect_fix"]:
            res["risks_of_incorrect_fix"].insert(0, msg)


def bug_investigation(text: str) -> Dict[str, Any]:
    """Heuristic bug localization from a stack trace / description.

    MOCK/TODO: real semantic localization + verification evidence wiring is future
    work. This v1 matches file/identifier tokens to indexed modules — honest and
    deterministic, with explicit confidence.
    """
    index = _STATE.get("index")
    if not index:
        return {"ok": False, "error": "No repository scanned yet."}
    blob = (text or "")
    paths = [f["path"] for f in index["files"] if f["path"] and f["path"] in blob.replace("\\", "/")]
    # token-level fallback: match basenames / dotted modules mentioned in the text
    lowered = blob.lower()
    if not paths:
        for f in index["files"]:
            base = os.path.basename(f["path"]).lower()
            if base and base.endswith(".py") and base[:-3] in lowered and len(base) > 6:
                paths.append(f["path"])
    paths = sorted(set(paths))[:8]
    confidence = "high" if any(p in blob.replace("\\", "/") for p in paths) else ("medium" if paths else "low")
    return {
        "ok": True,
        "mock": not bool(paths),
        "todo": "Wire semantic localization + verification evidence for confirmed-defect ranking.",
        "likely_modules": paths,
        "evidence": [f"`{p}` referenced in the provided text" for p in paths] or
                    ["No repository path or module name matched the input text."],
        "confidence": confidence,
        "recommended_files": paths,
        "suggested_prompt": _bug_prompt(text, paths),
    }


def context_export(target: str = "claude", packet: str = "compact", *, track: bool = True) -> Dict[str, Any]:
    """Build a copyable, token-estimated AI-context packet for the open repo."""
    if not _STATE.get("scan"):
        return {"ok": False, "error": "No repository scanned yet."}
    target = (target or "claude").lower()
    packet = (packet or "compact").lower()
    if target not in ("claude", "codex", "cursor"):
        target = "claude"
    if packet not in ("compact", "verbose"):
        packet = "compact"
    text = _render_context(target, packet)
    if track:
        track_analytics_event("export_created", target=target, packet=packet)
        _record_usage("export_created", target=target, packet=packet)
    return {
        "ok": True,
        "target": target,
        "packet": packet,
        "estimated_tokens": estimate_tokens(text),
        "text": text,
    }


def _graph_topology_svg(graph_payload: Dict[str, Any]) -> str:
    """2D galaxy topology SVG from real graph layout coordinates."""
    nodes = graph_payload.get("nodes") or []
    links = graph_payload.get("links") or []
    if not nodes:
        return '<svg xmlns="http://www.w3.org/2000/svg"><text x="8" y="16">No graph data</text></svg>'
    xs = [float(n.get("galaxy_x") or 0) for n in nodes]
    ys = [float(n.get("galaxy_y") or 0) for n in nodes]
    pad = 40.0
    min_x, max_x = min(xs) - pad, max(xs) + pad
    min_y, max_y = min(ys) - pad, max(ys) + pad
    width, height = max(max_x - min_x, 80), max(max_y - min_y, 80)
    by_id = {n["id"]: n for n in nodes}
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{min_x} {min_y} {width} {height}" '
        f'width="{int(width * 2)}" height="{int(height * 2)}">',
        f'<rect x="{min_x}" y="{min_y}" width="{width}" height="{height}" fill="#070b14"/>',
    ]
    for link in links:
        src = by_id.get(link.get("source"))
        tgt = by_id.get(link.get("target"))
        if not src or not tgt:
            continue
        stroke = "#42f5b0" if link.get("bridge") else "#5b76c8"
        opacity = link.get("opacity") or 0.2
        width_px = 1.2 if link.get("bridge") else 0.6
        parts.append(
            f'<line x1="{src["galaxy_x"]}" y1="{src["galaxy_y"]}" x2="{tgt["galaxy_x"]}" y2="{tgt["galaxy_y"]}" '
            f'stroke="{stroke}" stroke-opacity="{opacity}" stroke-width="{width_px}"/>'
        )
    for node in nodes:
        radius = 5 if node.get("is_hub") else 2.2
        fill = "#9a7bff" if node.get("in_cycle") else ("#3ef0ff" if node.get("is_hub") else "#5b76c8")
        parts.append(
            f'<circle cx="{node["galaxy_x"]}" cy="{node["galaxy_y"]}" r="{radius}" fill="{fill}"/>'
        )
        if node.get("is_hub"):
            label = str(node.get("label", "")).replace("&", "&amp;").replace("<", "&lt;")
            parts.append(
                f'<text x="{float(node["galaxy_x"]) + 6}" y="{float(node["galaxy_y"]) - 6}" '
                f'fill="#3ef0ff" font-size="8" font-family="Inter,sans-serif">{label}</text>'
            )
    parts.append("</svg>")
    return "".join(parts)


def _architecture_report_text(summary: Dict[str, Any]) -> str:
    lines = [
        "JARVIS Architecture Report",
        "==========================",
        f"Repository: {summary.get('repo_name', '')}",
        f"Modules: {summary.get('module_count', 0)}",
        f"Dependency edges: {summary.get('dependency_edges', 0)}",
        f"Subsystems: {summary.get('subsystem_count', 0)}",
        f"Risk score: {summary.get('risk_score', 0)}",
        f"Graph health: {(summary.get('graph_health') or {}).get('label', 'unknown')}",
        "",
        "Explanation",
        "-----------",
        summary.get("explanation", ""),
        "",
        "Top risks",
        "---------",
    ]
    for risk in summary.get("top_risks") or []:
        lines.append(f"- {risk.get('module')} ({risk.get('score')}): {', '.join(risk.get('reasons') or [])}")
    lines.extend(["", "Top hubs", "--------"])
    for hub in summary.get("top_hubs") or []:
        lines.append(f"- {hub.get('module')} <- {hub.get('fan_in')} importers")
    return "\n".join(lines)


def export_demo_bundle() -> Dict[str, Any]:
    """One-click demo bundle: summary, architecture report, graph SVG, AI context."""
    if not _STATE.get("scan"):
        return {"ok": False, "error": "No repository scanned yet."}
    summary = current_summary()
    if not summary.get("ok"):
        return summary
    graph = current_graph("module")
    context = context_export("claude", "compact", track=False)
    report = _architecture_report_text(summary)
    svg = _graph_topology_svg(graph)
    manifest = {
        "product": "JARVIS Desktop",
        "version": PRODUCT_VERSION,
        "repo_name": summary.get("repo_name"),
        "demo_mode": summary.get("demo_mode"),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "files": [
            "manifest.json",
            "summary.json",
            "architecture_report.txt",
            "graph_topology.svg",
            "context_claude_compact.txt",
            "screenshots/README.txt",
            "landing_assets/checklists.md",
        ],
    }
    landing_checklist = (
        "# Landing asset capture checklist\n\n"
        "## Screenshots\n"
        "- Command Center galaxy graph (Screenshot mode)\n"
        "- Module Inspector with evidence\n"
        "- Copilot impact answer with blast radius\n"
        "- Health Cockpit metrics\n\n"
        "## GIF ideas\n"
        "- Tour Repository camera flight\n"
        "- Copilot question -> graph highlight\n\n"
        "## Demo video beats\n"
        "1. Install / Try Demo\n2. Graph wow\n3. Risk tour\n4. Impact\n5. Export bundle\n"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", _json.dumps(manifest, indent=2))
        archive.writestr("summary.json", _json.dumps(summary, indent=2, default=str))
        archive.writestr("architecture_report.txt", report)
        archive.writestr("graph_topology.svg", svg)
        archive.writestr("context_claude_compact.txt", context.get("text", ""))
        archive.writestr(
            "screenshots/README.txt",
            "Capture marketing PNGs from JARVIS Desktop Screenshot mode, then add them here.\n",
        )
        archive.writestr("landing_assets/checklists.md", landing_checklist)
    payload = buffer.getvalue()
    stamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"jarvis_demo_bundle_{stamp}.zip"
    track_analytics_event("bundle_exported", bytes=len(payload))
    return {
        "ok": True,
        "filename": filename,
        "size_bytes": len(payload),
        "content_base64": base64.b64encode(payload).decode("ascii"),
    }


# --------------------------------------------------------------------------
# Derived intelligence (deterministic, from the scan)
# --------------------------------------------------------------------------
def _repo_risk_score() -> int:
    risks = (_STATE.get("risks") or {}).get("ranked_modules", [])
    if not risks:
        return 0
    top = max((r.get("total_score", 0) for r in risks[:5]), default=0)
    return int(round(top))


def _architecture_summary(arch: Dict[str, Any]) -> Dict[str, Any]:
    """Repository Map architectural surfaces (Phase 134)."""
    u = arch.get("unresolved", {}) or {}
    # Architectural hotspots = modules high on >= 2 distinct risk dimensions.
    hotspots: List[Dict[str, Any]] = []
    for r in arch.get("top_risks", []):
        comps = r.get("components", {}) or {}
        strong = [k for k, v in comps.items() if v >= 0.5]
        if len(strong) >= 2:
            hotspots.append({"path": r["path"], "score": r["score"],
                             "dimensions": strong, "patterns": r.get("patterns", [])})
    return {
        "ok": True,
        "top_boundaries": arch.get("top_boundaries", [])[:6],
        "cycles": arch.get("cycles", [])[:6],
        "cycle_count": len(arch.get("cycles", [])),
        "patterns": {k: v for k, v in list(arch.get("patterns", {}).items())[:14]},
        "dynamic_zones": arch.get("dynamic_zones", [])[:12],
        "hotspots": hotspots[:8],
        "hubs_risks_identical": arch.get("hubs_risks_identical"),
        "hubs_risks_overlap": arch.get("hubs_risks_overlap"),
        "unresolved_breakdown": {
            "buckets": u.get("buckets", {}),
            "internal_unresolved": u.get("internal_unresolved", 0),
            "external_unresolved": u.get("external_unresolved", 0),
            "dynamic_import_count": u.get("dynamic_import_count", u.get("dynamic_optional", 0)),
            "samples": u.get("samples", {}),
            "note": u.get("note", ""),
        },
        "architecture_summary": arch.get("architecture_summary", {}),
        "graph_health_reason": arch.get("graph_health_reason", ""),
    }


def _graph_health(scan: Dict[str, Any], arch: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    resolved = int(scan.get("resolved_imports", scan.get("dependency_edges", 0)) or 0)
    unresolved = int(scan.get("unresolved_imports", 0) or 0)
    external = int(scan.get("external_package_imports", 0) or 0)
    total = resolved + unresolved
    ratio = round(unresolved / total, 4) if total else 0.0

    # Phase 134 — health is driven by INTERNAL unresolved imports, not external
    # packages / stdlib / dynamic integration imports (which are expected and not
    # graph defects). Home Assistant has tens of thousands of external/dynamic
    # imports but a near-complete internal graph; it must not be flagged "partial"
    # for that reason.
    internal_unres = external_unres = dynamic_unres = None
    internal_ratio = None
    if arch and arch.get("ok"):
        u = arch.get("unresolved", {}) or {}
        internal_unres = int(u.get("internal_unresolved", 0))
        external_unres = int(u.get("external_unresolved", 0))
        dynamic_unres = int(u.get("dynamic_import_count", u.get("dynamic_optional", 0)))
        internal_total = resolved + internal_unres
        internal_ratio = round(internal_unres / internal_total, 4) if internal_total else 0.0
        unresolved_high = internal_unres >= 50 and internal_ratio >= 0.15
    else:
        unresolved_high = (
            unresolved >= UNRESOLVED_IMPORT_PARTIAL_MIN
            and ratio >= UNRESOLVED_IMPORT_PARTIAL_RATIO
        )

    cycles = scan.get("import_cycle_count", 0)
    if arch and arch.get("ok"):
        cycles = len(arch.get("cycles", [])) or cycles
    # A degraded SCOPE that is actually a complete import-level graph is not unhealthy.
    truly_degraded = bool(scan.get("degraded")) and scan.get("graph_detail") != "imports"
    graph_partial = truly_degraded or unresolved_high
    label = "partial" if graph_partial else ("healthy" if cycles <= 4 else "watch")

    # P161 — Graph health truth: a repository where Atlas scanned many files but
    # built almost no modules (e.g. Kubernetes: 24k files / 3 modules) must NEVER
    # report "healthy". Take the WORSE of the summary label and the reliability
    # assessment, and propagate the unified vocabulary {healthy, partial,
    # degraded, unsupported}.
    try:
        from . import reliability as _rel

        _rel_cat = _rel.classify_scan(scan).get("category") or _rel.OK
        _UNIFIED = {
            _rel.OK: "healthy",
            _rel.PARTIAL_GRAPH: "partial",
            _rel.UNRESOLVED_EXPLOSION: "partial",
            _rel.ZERO_EDGE_GRAPH: "degraded",
            _rel.ZERO_MODULE_SCAN: "degraded",
            _rel.TIMEOUT: "degraded",
            _rel.MEMORY_PRESSURE: "degraded",
            _rel.SCAN_CRASH: "degraded",
            _rel.SCAN_FAILED: "degraded",
            _rel.UNSUPPORTED_LANGUAGE: "unsupported",
            _rel.EMPTY_REPO: "empty",
        }
        _rel_label = _UNIFIED.get(_rel_cat, label)
        _SEVERITY = {"healthy": 0, "watch": 1, "partial": 2, "empty": 2, "degraded": 3, "unsupported": 4}
        if _SEVERITY.get(_rel_label, 0) > _SEVERITY.get(label, 0):
            label = _rel_label
        graph_partial = graph_partial or label in ("partial", "degraded", "unsupported")
    except Exception:
        _rel_cat = ""
    out = {
        "reliability_category": _rel_cat,
        "scope": scan["graph_scope"],
        "degraded": graph_partial,
        "modules": scan["module_count"],
        "edges": scan["dependency_edges"],
        "import_cycles": cycles,
        "resolved_imports": resolved,
        "unresolved_imports": unresolved,
        "external_package_imports": external,
        "unresolved_ratio": ratio,
        # Phase 123 — honest labeling (data trust). The current resolver reports
        # `imports_external`: every import whose target is OUTSIDE the internal
        # production module set. That bucket includes third-party packages and the
        # standard library, NOT just failed internal resolutions. A high ratio is
        # normal for dependency-heavy apps and does not by itself mean the internal
        # graph is incomplete. (External vs internal-unresolved split is a tracked
        # improvement — see reports/phase123_unresolved_imports_investigation.md.)
        "unresolved_ratio_note": (
            "External imports (targets outside the internal module set: third-party "
            "packages + standard library + any unresolved internal imports) ÷ all imports. "
            "High values are normal for apps with many dependencies."
        ),
        "external_label": "external + stdlib imports",
        "label": label,
    }
    if internal_unres is not None:
        out["unresolved_internal"] = internal_unres
        out["unresolved_external"] = external_unres
        out["unresolved_dynamic_optional"] = dynamic_unres
        out["unresolved_internal_ratio"] = internal_ratio
        out["health_basis"] = "internal_unresolved"
        out["notice"] = (
            (f"Graph health reflects {internal_unres} unresolved INTERNAL import(s) "
             f"({internal_ratio:.0%} of internal imports). The {external_unres} external/"
             "stdlib import(s) are expected dependencies, not defects.")
            if unresolved_high else
            (f"Internal graph is reliable: {internal_unres} unresolved internal import(s). "
             f"The {external_unres} external/stdlib import(s) are normal dependencies.")
        )
        out["reliable"] = not unresolved_high
        out["reason"] = scan.get("graph_health_reason") or out.get("notice", "")
        out["partial_reason"] = (
            "Many internal imports are unresolved — some internal edges may be missing."
            if unresolved_high else ""
        )
    else:
        out["notice"] = (
            "Many imports point outside the internal module set (third-party packages, "
            "standard library, or unresolved internal imports). Common for dependency-heavy "
            "apps — internal architecture may still be fully mapped."
        ) if unresolved_high else ""
    return out


def _token_savings(scan: Dict[str, Any]) -> Dict[str, Any]:
    # Estimated tokens a coding agent would otherwise read to understand the repo
    # (rough: production modules x avg module tokens) vs the compact packet.
    avg_module_tokens = 600
    naive = scan["module_count"] * avg_module_tokens
    compact = scan.get("compact_token_estimate", 0) or 1
    reduction = round(100 * (naive - compact) / naive, 1) if naive else 0
    return {
        "naive_read_estimate": naive,
        "compact_packet_tokens": compact,
        "reduction_percent": reduction,
        "verified": False,
        "show_in_cockpit": False,
        "note": "Unverified estimate (module_count × 600 vs compact packet chars/4). Not shown in cockpit to avoid misleading savings claims.",
    }


def _recommended_tests(path: str, subsystems: List[str]) -> List[str]:
    base = os.path.basename(path)[:-3] if path.endswith(".py") else os.path.basename(path)
    tests = [f"tests for `{path}` (e.g. test_{base}.py)"]
    if subsystems:
        tests.append(f"tests in affected subsystems: {', '.join(subsystems[:5])}")
    tests.append("the project's full test suite before merge")
    return tests


def _impact_prompt(target: str, fan_in: int, subsystems: List[str]) -> str:
    subs = ", ".join(subsystems[:6]) or "(none resolved)"
    return (
        f"I am about to change `{target}` (imported by {fan_in} module(s), affecting "
        f"subsystems: {subs}). Review the change for breakage risk: check each direct "
        f"importer's usage, confirm the public interface stays compatible, and list the "
        f"specific tests to run before merge. Flag any dynamic/unresolved usage I should verify manually."
    )


def _bug_prompt(text: str, paths: List[str]) -> str:
    files = ", ".join(f"`{p}`" for p in paths) or "the most relevant modules"
    snippet = (text or "").strip().splitlines()
    head = snippet[0][:160] if snippet else ""
    return (
        f"Investigate this bug. Start with {files}. "
        f"Reported symptom: \"{head}\". For each candidate file, trace the failing path, "
        f"identify the root cause (not just the symptom line), and propose a minimal fix "
        f"with the test that would have caught it. State your confidence and any unknowns."
    )


def _recommended_questions(scan: Dict[str, Any]) -> List[str]:
    qs = [
        "What are the most important production subsystems?",
        "Rank the top architectural-risk modules and explain why.",
    ]
    if scan["top_hubs"]:
        qs.append(f"What is the blast radius of changing {scan['top_hubs'][0]['module']}?")
    if scan.get("import_cycle_count", 0):
        qs.append("Where are the import cycles and how do I break them?")
    qs.append("Prepare a compact context packet for Claude/Codex/Cursor.")
    return qs


def _plain_english(scan: Dict[str, Any], prod: List[Dict[str, Any]], entries: List[str]) -> str:
    names = ", ".join(s["name"] for s in prod[:6]) or "(none detected)"
    hub = scan["top_hubs"][0]["module"] if scan["top_hubs"] else "n/a"
    risk = scan["top_risks"][0]["module"] if scan["top_risks"] else "n/a"
    return (
        f"This repository has {scan['module_count']} production modules across "
        f"{scan['subsystem_count']} top-level subsystems. The largest production "
        f"subsystems are {names}. Its most depended-on module is {hub}, and the "
        f"highest architectural-risk module is {risk}. The dependency graph is "
        f"'{scan['graph_scope']}' with {scan['dependency_edges']} resolved import "
        f"edges and {scan.get('import_cycle_count', 0)} import cycle(s). Entry points "
        f"include {', '.join(entries[:4]) or 'n/a'}."
    )


# --------------------------------------------------------------------------
# Context packet rendering (the product's core value)
# --------------------------------------------------------------------------
_TARGET_PREAMBLE = {
    "claude": "You are assisting with the repository below. Use this precomputed Atlas repository intelligence as ground truth; read cited files only when you need detail.",
    "codex": "Repository context for Codex. Treat the Atlas facts below as verified structure; do not re-derive them by scanning the whole repo.",
    "cursor": "Cursor workspace context. Atlas has pre-analyzed this repo; use these facts to navigate and answer with fewer reads.",
}


def _render_context(target: str, packet: str) -> str:
    scan = _STATE.get("scan")
    index = _STATE.get("index") or {}
    if not scan:
        return ""
    subs = sorted(
        (s for s in index.get("subsystems", []) if s.get("role_counts", {}).get("production_code", 0) > 0),
        key=lambda s: (-s.get("role_counts", {}).get("production_code", 0), s.get("name", "")),
    )
    sub_lines = []
    for s in subs[: (8 if packet == "compact" else 20)]:
        deps = ",".join(s.get("dependencies", [])[:6])
        entry = ",".join(s.get("entry_files", [])[:2])
        sub_lines.append(
            f"- {s['name']} ({s['role_counts'].get('production_code',0)} prod files)"
            + (f"; entry: {entry}" if entry else "")
            + (f"; deps: {deps}" if deps else "")
        )
    hub_lines = [f"- {h['module']} <- {h['fan_in']} importers" for h in scan["top_hubs"][: (5 if packet == "compact" else 8)]]
    risk_lines = [
        f"- {r['module']} (score {r['score']}): {', '.join(r['reasons'][:3])}"
        for r in scan["top_risks"][: (4 if packet == "compact" else 6)]
    ]
    lines = [
        _TARGET_PREAMBLE[target],
        "",
        f"# ATLAS REPOSITORY CONTEXT — {scan['repo_name']}  ({packet})",
        f"scope={scan['graph_scope']} degraded={scan['degraded']}",
        f"modules={scan['module_count']} subsystems={scan['subsystem_count']} "
        f"edges={scan['dependency_edges']} cycles={scan.get('import_cycle_count',0)}",
        "",
        "## PRODUCTION SUBSYSTEMS",
        *sub_lines,
        "",
        "## MOST DEPENDED-ON MODULES (import fan-in)",
        *hub_lines,
        "",
        "## TOP ARCHITECTURAL RISKS",
        *risk_lines,
        "",
        "## UNCERTAINTY",
        "- Fan-in is a static lower bound (dynamic imports/dispatch not counted).",
    ]
    if scan["degraded"]:
        lines.append("- Dependency graph is DEGRADED; treat structure facts as partial.")
    if packet == "verbose":
        lines += [
            "",
            "## ENTRY POINTS",
            *[f"- {e}" for e in (current_summary().get("entry_points", [])[:10])],
        ]
    lines += [
        "",
        "## HOW TO USE",
        "Answer the user's question using these facts first; open a cited file only "
        "if you need its body. Prefer these structured facts over re-scanning the repo.",
    ]
    return "\n".join(lines).strip() + "\n"


# --------------------------------------------------------------------------
# Interactive repository copilot (Phase 109)
# --------------------------------------------------------------------------
def _copilot_copy_targets(packet: str = "compact") -> Dict[str, str]:
    return {
        "claude": _render_context("claude", packet),
        "codex": _render_context("codex", packet),
        "cursor": _render_context("cursor", packet),
    }


def _copilot_envelope(
    mode: str,
    answer: str,
    *,
    evidence: Optional[List[str]] = None,
    files: Optional[List[str]] = None,
    risk_level: str = "unknown",
    suggested_prompt: str = "",
    suggested_action: str = "",
    confidence: str = "high",
    limitations: Optional[List[str]] = None,
    packet: str = "compact",
    graph_highlight: Optional[Dict[str, Any]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload = {
        "ok": True,
        "mode": mode,
        "answer": answer,
        "evidence": evidence or [],
        "files": files or [],
        "risk_level": risk_level,
        "suggested_prompt": suggested_prompt,
        "suggested_action": suggested_action,
        "copy_targets": _copilot_copy_targets(packet),
        "confidence": confidence,
        "limitations": limitations or [],
    }
    if graph_highlight:
        payload["graph_highlight"] = graph_highlight
    if extra:
        payload.update(extra)
    return payload


def classify_copilot_question(question: str) -> str:
    """Deterministic intent routing for copilot questions."""
    q = (question or "").strip().lower()
    if not q:
        return "unknown"
    if any(token in q for token in ("claude", "codex", "cursor", "context packet", "generate a prompt", "generate prompt")):
        return "context_export"
    if "prompt" in q and any(token in q for token in ("generate", "copy", "prepare", "export")):
        return "context_export"
    if any(token in q for token in ("cycle", "circular", "import loop")):
        return "cycles"
    if any(token in q for token in ("who imports", "importers", "imported by", "imports this")):
        return "dependency"
    if any(token in q for token in ("what breaks", "blast radius", "impact of", "if i change", "what tests",
                                    "what depends on", "what happens if", "get rid of")):
        return "impact"
    if any(verb in q for verb in ("change ", "changing ", "remove ", "removing ", "delete ", "deleting ", "disable ")):
        return "impact"
    if any(token in q for token in ("risk", "dangerous", "bottleneck", "architectural risk")):
        return "risk"
    if any(token in q for token in ("what does this", "what does the repo", "repository do", "where should i start", "where to start", "entry point")):
        return "repository_understanding"
    if any(token in q for token in ("architecture", "subsystem", "subsystems", "explain module", "explain this module")):
        return "repository_understanding"
    if any(token in q for token in ("dependenc", "depend on")):
        return "dependency"
    return "unknown"


def _extract_path_from_question(question: str) -> Optional[str]:
    text = (question or "").replace("\\", "/")
    match = re.search(r"[\w./-]+\.py\b", text)
    if match:
        return match.group(0).strip("`'\"")
    match = re.search(r"change\s+([\w./-]+)", text, re.I)
    if match:
        candidate = match.group(1).strip("`'\"")
        if candidate.endswith(".py") or "/" in candidate:
            return candidate
    return None


def _extract_subsystem_from_question(question: str) -> Optional[str]:
    index = _STATE.get("index") or {}
    q = (question or "").lower()
    best = ""
    best_name = ""
    for sub in index.get("subsystems", []):
        name = str(sub.get("name", ""))
        if not name:
            continue
        if name.lower() in q and len(name) > len(best):
            best = name.lower()
            best_name = name
    return best_name or None


def _resolve_module_path(question: str, node_context: Optional[Dict[str, Any]] = None) -> Optional[str]:
    if node_context and node_context.get("path"):
        return str(node_context["path"])
    extracted = _extract_path_from_question(question)
    if extracted:
        return extracted
    graph = _STATE.get("graph") or {}
    q = (question or "").lower()
    for node in graph.get("nodes", []):
        if node.get("type") != "module":
            continue
        path = str(node.get("path", ""))
        label = str(node.get("dotted") or path)
        base = path.split("/")[-1].lower()
        if path and path.lower() in q:
            return path
        if base and base in q:
            return path
        if label.lower() in q:
            return path
    return None


def node_copilot_prompts(node: Dict[str, Any]) -> List[str]:
    path = str(node.get("path") or node.get("label") or "this module")
    return [
        f"Explain module {path}",
        f"What breaks if I change {path}?",
        f"Who imports {path}?",
        f"Generate a Claude prompt for {path}",
    ]


def _module_graph_neighbors(path: str) -> Tuple[Optional[Dict[str, Any]], List[str], List[str]]:
    graph = _STATE.get("graph") or {}
    nodes = {n["id"]: n for n in graph.get("nodes", []) if n.get("type") == "module"}
    match: Optional[Tuple[str, Dict[str, Any]]] = None
    for nid, node in nodes.items():
        node_path = str(node.get("path", ""))
        if node_path == path or node_path.endswith("/" + path) or path.endswith(node_path):
            match = (nid, node)
            break
    if match is None:
        return None, [], []
    nid, node = match
    importers: List[str] = []
    imports: List[str] = []
    for edge in graph.get("edges", []):
        if edge.get("type") != "imports" or not edge.get("resolved"):
            continue
        if edge.get("to") == nid and edge.get("from") in nodes:
            importers.append(nodes[edge["from"]]["path"])
        if edge.get("from") == nid and edge.get("to") in nodes:
            imports.append(nodes[edge["to"]]["path"])
    return node, sorted(set(importers)), sorted(set(imports))


def _answer_repository_understanding(question: str, packet: str) -> Dict[str, Any]:
    summary = current_summary()
    scan = _STATE.get("scan") or {}
    sub_name = _extract_subsystem_from_question(question)
    limitations: List[str] = []
    if sub_name:
        sub = next((s for s in summary.get("subsystems", []) if s.get("name") == sub_name), None)
        if sub:
            answer = (
                f"Subsystem `{sub_name}` contains {sub.get('production_files', 0)} production file(s). "
                f"Entry files: {', '.join(sub.get('entry_files') or []) or 'none listed'}. "
                f"Cross-subsystem dependencies: {', '.join(sub.get('dependencies') or []) or 'none detected'}."
            )
            evidence = [
                f"subsystem={sub_name}",
                f"production_files={sub.get('production_files', 0)}",
            ]
            files = list(sub.get("entry_files") or [])[:6]
            return _copilot_envelope(
                "repository_understanding",
                answer,
                evidence=evidence,
                files=files,
                risk_level="low",
                suggested_prompt=f"Explain the role of subsystem `{sub_name}` in this repository and how its entry files connect to the rest of the codebase.",
                suggested_action=f"Open entry files under `{sub_name}` and trace their imports.",
                confidence="high",
                limitations=limitations,
                packet=packet,
            )
        limitations.append(f"Subsystem `{sub_name}` was mentioned but not found in the scan index.")
    if "start" in question.lower():
        entries = summary.get("entry_points") or []
        answer = (
            "Start with the detected entry points, then follow import hubs. "
            f"Suggested entry files: {', '.join(entries[:6]) or 'none detected'}."
        )
        suggested_action = f"Inspect {entries[0]}" if entries else "Scan subsystems in Project Intelligence."
    else:
        answer = summary.get("explanation") or "No repository summary available."
        suggested_action = "Review subsystems and top hubs in Project Intelligence."
    return _copilot_envelope(
        "repository_understanding",
        answer,
        evidence=[
            f"modules={scan.get('module_count', 0)}",
            f"subsystems={scan.get('subsystem_count', 0)}",
            f"graph_scope={scan.get('graph_scope', '')}",
        ],
        files=(summary.get("entry_points") or [])[:8],
        risk_level="low",
        suggested_prompt=_render_context("claude", packet)[:800] + ("…" if len(_render_context("claude", packet)) > 800 else ""),
        suggested_action=suggested_action,
        confidence="high",
        limitations=limitations,
        packet=packet,
    )


def _answer_risk(packet: str) -> Dict[str, Any]:
    risks = current_risks()
    ranked = risks.get("ranked_modules") or []
    if not ranked:
        return _copilot_envelope(
            "risk",
            "No architectural risk ranking is available for this scan.",
            confidence="low",
            limitations=["Risk engine returned no ranked modules."],
            packet=packet,
        )
    lines = []
    evidence = []
    files = []
    for item in ranked[:8]:
        path = item.get("path", "")
        lines.append(
            f"{item.get('rank', '?')}. {item.get('label', path)} — score {item.get('total_score', 0)} "
            f"(fan-in={item.get('metrics', {}).get('fan_in', 0)})"
        )
        evidence.extend((item.get("signals") or [])[:2])
        if path:
            files.append(path)
    top_score = ranked[0].get("total_score", 0)
    risk_level = "high" if top_score >= 25 else "medium" if top_score >= 10 else "low"
    answer = "Top architectural-risk modules (production scope):\n" + "\n".join(lines)
    return _copilot_envelope(
        "risk",
        answer,
        evidence=evidence[:10],
        files=files[:10],
        risk_level=risk_level,
        suggested_prompt=(
            "Review the top architectural-risk modules below and explain which signals "
            "are structural vs. which could be challenged with better tests or refactors:\n"
            + answer
        ),
        suggested_action="Open the highest-ranked module and inspect its importers and test coverage.",
        confidence="high",
        limitations=["Ranking uses static import graph evidence; dynamic dispatch is not counted."],
        packet=packet,
    )


# Phase 134.2 — strip the question wrapper so the SEMANTIC resolver receives the
# bare concept ("event bus"), not the whole sentence ("what breaks if I remove…").
_IMPACT_CONCEPT_PATTERNS = (
    r"what breaks if i (?:remove|delete|drop|change|disable|get rid of)\s+(.+)",
    r"what happens if i (?:remove|delete|change|disable|drop)\s+(.+)",
    r"impact of (?:changing|removing|deleting|disabling)\s+(.+)",
    r"blast radius of\s+(.+)",
    r"what depends on\s+(.+)",
    r"what tests?(?: cover| are affected by| break)?\s+(.+)",
    r"(?:remove|delete|change|disable|drop|get rid of)\s+(.+)",
)


def _extract_impact_concept(question: str) -> str:
    q = (question or "").strip().rstrip("?.! ").lower()
    for pat in _IMPACT_CONCEPT_PATTERNS:
        m = re.search(pat, q)
        if m:
            concept = m.group(1).strip(" `'\"")
            concept = re.sub(r"^(the|a|an|our|my)\s+", "", concept).strip()
            return concept
    return ""


def _answer_impact(question: str, node_context: Optional[Dict[str, Any]], packet: str) -> Dict[str, Any]:
    # Candidate seeds, in priority order: an explicit file/module path, then the
    # bare architecture concept text. Each is fed to the impact engine, which runs
    # exact lookup -> semantic concept resolution -> architecture-symbol resolution.
    literal = _resolve_module_path(question, node_context)
    concept = _extract_impact_concept(question)
    seeds: List[str] = []
    for s in (literal, concept):
        if s and s not in seeds:
            seeds.append(s)
    res: Optional[Dict[str, Any]] = None
    for seed in seeds:
        r = change_impact_simulation(seed)
        if not r.get("ok"):
            continue
        if not r.get("mock"):
            res = r
            break
        # Phase 137 — generic concept resolution may land on modules outside the
        # production import graph (TS layouts, extension folders). Still usable.
        if r.get("resolved_modules") or r.get("affected_files"):
            res = r
            break
    if res is None:
        return _copilot_envelope(
            "impact",
            "Name a file, module, or architecture concept to analyze "
            "(for example `core.py`, `websocket support`, or `event bus`).",
            confidence="low",
            suggested_action="Ask: What breaks if I remove the event bus?",
            limitations=["No file, module, or known architecture concept could be resolved."],
            packet=packet,
        )

    target = res.get("target") or ""
    sem = res.get("semantic_label") or ""
    resolved_modules = res.get("resolved_modules") or []
    resolved_symbols = res.get("resolved_symbols") or []
    direct = res.get("direct_impact") or []
    indirect = res.get("indirect_impact") or []
    affected = res.get("affected_files") or []
    subs = res.get("affected_subsystems") or []
    arch_block = res.get("architecture") or {}
    blast = res.get("architectural_blast_radius") or arch_block.get("architectural_blast_radius") or 0
    conf_expl = res.get("confidence_explanation") or arch_block.get("confidence_explanation") or ""

    if sem:
        related = f" + {len(resolved_modules) - 1} related module(s)" if len(resolved_modules) > 1 else ""
        header = f"Removing **{sem}** (resolved to `{target}`{related})"
    else:
        header = f"Changing `{target}`"
    answer = (f"{header} affects {len(direct)} direct + {len(indirect)} transitive importer(s) "
              f"across {len(subs)} subsystem(s).")
    # Append the explanation only when it adds context (runtime/config/semantic),
    # not the generic count restatement.
    if conf_expl and (sem or "runtime" in conf_expl.lower() or "config" in conf_expl.lower()):
        answer += " " + conf_expl

    highlight_ids = [res.get("target_node_id")] + (res.get("affected_node_ids") or [])
    highlight_ids = [item for item in highlight_ids if item]
    return _copilot_envelope(
        "impact",
        answer,
        evidence=(res.get("evidence") or [])[:8],
        files=(affected or resolved_modules)[:20],
        risk_level=str(res.get("risk_level", "unknown")),
        suggested_prompt=str(res.get("recommended_prompt", "")) or _impact_prompt(target, len(direct), subs),
        suggested_action="Run the recommended tests before merging the change.",
        confidence=str(res.get("confidence", "medium")),
        limitations=res.get("limitations") or [],
        packet=packet,
        graph_highlight={
            "kind": "blast_radius",
            "target_node_id": res.get("target_node_id"),
            "target_path": target,
            "node_ids": highlight_ids[:80],
            "affected_node_ids": res.get("affected_node_ids") or [],
        },
        extra={
            "semantic_label": sem,
            "resolved_modules": resolved_modules,
            "resolved_symbols": resolved_symbols,
            "direct_impact": direct,
            "indirect_impact": indirect,
            "architectural_blast_radius": blast,
            "confidence_explanation": conf_expl,
            "target": target,
            "risky_areas": res.get("risky_areas") or arch_block.get("risky_areas") or [],
            "safe_areas": res.get("safe_areas") or arch_block.get("safe_areas") or [],
        },
    )


def _answer_cycles(packet: str) -> Dict[str, Any]:
    graph = _STATE.get("graph") or {}
    cycles = (graph.get("statistics") or {}).get("import_cycles") or []
    if not cycles:
        return _copilot_envelope(
            "cycles",
            "No import cycles were detected in the production dependency graph.",
            evidence=[f"graph_scope={graph.get('graph_scope', '')}"],
            risk_level="low",
            suggested_action="Review top fan-in modules instead.",
            confidence="high",
            packet=packet,
        )
    lines = []
    files: List[str] = []
    for index, cycle in enumerate(cycles[:8], 1):
        members = cycle if isinstance(cycle, list) else cycle.get("members", [])
        shown = [str(item).replace("module:", "") for item in members[:6]]
        lines.append(f"Cycle {index}: {' -> '.join(shown)}")
        for item in members:
            path = str(item).split(":", 1)[-1]
            if path.endswith(".py"):
                files.append(path)
    answer = f"Found {len(cycles)} import cycle(s):\n" + "\n".join(lines)
    return _copilot_envelope(
        "cycles",
        answer,
        evidence=[f"cycle_count={len(cycles)}"],
        files=sorted(set(files))[:12],
        risk_level="medium" if len(cycles) <= 3 else "high",
        suggested_prompt="Help me break these import cycles with the smallest safe refactor plan.",
        suggested_action="Pick one cycle and remove the weakest dependency edge first.",
        confidence="high",
        limitations=["Cycles are computed on resolved import edges only."],
        packet=packet,
    )


def _answer_dependency(question: str, node_context: Optional[Dict[str, Any]], packet: str) -> Dict[str, Any]:
    target = _resolve_module_path(question, node_context)
    if not target:
        return _copilot_envelope(
            "dependency",
            "Specify a module path to inspect importers and imports.",
            confidence="low",
            suggested_action="Ask: Who imports builder_core/ask.py?",
            packet=packet,
        )
    node, importers, imports = _module_graph_neighbors(target)
    if node is None:
        return _copilot_envelope(
            "dependency",
            f"`{target}` was not found in the production module graph.",
            files=[target],
            confidence="low",
            limitations=["Target not indexed as a production module."],
            packet=packet,
        )
    answer = (
        f"Module `{node.get('path')}` is imported by {len(importers)} module(s) and imports "
        f"{len(imports)} resolved module(s)."
    )
    if importers:
        answer += "\nImporters: " + ", ".join(importers[:12])
    if imports:
        answer += "\nImports: " + ", ".join(imports[:12])
    return _copilot_envelope(
        "dependency",
        answer,
        evidence=[
            f"fan_in={len(importers)}",
            f"fan_out={len(imports)}",
        ],
        files=([node.get("path", "")] + importers + imports)[:20],
        risk_level="high" if len(importers) >= 25 else "medium" if len(importers) >= 6 else "low",
        suggested_prompt=f"Explain how `{node.get('path')}` is used across the repository based on these importers and imports.",
        suggested_action="Inspect the top importer modules before changing this file.",
        confidence="high",
        limitations=["Unresolved/dynamic imports are not included."],
        packet=packet,
    )


def _answer_context_export(question: str, packet: str) -> Dict[str, Any]:
    targets = _copilot_copy_targets(packet)
    primary = "claude"
    q = question.lower()
    if "codex" in q:
        primary = "codex"
    elif "cursor" in q:
        primary = "cursor"
    tokens = estimate_tokens(targets[primary])
    answer = (
        f"Generated a {packet} JARVIS context packet (~{tokens} tokens) for {primary.title()}. "
        "Use the copy buttons to paste into your assistant."
    )
    return _copilot_envelope(
        "context_export",
        answer,
        evidence=[f"packet={packet}", f"estimated_tokens={tokens}"],
        risk_level="low",
        suggested_prompt=targets[primary],
        suggested_action=f"Copy the {primary.title()} prompt and attach your follow-up question.",
        confidence="high",
        limitations=["Context is deterministic from the scan; it is not a live LLM answer."],
        packet=packet,
    )


def _answer_unknown(question: str, packet: str) -> Dict[str, Any]:
    scan = _STATE.get("scan") or {}
    suggestions = _recommended_questions(scan)
    answer = (
        "I could not map that question to a grounded analysis mode. "
        "Try one of the suggested questions below."
    )
    return _copilot_envelope(
        "unknown",
        answer,
        evidence=[f"question={question[:120]}"],
        risk_level="unknown",
        suggested_prompt=suggestions[0] if suggestions else "What does this repository do?",
        suggested_action="Pick a suggested question or name a specific file path.",
        confidence="low",
        limitations=["Question did not match deterministic routing rules."],
        packet=packet,
    )


def copilot_ask(
    question: str,
    target: str = "none",
    packet: str = "compact",
    *,
    node_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Answer repository questions using deterministic Builder Core scan outputs."""
    if not _STATE.get("scan"):
        return {
            "ok": False,
            "error": "No repository scanned yet.",
            "mode": "unknown",
            "answer": "",
            "evidence": [],
            "files": [],
            "risk_level": "unknown",
            "suggested_prompt": "",
            "suggested_action": "",
            "copy_targets": {"claude": "", "codex": "", "cursor": ""},
            "confidence": "low",
            "limitations": ["Scan a repository first."],
        }
    packet = (packet or "compact").lower()
    if packet not in ("compact", "verbose"):
        packet = "compact"
    _ = (target or "none").lower()  # reserved for future primary copy target preference

    mode = classify_copilot_question(question)
    if node_context and mode == "unknown":
        q = question.lower()
        if "impact" in q or "break" in q or "change" in q:
            mode = "impact"
        elif "import" in q:
            mode = "dependency"
        elif "explain" in q or "module" in q:
            mode = "repository_understanding"
        elif "prompt" in q or "claude" in q:
            mode = "context_export"

    track_analytics_event("copilot_question", mode=mode)

    if mode == "repository_understanding":
        return _answer_repository_understanding(question, packet)
    if mode == "risk":
        return _answer_risk(packet)
    if mode == "impact":
        return _answer_impact(question, node_context, packet)
    if mode == "cycles":
        return _answer_cycles(packet)
    if mode == "dependency":
        return _answer_dependency(question, node_context, packet)
    if mode == "context_export":
        return _answer_context_export(question, packet)
    return _answer_unknown(question, packet)
