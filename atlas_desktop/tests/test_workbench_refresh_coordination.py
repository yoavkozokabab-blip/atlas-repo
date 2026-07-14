from __future__ import annotations

import json
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

from atlas_desktop import api, server, trust_integrity


ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "atlas_desktop" / "static"


def _run_node(script: str) -> dict:
    completed = subprocess.run(
        ["node", "-"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        input=script,
    )
    if completed.returncode:
        raise AssertionError(completed.stderr or completed.stdout)
    return json.loads(completed.stdout)


def test_twenty_identical_consumers_share_one_request_and_expected_cancel_is_not_transport_error() -> None:
    app_source = (STATIC / "app.js").read_text(encoding="utf-8")
    transport_source = app_source.split("/* Atlas application. */", 1)[0]
    script = r"""
const vm = require("vm");
const source = __SOURCE__;
const calls = [];
let diagnosticsRelease = null;
let recentRelease = null;
let diagnosticsCalls = 0;
const attrs = {};
const document = {
  hidden: false,
  documentElement: { setAttribute(name, value) { attrs[name] = value; } },
  dispatchEvent() {},
};
const context = {
  location: { origin: "http://127.0.0.1:8778" }, document, URL, URLSearchParams,
  Headers, AbortController, Response,
  CustomEvent: class CustomEvent { constructor(name, options) { this.name = name; this.detail = options && options.detail; } },
  setTimeout, clearTimeout,
  fetch: async (url) => {
    calls.push(url);
    const parsed = new URL(url, "http://127.0.0.1:8778");
    if (parsed.pathname === "/api/runtime/handshake") {
      return new Response(JSON.stringify({ ok: true, product: "Atlas Desktop", protocol: "atlas-desktop-runtime-v1", challenge: parsed.searchParams.get("challenge"), port: 8778, pid: 42, instance_id: "test", proof: "a".repeat(64) }), { status: 200, headers: { "Content-Type": "application/json" } });
    }
    if (parsed.pathname === "/api/system/diagnostics") {
      diagnosticsCalls += 1;
      if (diagnosticsCalls <= 2) await new Promise((resolve) => { diagnosticsRelease = resolve; });
      return new Response(JSON.stringify({ ok: true, diagnosticsCalls }), { status: 200, headers: { "Content-Type": "application/json" } });
    }
    if (parsed.pathname === "/api/repositories/recent") {
      await new Promise((resolve) => { recentRelease = resolve; });
      return new Response(JSON.stringify({ ok: true, items: [] }), { status: 200, headers: { "Content-Type": "application/json" } });
    }
    throw new Error("unexpected " + parsed.pathname);
  },
};
context.window = context;
vm.createContext(context);
vm.runInContext(source, context);
const waitFor = async (predicate) => { for (let i = 0; i < 100 && !predicate(); i += 1) await new Promise((resolve) => setTimeout(resolve, 1)); };
(async () => {
  const consumers = Array.from({ length: 20 }, () => context.atlasRequestCoordinator.request("/api/system/diagnostics", { method: "GET" }));
  const promiseIdentityCount = new Set(consumers).size;
  await waitFor(() => diagnosticsRelease);
  diagnosticsRelease();
  await Promise.all(consumers);
  const callsAfterTwenty = calls.filter((url) => String(url).includes("/api/system/diagnostics")).length;
  await context.atlasRequestCoordinator.request("/api/system/diagnostics", { method: "GET" });
  const callsAfterCache = calls.filter((url) => String(url).includes("/api/system/diagnostics")).length;

  const forced = Array.from({ length: 20 }, () => context.atlasRequestCoordinator.request("/api/system/diagnostics", { method: "GET", force: true }));
  await waitFor(() => diagnosticsCalls === 2 && diagnosticsRelease);
  diagnosticsRelease();
  await Promise.all(forced);

  const controller = new AbortController();
  const cancelled = context.atlasRequestCoordinator.request("/api/repositories/recent", { method: "GET", signal: controller.signal });
  const cancelledResultPromise = cancelled.then(() => null, (error) => ({ name: error.name, kind: error.kind, expected: error.expected }));
  const survivor = context.atlasRequestCoordinator.request("/api/repositories/recent", { method: "GET" });
  controller.abort();
  await waitFor(() => recentRelease);
  recentRelease();
  const cancelledResult = await cancelledResultPromise;
  const survivorResult = await survivor;
  const state = context.atlasRequestCoordinator.getState();
  process.stdout.write(JSON.stringify({ promiseIdentityCount, callsAfterTwenty, callsAfterCache, diagnosticsCalls, cancelledResult, survivorResult, inflight: state.inflight, trace: state.trace, auroraCalls: calls.filter((url) => String(url).includes(":8777")) }));
})().catch((error) => { console.error(error); process.exitCode = 1; });
""".replace("__SOURCE__", json.dumps(transport_source))
    result = _run_node(script)
    assert result["promiseIdentityCount"] == 1
    assert result["callsAfterTwenty"] == result["callsAfterCache"] == 1
    assert result["diagnosticsCalls"] == 2
    assert result["cancelledResult"] == {"name": "AbortError", "kind": "cancelled", "expected": True}
    assert result["survivorResult"]["ok"] is True
    assert result["inflight"] == []
    assert result["auroraCalls"] == []
    assert any(entry["type"] == "coalesced" and entry.get("consumers") == 20 for entry in result["trace"])


def test_memory_state_order_navigation_repository_switch_and_supersession_are_deterministic() -> None:
    shell_source = (STATIC / "desktop-shell.js").read_text(encoding="utf-8")
    script = r"""
const vm = require("vm");
const source = __SOURCE__;
function element(id) { return { id, dataset: {}, style: {}, textContent: "", innerHTML: "", classList: { contains() { return false; }, toggle() {} }, querySelectorAll() { return []; }, addEventListener() {}, appendChild(child) { child.parentElement = this; } }; }
function deferred() { let resolve, reject; const promise = new Promise((res, rej) => { resolve = res; reject = rej; }); return { promise, resolve, reject }; }
function batch(repo) { return { repo, summary: deferred(), history: deferred(), health: deferred(), trust: deferred() }; }
const elements = {};
let active = { id: "view-memory" };
let current = null;
const listeners = {};
let intervals = 0;
const document = {
  readyState: "loading", hidden: false,
  body: { classList: { contains() { return false; } } },
  getElementById(id) { return elements[id] || (elements[id] = element(id)); },
  querySelector(selector) { return selector === ".view.active" ? active : null; },
  querySelectorAll() { return []; },
  addEventListener(name, fn) { (listeners[name] || (listeners[name] = [])).push(fn); },
  dispatchEvent(event) { (listeners[event.type || event.name] || []).forEach((fn) => fn(event)); },
};
function abortable(source, signal) {
  if (!signal) return source.promise;
  if (signal.aborted) return Promise.reject(Object.assign(new Error("cancelled"), { name: "AbortError", kind: "cancelled" }));
  return new Promise((resolve, reject) => {
    const cancel = () => reject(Object.assign(new Error("cancelled"), { name: "AbortError", kind: "cancelled" }));
    signal.addEventListener("abort", cancel, { once: true });
    source.promise.then((value) => { signal.removeEventListener("abort", cancel); resolve(value); }, (error) => { signal.removeEventListener("abort", cancel); reject(error); });
  });
}
const context = {
  document, location: { origin: "http://127.0.0.1:8778" }, URL, AbortController,
  CustomEvent: class CustomEvent { constructor(type, options) { this.type = type; this.detail = options && options.detail; } },
  STATE: { summary: { ok: true, repo_name: "A", repo_path: "C:/A" } },
  api(path, _method, _body, options) {
    const target = path === "/api/repositories/current/summary" ? current.summary : path === "/api/history" ? current.history : current.health;
    return abortable(target, options && options.signal);
  },
  requestAtlasTrustStatus(options) { return abortable(current.trust, options && options.signal); },
  setTimeout, clearTimeout,
  setInterval() { intervals += 1; return intervals; }, clearInterval() {},
  requestAnimationFrame(fn) { fn(); }, scrollTo() {},
  MutationObserver: class MutationObserver { observe() {} },
};
context.window = context;
vm.createContext(context);
vm.runInContext(source, context);
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));
const summary = (repo) => ({ ok: true, repo_name: repo, repo_path: `C:/${repo}`, file_count: 20, module_count: 4, dependency_edges: 3, graph_health: { label: "healthy", unresolved_internal: 0 }, evidence_coverage: { symbol_count: 8, files_with_symbols: 5 }, subsystems: [] });
const history = { ok: true, items: [] };
const health = { ok: true, persistence: { ok: true, restored: true, resume_card: { freshness_status: "fresh", validation_status: "valid" } } };
const trust = { ok: true, fresh: true, user_trust_label: "Fresh", trust_status: { fresh: true } };
async function settle(run, b, order) {
  for (const item of order) {
    if (item === "summary") b.summary.resolve(summary(b.repo));
    if (item === "history") b.history.resolve(history);
    if (item === "health") b.health.resolve(health);
    if (item === "trust") b.trust.resolve(trust);
    await tick();
  }
  return run;
}
(async () => {
  current = batch("facts-first"); context.STATE.summary = summary("facts-first");
  const factsRun = context.atlasDesktopShell.renderMemory();
  current.summary.resolve(summary("facts-first")); await tick(); await tick();
  const factsBeforeTrust = { state: context.atlasDesktopShell.memory.state, facts: elements.memoryFacts.innerHTML, status: elements.memoryStatusStrip.innerHTML };
  current.history.resolve(history); current.health.resolve(health); current.trust.resolve(trust);
  const factsFinal = await factsRun;

  current = batch("trust-first"); context.STATE.summary = summary("trust-first");
  const trustRun = context.atlasDesktopShell.renderMemory();
  current.trust.resolve(trust); current.history.resolve(history); current.health.resolve(health); await tick(); current.summary.resolve(summary("trust-first"));
  const trustFinal = await trustRun;

  current = batch("optional-timeout"); context.STATE.summary = summary("optional-timeout");
  const timeoutRun = context.atlasDesktopShell.renderMemory();
  current.summary.resolve(summary("optional-timeout")); current.history.resolve(history); current.health.resolve(health); current.trust.reject(Object.assign(new Error("slow trust"), { kind: "timeout" }));
  const timeoutFinal = await timeoutRun;

  current = batch("navigation"); context.STATE.summary = summary("navigation");
  const navigationRun = context.atlasDesktopShell.renderMemory();
  active = { id: "view-home" }; context.atlasDesktopShell.cancelMemoryRender("navigation");
  const navigationFinal = await navigationRun;

  active = { id: "view-memory" };
  const oldBatch = batch("old"); current = oldBatch; context.STATE.summary = summary("old");
  const oldRun = context.atlasDesktopShell.renderMemory();
  context.atlasDesktopShell.cancelMemoryRender("repository_switch", true);
  const newBatch = batch("new"); current = newBatch; context.STATE.summary = summary("new");
  const newRun = context.atlasDesktopShell.renderMemory();
  await settle(newRun, newBatch, ["trust", "health", "history", "summary"]);
  oldBatch.summary.resolve(summary("old")); oldBatch.history.resolve(history); oldBatch.health.resolve(health); oldBatch.trust.resolve(trust);
  const oldFinal = await oldRun;

  const staleBatch = batch("stale"); current = staleBatch; context.STATE.summary = summary("stale");
  const staleRun = context.atlasDesktopShell.renderMemory();
  const newestBatch = batch("newest"); current = newestBatch; context.STATE.summary = summary("newest");
  const newestRun = context.atlasDesktopShell.renderMemory();
  await settle(newestRun, newestBatch, ["summary", "history", "health", "trust"]);
  staleBatch.summary.resolve(summary("stale")); staleBatch.history.resolve(history); staleBatch.health.resolve(health); staleBatch.trust.resolve(trust);
  const staleFinal = await staleRun;

  context.atlasDesktopShell.init();
  const listenerCount = Object.values(listeners).reduce((total, rows) => total + rows.length, 0);
  context.atlasDesktopShell.init();
  process.stdout.write(JSON.stringify({
    factsBeforeTrust, factsFinal, trustFinal, timeoutFinal, navigationFinal, oldFinal, staleFinal,
    finalState: context.atlasDesktopShell.memory.state,
    finalRepo: context.atlasDesktopShell.memory.data.summary.repo_name,
    finalStatus: elements.memoryStatusStrip.innerHTML,
    intervals, listenerCount,
    listenerCountAfterSecondInit: Object.values(listeners).reduce((total, rows) => total + rows.length, 0),
  }));
})().catch((error) => { console.error(error); process.exitCode = 1; });
""".replace("__SOURCE__", json.dumps(shell_source))
    result = _run_node(script)
    assert result["factsBeforeTrust"]["state"] == "partial"
    assert "facts-first" in result["factsBeforeTrust"]["facts"]
    assert "Checking" not in result["factsBeforeTrust"]["status"]
    assert result["factsFinal"] == result["trustFinal"] == result["timeoutFinal"] == "loaded_fresh"
    assert result["navigationFinal"] is None
    assert result["oldFinal"] is None
    assert result["staleFinal"] is None
    assert result["finalState"] == "loaded_fresh"
    assert result["finalRepo"] == "newest"
    assert "Checking" not in result["finalStatus"]
    assert result["intervals"] == 1
    assert result["listenerCount"] == result["listenerCountAfterSecondInit"]


def test_slow_trust_work_does_not_hold_global_state_lock(monkeypatch) -> None:
    entered = threading.Event()
    release = threading.Event()
    result: list[dict] = []
    api._TRUST_CACHE.update({"key": None, "at": 0.0, "status": None})

    def slow_assessment(_snapshot):
        entered.set()
        release.wait(timeout=2)
        return {"fresh": True, "status": "fresh", "repo_changed_outside_plan": False}

    monkeypatch.setattr(trust_integrity, "assess_staleness", slow_assessment)
    worker = threading.Thread(target=lambda: result.append(api.trust_integrity_status()), daemon=True)
    worker.start()
    assert entered.wait(timeout=1)
    started = time.perf_counter()
    with trust_integrity.state_guard():
        elapsed = time.perf_counter() - started
    release.set()
    worker.join(timeout=2)
    assert elapsed < 0.1
    assert result and result[0]["ok"] is True


def test_fresh_diagnostics_hashes_repository_once_and_skips_manifest_rehash(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    source = repo / "app.py"
    source.write_text("print('atlas')\n", encoding="utf-8")
    scope = {"mode": "entire_repo"}
    stored = trust_integrity.compute_signature_v2(
        str(repo), scope, include_content_hash=True, signature_version=trust_integrity.SIGNATURE_VERSION
    )
    state = {
        "path": str(repo),
        "scan": {"repo_path": str(repo), "scope": scope, "signature_v2": stored, "graph_health": {"label": "healthy"}},
        "last_scope": scope,
        "file_manifest": {
            "app.py": {"size": source.stat().st_size, "mtime": int(source.stat().st_mtime), "content_hash": trust_integrity._content_hash(str(source))}
        },
        "index": {"files": [{"path": "app.py"}]},
    }
    original = trust_integrity.compute_signature_v2
    calls = 0

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(trust_integrity, "compute_signature_v2", counted)
    monkeypatch.setattr(
        trust_integrity,
        "detect_changed_files",
        lambda _state: (_ for _ in ()).throw(AssertionError("fresh signature must not rehash the manifest")),
    )
    diagnostics = trust_integrity.trust_integrity_diagnostics(state)
    assert diagnostics["scan_stale"] is False
    assert diagnostics["stored_signature"] == diagnostics["live_signature"]
    assert calls == 1


def test_threaded_server_keeps_health_responsive_while_diagnostics_is_slow(monkeypatch) -> None:
    entered = threading.Event()
    release = threading.Event()

    def slow_diagnostics():
        entered.set()
        release.wait(timeout=2)
        return {"ok": True}

    monkeypatch.setattr(api, "beta_diagnostics", slow_diagnostics)
    httpd = server.AtlasHTTPServer(("127.0.0.1", 0), server.AtlasHandler)
    port = int(httpd.server_address[1])
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    slow_result: list[bytes] = []
    slow_thread = threading.Thread(
        target=lambda: slow_result.append(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/system/diagnostics", timeout=3).read()),
        daemon=True,
    )
    slow_thread.start()
    try:
        assert entered.wait(timeout=1)
        started = time.perf_counter()
        health = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1).read())
        elapsed = time.perf_counter() - started
        assert health["ok"] is True
        assert elapsed < 0.5
    finally:
        release.set()
        slow_thread.join(timeout=2)
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)
    assert slow_result


