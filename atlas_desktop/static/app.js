/* Atlas runtime transport boundary. Keep this first: account and workbench clients delegate here. */
(function (global) {
  "use strict";

  const TRACE_LIMIT = 200;
  const DEFAULT_TIMEOUT_MS = 15_000;
  const RUNTIME_PROTOCOL = "atlas-desktop-runtime-v1";
  const RUNTIME_PRODUCT = "Atlas Desktop";
  const ALLOWED_REQUEST_HEADERS = new Set(["accept", "content-type"]);
  const states = { runtime: "starting", account: "unknown", repository: "unknown", graph: "idle", trust: "unknown", auxiliary: "unknown" };
  const trace = [];
  const coordinatedInflight = new Map();
  const coordinatedCache = new Map();
  const coordinatorTrace = [];
  const coordinatorStats = { starts: 0, completed: 0, failed: 0, timeouts: 0, coalesced: 0, cacheHits: 0, maxInflight: 0 };
  let repositoryGeneration = 0;
  let runtimeIdentityPromise = null;
  let runtimeIdentityValue = null;

  class AtlasTransportError extends Error {
    constructor(kind, message, detail) {
      super(message);
      this.name = "AtlasTransportError";
      this.kind = kind;
      this.code = kind === "timeout" ? "request_timed_out" : `transport_${kind}`;
      Object.assign(this, detail || {});
    }
  }

  function runtimeOrigin() {
    const raw = String(global.location && global.location.origin || "");
    let parsed;
    try { parsed = new URL(raw); } catch (_error) {
      throw new AtlasTransportError("invalid_origin", "Atlas must be served by its local runtime.", { pageOrigin: raw });
    }
    const loopback = parsed.hostname === "127.0.0.1" || parsed.hostname === "localhost" || parsed.hostname === "[::1]" || parsed.hostname === "::1";
    if (parsed.protocol !== "http:" || !loopback || !parsed.port) {
      throw new AtlasTransportError("invalid_origin", "Atlas must be served from a verified loopback runtime origin.", { pageOrigin: raw });
    }
    return parsed.origin;
  }

  const origin = runtimeOrigin();

  function inferScope(path) {
    if (path.startsWith("/api/accounts/")) return "account";
    if (path === "/api/health" || path.startsWith("/api/runtime/")) return "runtime";
    if (path.includes("trust-status")) return "trust";
    if (path.includes("graph")) return "graph";
    if (path.startsWith("/api/repositories/") || path === "/api/history" || path === "/api/system/diagnostics") return "repository";
    return "auxiliary";
  }

  function resolveApiUrl(path) {
    const raw = String(path || "");
    if ((raw !== "/api" && !raw.startsWith("/api/")) || raw.startsWith("//") || raw.includes("\\")) {
      throw new AtlasTransportError("origin_mismatch", "Atlas API requests must use a root-relative /api path.", { requestPath: raw, pageOrigin: origin });
    }
    const resolved = new URL(raw, `${origin}/`);
    if (resolved.origin !== origin || resolved.username || resolved.password) {
      throw new AtlasTransportError("origin_mismatch", "Atlas blocked an API request outside the active runtime origin.", {
        requestUrl: resolved.href,
        requestOrigin: resolved.origin,
        pageOrigin: origin,
      });
    }
    return resolved;
  }

  function publishTrace() {
    const root = global.document && global.document.documentElement;
    if (!root || typeof root.setAttribute !== "function") return;
    root.setAttribute("data-atlas-runtime-origin", origin);
    root.setAttribute("data-atlas-runtime-state", states.runtime);
    root.setAttribute("data-atlas-account-state", states.account);
    root.setAttribute("data-atlas-repository-state", states.repository);
    root.setAttribute("data-atlas-graph-state", states.graph);
    root.setAttribute("data-atlas-trust-state", states.trust);
    root.setAttribute("data-atlas-auxiliary-state", states.auxiliary);
    root.setAttribute("data-atlas-transport-trace", JSON.stringify(trace));
  }

  function setState(scope, value, detail) {
    if (Object.prototype.hasOwnProperty.call(states, scope)) states[scope] = value;
    publishTrace();
    try {
      global.document && global.document.dispatchEvent(new CustomEvent("atlas:transport-state", {
        detail: { scope, state: value, ...(detail || {}) },
      }));
    } catch (_error) {}
  }

  function record(entry) {
    trace.push(entry);
    if (trace.length > TRACE_LIMIT) trace.splice(0, trace.length - TRACE_LIMIT);
    publishTrace();
  }

  function safeResponseHeaders(headers) {
    const result = {};
    try {
      headers.forEach((value, name) => {
        const lowered = String(name).toLowerCase();
        if (lowered !== "set-cookie" && lowered !== "authorization" && lowered !== "proxy-authorization") result[lowered] = value;
      });
    } catch (_error) {}
    return result;
  }

  function requestStartState(scope) {
    if (scope === "graph") return "loading";
    if (scope === "runtime" && states.runtime === "starting") return "starting";
    return "checking";
  }

  function requestSuccessState(scope) {
    return scope === "graph" ? "loaded" : "available";
  }

  function runtimeChallenge() {
    const bytes = new Uint8Array(18);
    if (global.crypto && typeof global.crypto.getRandomValues === "function") {
      global.crypto.getRandomValues(bytes);
    } else {
      for (let index = 0; index < bytes.length; index += 1) bytes[index] = Math.floor(Math.random() * 256);
    }
    return Array.from(bytes, (value) => value.toString(16).padStart(2, "0")).join("");
  }

  function ensureRuntimeIdentity() {
    if (runtimeIdentityValue) return Promise.resolve(runtimeIdentityValue);
    if (runtimeIdentityPromise) return runtimeIdentityPromise;
    const challenge = runtimeChallenge();
    runtimeIdentityPromise = request(
      `/api/runtime/handshake?challenge=${encodeURIComponent(challenge)}`,
      {
        scope: "runtime",
        requireOk: true,
        requireRuntimeHandshake: true,
        handshakeChallenge: challenge,
        skipRuntimeHandshake: true,
      },
    ).then((identity) => {
      runtimeIdentityValue = identity;
      const root = global.document && global.document.documentElement;
      if (root && typeof root.setAttribute === "function") root.setAttribute("data-atlas-runtime-protocol", identity.protocol);
      return identity;
    }).catch((error) => {
      runtimeIdentityPromise = null;
      throw error;
    });
    return runtimeIdentityPromise;
  }

  async function request(path, options) {
    const settings = options || {};
    const resolved = resolveApiUrl(path);
    const method = String(settings.method || "GET").toUpperCase();
    const scope = settings.scope || inferScope(resolved.pathname);
    if (resolved.pathname !== "/api/runtime/handshake" && settings.skipRuntimeHandshake !== true) {
      await ensureRuntimeIdentity();
    }
    const hasBody = settings.body !== undefined && settings.body !== null;
    const headers = new Headers(settings.headers || {});
    headers.set("Accept", "application/json");
    if (hasBody) headers.set("Content-Type", "application/json");
    else headers.delete("Content-Type");
    for (const name of headers.keys()) {
      if (!ALLOWED_REQUEST_HEADERS.has(String(name).toLowerCase())) {
        throw new AtlasTransportError("unsafe_header", `Atlas blocked unsupported request header: ${name}`, { requestUrl: resolved.href, scope });
      }
    }

    const controller = new AbortController();
    const timeoutMs = Math.max(1, Number(settings.timeoutMs || DEFAULT_TIMEOUT_MS));
    const started = Date.now();
    const entry = {
      id: `${started}-${trace.length + 1}`,
      pageOrigin: origin,
      requestOrigin: resolved.origin,
      requestUrl: resolved.href,
      method,
      credentials: "same-origin",
      mode: "same-origin",
      headers: Object.fromEntries(headers.entries()),
      hasBody,
      scope,
      startedAt: new Date(started).toISOString(),
      status: null,
      outcome: "pending",
    };
    record(entry);
    setState(scope, requestStartState(scope), { requestUrl: resolved.href });

    const timer = global.setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await global.fetch(`${resolved.pathname}${resolved.search}`, {
        method,
        headers,
        body: hasBody ? JSON.stringify(settings.body) : undefined,
        credentials: "same-origin",
        mode: "same-origin",
        signal: controller.signal,
      });
      entry.status = response.status;
      entry.statusText = response.statusText;
      entry.responseHeaders = safeResponseHeaders(response.headers);
      entry.durationMs = Date.now() - started;
      let payload;
      try { payload = await response.json(); } catch (_error) {
        throw new AtlasTransportError("invalid_response", "Atlas runtime returned a non-JSON response.", { requestUrl: resolved.href, status: response.status, scope });
      }
      if (settings.requireAtlasIdentity && (!payload || payload.ok !== true || payload.product !== "ATLAS")) {
        throw new AtlasTransportError("identity_mismatch", "The selected listener did not identify itself as Atlas.", { requestUrl: resolved.href, status: response.status, scope });
      }
      if (settings.requireRuntimeHandshake) {
        const activePort = Number(new URL(origin).port);
        const proof = String(payload && payload.proof || "");
        if (
          !payload
          || payload.ok !== true
          || payload.product !== RUNTIME_PRODUCT
          || payload.protocol !== RUNTIME_PROTOCOL
          || payload.challenge !== settings.handshakeChallenge
          || Number(payload.port) !== activePort
          || !Number.isInteger(Number(payload.pid))
          || Number(payload.pid) <= 0
          || !String(payload.instance_id || "")
          || !/^[a-f0-9]{64}$/i.test(proof)
        ) {
          throw new AtlasTransportError("identity_mismatch", "The selected listener failed the Atlas runtime handshake.", { requestUrl: resolved.href, status: response.status, scope });
        }
      }
      if (settings.requireOk && (!response.ok || !payload || payload.ok !== true)) {
        throw new AtlasTransportError("http_error", String(payload && payload.error || `Atlas runtime returned HTTP ${response.status}.`), { requestUrl: resolved.href, status: response.status, scope });
      }
      entry.outcome = response.ok ? "success" : "http_error";
      setState(scope, response.ok ? requestSuccessState(scope) : "http_error", { status: response.status, requestUrl: resolved.href });
      publishTrace();
      return payload;
    } catch (error) {
      let transportError = error;
      if (!(error instanceof AtlasTransportError)) {
        const timedOut = controller.signal.aborted || (error && error.name === "AbortError");
        transportError = new AtlasTransportError(timedOut ? "timeout" : "network_error", timedOut ? "Atlas request timed out." : "Atlas runtime request failed.", {
          requestUrl: resolved.href,
          scope,
          cause: String(error && (error.message || error) || "unknown error"),
        });
      }
      entry.outcome = transportError.kind;
      entry.error = transportError.message;
      entry.durationMs = Date.now() - started;
      const failureState = transportError.kind === "timeout" ? "timed_out" : transportError.kind === "http_error" ? "http_error" : "unavailable";
      setState(scope, failureState, { kind: transportError.kind, requestUrl: resolved.href });
      publishTrace();
      throw transportError;
    } finally {
      global.clearTimeout(timer);
    }
  }

  function canonicalGetKey(path) {
    const resolved = resolveApiUrl(path);
    const params = new URLSearchParams(resolved.search);
    params.sort();
    const query = params.toString();
    return `GET ${resolved.pathname}${query ? `?${query}` : ""}`;
  }

  function cacheWindowMs(pathname) {
    if (pathname === "/api/system/diagnostics") return 30_000;
    if (pathname === "/api/repositories/recent") return 300_000;
    if (pathname === "/api/history" || pathname === "/api/history/item") return 300_000;
    if (pathname === "/api/repositories/current/system-health") return 30_000;
    if (pathname === "/api/repositories/current/trust-status") return 30_000;
    if (pathname === "/api/repositories/current/graph") return 30_000;
    if (pathname === "/api/integrations/mcp/status") return 10_000;
    if (pathname === "/api/product/config") return 60_000;
    if (pathname === "/api/repositories/current/summary") return 5_000;
    if (pathname === "/api/health") return 5_000;
    return 0;
  }

  function recordCoordinator(entry) {
    if (entry.type === "start") coordinatorStats.starts += 1;
    if (entry.type === "complete") coordinatorStats.completed += 1;
    if (entry.type === "failed") {
      coordinatorStats.failed += 1;
      if (entry.kind === "timeout") coordinatorStats.timeouts += 1;
    }
    if (entry.type === "coalesced") coordinatorStats.coalesced += 1;
    if (entry.type === "cache_hit") coordinatorStats.cacheHits += 1;
    coordinatorStats.maxInflight = Math.max(coordinatorStats.maxInflight, coordinatedInflight.size);
    coordinatorTrace.push(entry);
    if (coordinatorTrace.length > TRACE_LIMIT) coordinatorTrace.splice(0, coordinatorTrace.length - TRACE_LIMIT);
    const root = global.document && global.document.documentElement;
    if (root && typeof root.setAttribute === "function") {
      root.setAttribute("data-atlas-request-coordinator", JSON.stringify({
        inflight: coordinatedInflight.size,
        cache: coordinatedCache.size,
        repositoryGeneration,
        stats: coordinatorStats,
        heapUsed: Number(global.performance && global.performance.memory && global.performance.memory.usedJSHeapSize || 0),
        trace: coordinatorTrace,
      }));
    }
  }

  function cancellationError(reason) {
    const error = new Error(reason || "Atlas request cancelled.");
    error.name = "AbortError";
    error.kind = "cancelled";
    error.code = "request_cancelled";
    error.expected = true;
    return error;
  }

  function attachConsumer(shared, signal) {
    if (!signal) return shared;
    if (signal.aborted) return Promise.reject(cancellationError("Atlas request cancelled before it started."));
    return new Promise((resolve, reject) => {
      const cancel = () => reject(cancellationError("Atlas request cancelled because its view is no longer active."));
      signal.addEventListener("abort", cancel, { once: true });
      shared.then((value) => {
        signal.removeEventListener("abort", cancel);
        resolve(value);
      }, (error) => {
        signal.removeEventListener("abort", cancel);
        reject(error);
      });
    });
  }

  function invalidateCoordinated(reason) {
    repositoryGeneration += 1;
    coordinatedCache.clear();
    recordCoordinator({ type: "invalidate", reason: String(reason || "state_change"), at: new Date().toISOString(), repositoryGeneration });
    try {
      global.document && global.document.dispatchEvent(new CustomEvent("atlas:repository-invalidated", {
        detail: { reason: String(reason || "state_change"), repositoryGeneration },
      }));
    } catch (_error) {}
  }

  function mutationInvalidationScope(pathname) {
    if (
      pathname.startsWith("/api/repositories/")
      || pathname === "/api/demo/load"
      || pathname === "/api/system/clear-cache"
      || pathname === "/api/system/rebuild-index"
    ) return "repository";
    if (pathname.startsWith("/api/copilot/") || pathname.startsWith("/api/planning/")) return "history";
    return "";
  }

  function coordinatedRequest(path, options) {
    const settings = options || {};
    const method = String(settings.method || "GET").toUpperCase();
    const resolved = resolveApiUrl(path);
    if (method !== "GET") {
      return request(path, settings).then((payload) => {
        if (payload && payload.ok) {
          const scope = mutationInvalidationScope(resolved.pathname);
          if (scope) invalidateCoordinated(scope);
        }
        return payload;
      });
    }

    const key = canonicalGetKey(path);
    const now = Date.now();
    const cached = coordinatedCache.get(key);
    const ttl = cacheWindowMs(resolved.pathname);
    if (!settings.force && cached && cached.expiresAt > now) {
      recordCoordinator({ type: "cache_hit", key, at: new Date(now).toISOString(), ageMs: now - cached.storedAt, repositoryGeneration });
      return attachConsumer(Promise.resolve(cached.value), settings.signal);
    }

    const active = coordinatedInflight.get(key);
    if (active) {
      active.consumers += 1;
      recordCoordinator({ type: "coalesced", key, at: new Date(now).toISOString(), consumers: active.consumers, visible: !(global.document && global.document.hidden), repositoryGeneration });
      return attachConsumer(active.promise, settings.signal);
    }

    const startedAt = now;
    const requestSettings = { ...settings };
    delete requestSettings.signal;
    delete requestSettings.force;
    delete requestSettings.optional;
    const entry = { key, consumers: 1, startedAt, promise: null };
    const shared = request(path, requestSettings).then((payload) => {
      if (ttl > 0 && payload && payload.ok) {
        coordinatedCache.set(key, { value: payload, storedAt: Date.now(), expiresAt: Date.now() + ttl, repositoryGeneration });
      }
      recordCoordinator({ type: "complete", key, at: new Date().toISOString(), durationMs: Date.now() - startedAt, consumers: entry.consumers, repositoryGeneration });
      return payload;
    }).catch((error) => {
      if (settings.optional && cached && cached.value) {
        recordCoordinator({ type: "stale_fallback", key, at: new Date().toISOString(), durationMs: Date.now() - startedAt, kind: error && error.kind, repositoryGeneration });
        return cached.value;
      }
      recordCoordinator({ type: "failed", key, at: new Date().toISOString(), durationMs: Date.now() - startedAt, kind: error && error.kind, repositoryGeneration });
      throw error;
    }).finally(() => {
      if (coordinatedInflight.get(key) === entry) coordinatedInflight.delete(key);
      recordCoordinator({ type: "settled", key, at: new Date().toISOString(), repositoryGeneration });
    });
    entry.promise = shared;
    coordinatedInflight.set(key, entry);
    recordCoordinator({ type: "start", key, at: new Date(startedAt).toISOString(), visible: !(global.document && global.document.hidden), repositoryGeneration });
    return attachConsumer(shared, settings.signal);
  }

  function getTrace() {
    return trace.map((item) => ({ ...item, headers: { ...(item.headers || {}) }, responseHeaders: { ...(item.responseHeaders || {}) } }));
  }

  function getStates() {
    return { ...states };
  }

  function clearTrace() {
    trace.splice(0, trace.length);
    publishTrace();
  }

  global.atlasTransport = Object.freeze({
    origin,
    request,
    resolveApiUrl: (path) => resolveApiUrl(path).href,
    setState,
    getStates,
    getTrace,
    clearTrace,
    ensureRuntimeIdentity,
    runtimeIdentity: () => runtimeIdentityValue && { ...runtimeIdentityValue },
    AtlasTransportError,
  });
  global.atlasRequestCoordinator = Object.freeze({
    request: coordinatedRequest,
    invalidate: invalidateCoordinated,
    getState: () => ({
      inflight: Array.from(coordinatedInflight.keys()),
      cache: Array.from(coordinatedCache.keys()),
      trace: coordinatorTrace.map((item) => ({ ...item })),
      stats: { ...coordinatorStats },
      heapUsed: Number(global.performance && global.performance.memory && global.performance.memory.usedJSHeapSize || 0),
      repositoryGeneration,
    }),
  });
  publishTrace();
})(window);

/* Atlas application. */
"use strict";
const STATE = {
  repo: null, summary: null, graph: null, graphView: "module", graphPerf: null,
  exportTarget: "claude", exportPacket: "compact", graph3d: null, hoverNodeId: null,
  selectedNode: null, copilotResult: null, showEdges: true, riskPercentiles: null,
  demoMode: false, tourStops: null, screenshotMode: false, demoPack: "medium", productTourActive: false,
  massiveMode: false, lastEstimate: null, hierarchy: { level: "subsystem", subsystem: "", package: "", module: "" },
  homeHealth: null, homeMcpStatus: null, homeTrustStatus: null, homeRecent: [],
};
window.STATE = STATE;
const RECENT_KEY = "atlas_recent_repos";
const LEGACY_RECENT_KEY = "\u006a\u0061\u0072\u0076\u0069\u0073_recent_repos";
const ONBOARDING_KEY = "atlas_onboarding_v2_done";
const WORKFLOW_HINT_KEY = "atlas_workflow_examples_seen";
const DEMO_PACK_KEY = "atlas_demo_pack_v1";
const DEFAULT_DEMO_PACK = "medium";
const DEFAULT_FIRST_QUESTION = "Where is authentication implemented?";
const HN_FIRST_QUESTION = "Where is authentication implemented?";
const NAV_ALIASES = { intel: "center", bug: "investigate", map: "center", "command-center": "center", copilot: "ask", hn: "hn" };
const PROTECTED_VIEWS = new Set(["home", "scan", "hn", "memory", "files", "ask", "center", "build", "investigate", "impact", "export"]);
const RECENT_MAX_VISIBLE = 4;
const RECENT_HIDE_PATTERNS = [/^test_/i, /^repo_a$/i, /smoke/i, /fixture/i, /^debug_/i];
const GRAPH_HIERARCHY_THRESHOLD = 1000;
const ATLAS_SHOW_GRAPH_DEBUG = false;
let _recentExpanded = false;
let _hnDemoActive = false;
let _suggestDelegated = false;

function resolveDefaultGraphView(moduleCount) {
  return (moduleCount || 0) >= GRAPH_HIERARCHY_THRESHOLD ? "hierarchy" : "module";
}

function graphModeTitle(view, graph) {
  if (view === "module") return "Module Graph";
  if (view === "subsystem") return "Architecture Overview";
  return "Hierarchy View";
}

function graphUnderlyingTotals(sum, graph) {
  return {
    modules: graph?.total_modules ?? sum?.module_count ?? 0,
    edges: graph?.total_edges ?? sum?.dependency_edges ?? 0,
  };
}

function graphVisibleCounts(graph) {
  return {
    nodes: graph?.node_count ?? (graph?.nodes || []).length,
    links: graph?.link_count ?? (graph?.links || []).length,
  };
}

function formatEntitySummary(view, graph, totals) {
  const vis = graphVisibleCounts(graph);
  const x = vis.nodes;
  const y = totals.modules;
  if (view === "module") {
    return `Showing ${x.toLocaleString()} of ${y.toLocaleString()} modules`;
  }
  if (view === "subsystem") {
    const kind = graph?.architecture_clusters ? "architecture subsystems" : "subsystems";
    return `Showing ${x.toLocaleString()} ${kind} representing ${y.toLocaleString()} modules`;
  }
  const level = graph?.level || "subsystem";
  if (level === "package") {
    return `Showing ${x.toLocaleString()} packages in this subsystem (${y.toLocaleString()} modules in repository)`;
  }
  if (level === "module") {
    return `Showing ${x.toLocaleString()} modules in this package (${y.toLocaleString()} modules in repository)`;
  }
  return `Showing ${x.toLocaleString()} top-level hierarchy nodes representing ${y.toLocaleString()} modules`;
}

function graphViewToastMessage(view, graph, totals) {
  const vis = graphVisibleCounts(graph);
  if (view === "module") {
    return `Viewing Module Graph (${vis.nodes.toLocaleString()} modules)`;
  }
  if (view === "subsystem") {
    const kind = graph?.architecture_clusters ? "architecture subsystems" : "subsystems";
    return `Viewing Architecture Overview (${vis.nodes.toLocaleString()} ${kind})`;
  }
  const level = graph?.level || "subsystem";
  if (level === "package") return `Viewing Hierarchy — packages (${vis.nodes.toLocaleString()} nodes)`;
  if (level === "module") return `Viewing Hierarchy — modules (${vis.nodes.toLocaleString()} nodes)`;
  return `Viewing Hierarchy (${vis.nodes.toLocaleString()} top-level nodes)`;
}

