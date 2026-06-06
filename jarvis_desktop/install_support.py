"""Phase 143 — one-click install support: startup checks, recovery, support bundle."""

from __future__ import annotations

import base64
import io
import json
import os
import re
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
    from .data_paths import desktop_data_dir

    return desktop_data_dir()


def data_dir_diagnostics() -> Dict[str, Any]:
    from .data_paths import desktop_data_dir_info

    return desktop_data_dir_info()


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
        "hint": None if ok else "Reinstall Atlas or run from the folder that contains jarvis_desktop. Do not pip install the monorepo requirements.txt.",
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
        "hint": None if ok else (
            "Atlas could not write app data. Close other Atlas instances, check disk space, "
            "or set JARVIS_DESKTOP_DATA to a writable folder."
        ),
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
        "data_dir_info": data_dir_diagnostics(),
    }


def _frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _selftest_executable() -> Dict[str, Any]:
    """Verify the Atlas application binary (frozen) or launcher (source) exists."""
    if _frozen():
        exe = sys.executable or ""
        ok = bool(exe) and os.path.isfile(exe)
        name = os.path.basename(exe) if exe else "(unknown)"
        return {
            "id": "executable",
            "label": "Atlas application",
            "ok": ok,
            "detail": f"{name}" if ok else "Atlas.exe not found",
            "hint": None if ok else "Reinstall Atlas — the application binary is missing.",
        }
    launcher = _REPO_ROOT / "run_atlas.py"
    ok = launcher.is_file()
    return {
        "id": "executable",
        "label": "Atlas launcher (source mode)",
        "ok": ok,
        "detail": "run_atlas.py present" if ok else "run_atlas.py missing",
        "hint": None if ok else "Run Atlas from the folder that contains run_atlas.py.",
    }


def _shortcut_locations() -> List[str]:
    """Best-effort Windows shortcut paths created by the installer."""
    paths: List[str] = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        paths.append(os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Atlas"))
    userprofile = os.environ.get("USERPROFILE")
    if userprofile:
        paths.append(os.path.join(userprofile, "Desktop", "Atlas.lnk"))
        paths.append(os.path.join(userprofile, "Desktop", "Launch Atlas.lnk"))
    public = os.environ.get("PUBLIC")
    if public:
        paths.append(os.path.join(public, "Desktop", "Atlas.lnk"))
    return paths


def _selftest_shortcuts() -> Dict[str, Any]:
    """Check that install shortcuts exist (Windows only; optional / non-fatal)."""
    if sys.platform != "win32":
        return {
            "id": "shortcuts",
            "label": "Shortcuts",
            "ok": True,
            "optional": True,
            "detail": "n/a on this platform",
            "hint": None,
        }
    found = [p for p in _shortcut_locations() if os.path.exists(p)]
    ok = bool(found)
    return {
        "id": "shortcuts",
        "label": "Start menu / desktop shortcuts",
        "ok": ok,
        # In source mode (not installed) shortcuts won't exist — treat as optional
        # so the self-test stays green for developers while still reporting status.
        "optional": not _frozen(),
        "detail": (found[0] if ok else "no Atlas shortcuts found"),
        "hint": None if ok else (
            "Shortcuts were not created. You can still launch Atlas from its install "
            "folder, or re-run the installer to recreate them."
        ),
    }


def _selftest_browser() -> Dict[str, Any]:
    """Verify Atlas can open a browser to show the UI (best-effort, non-fatal)."""
    detail = ""
    ok = True
    try:
        import webbrowser

        controller = webbrowser.get()
        detail = f"default browser available ({getattr(controller, 'name', 'system')})"
    except Exception as exc:  # no registered browser
        ok = False
        detail = f"no default browser ({type(exc).__name__})"
    return {
        "id": "browser",
        "label": "Browser auto-open",
        "ok": ok,
        "optional": True,
        "detail": detail,
        "hint": None if ok else (
            "Atlas could not detect a default browser. Open http://127.0.0.1:8777/ "
            "manually in any browser."
        ),
    }


def installer_self_test(*, check_browser: bool = True) -> Dict[str, Any]:
    """Phase 157 — post-install self-test.

    Verifies that the Atlas binary/launcher exists, required assets are present,
    install shortcuts exist (Windows), and a browser can be opened. Optional
    checks (shortcuts in source mode, browser) never fail the overall result.
    """
    checks: List[Dict[str, Any]] = [
        _selftest_executable(),
        _check_directories(),
        _selftest_shortcuts(),
    ]
    if check_browser:
        checks.append(_selftest_browser())
    critical = [c for c in checks if not c.get("ok") and not c.get("optional")]
    warnings = [c for c in checks if not c.get("ok") and c.get("optional")]
    return {
        "ok": True,
        "ready": len(critical) == 0,
        "frozen": _frozen(),
        "checks": checks,
        "critical_failures": [c["label"] for c in critical],
        "warnings": [c["label"] for c in warnings],
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
            "data_dir_info": data_dir_diagnostics(),
            "launcher_log": launcher_log_path(),
        },
        "trust_integrity": __import__("jarvis_desktop.trust_integrity", fromlist=["trust_integrity_diagnostics"]).trust_integrity_diagnostics(
            __import__("jarvis_desktop.api", fromlist=["_STATE"])._STATE
        ),
    }


