"""Phase 143 — one-click install support: startup checks, recovery, support bundle."""

from __future__ import annotations

import base64
import io
import json
import os
import sys
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Optional imports checked at runtime
_PKG_ROOT = Path(__file__).resolve().parent
_REPO_ROOT = _PKG_ROOT.parent


def repo_root() -> Path:
    return _REPO_ROOT


def static_dir() -> Path:
    return _PKG_ROOT / "static"


def data_dir() -> str:
    override = os.environ.get("JARVIS_DESKTOP_DATA", "").strip()
    if override:
        return os.path.abspath(override)
    return os.path.join(os.path.expanduser("~"), ".jarvis_desktop")


def launcher_log_path() -> str:
    return os.path.join(data_dir(), "launcher.log")


def _check_python() -> Dict[str, Any]:
    ver = sys.version_info
    ok = ver.major >= 3 and (ver.major > 3 or ver.minor >= 10)
    return {
        "id": "python",
        "label": "Python",
        "ok": ok,
        "detail": f"{ver.major}.{ver.minor}.{ver.micro}",
        "hint": None if ok else "Install Python 3.10+ from python.org and ensure the py launcher works.",
    }


def _check_imports() -> Dict[str, Any]:
    missing: List[str] = []
    for mod in ("jarvis_desktop", "jarvis_desktop.api", "jarvis_desktop.server"):
        try:
            __import__(mod)
        except Exception as exc:
            missing.append(f"{mod}: {type(exc).__name__}")
    ok = not missing
    return {
        "id": "dependencies",
        "label": "Atlas modules",
        "ok": ok,
        "detail": "ready" if ok else "; ".join(missing[:3]),
        "hint": None if ok else "Reinstall Atlas or run from the folder that contains jarvis_desktop.",
    }


def _check_directories() -> Dict[str, Any]:
    required = [
        ("static", static_dir()),
        ("demo", _PKG_ROOT / "demo"),
        ("data (writable)", Path(data_dir())),
    ]
    problems: List[str] = []
    for label, path in required:
        p = Path(path)
        if label.startswith("data"):
            try:
                p.mkdir(parents=True, exist_ok=True)
                test = p / ".write_test"
                test.write_text("ok", encoding="utf-8")
                test.unlink(missing_ok=True)
            except OSError as exc:
                problems.append(f"{label}: {exc}")
        elif not p.is_dir():
            problems.append(f"{label} missing: {p}")
    ok = not problems
    return {
        "id": "directories",
        "label": "Required directories",
        "ok": ok,
        "detail": "present" if ok else "; ".join(problems),
        "hint": None if ok else "Repair the installation or reinstall from Atlas_Setup.exe.",
    }


def _optional_dependencies() -> Dict[str, Any]:
    optional = []
    for name in ("fastapi", "uvicorn"):
        try:
            __import__(name)
            optional.append(f"{name}: installed")
        except ImportError:
            optional.append(f"{name}: not installed (optional)")
    return {
        "id": "optional",
        "label": "Optional packages",
        "ok": True,
        "detail": ", ".join(optional),
        "hint": "FastAPI is optional; Atlas uses the built-in server by default.",
    }


def startup_checks() -> Dict[str, Any]:
    checks = [_check_python(), _check_imports(), _check_directories(), _optional_dependencies()]
    critical = [c for c in checks if c["id"] != "optional" and not c["ok"]]
    return {
        "ok": True,
        "ready": len(critical) == 0,
        "checks": checks,
        "repo_root": str(_REPO_ROOT),
        "data_dir": data_dir(),
    }