function massiveModeReasonText(sum) {
  const r = sum?.massive_reason || {};
  const fc = sum?.file_count ? sum.file_count.toLocaleString() : "";
  if (r.manual) return "Manually enabled — Atlas is sampling this repository";
  if (r.modules) return `Large repository${fc ? ` (${fc} files)` : ""} — Atlas sampled the most important modules`;
  if (r.files) return `Large repository${fc ? ` (${fc} files)` : ""} — Atlas sampled the top files`;
  if (r.size) return "Large repository — Atlas sampled to keep scan fast";
  return `Large repository — Atlas sampled the top files`;
}

function renderGraphModeMetrics(sum, graph) {
  const view = STATE.graphView || "module";
  const totals = graphUnderlyingTotals(sum, graph);
  const vis = graphVisibleCounts(graph);
  const badge = $("graphModeBadge");
  if (badge) badge.style.display = "none";  // no floating center badge
  const host = $("graphScaleHeader");
  if (host) {
    const gh = sum?.graph_health || {};
    const risk = sum?.risk_score ?? 0;
    const cycles = gh.import_cycles ?? 0;
    const coverage = gh.label || "—";
    if (view === "module") {
      const riskLabel = risk > 60 ? "high" : risk > 30 ? "medium" : risk > 0 ? "low" : "—";
      const coverageLabel = coverage === "healthy" ? "complete" : coverage === "watch" ? "incomplete" : (coverage || "—");
      host.innerHTML = `
        <div class="scale-row">
          <div class="scale-stat"><span class="scale-num">${vis.nodes.toLocaleString()}</span><span class="scale-lbl">modules</span></div>
          <div class="scale-stat"><span class="scale-num">${vis.links.toLocaleString()}</span><span class="scale-lbl">dependencies</span></div>
          <div class="scale-stat"><span class="scale-num" style="color:${cycles > 0 ? 'var(--amber)' : 'var(--muted)'}">${cycles}</span><span class="scale-lbl">cycles</span></div>
          <div class="scale-stat"><span class="scale-num" style="font-size:13px;color:${coverageLabel === 'complete' ? 'var(--green)' : 'var(--amber)'}">${coverageLabel}</span><span class="scale-lbl">import resolution</span></div>
        </div>`;
    } else if (view === "subsystem") {
      const linkLbl = graph?.architecture_clusters ? "cluster links" : "subsystem links";
      host.innerHTML = `
        <div class="scale-row">
          <div class="scale-row-title">Visible</div>
          <div class="scale-stat"><span class="scale-num">${vis.nodes.toLocaleString()}</span><span class="scale-lbl">subsystems</span></div>
          <div class="scale-stat"><span class="scale-num">${vis.links.toLocaleString()}</span><span class="scale-lbl">${linkLbl}</span></div>
        </div>
        <div class="scale-row underlying">
          <div class="scale-row-title">Underlying repository</div>
          <div class="scale-stat"><span class="scale-num">${totals.modules.toLocaleString()}</span><span class="scale-lbl">modules</span></div>
          <div class="scale-stat"><span class="scale-num">${totals.edges.toLocaleString()}</span><span class="scale-lbl">dependencies</span></div>
        </div>`;
    } else {
      const levelLbl = graph?.level === "package" ? "packages" : graph?.level === "module" ? "modules" : "top-level nodes";
      host.innerHTML = `
        <div class="scale-row">
          <div class="scale-row-title">Visible</div>
          <div class="scale-stat"><span class="scale-num">${vis.nodes.toLocaleString()}</span><span class="scale-lbl">${levelLbl}</span></div>
          <div class="scale-stat"><span class="scale-num">${vis.links.toLocaleString()}</span><span class="scale-lbl">links</span></div>
        </div>
        <div class="scale-row underlying">
          <div class="scale-row-title">Underlying repository</div>
          <div class="scale-stat"><span class="scale-num">${totals.modules.toLocaleString()}</span><span class="scale-lbl">modules</span></div>
          <div class="scale-stat"><span class="scale-num">${totals.edges.toLocaleString()}</span><span class="scale-lbl">dependencies</span></div>
        </div>`;
    }
  }
  const summaryEl = $("graphEntitySummary");
  if (summaryEl) summaryEl.textContent = formatEntitySummary(view, graph, totals);
  renderMassiveModeBanner(sum, graph);
  renderGraphRenderDiagnostics(STATE.graphPerf);
}

function renderGraphRenderDiagnostics(perf) {
  const el = $("graphRenderDiagnostics");
  if (!el) return;
  if (!ATLAS_SHOW_GRAPH_DEBUG) {
    el.style.display = "none";
    return;
  }
  const view = STATE.graphView || "module";
  const d = perf?.renderDiagnostics || ATLAS_UNIVERSE.getRenderDiagnostics?.();
  if (!d || view !== "module") {
    el.style.display = "none";
    return;
  }
  el.style.display = "block";
  const ok = d.meshes === d.nodes;
  el.innerHTML = `
    <div><b>Nodes:</b> ${d.nodes}</div>
    <div><b>Meshes:</b> ${d.meshes}${ok ? "" : " ⚠"}</div>
    <div><b>Min radius:</b> ${d.minRadius}</div>
    <div><b>Max radius:</b> ${d.maxRadius}</div>
    <div class="muted tiny">${d.forceVisibleModule ? "force-visible mode" : "custom mesh"}</div>`;
}

function renderMassiveModeBanner(sum, graph) {
  const banner = $("massiveModeBanner");
  if (!banner) return;
  const massive = !!(sum?.massive_mode || graph?.massive_mode);
  if (!massive) {
    banner.style.display = "none";
    return;
  }
  banner.style.display = "block";
  const reasonEl = $("massiveModeReason");
  if (reasonEl) reasonEl.textContent = `Reason: ${massiveModeReasonText(sum)}`;
  const btn = $("showFullModuleGraphBtn");
  if (btn) {
    const onModule = (STATE.graphView || "module") === "module";
    btn.style.display = onModule ? "none" : "inline-block";
  }
}

function showFullModuleGraph() {
  setGraphView("module");
}

function sleep(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }

const TELEMETRY_WARNING_TEXT = typeof atlasFriendlyTelemetry === "function"
  ? atlasFriendlyTelemetry("")
  : "Usage stats temporarily unavailable — scanning and plans still work.";

function updateTelemetryWarning(source) {
  const el = $("telemetryWarning");
  if (!el) return;
  const degraded = source && (source.analytics_status === "degraded" || source.telemetry_warning);
  if (degraded) {
    el.style.display = "block";
    const raw = source.telemetry_warning || TELEMETRY_WARNING_TEXT;
    el.textContent = typeof atlasFriendlyTelemetry === "function" ? atlasFriendlyTelemetry(raw) : raw;
  } else {
    el.style.display = "none";
  }
}

async function trackAnalytics(event, props) {
  try {
    await api("/api/analytics/event", "POST", { event, ...(props || {}) });
  } catch (e) { /* local-only, never block UX */ }
}

// This is intentionally a local UI activity signal, not a repository signal.
// It records only the named Atlas screen and approximate engaged duration. The
// server-side allowlist drops any non-approved field before local persistence
// or optional first-party delivery.
const desktopEngagement = (() => {
  const IDLE_MS = 60_000;
  const HEARTBEAT_MS = 30_000;
  let startedAt = 0;
  let screenStartedAt = 0;
  let currentScreen = "home";
  let lastInteractionAt = 0;
  let activeStartedAt = 0;
  let screenActiveMs = 0;
  let reportedActiveMs = 0;
  let started = false;

  function now() { return Date.now(); }
  function isActive(at = now()) {
    return !document.hidden && document.hasFocus() && at - lastInteractionAt <= IDLE_MS;
  }
  function accrue(at = now()) {
    if (activeStartedAt && isActive(at)) screenActiveMs += Math.max(0, at - activeStartedAt);
    activeStartedAt = isActive(at) ? at : 0;
  }
  function heartbeat() {
    if (!started) return;
    const at = now();
    accrue(at);
    const delta = screenActiveMs - reportedActiveMs;
    if (delta < 1_000) return;
    reportedActiveMs = screenActiveMs;
    trackAnalytics("screen_active_heartbeat", {
      screen: currentScreen,
      duration_active_ms: Math.round(delta),
      duration_elapsed_ms: HEARTBEAT_MS,
    });
  }
  function finishScreen(reason) {
    if (!started || !screenStartedAt) return;
    const at = now();
    accrue(at);
    const unreported = screenActiveMs - reportedActiveMs;
    const elapsed = at - screenStartedAt;
    if (elapsed >= 1_000) {
      trackAnalytics("screen_active_ended", {
        screen: currentScreen,
        surface: reason,
        duration_active_ms: Math.round(Math.max(0, unreported)),
        duration_elapsed_ms: Math.round(elapsed),
      });
    }
  }
  function markInteraction() {
    const at = now();
    accrue(at);
    lastInteractionAt = at;
    if (!activeStartedAt && isActive(at)) activeStartedAt = at;
  }
  function start(screen) {
    if (started) return;
    started = true;
    startedAt = now();
    screenStartedAt = startedAt;
    currentScreen = screen || "home";
    lastInteractionAt = startedAt;
    activeStartedAt = startedAt;
    trackAnalytics("screen_view", { screen: currentScreen });
  }
  function viewChanged(screen) {
    if (!started) start(screen);
    if (!screen || screen === currentScreen) return;
    finishScreen("view_change");
    currentScreen = screen;
    screenStartedAt = now();
    screenActiveMs = 0;
    reportedActiveMs = 0;
    activeStartedAt = isActive() ? screenStartedAt : 0;
    trackAnalytics("screen_view", { screen: currentScreen });
  }
  function finishSession() {
    if (!started) return;
    finishScreen("pagehide");
    const at = now();
    trackAnalytics("app_session_ended", {
      duration_active_ms: Math.round(screenActiveMs),
      duration_elapsed_ms: Math.max(0, Math.round(at - startedAt)),
    });
  }

  ["pointerdown", "keydown", "scroll", "touchstart"].forEach((event) => {
    window.addEventListener(event, markInteraction, { passive: true });
  });
  window.addEventListener("focus", markInteraction);
  window.addEventListener("blur", () => accrue());
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) accrue(); else markInteraction();
  });
  window.addEventListener("pagehide", finishSession);
  window.setInterval(heartbeat, HEARTBEAT_MS);
  document.addEventListener("DOMContentLoaded", () => start("home"), { once: true });

  return { viewChanged };
})();

function api(path, method = "GET", body, transportOptions = {}) {
  const raw = String(path || "");
  const splitAt = raw.indexOf("?");
  const pathPart = splitAt >= 0 ? raw.slice(0, splitAt) : raw;
  const queryPart = splitAt >= 0 ? raw.slice(splitAt + 1) : "";
  const normalizedPath = pathPart.replace(/\/+$/, "") || "/api";
  const normalized = queryPart ? `${normalizedPath}?${queryPart}` : normalizedPath;
  if (!window.atlasTransport) return Promise.reject(new Error("Atlas runtime transport is unavailable"));
  const request = window.atlasRequestCoordinator && typeof window.atlasRequestCoordinator.request === "function"
    ? window.atlasRequestCoordinator.request
    : window.atlasTransport.request;
  const payloadPromise = request(normalized, {
    ...transportOptions,
    method,
    body,
    requireAtlasIdentity: normalizedPath === "/api/health" || transportOptions.requireAtlasIdentity === true,
  });
  return payloadPromise.then((payload) => {
    if (payload && !payload.ok && String(payload.error || "").startsWith("Unknown endpoint")) {
      console.error("Atlas API route missing:", method, normalized, payload.error);
    }
    return payload;
  });
}
window.api = api;

function requestAtlasRuntimeIdentity() {
  if (!window.atlasTransport || typeof window.atlasTransport.ensureRuntimeIdentity !== "function") {
    return Promise.reject(Object.assign(new Error("Atlas runtime handshake unavailable"), { kind: "identity_mismatch" }));
  }
  return window.atlasTransport.ensureRuntimeIdentity().then((identity) => {
    STATE.runtimeIdentity = identity;
    document.documentElement?.setAttribute("data-atlas-runtime-protocol", identity.protocol);
    return identity;
  });
}
window.requestAtlasRuntimeIdentity = requestAtlasRuntimeIdentity;

function requestAtlasTrustStatus(options = {}) {
  const request = Object.keys(options).length
    ? api("/api/repositories/current/trust-status", "GET", undefined, { optional: true, ...options })
    : api("/api/repositories/current/trust-status");
  window.atlasTrustRequest = request;
  request.then(() => {
    if (window.atlasTrustRequest === request) window.atlasTrustRequest = null;
  }, () => {
    if (window.atlasTrustRequest === request) window.atlasTrustRequest = null;
  });
  return request;
}
window.requestAtlasTrustStatus = requestAtlasTrustStatus;
function $(id) { return document.getElementById(id); }
function toast(msg, kind) {
  const t = $("toast");
  t.textContent = msg;
  t.className = "toast show" + (kind === "success" ? " toast-success" : kind === "error" ? " toast-error" : "");
  setTimeout(() => { t.classList.remove("show"); t.className = "toast"; }, 2400);
}
function requireAtlasAccess(actionLabel) {
  if (window.atlasAccounts && typeof window.atlasAccounts.requireAccess === "function") {
    const ok = window.atlasAccounts.requireAccess();
    if (!ok) toast(`${actionLabel || "Atlas"} requires sign-in or local guest mode`, "error");
    return ok;
  }
  if (document.body.classList.contains("auth-mode")) {
    toast(`${actionLabel || "Atlas"} requires sign-in or local guest mode`, "error");
    return false;
  }
  return true;
}
async function copyText(text, label) {
  const payload = String(text || "");
  if (!payload.trim()) {
    toast("Nothing to copy — generate a result first", "error");
    return false;
  }
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(payload);
      toast((label || "Copied") + " ✓", "success");
      return true;
    }
    throw new Error("clipboard unavailable");
  } catch (e) {
    try {
      const ta = document.createElement("textarea");
      ta.value = payload;
      ta.setAttribute("readonly", "");
      ta.style.position = "fixed";
      ta.style.left = "-9999px";
      ta.style.top = "0";
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      ta.setSelectionRange(0, payload.length);
      const ok = document.execCommand("copy");
      ta.remove();
      if (!ok) throw new Error("execCommand copy failed");
      toast((label || "Copied") + " ✓", "success");
      return true;
    } catch (e2) {
      toast("Copy failed — use Download markdown instead", "error");
      return false;
    }
  }
}

function emptyStateHtml(title, body, actionLabel, actionFn) {
  return `<div class="empty-state glass"><h3>${title}</h3><p>${body}</p><button class="btn primary" onclick="${actionFn}">${actionLabel}</button></div>`;
}

function updateRepoChip(name, demo) {
  $("repoChip").textContent = name || "No repository";
  $("demoBadge").style.display = demo ? "inline-block" : "none";
  STATE.demoMode = !!demo;
}

function updateMassiveBadge(on) {
  STATE.massiveMode = !!on;
  if ($("massiveBadge")) $("massiveBadge").style.display = on ? "inline-block" : "none";
}

function readScopeConfig() {
  const mode = $("scopeMode")?.value || "entire_repo";
  const folder = ($("scopeFolder")?.value || "").trim();
  const include_patterns = (($("scopeInclude")?.value || "").split(",").map(s => s.trim()).filter(Boolean));
  const exclude_patterns = (($("scopeExclude")?.value || "").split(",").map(s => s.trim()).filter(Boolean));
  const manual_massive_mode = !!$("manualMassiveMode")?.checked;
  return { mode, folder, include_patterns, exclude_patterns, manual_massive_mode };
}

function dismissOnboarding(skipDemo) {
  try { localStorage.setItem(ONBOARDING_KEY, "1"); } catch (e) {}
  $("onboarding").style.display = "none";
  if (!skipDemo) go("home");
}

function onboardingLoadSample() {
  if (!requireAtlasAccess("Sample repository")) return;
  dismissOnboarding(true);
  loadDemoMode(DEFAULT_DEMO_PACK);
}

function maybeShowOnboarding() {
  try {
    if (localStorage.getItem(ONBOARDING_KEY) === "1") return;
  } catch (e) {}
  $("onboarding").style.display = "grid";
}

function workflowEmptyHtml(title, body, primaryLabel, primaryFn, secondaryLabel, secondaryFn) {
  return `<div class="glass empty-panel">
    <h3 style="margin:0 0 8px">${title}</h3>
    <p class="muted" style="margin:0 0 14px">${body}</p>
    <div class="success-buttons">
      <button class="btn primary" type="button" onclick="${primaryFn}">${primaryLabel}</button>
      ${secondaryLabel ? `<button class="btn ghost" type="button" onclick="${secondaryFn}">${secondaryLabel}</button>` : ""}
    </div>
  </div>`;
}

function repoRequiredEmptyHtml(body) {
  return workflowEmptyHtml(
    "Scan a repository first",
    body || "Atlas needs a local code map before it can resolve repository evidence.",
    "Load sample repository",
    "loadDemoMode('medium')",
    "Scan local repository",
    "go('scan')"
  );
}

function renderWorkflowGate(view) {
  const map = {
    build: { el: "buildOut", title: "Scan a repository first.", body: "Implementation planning needs indexed files before Atlas can name an edit sequence.", primary: "Load sample repository", fn: "loadDemoMode('medium')", secondary: "Scan local repository", fn2: "go('scan')" },
    investigate: { el: "investigateOut", title: "Scan a repository first.", body: "Failure investigation needs repository evidence before Atlas can rank likely causes.", primary: "Load sample repository", fn: "loadDemoMode('medium')", secondary: "Scan local repository", fn2: "go('scan')" },
    impact: { el: "impactOut", title: "Scan a repository first.", body: "Change impact needs a dependency graph before Atlas can trace the blast radius.", primary: "Load sample repository", fn: "loadDemoMode('medium')", secondary: "Scan local repository", fn2: "go('scan')" },
  };
  const spec = map[view];
  if (!spec) return false;
  const host = $(spec.el);
  if (!host) return false;
  host.innerHTML = workflowEmptyHtml(spec.title, spec.body, spec.primary, spec.fn, spec.secondary, spec.fn2);
  return true;
}

function activeRepositoryKey(summary) {
  const s = summary || STATE.summary || {};
  return String(s.repo_id || s.repo_path || s.repo_name || "").trim();
}

function renderWorkflowContextLine(view) {
  const lines = { build: "buildContextLine", investigate: "investigateContextLine", impact: "impactContextLine" };
  const lineId = lines[view];
  const line = lineId ? $(lineId) : null;
  if (!line) return;
  if (!STATE.summary?.ok) {
    line.hidden = true;
    line.textContent = "";
    return;
  }
  const repo = STATE.summary.repo_name || "Current repository";
  const files = homeMetric(STATE.summary.file_count);
  const edges = homeMetric(STATE.summary.dependency_edges);
  line.hidden = false;
  line.textContent = `Ready · ${repo}${files ? ` · ${files} files` : ""}${edges ? ` · ${edges} dependencies` : ""}`;
}

function renderWorkflowEmptyState(view) {
  const specs = {
    build: {
      el: "buildOut",
      body: "Define the intended change. Atlas will rank affected files, sequence the work, and surface implementation risk.",
    },
    investigate: {
      el: "investigateOut",
      body: "Describe the observed failure. Atlas will correlate it with indexed code paths and rank testable hypotheses.",
    },
    impact: {
      el: "impactOut",
      body: "Choose a file or module. Atlas will trace direct dependents, transitive reach, affected tests, and unresolved edges.",
    },
  };
  const spec = specs[view];
  if (!spec || !STATE.summary?.ok) return false;
  const host = $(spec.el);
  if (!host) return false;
  if (host.querySelector(".impact-result-panel, .beginner-plan-card, .advanced-only.impact-card, .domain-panel")) return false;
  const current = host.textContent.trim();
  if (current && !current.startsWith("Scan a repository first") && !host.querySelector(".workflow-empty-state")) return false;
  host.innerHTML = `<div class="workflow-empty-state"><p class="muted">${spec.body}</p></div>`;
  host.dataset.atlasRepoKey = activeRepositoryKey();
  return true;
}

function renderWorkflowReadyState(view) {
  renderWorkflowContextLine(view);
  return renderWorkflowEmptyState(view);
}

function clearWorkflowInvestigationState() {
  STATE.buildResult = null;
  STATE.investigateResult = null;
  STATE.impactResult = null;
  [
    ["buildOut", "build"],
    ["investigateOut", "investigate"],
    ["impactOut", "impact"],
  ].forEach(([hostId, view]) => {
    const host = $(hostId);
    if (!host) return;
    delete host.dataset.atlasRepoKey;
    host.innerHTML = "";
    if (STATE.summary?.ok) {
      renderWorkflowEmptyState(view);
      renderWorkflowContextLine(view);
    } else {
      renderWorkflowGate(view);
      renderWorkflowContextLine(view);
    }
  });
  ["buildHistory", "investigateHistory", "impactHistory"].forEach((id) => {
    const host = $(id);
    if (host) host.innerHTML = "";
  });
  updateWorkflowToolbars();
  if (STATE.summary?.ok) {
    ["buildOut", "investigateOut", "impactOut"].forEach((id) => {
      const host = $(id);
      if (host) host.dataset.atlasRepoKey = activeRepositoryKey();
    });
  }
}

function workflowResultMatchesRepository(view) {
  const hosts = { build: "buildOut", investigate: "investigateOut", impact: "impactOut" };
  const host = $(hosts[view]);
  if (!host || !host.querySelector(".impact-result-panel, .beginner-plan-card, .advanced-only.impact-card, .domain-panel")) return false;
  const current = activeRepositoryKey();
  return !!current && host.dataset.atlasRepoKey === current;
}

function fiCapScore(score) {
  const n = Math.round(Number(score) || 0);
  return Math.max(0, Math.min(100, n));
}

function fiUserFacingStatus(status, goal) {
  if (status !== "Implemented") return status || "";
  const g = String(goal || "").toLowerCase();
  if (/^(add |implement |create |introduce |build |enable |new )/.test(g) || g.includes(" add ")) return "Proposed";
  return status;
}

const WORKFLOW_ERROR_FRIENDLY = {
  no_repository: "Scan a repository first.",
  stale_context: "Your repository changed — rescan or refresh, then try again.",
  partial_graph: "The dependency map is incomplete — try a narrower scan scope.",
  unsupported_language: "This repository uses languages with limited support.",
  grounding_gap: "Atlas needs more detail — include a file path or error message.",
};

function workflowErrorHtml(title, r, hint) {
  const code = r && r.code;
  const msg = r.demo_notice
    || (code && WORKFLOW_ERROR_FRIENDLY[code])
    || (r.error && !String(r.error).includes("_") ? r.error : null)
    || hint
    || "Something went wrong — try again or load the sample repository.";
  const extra = r.demo_notice ? "" : `<p class="muted tiny">${esc(hint || "")}</p>`;
  return `<div class="glass empty-panel"><h3 style="margin:0">${esc(title)}</h3><p class="muted">${esc(msg)}</p>${extra}</div>`;
}

