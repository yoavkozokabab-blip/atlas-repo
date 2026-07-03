"""Phase 175D — close final beta gates (175C NO-GO blockers)."""

from __future__ import annotations

import base64
import io
import os
import sys
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from atlas_desktop import api, server
from atlas_desktop.install_support import _redact_support_text

STATIC = Path(__file__).resolve().parents[1] / "static"
ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_MARKERS = ("api_key=", "token=", "Authorization:", "Bearer ")


def _fresh() -> None:
    api._STATE.clear()
    api._STATE.update({
        "path": None, "scan": None, "graph": None, "index": None, "risks": None,
        "demo_mode": False, "last_scope": {"mode": "entire_repo"},
        "scan_cache": {}, "scan_job": {"id": None, "cancelled": False, "stage": "idle"},
        "session_export": None, "repository_memory": None, "_current_memory": None,
    })


# --- Blocker 1: strict support bundle redaction ---

@pytest.mark.parametrize("sample", [
    "api_key=LEAK_ME",
    "token=TOKEN_LEAK_ME",
    "Authorization: Bearer BEARER_LEAK_ME",
    "Authorization=Bearer TESTTOKEN",
])
def test_redact_removes_secret_names_and_values(sample: str):
    out = _redact_support_text(sample)
    assert "[REDACTED]" in out
    for marker in FORBIDDEN_MARKERS:
        assert marker.lower() not in out.lower()


def test_a10_strict_support_bundle_no_key_patterns(tmp_path, monkeypatch):
    """175C A10 — values and key labels must not survive in bundle logs."""
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr("atlas_desktop.install_support.data_dir", lambda: str(data))
    log = (
        "Failure at C:\\secret\\app.py with SECRET_X "
        "and api_key=LEAK_ME and token=TOKEN_LEAK_ME "
        "and Authorization: Bearer BEARER_LEAK_ME"
    )
    (data / "launcher.log").write_text(log, encoding="utf-8")
    _fresh()
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("x=1\n", encoding="utf-8")
    api.scan_repository(str(repo))
    _, bundle = server.dispatch("POST", "/api/system/support-bundle")
    raw = base64.b64decode(bundle["content_base64"])
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        blob = zf.read("logs/launcher.log").decode("utf-8")
    assert "LEAK_ME" not in blob
    assert "TOKEN_LEAK_ME" not in blob
    assert "BEARER_LEAK_ME" not in blob
    for marker in FORBIDDEN_MARKERS:
        assert marker.lower() not in blob.lower()
    assert "[REDACTED]" in blob


# --- Blocker 2: port fallback ---

def test_port_bind_retryable_includes_winerror_10013():
    exc = PermissionError(13, "access forbidden")
    exc.winerror = 10013  # type: ignore[attr-defined]
    assert server._port_bind_retryable(exc) is True


def test_bind_http_server_retries_on_winerror_10013(monkeypatch):
    attempts = []

    class _FakeHttpd:
        def __init__(self, addr, _handler):
            attempts.append(addr[1])
            if addr[1] == 8822:
                exc = PermissionError(13, "forbidden")
                exc.winerror = 10013  # type: ignore[attr-defined]
                raise exc
            self.server_address = (addr[0], addr[1])

        def server_close(self):
            return None

    monkeypatch.setattr(server, "ThreadingHTTPServer", _FakeHttpd)
    httpd, port = server._bind_http_server("127.0.0.1", 8822, attempts=5)
    assert attempts == [8822, 8823]
    assert port == 8823
    httpd.server_close()


def test_run_atlas_has_startup_error_fallback():
    text = (ROOT / "run_atlas.py").read_text(encoding="utf-8")
    assert "startup-error.html" in text
    assert "_install_source_excepthook" in text
    assert "_safe_console_print" in text


# --- Blocker 3: brand cleanup ---

USER_FACING_STATIC = (
    # beta.html / atlas_beta.js were deleted in RC-1; atlas_workflows.js and
    # atlas_admin.js replaced/joined the shipped bundle.
    "index.html", "about.html", "contact.html", "support.html", "pricing.html",
    "usage.html", "quickstart.html", "landing.html", "feedback.html",
    "gallery.html", "demo.html", "studio.html", "admin.html", "startup-error.html",
    "app.js", "universe.js", "studio.js", "atlas_workflows.js", "atlas_zero_friction.js",
    "atlas_product.js", "atlas_admin.js", "feedback.js", "billing.js", "support.js",
)


@pytest.mark.parametrize("rel", USER_FACING_STATIC)
def test_no_jarvis_or_phase_labels_in_shipped_static(rel: str):
    text = (STATIC / rel).read_text(encoding="utf-8")
    assert "JARVIS" not in text, f"{rel} still contains JARVIS"
    assert "phase146" not in text.lower(), f"{rel} still contains phase146"
    assert "phase107" not in text.lower(), f"{rel} still contains phase107"


def test_universe_exports_atlas_global():
    js = (STATIC / "universe.js").read_text(encoding="utf-8")
    assert "ATLAS_UNIVERSE" in js
    assert "JARVIS_UNIVERSE" not in js


# --- Blocker 4: no raw traceback in browser-facing assets ---

def test_startup_error_page_exists_without_traceback():
    html = (STATIC / "startup-error.html").read_text(encoding="utf-8")
    assert "Startup check failed" in html
    assert "Traceback (most recent call last)" not in html


def test_run_atlas_avoids_unicode_cross_mark():
    text = (ROOT / "run_atlas.py").read_text(encoding="utf-8")
    assert "\u2717" not in text
    assert "[X]" in text
