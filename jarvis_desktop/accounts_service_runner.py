"""Start and supervise the local Atlas accounts service (port 8788)."""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from typing import Optional

_process: Optional[subprocess.Popen] = None
_lock = threading.Lock()
_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _log(message: str) -> None:
    try:
        from jarvis_desktop.install_support import append_launcher_log

        append_launcher_log(message)
    except Exception:
        pass


def is_running() -> bool:
    from jarvis_desktop import accounts_client

    return accounts_client.is_service_running()


def start_accounts_service() -> bool:
    """Launch accounts_service in a background subprocess if not already running."""
    global _process
    with _lock:
        if is_running():
            return True
        if _process is not None and _process.poll() is None:
            return True

        lib = os.path.join(_repo_root, "accounts_service", ".lib")
        env = os.environ.copy()
        if lib not in env.get("PYTHONPATH", "").split(os.pathsep):
            env["PYTHONPATH"] = lib + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")

        cmd = [sys.executable, "-m", "accounts_service.main"]
        try:
            _process = subprocess.Popen(
                cmd,
                cwd=_repo_root,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            _log(f"accounts service subprocess started pid={_process.pid}")
            return True
        except OSError as exc:
            _log(f"accounts service start failed: {type(exc).__name__}: {exc}")
            _process = None
            return False


def ensure_running(timeout: float = 12.0) -> bool:
    """Ensure the accounts service responds to /health within timeout seconds."""
    if is_running():
        return True
    start_accounts_service()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_running():
            return True
        time.sleep(0.2)
    return is_running()


def ensure_running_async() -> None:
    """Best-effort background start (desktop server boot)."""
    if is_running():
        return

    def _worker() -> None:
        ensure_running(timeout=15.0)

    threading.Thread(target=_worker, name="atlas-accounts-boot", daemon=True).start()