function renderWorkflowQuickStarts(view) {
  if (!STATE.summary?.ok) return;
  const pack = STATE.demoPack || STATE.summary?.demo_pack || "medium";
  const byPack = {
    small: {
      build: "Improve error handling in core/hub.py",
      investigate: "API requests fail intermittently under load",
      impact: "core/hub.py",
    },
    medium: {
      build: "Add structured logging to API handlers",
      investigate: "API requests fail intermittently under load",
      impact: "api/handlers.py",
    },
    large: {
      build: "Improve error handling in gateway/entry.py",
      investigate: "API gateway returns 500 under load",
      impact: "platform/kernel.py",
    },
  };
  const packEx = byPack[pack] || byPack.small;
  const examples = {
    build: { text: packEx.build, target: "buildRequest", run: "runChangePlan" },
    investigate: { text: packEx.investigate, target: "investigateSymptom", run: "runInvestigationPlan" },
    impact: { text: packEx.impact, target: "impactTarget", run: "runImpact" },
  };
  const ex = examples[view];
  if (!ex) return;
  const io = document.querySelector(`#view-${view} .io`);
  if (!io || io.querySelector(".workflow-examples")) return;
  // Pre-fill the workflow input (e.g. the Plan Change box) with the pack-specific
  // example so the first action names a real file. Never overwrite user input.
  const field = $(ex.target);
  if (field && !field.value.trim()) field.value = ex.text;
  const box = document.createElement("div");
  box.className = "workflow-examples glass";
  box.innerHTML = `<span class="muted tiny">Try an example:</span>
    <button class="btn small ghost" type="button">${esc(ex.text)}</button>`;
  box.querySelector("button").onclick = function () {
    if (field) field.value = ex.text;
    window[ex.run]();
  };
  io.appendChild(box);
}

function showScanPanel(which) {
  const picker = $("scanPicker");
  if (picker) picker.style.display = (which === "running" || which === "success" || which === "failed") ? "none" : "block";
  $("scanRunning").style.display = which === "running" ? "block" : "none";
  $("scanSuccess").style.display = which === "success" ? "block" : "none";
  $("scanFailed").style.display = which === "failed" ? "block" : "none";
}

function expandScanLocal() {
  const panel = $("scanLocalPanel");
  if (panel) {
    panel.classList.remove("collapsed");
    const toggle = panel.querySelector(".scan-local-toggle");
    if (toggle) toggle.textContent = "▾ Local folder path";
  }
  setTimeout(() => $("repoPath")?.focus(), 80);
}

function toggleScanLocal() {
  const panel = $("scanLocalPanel");
  if (!panel) return;
  panel.classList.toggle("collapsed");
  const toggle = panel.querySelector(".scan-local-toggle");
  if (toggle) toggle.textContent = panel.classList.contains("collapsed") ? "▸ Local folder path" : "▾ Local folder path";
}

function updateHnProgress(step) {
  [1, 2, 3].forEach((n) => {
    const el = $("hnStep" + n);
    if (!el) return;
    el.classList.remove("done", "active");
    if (n < step) el.classList.add("done");
    else if (n === step) el.classList.add("active");
  });
}

async function startHnDemo() {
  if (!requireAtlasAccess("HN demo")) return;
  _hnDemoActive = true;
  updateHnProgress(1);
  const btn = $("hnLoadBtn");
  if (btn) { btn.disabled = true; btn.textContent = "Loading sample…"; }
  await loadDemoMode("medium");
  if (btn) { btn.disabled = false; btn.textContent = "Load sample repository"; }
}

function renderScanSkeleton() {
  const sk = $("scanSkeleton");
  if (sk) sk.innerHTML = Array.from({ length: 3 }, () => '<div class="skeleton"></div>').join("");
}

function showScanFailed(message, code) {
  showScanPanel("failed");
  const friendly = {
    empty_path: "No folder path was provided.",
    not_found: "Atlas could not find that folder on disk.",
    no_code_files: "This folder has no recognizable source files.",
    permission_denied: "Atlas does not have permission to read this folder.",
    partial_graph: "Scan finished but the dependency graph is incomplete.",
    symbols_missing: "Some files were indexed without symbol evidence.",
  };
  $("scanFailedMsg").textContent = friendly[code] || message || "The scan could not complete.";
  const hints = {
    empty_path: ["Enter the full path to your project root (not a single file).", "Example: C:\\dev\\my-app"],
    not_found: ["Check spelling and drive letter.", "Click Validate before scanning."],
    no_code_files: ["Choose a folder that contains .py, .ts, .js, or similar source files.", "Load a sample repository to explore Atlas first."],
    permission_denied: ["Run Atlas from an account that can read the folder.", "Avoid Windows system folders and protected drives."],
    partial_graph: ["You can still run Plan Change — some files may have fewer links.", "For your own repo: try scan scope “Only backend” or “Only Python”."],
    not_directory: ["Choose the repository root folder, not a single file.", "Use Browse or paste the parent directory path."],
    symbols_missing: ["Plan Change and Debug may have fewer file anchors.", "Re-scan after fixing syntax errors in key entry files."],
  };
  $("scanFailedHints").innerHTML = (hints[code] || [
    "Load a sample repository to see Atlas working end-to-end.",
    "Pick a different folder or adjust scan scope.",
  ]).map(h => `<li>${h}</li>`).join("");
}

function renderScanSuccess(scan) {
  showScanPanel("success");
  const titleEl = $("scanSuccessTitle");
  if (titleEl) titleEl.textContent = scan.demo_mode ? "Atlas understood the sample repository." : "Atlas understood your repository.";
  const demo = scan.demo_mode ? " · Sample repository" : "";
  $("scanSuccessSub").textContent = `${scan.repo_name || "Repository"} indexed in ${scan.scan_duration_seconds || "?"}s${demo}`;

  // Token savings vs raw context paste
  const modules = scan.module_count || 0;
  const rawEst = Math.round(modules * 420);   // ~420 tokens per file if pasted raw
  const exportEst = 86 + Math.min(modules * 4, 600); // memory header + delta
  const savedPct = rawEst > 0 ? Math.round((1 - exportEst / rawEst) * 100) : 97;
  const tokenSavingNote = modules > 5
    ? `<div class="metric"><div class="mv" style="color:var(--green)">${savedPct}%</div><div class="ml">tokens saved<br><span style="font-size:10px;color:var(--muted)">vs pasting raw</span></div></div>`
    : "";

  $("scanSuccessMetrics").innerHTML = [
    ["Files", scan.file_count],
    ["Modules", scan.module_count],
    ["Architecture groups", scan.subsystem_count],
  ].map(([l, v]) => `<div class="metric"><div class="mv">${v ?? "—"}</div><div class="ml">${l}</div></div>`).join("") + tokenSavingNote;

  // Plain-language risk: most depended-on module, not raw score
  const risk = scan.top_risks?.[0];
  const riskPath = risk ? (risk.module || risk.path || "") : "";
  const riskName = riskPath.split(/[/\\]/).pop().replace(/\.py$/, "");
  $("scanSuccessRisk").innerHTML = risk && riskName
    ? `<b style="color:var(--amber)">Most depended-on:</b> <span class="tag">${esc(riskPath)}</span> — changes here ripple furthest.`
    : `<span class="muted">No high-coupling modules found.</span>`;

  const nextActions = scan.demo_mode
    ? [`Run a repository analysis: ${DEFAULT_FIRST_QUESTION}`, "The report will include cited evidence and relevant files."]
    : ["Define your first repository investigation.", "Use Architecture Map, Failure Investigation, Change Impact, and Implementation Plan for deeper analysis."];
  $("scanSuccessActions").innerHTML = nextActions.map(a => `<li>${a}</li>`).join("");
  if (typeof renderScanReliabilityNotice === "function") renderScanReliabilityNotice(scan);

  // Populate the "What breaks?" file picker with top scanned files
  _populateImpactFilePicker(scan);

  // Repository Understanding feedback funnel.
  const ufs = $("understandingFeedbackSlot");
  if (ufs && typeof workflowFeedbackHtml === "function") ufs.innerHTML = workflowFeedbackHtml("understanding");
}

function _populateImpactFilePicker(scan) {
  const host = $("impactFilePicker");
  if (!host) return;
  const risks = (scan.top_risks || []).slice(0, 6).map(r => r.module || r.path).filter(Boolean);
  if (!risks.length) { host.innerHTML = ""; return; }
  host.innerHTML = `<span class="muted">Pick from your riskiest files: </span>`
    + risks.map(p => `<button class="btn tiny ghost" type="button" style="margin:2px" onclick="$('impactTarget').value=${JSON.stringify(p)};runImpact()">${esc(p.split(/[/\\]/).pop())}</button>`).join("");
}

async function validateRepoPath(showToast) {
  if (!requireAtlasAccess("Repository validation")) return null;
  const path = ($("repoPath").value || "").trim();
  $("pathError").style.display = "none";
  $("pathOk").style.display = "none";
  if (!path) {
    updateScanBtnState(false);
    $("pathError").style.display = "block";
    $("pathError").textContent = "Enter a folder path first.";
    if (showToast) toast("Enter a folder path", "error");
    return null;
  }
  const res = await api("/api/repositories/validate", "POST", { path });
  if (!res.ok) {
    updateScanBtnState(false);
    $("pathError").style.display = "block";
    const msg = typeof friendlyValidateMessage === "function" ? friendlyValidateMessage(res) : (res.error || "Invalid path");
    $("pathError").textContent = msg;
    if (showToast) toast("✗ " + msg, "error");
    return null;
  }
  updateScanBtnState(true);
  $("pathOk").style.display = "block";
  $("pathOk").textContent = `✓ ${res.name} — ${res.code_files} code file(s) found`;
  if (res.warnings?.length) {
    $("pathOk").textContent += " · " + res.warnings.join(" ");
  }
  if (showToast) toast("Path validated ✓", "success");
  try {
    const estimate = await api("/api/repositories/estimate", "POST", { path: res.path, scope: readScopeConfig() });
    STATE.lastEstimate = estimate.ok ? estimate : null;
    if (estimate.ok) {
      updateMassiveBadge(!!estimate.massive_mode_auto || !!readScopeConfig().manual_massive_mode);
      $("preScanEstimate").textContent =
        `${estimate.total_files} files · ${estimate.code_files} code · ${estimate.repo_size_mb} MB · ` +
        `~${estimate.likely_scan_time_seconds}s · suggested: ${(estimate.suggested_scopes || []).join(", ")}`;
    }
  } catch (e) {}
  return res;
}

async function browseRepoFolder() {
  if (!requireAtlasAccess("Folder selection")) return;
  const btn = $("browseRepoBtn");
  if (btn) { btn.disabled = true; btn.textContent = "Opening…"; }
  try {
    const res = await api("/api/system/browse-folder", "POST", {});
    if (res.cancelled) return;
    if (!res.ok || !res.path) {
      const fallback = res.message || res.error || "Paste the folder path manually.";
      $("pathError").style.display = "block";
      $("pathError").textContent = fallback;
      if (res.code !== "unsupported_browse_dialog" && res.error !== "unsupported_browse_dialog") {
        toast("Browse unavailable — paste a path manually", "error");
      } else {
        toast(fallback, "error");
      }
      return;
    }
    $("repoPath").value = res.path;
    await validateRepoPath(true);
  } catch (e) {
    $("pathError").style.display = "block";
    $("pathError").textContent = "Native folder selection is unavailable. Paste the repository path manually.";
    toast("Browse unavailable — paste a path manually", "error");
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "Browse"; }
  }
}

function updateScanBtnState(enabled) {
  const btn = $("scanBtn");
  if (!btn) return;
  if (enabled) btn.removeAttribute("disabled");
  else btn.setAttribute("disabled", "");
}

/* ---------- Auto-validate on path input (eliminates separate Validate button) ---------- */
let _autoValidateTimer = null;
function debouncedAutoValidate() {
  if (_autoValidateTimer) clearTimeout(_autoValidateTimer);
  const path = ($("repoPath") && $("repoPath").value || "").trim();
  if (!path) { updateScanBtnState(false); return; }
  $("pathOk") && ($("pathOk").style.display = "none");
  $("pathError") && ($("pathError").style.display = "none");
  // Short debounce so fast typists don't fire a request each keystroke
  _autoValidateTimer = setTimeout(function () { validateRepoPath(false); }, 600);
}

function goToScanStart() {
  go("scan");
  setTimeout(() => $("repoPath")?.focus(), 120);
}

function focusCopilot() {
  go("ask");
  setTimeout(() => $("askInput")?.focus(), 120);
}

function primeAskAtlasPrompt(scan) {
  const question = _hnDemoActive ? HN_FIRST_QUESTION : DEFAULT_FIRST_QUESTION;
  const field = $("askInput");
  if (field) field.value = question;
  const status = $("askStatus");
  if (status) {
    const repo = scan?.repo_name || STATE.summary?.repo_name || "Repository";
    status.textContent = `${repo} indexed. Define an investigation or choose a template.`;
  }
  if ($("suggest")) $("suggest").innerHTML = renderCopilotSuggestions(STATE.summary || scan || {});
  updateHnProgress(2);
}

function routeToAskAfterScan(scan) {
  setTimeout(function () {
    go("ask");
    primeAskAtlasPrompt(scan);
    updateHnProgress(3);
    toast("Repository indexed. Analysis is ready.", "success");
    if (_hnDemoActive && window.atlasDemoTour) atlasDemoTour.start();
    _hnDemoActive = false;
  }, scan?.demo_mode ? 250 : 650);
}

function finishScanSession(scan, pathLabel) {
  if (pathLabel && !scan.demo_mode) pushRecent(pathLabel, scan);
  else if (scan.demo_mode) pushRecent(scan.repo_path || "Atlas Demo", scan);
  window.atlasActivity?.add(scan.demo_mode ? "Sample repository indexed" : "Repository indexed");
  STATE.graph = null;
  STATE.graph3d = null;
  STATE.graphPerf = null;
  STATE.graphView = resolveDefaultGraphView(scan?.module_count);
  STATE._graphViewUserPicked = false;
  document.querySelectorAll('input[name="graphView"]').forEach(el => {
    el.checked = el.value === STATE.graphView;
  });
  updateTelemetryWarning(scan);
  updateRepoChip(scan.repo_name, scan.demo_mode);
  unlockNav();
  document.body.classList.remove("atlas-no-repo");  // repo scanned → reveal repo-dependent UI
  updateWorkflowToolbars();
  renderScanSuccess(scan);
  try {
    if (localStorage.getItem(ONBOARDING_KEY) !== "1") {
      localStorage.setItem(ONBOARDING_KEY, "1");
      $("onboarding").style.display = "none";
    }
  } catch (e) {}
  routeToAskAfterScan(scan);
}

async function loadDemoMode(pack) {
  if (!requireAtlasAccess("Sample repository")) return;
  dismissOnboarding(true);
  if (typeof hideHomeScanFocus === "function") hideHomeScanFocus();
  const packId = pack || STATE.demoPack || DEFAULT_DEMO_PACK;
  if (_hnDemoActive) updateHnProgress(1);
  go("scan");
  showScanPanel("running");
  $("scanPath").textContent = `Loading Atlas demo (${packId})…`;
  renderScanSkeleton();
  setBar(30);
  const scan = await api("/api/demo/load", "POST", { pack: packId });
  setBar(100);
  if (!scan.ok) { showScanFailed(scan.error, scan.code); toast("✗ Demo load failed", "error"); return; }
  STATE.demoPack = scan.demo_pack || packId;
  try { localStorage.setItem(DEMO_PACK_KEY, STATE.demoPack); } catch (e) {}
  STATE.summary = await api("/api/repositories/current/summary");
  STATE.sessionExport = await api("/api/repositories/current/session-export");
  STATE.exportMode = "MINIMAL_EXPORT";
  finishScanSession(scan, null);
  toast("Demo loaded ✓", "success");
}

async function renderDemoPackPicker() {
  const host = $("demoPackList");
  if (!host) return;
  const res = await api("/api/demo/packs");
  if (!res.ok || !(res.packs || []).length) {
    host.innerHTML = `<span class="muted tiny">Sample repositories unavailable — restart Atlas or check your install.</span>`;
    return;
  }
  let selected = STATE.demoPack || DEFAULT_DEMO_PACK;
  try {
    const saved = localStorage.getItem(DEMO_PACK_KEY);
    if (saved) selected = saved;
  } catch (e) {}
  STATE.demoPack = selected;
  host.innerHTML = res.packs.map(p => `
    <div class="demo-pack-card glass ${p.id === selected ? "active" : ""}" onclick="selectDemoPack(${JSON.stringify(p.id)})">
      <h4>${p.label}</h4>
      <p>${p.description}</p>
    </div>`).join("");
}

function selectDemoPack(id) {
  STATE.demoPack = id;
  try { localStorage.setItem(DEMO_PACK_KEY, id); } catch (e) {}
  renderDemoPackPicker();
  loadDemoMode(id);
}

const HOME_AGENT_LABELS = { claude: "Claude Code", cursor: "Cursor", codex: "Codex" };

function homeConnectedAgents(status) {
  return Object.keys(HOME_AGENT_LABELS).filter(key => !!(status?.[key]?.connected || status?.connections?.clients?.[key]?.connected));
}

function setHomeText(id, value) {
  const el = $(id);
  if (el) el.textContent = value;
}

function homeMetric(value) {
  if (value === null || value === undefined || value === "") return "";
  return Number.isFinite(Number(value)) ? Number(value).toLocaleString() : "";
}

function homeDisplayName(value) {
  return String(value || "").replace(/[-_]+/g, " ").replace(/\s+/g, " ").trim();
}

function setHomeFact(id, value) {
  const el = $(id);
  if (!el) return;
  const visible = value !== null && value !== undefined && String(value).trim() !== "";
  el.textContent = visible ? String(value) : "";
  if (el.parentElement) el.parentElement.hidden = !visible;
}

function homeLastIndexed(summary, recent) {
  const repoPath = String(summary?.repo_path || "").toLowerCase().replace(/\\/g, "/");
  const match = (recent || []).find(item => String(item.repo_path || "").toLowerCase().replace(/\\/g, "/") === repoPath);
  if (!match?.last_scan_at) return "";
  const date = new Date(match.last_scan_at);
  return Number.isNaN(date.getTime()) ? String(match.last_scan_at) : date.toLocaleString();
}

function renderHomeExperience(update) {
  if (update?.mcpStatus) STATE.homeMcpStatus = update.mcpStatus;
  if (update?.trustStatus) STATE.homeTrustStatus = update.trustStatus;
  if (Array.isArray(update?.recent)) STATE.homeRecent = update.recent;
  const dash = $("homeDashboard");
  if (!dash) return "empty";

  const summary = STATE.summary;
  const hasRepo = !!summary?.ok;
  const agents = homeConnectedAgents(STATE.homeMcpStatus);
  const state = !hasRepo ? "empty" : (agents.length ? "productive" : "indexed");
  if (dash.dataset.homeState !== state) dash.dataset.homeState = state;
  dash.querySelectorAll("[data-home-panel]").forEach(panel => {
    const active = panel.dataset.homePanel === state;
    panel.hidden = !active;
    panel.setAttribute("aria-hidden", active ? "false" : "true");
  });

  if (!hasRepo) return state;
  const repoName = homeDisplayName(summary.repo_name) || "Current repository";
  const fileCount = homeMetric(summary.file_count);
  const agentNames = agents.map(key => HOME_AGENT_LABELS[key]);
  const agentText = agentNames.length ? agentNames.join(", ") : "No agent connected";
  const trustLabel = STATE.homeTrustStatus?.user_trust_label || "Checking";
  const restored = !!STATE.homeHealth?.persistence?.restored;
  const stale = trustLabel !== "Fresh" && trustLabel !== "Checking";

  setHomeFact("homeRepoName", repoName);
  setHomeFact("homeFileCount", fileCount);
  setHomeFact("homeNodeCount", homeMetric(summary.module_count));
  setHomeFact("homeEdgeCount", homeMetric(summary.dependency_edges));
  setHomeFact("homeLastIndexed", homeLastIndexed(summary, STATE.homeRecent));
  setHomeFact("homeRestoreStatus", restored ? "Repository restored" : "Ready for fresh agent sessions");
  setHomeText("homeFreshness", trustLabel);
  setHomeText("homeIndexedTitle", stale ? "Repository needs refresh." : "Repository ready.");
  setHomeText("homeIndexedLead", stale
    ? "Repository changed since the last index. Refresh before relying on graph evidence."
    : "Atlas already knows this repository. Connect the coding agent you use next, or open repository analysis.");
  setHomeText("homeProductiveKicker", stale ? "Repository context needs refresh" : "Repository context ready");
  setHomeText("homeProductiveRepoName", repoName);
  setHomeText("homeProductiveContext", stale
    ? "changed since indexing. Refresh before relying on graph evidence. Connected agent:"
    : "has current repository evidence available to");
  setHomeText("homeConnectedAgents", agentNames.join(" and ") || "your agent");
  setHomeText("homeCompactRepo", repoName);
  setHomeText("homeCompactFiles", fileCount);
  setHomeText("homeCompactAgents", agentText);
  setHomeText("homeProductiveFreshness", trustLabel);
  [$("homeFreshness"), $("homeProductiveFreshness")].forEach(el => {
    if (!el) return;
    el.classList.toggle("is-fresh", trustLabel === "Fresh");
    el.classList.toggle("is-stale", stale);
  });
  window.atlasActivity?.render();
  return state;
}

async function refreshHomeExperience() {
  renderHomeExperience();
  if (!STATE.summary?.ok) return;
  const recent = await api("/api/repositories/recent").catch(() => null);
  renderHomeExperience({
    recent: recent?.ok ? (recent.items || []) : STATE.homeRecent,
  });
  if (!window.atlasHomeTrustTimer) {
    window.atlasHomeTrustTimer = window.setTimeout(async () => {
      window.atlasHomeTrustTimer = null;
      const trust = await requestAtlasTrustStatus().catch(() => null);
      renderHomeExperience({
        trustStatus: trust?.ok ? trust : null,
        recent: recent?.ok ? (recent.items || []) : STATE.homeRecent,
      });
    }, 7000);
  }
}

function focusHomeAgentConnections() {
  const section = $("mcpSetupSection");
  section?.scrollIntoView({ block: "start", behavior: "smooth" });
  const disconnected = homeConnectedAgents(STATE.homeMcpStatus);
  const next = ["claude", "cursor", "codex"].find(key => !disconnected.includes(key)) || "claude";
  setTimeout(() => $(`mcp${next.charAt(0).toUpperCase() + next.slice(1)}Btn`)?.focus(), 180);
}

function submitHomeAsk(event) {
  event?.preventDefault();
  const source = $("homeAskInput");
  const prompt = String(source?.value || "").trim();
  if (!prompt) { source?.focus(); return; }
  if ($("askInput")) $("askInput").value = prompt;
  go("ask");
  sendCopilotQuestion();
}

