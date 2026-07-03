"""Phase 173B beta infrastructure sprint — P0-01..04 + UX rails (no intelligence)."""

from __future__ import annotations

import base64
import io
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from atlas_desktop import api, install_support, server


def _fresh_state() -> None:
    api._STATE.clear()
    api._STATE.update({
        "path": None,
        "scan": None,
        "graph": None,
        "index": None,
        "risks": None,
        "demo_mode": False,
        "last_scope": {"mode": "entire_repo"},
        "scan_cache": {},
        "scan_job": {"id": None, "cancelled": False, "stage": "idle"},
        "session_export": None,
    })


def _tiny_repo(tmp_path: Path, name: str, body: str = "x = 1\n") -> Path:
    root = tmp_path / name
    root.mkdir()
    (root / "a.py").write_text(body, encoding="utf-8")
    return root


def test_p0_01_select_clears_scan_and_blocks_plan(tmp_path):
    _fresh_state()
    a = _tiny_repo(tmp_path, "repo_a")
    assert api.scan_repository(str(a))["ok"]
    b = _tiny_repo(tmp_path, "repo_b", "z = 9\n")
    sel = api.select_repository(str(b))
    assert sel["requires_rescan"] is True
    assert api._STATE["scan"] is None
    plan = api.plan_change("add feature")
    assert plan["ok"] is False
    assert plan["code"] == "requires_rescan"


def test_p0_03_bind_http_server_tries_next_port(monkeypatch):
    attempts = []

    class _FakeHttpd:
        def __init__(self, addr, _handler):
            attempts.append(addr[1])
            if len(attempts) < 2:
                exc = OSError("in use")
                exc.winerror = 10048  # type: ignore[attr-defined]
                raise exc
            self.server_address = (addr[0], addr[1])

        def server_close(self):
            return None

    monkeypatch.setattr(server, "ThreadingHTTPServer", _FakeHttpd)
    httpd, port = server._bind_http_server("127.0.0.1", 8777, attempts=5)
    assert attempts == [8777, 8778]
    assert port == 8778
    httpd.server_close()


def test_p0_04_support_bundle_redacts_absolute_paths(tmp_path):
    secret_root = tmp_path / "secret_customer_acme"
    secret_root.mkdir()
    (secret_root / "secret_customer_name.py").write_text(
        'def name():\n    return "SECRET_SOURCE_CANARY_173C_DO_NOT_EXPORT"\n',
        encoding="utf-8",
    )
    _fresh_state()
    api.scan_repository(str(secret_root))
    _, bundle = server.dispatch("POST", "/api/system/support-bundle")
    assert bundle["ok"] is True
    raw = base64.b64decode(bundle["content_base64"])
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        blob = zf.read("diagnostics.json").decode("utf-8")
    assert "SECRET_SOURCE_CANARY" not in blob
    assert str(secret_root) not in blob
    assert "[path-redacted]" in blob or "secret_customer" not in blob.lower()


def test_startup_error_page_exists():
    static = Path(__file__).resolve().parents[1] / "static" / "startup-error.html"
    assert static.is_file()
    text = static.read_text(encoding="utf-8")
    assert "Startup check failed" in text
    assert "support.html" in text


def test_static_index_173b_ux_copy():
    html = (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(encoding="utf-8")
    assert "Repository Context" in html
    assert "Create Change Plan" in html
    assert 'onclick="welcomeScanMyRepo()"' in html
    assert "Send to AI" not in html


def test_zero_friction_beginner_copy():
    js = (Path(__file__).resolve().parents[1] / "static" / "atlas_zero_friction.js").read_text(encoding="utf-8")
    assert "beginnerPlanHero" in js
    # RC-1 copy: the hero funnels to a single "Copy for Claude" action.
    assert "Copy for Claude" in js
    assert "applyExportNavVisibility" in js
