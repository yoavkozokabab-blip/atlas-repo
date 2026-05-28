"""Safe PowerShell execution — allowlisted scripts only."""

from __future__ import annotations

import subprocess
from pathlib import Path

from config import ALLOWED_POWERSHELL_SCRIPTS


def run_allowlisted_script(script_path: Path, *, new_window: bool = True) -> str:
    """
    Execute a hardcoded PowerShell script path.
    Raises ValueError if the path is not on the allowlist.
    """
    resolved = script_path.resolve()
    allowed = {p.resolve() for p in ALLOWED_POWERSHELL_SCRIPTS}
    if resolved not in allowed:
        raise ValueError(f"Script not allowlisted: {resolved}")

    if not resolved.is_file():
        raise FileNotFoundError(f"Script not found: {resolved}")

    args = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(resolved),
    ]
    if new_window:
        subprocess.Popen(
            ["cmd.exe", "/c", "start", "", *args],
            shell=False,
        )
        return f"Started script in new window: {resolved.name}"

    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(err or f"Script failed with code {result.returncode}")
    return (result.stdout or "").strip() or "Script completed."