function routeHomeSuggestion(view, prompt) {
  if (view === "ask" && prompt && $("askInput")) $("askInput").value = prompt;
  go(view);
  const targets = { ask: "askInput", impact: "impactTarget", investigate: "investigateSymptom", build: "buildRequest" };
  setTimeout(() => $(targets[view])?.focus(), 60);
}

window.renderHomeExperience = renderHomeExperience;

function atlasScrollContainer() {
  return document.getElementById("app") || document.scrollingElement || document.documentElement;
}

function resetViewScroll(viewEl) {
  const root = atlasScrollContainer();
  root.scrollTo({ top: 0, behavior: "auto" });
  window.scrollTo({ top: 0, behavior: "auto" });
  if (!viewEl) return;
  viewEl.querySelectorAll(".table-scroll, .memory-workbench, .memory-concepts, .memory-inspector, .ask-history-rail, .ask-evidence-rail, .files-workbench").forEach((el) => {
    el.scrollTop = 0;
  });
}

function go(view) {
  if (document.body.classList.contains('auth-mode') && view !== 'accounts') return;
  view = NAV_ALIASES[view] || view;
  // Admin Console is restricted to admin/superadmin accounts.
  if (view === "admin" && !(window.atlasAccounts && atlasAccounts.isAdmin && atlasAccounts.isAdmin())) {
    if (typeof toast === "function") toast("Admin access required", "error");
    view = "accounts";
  }
  if (PROTECTED_VIEWS.has(view) && !requireAtlasAccess("Atlas")) return;
  desktopEngagement.viewChanged(view);
  document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
  const el = $("view-" + view); if (el) el.classList.add("active");
  document.querySelectorAll("#nav button").forEach(b => {
    const target = NAV_ALIASES[b.dataset.view] || b.dataset.view;
    b.classList.toggle("active", target === view);
    if (target === view) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  });
  const reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  resetViewScroll(el);
  document.dispatchEvent(new CustomEvent("atlas:viewchange", { detail: { view } }));
  if (el && view !== "home") {
    setTimeout(() => el.querySelector("h1[tabindex='-1'], h2[tabindex='-1'], h1, h2")?.focus({ preventScroll: true }), 60);
  }
  if (view === "center") {
    trackAnalytics("graph_opened");
    api("/api/usage/event", "POST", { event_type: "repository_map_opened" }).catch(function () {});
    setTimeout(renderCenter, 60);
  }
  if (view === "home") {
    if (window.STATE && STATE.summary && STATE.summary.ok) document.body.classList.remove("atlas-no-repo");
    if (typeof atlasPollTrustStatus === "function") atlasPollTrustStatus();
    refreshHomeExperience();
    setTimeout(() => $("homeDashboard")?.querySelector("[data-home-panel]:not([hidden]) h1")?.focus(), 60);
  }
  if (view === "scan") {
    showScanPanel(null);
    loadRecent();
  }
  if (view === "hn") updateHnProgress(STATE.summary?.ok ? 3 : 1);
  if (view === "ask") renderAskPage();
  if (view === "export") refreshExport();
  if (view === "build" || view === "investigate" || view === "impact") {
    if (!STATE.summary?.ok) renderWorkflowGate(view);
    else {
      if (!workflowResultMatchesRepository(view)) {
        renderWorkflowReadyState(view);
      } else {
        renderWorkflowContextLine(view);
      }
      renderWorkflowQuickStarts(view);
      if (view === "build") showFirstBuildBannerIfNeeded();
    }
  }
}

function showFirstBuildBannerIfNeeded() {
  const banner = $("firstBuildBanner");
  if (!banner || !STATE.summary?.ok) return;
  let done = false;
  try { done = localStorage.getItem("atlas_first_build_plan_done") === "1"; } catch (e) {}
  banner.style.display = done ? "none" : "block";
}
function applyBillingNav(enabled, isAdmin) {
  const nav = $("billingNav");
  if (nav) nav.style.display = enabled ? "inline-flex" : "none";
  document.querySelectorAll(".billing-admin").forEach(el => {
    el.style.display = enabled && isAdmin ? "" : "none";
  });
}

function unlockNav() { document.querySelectorAll('#nav button[data-lock="1"]').forEach(b => b.removeAttribute("data-lock")); }

function updateWorkflowToolbars() {
  const on = !!STATE.summary?.ok;
  const hasBuild = !!(STATE.buildResult && STATE.buildResult.ok);
  const hasInvestigate = !!(STATE.investigateResult && STATE.investigateResult.ok);
  const hasImpact = !!(STATE.impactResult && STATE.impactResult.ok);
  [
    ["buildToolbar", hasBuild],
    ["investigateToolbar", hasInvestigate],
    ["impactToolbar", hasImpact],
  ].forEach(([id, show]) => {
    const el = $(id);
    if (el) el.style.display = on && show ? "flex" : "none";
  });
}

function selectRecentPath(p) {
  $("repoPath").value = p;
  validateRepoPath(false);
}

/* ---------------- Recent repos ---------------- */
function normalizeRecentEntry(raw) {
  if (!raw) return null;
  if (typeof raw === "string") return { path: raw, name: raw.split(/[\\/]/).pop() || raw, scanned_at: "", files: 0, modules: 0, duration_sec: 0, size_mb: 0 };
  return {
    path: raw.path || "",
    name: raw.name || (raw.path || "").split(/[\\/]/).pop() || raw.path,
    scanned_at: raw.scanned_at || "",
    files: raw.files || 0,
    modules: raw.modules || 0,
    duration_sec: raw.duration_sec || 0,
    size_mb: raw.size_mb || 0,
  };
}

function isHiddenRecentRepo(entry) {
  const name = (entry.name || entry.path || "").split(/[\\/]/).pop() || "";
  const base = name.replace(/\.(py|js|ts)$/i, "");
  if (RECENT_HIDE_PATTERNS.some((p) => p.test(name) || p.test(base))) return true;
  if (/^app$/i.test(base) && (entry.path || "").split(/[\\/]/).length <= 3) return true;
  return false;
}

function dedupeRecentList(list) {
  const seenPaths = new Set();
  const seenNames = new Set();
  const out = [];
  for (const raw of list) {
    const e = normalizeRecentEntry(raw);
    if (!e || !e.path) continue;
    const pathKey = e.path.toLowerCase().replace(/\\/g, "/");
    const nameKey = (e.name || "").toLowerCase();
    if (seenPaths.has(pathKey)) continue;
    if (nameKey && seenNames.has(nameKey)) continue;
    if (isHiddenRecentRepo(e)) continue;
    seenPaths.add(pathKey);
    if (nameKey) seenNames.add(nameKey);
    out.push(e);
  }
  return out;
}

function toggleRecentExpanded() {
  _recentExpanded = !_recentExpanded;
  loadRecent();
}

async function loadRecent() {
  let list = [];
  try {
    const remote = await api("/api/repositories/recent");
    if (remote.ok && (remote.items || []).length) {
      list = remote.items.map(it => ({
        path: it.repo_path,
        name: it.repo_name,
        scanned_at: it.last_scan_at,
        files: it.file_count,
        modules: it.module_count,
        graph_health: it.graph_health,
        repo_id: it.repo_id,
        can_resume: it.can_resume,
      })).filter(e => e.path);
    }
  } catch (e) {}
  if (!list.length) {
    try { list = JSON.parse(localStorage.getItem(RECENT_KEY) || "[]"); } catch (e2) {}
    if (!list.length) {
      try {
        const legacy = JSON.parse(localStorage.getItem(LEGACY_RECENT_KEY) || "[]");
        if (legacy.length) { list = legacy.map(normalizeRecentEntry).filter(Boolean); localStorage.setItem(RECENT_KEY, JSON.stringify(list)); }
      } catch (e3) {}
    }
  }
  list = dedupeRecentList(list.map(normalizeRecentEntry).filter((e) => e && e.path));
  const box = $("recentList");
  const showAllBtn = $("recentShowAllBtn");
  if (!box) return;
  if (!list.length) {
    box.innerHTML = '<span class="muted tiny">No history yet — load the sample or scan a folder.</span>';
    if (showAllBtn) showAllBtn.style.display = "none";
    return;
  }
  const visible = _recentExpanded ? list : list.slice(0, RECENT_MAX_VISIBLE);
  box.innerHTML = visible.map(entry => {
    const when = entry.scanned_at ? entry.scanned_at.replace("T", " ").slice(0, 16) : "last session";
    const meta = `${entry.files || "—"} files · ${entry.modules || "—"} modules`;
    const resume = entry.repo_id && entry.can_resume
      ? ` onclick="resumePersistedScan(${JSON.stringify(entry.repo_id)})"`
      : ` onclick="selectRecentPath(${JSON.stringify(entry.path)})"`;
    return `<button type="button" class="recent-card" title="${esc(entry.path)}"${resume}>
      <span class="recent-name">${esc(entry.name)}</span>
      <span class="recent-meta muted tiny">${esc(meta)}</span>
      <span class="recent-when muted tiny">${esc(when)}</span>
    </button>`;
  }).join("");
  if (showAllBtn) {
    if (list.length > RECENT_MAX_VISIBLE) {
      showAllBtn.style.display = "";
      showAllBtn.textContent = _recentExpanded ? "Show less" : "Show all";
    } else {
      showAllBtn.style.display = "none";
    }
  }
}

function renderResumeCard(card) {
  const host = $("resumeScanCard");
  if (!host) return;
  if (!card || !card.repo_id || STATE.summary?.ok) {
    host.style.display = "none";
    host.innerHTML = "";
    return;
  }
  const when = card.last_scan_at ? card.last_scan_at.replace("T", " ").slice(0, 16) : "recently";
  const gh = card.graph_health || "unknown";
  const title = card.can_resume ? `Resume ${card.repo_name}` : (card.needs_refresh ? `Refresh ${card.repo_name}` : card.repo_name);
  const meta = `Last scanned ${when} · Files: ${card.file_count || "—"} · Modules: ${card.module_count || "—"} · Graph: ${gh}`;
  host.style.display = "block";
  host.innerHTML = `<div class="resume-scan-head">
      <div><h3 style="margin:0 0 4px;font-size:16px">${esc(title)}</h3><p class="muted tiny" style="margin:0">${esc(meta)}</p>
      <p class="muted tiny" style="margin:6px 0 0">${esc(card.path_display || card.repo_path || "")}</p></div>
    </div>
    <div class="resume-scan-actions">
      ${card.can_resume ? `<button class="btn primary" type="button" onclick="resumePersistedScan(${JSON.stringify(card.repo_id)})">Resume</button>` : ""}
      ${card.needs_refresh ? `<button class="btn ghost" type="button" onclick="refreshPersistedScan(${JSON.stringify(card.repo_id)}, ${JSON.stringify(card.repo_path || "")})">Refresh changed files</button>` : ""}
      <button class="btn ghost" type="button" onclick="fullRescanFromResume(${JSON.stringify(card.repo_path || "")})">Full rescan</button>
      <button class="btn ghost" type="button" onclick="showHomeScanFocus()">Scan another repository</button>
    </div>`;
}

async function resumePersistedScan(repoId) {
  const r = await api("/api/repositories/resume", "POST", { repo_id: repoId });
  if (!r.ok) {
    toast(r.error || "Could not resume", "error");
    if (r.code === "stale_scan" && r.validation) renderResumeCard({ ...r.validation, repo_id: repoId, needs_refresh: true });
    return;
  }
  STATE.summary = r.summary || await api("/api/repositories/current/summary");
  unlockNav();
  document.body.classList.remove("atlas-no-repo");
  updateRepoChip(r.repo_name || STATE.summary?.repo_name, false);
  renderResumeCard(null);
  toast(`Resumed ${r.repo_name || "repository"}`, "success");
  go("ask");
  primeAskAtlasPrompt({ repo_name: r.repo_name || STATE.summary?.repo_name });
}

async function refreshPersistedScan(repoId, repoPath) {
  const resumed = await api("/api/repositories/resume", "POST", { repo_id: repoId });
  if (!resumed.ok && resumed.code !== "stale_scan") {
    toast(resumed.error || "Resume first failed", "error");
    return;
  }
  if (repoPath && $("repoPath")) $("repoPath").value = repoPath;
  const r = await api("/api/repositories/current/refresh-changed-files", "POST", {});
  toast(r.ok ? (r.message || "Refresh complete") : (r.error || "Refresh failed"), r.ok ? "success" : "error");
  if (typeof atlasPollTrustStatus === "function") atlasPollTrustStatus();
  await loadRecent();
}

function fullRescanFromResume(repoPath) {
  if (repoPath && $("repoPath")) $("repoPath").value = repoPath;
  showHomeScanFocus();
  validateRepoPath(false).then(() => scanFlow());
}

function renderWorkflowHistory(workflowType, hostId) {
  const host = $(hostId);
  if (!host) return;
  api(`/api/history?workflow_type=${encodeURIComponent(workflowType)}`).then(data => {
    const items = (data.items || []).slice(0, 5);
    if (!items.length) { host.innerHTML = ""; return; }
    host.innerHTML = `<div class="workflow-history glass">
      <div class="report-label">Recent results</div>
      ${items.map(it => `<div class="workflow-history-item">
        <button class="btn ghost small" type="button" onclick="reopenHistoryItem(${JSON.stringify(it.history_id)}, ${JSON.stringify(workflowType)})">${esc((it.request_text || "").slice(0, 48))}</button>
        <span class="muted tiny">${esc((it.created_at || "").slice(0, 16).replace("T", " "))}</span>
        ${(it.historical_only || it.stale_reason) ? `<span class="workflow-history-stale">${esc(it.stale_reason || "Historical result — reopen to verify")}</span>` : ""}
      </div>`).join("")}
    </div>`;
  }).catch(() => { host.innerHTML = ""; });
}

async function reopenHistoryItem(historyId, workflowType) {
  const r = await api(`/api/history/item?history_id=${encodeURIComponent(historyId)}`);
  if (!r.ok || !r.item) { toast(r.error || "Could not load history", "error"); return; }
  const item = r.item;
  const currentRepo = activeRepositoryKey();
  const itemRepo = String(item.repo_id || item.repository_id || "").trim();
  const staleFromOtherRepo = !!(currentRepo && itemRepo && itemRepo !== currentRepo);
  const staleNote = staleFromOtherRepo
    ? `<p class="workflow-history-stale">Historical result from another repository — rerun analysis for the current repository.</p>`
    : (item.export_allowed === false
      ? `<p class="workflow-history-stale">Refresh before exporting — ${esc(item.stale_reason || "context is stale")}</p>` : "");
  const md = esc(item.summary_markdown || "");
  if (workflowType === "build") {
    if ($("buildRequest") && item.request_text) $("buildRequest").value = item.request_text;
    STATE.buildResult = { ok: true, plan: (item.result_json || {}).plan || {}, formatted: item.summary_markdown || "", export_blocked: !item.export_allowed };
    $("buildOut").innerHTML = `${staleNote}<pre class="code" style="max-height:360px;overflow:auto">${md}</pre>`;
    go("build");
  } else if (workflowType === "investigate") {
    if ($("investigateSymptom") && item.request_text) $("investigateSymptom").value = item.request_text;
    STATE.investigateResult = { ok: true, plan: (item.result_json || {}).plan || {}, formatted: item.summary_markdown || "", export_blocked: !item.export_allowed };
    $("investigateOut").innerHTML = `${staleNote}<pre class="code" style="max-height:360px;overflow:auto">${md}</pre>`;
    go("investigate");
  } else {
    if ($("impactTarget") && item.request_text) $("impactTarget").value = item.request_text;
    $("impactOut").innerHTML = `${staleNote}<pre class="code" style="max-height:360px;overflow:auto">${md}</pre>`;
    go("impact");
  }
  if (item.export_allowed === false) toast("Saved result is stale — refresh before exporting", "error");
}

function pushRecent(p, scan) {
  if (!p) return;
  const entry = {
    path: p,
    name: (scan && scan.repo_name) || p.split(/[\\/]/).pop() || p,
    scanned_at: new Date().toISOString().slice(0, 19),
    files: scan?.file_count || 0,
    modules: scan?.module_count || 0,
    duration_sec: scan?.scan_duration_seconds || 0,
    size_mb: scan?.repo_size_mb || STATE.lastEstimate?.repo_size_mb || 0,
  };
  let list = [];
  try { list = JSON.parse(localStorage.getItem(RECENT_KEY) || "[]"); } catch (e) {}
  list = list.map(normalizeRecentEntry).filter(e => e && e.path);
  list = [entry, ...list.filter(x => x.path !== p)].slice(0, 8);
  try { localStorage.setItem(RECENT_KEY, JSON.stringify(list)); } catch (e) {}
  loadRecent();
}

/* ---------------- Scan flow ---------------- */
const STAGES = ["Indexing files…", "Building dependency graph…", "Preparing repository analysis…"];

const STAGE_LABEL_INDEX = {};
STAGES.forEach((label, i) => { STAGE_LABEL_INDEX[label] = i; });

function applyScanStatus(status) {
  if (!status || !status.ok) return;
  const label = status.stage_label || "";
  const pct = status.progress_pct || 0;
  setBar(pct);
  let idx = STAGE_LABEL_INDEX[label];
  if (idx === undefined) {
    const lower = label.toLowerCase();
    if (lower.includes("index") || lower.includes("scan") || lower.includes("file")) idx = 0;
    else if (lower.includes("graph") || lower.includes("depend") || lower.includes("architect")) idx = 1;
    else idx = 2;
  }
  const mapped = Math.min(idx, STAGES.length - 1);
  STAGES.forEach((_, i) => {
    if (i < mapped) setStage(i, "done");
    else if (i === mapped) setStage(i, "run");
    else setStage(i, "todo");
  });
  const lbl = $("st" + mapped)?.querySelector(".lbl");
  if (lbl) lbl.textContent = STAGES[mapped];
}

async function pollScanProgress(stopRef) {
  while (!stopRef.stop) {
    const status = await api("/api/repositories/current/scan-status");
    applyScanStatus(status);
    if (status.scan_complete) break;
    await sleep(400);
  }
}

async function scanFlow() {
  if (!requireAtlasAccess("Repository scan")) return;
  const validation = await validateRepoPath(true);
  if (!validation) return;
  const broad = validation.broad_warnings || [];
  if (broad.length && typeof atlasShowBroadFolderModal === "function") {
    atlasShowBroadFolderModal(broad, function () { executeScanFlow(validation); });
    return;
  }
  return executeScanFlow(validation);
}

async function executeScanFlow(validation) {
  if (!requireAtlasAccess("Repository scan")) return;
  const path = validation.path;
  const sel = await api("/api/repositories/select", "POST", { path });
  if (!sel.ok) { toast("✗ " + (sel.error || "Invalid path"), "error"); return; }
  STATE.repo = sel;
  updateRepoChip(sel.name, false);
  $("scanPath").textContent = sel.path;
  go("scan");
  showScanPanel("running");
  $("stages").innerHTML = STAGES.map((s, i) => `<div class="stage todo" id="st${i}"><span class="dot"></span><span class="lbl">${s}</span></div>`).join("");
  renderScanSkeleton();
  setStage(0, "run"); setBar(4);
  const pollRef = { stop: false };
  const pollTask = pollScanProgress(pollRef);

  const scan = await api("/api/repositories/scan", "POST", { path, scope: readScopeConfig() });
  pollRef.stop = true;
  await pollTask;
  const finalStatus = await api("/api/repositories/current/scan-status");
  applyScanStatus(finalStatus);
  STAGES.forEach((_, i) => setStage(i, "done")); setBar(100); $("scanPct").textContent = "100%";
  if (!scan.ok) {
    const code = scan.code || (scan.degraded ? "partial_graph" : "");
    showScanFailed(scan.error || "Scan failed", code);
    toast("✗ Scan failed", "error");
    return;
  }
  updateMassiveBadge(!!scan.massive_mode);
  if (scan.full_graph_pending) {
    $("scanModeInfo").style.display = "block";
    $("scanModeInfo").textContent = "Import-level graph ready (~" + (scan.module_count || 0) + " modules). Open Repository Map for the full module graph.";
  } else if (scan.massive_mode) {
    $("scanModeInfo").style.display = "block";
    $("scanModeInfo").textContent = "Massive Repository Mode enabled. Starting with architecture overview is recommended.";
  } else if (scan.degraded) {
    $("scanModeInfo").style.display = "block";
    $("scanModeInfo").textContent = "Some dependencies could not be linked. Plans still work; results may cover fewer files.";
  } else if (!scan.module_count && (scan.code_files || scan.file_count || 0) > 0) {
    $("scanModeInfo").style.display = "block";
    $("scanModeInfo").textContent = "This repository uses languages not yet supported for dependency extraction.";
  } else {
    $("scanModeInfo").style.display = "none";
  }
  const metrics = $("scanMetrics");
  if (metrics) metrics.innerHTML = metricGrid(scan);
  STATE.summary = await api("/api/repositories/current/summary");
  STATE.sessionExport = await api("/api/repositories/current/session-export");
  STATE.exportMode = "MINIMAL_EXPORT";
  finishScanSession(scan, sel.path);
  toast("Scan complete ✓", "success");
  if ((scan.module_count || 0) < GRAPH_HIERARCHY_THRESHOLD) {
    toast(`Opening Module Graph (${(scan.module_count || 0).toLocaleString()} modules)`, "success");
  }
}
function setStage(i, cls) { const el = $("st" + i); if (el) el.className = "stage " + cls; }
function setBar(pct) {
  const value = Math.max(0, Math.min(100, Math.round(pct)));
  $("scanBar").style.width = value + "%";
  $("scanPct").textContent = value + "%";
  $("scanProgress")?.setAttribute("aria-valuenow", String(value));
}
async function cancelCurrentScan() {
  const res = await api("/api/repositories/current/cancel-scan", "POST", {});
  if (res.ok) toast("Cancel requested", "success");
}
function metricGrid(s) {
  const lb = s.language_breakdown || {};
  const M = [
    ["files discovered", s.files_discovered], ["modules indexed", s.module_count],
    ["typescript modules", lb.typescript_modules], ["javascript modules", lb.javascript_modules],
    ["python modules", lb.python_modules], ["external package imports", lb.external_package_imports],
    ["subsystems", s.subsystem_count], ["dependency edges", s.dependency_edges],
    ["resolved imports", s.resolved_imports], ["unresolved imports", s.unresolved_imports],
    ["unresolved ratio", s.unresolved_ratio == null ? null : `${(s.unresolved_ratio * 100).toFixed(1)}%`],
    ["import cycles", s.import_cycle_count],
    ["graph scope", s.graph_scope || "—"], ["compact tokens", s.compact_token_estimate],
  ];
  return M.map(([l, v]) => `<div class="metric"><div class="mv">${v === undefined || v === null ? "—" : v}</div><div class="ml">${l}</div></div>`).join("");
}

/* ---------------- Command Center ---------------- */
async function fetchGraphPayload() {
  const view = STATE.graphView || "module";
  if (view === "hierarchy") {
    const h = STATE.hierarchy || { level: "subsystem", subsystem: "", package: "" };
    if (h.level === "package") {
      return api(`/api/repositories/current/hierarchy-graph?level=package&parent=${encodeURIComponent(h.subsystem || "")}`, "GET", undefined, { requireOk: true });
    }
    if (h.level === "module") {
      return api(`/api/repositories/current/hierarchy-graph?level=module&parent=${encodeURIComponent(h.package || h.subsystem || "")}`, "GET", undefined, { requireOk: true });
    }
    return api("/api/repositories/current/hierarchy-graph?level=subsystem", "GET", undefined, { requireOk: true });
  }
  return api(`/api/repositories/current/graph?view=${encodeURIComponent(view)}`, "GET", undefined, { requireOk: true });
}

