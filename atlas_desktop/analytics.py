"""Local-only product analytics for Atlas Desktop (no cloud, no accounts)."""

from __future__ import annotations

import inspect
import json
import logging
import os
import threading
import time
import traceback
from typing import Any, Dict, List

_LOGGER = logging.getLogger("atlas.analytics")
_TELEMETRY_WARNING = "Telemetry unavailable. Repository analysis unaffected."
_WRITE_LOCK = threading.Lock()
_STATUS_LOCK = threading.Lock()
_ANALYTICS_STATUS = "ok"
_LAST_ERROR = ""

# Phase 116E investigation diagnostics (opt-in: ATLAS_ANALYTICS_DIAG=1).
_DIAG_LOGGER = logging.getLogger("atlas.analytics.write_diag")
_PHASE116E_DIAG = os.environ.get("ATLAS_ANALYTICS_DIAG", "0").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def _ensure_diag_handler() -> None:
    if not _PHASE116E_DIAG or _DIAG_LOGGER.handlers:
        return
    os.makedirs(analytics_data_dir(), exist_ok=True)
    _DIAG_LOGGER.setLevel(logging.DEBUG)
    handler = logging.FileHandler(
        os.path.join(analytics_data_dir(), "analytics_write_diag.log"),
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    _DIAG_LOGGER.addHandler(handler)
    _DIAG_LOGGER.propagate = False


def _log_write_diag(action: str, path: str, mode: str, *, error: str = "") -> None:
    if not _PHASE116E_DIAG:
        return
    _ensure_diag_handler()
    frame = inspect.stack()[2]
    caller = f"{frame.filename}:{frame.function}:{frame.lineno}"
    pid = os.getpid()
    tid = threading.get_ident()
    line = (
        f"action={action} pid={pid} tid={tid} caller={caller} "
        f"mode={mode!r} path={path!r}"
    )
    if error:
        line += f" error={error!r}\n{traceback.format_exc()}"
    _DIAG_LOGGER.info(line)


def _set_degraded(exc: BaseException) -> None:
    global _ANALYTICS_STATUS, _LAST_ERROR
    with _STATUS_LOCK:
        _ANALYTICS_STATUS = "degraded"
        _LAST_ERROR = type(exc).__name__


def _set_ok() -> None:
    global _ANALYTICS_STATUS, _LAST_ERROR
    with _STATUS_LOCK:
        _ANALYTICS_STATUS = "ok"
        _LAST_ERROR = ""


def status_snapshot() -> Dict[str, Any]:
    with _STATUS_LOCK:
        degraded = _ANALYTICS_STATUS == "degraded"
        return {
            "analytics_status": _ANALYTICS_STATUS,
            "telemetry_warning": _TELEMETRY_WARNING if degraded else "",
            "telemetry_error": _LAST_ERROR if degraded else "",
        }


def analytics_data_dir() -> str:
    from .data_paths import desktop_data_dir

    return desktop_data_dir()


def analytics_file_path() -> str:
    return os.path.join(analytics_data_dir(), "analytics.jsonl")


def track_event(event: str, **properties: Any) -> Dict[str, Any]:
    """Append one analytics row; never raises OSError/IOError to callers."""
    name = (event or "").strip()
    if not name:
        return {"ok": False, "error": "Event name required.", "analytics_status": _ANALYTICS_STATUS}
    row = {
        "ts": time.time(),
        "event": name,
        **{k: v for k, v in properties.items() if v is not None},
    }
    path = analytics_file_path()
    _log_write_diag("open_attempt", path, "a")
    try:
        with _WRITE_LOCK:
            os.makedirs(analytics_data_dir(), exist_ok=True)
            with open(path, "a", encoding="utf-8") as fh:
                _log_write_diag("open_ok", path, "a")
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                _log_write_diag("write_ok", path, "a")
    except OSError as exc:
        _log_write_diag("write_failed", path, "a", error=f"{type(exc).__name__}: {exc}")
        _set_degraded(exc)
        _LOGGER.warning(
            "analytics write failed for event=%s path=%s: %s",
            name,
            path,
            exc,
            exc_info=True,
        )
        return {
            "ok": False,
            "event": name,
            "path": path,
            "analytics_status": "degraded",
            "telemetry_warning": _TELEMETRY_WARNING,
            "error": "analytics_unavailable",
            "error_type": type(exc).__name__,
        }
    _set_ok()
    return {"ok": True, "event": name, "path": path, "analytics_status": "ok"}


def _read_events() -> List[Dict[str, Any]]:
    path = analytics_file_path()
    if not os.path.isfile(path):
        return []
    rows: List[Dict[str, Any]] = []
    _log_write_diag("read_open_attempt", path, "r")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            _log_write_diag("read_open_ok", path, "r")
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError as exc:
        _log_write_diag("read_failed", path, "r", error=f"{type(exc).__name__}: {exc}")
        _set_degraded(exc)
        _LOGGER.warning("analytics read failed path=%s: %s", path, exc, exc_info=True)
        return []
    return rows


def analytics_summary() -> Dict[str, Any]:
    snap = status_snapshot()
    events = _read_events()
    counts: Dict[str, int] = {}
    for row in events:
        key = str(row.get("event", "unknown"))
        counts[key] = counts.get(key, 0) + 1
    return {
        "ok": True,
        "local_only": True,
        "path": analytics_file_path(),
        "total_events": len(events),
        "counts": counts,
        "scans_completed": counts.get("scan_completed", 0),
        "graph_opens": counts.get("graph_opened", 0),
        "copilot_questions": counts.get("copilot_question", 0),
        "exports": counts.get("export_created", 0) + counts.get("bundle_exported", 0),
        **snap,
    }


def reset_analytics_for_tests() -> None:
    global _ANALYTICS_STATUS, _LAST_ERROR
    path = analytics_file_path()
    if os.path.isfile(path):
        os.remove(path)
    with _STATUS_LOCK:
        _ANALYTICS_STATUS = "ok"
        _LAST_ERROR = ""
