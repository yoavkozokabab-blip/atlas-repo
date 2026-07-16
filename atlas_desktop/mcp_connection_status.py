"""Runtime MCP connection status shared between stdio MCP processes and the UI.

The desktop UI runs in the local HTTP process, while each MCP client launches an
Atlas ``--mcp`` stdio process. Configuration files can prove only that setup was
written; they cannot prove an active client session. This module records only
minimal, non-sensitive runtime session facts in the Atlas data directory so the
desktop process can answer "which clients are connected right now?"
"""

from __future__ import annotations

import json
import os
import secrets
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from .data_paths import desktop_data_dir
from . import runtime_startup

CLIENT_KEYS = ("cursor", "claude", "codex")
CLIENT_LABELS = {
    "cursor": "Cursor",
    "claude": "Claude Code",
    "codex": "Codex",
    "other": "Other MCP client",
}
STALE_TIMEOUT_SECONDS = 60.0


def _now_iso(now: Optional[float] = None) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() if now is None else now))


def _now_ts(now: Optional[float] = None) -> float:
    return float(time.time() if now is None else now)


def _root(data_dir: Optional[str] = None) -> Path:
    root = Path(data_dir or desktop_data_dir()) / "mcp_connections"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _session_path(session_id: str, data_dir: Optional[str] = None) -> Path:
    safe = "".join(ch for ch in str(session_id or "") if ch.isalnum() or ch in {"-", "_"})
    if not safe:
        safe = secrets.token_urlsafe(18).replace("-", "_")
    return _root(data_dir) / f"{safe}.json"


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def _write_record(record: Dict[str, Any], data_dir: Optional[str] = None) -> None:
    path = _session_path(str(record.get("session_id") or ""), data_dir)
    tmp = path.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(record, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, path)


def _current_desktop_instance_id(data_dir: Optional[str] = None) -> str:
    descriptor = runtime_startup.read_runtime_descriptor(data_dir=data_dir)
    if not descriptor:
        return ""
    return str(descriptor.get("instance_id") or "")


def normalize_client(client_name: str) -> str:
    """Return a deterministic client key from MCP initialize clientInfo.name."""
    normalized = " ".join(str(client_name or "").strip().lower().replace("_", " ").replace("-", " ").split())
    if not normalized:
        return "other"
    if "cursor" in normalized:
        return "cursor"
    if "codex" in normalized:
        return "codex"
    if "claude" in normalized:
        return "claude"
    return "other"


def record_initialize(
    client_info: Optional[Dict[str, Any]],
    *,
    session_id: Optional[str] = None,
    data_dir: Optional[str] = None,
    pid: Optional[int] = None,
    now: Optional[float] = None,
) -> str:
    """Record an MCP initialize event and return the session id."""
    info = client_info if isinstance(client_info, dict) else {}
    raw_name = str(info.get("name") or "").strip()
    raw_version = str(info.get("version") or "").strip()
    client_type = normalize_client(raw_name)
    sid = session_id or secrets.token_urlsafe(24)
    ts = _now_ts(now)
    record = {
        "schema": 1,
        "session_id": sid,
        "client_type": client_type,
        "client_name": raw_name or CLIENT_LABELS["other"],
        "client_version": raw_version,
        "connected": True,
        "connected_at": _now_iso(ts),
        "connected_at_ts": ts,
        "last_seen_at": _now_iso(ts),
        "last_seen_at_ts": ts,
        "transport_seen_at": _now_iso(ts),
        "transport_seen_at_ts": ts,
        "pid": int(pid if pid is not None else os.getpid()),
        "desktop_instance_id": _current_desktop_instance_id(data_dir),
        "disconnect_reason": "",
    }
    _write_record(record, data_dir)
    return sid


def touch_session(
    session_id: str,
    *,
    data_dir: Optional[str] = None,
    now: Optional[float] = None,
    transport_only: bool = False,
) -> None:
    path = _session_path(session_id, data_dir)
    record = _read_json(path)
    if not record or not record.get("connected"):
        return
    ts = _now_ts(now)
    if not transport_only:
        record["last_seen_at"] = _now_iso(ts)
        record["last_seen_at_ts"] = ts
    record["transport_seen_at"] = _now_iso(ts)
    record["transport_seen_at_ts"] = ts
    _write_record(record, data_dir)


def disconnect_session(
    session_id: str,
    reason: str,
    *,
    data_dir: Optional[str] = None,
    now: Optional[float] = None,
) -> None:
    path = _session_path(session_id, data_dir)
    record = _read_json(path)
    if not record:
        return
    ts = _now_ts(now)
    record["connected"] = False
    record["disconnected_at"] = _now_iso(ts)
    record["disconnected_at_ts"] = ts
    record["last_seen_at"] = record.get("last_seen_at") or _now_iso(ts)
    record["last_seen_at_ts"] = float(record.get("last_seen_at_ts") or ts)
    record["disconnect_reason"] = str(reason or "disconnected")[:80]
    _write_record(record, data_dir)