function setGraphView(view, options = {}) {
  STATE.graphView = view;
  if (!options.silent) STATE._pendingGraphViewToast = view;
  if (!options.preserveUserPick) STATE._graphViewUserPicked = true;
  if (view === "hierarchy") {
    STATE.hierarchy = { level: "subsystem", subsystem: "", package: "", module: "" };
  }
  STATE.graph = null;
  STATE.graph3d = null;
  STATE.graphPerf = null;
  document.querySelectorAll('input[name="graphView"]').forEach(el => {
    el.checked = el.value === view;
  });
  renderCenter();
}

function renderHierarchyBreadcrumb() {
  const host = $("hierarchyBreadcrumb");
  if (!host) return;
  const h = STATE.hierarchy || { level: "subsystem", subsystem: "", package: "", module: "" };
  const crumbs = [
    `<span class="crumb-link" onclick="navigateHierarchy('subsystem')">Repository</span>`,
  ];
  if (h.subsystem) crumbs.push(`<span>/</span><span class="crumb-link" onclick="navigateHierarchy('package', ${JSON.stringify(h.subsystem)})">${h.subsystem}</span>`);
  if (h.package) crumbs.push(`<span>/</span><span class="crumb-link" onclick="navigateHierarchy('module', ${JSON.stringify(h.package)})">${h.package}</span>`);
  if (h.module) crumbs.push(`<span>/</span><span>${h.module}</span>`);
  host.innerHTML = crumbs.join("");
}

function updateHierarchyCounts(graph) {
  const c = graph?.counts || {};
  $("hierarchyCounts").textContent = graph?.level
    ? `${graph.level}: files ${c.files ?? 0} · modules ${c.modules ?? 0} · edges ${c.edges ?? 0} · hotspots ${c.risk_hotspots ?? 0}`
    : "";
}

function navigateHierarchy(level, parent = "") {
  if (level === "subsystem") {
    STATE.hierarchy = { level: "subsystem", subsystem: "", package: "", module: "" };
  } else if (level === "package") {
    STATE.hierarchy = { level: "package", subsystem: parent || "", package: "", module: "" };
  } else if (level === "module") {
    const parentText = String(parent || "");
    STATE.hierarchy = { level: "module", subsystem: STATE.hierarchy.subsystem || "", package: parentText, module: "" };
  }
  STATE._pendingGraphViewToast = "hierarchy";
  STATE.graph = null;
  renderCenter();
}

function backToOverview() {
  const modules = STATE.summary?.module_count ?? STATE.graph?.total_modules ?? 0;
  setGraphView(resolveDefaultGraphView(modules));
}

function updateGraphMeta(data, perf) {
  const sum = STATE.summary || {};
  const perfText = perf && perf.loadMs != null ? ` · loaded ${perf.loadMs}ms` : "";
  const cacheText = (STATE.summary?.cache?.hit || STATE.graph?.cache?.hit) ? " · cache hit" : "";
  const scopeText = sum.graph_scope || data.graph_scope || "";
  $("graphMeta").textContent = [scopeText, cacheText, perfText].filter(Boolean).join(" · ");
}

async function renderCenter() {
  let sum = STATE.summary;
  if (!sum) {
    try {
      sum = STATE.summary = await api("/api/repositories/current/summary");
    } catch (error) {
      $("leftPanel").innerHTML = repoRequiredEmptyHtml("Repository endpoint unavailable. Retry when the local runtime responds.");
      $("graph3d").innerHTML = repoRequiredEmptyHtml(error?.kind === "timeout" ? "Graph request timed out." : "Repository graph is temporarily unavailable.");
      $("suggest").innerHTML = "";
      $("moduleInspector").innerHTML = `<h3>Module Inspector</h3><p class="muted tiny">Repository endpoint unavailable.</p>`;
      window.atlasTransport?.setState("repository", error?.kind === "timeout" ? "timed_out" : "unavailable", { kind: error?.kind || "network_error" });
      return;
    }
  }
  if (!sum.ok) {
    $("leftPanel").innerHTML = repoRequiredEmptyHtml("Scan a folder or load the sample to explore architecture, dependencies, and risk hubs.");
    $("graph3d").innerHTML = repoRequiredEmptyHtml("Complete a scan to render the dependency map.");
    $("suggest").innerHTML = "";
    $("moduleInspector").innerHTML = `<h3>Module Inspector</h3><p class="muted tiny">Scan a repository first.</p>`;
    ATLAS_UNIVERSE.renderTimeline($("timelinePanel"), null);
    return;
  }
  renderHealthCockpit(sum);
  renderMapHeader(sum);
  $("suggest").innerHTML = renderCopilotSuggestions(sum);
  let graph = STATE.graph;
  if (!graph) {
    try {
      graph = STATE.graph = await fetchGraphPayload();
    } catch (error) {
      $("graph3d").innerHTML = repoRequiredEmptyHtml(error?.kind === "timeout" ? "Graph request timed out. Retry Graph." : "Graph endpoint unavailable. Retry Graph.");
      $("moduleInspector").innerHTML = `<h3>Module Inspector</h3><p class="muted tiny">Graph data is temporarily unavailable.</p>`;
      window.atlasTransport?.setState("graph", error?.kind === "timeout" ? "timed_out" : "unavailable", { kind: error?.kind || "network_error" });
      return;
    }
  }
  const bc = $("mapBreadcrumb");
  if (STATE.graphView === "hierarchy") {
    if (bc) bc.style.display = "flex";
    renderHierarchyBreadcrumb();
    updateHierarchyCounts(graph);
  } else {
    if (bc) bc.style.display = "none";
    $("hierarchyBreadcrumb").textContent = "Repository";
    $("hierarchyCounts").textContent = "";
  }
  setMapWarning(graph, sum);
  STATE.tourStops = graph.tour_stops || [];
  STATE.riskPercentiles = computeRiskPercentiles(graph.nodes || []);
  renderGraphModeMetrics(sum, graph);
  updateGraphMeta(graph, STATE.graphPerf);
  if (STATE._pendingGraphViewToast) {
    const totals = graphUnderlyingTotals(sum, graph);
    toast(graphViewToastMessage(STATE._pendingGraphViewToast, graph, totals), "success");
    STATE._pendingGraphViewToast = null;
  }
  const timeline = await api("/api/repositories/current/timeline");
  ATLAS_UNIVERSE.renderTimeline($("timelinePanel"), timeline);
  renderModuleInspectorPlaceholder();
  renderArchitectureSummary(sum);
  renderModuleBrowsePanel(graph, sum);
  build3DGraph(graph);
}

function renderMapHeader(sum) {
  const nameEl = $("mapRepoName");
  if (nameEl) nameEl.textContent = sum.repo_name ? `· ${sum.repo_name}` : "";
  const badge = $("mapHealthBadge");
  if (badge) {
    const raw = sum.graph_health?.label || "—";
    const label = typeof atlasFriendlyGraphHealth === "function" ? atlasFriendlyGraphHealth(raw) : raw;
    badge.textContent = label;
    badge.className = `map-health-badge ${raw}`;
  }
}

// Concise warning + "Details" link (full explanation in a toast, not a wall of text).
function setMapWarning(graph, sum) {
  const el = $("graphWarning");
  if (!el) return;
  const partial = (sum.graph_health?.label || "") !== "healthy";
  const full = [graph.render_warning, partial ? sum.graph_health?.notice : ""].filter(Boolean).join(" ");
  if (!full) { el.style.display = "none"; el.textContent = ""; return; }
  const concise = partial
    ? "Some file links could not be resolved. Most missing links are external or dynamic imports."
    : "Some dependencies could not be resolved.";
  el.style.display = "flex";
  el.innerHTML = `<span>${concise}</span><span class="map-warning-details" role="button" tabindex="0" onclick="toast(${JSON.stringify(full)})">Details</span>`;
}

function renderArchitectureSummary(sum) {
  const host = $("architectureSummary");
  if (!host || !sum?.ok) return;
  const subsystems = (sum.subsystems || []).slice(0, 8);
  const arch = sum.architecture || {};
  const u = arch.unresolved_breakdown || {};
  const buckets = u.buckets || sum.unresolved_breakdown || {};
  const internal = u.internal_unresolved ?? 0;
  const boundaries = (sum.top_boundaries || arch.top_boundaries || []).slice(0, 4);
  const areas = sum.architecture_summary?.areas || arch.architecture_summary?.areas || {};
  const areaTags = ["components", "helpers", "core", "auth", "config_entries"]
    .filter(k => (areas[k] || 0) > 0)
    .map(k => `<span class="tag">${esc(k)}</span>`).join("");
  host.innerHTML = `
    <h3 style="margin-top:16px">Architecture</h3>
    <p class="muted tiny" style="margin:4px 0 8px">${esc((sum.explanation || "").slice(0, 280))}${(sum.explanation || "").length > 280 ? "…" : ""}</p>
    <div class="taglist">${subsystems.map(s => `<span class="tag" title="${esc((s.dependencies || []).join(", "))}">${esc(s.name)} · ${s.production_files || 0}</span>`).join("") || '<span class="muted tiny">—</span>'}</div>
    ${areaTags ? `<div class="taglist" style="margin-top:6px">${areaTags}</div>` : ""}
    ${boundaries.length ? `<p class="muted tiny" style="margin-top:6px">Boundaries: ${boundaries.map(b => esc((b.module || b.path || "").split("/").pop())).join(", ")}</p>` : ""}
    ${internal ? `<p class="muted tiny">Imports Atlas could not link: <b>${internal}</b></p>` : ""}
    ${Object.keys(buckets).length ? `<p class="muted tiny">Unresolved: ${Object.entries(buckets).filter(([,v]) => v).slice(0,5).map(([k,v]) => `${k} ${v}`).join(" · ")}</p>` : ""}
    <p class="muted tiny" style="margin-top:8px">Entry: ${esc((sum.entry_points || []).slice(0, 3).join(", ") || "none detected")}</p>`;
}

function renderModuleBrowsePanel(graph, sum) {
  const panel = $("moduleBrowsePanel");
  const list = $("moduleBrowseList");
  if (!panel || !list) return;
  const view = STATE.graphView || "module";
  const nodes = (graph?.nodes || []).filter(n => n.path || n.name || n.id);
  const showList = nodes.length > 0;
  panel.style.display = showList ? "block" : "none";
  if (!showList) return;
  if (!panel.dataset.initialized) {
    panel.dataset.initialized = "1";
    panel.classList.add("is-collapsed");
  }
  const totals = graphUnderlyingTotals(sum, graph);
  const summary = $("moduleBrowseSummary");
  if (summary) summary.textContent = `${graphModeTitle(view, graph)} list · ${nodes.length.toLocaleString()} visible of ${totals.modules.toLocaleString()} modules`;
  const ranked = [...nodes].sort((a, b) => (b.fan_in || 0) - (a.fan_in || 0) || (b.risk_score || 0) - (a.risk_score || 0));
  STATE.moduleBrowseNodes = ranked;
  filterModuleBrowseList();
}

function toggleModuleBrowsePanel() {
  const panel = $("moduleBrowsePanel");
  const button = $("moduleBrowseToggle");
  if (!panel || !button) return;
  const expanded = panel.classList.toggle("is-collapsed") === false;
  button.setAttribute("aria-expanded", String(expanded));
  button.textContent = expanded ? "Hide module list" : "Show module list";
  if (expanded) setTimeout(() => $("moduleBrowseFilter")?.focus(), 30);
}

function filterModuleBrowseList() {
  const list = $("moduleBrowseList");
  if (!list || !STATE.moduleBrowseNodes) return;
  const q = ($("moduleBrowseFilter")?.value || "").trim().toLowerCase();
  const items = STATE.moduleBrowseNodes.filter(n => !q || `${n.path || ""} ${n.name || ""}`.toLowerCase().includes(q)).slice(0, 100);
  list.innerHTML = items.map(n => {
    const path = n.path || n.name || n.id || "";
    const fi = n.fan_in || 0, fo = n.fan_out || 0;
    const risk = n.risk_score || 0;
    const sub = n.subsystem || "";
    const rc = risk >= 60 ? "var(--red)" : risk >= 35 ? "var(--amber)" : risk >= 15 ? "var(--cyan)" : "var(--green)";
    return `<li><button type="button" class="mbp-item" aria-label="Inspect ${esc(path)}" onclick="selectModuleFromList(${JSON.stringify(path)})">
      <span class="mbp-path">${esc(path)}</span>
      <span class="mbp-meta"><b style="color:${rc}">risk ${risk}</b> · ${fi} dependents · ${fo} imports</span>
    </button></li>`;
  }).join("") || '<li class="muted tiny">No modules match filter</li>';
}

function selectModuleFromList(path) {
  if (!path || !STATE.graph) return;
  const node = (STATE.graph.nodes || []).find(n => (n.path || n.name || n.id) === path);
  if (node) showNode(node);
}

function formatMs(ms) {
  if (ms == null || ms === "") return "—";
  const n = Number(ms);
  if (!isFinite(n)) return "—";
  if (n < 1000) return n + " ms";
  return (n / 1000).toFixed(1) + " s";
}

function renderPerformancePanel(health) {
  const host = $("perfPanel");
  if (!host) return;
  if (!health || !health.ok) {
    host.innerHTML = `<p class="muted tiny">Performance timings appear after your first scan and workflow run.</p>`;
    return;
  }
  const scanPerf = health.scan_performance || {};
  const events = scanPerf.events || [];
  const byStage = {};
  events.forEach(ev => { byStage[ev.stage] = ev.duration_ms; });
  const wf = health.workflow_performance || {};
  host.innerHTML = `
    <div class="perf-grid">
      <div class="perf-row"><span>Total scan</span><b>${formatMs(scanPerf.total_duration_ms)}</b></div>
      <div class="perf-row"><span>Graph build</span><b>${formatMs(byStage.building_graph || byStage.building_dependency_graph)}</b></div>
      <div class="perf-row"><span>Evidence index</span><b>${formatMs(byStage.building_evidence_index)}</b></div>
      <div class="perf-row"><span>Plan Change</span><b>${formatMs((wf.build_plan || {}).duration_ms)}</b></div>
      <div class="perf-row"><span>Debug</span><b>${formatMs((wf.investigation || {}).duration_ms)}</b></div>
      <div class="perf-row"><span>What breaks?</span><b>${formatMs((wf.impact || {}).duration_ms)}</b></div>
    </div>`;
}

async function renderSystemHealth(sum) {
  updateTelemetryWarning(sum);
  const sav = sum.token_savings || {};
  const gh = sum.graph_health || {};
  const ev = sum.evidence_coverage || {};
  const showTokenSavings = sav.show_in_cockpit === true && sav.verified === true;
  const ratioNote = gh.unresolved_ratio_note || "";
  const graphNotice = gh.notice
    ? `<div class="cockpit-card wide"><div class="cc-label">Graph note</div><div class="cc-val" style="font-size:13px;color:var(--amber)">${esc(gh.notice)}</div></div>`
    : "";
  const telMsg = typeof atlasFriendlyTelemetry === "function"
    ? atlasFriendlyTelemetry(sum.telemetry_warning || TELEMETRY_WARNING_TEXT)
    : (sum.telemetry_warning || TELEMETRY_WARNING_TEXT);
  const tel = sum.analytics_status === "degraded"
    ? `<div class="cockpit-card wide"><div class="cc-label">Usage stats</div><div class="cc-val" style="font-size:13px;color:var(--amber)">${esc(telMsg)}</div></div>`
    : "";
  const tokenCard = showTokenSavings
    ? `<div class="cockpit-card"><div class="cc-label">Token savings (verified)</div><div class="cc-val" id="ccSavings">${sav.reduction_percent || 0}%</div></div>`
    : "";
  const healthColor = gh.label === "healthy" ? "var(--green)" : "var(--amber)";
  $("leftPanel").innerHTML = `
    <h3>System Health</h3>
    <p class="muted tiny" style="margin:0 0 10px">Local scan quality for <b>${esc(sum.repo_name || "repository")}</b></p>
    ${tel}
    ${graphNotice}
    <div class="cockpit-grid">
      <div class="cockpit-card"><div class="cc-label">Indexed files</div><div class="cc-val">${(sum.file_count || 0).toLocaleString()}</div></div>
      <div class="cockpit-card"><div class="cc-label">Modules</div><div class="cc-val" id="ccModules">${(sum.module_count || 0).toLocaleString()}</div></div>
      <div class="cockpit-card"><div class="cc-label">Module links</div><div class="cc-val">${(sum.dependency_edges || 0).toLocaleString()}</div></div>
      <div class="cockpit-card warn"><div class="cc-label">Unlinked imports</div><div class="cc-val">${gh.unresolved_internal ?? gh.unresolved_imports ?? 0}</div></div>
      <div class="cockpit-card"><div class="cc-label">Scan duration</div><div class="cc-val" style="font-size:16px">${sum.scan_duration_seconds != null ? sum.scan_duration_seconds + "s" : "—"}</div></div>
      <div class="cockpit-card"><div class="cc-label">Scan quality</div><div class="cc-val" id="ccHealth" style="font-size:16px;color:${healthColor}">${typeof atlasFriendlyGraphHealth === "function" ? atlasFriendlyGraphHealth(gh.label) : (gh.label || "—")}</div></div>
    </div>
    <div class="cockpit-grid">
      <div class="cockpit-card"><div class="cc-label">Symbols indexed</div><div class="cc-val">${(ev.symbol_count || 0).toLocaleString()}</div></div>
      <div class="cockpit-card"><div class="cc-label">Files w/ symbols</div><div class="cc-val">${ev.files_with_symbols || 0}</div></div>
      <div class="cockpit-card risk"><div class="cc-label">Risk score</div><div class="cc-val" id="ccRisk">${sum.risk_score}</div></div>
      <div class="cockpit-card warn"><div class="cc-label">Import cycles</div><div class="cc-val" id="ccCycles">${gh.import_cycles ?? 0}</div></div>
      ${tokenCard}
    </div>
    <p class="muted tiny" style="margin:4px 0 10px">${esc(gh.notice || ratioNote)}</p>
    <h3 style="margin-top:12px">Performance</h3>
    <div id="perfPanel"><p class="muted tiny">Loading timings…</p></div>
    <div id="architectureSummary"></div>
    <h3 style="margin-top:14px">Riskiest to change</h3>
    <ul class="clean cockpit-hubs">${(sum.top_risks || []).slice(0, 5).map(r => `<li><b style="color:${riskColor(r.score)}">${(r.module || r.path || "").split(/[./\\]/).pop()}</b> <span class="muted">${r.score ?? ""}</span></li>`).join("") || '<li class="muted tiny">Scan more modules to populate risk ranking.</li>'}</ul>
    <h3 style="margin-top:14px">Most depended-on</h3>
    <ul class="clean cockpit-hubs">${(sum.top_hubs || []).slice(0, 5).map(h => `<li>${(h.module || h.path || "").split(/[./\\]/).pop()} <span class="muted">← ${h.fan_in}</span></li>`).join("") || '<li class="muted tiny">No hub data yet.</li>'}</ul>`;
  ATLAS_UNIVERSE.animateCounter($("ccRisk"), sum.risk_score, 800);
  ATLAS_UNIVERSE.animateCounter($("ccModules"), sum.module_count, 900);
  ATLAS_UNIVERSE.animateCounter($("ccCycles"), gh.import_cycles ?? 0, 700);
  if (showTokenSavings && $("ccSavings")) ATLAS_UNIVERSE.animateCounter($("ccSavings"), sav.reduction_percent || 0, 900);
  renderArchitectureSummary(sum);
  const health = await api("/api/repositories/current/system-health");
  renderPerformancePanel(health);
  const diagBtn = $("copyDiagnosticsBtn");
  if (diagBtn) diagBtn.style.display = "inline-block";
}

function renderHealthCockpit(sum) {
  renderSystemHealth(sum);
}
function riskColor(s) { return s >= 60 ? "var(--red)" : s >= 35 ? "var(--amber)" : s >= 15 ? "var(--cyan)" : "var(--green)"; }

function computeRiskPercentiles(nodes) {
  const ranked = [...nodes].sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0));
  const count = ranked.length || 1;
  const top1 = Math.max(1, Math.ceil(count * 0.01));
  const top5 = Math.max(1, Math.ceil(count * 0.05));
  return {
    top1: new Set(ranked.slice(0, top1).map(n => n.id)),
    top5: new Set(ranked.slice(0, top5).map(n => n.id)),
  };
}

async function ensureRepoSummary() {
  if (STATE.summary?.ok) return STATE.summary;
  let sum;
  try {
    sum = await api("/api/repositories/current/summary");
  } catch (error) {
    window.atlasTransport?.setState("repository", error?.kind === "timeout" ? "timed_out" : "unavailable", { kind: error?.kind || "network_error" });
    return { ok: false, transport_error: true, error: error?.message || "Repository endpoint unavailable" };
  }
  if (sum?.ok) {
    STATE.summary = sum;
    document.body.classList.remove("atlas-no-repo");
    unlockNav();
    updateRepoChip(sum.repo_name, sum.demo_mode);
    updateWorkflowToolbars();
    try {
      if (window.AtlasRepositoryState) window.AtlasRepositoryState.publish({ summary: sum });
      document.dispatchEvent(new CustomEvent("atlas:repository-state-changed"));
    } catch (_error) {}
  } else {
    document.body.classList.add("atlas-no-repo");
  }
  return sum;
}

async function renderAskPage() {
  const gate = $("askEmptyState");
  const panel = $("askPanel");
  const sum = await ensureRepoSummary();
  if (!sum?.ok) {
    if (panel) panel.style.display = "none";
    if (gate) {
      gate.style.display = "block";
      gate.innerHTML = repoRequiredEmptyHtml(
        "Atlas needs a local code map before it can resolve repository evidence."
      );
    }
    return;
  }
  if (gate) { gate.style.display = "none"; gate.innerHTML = ""; }
  if (panel) panel.style.display = "block";
  const status = $("askStatus");
  if (status) status.textContent = `${sum.repo_name || "Repository"} ready for questions.`;
  const askRoot = $("view-ask");
  const live = askRoot && askRoot.querySelector ? askRoot.querySelector(".ask-live-state") : null;
  if (live) live.innerHTML = `<i></i>${escapeHtml(sum.repo_name || "Repository active")}`;
  if ($("suggest")) $("suggest").innerHTML = renderCopilotSuggestions(sum);
}

function launchCopilotQuestions() {
  return [
    "Where is authentication implemented?",
    "What breaks if I change services/auth.py?",
    "Explain the request flow.",
    "Which files should I read first?",
    "What does this repository do?",
  ];
}

