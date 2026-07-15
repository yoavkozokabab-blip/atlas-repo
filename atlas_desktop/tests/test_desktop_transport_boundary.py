from __future__ import annotations

import http.client
import json
import shutil
import subprocess
import threading
from types import SimpleNamespace
from pathlib import Path

import pytest

from atlas_desktop import data_paths, server


STATIC = Path(__file__).resolve().parents[1] / "static"


@pytest.fixture(autouse=True)
def _isolated_runtime_data(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(tmp_path / "atlas-data"))
    data_paths.reset_desktop_data_dir_cache()
    yield
    data_paths.reset_desktop_data_dir_cache()


@pytest.fixture()
def atlas_http_server():
    httpd = server.AtlasHTTPServer(("127.0.0.1", 0), server.AtlasHandler)
    port = int(httpd.server_address[1])
    httpd.atlas_runtime_identity = {"pid": 12345, "instance_id": "transport-boundary-test"}
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def _request(port: int, method: str, path: str, headers: dict[str, str] | None = None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request(method, path, headers=headers or {})
    response = conn.getresponse()
    body = response.read()
    response_headers = {name.lower(): value for name, value in response.getheaders()}
    conn.close()
    return response.status, response_headers, body


def test_same_origin_api_and_scoped_options(atlas_http_server):
    port = atlas_http_server
    origin = f"http://127.0.0.1:{port}"

    status, headers, _body = _request(port, "GET", "/api/health")
    assert status == 200
    assert "access-control-allow-origin" not in headers

    status, headers, _body = _request(port, "GET", "/api/health", {"Origin": origin})
    assert status == 200
    assert headers["access-control-allow-origin"] == origin
    assert headers["vary"] == "Origin"
    assert headers["access-control-allow-origin"] != "*"
    assert "access-control-allow-credentials" not in headers

    status, headers, body = _request(
        port,
        "OPTIONS",
        "/api/accounts/state",
        {
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Accept, Content-Type",
        },
    )
    assert status == 204
    assert body == b""
    assert headers["access-control-allow-origin"] == origin
    assert headers["allow"] == "GET, OPTIONS"
    assert headers["access-control-allow-methods"] == "GET"
    assert headers["access-control-allow-headers"] == "Accept, Content-Type"
    assert headers["vary"] == "Origin"
    assert "access-control-allow-credentials" not in headers

    status, headers, body = _request(
        port,
        "OPTIONS",
        "/api/accounts/guest/start",
        {
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert status == 204
    assert body == b""
    assert headers["allow"] == "POST, OPTIONS"
    assert headers["access-control-allow-methods"] == "POST"

    status, _headers, body = _request(port, "GET", "/api/runtime/handshake?challenge=boundary-test")
    handshake = json.loads(body.decode("utf-8"))
    assert status == 200
    assert handshake["ok"] is True
    assert handshake["product"] == "Atlas Desktop"
    assert handshake["protocol"] == "atlas-desktop-runtime-v1"
    assert handshake["challenge"] == "boundary-test"
    assert handshake["port"] == port

    status, headers, body = _request(port, "POST", "/api/runtime/handshake?challenge=boundary-test")
    assert status == 405
    assert headers["allow"] == "GET, OPTIONS"
    assert json.loads(body.decode("utf-8"))["code"] == "method_not_allowed"


@pytest.mark.parametrize(
    ("path", "requested_method"),
    [
        ("/api/accounts/state", "POST"),
        ("/api/accounts/guest/start", "GET"),
        ("/api/not-a-real-route", "GET"),
    ],
)
def test_options_rejects_unknown_or_wrong_route_method(atlas_http_server, path, requested_method):
    port = atlas_http_server
    origin = f"http://127.0.0.1:{port}"
    status, headers, body = _request(
        port,
        "OPTIONS",
        path,
        {"Origin": origin, "Access-Control-Request-Method": requested_method},
    )
    assert status == 403
    assert "access-control-allow-origin" not in headers
    assert json.loads(body.decode("utf-8"))["code"] == "cors_request_rejected"


@pytest.mark.parametrize(
    ("headers", "method"),
    [
        ({"Origin": "https://attacker.example"}, "GET"),
        ({"Origin": "null"}, "GET"),
        ({"Origin": "http://localhost:{port}"}, "GET"),
        ({"Host": "attacker.example:{port}"}, "GET"),
        ({"Host": "127.0.0.1:{port}/unexpected"}, "GET"),
        ({"Host": "127.0.0.1:{port}?unexpected=1"}, "GET"),
        (
            {
                "Origin": "http://127.0.0.1:{port}",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization",
            },
            "OPTIONS",
        ),
    ],
)
def test_unknown_origin_host_and_headers_are_rejected(atlas_http_server, headers, method):
    port = atlas_http_server
    formatted = {name: value.format(port=port) for name, value in headers.items()}
    status, response_headers, body = _request(port, method, "/api/health", formatted)
    assert status == 403
    assert "access-control-allow-origin" not in response_headers
    assert json.loads(body.decode("utf-8"))["ok"] is False


def _run_node(script: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for deterministic frontend transport tests")
    completed = subprocess.run(
        [node, "-"],
        input=script,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return json.loads(completed.stdout)


def test_frontend_canonical_origin_headers_and_fallback_port():
    app_source = (STATIC / "app.js").read_text(encoding="utf-8")
    transport_source = app_source.split("/* Atlas application. */", 1)[0]
    script = f"""
const vm = require("vm");
const source = {json.dumps(transport_source)};
const attrs = {{}};
const calls = [];
let badHandshake = false;
const document = {{
  documentElement: {{ setAttribute(name, value) {{ attrs[name] = value; }} }},
  dispatchEvent() {{}},
}};
const context = {{
  location: {{ origin: "http://127.0.0.1:8778" }},
  document,
  URL,
  Headers,
  AbortController,
  CustomEvent: class CustomEvent {{ constructor(name, options) {{ this.name = name; this.detail = options && options.detail; }} }},
  setTimeout,
  clearTimeout,
  fetch: async (url, options) => {{
    calls.push({{ url, method: options.method, credentials: options.credentials, mode: options.mode, headers: Object.fromEntries(options.headers.entries()), body: options.body }});
    const parsed = new URL(url, "http://127.0.0.1:8778");
    let payload = {{ ok: true }};
    let status = 200;
    if (parsed.pathname === "/api/health") payload = {{ ok: true, product: "ATLAS" }};
    if (parsed.pathname === "/api/runtime/handshake") payload = {{
      ok: true,
      product: badHandshake ? "Aurora" : "Atlas Desktop",
      protocol: "atlas-desktop-runtime-v1",
      challenge: parsed.searchParams.get("challenge"),
      port: 8778,
      pid: 2468,
      instance_id: "test-runtime",
      proof: "a".repeat(64),
    }};
    if (parsed.pathname === "/api/fail") {{ payload = {{ ok: false, error: "deterministic failure" }}; status = 503; }}
    if (parsed.pathname === "/api/product/config") {{ payload = {{ ok: false, error: "product service unavailable" }}; status = 503; }}
    return new Response(JSON.stringify(payload), {{ status, headers: {{ "Content-Type": "application/json", "X-Atlas-Test": "ok" }} }});
  }},
}};
context.window = context;
vm.createContext(context);
vm.runInContext(source, context);
(async () => {{
  await context.atlasTransport.request("/api/health", {{ requireAtlasIdentity: true }});
  const identity = await context.atlasTransport.ensureRuntimeIdentity();
  await context.atlasTransport.request("/api/accounts/state", {{ method: "GET", scope: "account" }});
  await context.atlasTransport.request("/api/accounts/guest/start", {{ method: "POST", body: {{}}, scope: "account" }});
  const availableStates = context.atlasTransport.getStates();
  let httpErrorKind = null;
  try {{ await context.atlasTransport.request("/api/fail", {{ scope: "graph", requireOk: true }}); }} catch (error) {{ httpErrorKind = error.kind; }}
  let productErrorKind = null;
  try {{ await context.atlasTransport.request("/api/product/config", {{ requireOk: true }}); }} catch (error) {{ productErrorKind = error.kind; }}
  const scopedFailureStates = context.atlasTransport.getStates();
  badHandshake = true;
  let badHandshakeKind = null;
  try {{
    await context.atlasTransport.request("/api/runtime/handshake?challenge=bad", {{ scope: "runtime", requireOk: true, requireRuntimeHandshake: true, handshakeChallenge: "bad" }});
  }} catch (error) {{ badHandshakeKind = error.kind; }}
  let absoluteRejected = false;
  let localhostRejected = false;
  try {{ context.atlasTransport.resolveApiUrl("http://127.0.0.1:8777/api/health"); }} catch (_error) {{ absoluteRejected = true; }}
  try {{ context.atlasTransport.resolveApiUrl("http://localhost:8778/api/health"); }} catch (_error) {{ localhostRejected = true; }}
  process.stdout.write(JSON.stringify({{
    origin: context.atlasTransport.origin,
    identity,
    calls,
    availableStates,
    httpErrorKind,
    productErrorKind,
    scopedFailureStates,
    badHandshakeKind,
    absoluteRejected,
    localhostRejected,
    states: context.atlasTransport.getStates(),
    trace: JSON.parse(attrs["data-atlas-transport-trace"]),
  }}));
}})().catch((error) => {{ console.error(error); process.exitCode = 1; }});
"""
    result = _run_node(script)
    assert result["origin"] == "http://127.0.0.1:8778"
    assert result["identity"]["product"] == "Atlas Desktop"
    assert result["identity"]["protocol"] == "atlas-desktop-runtime-v1"
    assert result["calls"][0]["url"].startswith("/api/runtime/handshake?challenge=")
    assert result["calls"][1]["url"] == "/api/health"
    assert result["absoluteRejected"] is True
    assert result["localhostRejected"] is True
    assert all(call["url"].startswith("/api/") for call in result["calls"])
    assert not any("8777" in call["url"] or "localhost" in call["url"] for call in result["calls"])
    assert result["calls"][0]["credentials"] == "same-origin"
    assert result["calls"][0]["mode"] == "same-origin"
    assert result["calls"][0]["headers"]["accept"] == "application/json"
    assert "content-type" not in result["calls"][0]["headers"]
    assert "content-type" not in result["calls"][1]["headers"]
    assert "content-type" not in result["calls"][2]["headers"]
    assert result["calls"][3]["headers"]["content-type"] == "application/json"
    assert all(item["pageOrigin"] == item["requestOrigin"] == result["origin"] for item in result["trace"])
    assert result["availableStates"]["runtime"] == "available"
    assert result["availableStates"]["account"] == "available"
    assert result["httpErrorKind"] == "http_error"
    assert result["productErrorKind"] == "http_error"
    assert result["scopedFailureStates"]["runtime"] == "available"
    assert result["scopedFailureStates"]["auxiliary"] == "http_error"
    assert result["states"]["graph"] == "http_error"
    assert result["badHandshakeKind"] == "identity_mismatch"
    assert result["states"]["runtime"] == "unavailable"


def test_account_failure_preserves_valid_guest_workspace():
    accounts_source = (STATIC / "atlas_accounts.js").read_text(encoding="utf-8")
    script = f"""
const vm = require("vm");
const source = {json.dumps(accounts_source)};
const classes = new Set(["auth-mode", "auth-loading"]);
const chip = {{ textContent: "", className: "", style: {{}}, dataset: {{}}, title: "" }};
const attrs = {{}};
let requests = 0;
const document = {{
  readyState: "loading",
  documentElement: {{ setAttribute(name, value) {{ attrs[name] = value; }} }},
  body: {{ classList: {{
    contains(name) {{ return classes.has(name); }},
    add(name) {{ classes.add(name); }},
    remove(...names) {{ names.forEach(name => classes.delete(name)); }},
    toggle(name, on) {{ if (on === undefined) on = !classes.has(name); if (on) classes.add(name); else classes.delete(name); return on; }},
  }} }},
  getElementById(id) {{ return id === "accountChip" ? chip : null; }},
  querySelectorAll() {{ return []; }},
  querySelector() {{ return null; }},
  addEventListener() {{}},
  dispatchEvent() {{}},
}};
const context = {{
  document,
  CustomEvent: class CustomEvent {{ constructor(name, options) {{ this.name = name; this.detail = options && options.detail; }} }},
  setTimeout() {{ return 1; }},
  clearTimeout() {{}},
  setInterval() {{ return 1; }},
  clearInterval() {{}},
  requestAnimationFrame(fn) {{ fn(); }},
  localStorage: {{ getItem() {{ return null; }}, setItem() {{}}, removeItem() {{}} }},
  sessionStorage: {{ getItem() {{ return null; }}, setItem() {{}}, removeItem() {{}} }},
  scrollTo() {{}},
  bootAtlasApp() {{ context.boots += 1; }},
  go() {{}},
  boots: 0,
  atlasTransport: {{ request: async () => {{
    requests += 1;
    if (requests === 2) return {{ ok: true, guest: true, local_access: true, authenticated: false, signed_in: false, license: {{ valid: true }} }};
    const error = new Error("network"); error.kind = "network_error"; error.code = "transport_network_error"; throw error;
  }} }},
}};
context.window = context;
vm.createContext(context);
vm.runInContext(source, context);
(async () => {{
  const firstFailed = await context.atlasAccounts.refresh();
  const afterFirstFailure = {{
    authMode: classes.has("auth-mode"),
    state: context.atlasAccounts.transportState(),
    chip: {{ textContent: chip.textContent, title: chip.title }},
    boots: context.boots,
  }};
  const firstAccess = context.atlasAccounts.requireAccess();
  await context.atlasAccounts.refresh();
  const afterSuccess = {{ guest: context.atlasAccounts.isGuest(), authMode: classes.has("auth-mode"), state: context.atlasAccounts.transportState() }};
  const failed = await context.atlasAccounts.refresh();
  process.stdout.write(JSON.stringify({{
    firstFailed,
    afterFirstFailure,
    firstAccess,
    afterSuccess,
    failed,
    requests,
    guestPreserved: context.atlasAccounts.isGuest(),
    accessPreserved: context.atlasAccounts.requireAccess(),
    authMode: classes.has("auth-mode"),
    state: context.atlasAccounts.transportState(),
    chip,
    domState: attrs["data-atlas-account-state"],
  }}));
}})().catch((error) => {{ console.error(error); process.exitCode = 1; }});
"""
    result = _run_node(script)
    assert result["firstFailed"]["transport_error"] is True
    assert result["firstAccess"] is False
    assert result["afterFirstFailure"] == {
        "authMode": False,
        "state": "unavailable",
        "chip": {
            "textContent": "Account unavailable",
            "title": "Account endpoint unavailable. Repository features remain available.",
        },
        "boots": 1,
    }
    assert result["afterSuccess"] == {"guest": True, "authMode": False, "state": "available"}
    assert result["failed"]["transport_error"] is True
    assert result["requests"] == 3
    assert result["guestPreserved"] is True
    assert result["accessPreserved"] is True
    assert result["authMode"] is False
    assert result["state"] == result["domState"] == "unavailable"
    assert result["chip"]["textContent"] == "Local guest mode"


def test_frontend_blocks_api_requests_when_handshake_fails():
    app_source = (STATIC / "app.js").read_text(encoding="utf-8")
    transport_source = app_source.split("/* Atlas application. */", 1)[0]
    script = f"""
const vm = require("vm");
const source = {json.dumps(transport_source)};
const calls = [];
const document = {{
  documentElement: {{ setAttribute() {{}} }},
  dispatchEvent() {{}},
}};
const context = {{
  location: {{ origin: "http://127.0.0.1:8778" }},
  document,
  URL,
  Headers,
  AbortController,
  CustomEvent: class CustomEvent {{ constructor(name, options) {{ this.name = name; this.detail = options && options.detail; }} }},
  setTimeout,
  clearTimeout,
  fetch: async (url) => {{
    calls.push(url);
    const parsed = new URL(url, "http://127.0.0.1:8778");
    const payload = {{
      ok: true,
      product: "Aurora",
      protocol: "atlas-desktop-runtime-v1",
      challenge: parsed.searchParams.get("challenge"),
      port: 8778,
      pid: 9988,
      instance_id: "foreign-runtime",
      proof: "b".repeat(64),
    }};
    return new Response(JSON.stringify(payload), {{ status: 200, headers: {{ "Content-Type": "application/json" }} }});
  }},
}};
context.window = context;
vm.createContext(context);
vm.runInContext(source, context);
(async () => {{
  let kind = null;
  try {{ await context.atlasTransport.request("/api/accounts/state", {{ scope: "account" }}); }}
  catch (error) {{ kind = error.kind; }}
  process.stdout.write(JSON.stringify({{ calls, kind, states: context.atlasTransport.getStates(), trace: context.atlasTransport.getTrace() }}));
}})().catch((error) => {{ console.error(error); process.exitCode = 1; }});
"""
    result = _run_node(script)
    assert result["kind"] == "identity_mismatch"
    assert len(result["calls"]) == 1
    assert result["calls"][0].startswith("/api/runtime/handshake?challenge=")
    assert not any("/api/accounts/state" in url for url in result["calls"])
    assert result["states"]["runtime"] == "unavailable"
    assert result["states"]["account"] == "unknown"
    assert len(result["trace"]) == 1


def test_global_status_uses_atlas_health_not_repository_or_account_failure():
    shell_source = (STATIC / "desktop-shell.js").read_text(encoding="utf-8")
    script = f"""
const vm = require("vm");
const source = {json.dumps(shell_source)};
const readiness = {{ dataset: {{}} }};
const label = {{ textContent: "Starting" }};
const requested = [];
const document = {{
  readyState: "loading",
  getElementById(id) {{ return id === "globalReadiness" ? readiness : id === "globalReadinessLabel" ? label : null; }},
  addEventListener() {{}},
  querySelector() {{ return null; }},
  querySelectorAll() {{ return []; }},
  body: {{ classList: {{ contains() {{ return false; }} }} }},
}};
const context = {{
  document,
  location: {{ origin: "http://127.0.0.1:8778" }},
  URL,
  STATE: {{ summary: null }},
  AtlasRepositoryState: {{ publish() {{ return {{ hasRepo: false }}; }} }},
  api: async (path, method, body, options) => {{
    requested.push(path);
    if (path === "/api/health") return {{ ok: true, product: "ATLAS", persistence: {{ resume_card: {{ freshness_status: "fresh", validation_status: "valid" }} }} }};
    if (path === "/api/repositories/current/summary") throw Object.assign(new Error("repository network failure"), {{ kind: "network_error", optional: true }});
    throw new Error("unexpected endpoint " + path);
  }},
  setTimeout() {{ return 1; }},
  clearTimeout() {{}},
  setInterval() {{ return 1; }},
  clearInterval() {{}},
  MutationObserver: class MutationObserver {{ observe() {{}} }},
  requestAnimationFrame() {{}},
}};
context.window = context;
vm.createContext(context);
vm.runInContext(source, context);
(async () => {{
  await context.atlasDesktopShell.updateGlobalStatus();
  process.stdout.write(JSON.stringify({{ label: label.textContent, state: readiness.dataset.state, requested }}));
}})().catch((error) => {{ console.error(error); process.exitCode = 1; }});
"""
    result = _run_node(script)
    assert result["label"] == "No repository loaded"
    assert result["state"] == "idle"
    assert "/api/health" in result["requested"]
    assert not any(path.startswith("/api/runtime/handshake") for path in result["requested"])
    assert not any(path.startswith("/api/accounts/") for path in result["requested"])


def test_restored_home_graph_and_ask_render_deterministically_without_scan():
    app_source = (STATIC / "app.js").read_text(encoding="utf-8")
    workbench_source = (STATIC / "workbench-v3.js").read_text(encoding="utf-8")
    home_source = "const HOME_AGENT_LABELS" + app_source.split(
        "const HOME_AGENT_LABELS", 1
    )[1].split("async function refreshHomeExperience", 1)[0]
    graph_helpers = "function graphUnderlyingTotals" + app_source.split(
        "function graphUnderlyingTotals", 1
    )[1].split("function graphViewToastMessage", 1)[0]
    graph_renderer = "function renderGraphModeMetrics" + app_source.split(
        "function renderGraphModeMetrics", 1
    )[1].split("function renderGraphRenderDiagnostics", 1)[0]
    ask_renderer = "async function renderAskPage" + app_source.split(
        "async function renderAskPage", 1
    )[1].split("function launchCopilotQuestions", 1)[0]
    script = f"""
const vm = require("vm");
function element(id) {{
  const classes = new Set();
  return {{
    id, dataset: {{}}, style: {{}}, textContent: "", innerHTML: "", hidden: false,
    disabled: false, parentElement: {{ hidden: false }},
    classList: {{ toggle(name, on) {{ if (on) classes.add(name); else classes.delete(name); }} }},
    setAttribute(name, value) {{ this[name] = value; }}, addEventListener() {{}},
    querySelector() {{ return null; }}, querySelectorAll() {{ return []; }},
  }};
}}
const summary = {{
  ok: true, repo_name: "atlas-rc1-clean", repo_path: "C:/J.A.R.V.I.S/atlas-rc1-clean",
  file_count: 20877, module_count: 382, dependency_edges: 481, subsystem_count: 28,
  graph_health: {{ label: "healthy", import_cycles: 0, unresolved_internal: 0 }},
  recommended_questions: ["Where is runtime startup implemented?"],
}};

const homeElements = {{ homeDashboard: element("homeDashboard") }};
const panels = ["empty", "indexed", "productive"].map((name) => {{
  const panel = element(`panel-${{name}}`); panel.dataset.homePanel = name; return panel;
}});
homeElements.homeDashboard.querySelectorAll = () => panels;
const homeContext = {{
  STATE: {{
    summary,
    homeMcpStatus: {{ ok: true, claude: {{ atlas_configured: false }}, cursor: {{ atlas_configured: false }}, codex: {{ atlas_configured: true }} }},
    homeTrustStatus: {{ ok: true, fresh: true, user_trust_label: "Fresh" }},
    homeHealth: {{ persistence: {{ restored: true }} }},
    homeRecent: [{{ repo_path: summary.repo_path, last_scan_at: "2026-07-14T10:00:00Z" }}],
  }},
  $: (id) => homeElements[id] || (homeElements[id] = element(id)),
  atlasActivity: {{ render() {{}} }},
}};
homeContext.window = homeContext;
vm.createContext(homeContext);
vm.runInContext({json.dumps(home_source)}, homeContext);
const homeState = homeContext.renderHomeExperience();

const graphElements = {{}};
const moduleNodes = Array.from({{ length: 382 }}, (_, index) => ({{ id: `module-${{index}}` }}));
const moduleLinks = Array.from({{ length: 481 }}, (_, index) => ({{
  source: `module-${{index % 382}}`, target: `module-${{(index + 1) % 382}}`,
}}));
const graphContext = {{
  STATE: {{ graphView: "module", graphPerf: null }},
  $: (id) => graphElements[id] || (graphElements[id] = element(id)),
  renderMassiveModeBanner() {{}}, renderGraphRenderDiagnostics() {{}},
}};
graphContext.window = graphContext;
vm.createContext(graphContext);
vm.runInContext({json.dumps(graph_helpers + graph_renderer)}, graphContext);
graphContext.renderGraphModeMetrics(summary, {{ node_count: 382, link_count: 481, nodes: moduleNodes, links: moduleLinks }});

const workbenchElements = {{}};
const workbenchRequests = [];
const workbenchDocument = {{
  readyState: "loading",
  body: {{ classList: {{ toggle() {{}}, contains() {{ return false; }} }} }},
  getElementById(id) {{ return workbenchElements[id] || (workbenchElements[id] = element(id)); }},
  addEventListener() {{}}, querySelector() {{ return null; }}, querySelectorAll() {{ return []; }},
}};
const agentStatus = {{ ok: true, claude: {{ atlas_configured: false }}, cursor: {{ atlas_configured: false }}, codex: {{ atlas_configured: true }} }};
const workbenchContext = {{
  document: workbenchDocument, STATE: {{ summary }},
  $: (id) => workbenchDocument.getElementById(id),
  api: async (path) => {{
    workbenchRequests.push(path);
    if (path === "/api/repositories/current/graph?view=subsystem") return {{ ok: true, nodes: moduleNodes.slice(0, 14), links: moduleLinks.slice(0, 20) }};
    if (path === "/api/history") return {{ ok: true, items: [] }};
    if (path === "/api/repositories/recent") return {{ ok: true, items: [] }};
    if (path === "/api/health") return {{ ok: true, persistence: {{ restored: true, resume_card: {{ freshness_status: "fresh", validation_status: "valid" }} }} }};
    if (path === "/api/repositories/current/trust-status") return {{ ok: true, fresh: true, user_trust_label: "Fresh" }};
    throw new Error(`unexpected endpoint ${{path}}`);
  }},
  atlasMcpSetup: {{ loadStatus: async () => agentStatus }},
  requestAtlasTrustStatus: async () => ({{ ok: true, fresh: true, user_trust_label: "Fresh" }}),
  atlasActivity: {{ render() {{}} }},
  setTimeout() {{ return 1; }}, clearTimeout() {{}}, Event: class Event {{}},
}};
workbenchContext.window = workbenchContext;
vm.createContext(workbenchContext);
vm.runInContext({json.dumps(home_source)}, workbenchContext);
vm.runInContext({json.dumps(workbench_source)}, workbenchContext);

const askElements = {{}};
const requests = [];
const askContext = {{
  $: (id) => askElements[id] || (askElements[id] = element(id)),
  ensureRepoSummary: async () => {{ requests.push("/api/repositories/current/summary"); return summary; }},
  renderCopilotSuggestions: () => "<button>Grounded question</button>",
  repoRequiredEmptyHtml: (message) => message,
}};
askContext.window = askContext;
vm.createContext(askContext);
vm.runInContext({json.dumps(ask_renderer)}, askContext);
(async () => {{
  await workbenchContext.atlasWorkbench.renderHomeWorkbench();
  await askContext.renderAskPage();
  process.stdout.write(JSON.stringify({{
    home: {{
      state: homeState,
      repo: homeElements.homeRepoName.textContent,
      files: homeElements.homeFileCount.textContent,
      modules: homeElements.homeNodeCount.textContent,
      edges: homeElements.homeEdgeCount.textContent,
      freshness: homeElements.homeFreshness.textContent,
      restored: homeElements.homeRestoreStatus.textContent,
    }},
    graph: {{
      metrics: graphElements.graphScaleHeader.innerHTML,
      summary: graphElements.graphEntitySummary.textContent,
      nodes: moduleNodes.length,
      links: moduleLinks.length,
    }},
    workbenchHome: {{
      state: workbenchElements.homeDashboard.dataset.homeState,
      modules: workbenchElements.homeMetricModules.textContent,
      edges: workbenchElements.homeMetricEdges.textContent,
      subsystems: workbenchElements.homeMetricSubsystems.textContent,
      health: workbenchElements.homeMetricHealth.textContent,
      memory: workbenchElements.homeMemoryState.textContent,
    }},
    ask: {{
      status: askElements.askStatus.textContent,
      panel: askElements.askPanel.style.display,
      empty: askElements.askEmptyState.style.display,
      inputDisabled: askContext.$("askInput").disabled,
    }},
    requests: [...requests, ...workbenchRequests],
  }}));
}})().catch((error) => {{ console.error(error); process.exitCode = 1; }});
"""
    result = _run_node(script)
    assert result["home"] == {
        "state": "productive",
        "repo": "atlas rc1 clean",
        "files": "20,877",
        "modules": "382",
        "edges": "481",
        "freshness": "Fresh",
        "restored": "Repository restored",
    }
    assert "382" in result["graph"]["metrics"] and "modules" in result["graph"]["metrics"]
    assert "481" in result["graph"]["metrics"] and "dependencies" in result["graph"]["metrics"]
    assert result["graph"]["summary"] == "Showing 382 of 382 modules"
    assert result["graph"]["nodes"] == 382
    assert result["graph"]["links"] == 481
    assert result["workbenchHome"] == {
        "state": "productive",
        "modules": "382",
        "edges": "481",
        "subsystems": "28",
        "health": "healthy",
        "memory": "Memory restored",
    }
    assert result["ask"] == {
        "status": "atlas-rc1-clean ready for questions.",
        "panel": "block",
        "empty": "none",
        "inputDisabled": False,
    }
    assert result["requests"] == [
        "/api/repositories/current/summary",
        "/api/repositories/current/graph?view=subsystem",
        "/api/history",
        "/api/repositories/recent",
        "/api/health",
    ]
    assert not any("/scan" in path for path in result["requests"])


def test_restored_memory_leaves_checking_state_without_scan():
    shell_source = (STATIC / "desktop-shell.js").read_text(encoding="utf-8")
    script = f"""
const vm = require("vm");
const source = {json.dumps(shell_source)};
function element(id) {{ return {{ id, dataset: {{}}, style: {{}}, textContent: "", innerHTML: "" }}; }}
const elements = {{}};
const requested = [];
const summary = {{
  ok: true, repo_name: "atlas-rc1-clean", file_count: 20877, module_count: 382,
  dependency_edges: 481, evidence_coverage: {{ symbol_count: 1200, files_with_symbols: 900 }},
  graph_health: {{ label: "healthy", unresolved_internal: 0 }}, subsystems: ["desktop runtime"],
}};
const document = {{
  readyState: "loading",
  getElementById(id) {{ return elements[id] || (elements[id] = element(id)); }},
  addEventListener() {{}}, querySelectorAll() {{ return []; }}, querySelector() {{ return null; }},
  body: {{ classList: {{ contains() {{ return false; }} }} }},
}};
const context = {{
  document,
  api: async (path) => {{
    requested.push(path);
    if (path === "/api/repositories/current/summary") return summary;
    if (path === "/api/history") return {{ ok: true, items: [] }};
    if (path === "/api/system/diagnostics") return {{ ok: true, trust_integrity: {{ memory_persistence_status: "ok" }} }};
    if (path === "/api/health") return {{ ok: true, persistence: {{ ok: true, restored: true, resume_card: {{ freshness_status: "fresh", validation_status: "valid" }} }} }};
    throw new Error(`unexpected endpoint ${{path}}`);
  }},
  setTimeout() {{ return 1; }}, clearTimeout() {{}}, setInterval() {{ return 1; }}, clearInterval() {{}},
  MutationObserver: class MutationObserver {{ observe() {{}} }}, requestAnimationFrame() {{}},
  location: {{ origin: "http://127.0.0.1:8778" }}, URL,
}};
context.window = context;
vm.createContext(context);
vm.runInContext(source, context);
(async () => {{
  await context.atlasDesktopShell.renderMemory();
  process.stdout.write(JSON.stringify({{
    status: elements.memoryStatusStrip.innerHTML,
    freshness: elements.memoryFreshnessLabel.textContent,
    freshnessState: elements.memoryFreshnessLabel.dataset.state,
    facts: elements.memoryFacts.innerHTML,
    requested,
  }}));
}})().catch((error) => {{ console.error(error); process.exitCode = 1; }});
"""
    result = _run_node(script)
    assert "Checking" not in result["status"]
    assert "Fresh" in result["status"]
    assert result["freshness"] == "Fresh"
    assert result["freshnessState"] == "ready"
    for value in ("atlas-rc1-clean", "20,877", "382", "481", "healthy", "Restored and verified"):
        assert value in result["facts"]
    assert result["requested"] == [
        "/api/repositories/current/summary",
        "/api/history",
        "/api/health",
        "/api/repositories/current/trust-status",
    ]
    assert not any("/scan" in path for path in result["requested"])


def test_transport_is_loaded_before_all_core_clients_and_boot_never_scans():
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    accounts = (STATIC / "atlas_accounts.js").read_text(encoding="utf-8")
    boot = app.split("async function bootAtlasApp()", 1)[1].split("window.bootAtlasApp", 1)[0]
    assert index.index('src="app.js"') < index.index('src="atlas_accounts.js"')
    assert app.startswith("/* Atlas runtime transport boundary.")
    assert "window.atlasTransport.request" in app
    assert "window.atlasTransport.request" in accounts
    assert "const accountRequest = String(path || '').startsWith('/api/accounts/');" in accounts
    assert "...(accountRequest ? { scope: 'account' } : {})" in accounts
    assert "/api/repositories/scan" not in boot
    assert 'normalizedPath === "/api/health"' in app
    assert 'requireRuntimeHandshake: true' in app
    assert 'requireOk: true' in boot
    workbench = (STATIC / "workbench-v3.js").read_text(encoding="utf-8")
    assert "if (nextHomeState === previousHomeState) return;" in workbench
    assert 'if (dash.dataset.homeState !== state) dash.dataset.homeState = state;' in app
    home_details = workbench.split("function renderHomeDetails", 1)[1].split("async function renderHomeWorkbench", 1)[0]
    assert "dataset.homeState =" not in home_details
    for client_name in ("feedback.js", "atlas_acquisition.js", "atlas_admin.js", "workbench-v3.js"):
        client = (STATIC / client_name).read_text(encoding="utf-8")
        assert "fetch(" not in client, client_name


def test_trust_poll_fast_failure_completes_and_retries():
    product = (STATIC / "atlas_product.js").read_text(encoding="utf-8")
    poll_source = "async function atlasPollTrustStatus()" + product.split(
        "async function atlasPollTrustStatus()", 1
    )[1].split("async function atlasRefreshChangedFiles", 1)[0]
    script = f"""
const vm = require("vm");
const source = {json.dumps(poll_source)};
let calls = 0;
const context = {{
  api() {{}},
  setTimeout(fn) {{ return setTimeout(fn, 0); }},
  requestAtlasTrustStatus() {{
    calls += 1;
    return Promise.reject(Object.assign(new Error("fast failure"), {{ kind: "network_error" }}));
  }},
}};
context.window = context;
vm.createContext(context);
vm.runInContext(source, context);
(async () => {{
  const first = await context.atlasPollTrustStatus();
  const second = await context.atlasPollTrustStatus();
  process.stdout.write(JSON.stringify({{
    first,
    second,
    calls,
    requestCleared: context.atlasTrustRequest == null,
    timerCleared: context.atlasTrustPollTimer == null,
  }}));
}})().catch((error) => {{ console.error(error); process.exitCode = 1; }});
"""
    result = _run_node(script)
    assert result == {
        "first": None,
        "second": None,
        "calls": 2,
        "requestCleared": True,
        "timerCleared": True,
    }


@pytest.mark.parametrize("disconnect_stage", ["headers", "body"])
def test_json_response_ignores_client_disconnect(disconnect_stage):
    handler = object.__new__(server.AtlasHandler)
    handler._atlas_cors_origin = None
    handler.send_response = lambda _status: None
    handler.send_header = lambda _name, _value: None
    if disconnect_stage == "headers":
        handler.end_headers = lambda: (_ for _ in ()).throw(ConnectionResetError("closed"))
        handler.wfile = SimpleNamespace(write=lambda _data: None)
    else:
        handler.end_headers = lambda: None
        handler.wfile = SimpleNamespace(write=lambda _data: (_ for _ in ()).throw(BrokenPipeError("closed")))
    handler._send_json(200, {"ok": True})


def test_static_response_and_request_body_ignore_client_disconnect(tmp_path, monkeypatch):
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "asset.txt").write_text("atlas", encoding="utf-8")
    monkeypatch.setattr(server, "STATIC_DIR", str(static_dir))

    handler = object.__new__(server.AtlasHandler)
    handler.path = "/asset.txt"
    handler._atlas_cors_origin = None
    handler.send_response = lambda _status: None
    handler.send_header = lambda _name, _value: None
    handler.end_headers = lambda: (_ for _ in ()).throw(ConnectionAbortedError("closed"))
    handler.wfile = SimpleNamespace(write=lambda _data: None)
    handler._serve_static()

    handler.headers = {"Content-Length": "1"}
    handler.rfile = SimpleNamespace(read=lambda _length: (_ for _ in ()).throw(ConnectionResetError("closed")))
    assert handler._read_body() is None

    dispatched = []
    handler.path = "/api/repositories/scan"
    handler.command = "POST"
    handler.client_address = ("127.0.0.1", 51000)
    handler.server = SimpleNamespace(server_address=("127.0.0.1", 8778))
    handler.headers = {"Host": "127.0.0.1:8778", "Content-Length": "1"}
    monkeypatch.setattr(server, "dispatch", lambda *args, **kwargs: dispatched.append((args, kwargs)))
    handler._route_api()
    assert dispatched == []

    handler.rfile = SimpleNamespace(read=lambda _length: b"")
    handler._route_api()
    assert dispatched == []


def test_fastapi_runtime_handshake_matches_listener_port(monkeypatch):
    pytest.importorskip("fastapi")
    testclient_module = pytest.importorskip("fastapi.testclient")
    monkeypatch.setattr(server.runtime_startup, "write_runtime_descriptor", lambda identity: None)
    app = server.create_fastapi_app()
    client = testclient_module.TestClient(
        app,
        base_url="http://127.0.0.1:8779",
        client=("127.0.0.1", 51000),
    )

    response = client.get("/api/runtime/handshake?challenge=fastapi-boundary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["product"] == "Atlas Desktop"
    assert payload["protocol"] == "atlas-desktop-runtime-v1"
    assert payload["port"] == 8779
    assert payload["challenge"] == "fastapi-boundary"
    assert server.runtime_startup.verify_handshake(payload, "fastapi-boundary", 8779)

    origin = "http://127.0.0.1:8779"
    response = client.get(
        "/api/runtime/handshake?challenge=fastapi-origin",
        headers={"Origin": origin},
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers["vary"] == "Origin"
    assert "access-control-allow-credentials" not in response.headers

    response = client.options(
        "/api/runtime/handshake",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Accept",
        },
    )
    assert response.status_code == 204
    assert response.content == b""
    assert response.headers["allow"] == "GET, OPTIONS"
    assert response.headers["access-control-allow-methods"] == "GET"
    assert response.headers["access-control-allow-headers"] == "Accept"
    assert response.headers["access-control-allow-origin"] == origin

    response = client.options(
        "/api/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )
    assert response.status_code == 403
    assert "access-control-allow-origin" not in response.headers
    assert response.json()["code"] == "cors_request_rejected"

    response = client.options(
        "/api/accounts/state",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 403
    assert response.json()["code"] == "cors_request_rejected"

    for headers in (
        {"Origin": "https://attacker.example"},
        {"Origin": "http://localhost:8779"},
        {"Host": "127.0.0.1:8777"},
    ):
        response = client.get("/api/runtime/handshake?challenge=blocked", headers=headers)
        assert response.status_code == 403
        assert "access-control-allow-origin" not in response.headers
        assert response.json()["code"] == "untrusted_runtime_origin"

    response = client.post("/api/runtime/handshake?challenge=wrong-method")
    assert response.status_code == 405
    assert response.headers["allow"] == "GET, OPTIONS"
    assert response.json()["code"] == "method_not_allowed"

    status, dispatch_payload = server.dispatch("GET", server.runtime_startup.HANDSHAKE_PATH)
    assert status == 400
    assert dispatch_payload["code"] == "http_context_required"


def test_fastapi_client_disconnect_never_dispatches_state_changing_default(monkeypatch):
    import asyncio

    pytest.importorskip("fastapi")
    requests_module = pytest.importorskip("starlette.requests")
    app = server.create_fastapi_app()
    route = next(item for item in app.routes if getattr(item, "path", None) == "/api/system/rebuild-index")
    dispatched = []
    monkeypatch.setattr(
        server.api,
        "rebuild_repository_index",
        lambda *args, **kwargs: dispatched.append((args, kwargs)),
    )

    class DisconnectedRequest:
        async def json(self):
            raise requests_module.ClientDisconnect()

    with pytest.raises(requests_module.ClientDisconnect):
        asyncio.run(route.endpoint(DisconnectedRequest()))
    assert dispatched == []


def test_run_propagates_selected_fallback_port_to_open_url(monkeypatch):
    events = []

    class FakeHTTPServer:
        server_address = ("127.0.0.1", 8778)

        def serve_forever(self):
            events.append(("served", 8778))

        def server_close(self):
            events.append(("closed", 8778))

    class ImmediateThread:
        def __init__(self, *, target, args, kwargs, daemon):
            self.target = target
            self.args = args
            self.kwargs = kwargs
            assert daemon is True

        def start(self):
            self.target(*self.args, **self.kwargs)

    fake_httpd = FakeHTTPServer()
    monkeypatch.setattr(server, "_track_app_started", lambda: None)
    monkeypatch.setattr(server.accounts_service_runner, "ensure_running_async", lambda: None)
    monkeypatch.setattr(server, "_select_runtime", lambda host, port: (fake_httpd, 8778, None))
    monkeypatch.setattr(server.runtime_startup, "new_instance_identity", lambda port: {"port": port, "pid": 123, "instance_id": "fallback"})
    monkeypatch.setattr(server.runtime_startup, "write_runtime_descriptor", lambda identity: None)
    monkeypatch.setattr(server, "_open_after_health", lambda host, port, url, *, mode: events.append((host, port, url, mode)))
    monkeypatch.setattr(server.threading, "Thread", ImmediateThread)

    server.run(host="127.0.0.1", port=8777, open_browser=True, open_mode="app")

    assert ("127.0.0.1", 8778, "http://127.0.0.1:8778/", "app") in events
    assert all("8777" not in str(event) for event in events)
    assert ("served", 8778) in events
    assert ("closed", 8778) in events
