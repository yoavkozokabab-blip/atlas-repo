"""Signing-secret resolution guards (v1.0.5 per-install key store)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from accounts_service.jwt_secret import load_jwt_secret


def test_no_env_secret_falls_back_to_per_install_store(monkeypatch, tmp_path):
    monkeypatch.delenv("ATLAS_AUTH_JWT_SECRET", raising=False)
    monkeypatch.delenv("ATLAS_JWT_SECRET", raising=False)
    monkeypatch.setenv("ATLAS_ACCOUNTS_DATA_DIR", str(tmp_path))
    secret = load_jwt_secret()
    assert len(secret) >= 32
    # The key store is created under auth/, protected, and stable.
    assert (tmp_path / "auth" / "signing_key.v1.bin").is_file()
    assert load_jwt_secret() == secret


def test_short_env_secret_rejected(monkeypatch):
    monkeypatch.setenv("ATLAS_AUTH_JWT_SECRET", "too-short")
    with pytest.raises(RuntimeError, match="32"):
        load_jwt_secret()


def test_env_signer_secret_wins_and_writes_no_files(monkeypatch, tmp_path):
    monkeypatch.setenv("ATLAS_AUTH_JWT_SECRET", "test-only-secret-with-at-least-thirty-two-bytes")
    monkeypatch.setenv("ATLAS_ACCOUNTS_DATA_DIR", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    assert load_jwt_secret() == "test-only-secret-with-at-least-thirty-two-bytes"
    assert not list(Path(tmp_path).rglob("*.bin"))
    assert not list(Path(tmp_path).rglob("*jwt*secret*"))


def test_gitignore_prohibits_jwt_secret_artifacts():
    root = Path(__file__).resolve().parents[2]
    ignored = (root / ".gitignore").read_text(encoding="utf-8")
    assert "auth/jwt_secret" in ignored
    assert "**/*jwt*secret*" in ignored
