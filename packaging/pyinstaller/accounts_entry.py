"""Frozen entry point for the Atlas Accounts Service (AtlasAccounts.exe).

Runs the FastAPI accounts app under uvicorn on 127.0.0.1:8788. The desktop app
(Atlas.exe) launches this sibling executable automatically — no Python, no
terminal, no manual setup required.

Data (SQLite DB + JWT secret) is written to a per-user writable directory so the
service works even when the app is installed under a read-only location.
"""
from __future__ import annotations

import os
import sys


def _setup_writable_data_dir() -> None:
    """Point the DB + JWT secret at a per-user writable directory (env-overridable)."""
    if not os.environ.get("ATLAS_ACCOUNTS_DATA_DIR"):
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        data_dir = os.path.join(base, "Atlas", "accounts_service")
        try:
            os.makedirs(os.path.join(data_dir, "auth"), exist_ok=True)
        except OSError:
            data_dir = os.path.join(os.path.expanduser("~"), ".atlas_accounts")
            os.makedirs(os.path.join(data_dir, "auth"), exist_ok=True)
        os.environ["ATLAS_ACCOUNTS_DATA_DIR"] = data_dir
    if not os.environ.get("ATLAS_ACCOUNTS_DB"):
        data_dir = os.environ["ATLAS_ACCOUNTS_DATA_DIR"]
        db_path = os.path.join(data_dir, "atlas_accounts.db").replace(os.sep, "/")
        os.environ["ATLAS_ACCOUNTS_DB"] = f"sqlite:///{db_path}"


def main() -> int:
    _setup_writable_data_dir()
    host = os.environ.get("ATLAS_ACCOUNTS_HOST", "127.0.0.1")
    try:
        port = int(os.environ.get("ATLAS_ACCOUNTS_PORT", "8788"))
    except ValueError:
        port = 8788

    # Imported here (after env is set) so accounts_service.config reads the
    # writable paths, and so PyInstaller traces uvicorn from this entry point.
    import uvicorn

    uvicorn.run(
        "accounts_service.main:app",
        host=host,
        port=port,
        reload=False,
        log_level="warning",
        access_log=False,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
