"""Resolve Atlas' stable per-user desktop data directory."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

_RESOLVED_DIR: Optional[str] = None
_FALLBACK_KIND: Optional[str] = None
# The env override the cached value was computed from ("" = no override), so a
# changed/removed override invalidates the cache instead of leaking a stale
# directory into later calls.
_RESOLVED_FROM_OVERRIDE: Optional[str] = None
_MIGRATION_RESULT: Optional[dict] = None
_TEST_MODE_ENV = "ATLAS_TEST_MODE"
_PROTECTED_ROOT_ENV = "ATLAS_TEST_PROTECTED_DATA_ROOT"


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


# Pre-rename installs stored data under this name. Validated migration copies
# it; path resolution itself never renames user data.
_LEGACY_HOME_DIR_NAME = ".jarvis_desktop"


def _user_home() -> str:
    """Return the per-user profile without cwd or executable-directory input."""
    if os.name == "nt":
        profile = os.environ.get("USERPROFILE", "").strip()
        if profile:
            return os.path.abspath(profile)
    return os.path.abspath(os.path.expanduser("~"))


def canonical_desktop_data_dir() -> str:
    return os.path.join(_user_home(), ".atlas_desktop")


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _normalized_path(path: str) -> str:
    return os.path.normcase(os.path.abspath(os.path.realpath(path)))


def protected_test_data_root() -> str:
    """Return the real user root tests are forbidden to access.

    The test supervisor captures this before tests can monkeypatch USERPROFILE.
    Standalone test-mode children fall back to the process' canonical root.
    """
    configured = os.environ.get(_PROTECTED_ROOT_ENV, "").strip()
    return os.path.abspath(configured or canonical_desktop_data_dir())


def assert_safe_test_data_dir(path: str) -> str:
    """Fail closed when test mode targets the real Atlas user-data tree."""
    resolved = os.path.abspath(path or "")
    if not _env_truthy(_TEST_MODE_ENV):
        return resolved
    if not path:
        raise RuntimeError("Atlas test mode requires an explicit isolated data root.")

    candidate = _normalized_path(resolved)
    protected = _normalized_path(protected_test_data_root())
    try:
        inside_protected = os.path.commonpath([candidate, protected]) == protected
    except ValueError:
        inside_protected = candidate == protected
    if inside_protected:
        raise RuntimeError(
            "Atlas test mode refused the protected canonical data root: "
            f"{protected_test_data_root()}"
        )
    return resolved


def _candidate_dirs() -> List[Tuple[str, str]]:
    local_app = os.environ.get("LOCALAPPDATA", "").strip()
    temp = tempfile.gettempdir()
    out: List[Tuple[str, str]] = [
        (canonical_desktop_data_dir(), "home"),
    ]
    if local_app:
        out.append((os.path.join(local_app, "Atlas", "desktop_data"), "localappdata"))
    out.append((os.path.join(temp, "atlas_desktop_data"), "temp"))
    return out


def reset_desktop_data_dir_cache() -> None:
    global _RESOLVED_DIR, _FALLBACK_KIND, _RESOLVED_FROM_OVERRIDE, _MIGRATION_RESULT
    _RESOLVED_DIR = None
    _FALLBACK_KIND = None
    _RESOLVED_FROM_OVERRIDE = None
    _MIGRATION_RESULT = None


def _current_override() -> str:
    return (
        os.environ.get("ATLAS_DESKTOP_DATA", "").strip()
        # Legacy env name from pre-rename installs.
        or os.environ.get("JARVIS_DESKTOP_DATA", "").strip()
    )


def resolve_desktop_data_dir(*, force: bool = False) -> str:
    """Pick the first writable data directory; never require manual env vars."""
    global _RESOLVED_DIR, _FALLBACK_KIND, _RESOLVED_FROM_OVERRIDE

    override = _current_override()
    if _env_truthy(_TEST_MODE_ENV) and not override:
        raise RuntimeError("Atlas test mode requires ATLAS_DESKTOP_DATA for every process.")
    if override:
        path = assert_safe_test_data_dir(override)
        _RESOLVED_DIR = path
        _FALLBACK_KIND = None
        _RESOLVED_FROM_OVERRIDE = override
        return path

    if _RESOLVED_DIR and not force and not _RESOLVED_FROM_OVERRIDE:
        return assert_safe_test_data_dir(_RESOLVED_DIR)

    for path, kind in _candidate_dirs():
        if _is_writable(path):
            _RESOLVED_DIR = os.path.abspath(path)
            _FALLBACK_KIND = None if kind == "home" else kind
            _RESOLVED_FROM_OVERRIDE = None
            return _RESOLVED_DIR

    fallback = os.path.join(tempfile.gettempdir(), "atlas_desktop_data")
    os.makedirs(fallback, exist_ok=True)
    _RESOLVED_DIR = os.path.abspath(fallback)
    _FALLBACK_KIND = "temp"
    _RESOLVED_FROM_OVERRIDE = None
    return _RESOLVED_DIR


def desktop_data_dir() -> str:
    return resolve_desktop_data_dir()


def historical_desktop_data_dirs() -> List[str]:
    """Known product roots eligible for validated one-time discovery."""
    home = _user_home()
    roots = [os.path.join(home, _LEGACY_HOME_DIR_NAME)]
    local_app = os.environ.get("LOCALAPPDATA", "").strip()
    if local_app:
        roots.append(os.path.join(local_app, "Atlas", "desktop_data"))
    roots.append(os.path.join(tempfile.gettempdir(), "atlas_desktop_data"))
    canonical = os.path.normcase(os.path.abspath(canonical_desktop_data_dir()))
    return [
        os.path.abspath(path)
        for path in roots
        if os.path.normcase(os.path.abspath(path)) != canonical
    ]


def ensure_repository_state_migrated(*, source_roots: Optional[List[str]] = None) -> dict:
    """Discover valid historical scans without crossing override boundaries."""
    global _MIGRATION_RESULT
    effective = desktop_data_dir()
    if _current_override() and source_roots is None:
        _MIGRATION_RESULT = {
            "status": "skipped_override",
            "canonical_root": canonical_desktop_data_dir(),
            "effective_root": effective,
        }
        return dict(_MIGRATION_RESULT)
    if _MIGRATION_RESULT is not None and source_roots is None:
        return dict(_MIGRATION_RESULT)
    from .persistence_migration import migrate_repository_state

    _MIGRATION_RESULT = migrate_repository_state(
        canonical_root=canonical_desktop_data_dir(),
        source_roots=source_roots or historical_desktop_data_dirs(),
        force=source_roots is not None,
    )
    return dict(_MIGRATION_RESULT)


def desktop_data_dir_info() -> dict:
    resolve_desktop_data_dir()
    effective = _RESOLVED_DIR or desktop_data_dir()
    return {
        "path": effective,
        "canonical_path": canonical_desktop_data_dir(),
        "registry_path": os.path.join(effective, "scans", "registry.json"),
        "scans_path": os.path.join(effective, "scans"),
        "account_session_path": os.path.join(effective, "accounts_state.json"),
        "repository_history_path": os.path.join(effective, "histories"),
        "settings_path": "browser localStorage for the Atlas runtime origin",
        "fallback": _FALLBACK_KIND,
        "override_env": bool(
            os.environ.get("ATLAS_DESKTOP_DATA", "").strip()
            or os.environ.get("JARVIS_DESKTOP_DATA", "").strip()
        ),
        "migration": dict(_MIGRATION_RESULT or {}),
    }