def _iter_records(data_dir: Optional[str] = None) -> Iterable[Dict[str, Any]]:
    try:
        paths = sorted(_root(data_dir).glob("*.json"))
    except OSError:
        return []
    records = []
    for path in paths:
        record = _read_json(path)
        if isinstance(record, dict):
            records.append(record)
    return records


def _mark_stale(record: Dict[str, Any], *, data_dir: Optional[str], now: float) -> Dict[str, Any]:
    return _mark_disconnected(record, reason="stale_timeout", data_dir=data_dir, now=now)


def _mark_disconnected(
    record: Dict[str, Any],
    *,
    reason: str,
    data_dir: Optional[str],
    now: float,
) -> Dict[str, Any]:
    record = dict(record)
    record["connected"] = False
    record["disconnected_at"] = _now_iso(now)
    record["disconnected_at_ts"] = now
    record["disconnect_reason"] = str(reason or "disconnected")[:80]
    try:
        _write_record(record, data_dir)
    except OSError:
        pass
    return record


def _process_is_alive(pid: Any) -> bool:
    """Best-effort local process liveness check for MCP child processes."""
    try:
        value = int(pid)
    except (TypeError, ValueError):
        return True
    if value <= 0:
        return False
    if value == os.getpid():
        return True
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            process_query_limited_information = 0x1000
            still_active = 259
            handle = kernel32.OpenProcess(process_query_limited_information, False, value)
            if not handle:
                return False
            try:
                exit_code = wintypes.DWORD()
                if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    return False
                return int(exit_code.value) == still_active
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return True
    try:
        os.kill(value, 0)
        return True
    except OSError:
        return False


def connections_payload(
    *,
    data_dir: Optional[str] = None,
    now: Optional[float] = None,
    stale_timeout_seconds: float = STALE_TIMEOUT_SECONDS,
    current_instance_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Return safe, local-only MCP connection status for the desktop UI."""
    ts = _now_ts(now)
    instance_id = current_instance_id if current_instance_id is not None else _current_desktop_instance_id(data_dir)
    buckets: Dict[str, list[Dict[str, Any]]] = {key: [] for key in CLIENT_KEYS}
    disconnected_reasons: Dict[str, str] = {}
    other_connected = 0

    for record in _iter_records(data_dir):
        client_type = str(record.get("client_type") or "other")
        last_seen_ts = float(record.get("transport_seen_at_ts") or record.get("last_seen_at_ts") or 0)
        same_instance = str(record.get("desktop_instance_id") or "") == str(instance_id or "")
        active = bool(record.get("connected")) and same_instance
        if active and not _process_is_alive(record.get("pid")):
            record = _mark_disconnected(record, reason="process_exited", data_dir=data_dir, now=ts)
            active = False
        if active and stale_timeout_seconds > 0 and (ts - last_seen_ts) > stale_timeout_seconds:
            record = _mark_stale(record, data_dir=data_dir, now=ts)
            active = False
        if active and client_type in buckets:
            buckets[client_type].append(record)
        elif active:
            other_connected += 1
        elif client_type in disconnected_reasons and not disconnected_reasons[client_type]:
            disconnected_reasons[client_type] = str(record.get("disconnect_reason") or "")
        elif client_type in CLIENT_KEYS:
            disconnected_reasons.setdefault(client_type, str(record.get("disconnect_reason") or ""))

    clients: Dict[str, Dict[str, Any]] = {}
    for key in CLIENT_KEYS:
      active_records = sorted(
          buckets[key],
          key=lambda item: float(item.get("last_seen_at_ts") or 0),
          reverse=True,
      )
      if not active_records:
          clients[key] = {"connected": False}
          reason = disconnected_reasons.get(key) or ""
          if reason:
              clients[key]["disconnect_reason"] = reason
          continue
      latest = active_records[0]
      clients[key] = {
          "connected": True,
          "client_name": str(latest.get("client_name") or CLIENT_LABELS[key]),
          "client_version": str(latest.get("client_version") or ""),
          "connected_at": min(str(item.get("connected_at") or "") for item in active_records if item.get("connected_at")),
          "last_seen_at": str(latest.get("last_seen_at") or ""),
          "session_count": len(active_records),
      }

    return {
        "ok": True,
        "clients": clients,
        "other_clients_connected": other_connected,
        "stale_timeout_seconds": int(stale_timeout_seconds),
        "generated_at": _now_iso(ts),
    }


def reset_for_tests(*, data_dir: Optional[str] = None) -> None:
    try:
        for path in _root(data_dir).glob("*.json"):
            path.unlink(missing_ok=True)
    except OSError:
        pass
