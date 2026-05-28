"""Dashboard health probing with startup grace and retries (Phase 51)."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import DATA_DIR, TRADING_DASHBOARD_URL

DASHBOARD_HEALTH_PATH = DATA_DIR / "dashboard_health.json"
GRACE_SECONDS = int(os.getenv("DASHBOARD_STARTUP_GRACE_SECONDS", "20"))
PROBE_RETRIES = int(os.getenv("DASHBOARD_HEALTH_PROBE_RETRIES", "4"))
PROBE_DELAY_SECONDS = float(os.getenv("DASHBOARD_HEALTH_PROBE_DELAY_SECONDS", "2.0"))
STABILIZATION_SECONDS = int(os.getenv("DASHBOARD_HEALTH_STABILIZATION_SECONDS", "5"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> dict[str, Any]:
    if not DASHBOARD_HEALTH_PATH.exists():
        return {}
    try:
        data = json.loads(DASHBOARD_HEALTH_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save(data: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DASHBOARD_HEALTH_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")


def mark_dashboard_open_requested() -> None:
    data = _load()
    data["last_open_requested_at"] = _now_iso()
    data["last_open_monotonic"] = time.monotonic()
    _save(data)


def _probe_once(url: str, *, timeout: float = 3.0) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            if 200 <= resp.status < 400:
                return True, f"HTTP {resp.status}"
            return False, f"HTTP {resp.status}"
    except urllib.error.URLError as exc:
        return False, str(exc.reason if hasattr(exc, "reason") else exc)
    except Exception as exc:
        return False, str(exc)


def probe_dashboard_health(*, url: str | None = None) -> dict[str, Any]:
    target = url or TRADING_DASHBOARD_URL
    state = _load()
    open_mono = float(state.get("last_open_monotonic") or 0.0)
    since_open = time.monotonic() - open_mono if open_mono else None

    attempts: list[dict[str, Any]] = []
    ok = False
    detail = ""
    for attempt in range(max(1, PROBE_RETRIES)):
        attempt_ok, attempt_detail = _probe_once(target)
        attempts.append({"attempt": attempt + 1, "ok": attempt_ok, "detail": attempt_detail})
        if attempt_ok:
            ok = True
            detail = attempt_detail
            break
        detail = attempt_detail
        if attempt + 1 < PROBE_RETRIES:
            time.sleep(PROBE_DELAY_SECONDS)

    if ok:
        status = "healthy"
    elif since_open is not None and since_open < GRACE_SECONDS:
        status = "starting"
    elif since_open is not None and since_open < GRACE_SECONDS + STABILIZATION_SECONDS:
        status = "degraded"
    else:
        status = "failed"

    payload = {
        "url": target,
        "status": status,
        "reachable": ok,
        "detail": detail,
        "checked_at": _now_iso(),
        "since_open_seconds": round(since_open, 2) if since_open is not None else None,
        "grace_seconds": GRACE_SECONDS,
        "attempts": attempts,
    }
    state["last_probe"] = payload
    if ok:
        state["last_healthy_at"] = _now_iso()
    _save(state)
    return payload


def dashboard_status_label(probe: dict[str, Any]) -> str:
    return str(probe.get("status") or ("healthy" if probe.get("reachable") else "failed"))
