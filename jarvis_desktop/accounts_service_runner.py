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


def _frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _accounts_data_dir() -> str:
    """A per-user writable directory for the accounts DB + JWT secret."""
    try:
        from jarvis_desktop.data_paths import desktop_data_dir

        base = desktop_data_dir()
    except Exception:
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        base = os.path.join(base, "Atlas")
    data_dir = os.path.join(base, "accounts_service")
    try:
        os.makedirs(os.path.join(data_dir, "auth"), exist_ok=True)
    except OSError:
        pass
    return data_dir


def _frozen_accounts_exe() -> Optional[str]:
    """Locate the bundled AtlasAccounts.exe next to the frozen Atlas.exe."""
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    for candidate in (
        os.path.join(exe_dir, "accounts", "AtlasAccounts.exe"),
        os.path.join(exe_dir, "AtlasAccounts.exe"),
    ):
        if os.path.isfile(candidate):
            return candidate
    return None


def _service_env() -> dict:
    """Environment for the accounts service: writable DB + JWT secret paths."""
    env = os.environ.copy()
    data_dir = _accounts_data_dir()
    env.setdefault("ATLAS_ACCOUNTS_DATA_DIR", data_dir)
    if not env.get("ATLAS_ACCOUNTS_DB"):
        db_path = os.path.join(data_dir, "atlas_accounts.db").replace(os.sep, "/")
        env["ATLAS_ACCOUNTS_DB"] = f"sqlite:///{db_path}"
    return env


def start_accounts_service() -> bool:
    """Launch the accounts service in the background if not already running.

    Frozen install: spawn the bundled AtlasAccounts.exe (no Python required).
    Source mode: spawn ``python -m accounts_service.main``.
    """
    global _process
    with _lock:
        if is_running():
            return True
        if _process is not None and _process.poll() is None:
            return True

        env = _service_env()
        if _frozen():
            exe = _frozen_accounts_exe()
            if not exe:
                _log("accounts service exe not found next to Atlas.exe")
                return False
            cmd = [exe]
            cwd = os.path.dirname(exe)
        else:
            lib = os.path.join(_repo_root, "accounts_service", ".lib")
            if lib not in env.get("PYTHONPATH", "").split(os.pathsep):
                env["PYTHONPATH"] = lib + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
            cmd = [sys.executable, "-m", "accounts_service.main"]
            cwd = _repo_root

        try:
            _process = subprocess.Popen(
                cmd,
                cwd=cwd,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            _log(f"accounts service started pid={_process.pid} frozen={_frozen()}")
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
    from jarvis_desktop import accounts_client

    if accounts_client.auth_mode() == "website":
        # Website authority: never spawn a local service. Instead verify the
        # cached session against /me in the background (Phase 186A).
        def _verify() -> None:
            try:
                accounts_client.verify_session()
            except Exception:
                pass

        threading.Thread(target=_verify, name="atlas-session-verify", daemon=True).start()
        return

    if is_running():
        return

    def _worker() -> None:
        ensure_running(timeout=15.0)

    threading.Thread(target=_worker, name="atlas-accounts-boot", daemon=True).start()