def clear_scan_cache() -> Dict[str, Any]:
    from . import api

    n = len(api._STATE.get("scan_cache") or {})
    api._STATE["scan_cache"] = {}
    append_launcher_log("clear_scan_cache")
    return {"ok": True, "cleared_entries": n, "message": "Scan cache cleared."}


def rebuild_index(*, rescan: bool = True) -> Dict[str, Any]:
    from . import api
    from . import trust_integrity as _ti

    with _ti.state_guard():
        return _rebuild_index_locked(rescan=rescan)


def _rebuild_index_locked(*, rescan: bool = True) -> Dict[str, Any]:
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
        # Phase 172 mitigation A2: clear stale session/memory so poisoned state can't survive
        api._STATE["session_export"] = None
        api._STATE["repository_memory"] = None
        api._STATE.pop("_current_memory", None)
        api._STATE.pop("memory_persistence_status", None)
        api._STATE.pop("memory_persistence_error", None)
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


_SECRET_KEY_NAMES = (
    "api_key",
    "apikey",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "bearer",
    "password",
    "secret",
    "private_key",
    "client_secret",
)


def _redact_secret_values(text: str) -> str:
    """Redact common key=value, JSON, header, and token-prefix secrets."""
    if not text:
        return text
    out = text
    for key in _SECRET_KEY_NAMES:
        out = re.sub(
            rf"(?i)(\b{re.escape(key)}\s*[=:]\s*)([\"']?)([^\"'\s\\]+)",
            r"\1\2[REDACTED]",
            out,
        )
        out = re.sub(
            rf'(?i)"{re.escape(key)}"\s*:\s*"([^"]*)"',
            rf'"{key}": "[REDACTED]"',
            out,
        )
        out = re.sub(
            rf"(?i)('{re.escape(key)}'\s*:\s*)'([^']*)'",
            r"\1'[REDACTED]'",
            out,
        )
    out = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._\-]+", "Bearer [REDACTED]", out)
    out = re.sub(r"(?i)\bAuthorization:\s*[^\s\"']+", "Authorization: [REDACTED]", out)
    out = re.sub(r"sk-ant-[A-Za-z0-9_\-]+", "[REDACTED]", out)
    out = re.sub(r"\bsk-[A-Za-z0-9_\-]{8,}", "[REDACTED]", out)
    out = re.sub(r"ghp_[A-Za-z0-9]+", "[REDACTED]", out)
    out = re.sub(r"github_pat_[A-Za-z0-9_]+", "[REDACTED]", out)
    out = re.sub(r"xoxb-[A-Za-z0-9\-]+", "[REDACTED]", out)
    out = re.sub(r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]*", "[REDACTED]", out)
    return out


def _redact_support_text(text: str) -> str:
    """Beta P0-04 / 174D — strip paths and secrets from support bundle text."""
    if not text:
        return text
    out = re.sub(r"[A-Za-z]:\\(?:[^\"\\\s]|\\.)+", "[path-redacted]", text)
    out = re.sub(r"/(?:home|Users|var)/(?:[^\"\\\s]|\\.)+", "[path-redacted]", out)
    out = re.sub(r"SECRET_[A-Z0-9_]+", "[secret-redacted]", out)
    return _redact_secret_values(out)


def _sanitize_support_payload(payload: Any) -> Any:
    """Deep-copy and redact a JSON-serializable support bundle section."""
    try:
        blob = json.dumps(payload, indent=2, default=str)
    except TypeError:
        blob = json.dumps(str(payload))
    return json.loads(_redact_support_text(blob))


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
    logs = {name: _redact_support_text(text) for name, text in collect_error_logs().items()}
    diag = _sanitize_support_payload(env.get("diagnostics") or {})
    env_blob = _sanitize_support_payload(env.get("environment") or {})
    scan_meta = _sanitize_support_payload(scan_meta)
    startup_blob = _sanitize_support_payload(env.get("startup") or {})
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
        zf.writestr("diagnostics.json", json.dumps(diag, indent=2, default=str))
        zf.writestr("environment.json", json.dumps(env_blob, indent=2, default=str))
        zf.writestr("scan_metadata.json", json.dumps(scan_meta, indent=2, default=str))
        zf.writestr("startup_checks.json", json.dumps(startup_blob, indent=2, default=str))
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
