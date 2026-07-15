"""Product metadata, release config, and user-facing labels."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

PRODUCT_VERSION = "1.0.1"
LAUNCH_BUILD_LABEL = "Atlas v1.0.1 launch build"
DEFAULT_SUPPORT_EMAIL = "yoavkozokabab@gmail.com"

_BUILD_DATE = time.strftime("%Y-%m-%d", time.gmtime())
_BUILD_COMMIT_CACHE: Optional[str] = None


def build_commit() -> str:
    """Best-effort exact git SHA or env override."""
    global _BUILD_COMMIT_CACHE
    if _BUILD_COMMIT_CACHE:
        return _BUILD_COMMIT_CACHE
    env = (os.environ.get("ATLAS_BUILD_COMMIT") or "").strip()
    if env:
        _BUILD_COMMIT_CACHE = env
        return env
    # Packaged builds ship build_info.json; prefer it over `git`, which would
    # otherwise pick up whatever repository happens to contain the install dir.
    if getattr(sys, "frozen", False):
        try:
            root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            info_path = os.path.join(root, "packaging", "installer", "build_info.json")
            with open(info_path, encoding="utf-8-sig") as fh:
                commit = str(json.load(fh).get("commit") or "").strip()
            if commit:
                _BUILD_COMMIT_CACHE = commit
                return commit
        except (OSError, ValueError):
            pass
    try:
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        proc = subprocess.run(
            ["git", "-C", root, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            _BUILD_COMMIT_CACHE = proc.stdout.strip()
            return _BUILD_COMMIT_CACHE
    except (OSError, subprocess.SubprocessError):
        pass
    _BUILD_COMMIT_CACHE = "unknown"
    return _BUILD_COMMIT_CACHE


def build_date() -> str:
    return (os.environ.get("ATLAS_BUILD_DATE") or "").strip() or _BUILD_DATE


def support_email() -> str:
    return (os.environ.get("ATLAS_SUPPORT_EMAIL") or "").strip() or DEFAULT_SUPPORT_EMAIL


def feedback_url() -> str:
    return (os.environ.get("ATLAS_FEEDBACK_URL") or "").strip()


def update_check_url() -> str:
    return (os.environ.get("ATLAS_UPDATE_CHECK_URL") or "").strip()


def version_info() -> Dict[str, Any]:
    return {
        "version": PRODUCT_VERSION,
        "launch_build_label": LAUNCH_BUILD_LABEL,
        "build_commit": build_commit(),
        "build_date": build_date(),
        "product": "ATLAS",
        "channel": "release",
    }


def product_config() -> Dict[str, Any]:
    """Public product configuration for UI (no secrets)."""
    return {
        "ok": True,
        **version_info(),
        "support_email": support_email(),
        "feedback_url_configured": bool(feedback_url()),
        "update_check_configured": bool(update_check_url()),
        "billing_enabled": False,
        "payments_active": False,
        "checkout_enabled": False,
        "billing_message": "Billing is not enabled in this build. Plans and usage are preview-only.",
    }


def user_trust_label(staleness: Dict[str, Any], *, graph_label: str = "") -> str:
    """Map internal trust state to a simple user-facing label."""
    if not staleness:
        return "Fresh"
    status = str(staleness.get("status") or "")
    if staleness.get("fresh") is True or status == "fresh":
        return "Fresh"
    if status == "targeted_refresh_required":
        return "Needs refresh"
    gl = (graph_label or "").lower()
    if gl in ("unsupported_language_limited",) or "unsupported" in gl:
        return "Limited language support"
    if status in (
        "requires_rescan",
        "stale_scan",
        "stale_outside_plan",
        "stale_git_head_changed",
        "full_rescan_required",
        "memory_invalid",
        "memory_stale",
    ):
        return "Full rescan required"
    if not staleness.get("fresh"):
        return "Needs refresh"
    return "Fresh"


def check_for_update() -> Dict[str, Any]:
    """Optional update check — fails silently when unavailable."""
    current = PRODUCT_VERSION
    url = update_check_url()
    if not url:
        return {
            "ok": True,
            "configured": False,
            "update_available": False,
            "current_version": current,
        }
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
        resp = urllib.request.urlopen(req, timeout=5)
        try:
            raw = resp.read().decode("utf-8", errors="replace")
        finally:
            if hasattr(resp, "close"):
                resp.close()
        data = json.loads(raw) if raw.strip() else {}
        latest = str(data.get("version") or data.get("latest") or "").strip()
        update_available = bool(latest and latest != current)
        return {
            "ok": True,
            "configured": True,
            "update_available": update_available,
            "current_version": current,
            "latest_version": latest or None,
            "release_notes_url": data.get("release_notes_url") or data.get("url"),
        }
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError, ValueError):
        return {
            "ok": True,
            "configured": True,
            "update_available": False,
            "current_version": current,
            "check_failed": True,
        }
