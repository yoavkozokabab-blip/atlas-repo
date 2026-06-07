"""Persisted JWT signing secret for the accounts service."""
from __future__ import annotations

import os
import secrets
from typing import Optional

_SECRET_FILENAME = "jwt_secret"


def accounts_data_dir() -> str:
    """Directory for accounts-service local state (secret file, etc.)."""
    env = (os.environ.get("ATLAS_ACCOUNTS_DATA_DIR") or "").strip()
    if env:
        return os.path.abspath(env)
    db_url = (os.environ.get("ATLAS_ACCOUNTS_DB") or "sqlite:///./atlas_accounts.db").strip()
    if db_url.startswith("sqlite:///"):
        path = db_url[len("sqlite:///"):]
        if path and path != ":memory:":
            return os.path.abspath(os.path.dirname(path) or ".")
    return os.path.abspath(".")


def jwt_secret_file_path() -> str:
    return os.path.join(accounts_data_dir(), "auth", _SECRET_FILENAME)


def load_jwt_secret() -> str:
    """Load JWT secret from env or create/load a persisted local secret."""
    for key in ("ATLAS_AUTH_JWT_SECRET", "ATLAS_JWT_SECRET"):
        value = (os.environ.get(key) or "").strip()
        if value:
            return value

    path = jwt_secret_file_path()
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as fh:
                stored = fh.read().strip()
            if stored:
                return stored
        except OSError:
            pass

    secret = secrets.token_hex(32)
    auth_dir = os.path.dirname(path)
    os.makedirs(auth_dir, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, secret.encode("utf-8"))
        finally:
            os.close(fd)
    except FileExistsError:
        with open(path, encoding="utf-8") as fh:
            secret = fh.read().strip() or secret
    except OSError:
        pass
    return secret
