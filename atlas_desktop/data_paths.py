"""Resolve a writable Atlas desktop data directory (startup + analytics + usage)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

_RESOLVED_DIR: Optional[str] = None
_FALLBACK_KIND: Optional[str] = None


def _is_writable(path: str) -> bool:
    try:
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        test = p / ".write_test"
        test.write_text("ok", encoding="utf-8")
        test.unlink(missing_ok=True)
        return True
    except OSError:
        return False


# Pre-rename installs stored data under this name; migrated once at startup.
_LEGACY_HOME_DIR_NAME = ".jarvis_desktop"


def _migrate_legacy_home_dir(home: str, new_dir: str) -> None:
    """One-time rename of the legacy data dir so existing installs keep their
    scans, settings and session after the product rename."""
    legacy = os.path.join(home, _LEGACY_HOME_DIR_NAME)
    if os.path.isdir(legacy) and not os.path.exists(new_dir):
        try:
            os.rename(legacy, new_dir)
        except OSError:
            pass


def _candidate_dirs() -> List[Tuple[str, str]]:
    home = os.path.expanduser("~")
    local_app = os.environ.get("LOCALAPPDATA", "").strip()
    temp = tempfile.gettempdir()
    new_home = os.path.join(home, ".atlas_desktop")
    _migrate_legacy_home_dir(home, new_home)
    out: List[Tuple[str, str]] = [
        (new_home, "home"),
    ]
    if local_app:
        out.append((os.path.join(local_app, "Atlas", "desktop_data"), "localappdata"))
    out.append((os.path.join(temp, "atlas_desktop_data"), "temp"))
    return out


def reset_desktop_data_dir_cache() -> None:
    global _RESOLVED_DIR, _FALLBACK_KIND
    _RESOLVED_DIR = None
    _FALLBACK_KIND = None


def resolve_desktop_data_dir(*, force: bool = False) -> str:
    """Pick the first writable data directory; never require manual env vars."""
    global _RESOLVED_DIR, _FALLBACK_KIND

    override = (
        os.environ.get("ATLAS_DESKTOP_DATA", "").strip()
        # Legacy env name from pre-rename installs.
        or os.environ.get("JARVIS_DESKTOP_DATA", "").strip()
    )
    if override:
        path = os.path.abspath(override)
        _RESOLVED_DIR = path
        _FALLBACK_KIND = None
        return path

    if _RESOLVED_DIR and not force:
        return _RESOLVED_DIR

    for path, kind in _candidate_dirs():
        if _is_writable(path):
            _RESOLVED_DIR = os.path.abspath(path)
            _FALLBACK_KIND = None if kind == "home" else kind
            return _RESOLVED_DIR

    fallback = os.path.join(tempfile.gettempdir(), "atlas_desktop_data")
    os.makedirs(fallback, exist_ok=True)
    _RESOLVED_DIR = os.path.abspath(fallback)
    _FALLBACK_KIND = "temp"
    return _RESOLVED_DIR


def desktop_data_dir() -> str:
    return resolve_desktop_data_dir()


def desktop_data_dir_info() -> dict:
    resolve_desktop_data_dir()
    return {
        "path": _RESOLVED_DIR or desktop_data_dir(),
        "fallback": _FALLBACK_KIND,
        "override_env": bool(
            os.environ.get("ATLAS_DESKTOP_DATA", "").strip()
            or os.environ.get("JARVIS_DESKTOP_DATA", "").strip()
        ),
    }