function defaultCopilotQuestions(summary) {
  const qs = launchCopilotQuestions();
  const topHub = summary?.top_hubs?.[0]?.path;
  if (topHub) {
    const q = `What breaks if I change ${topHub}?`;
    if (!qs.includes(q)) qs.splice(1, 0, q);
  }
  return qs.slice(0, 6);
}

function escAttr(s) {
  return String(s || "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
}

function ensureSuggestDelegation() {
  if (_suggestDelegated) return;
  const host = $("suggest");
  if (!host) return;
  host.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-prompt]");
    if (!btn) return;
    const q = btn.getAttribute("data-prompt");
    if (q) askQuestion(q);
  });
  _suggestDelegated = true;
}

function renderCopilotSuggestions(summary) {
  ensureSuggestDelegation();
  const qs = STATE.selectedNode ? nodeCopilotQuestions(STATE.selectedNode) : defaultCopilotQuestions(summary);
  return qs.map((q) => `<button type="button" class="sg" data-prompt="${escAttr(q)}">${esc(q)}</button>`).join("");
}

async function askQuestion(q) {
  const field = $("askInput");
  if (field) field.value = q;
  await sendCopilotQuestion();
}

async function sendCopilotQuestion() {
  const question = ($("askInput").value || "").trim();
  if (!question) { toast("Enter an investigation brief"); return; }
  STATE.copilotQuestion = question;
  const sum = await ensureRepoSummary();
  if (!sum?.ok) {
    renderAskPage();
    toast("Scan a repository first", "error");
    return;
  }
  $("copilotLoading").style.display = "block";
  $("copilotCard").style.display = "none";
  window.atlasActivity?.add("Repository analysis started");
  const body = { question, target: "none", packet: "compact" };
  if (STATE.selectedNode) body.node_context = STATE.selectedNode;
  const res = await api("/api/copilot/ask", "POST", body);
  $("copilotLoading").style.display = "none";
  if (!res.ok) {
    if (res.code === "no_repository" || res.code === "requires_scan") renderAskPage();
    toast("✗ " + (res.error || "Repository analysis failed"));
    return;
  }
  STATE.copilotResult = res;
  renderCopilotAnswer(res);
}

const _ANALYSIS_MODES = new Set(["comparison", "general_analysis", "repository_understanding", "location", "risk"]);

function _copilotModeLabel(mode) {
  return ({
    comparison: "Comparison",
    general_analysis: "Analysis",
    repository_understanding: "Overview",
    location: "Where is it",
    impact: "Impact",
    dependency: "Dependencies",
    cycles: "Import cycles",
    context_export: "Context packet",
    risk: "Risk",
    unknown: "No grounded match",
  })[mode] || (mode || "unknown");
}

function renderCopilotAnswer(res) {
  $("copilotCard").style.display = "block";
  $("copilotMode").textContent = _copilotModeLabel(res.mode);
  const showRisk = res.mode === "impact" || (res.risk_level && res.risk_level !== "low" && res.risk_level !== "unknown");
  $("copilotRisk").style.display = showRisk ? "" : "none";
  $("copilotRisk").textContent = `${res.risk_level || "unknown"} risk`;
  $("copilotRisk").className = `lvl ${res.risk_level || "unknown"}`;

  const hasReport = res.report && typeof renderStructuredReportHtml === "function";
  if (hasReport) {
    const title = res.mode === "comparison" ? "Comparison"
      : res.mode === "repository_understanding" ? "Repository overview" : "Analysis";
    // The structured report is the primary document; the one-line answer is folded
    // into it as the executive summary, so we don't repeat it above.
    $("copilotAnswer").innerHTML = renderStructuredReportHtml(res.report, title);
  } else {
    $("copilotAnswer").textContent = res.answer || "";
  }

  // Impact analysis gets a dedicated result hierarchy (risk -> direct -> indirect
  // -> tests -> unknown -> evidence) instead of a flat chip list.
  const impSum = $("copilotImpactSummary");
  const impHier = $("copilotImpactHierarchy");
  if (impSum) {
    if (res.mode === "impact" && (res.semantic_label || res.architectural_blast_radius != null)) {
      // Risk-summary visuals: semantic target + blast-radius metrics.
      impSum.style.display = "block";
      impSum.innerHTML = impactSemanticCard(res) + impactBlastCard(res);
    } else {
      impSum.style.display = "none";
      impSum.innerHTML = "";
    }
  }
  if (impHier) {
    if (res.mode === "impact") {
      impHier.style.display = "block";
      impHier.innerHTML = renderImpactHierarchy(res);
    } else {
      impHier.style.display = "none";
      impHier.innerHTML = "";
    }
  }

  // Flat evidence + file-chip lists are redundant once a structured report or the
  // impact hierarchy is shown; keep them hidden behind "Inspect evidence".
  const detailed = hasReport || res.mode === "impact";
  const evidence = res.evidence || [];
  $("copilotEvidence").innerHTML = evidence.map(item => `<li>${esc(item)}</li>`).join("");
  $("copilotEvidenceWrap").style.display = (!detailed && evidence.length) ? "block" : "none";
  const files = res.files || [];
  $("copilotFiles").innerHTML = files.map(f => `<span class="tag">${esc(f)}</span>`).join("");
  $("copilotFilesWrap").style.display = (!detailed && files.length) ? "block" : "none";
  $("copilotActionWrap").style.display = (!detailed && res.suggested_action) ? "block" : "none";
  $("copilotAction").textContent = res.suggested_action || "";

  renderCopilotPrimaryActions(res);

  const limits = (res.limitations || []).filter(Boolean);
  const grounded = (res.files || []).length > 0;
  if (!grounded && res.mode === "unknown") {
    $("copilotOut").innerHTML = `<span class="muted">${esc(res.answer || "No grounded match.")}</span>
      <div class="suggest" style="margin-top:8px">
        <div class="sg" onclick="askQuestion('What are the top architectural risks?')">Ask about top risks</div>
        <div class="sg" onclick="askQuestion('Explain the main subsystems')">Explain a subsystem</div>
        <div class="sg" onclick="askQuestion('Which files should I read first?')">Where to start</div>
      </div>`;
  } else {
    $("copilotOut").innerHTML = limits.length
      ? `<span class="muted">Confidence: ${esc(res.confidence || "medium")} · Verify claims in the cited files.</span>`
      : `<span class="muted">Confidence: ${esc(res.confidence || "medium")}</span>`;
  }
  if (res.graph_highlight && window.ATLAS_UNIVERSE) ATLAS_UNIVERSE.highlightBlastRadius(res.graph_highlight);
}

// Primary investigation actions (Refine analysis, Inspect evidence, Run Impact, Show
// in Map, Create change plan). Copy/export live under "More actions".
function renderCopilotPrimaryActions(res) {
  const host = $("copilotPrimaryActions");
  if (!host) return;
  const topFile = (res.files || [])[0] || "";
  const btns = [];
  btns.push(`<button class="btn small" onclick="copilotFollowUp()">Refine analysis</button>`);
  if ((res.evidence || []).length || (res.files || []).length) {
    btns.push(`<button class="btn small ghost" onclick="copilotInspectEvidence()">Inspect evidence</button>`);
  }
  if (topFile && res.mode !== "impact") {
    btns.push(`<button class="btn small ghost" onclick="copilotRunImpact()">Run Impact</button>`);
  }
  if ((res.files || []).length) {
    btns.push(`<button class="btn small ghost" onclick="copilotShowInMap()">Show in Map</button>`);
  }
  // Create change plan is the primary call-to-action for impact results.
  const planClass = res.mode === "impact" ? "btn small primary" : "btn small ghost";
  btns.push(`<button class="${planClass}" onclick="copilotCreatePlan()">Create change plan</button>`);
  host.innerHTML = btns.join("");
}

function copilotFollowUp() {
  const field = $("askInput");
  if (field) { field.value = ""; field.focus(); }
}
function copilotInspectEvidence() {
  const ev = $("copilotEvidenceWrap"), fl = $("copilotFilesWrap");
  const show = ev && ev.style.display === "none";
  if (ev && (STATE.copilotResult?.evidence || []).length) ev.style.display = show ? "block" : "none";
  if (fl && (STATE.copilotResult?.files || []).length) fl.style.display = show ? "block" : "none";
}
function copilotRunImpact() {
  const topFile = (STATE.copilotResult?.files || [])[0];
  if (!topFile) { toast("No file to analyze"); return; }
  askQuestion(`What breaks if I change ${topFile}?`);
}
function copilotShowInMap() {
  go("center");
  const gh = STATE.copilotResult?.graph_highlight;
  if (gh && window.ATLAS_UNIVERSE) setTimeout(() => ATLAS_UNIVERSE.highlightBlastRadius(gh), 200);
}
function copilotCreatePlan() {
  const q = STATE.copilotQuestion || STATE.copilotResult?.answer || "";
  const topFile = (STATE.copilotResult?.files || [])[0] || "";
  const field = $("buildRequest");
  if (field) field.value = topFile ? `Plan a change related to ${topFile}: ${q}` : q;
  go("build");
  setTimeout(() => $("buildRequest")?.focus(), 60);
}

function copyCopilotAnswer() {
  if (!STATE.copilotResult?.answer) { toast("Nothing to copy"); return; }
  copyText(STATE.copilotResult.answer, "Analysis report copied");
}
function copyCopilotTarget(target) {
  const text = STATE.copilotResult?.copy_targets?.[target] || STATE.copilotResult?.suggested_prompt;
  if (!text) { toast("Nothing to copy"); return; }
  copyText(text, `${target} handoff copied`);
}

function toggleGraphEdges() {
  STATE.showEdges = $("showEdges").checked;
  ATLAS_UNIVERSE.setShowEdges(STATE.showEdges);
  ATLAS_UNIVERSE.refreshHighlight(STATE.hoverNodeId ? { id: STATE.hoverNodeId } : STATE.selectedNode);
}

function build3DGraph(data) {
  ATLAS_UNIVERSE.destroyGraph?.();
  STATE.graph3d = ATLAS_UNIVERSE.buildGraph($("graph3d"), data, {
    onNodeClick: n => {
      if (STATE.graphView === "hierarchy") {
        handleHierarchyClick(n);
        return;
      }
      if (STATE.graphView === "subsystem" && (n.expandable || STATE.graph?.architecture_clusters)) {
        STATE.graphView = "hierarchy";
        STATE._graphViewUserPicked = true;
        STATE.hierarchy = {
          level: "package",
          subsystem: n.label || n.subsystem || "",
          package: "",
          module: "",
        };
        STATE.graph = null;
        document.querySelectorAll('input[name="graphView"]').forEach(el => {
          el.checked = el.value === "hierarchy";
        });
        renderCenter();
        return;
      }
      showNode(n);
    },
    onNodeHover: n => { STATE.hoverNodeId = n ? n.id : null; }, // lightweight; inspector on click only
    onBackgroundClick: () => {
      STATE.selectedNode = null;
      $("selectedNodeCard").style.display = "none";
      if ($("inspectorQuick")) $("inspectorQuick").style.display = "none";
      renderModuleInspectorPlaceholder();
      if (STATE.summary) $("suggest").innerHTML = renderCopilotSuggestions(STATE.summary);
    },
    getSelectedNode: () => STATE.selectedNode,
    onLoaded: perf => {
      STATE.graphPerf = perf;
      updateGraphMeta(data, perf);
      renderGraphRenderDiagnostics(perf);
    },
  });
}

function handleHierarchyClick(n) {
  if (!n) return;
  const level = STATE.hierarchy.level || "subsystem";
  if (level === "subsystem") {
    STATE.hierarchy = { level: "package", subsystem: n.subsystem || n.label || "", package: "", module: "" };
    STATE.graph = null;
    renderCenter();
    return;
  }
  if (level === "package") {
    const pkg = String(n.label || "").replace(/^package:/, "");
    STATE.hierarchy = { level: "module", subsystem: n.subsystem || STATE.hierarchy.subsystem || "", package: pkg, module: "" };
    STATE.graph = null;
    renderCenter();
    return;
  }
  if (level === "module") {
    STATE.hierarchy.module = n.path || n.label || "";
    showNode(n);
  }
}

async function renderModuleInspector(node) {
  const wrap = $("moduleInspector");
  if (!node?.path && !node?.id) {
    renderModuleInspectorPlaceholder();
    return;
  }
  wrap.innerHTML = `<h3>Module Inspector</h3><div class="muted tiny">Loading ${node.path || node.label}…</div>`;
  const target = node.path || node.id;
  const info = await api(`/api/repositories/current/module?target=${encodeURIComponent(target)}`);
  if (!info.ok) {
    wrap.innerHTML = `<h3>Module Inspector</h3><p class="muted tiny">${info.error || "Unavailable"}</p>`;
    return;
  }
  wrap.innerHTML = `
    <h3>Module Inspector 2.0</h3>
    <div class="inspector-card glass">
      <h4>${info.label}</h4>
      <div class="nr"><span>path</span><b>${info.path}</b></div>
      <div class="nr"><span>subsystem</span><b>${info.subsystem}</b></div>
      <div class="nr"><span>risk score</span><b style="color:${riskColor(info.risk_score)}">${info.risk_score}</b></div>
      <div class="nr"><span>rank</span><b>${info.risk_rank ?? "—"}</b></div>
      <div class="nr"><span>LOC</span><b>${info.loc}</b></div>
      <div class="nr"><span>dependents / dependencies</span><b>${info.fan_in} / ${info.fan_out}</b></div>
      <div class="nr"><span>cycle member</span><b>${info.in_cycle ? "yes" : "no"}</b></div>
      <div class="nr"><span>blast radius</span><b>${info.blast_radius}</b></div>
      <div class="inspector-evidence"><div class="copilot-label">Importers</div><div class="taglist">${(info.importers || []).slice(0, 8).map(f => `<span class="tag">${f}</span>`).join("") || '<span class="muted">none</span>'}</div></div>
      <div class="inspector-evidence"><div class="copilot-label">Imports</div><div class="taglist">${(info.imports || []).slice(0, 8).map(f => `<span class="tag">${f}</span>`).join("") || '<span class="muted">none</span>'}</div></div>
      <div class="inspector-evidence"><div class="copilot-label">Evidence</div><ul class="clean">${(info.evidence || []).map(e => `<li>${e}</li>`).join("") || "<li class='muted'>No ranked signals</li>"}</ul></div>
      <div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap">
        <button class="btn small" onclick="askQuestion(${JSON.stringify(`Explain module ${info.path}`)})">Explain this module</button>
        <button class="btn small ghost" onclick="impactFor(${JSON.stringify(info.path)})">Analyze impact →</button>
      </div>
    </div>`;
}

function renderModuleInspectorPlaceholder() {
  const sum = STATE.summary || {};
  const hubs = (sum.top_hubs || []).slice(0, 5);
  const risks = (sum.top_risks || []).slice(0, 5);
  const hubItems = hubs.map(h => `<button type="button" class="qpick" onclick="selectModuleFromList(${JSON.stringify(h.path || h.module || "")})">${esc((h.module || h.path || "").split(/[./\\]/).pop())} <span class="muted">← ${h.fan_in ?? 0}</span></button>`).join("") || '<span class="muted tiny">—</span>';
  const riskItems = risks.map(r => `<button type="button" class="qpick" onclick="selectModuleFromList(${JSON.stringify(r.path || "")})">${esc((r.module || r.path || "").split(/[./\\]/).pop())} <span class="muted">${r.score ?? ""}</span></button>`).join("") || '<span class="muted tiny">—</span>';
  $("moduleInspector").innerHTML = `
    <h3>Module Inspector</h3>
    <p class="muted tiny inspector-empty">Select a module</p>
    <p class="muted tiny" style="margin:2px 0 10px">Click a node, or choose a file below, to inspect dependencies, risk, and impact.</p>
    <input type="search" id="inspectorSearch" class="mbp-filter" placeholder="Search modules…" oninput="inspectorSearchModules()" />
    <ul class="clean qpick-list" id="inspectorSearchResults" style="display:none"></ul>
    <div class="qpick-group"><div class="copilot-label">Top hubs</div><div class="qpick-row">${hubItems}</div></div>
    <div class="qpick-group"><div class="copilot-label">Top risks</div><div class="qpick-row">${riskItems}</div></div>`;
}

function inspectorSearchModules() {
  const q = ($("inspectorSearch")?.value || "").trim().toLowerCase();
  const out = $("inspectorSearchResults");
  if (!out) return;
  if (!q) { out.style.display = "none"; out.innerHTML = ""; return; }
  const nodes = (STATE.graph?.nodes || []).filter(n => n.path && n.path.toLowerCase().includes(q)).slice(0, 12);
  out.style.display = nodes.length ? "block" : "none";
  out.innerHTML = nodes.map(n => `<li><button type="button" class="mbp-item" onclick="selectModuleFromList(${JSON.stringify(n.path)})"><span class="mbp-path">${esc(n.path)}</span></button></li>`).join("");
}

function showNode(n) {
  STATE.selectedNode = n;
  $("selectedNodeCard").style.display = "block";
  $("selectedNodeCard").innerHTML = `<h4>Selected: ${n.label}</h4>
    <div class="muted tiny">${n.path || ""} · ${n.subsystem || ""} · ${n.fan_in ? `<b>${n.fan_in}</b> file${n.fan_in === 1 ? "" : "s"} import this` : "no importers"}</div>`;
  if (STATE.summary) $("suggest").innerHTML = renderCopilotSuggestions(STATE.summary);
  if ($("inspectorQuick")) $("inspectorQuick").style.display = n.path ? "flex" : "none";
  renderModuleInspector(n);
  ATLAS_UNIVERSE.refreshHighlight(n);
  ATLAS_UNIVERSE.flyToNode(n, 1100);
}

function startRepositoryTour() {
  const stops = STATE.tourStops || STATE.graph?.tour_stops || [];
  if (!stops.length) { toast("Tour unavailable — scan a repository first"); return; }
  $("tourPanel").style.display = "block";
  ATLAS_UNIVERSE.startTour(stops, ({ stop, index, total, done }) => {
    if (done) {
      $("tourPanel").style.display = "none";
      toast("Tour complete ✓", "success");
      return;
    }
    $("tourStep").textContent = `Step ${index + 1}/${total}`;
    $("tourTitle").textContent = stop.title;
    $("tourNarration").textContent = stop.narration;
  });
}

function stopRepositoryTour() {
  ATLAS_UNIVERSE.stopTour();
  $("tourPanel").style.display = "none";
}

function exportGraphPNG() {
  const url = ATLAS_UNIVERSE.exportPNG(2);
  if (!url) { toast("Export failed"); return; }
  ATLAS_UNIVERSE.downloadDataUrl(url, `atlas-universe-${Date.now()}.png`);
  toast("PNG exported ✓", "success");
}

function exportGraphSVG() {
  const svg = ATLAS_UNIVERSE.exportSVG();
  if (!svg) { toast("SVG export failed"); return; }
  ATLAS_UNIVERSE.downloadText(svg, `atlas-universe-${Date.now()}.svg`, "image/svg+xml");
  toast("SVG exported ✓", "success");
}

function toggleScreenshotMode() {
  STATE.screenshotMode = !STATE.screenshotMode;
  ATLAS_UNIVERSE.toggleScreenshotMode(STATE.screenshotMode);
  $("screenshotBtn").textContent = STATE.screenshotMode ? "Exit screenshot" : "Screenshot";
  if ($("screenshotExitBtn")) {
    $("screenshotExitBtn").style.display = STATE.screenshotMode ? "block" : "none";
    $("screenshotExitBtn").textContent = STATE.productTourActive ? "Stop tour" : "Exit screenshot";
  }
  if ($("presentationBadge")) $("presentationBadge").style.display = STATE.screenshotMode ? "block" : "none";
  if (STATE.graph3d || ATLAS_UNIVERSE.fg) {
    const host = $("graph3d");
    ATLAS_UNIVERSE.fg?.width(host.clientWidth).height(host.clientHeight);
  }
}

function exitPresentationMode() {
  if (STATE.productTourActive) { stopProductTour(); return; }
  if (STATE.screenshotMode) toggleScreenshotMode();
}

function resetGraphView() {
  if (typeof ATLAS_UNIVERSE?.resetGraphView === "function") {
    ATLAS_UNIVERSE.resetGraphView();
    return;
  }
  if (ATLAS_UNIVERSE?.fg) {
    ATLAS_UNIVERSE.fg.cameraPosition({ x: 0, y: 0, z: 600 }, { x: 0, y: 0, z: 0 }, 800);
  }
}

function copyInspectorPath() {
  const node = STATE.selectedNode;
  if (!node?.path) { toast("No module selected"); return; }
  copyText(node.path, "Path copied");
}

function genInspectorPrompt(target) {
  const node = STATE.selectedNode;
  if (!node?.path) { toast("No module selected"); return; }
  askQuestion(`Generate a ${target} prompt for module ${node.path}`);
}