def test_refresh_sources_have_single_lifecycle_owners_and_no_scan_start() -> None:
    app_source = (STATIC / "app.js").read_text(encoding="utf-8")
    shell_source = (STATIC / "desktop-shell.js").read_text(encoding="utf-8")
    workbench_source = (STATIC / "workbench-v3.js").read_text(encoding="utf-8")
    product_source = (STATIC / "atlas_product.js").read_text(encoding="utf-8")
    active_memory = shell_source.split("async function renderMemory(options", 1)[1].split("function fileRow", 1)[0]
    assert "/api/system/diagnostics" not in active_memory
    assert 'if (view === "memory")' not in workbench_source.split("function onView(view)", 1)[1].split("function init()", 1)[0]
    assert "workbench.initialized" in workbench_source
    assert "shell.initialized" in shell_source
    assert "window.atlasProductBooted" in product_source
    assert "document.hidden" in product_source
    assert 'api("/api/repositories/scan"' in app_source  # user action remains available
    boot = app_source.split("async function bootAtlasApp", 1)[1]
    assert 'api("/api/repositories/scan"' not in boot


def test_graph_route_rebuild_disposes_webgl_resources() -> None:
    source = (STATIC / "universe.js").read_text(encoding="utf-8")
    start = source.index("function destroyGraph()")
    destroy = source[start : source.index("function setShowEdges", start)]

    assert "previous.pauseAnimation?.()" in destroy
    assert "previous.controls?.()?.dispose?.()" in destroy
    assert "object.geometry?.dispose?.()" in destroy
    assert "material.dispose?.()" in destroy
    assert "renderer?.dispose?.()" in destroy
    assert "renderer?.forceContextLoss?.()" in destroy

