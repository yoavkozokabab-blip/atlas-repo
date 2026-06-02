"""Phase 116C - native Browse flow and frontend/backend route parity."""

from __future__ import annotations

import re
from pathlib import Path

from jarvis_desktop import server, system_browse

STATIC_DIR = Path(__file__).resolve().parents[1] / "static"


def test_browse_endpoint_returns_selected_path(monkeypatch, tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.setattr(system_browse, "_pick_folder_native", lambda: str(root))

    status, payload = server.dispatch("POST", "/api/system/browse-folder")

    assert status == 200
    assert payload == {
        "ok": True,
        "supported": True,
        "cancelled": False,
        "path": str(root.resolve()),
    }


def test_browse_endpoint_handles_cancel(monkeypatch):
    monkeypatch.setattr(system_browse, "_pick_folder_native", lambda: "")

    status, payload = server.dispatch("POST", "/api/system/browse-folder")

    assert status == 200
    assert payload["ok"] is True
    assert payload["supported"] is True
    assert payload["cancelled"] is True
    assert payload["path"] is None


def test_browse_endpoint_handles_unsupported_environment(monkeypatch):
    def _raise() -> str:
        raise RuntimeError("no desktop session")

    monkeypatch.setattr(system_browse, "_pick_folder_native", _raise)

    status, payload = server.dispatch("POST", "/api/system/browse-folder")

    assert status == 200
    assert payload["ok"] is False
    assert payload["supported"] is False
    assert payload["cancelled"] is False
    assert payload["code"] == "unsupported_browse_dialog"
    assert payload["message"] == "Paste the folder path manually."
    assert payload["reason_type"] == "RuntimeError"
    assert "no desktop session" not in str(payload)


def test_native_browse_route_is_localhost_only():
    assert server._is_loopback_host("127.0.0.1")
    assert server._is_loopback_host("::1")
    assert not server._is_loopback_host("192.0.2.10")


def test_frontend_browse_updates_input_then_validates():
    app = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    start = app.index("async function browseRepoFolder()")
    end = app.index("function focusCopilot()", start)
    browse = app[start:end]

    assert 'api("/api/system/browse-folder", "POST", {})' in browse
    assert '$("repoPath").value = res.path;' in browse
    assert "await validateRepoPath(true);" in browse
    assert browse.index('$("repoPath").value = res.path;') < browse.index("await validateRepoPath(true);")
    assert 'id="browseRepoBtn"' in html
    assert 'onclick="browseRepoFolder()"' in html


def test_manual_input_scan_and_recent_repo_flow_remain_present():
    app = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    assert 'id="repoPath"' in html
    assert 'onclick="scanFlow()"' in html
    assert 'const validation = await validateRepoPath(true);' in app
    assert "function selectRecentPath(p)" in app
    assert '$("repoPath").value = p;' in app
    assert "validateRepoPath(false);" in app


def test_copilot_send_button_has_one_click_execution_path():
    app = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    assert 'id="askSend" onclick="sendCopilotQuestion()"' in html
    assert '$("askSend").addEventListener("click", sendCopilotQuestion);' not in app


def test_screenshot_mode_keeps_a_visible_exit_control():
    app = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    css = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")

    assert 'id="screenshotExitBtn"' in html
    assert 'onclick="exitPresentationMode()"' in html
    assert '$("screenshotExitBtn").style.display = STATE.screenshotMode ? "block" : "none";' in app
    assert "function exitPresentationMode()" in app
    assert "if (STATE.productTourActive) { stopProductTour(); return; }" in app
    assert "function stopProductTour()" in app
    assert "stopRepositoryTour();" in app
    assert "body.screenshot-mode .screenshot-exit{display:block!important}" in css


def _frontend_api_calls() -> set[tuple[str, str]]:
    calls: set[tuple[str, str]] = set()
    sources = [
        STATIC_DIR / "app.js",
        STATIC_DIR / "studio.js",
        STATIC_DIR / "admin.html",
        STATIC_DIR / "marketing.js",
    ]
    for source in sources:
        text = source.read_text(encoding="utf-8")
        for match in re.finditer(r"""\bapi\(\s*["`](/api/[^"`?]+)(?:\?[^"`]*)?["`](?:\s*,\s*["`](GET|POST)["`])?""", text):
            calls.add(((match.group(2) or "GET"), server.normalize_api_path(match.group(1))))
        for match in re.finditer(r"""\bjget\(\s*["`](/api/[^"`?]+)""", text):
            calls.add(("GET", server.normalize_api_path(match.group(1))))
        for match in re.finditer(r"""\bjpost\(\s*["`](/api/[^"`?]+)""", text):
            calls.add(("POST", server.normalize_api_path(match.group(1))))
        for match in re.finditer(r"""\bfetch\(\s*"(/api/[^"?]+)"([^)]*)\)""", text):
            method = "POST" if re.search(r"""method\s*:\s*["']POST["']""", match.group(2)) else "GET"
            calls.add((method, server.normalize_api_path(match.group(1))))
    return calls


def test_every_frontend_api_call_has_backend_route():
    registered = set(server.ROUTES)
    calls = _frontend_api_calls()
    missing = sorted(calls - registered)
    assert ("POST", "/api/system/browse-folder") in calls
    assert not missing, "Frontend endpoints missing backend routes:\n" + "\n".join(
        f"{method} {path}" for method, path in missing
    )