async function exportDemoBundle() {
  const res = await api("/api/demo/export-bundle", "POST", {});
  if (!res.ok) { toast("✗ " + (res.error || "Export failed")); return; }
  const binary = atob(res.content_base64 || "");
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  const blob = new Blob([bytes], { type: "application/zip" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = res.filename || "atlas_demo_bundle.zip";
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 3000);
  toast("Demo bundle exported ✓", "success");
}

let _productTourTimer = null;
function stopProductTour() {
  STATE.productTourActive = false;
  if (_productTourTimer) clearTimeout(_productTourTimer);
  stopRepositoryTour();
  $("productTourPanel").style.display = "none";
  if (STATE.screenshotMode) toggleScreenshotMode();
}

function setProductTourStep(title, narration) {
  $("productTourPanel").style.display = "block";
  $("productTourTitle").textContent = title;
  $("productTourNarration").textContent = narration;
}

async function startProductTour() {
  if (STATE.productTourActive) return;
  if (!requireAtlasAccess("Product tour")) return;
  STATE.productTourActive = true;
  trackAnalytics("product_tour_started");
  dismissOnboarding(true);
  setProductTourStep("Loading demo", "Scanning bundled repository for a screen-recording friendly walkthrough…");
  await loadDemoMode("medium");
  await sleep(1200);
  if (!STATE.productTourActive) return;
  toggleScreenshotMode();
  go("center");
  await sleep(2500);
  if (!STATE.productTourActive) return;
  setProductTourStep("Repository universe", "Flying through subsystem galaxies — each cluster is real architecture from the scan.");
  startRepositoryTour();
  await sleep(34000);
  if (!STATE.productTourActive) return;
  stopRepositoryTour();
  setProductTourStep("Architectural risks", "Copilot answers are grounded in Builder Core ranking — no cloud API.");
  $("askInput").value = "What are the top architectural risks?";
  await sendCopilotQuestion();
  await sleep(6000);
  if (!STATE.productTourActive) return;
  const hub = STATE.summary?.top_hubs?.[0]?.path;
  if (hub) {
    setProductTourStep("What breaks?", `Showing what depends on ${hub} before you change it.`);
    $("impactTarget").value = hub;
    go("impact");
    await runImpact();
    await sleep(5000);
  }
  if (!STATE.productTourActive) return;
  setProductTourStep("AI context export", "One-click compact packets for Claude, Codex, or Cursor.");
  go("export");
  await refreshExport();
  await sleep(4000);
  setProductTourStep("Tour complete", "Scan your own repository from Home, or keep exploring the sample.");
  STATE.productTourActive = false;
  toast("Product tour complete ✓", "success");
}
function impactFor(path) { $("impactTarget").value = path; go("impact"); runImpact(); }

async function copyContext(target) {
  if (!requireAtlasAccess("Copy context")) return;
  const res = await api("/api/copilot/ask", "POST", { question: `Generate a ${target} prompt for this repo`, target, packet: "compact" });
  if (!res.ok) { toast("✗ Scan a repo first"); return; }
  const text = res.copy_targets?.[target] || res.suggested_prompt || "";
  copyText(text, `Copied ${target} context`);
}

/* ---------------- Plan Change ---------------- */
function esc(s) { return String(s || "").replace(/</g, "&lt;"); }

function renderLimitations(items) {
  const list = items || [];
  if (!list.length) return "";
  return `<h3 style="font-size:13px;color:var(--amber);margin-top:14px">Limitations</h3><ul class="clean">${list.map(x => `<li>${esc(x)}</li>`).join("")}</ul>`;
}

function renderEvidenceSummary(panel, rev) {
  const ep = panel || rev?.evidence_panel || {};
  if (!ep || (!ep.matched_symbols?.length && !ep.selected_because?.length && !ep.repository_evidence?.length)) return "";
  const syms = (ep.matched_symbols || []).slice(0, 6);
  const refs = (ep.matched_references || []).slice(0, 5);
  const graph = (ep.graph_support || []).slice(0, 4);
  const repo = (ep.repository_evidence || []).slice(0, 4);
  const because = (ep.selected_because || []).slice(0, 5);
  return `
    <div class="report-section evidence-summary">
      <div class="report-label">Evidence Summary</div>
      ${syms.length ? `<p class="muted tiny"><b>Matched symbols</b></p><ul class="clean tiny">${syms.map(s => `<li><span class="tag sym">${esc(s.qualname || s.name)}</span> — ${esc(s.kind)} in <span class="tag" onclick="investigateFile(${JSON.stringify(s.file_path)})">${esc(s.file_path)}</span></li>`).join("")}</ul>` : ""}
      ${refs.length ? `<p class="muted tiny"><b>Matched references</b></p><ul class="clean tiny">${refs.map(r => `<li>${esc(r.symbol)} ← ${esc(r.reference)}</li>`).join("")}</ul>` : ""}
      ${graph.length ? `<p class="muted tiny"><b>Graph support</b></p><ul class="clean tiny">${graph.map(g => `<li>${esc(g)}</li>`).join("")}</ul>` : ""}
      ${repo.length ? `<p class="muted tiny"><b>Repository evidence</b></p><ul class="clean tiny">${repo.map(r => `<li>${esc(r)}</li>`).join("")}</ul>` : ""}
      ${because.length ? `<p class="muted tiny"><b>Selected because</b></p><ul class="clean tiny">${because.map(b => `<li>${esc(b)}</li>`).join("")}</ul>` : ""}
    </div>`;
}

function renderImplementationWhy(items) {
  const rows = (items || []).filter(x => x && x.path).slice(0, 8);
  if (!rows.length) return "";
  return `
    <div class="report-section">
      <div class="report-label">Why these files</div>
      <ul class="clean tiny">${rows.map(r => `<li><span class="tag" onclick="investigateFile(${JSON.stringify(r.path)})">${esc(r.path)}</span>${r.tier === "review" ? ' <span class="pill">review only</span>' : ""} — ${esc(r.why || "")}</li>`).join("")}</ul>
    </div>`;
}

function renderRepositoryEvidence(rev, plan) {
  if (!rev || !rev.status) {
    if (plan?.evidence_panel) return renderEvidenceSummary(plan.evidence_panel, null);
    return "";
  }
  const goal = plan?.goal || plan?.change_goal || plan?.symptom || plan?.symptom_summary || "";
  const status = fiUserFacingStatus(rev.status, goal);
  const score = fiCapScore(rev.confidence_score);
  const files = (rev.file_evidences || []).slice(0, 5);
  return `
    <div class="domain-panel glass evidence-panel advanced-only">
      <div class="domain-head">
        <span class="domain-concept">Repository match</span>
        <span class="pill quality-source">${esc(status)}</span>
      </div>
      ${renderEvidenceSummary(rev.evidence_panel || plan?.evidence_panel, rev)}
      ${rev.found?.length ? `<div class="report-section"><div class="report-label">Found</div><ul class="clean tiny">${rev.found.slice(0, 6).map(x => `<li>${esc(x)}</li>`).join("")}</ul></div>` : ""}
      ${rev.missing?.length ? `<div class="report-section"><div class="report-label">Missing</div><ul class="clean tiny">${rev.missing.slice(0, 4).map(x => `<li>${esc(x)}</li>`).join("")}</ul></div>` : ""}
      ${rev.recommended_insertion ? `<p class="muted tiny"><b>Suggested location:</b> <span class="tag" onclick="investigateFile(${JSON.stringify(rev.recommended_insertion)})">${esc(rev.recommended_insertion)}</span></p>` : ""}
      ${files.length ? `<div class="report-section"><div class="report-label">Evidence by file</div><ul class="clean tiny">${files.map(f => `<li><span class="tag" onclick="investigateFile(${JSON.stringify(f.path)})">${esc(f.path)}</span> — ${esc(fiCapScore(f.evidence_score))}/100 · ${esc(f.selected_because || f.reason_selected || (f.matching_symbols || []).slice(0, 2).join(", "))}</li>`).join("")}</ul></div>` : ""}
    </div>`;
}

function renderDomainKnowledge(dk) {
  if (!dk || !dk.applied) return "";
  const roles = dk.file_roles || {};
  const risks = (dk.knowledge_risks || dk.risks || []).slice(0, 8);
  const failures = (dk.failure_modes || dk.domain_failure_modes || []).slice(0, 6);
  const verify = (dk.verification || []).slice(0, 5);
  const testing = (dk.testing || []).slice(0, 4);
  const source = dk.source || "local";
  const qualityLabel = dk.knowledge_quality_label || (dk.concept_quality_score === "generated_template" ? "Local generated" : "Curated");
  const qualityClass = dk.knowledge_depth_warning ? "quality-generated" : (dk.concept_quality_score === "source_backed" ? "quality-source" : "quality-curated");
  const tag = (p) => `<span class="tag" onclick="investigateFile(${JSON.stringify(p)})">${esc(p)}</span>`;
  return `
    <div class="domain-panel glass">
      <div class="domain-head">
        <span class="domain-concept">${esc(dk.concept_name)}${dk.concept_title && dk.concept_title !== dk.concept_name ? ' — ' + esc(dk.concept_title) : ''}</span>
        <span class="pill">${esc(dk.domain_label || dk.domain)}</span>
      </div>
      ${dk.knowledge_depth_warning ? `<p class="muted tiny warn">Template knowledge — verify with official docs before implementing.</p>` : ""}
      <p class="domain-why"><b>Meaning:</b> ${esc(dk.concept_understanding || dk.meaning || "")}</p>
      ${dk.why_this_matters ? `<p class="muted tiny">${esc(dk.why_this_matters)}</p>` : ""}
      ${risks.length ? `<div class="report-section"><div class="report-label">Risks</div><ul class="clean tiny">${risks.map(r => `<li>${esc(r)}</li>`).join("")}</ul></div>` : ""}
      ${failures.length ? `<div class="report-section"><div class="report-label">Failure modes</div><ul class="clean tiny">${failures.map(r => `<li>${esc(r)}</li>`).join("")}</ul></div>` : ""}
      ${verify.length ? `<div class="report-section"><div class="report-label">Verification</div><ul class="clean tiny">${verify.map(r => `<li>${esc(r)}</li>`).join("")}</ul></div>` : ""}
      ${testing.length ? `<div class="report-section"><div class="report-label">Testing</div><ul class="clean tiny">${testing.map(r => `<li>${esc(r)}</li>`).join("")}</ul></div>` : ""}
      ${(roles.must_inspect || []).length ? `<div class="report-section"><div class="report-label">Must inspect</div><div class="taglist">${roles.must_inspect.map(tag).join("")}</div></div>` : ""}
      ${(roles.likely_modify || []).length ? `<div class="report-section"><div class="report-label">Likely modify</div><div class="taglist">${roles.likely_modify.map(tag).join("")}</div></div>` : ""}
      ${(roles.verify_only || []).length ? `<div class="report-section"><div class="report-label">Verify only</div><div class="taglist">${roles.verify_only.map(tag).join("")}</div></div>` : ""}
      ${dk.integration_note ? `<p class="muted tiny">${esc(dk.integration_note)}</p>` : ""}
    </div>`;
}

async function runChangePlan() {
  if (!requireAtlasAccess("Implementation Plan")) return;
  const request = $("buildRequest")?.value.trim();
  if (!request) { toast("Describe the change you want"); return; }
  window.atlasActivity?.add("Implementation Plan created");
  const r = await api("/api/planning/change", "POST", { request });
  const out = $("buildOut");
  if (!r.ok) {
    out.innerHTML = workflowErrorHtml("Could not generate plan", r, "Try a more specific request or pick a module from the Map.");
    return;
  }
  STATE.buildResult = r;
  if (typeof markFirstBuildPlanDone === "function") markFirstBuildPlanDone();
  if (typeof afterChangePlanSuccess === "function") afterChangePlanSuccess();
  const p = r.plan || {};
  const prompts = r.prompts || {};
  if (typeof applyExportNavVisibility === "function") applyExportNavVisibility();
  // Explanatory sentence: why these files?
  const topFiles = (p.files_to_inspect_first || []).slice(0, 3);
  const filesNote = topFiles.length
    ? `<p class="muted tiny" style="margin:0 0 10px">These files ranked highest by how many other modules depend on them${p.likely_affected_subsystems?.length ? ` in <b>${esc(p.likely_affected_subsystems[0])}</b>` : ""}.</p>`
    : "";
  out.innerHTML = `
    ${typeof beginnerPlanHero === "function" ? beginnerPlanHero(p, "build") : (typeof sendToAiPanel === "function" ? sendToAiPanel("build") : "")}
    <div class="advanced-only">
    <div class="glass ocard">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
        <h3 style="margin:0">Implementation Plan</h3>
        <span class="lvl ${p.confidence?.includes('high') ? 'low' : 'medium'}">${typeof atlasFriendlyConfidence === "function" ? atlasFriendlyConfidence(p.confidence) : esc(p.confidence)} confidence</span>
      </div>
      ${filesNote}
      <p class="muted tiny" style="margin:4px 0 10px">Size: <b>${esc(p.estimated_change_size)}</b> · Risk: <b>${esc(p.risk_level)}</b></p>
      ${typeof trustBlock === "function" ? trustBlock("build") : ""}
      ${renderDomainKnowledge(p.domain_knowledge)}
      ${renderRepositoryEvidence(p.repository_evidence || p.domain_knowledge?.repository_evidence, p)}
      ${renderImplementationWhy(p.implementation_files_with_why)}
      <div class="plan-grid">
        <div class="report-section"><div class="report-label">Affected systems</div><div class="taglist">${(p.affected_systems || p.likely_affected_subsystems || []).map(s => `<span class="tag">${esc(s)}</span>`).join("") || '<span class="muted tiny">none matched</span>'}</div></div>
        <div class="report-section"><div class="report-label">Entry points</div><div class="taglist">${(p.entry_points || []).map(s => `<span class="tag">${esc(s)}</span>`).join("") || '<span class="muted tiny">none detected</span>'}</div></div>
      </div>
      <div class="report-section"><div class="report-label">Implementation order</div><ol class="clean">${(p.implementation_order || []).map(s => `<li>${esc(s)}</li>`).join("") || '<li class="muted">n/a</li>'}</ol></div>
      <div class="report-section"><div class="report-label">What may break</div><div class="taglist">${(p.what_may_break || p.files_likely_to_break || []).map(s => `<span class="tag" onclick="investigateFile(${JSON.stringify(s)})">${esc(s)}</span>`).join("") || '<span class="muted tiny">nothing high-risk identified</span>'}</div></div>
      <div class="report-section"><div class="report-label">Tests to run</div><ul class="clean">${(p.tests_required || p.tests_likely_affected || []).map(s => `<li>${esc(s)}</li>`).join("")}</ul></div>
      <details style="margin-top:8px"><summary class="muted tiny">Full plan (markdown)</summary>
        <pre class="code" style="max-height:320px;overflow:auto">${esc(r.formatted || "")}</pre>
      </details>
      ${renderLimitations(r.limitations)}
      <details style="margin-top:12px"><summary class="muted tiny">Agent handoff preview</summary>
        <pre class="code">${esc(prompts.claude || "")}</pre></details>
      <details style="margin-top:10px"><summary class="muted tiny">Simulate blast radius</summary>
        <div class="pick-row" style="margin-top:8px">
          <input id="buildImpactTarget" type="text" placeholder="module path" value="${esc((p.files_to_inspect_first || [])[0] || "")}" />
          <button class="btn ghost" onclick="runBuildImpact()">Simulate</button>
        </div>
        <div id="buildImpactOut"></div>
      </details>
      ${typeof workflowFeedbackHtml === "function" ? workflowFeedbackHtml("build") : ""}
    </div>
    </div>`;
  renderWorkflowHistory("build", "buildHistory");
}

function copyBuildPrompt(tool) {
  const text = STATE.buildResult?.prompts?.[tool] || "";
  if (!text) { toast("Generate a plan first"); return; }
  copyText(text, `Copied ${tool} prompt`);
}

async function runBuildImpact() {
  const target = $("buildImpactTarget")?.value.trim();
  if (!target) { toast("Enter a file or module"); return; }
  const r = await api("/api/planning/impact", "POST", { target });
  const host = $("buildImpactOut");
  if (!host) return;
  if (!r.ok) { host.innerHTML = `<p class="muted tiny">${esc(r.error)}</p>`; return; }
  const sim = r.simulation || {};
  host.innerHTML = `
    <div class="glass" style="margin-top:10px;padding:12px">
      <p><b>Risk:</b> ${esc(sim.risk_level)} · <b>Affected files:</b> ${(sim.potentially_affected_modules || []).length}</p>
      <div class="taglist">${(sim.potentially_affected_modules || []).slice(0, 12).map(f => `<span class="tag">${esc(f)}</span>`).join("")}</div>
      <ul class="clean tiny">${(sim.recommended_verification || []).map(v => `<li>${esc(v)}</li>`).join("")}</ul>
    </div>`;
}

/* ---------------- Investigate (Symptom Engine) ---------------- */
async function runInvestigationPlan() {
  if (!requireAtlasAccess("Failure Investigation")) return;
  const symptom = $("investigateSymptom")?.value.trim();
  if (!symptom) { toast("Describe the symptom"); return; }
  window.atlasActivity?.add("Failure Investigation completed");
  const r = await api("/api/planning/investigate", "POST", { symptom });
  const out = $("investigateOut");
  if (!r.ok) {
    out.innerHTML = workflowErrorHtml("Failure investigation could not run", r, "Include a file path, error message, or module name for better grounding.");
    return;
  }
  STATE.investigateResult = r;
  const p = r.plan || {};
  const prompts = r.prompts || {};
  out.innerHTML = `
    ${typeof beginnerInvestigateHero === "function" ? beginnerInvestigateHero(p) : ""}
    <div class="advanced-only glass ocard">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <h3 style="margin:0">Failure Investigation</h3>
        <span class="lvl ${p.confidence === 'high' ? 'low' : p.confidence === 'low' ? 'unknown' : 'medium'}">${typeof atlasFriendlyConfidence === "function" ? atlasFriendlyConfidence(p.confidence) : esc(p.confidence)} confidence</span>
      </div>
      <div class="report-section">
        <div class="report-label">What you reported</div>
        <p>${esc(p.symptom_summary || p.symptom || "")}</p>
      </div>
      ${typeof trustBlock === "function" ? trustBlock("investigate") : ""}
      ${renderDomainKnowledge(p.domain_knowledge)}
      ${renderRepositoryEvidence(p.repository_evidence || p.domain_knowledge?.repository_evidence, p)}
      ${(p.domain_failure_modes || []).length ? `<div class="report-section"><div class="report-label">What typically breaks here</div><ul class="clean">${p.domain_failure_modes.map(m => `<li>${esc(m)}</li>`).join("")}</ul></div>` : ""}
      <div class="report-section">
        <div class="report-label">Most likely cause</div>
        <p class="root-cause">${esc(p.most_likely_root_cause || p.most_likely_source || "Add a file path or error message to ground the analysis further.")}</p>
      </div>
      <div class="report-section">
        <div class="report-label">Hypotheses</div>
        ${renderHypotheses(p.hypotheses || [])}
      </div>
      ${(p.verification_checklist || []).length ? `<div class="report-section"><div class="report-label">How to confirm</div><ul class="clean">${p.verification_checklist.map(v => `<li>${esc(v)}</li>`).join("")}</ul></div>` : ""}
      ${(p.minimal_fix_strategy || []).length ? `<div class="report-section"><div class="report-label">Fix approach</div><ul class="clean">${p.minimal_fix_strategy.map(v => `<li>${esc(v)}</li>`).join("")}</ul></div>` : ""}
      ${(p.risks_of_incorrect_fix || []).length ? `<div class="report-section"><div class="report-label">What to watch out for</div><ul class="clean">${p.risks_of_incorrect_fix.map(v => `<li>${esc(v)}</li>`).join("")}</ul></div>` : ""}
      ${renderLimitations(r.limitations)}
      ${typeof sendToAiPanel === "function" ? sendToAiPanel("investigate") : ""}
      <details style="margin-top:12px"><summary class="muted tiny">Full analysis (markdown)</summary>
        <pre class="code">${esc(r.formatted || "")}</pre></details>
      ${typeof workflowFeedbackHtml === "function" ? workflowFeedbackHtml("investigate") : ""}
    </div>`;
  renderWorkflowHistory("investigate", "investigateHistory");
}

const _HYP_RANK_LABELS = ["Most likely", "Alternative", "Less likely"];
function renderHypotheses(hyps) {
  if (!hyps.length) {
    return `<p class="muted tiny">No grounded hypotheses yet — add a file path, error message, or module name and try again.</p>`;
  }
  return hyps.map((h, i) => {
    const conf = h.confidence === "high" ? "low" : h.confidence === "low" ? "unknown" : "medium";
    const rankLabel = _HYP_RANK_LABELS[i] || `Hypothesis ${i + 1}`;
    const files = (h.files_involved || []).map(f => `<span class="tag" onclick="investigateFile(${JSON.stringify(f)})" title="Check impact">${esc(f)}</span>`).join("")
      || '<span class="muted tiny">Add a stack trace or file path to ground this hypothesis</span>';
    return `
    <div class="hyp-card">
      <div class="hyp-head">
        <span class="hyp-rank">${esc(rankLabel)}</span>
        <span class="hyp-title">${esc(h.title)}</span>
        <span class="lvl ${conf}">${esc(h.confidence)}</span>
      </div>
      <p class="hyp-why"><b>Why it fits:</b> ${esc(h.why_it_fits)}</p>
      <div class="hyp-files">${files}</div>
      ${(h.evidence || []).length ? `<ul class="clean tiny hyp-evidence advanced-only">${h.evidence.map(e => `<li>${esc(e)}</li>`).join("")}</ul>` : ""}
      <p class="hyp-line"><b>If correct:</b> ${esc(h.what_should_be_true_if_correct || "")}</p>
      <p class="hyp-line disprove"><b>How to confirm or rule out:</b> ${esc(h.how_to_disprove || "")}</p>
    </div>`;
  }).join("");
}

function investigateFile(path) {
  if ($("impactTarget")) { $("impactTarget").value = path; }
  go("impact");
  runImpact();
}

function copyInvestigatePrompt(tool) {
  const text = STATE.investigateResult?.prompts?.[tool] || "";
  if (!text) { toast("Generate a plan first"); return; }
  copyText(text, `Copied ${tool} prompt`);
}

/* ---------------- Impact ---------------- */
async function runImpact() {
  if (!requireAtlasAccess("Change Impact")) return;
  const target = $("impactTarget").value.trim();
  if (!target) { toast("Enter a file or module"); return; }
  const out = $("impactOut");
  const btn = $("impactTarget")?.closest(".pick-row")?.querySelector(".btn.primary");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Analyzing…";
  }
  out.innerHTML = `<div class="impact-result-panel impact-loading"><p class="muted">Analyzing <span class="mono">${esc(target)}</span>…</p></div>`;
  out.dataset.atlasRepoKey = activeRepositoryKey();
  window.atlasActivity?.add("Impact analysis run");
  let r;
  try {
    r = await api("/api/planning/impact", "POST", { target });
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Analyze impact";
    }
  }
  if (!r.ok) {
    // Distinct state: the analysis ran fine but the target is not in the
    // scanned graph. This is not a failure of Atlas — say so plainly instead
    // of showing the generic error panel.
    if (r.status === "target_not_resolved" || r.unresolved) {
      out.innerHTML = `<div class="impact-result-panel impact-state-not-found">
        <h3 style="margin:0 0 6px">Target not found in this repository</h3>
        <p class="muted"><span class="mono">${esc(target)}</span> is not in the last scan, so Atlas cannot trace its dependents.</p>
        <ul class="clean tiny muted">
          <li>Check the spelling, or pick a file from the scanned list below the input.</li>
          <li>If the file is new, refresh the scan first.</li>
        </ul>
      </div>`;
      return;
    }
    out.innerHTML = `<div class="impact-result-panel impact-state-failed">${workflowErrorHtml("Change impact analysis could not run", r, "Use a path from the graph or an architecture concept (e.g. authentication, routing).")}</div>`;
    return;
  }
  STATE.impactResult = r;
  updateWorkflowToolbars();
  if (r.target_node_id) {
    ATLAS_UNIVERSE.highlightBlastRadius({
      target_node_id: r.target_node_id,
      affected_node_ids: r.affected_node_ids || [],
    });
  }
  const rl = r.risk_level || "unknown";
  const conf = r.confidence || "medium";
  const mockTag = r.mock ? `<span class="pill warn">Estimate only — not in last scan</span>` : "";
  const list = (arr, n) => (arr || []).slice(0, n || 8).map(t => `<li>${esc(t)}</li>`).join("") || "";
  const dirN = (r.direct_impact || []).length;
  const indN = (r.indirect_impact || []).length;
  const subs = [...new Set((r.affected_subsystems || r.architecture?.subsystems_impacted || []).map(String))].slice(0, 8);
  const unresolved = [...new Set([...(r.limitations || []), ...((r.risky_areas || []).map(a => typeof a === "string" ? a : (a.reason || a.label || "")))])].filter(Boolean).slice(0, 6);
  const repoLine = STATE.summary?.ok
    ? `<p class="impact-context-inline">Analyzing <span class="mono">${esc(STATE.summary.repo_name || "repository")}</span>${STATE.summary.file_count != null ? ` · ${homeMetric(STATE.summary.file_count)} files` : ""}${STATE.summary.dependency_edges != null ? ` · ${homeMetric(STATE.summary.dependency_edges)} dependencies` : ""}</p>`
    : "";
  const directHtml = dirN
    ? `<div class="report-section"><div class="report-label">Direct dependents (${dirN})</div>${impactModuleTags(r.direct_impact)}</div>`
    : `<div class="report-section"><div class="report-label">Direct dependents</div><p class="muted tiny">No indexed dependents found.</p></div>`;
  const indirectHtml = indN
    ? `<div class="report-section"><div class="report-label">Transitive dependents (${indN})</div>${impactModuleTags(r.indirect_impact)}</div>`
    : "";
  out.innerHTML = `<div class="impact-result-panel glass ocard impact-card" data-atlas-repo-key="${esc(activeRepositoryKey())}">
    ${repoLine}
    <div class="impact-head">
      <h3 style="margin:0">Impact of changing <span class="mono">${esc(r.target)}</span></h3>
      <div class="impact-badges"><span class="lvl ${rl}">${rl} risk</span><span class="pill">confidence ${esc(conf)}</span>${mockTag}</div>
    </div>
    ${impactSemanticCard(r)}
    ${impactBlastCard(r)}
    ${directHtml}
    ${indirectHtml}
    ${subs.length ? `<div class="report-section"><div class="report-label">Affected subsystems</div><ul class="clean">${subs.map(s => `<li>${esc(s)}</li>`).join("")}</ul></div>` : ""}
    <div class="report-section"><div class="report-label">Affected tests</div><ul class="clean">${list(r.tests_likely_affected) || '<li class="muted tiny">No indexed test paths linked to this target.</li>'}</ul></div>
    ${unresolved.length ? `<div class="report-section"><div class="report-label">Unresolved dynamic edges</div><ul class="clean tiny">${unresolved.map(u => `<li>${esc(u)}</li>`).join("")}</ul></div>` : ""}
    <div class="impact-arch-summary">${esc(impactArchSummary(r))}</div>
    ${typeof trustBlock === "function" ? `<div class="advanced-only">${trustBlock("impact")}</div>` : ""}
    <div class="report-section"><div class="report-label">Verification steps</div><ul class="clean">${list(r.recommended_verification) || '<li class="muted tiny">Run targeted tests after any change.</li>'}</ul></div>
    <details class="advanced-only" style="margin-top:6px"><summary class="muted tiny">What to watch out for · probably safe · evidence</summary>
      <div class="report-label" style="margin-top:8px">What to watch out for</div><ul class="clean tiny">${list(r.risks_of_incorrect_fix, 5) || '<li class="muted tiny">—</li>'}</ul>
      <div class="report-label" style="margin-top:8px">Likely safe (no import path)</div><ul class="clean tiny">${list(r.what_probably_wont_break, 6) || '<li class="muted tiny">—</li>'}</ul>
      <div class="report-label" style="margin-top:8px">Evidence</div><ul class="clean tiny">${list(r.evidence, 6) || '<li class="muted tiny">—</li>'}</ul></details>
    ${typeof sendToAiPanel === "function" ? sendToAiPanel("impact") : ""}
    <details class="advanced-only" style="margin-top:8px"><summary class="muted tiny">Full impact report (markdown)</summary>
      <pre class="code" style="max-height:320px;overflow:auto">${esc(r.formatted || "")}</pre>
    </details>
    <div class="copy-row" style="margin-top:12px">
      <button class="btn small ghost" onclick="go('center')">Show on map</button>
    </div>
    ${typeof workflowFeedbackHtml === "function" ? workflowFeedbackHtml("impact") : ""}
  </div>`;
  out.dataset.atlasRepoKey = activeRepositoryKey();
  renderWorkflowHistory("impact", "impactHistory");
}

