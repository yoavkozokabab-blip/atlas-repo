"""Windows Startup shortcut autostart (safe, confirm-required to change)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from config import PROJECT_ROOT
from core.file_cleanup import remove_file_best_effort
from core.logger import setup_logger

logger = setup_logger("jarvis.services.autostart")

TRAY_LAUNCH_SCRIPT = (PROJECT_ROOT / "scripts" / "run_jarvis_tray.ps1").resolve()
STARTUP_SHORTCUT_NAME = "JARVIS Tray.lnk"
ALLOWED_TARGET_NAMES = frozenset({"powershell.exe", "pwsh.exe", "WindowsPowerShell.exe"})


class AutostartError(Exception):
    pass


def _startup_folder() -> Path:
    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        raise AutostartError("APPDATA not set — cannot locate Startup folder.")
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def _shortcut_path() -> Path:
    return _startup_folder() / STARTUP_SHORTCUT_NAME


def validate_tray_script_path(path: Path | None = None) -> Path:
    """Ensure autostart target is only the project tray launcher script."""
    script = (path or TRAY_LAUNCH_SCRIPT).resolve()
    expected = TRAY_LAUNCH_SCRIPT
    if script != expected:
        raise AutostartError(
            f"Unsafe autostart target: {script}. Only {expected} is allowed."
        )
    if not script.is_file():
        raise AutostartError(f"Tray launcher script missing: {script}")
    return script


def _read_shortcut_target(shortcut: Path) -> dict[str, str]:
    """Read .lnk metadata via PowerShell (read-only)."""
    if not shortcut.is_file():
        return {}
    ps = (
        f'$s = (New-Object -ComObject WScript.Shell).CreateShortcut("{shortcut}"); '
        'Write-Output ($s.TargetPath + "|" + $s.Arguments + "|" + $s.WorkingDirectory)'
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return {}
        parts = proc.stdout.strip().split("|", 2)
        while len(parts) < 3:
            parts.append("")
        return {
            "target": parts[0],
            "arguments": parts[1],
            "working_directory": parts[2],
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.debug("Shortcut read failed: %s", exc)
        return {}


def is_autostart_enabled() -> bool:
    return _shortcut_path().is_file()


def get_autostart_status() -> dict[str, Any]:
    """Read-only autostart status."""
    script = TRAY_LAUNCH_SCRIPT
    shortcut = _shortcut_path()
    enabled = shortcut.is_file()
    meta = _read_shortcut_target(shortcut) if enabled else {}
    target_ok = False
    args_ok = False
    if enabled and meta:
        target_name = Path(meta.get("target", "")).name.lower()
        args = meta.get("arguments", "")
        target_ok = target_name in {n.lower() for n in ALLOWED_TARGET_NAMES}
        args_ok = str(script) in args.replace("/", "\\") or str(script).lower() in args.lower()
    return {
        "enabled": enabled,
        "shortcut_path": str(shortcut),
        "tray_script": str(script),
        "tray_script_exists": script.is_file(),
        "target_valid": target_ok,
        "arguments_valid": args_ok,
        "shortcut_meta": meta,
        "method": "windows_startup_shortcut",
    }


def enable_autostart() -> dict[str, Any]:
    """Create Startup shortcut pointing to run_jarvis_tray.ps1 (confirm before calling)."""
    script = validate_tray_script_path()
    startup = _startup_folder()
    startup.mkdir(parents=True, exist_ok=True)
    shortcut = _shortcut_path()
    ps_script = str(script).replace("'", "''")
    ps_root = str(PROJECT_ROOT.resolve()).replace("'", "''")
    ps_shortcut = str(shortcut).replace("'", "''")
    command = (
        f"$WshShell = New-Object -ComObject WScript.Shell; "
        f"$s = $WshShell.CreateShortcut('{ps_shortcut}'); "
        f"$s.TargetPath = 'powershell.exe'; "
        f"$s.Arguments = '-NoProfile -ExecutionPolicy Bypass -File \"{ps_script}\"'; "
        f"$s.WorkingDirectory = '{ps_root}'; "
        f"$s.Description = 'JARVIS tray (local_jarvis)'; "
        f"$s.Save()"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except OSError as exc:
        raise AutostartError(f"Could not create Startup shortcut: {exc}") from exc

    if proc.returncode != 0:
        raise AutostartError(
            proc.stderr.strip() or "PowerShell failed to create Startup shortcut."
        )

    status = get_autostart_status()
    status["action"] = "enabled"
    logger.info("Autostart enabled: %s", shortcut)
    return status


def disable_autostart() -> dict[str, Any]:
    """Remove Startup shortcut (confirm before calling)."""
    shortcut = _shortcut_path()
    removed = False
    if shortcut.is_file():
        if not remove_file_best_effort(shortcut):
            raise AutostartError(f"Could not remove shortcut: {shortcut}")
        removed = True
    status = get_autostart_status()
    status["action"] = "disabled"
    status["removed"] = removed
    logger.info("Autostart disabled (removed=%s)", removed)
    return status
