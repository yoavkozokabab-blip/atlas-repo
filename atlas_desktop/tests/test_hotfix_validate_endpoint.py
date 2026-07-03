"""Hotfix — Home validate endpoint must never return Unknown endpoint."""

from __future__ import annotations

import http.client
import json
import re
import threading
from http.server import HTTPServer
from pathlib import Path

import pytest

from atlas_desktop import api, server


@pytest.fixture(autouse=True)
def reset_state():
    api._STATE.update({"path": None, "scan": None, "graph": None, "index": None, "risks": None, "demo_mode": False})
    yield


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "main.py").write_text("def main():\n    return 1\n", encoding="utf-8")
    return root


def _post_json(port: int, path: str, body: dict) -> tuple[int, dict]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("POST", path, json.dumps(body), {"Content-Type": "application/json"})
    resp = conn.getresponse()
    payload = json.loads(resp.read().decode("utf-8"))
    conn.close()
    return resp.status, payload


@pytest.fixture()
def http_server():
    httpd = HTTPServer(("127.0.0.1", 0), server.AtlasHandler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_home_validate_success_over_http(http_server, tmp_path):
    """Home → enter path → Validate → structured success payload."""
    root = _repo(tmp_path)
    status, payload = _post_json(http_server, "/api/repositories/validate", {"path": str(root)})
    assert status == 200
    assert payload["ok"] is True
    assert payload["path"] == str(root.resolve())
    assert payload["code_files"] >= 1
    assert "Unknown endpoint" not in str(payload.get("error", ""))


def test_home_validate_invalid_path_over_http(http_server):
    """Invalid path → Validate → structured validation error (not Unknown endpoint)."""
    status, payload = _post_json(http_server, "/api/repositories/validate", {"path": ""})
    assert status == 200
    assert payload["ok"] is False
    assert payload["code"] == "empty_path"
    assert payload["error"]
    assert "Unknown endpoint" not in payload["error"]


def test_validate_trailing_slash_is_normalized(http_server, tmp_path):
    root = _repo(tmp_path)
    status, payload = _post_json(http_server, "/api/repositories/validate/", {"path": str(root)})
    assert status == 200
    assert payload["ok"] is True
    assert server.route_is_registered("POST", "/api/repositories/validate/")


def test_validate_survives_demo_and_rescan(tmp_path):
    assert api.load_demo_mode("small")["ok"]
    status, payload = server.dispatch("POST", "/api/repositories/validate", {"path": str(_repo(tmp_path))})
    assert status == 200 and payload["ok"]


def _frontend_api_calls() -> list[tuple[str, str, str]]:
    app_js = (Path(__file__).resolve().parents[1] / "static" / "app.js").read_text(encoding="utf-8")
    calls: list[tuple[str, str, str]] = []
    for match in re.finditer(r"""api\(\s*(['"`])(/api/[^'"`?]+)(?:\?[^'"`]*)?\1\s*,\s*(['"`])(GET|POST)\3""", app_js):
        calls.append(("app.js", match.group(2), match.group(4)))
    for match in re.finditer(r"""api\(\s*`(/api/[^`?]+)""", app_js):
        calls.append(("app.js", match.group(1), "GET"))
    # Explicit POST template calls without method literal after path
    if 'api(`/api/repositories/current/module?' in app_js:
        calls.append(("app.js", "/api/repositories/current/module", "GET"))
    if 'api(`/api/repositories/current/graph?' in app_js:
        calls.append(("app.js", "/api/repositories/current/graph", "GET"))
    return calls


def test_frontend_route_audit_table():
    """Every frontend api() call must map to a registered backend route."""
    registered = set(server.ROUTES)
    missing = []
    rows = []
    for source, endpoint, method in _frontend_api_calls():
        key = (method, server.normalize_api_path(endpoint))
        exists = key in registered
        rows.append((source, endpoint, method, exists))
        if not exists:
            missing.append(f"{method} {endpoint}")
    assert not missing, "Missing routes:\n" + "\n".join(missing)


def test_dispatch_registry_covers_routes():
    assert len(server.ROUTES) == len(set(server.ROUTES))
    for method, path in server.ROUTES:
        assert server.route_is_registered(method, path)
