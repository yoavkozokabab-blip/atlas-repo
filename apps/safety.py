"""Safety checks for app launch paths — no arbitrary execution."""

from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import urlparse

BLOCKED_EXECUTABLES: frozenset[str] = frozenset(
    {
        "cmd.exe",
        "powershell.exe",
        "pwsh.exe",
        "regedit.exe",
        "taskkill.exe",
        "wscript.exe",
        "cscript.exe",
        "rundll32.exe",
        "mshta.exe",
        "certutil.exe",
        "bitsadmin.exe",
        "regsvr32.exe",
    }
)

BLOCKED_EXTENSIONS: frozenset[str] = frozenset({".bat", ".cmd", ".ps1", ".vbs", ".js", ".jse", ".wsf"})

ALLOWED_URL_SCHEMES: frozenset[str] = frozenset()

_SYSTEM32_MARKERS = (
    "\\windows\\system32\\",
    "\\windows\\syswow64\\",
)


class SafetyError(Exception):
    """Path or target is not safe to launch."""


def _is_url(path_str: str) -> bool:
    parsed = urlparse(path_str.strip())
    return parsed.scheme in {"http", "https", "ftp", "file"}


def validate_launch_path(path: Path | str) -> Path:
    """
    Validate a shortcut or file path before os.startfile.
    Raises SafetyError if blocked.
    """
    resolved = Path(path).expanduser()
    try:
        resolved = resolved.resolve(strict=False)
    except (OSError, ValueError):
        resolved = Path(os.path.abspath(str(path)))

    if not resolved.exists():
        raise SafetyError(f"Path does not exist: {resolved}")

    raw = str(resolved).lower()
    if _is_url(raw):
        raise SafetyError("URL targets are not allowlisted for app launch.")

    suffix = resolved.suffix.lower()
    if suffix in BLOCKED_EXTENSIONS:
        raise SafetyError(f"Script/extension not allowed: {suffix}")

    name = resolved.name.lower()
    if name in BLOCKED_EXECUTABLES:
        raise SafetyError(f"Blocked executable: {name}")

    for marker in _SYSTEM32_MARKERS:
        if marker in raw:
            raise SafetyError("System directory executables are blocked.")

    if suffix == ".exe":
        # Only allow .exe outside system dirs (shortcuts preferred)
        if any(marker in raw for marker in _SYSTEM32_MARKERS):
            raise SafetyError("Blocked system executable path.")

    if suffix not in {".lnk", ".exe", ""}:
        # Allow .lnk primarily; .exe only when explicitly resolved and vetted
        if suffix not in {".url"}:
            pass  # .url often internet shortcut — block
        if suffix == ".url":
            raise SafetyError("Internet shortcut (.url) files are blocked.")

    return resolved


def validate_resolved_target(target: Path | str | None) -> Path | None:
    """Validate optional resolved .lnk target (exe); return None if only .lnk used."""
    if target is None:
        return None
    path = Path(target)
    if not path.suffix:
        return None
    return validate_launch_path(path)
