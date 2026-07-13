from pathlib import Path


STATIC = Path(__file__).resolve().parents[1] / "static"


def _read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def test_desktop_shell_assets_and_workspaces_are_shipped():
    html = _read("index.html")
    assert '<link rel="stylesheet" href="desktop-redesign.css" />' in html
    assert '<script src="desktop-shell.js"></script>' in html
    for view in ("memory", "files", "agents", "diagnostics", "settings"):
        assert f'id="view-{view}"' in html
        assert f'data-view="{view}"' in html


def test_desktop_shell_uses_existing_local_api_contracts():
    js = _read("desktop-shell.js")
    for endpoint in (
        "/api/repositories/current/summary",
        "/api/repositories/current/trust-status",
        "/api/repositories/current/graph?view=module",
        "/api/repositories/current/module?target=",
        "/api/system/diagnostics",
        "/api/system/startup-status",
        "/api/system/self-test",
        "/api/integrations/mcp/status",
    ):
        assert endpoint in js
    assert "host.appendChild(setup)" in js
    assert 'byId("mcpSetupSection")' in js
    assert "Promise.allSettled" in js
    assert "request_failures" in js
    assert "startupReady && installerReady && repositoryReady && memoryVerified" in js


def test_desktop_shell_includes_keyboard_and_status_affordances():
    html = _read("index.html")
    js = _read("desktop-shell.js")
    assert 'class="skip-link"' in html
    assert 'role="progressbar"' in html
    assert 'aria-label="Atlas workspaces"' in html
    assert 'aria-label="Repository relationship graph"' in html
    assert 'role="dialog"' in html
    assert 'event.key === "Enter" || event.key === " "' in js


def test_graph_warning_only_appears_for_real_degradation():
    app = _read("app.js")
    assert 'partial ? sum.graph_health?.notice : ""' in app
    assert 'el.textContent = ""' in app
    assert "toggleModuleBrowsePanel" in app
