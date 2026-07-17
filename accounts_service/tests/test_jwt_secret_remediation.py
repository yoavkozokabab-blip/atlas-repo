"""Regression guard: JWT signing material is environment-only and untracked."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from accounts_service.jwt_secret import load_jwt_secret


def test_missing_signer_secret_fails_closed(monkeypatch):
    monkeypatch.delenv("ATLAS_AUTH_JWT_SECRET", raising=False)
    monkeypatch.delenv("ATLAS_JWT_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="required"):
        load_jwt_secret()


def test_env_signer_secret_is_required_and_never_file_backed(monkeypatch, tmp_path):
    monkeypatch.setenv("ATLAS_AUTH_JWT_SECRET", "test-only-secret-with-at-least-thirty-two-bytes")
    monkeypatch.chdir(tmp_path)
    assert load_jwt_secret() == "test-only-secret-with-at-least-thirty-two-bytes"
    assert not list(Path(tmp_path).rglob("*jwt*secret*"))


def test_gitignore_prohibits_jwt_secret_artifacts():
    root = Path(__file__).resolve().parents[2]
    ignored = (root / ".gitignore").read_text(encoding="utf-8")
    assert "auth/jwt_secret" in ignored
    assert "**/*jwt*secret*" in ignored