/* ---- Impact summary cards (presentation only) ---- */
function _impactTag(f) {
  return `<span class="tag" role="button" onclick="impactInspect(${JSON.stringify(f)})">${esc(f)}</span>`;
}

function _isTestPath(p) {
  const s = String(p || "").toLowerCase();
  return /(^|\/)tests?\//.test(s) || /(^|\/)test_|_test\.|\.test\./.test(s) || /(^|\/)spec\//.test(s);
}

function _subsystemOf(p) {
  const parts = String(p || "").split("/");
  return parts.length > 1 ? parts[0] : "(root)";
}

function _impactCappedTags(arr, n, label) {
  arr = arr || [];
  if (!arr.length) return '<div class="muted tiny">none detected</div>';
  const top = arr.slice(0, n).map(_impactTag).join("");
  const rest = arr.slice(n);
  let html = `<div class="taglist">${top}</div>`;
  if (rest.length) {
    html += `<details class="impact-showall"><summary class="muted tiny">Show all ${arr.length} ${label} (+${rest.length} more)</summary>`
      + `<div class="taglist" style="margin-top:6px">${rest.map(_impactTag).join("")}</div></details>`;
  }
  return html;
}

// Impact result hierarchy: risk summary -> directly affected ->
// indirectly affected (grouped) -> tests -> unknown/dynamic -> evidence.
function renderImpactHierarchy(res) {
  const direct = (res.direct_impact || []).filter(f => !_isTestPath(f));
  const indirect = (res.indirect_impact || []).filter(f => !_isTestPath(f));
  const allAffected = [...(res.direct_impact || []), ...(res.indirect_impact || []), ...(res.files || [])];
  const tests = [...new Set(allAffected.filter(_isTestPath))];
  const rl = res.risk_level || "unknown";

  // Indirectly affected grouped by top-level subsystem.
  const groups = {};
  indirect.forEach(f => { (groups[_subsystemOf(f)] = groups[_subsystemOf(f)] || []).push(f); });
  const groupKeys = Object.keys(groups).sort((a, b) => groups[b].length - groups[a].length);
  const indirectHtml = groupKeys.length
    ? groupKeys.map(k => `<div class="impact-subgroup"><div class="muted tiny">${esc(k)} (${groups[k].length})</div>${_impactCappedTags(groups[k], 6, "modules")}</div>`).join("")
    : '<div class="muted tiny">none detected</div>';

  const unknown = [...(res.limitations || []), ...((res.risky_areas || []).map(a => typeof a === "string" ? a : (a.reason || a.label || "")))].filter(Boolean);
  const evidence = res.evidence || [];

  return `<div class="impact-hierarchy">
    <div class="impact-risk-summary">
      <span class="lvl ${esc(rl)}">${esc(rl)} risk</span>
      <span class="muted tiny">${direct.length} direct · ${indirect.length} transitive · ${(res.affected_subsystems || []).length} subsystem(s)</span>
      <p class="tiny" style="margin:6px 0 0">${esc(res.answer || "")}</p>
    </div>
    <div class="impact-tier"><div class="copilot-label">Directly affected</div>${_impactCappedTags(direct, 8, "direct dependents")}</div>
    <div class="impact-tier"><div class="copilot-label">Indirectly affected</div>${indirectHtml}</div>
    <div class="impact-tier"><div class="copilot-label">Tests likely affected</div>${tests.length ? _impactCappedTags(tests, 8, "test files") : '<div class="muted tiny">No indexed tests reference the affected modules.</div>'}</div>
    <div class="impact-tier"><div class="copilot-label">Unknown or dynamic risks</div>${unknown.length ? `<ul class="clean tiny">${unknown.slice(0, 5).map(u => `<li>${esc(u)}</li>`).join("")}</ul>` : '<div class="muted tiny">No dynamic-dispatch or unresolved-edge risks flagged.</div>'}</div>
    <details class="impact-tier"><summary class="copilot-label" style="cursor:pointer">Evidence (${evidence.length})</summary>${evidence.length ? `<ul class="clean tiny">${evidence.slice(0, 8).map(e => `<li>${esc(e)}</li>`).join("")}</ul>` : '<div class="muted tiny">No ranked signals.</div>'}</details>
  </div>`;
}

function impactModuleTags(arr, n) {
  arr = arr || [];
  n = n || 10;
  if (!arr.length) return '<div class="taglist"><span class="muted tiny">none</span></div>';
  const top = arr.slice(0, n).map(_impactTag).join("");
  const rest = arr.slice(n);
  let html = `<div class="taglist">${top}</div>`;
  if (rest.length) {
    html += `<details class="impact-showall"><summary class="muted tiny">Show all ${arr.length} impacted modules (+${rest.length} more)</summary>`
      + `<div class="taglist" style="margin-top:6px">${rest.map(_impactTag).join("")}</div></details>`;
  }
  return html;
}

function impactSemanticCard(r) {
  if (!r.semantic_label) return "";
  const mods = (r.resolved_modules || []).slice(0, 8);
  const syms = (r.resolved_symbols || [])
    .map(s => (typeof s === "string" ? s : (s.qualname || s.name))).filter(Boolean);
  const uniqSyms = [...new Set(syms)].slice(0, 8);
  return `<div class="impact-summary-card semantic">
    <div class="isc-label">Semantic target</div>
    <div class="isc-title">${esc(r.semantic_label)}<span class="pill">confidence ${esc(r.confidence || "medium")}</span></div>
    <div class="isc-sub">Resolved to ${(r.resolved_modules || []).length} module(s):</div>
    <div class="taglist">${mods.map(_impactTag).join("") || '<span class="muted tiny">—</span>'}</div>
    ${uniqSyms.length ? `<div class="isc-sub" style="margin-top:8px">Key symbols:</div><div class="taglist">${uniqSyms.map(s => `<span class="tag sym">${esc(s)}</span>`).join("")}</div>` : ""}
  </div>`;
}

function impactBlastCard(r) {
  const arch = r.architecture || {};
  const blast = r.architectural_blast_radius ?? arch.architectural_blast_radius ?? 0;
  const dir = (r.direct_impact || []).length;
  const ind = (r.indirect_impact || []).length;
  const rl = r.risk_level || "unknown";
  const c = riskColor(rl === "high" ? 70 : rl === "medium" ? 40 : 12);
  return `<div class="impact-summary-card blast">
    <div class="isc-label">Blast radius</div>
    <div class="blast-metrics">
      <div class="blast-metric"><span class="bm-num" style="color:${c}">${blast}</span><span class="bm-lbl">architectural blast radius</span></div>
      <div class="blast-metric"><span class="bm-num">${dir}</span><span class="bm-lbl">direct importers</span></div>
      <div class="blast-metric"><span class="bm-num">${ind}</span><span class="bm-lbl">transitive impact</span></div>
    </div>
  </div>`;
}

function _humanList(arr) {
  if (!arr.length) return "";
  if (arr.length === 1) return arr[0];
  return arr.slice(0, -1).join(", ") + " and " + arr[arr.length - 1];
}

function impactArchSummary(r) {
  const arch = r.architecture || {};
  const repo = (STATE.summary && STATE.summary.repo_name) ? STATE.summary.repo_name.replace(/[-_]/g, " ") : "";
  const subj = r.semantic_label || ((r.target || "").split(/[\\/]/).pop());
  const subjFull = repo ? `the ${repo} ${subj}` : subj;
  const subs = (arch.subsystems_impacted || r.affected_subsystems || [])
    .map(s => String(s).split("/").pop()).filter(Boolean);
  const uniq = [...new Set(subs)].slice(0, 5);
  const subsTxt = uniq.length ? _humanList(uniq) : "multiple";
  const blast = r.architectural_blast_radius ?? arch.architectural_blast_radius ?? 0;
  let reason;
  if (arch.runtime_criticality) {
    reason = "Blast radius is high because it sits on a runtime boundary that many components communicate through.";
  } else if (blast >= 12 || r.risk_level === "high") {
    reason = `Blast radius is high (${blast} importers across ${uniq.length || "several"} subsystem(s)).`;
  } else if (blast >= 4) {
    reason = `Blast radius is moderate (${blast} importer(s)).`;
  } else {
    reason = `Blast radius is contained (${blast} importer(s)).`;
  }
  return `Changing ${subjFull} affects ${subsTxt} ${uniq.length === 1 ? "subsystem" : "subsystems"}. ${reason}`;
}

function impactInspect(path) {
  if ($("impactTarget")) $("impactTarget").value = path;
  runImpact();
}

function copyImpactPrompt() {
  const r = STATE.impactResult;
  if (!r) { toast("Run an impact analysis first"); return; }
  const txt = `Assess the impact of changing \`${r.target}\` (risk: ${r.risk_level}).\n`
    + `Direct importers: ${(r.direct_impact || []).join(", ") || "none"}\n`
    + `Transitive importers: ${(r.indirect_impact || []).join(", ") || "none"}\n`
    + `Run these tests: ${(r.tests_likely_affected || []).slice(0, 6).join("; ")}\n`
    + `Verify each importer's behavior and the listed tests before merge. Do not change the public interface without checking every importer.`;
  copyText(txt, "Impact prompt copied");
}

/* ---------------- AI Context Export ---------------- */
function wireSeg(id, key) {
  $(id).querySelectorAll("button").forEach(b => b.onclick = () => {
    $(id).querySelectorAll("button").forEach(x => x.classList.remove("active"));
    b.classList.add("active"); STATE[key] = b.dataset.v; refreshExport();
  });
}
const EXPORT_TARGET_LABEL = { claude: "Claude", codex: "Codex", cursor: "Cursor" };

function updateCopyExportLabel() {
  const btn = $("copyExportBtn");
  if (btn) btn.textContent = `Generate ${EXPORT_TARGET_LABEL[STATE.exportTarget] || "Claude"} context`;
}

function agentTaskText() {
  return ($("agentTask")?.value || "").trim();
}

async function refreshExport() {
  if (!requireAtlasAccess("Context export")) return;
  updateCopyExportLabel();
  const sum = STATE.summary || await api("/api/repositories/current/summary");
  if (!sum.ok) {
    $("exportPreview").innerHTML = emptyStateHtml(
      "Scan a repository first",
      "Load the sample or scan your own folder to preview repo-wide context for Claude, Cursor, or Codex.",
      "Scan repository",
      "go('scan')"
    );
    $("tokEst").textContent = "—";
    $("previewMeta").textContent = "Scan first";
    return;
  }
  const res = await api("/api/context/export", "POST", { target: STATE.exportTarget, packet: STATE.exportPacket });
  if (!res.ok) { $("exportPreview").textContent = "Scan a repository first."; $("tokEst").textContent = "—"; return; }
  $("exportPreview").textContent = res.text;
  $("tokEst").textContent = res.estimated_tokens;
  $("previewMeta").textContent = `${res.target} · ${res.packet} · ~${res.estimated_tokens} tokens`;
  STATE._exportText = res.text;

  // export result feedback funnel.
  const efs = $("exportFeedbackSlot");
  if (efs && typeof workflowFeedbackHtml === "function") efs.innerHTML = workflowFeedbackHtml("export");
}

async function generateAgentExport() {
  if (!requireAtlasAccess("Agent export")) return;
  updateCopyExportLabel();
  const task = agentTaskText();
  if (!task) {
    toast("Describe the task first", "error");
    if ($("agentTask")) $("agentTask").focus();
    return;
  }
  const res = await api("/api/integrations/export", "POST", {
    target: STATE.exportTarget,
    task,
    max_files: 12,
  });
  if (!res.ok) {
    $("exportPreview").textContent = res.error || "Could not generate agent context.";
    $("tokEst").textContent = "—";
    $("previewMeta").textContent = res.code || "Export failed";
    toast(res.error || "Agent export failed", "error");
    return;
  }
  $("exportPreview").textContent = res.text;
  $("tokEst").textContent = res.estimated_tokens;
  $("previewMeta").textContent = `${res.target} · ${res.confidence} · ~${res.estimated_tokens} tokens`;
  STATE._exportText = res.text;
  STATE._agentExport = res;
  STATE._agentExportTask = task;
  toast(`Generated ${EXPORT_TARGET_LABEL[res.target] || res.target} context`, "success");
}

async function copyForTarget(target) {
  STATE.exportTarget = target;
  if ($("segTarget")) {
    $("segTarget").querySelectorAll("button").forEach(b => b.classList.toggle("active", b.dataset.v === target));
  }
  const task = agentTaskText();
  if (!task) {
    toast("Describe the task first", "error");
    if ($("agentTask")) $("agentTask").focus();
    return;
  }
  if (!STATE._agentExport || STATE._agentExport.target !== target || STATE._agentExportTask !== task) {
    await generateAgentExport();
  }
  if (STATE._exportText) copyText(STATE._exportText, `Copied ${EXPORT_TARGET_LABEL[target] || target} context`);
}

async function loadClaudeIntegration() {
  if (!requireAtlasAccess("Claude integration")) return;
  const res = await api("/api/integrations/claude/config");
  const box = $("claudeMcpConfig");
  if (box) {
    box.style.display = "block";
    box.textContent = res.copyable_json || JSON.stringify(res.snippet || {}, null, 2);
  }
  STATE._claudeMcpConfig = res.copyable_json || JSON.stringify(res.snippet || {}, null, 2);
  if (!res.ok) {
    toast(res.error || "Claude config unavailable", "error");
    return;
  }
  const status = res.atlas_configured ? "Atlas is already in Claude Desktop config." : `Claude config: ${res.config_path}`;
  $("previewMeta").textContent = status;
  if (!res.atlas_configured && res.can_auto_write && confirm("Write Atlas MCP config to Claude Desktop now? Existing MCP servers will be preserved.")) {
    const written = await api("/api/integrations/claude/write-config", "POST", { confirm: true });
    if (written.ok) toast("Claude MCP config updated. Restart Claude Desktop to load Atlas.", "success");
    else toast(written.error || "Could not write Claude config", "error");
    await loadClaudeIntegration();
  } else {
    toast(res.atlas_configured ? "Claude MCP config found" : "Claude MCP config ready to copy");
  }
}

async function copyClaudeMcpConfig() {
  if (!STATE._claudeMcpConfig) await loadClaudeIntegration();
  if (STATE._claudeMcpConfig) copyText(STATE._claudeMcpConfig, "Claude MCP config copied");
}

async function testClaudeMcp() {
  if (!requireAtlasAccess("MCP test")) return;
  const res = await api("/api/integrations/claude/test", "POST", {});
  if (!res.ok) {
    toast(res.error || "MCP test failed", "error");
    return;
  }
  $("previewMeta").textContent = `MCP tools: ${res.tool_count}`;
  toast(`MCP test passed (${res.tool_count} tools)`, "success");
}

async function writeCursorRule() {
  if (!requireAtlasAccess("Cursor rule")) return;
  const res = await api("/api/integrations/cursor/write-rule", "POST", { task: agentTaskText() });
  if (res.ok) toast(`Cursor rule updated: ${res.path}`, "success");
  else toast(res.error || "Could not write Cursor rule", "error");
}

async function writeClaudeCodeBlock() {
  if (!requireAtlasAccess("Claude Code block")) return;
  const res = await api("/api/integrations/claude-code/write-managed-block", "POST", { task: agentTaskText() });
  if (res.ok) toast(`CLAUDE.md updated: ${res.path}`, "success");
  else toast(res.error || "Could not update CLAUDE.md", "error");
}
async function copyExport() {
  if (!requireAtlasAccess("Copy/export")) return;
  if (STATE._exportText) copyText(STATE._exportText, `Copied ${STATE.exportPacket} context for ${STATE.exportTarget}`);
  else toast("Nothing to copy");
}
function saveExport() {
  if (!STATE._exportText) { toast("Nothing to save"); return; }
  const blob = new Blob([STATE._exportText], { type: "text/plain" });
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
  a.download = `atlas_context_${STATE.exportTarget}_${STATE.exportPacket}.txt`; a.click(); toast("Prompt saved ✓");
}

/* ---------------- Boot (deferred until authenticated) ---------------- */
let _atlasAppBooted = false;
let _atlasAppWired = false;
let _atlasBootPromise = null;
let _atlasBootRetryTimer = null;

function wireAtlasApp() {
  if (_atlasAppWired) return;
  _atlasAppWired = true;
  updateWorkflowToolbars();
  ensureSuggestDelegation();
  wireSeg("segTarget", "exportTarget"); wireSeg("segPacket", "exportPacket");
  $("askInput").addEventListener("keydown", e => { if (e.key === "Enter") sendCopilotQuestion(); }); // plain Enter and Ctrl/Cmd+Enter both submit
  $("repoPath").addEventListener("keydown", e => { if (e.key === "Enter") validateRepoPath(true); });
  ["scopeMode", "scopeFolder", "scopeInclude", "scopeExclude", "manualMassiveMode"].forEach(id => {
    const el = $(id);
    if (!el) return;
    el.addEventListener("change", () => validateRepoPath(false));
  });
}

async function bootAtlasApp() {
  if (_atlasAppBooted) return true;
  if (_atlasBootPromise) return _atlasBootPromise;
  wireAtlasApp();
  _atlasBootPromise = (async () => {
    try {
      await requestAtlasRuntimeIdentity();
      const h = await api("/api/health");
      STATE.homeHealth = h;
      updateTelemetryWarning(h);
      applyBillingNav(!!h.billing_ui_enabled, true);
      if (h.billing_ui_enabled) {
        try {
          const me = await api("/api/usage/me");
          applyBillingNav(true, !!(me.user && me.user.role === "admin"));
        } catch (e) {}
      }
      if (h.persistence?.resume_card) renderResumeCard(h.persistence.resume_card);
      if (h.repository_open || h.persistence?.restored) {
        unlockNav();
        updateScanBtnState(true);
        STATE.summary = await api("/api/repositories/current/summary", "GET", undefined, { requireOk: true });
        updateTelemetryWarning(STATE.summary);
        updateRepoChip(h.repo_name || STATE.summary?.repo_name, h.demo_mode);
        updateMassiveBadge(!!STATE.summary?.massive_mode);
        if (STATE.summary?.ok) {
          document.body.classList.remove("atlas-no-repo");
          renderResumeCard(null);
        }
      }
      _atlasAppBooted = true;
      refreshHomeExperience();
      loadRecent();
      showScanPanel(null);
      const hash = (location.hash || "").replace(/^#\/?/, "").toLowerCase();
      const pathTail = (location.pathname || "").split("/").pop().toLowerCase();
      if (hash === "hn" || pathTail === "hn") go("hn");
      return true;
    } catch (_error) {
      if (!_atlasBootRetryTimer) {
        _atlasBootRetryTimer = window.setTimeout(() => {
          _atlasBootRetryTimer = null;
          bootAtlasApp();
        }, 1200);
      }
      return false;
    } finally {
      _atlasBootPromise = null;
    }
  })();
  return _atlasBootPromise;
}
window.bootAtlasApp = bootAtlasApp;
document.addEventListener("atlas:authenticated", bootAtlasApp);
document.addEventListener("atlas:repository-invalidated", (event) => {
  // "history" invalidations only mean new history entries exist; wiping the
  // just-rendered workflow result here would erase every Impact/Plan/Debug
  // report the moment it completes. Only repository-scope changes clear them.
  if (event?.detail?.reason === "history") return;
  clearWorkflowInvestigationState();
});
document.addEventListener("atlas:repository-state-changed", () => {
  ["build", "investigate", "impact"].forEach((view) => {
    renderWorkflowContextLine(view);
    if (!workflowResultMatchesRepository(view)) renderWorkflowEmptyState(view);
  });
});
window.clearWorkflowInvestigationState = clearWorkflowInvestigationState;
window.resetViewScroll = resetViewScroll;