def append_launcher_log(message: str) -> None:
    try:
        os.makedirs(data_dir(), exist_ok=True)
        line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {message}\n"
        with open(launcher_log_path(), "a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError:
        pass


def environment_status() -> Dict[str, Any]:
    from . import api

    startup = startup_checks()
    health: Dict[str, Any] = {"ok": False}
    try:
        health = api.beta_system_health()
    except Exception as exc:
        health = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    diag: Dict[str, Any] = {}
    try:
        diag = api.beta_diagnostics()
    except Exception as exc:
        diag = {"ok": False, "error": str(exc)}
    return {
        "ok": True,
        "version": api.PRODUCT_VERSION,
        "startup": startup,
        "scan_health": health,
        "diagnostics": diag,
        "environment": {
            "platform": sys.platform,
            "executable": sys.executable,
            "cwd": os.getcwd(),
            "data_dir": data_dir(),
            "launcher_log": launcher_log_path(),
        },
    }


def clear_scan_cache() -> Dict[str, Any]:
    from . import api

    n = len(api._STATE.get("scan_cache") or {})
    api._STATE["scan_cache"] = {}
    append_launcher_log("clear_scan_cache")
    return {"ok": True, "cleared_entries": n, "message": "Scan cache cleared."}


def rebuild_index(*, rescan: bool = True) -> Dict[str, Any]:
    from . import api

    path = api._STATE.get("path")
    scope = api._STATE.get("last_scope") or {"mode": "entire_repo"}
    demo = bool(api._STATE.get("demo_mode"))
    pack = (api._STATE.get("scan") or {}).get("demo_pack", "small")
    clear_scan_cache()
    api._STATE.update(
        {
            "scan": None,
            "graph": None,
            "index": None,
            "risks": None,
            "evidence_store": None,
            "scan_perf": None,
            "scan_perf_live": None,
            "full_graph_pending": False,
        }
    )
    append_launcher_log("rebuild_index")
    if not rescan:
        return {"ok": True, "rescanned": False, "message": "In-memory index cleared. Scan a repository to rebuild."}
    if demo:
        result = api.load_demo_mode(str(pack))
        return {"ok": result.get("ok", False), "rescanned": True, "demo_mode": True, "scan": result}
    if path:
        result = api.scan_repository(path, scope)
        return {
            "ok": result.get("ok", False),
            "rescanned": True,
            "path": path,
            "scan": {k: result.get(k) for k in ("module_count", "file_count", "error", "code")},
        }
    return {"ok": True, "rescanned": False, "message": "Index cleared. No repository path to rescan."}


def _tail_file(path: str, max_bytes: int = 48_000) -> str:
    if not path or not os.path.isfile(path):
        return ""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as fh:
            if size > max_bytes:
                fh.seek(size - max_bytes)
            data = fh.read().decode("utf-8", errors="replace")
        return data
    except OSError:
        return ""


def collect_error_logs() -> Dict[str, str]:
    logs: Dict[str, str] = {}
    base = data_dir()
    for name in ("launcher.log", "analytics.jsonl", "analytics_write_diag.log"):
        path = os.path.join(base, name)
        text = _tail_file(path)
        if text:
            logs[name] = text
    return logs


def export_support_bundle() -> Dict[str, Any]:
    from . import api

    env = environment_status()
    scan_meta: Dict[str, Any] = {}
    if env.get("diagnostics", {}).get("ok"):
        scan_meta = {
            "scan_statistics": env["diagnostics"].get("scan_statistics"),
            "repository": env["diagnostics"].get("repository"),
            "evidence_coverage": env["diagnostics"].get("evidence_coverage"),
        }
    logs = collect_error_logs()
    manifest = {
        "product": "ATLAS",
        "bundle": "atlas_support_bundle",
        "version": api.PRODUCT_VERSION,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "note": "No source code included — diagnostics and logs only.",
        "files": [
            "manifest.json",
            "version.txt",
            "diagnostics.json",
            "environment.json",
            "scan_metadata.json",
            "startup_checks.json",
        ]
        + [f"logs/{k}" for k in logs],
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
        zf.writestr("version.txt", api.PRODUCT_VERSION + "\n")
        zf.writestr("diagnostics.json", json.dumps(env.get("diagnostics") or {}, indent=2, default=str))
        zf.writestr("environment.json", json.dumps(env.get("environment") or {}, indent=2, default=str))
        zf.writestr("scan_metadata.json", json.dumps(scan_meta, indent=2, default=str))
        zf.writestr("startup_checks.json", json.dumps(env.get("startup") or {}, indent=2, default=str))
        for name, text in logs.items():
            zf.writestr(f"logs/{name}", text)
        if not logs:
            zf.writestr("logs/README.txt", "No error logs captured yet.\n")
    payload = buffer.getvalue()
    stamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"atlas_support_bundle_{stamp}.zip"
    api.track_analytics_event("support_bundle_exported", bytes=len(payload))
    return {
        "ok": True,
        "filename": filename,
        "size_bytes": len(payload),
        "content_base64": base64.b64encode(payload).decode("ascii"),
    }
