(function () {
  "use strict";

  const shell = {
    files: [],
    diagnostics: null,
    readinessTimer: null,
    trustTimer: null,
    trustPromise: null,
    trustValue: null,
    memory: {
      state: "idle",
      generation: 0,
      repositoryKey: "",
      controller: null,
      data: null,
      lastError: null,
    },
    initialized: false,
  };

  const byId = (id) => document.getElementById(id);
  const list = (value) => Array.isArray(value) ? value : [];
  const text = (value, fallback = "—") => {
    if (value === null || value === undefined || value === "") return fallback;
    return String(value);
  };
  const number = (value) => Number.isFinite(Number(value)) ? Number(value).toLocaleString() : "—";
  const yesNo = (value) => value ? "Yes" : "No";
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[char]);

  function statusPill(label, state) {
    return `<span class="state-label" data-state="${escapeHtml(state || "neutral")}">${escapeHtml(label)}</span>`;
  }

  function factRows(rows) {
    return rows.map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(text(value))}</dd></div>`).join("");
  }

  function emptyState(message) {
    return `<div class="technical-empty">${escapeHtml(message)}</div>`;
  }

  function connectedAgents(status) {
    if (!status || !status.ok) return [];
    return ["claude", "cursor", "codex"].filter((key) => status[key] && status[key].atlas_configured);
  }

  function scheduleTrustCheck(delay = 6000) {
    if (shell.trustValue || shell.trustPromise || shell.trustTimer || document.hidden) return;
    shell.trustTimer = window.setTimeout(() => {
      shell.trustTimer = null;
      const request = typeof window.requestAtlasTrustStatus === "function"
        ? window.requestAtlasTrustStatus()
        : api("/api/repositories/current/trust-status");
      shell.trustPromise = request;
      request.then((value) => {
        if (!value || !value.ok) return;
        shell.trustValue = value;
        updateGlobalStatus();
        try { document.dispatchEvent(new CustomEvent("atlas:trust-status", { detail: value })); } catch (_error) {}
      }).catch(() => null).finally(() => {
        if (shell.trustPromise === request) shell.trustPromise = null;
      });
    }, delay);
  }

  async function updateGlobalStatus() {
    const readiness = byId("globalReadiness");
    const label = byId("globalReadinessLabel");
    if (!readiness || !label) return;

    const identityRequest = typeof window.requestAtlasRuntimeIdentity === "function"
      ? window.requestAtlasRuntimeIdentity()
      : Promise.reject(Object.assign(new Error("Atlas runtime handshake unavailable"), { kind: "identity_mismatch" }));
    const summaryRequest = (window.STATE && STATE.summary && STATE.summary.ok)
      ? Promise.resolve(STATE.summary)
      : api("/api/repositories/current/summary");
    const [identityResult, healthResult, summaryResult] = await Promise.allSettled([
      identityRequest,
      api("/api/health"),
      summaryRequest,
    ]);
    const identity = identityResult.status === "fulfilled" ? identityResult.value : null;
    const health = healthResult.status === "fulfilled" ? healthResult.value : null;
    if (
      identityResult.status === "rejected"
      || !identity
      || identity.product !== "Atlas Desktop"
      || identity.protocol !== "atlas-desktop-runtime-v1"
      || Number(identity.port) !== Number(new URL(window.location.origin).port)
      || healthResult.status === "rejected"
      || !health
      || !health.ok
      || health.product !== "ATLAS"
    ) {
      const reason = identityResult.status === "rejected"
        ? identityResult.reason
        : healthResult.status === "rejected" ? healthResult.reason : null;
      readiness.dataset.state = "error";
      label.textContent = reason && reason.kind === "timeout" ? "Runtime timed out" : "Backend unavailable";
      return;
    }
    if (summaryResult.status === "rejected") {
      readiness.dataset.state = "warning";
      label.textContent = summaryResult.reason && summaryResult.reason.kind === "timeout" ? "Repository timed out" : "Repository unavailable";
      return;
    }
    const summary = summaryResult.value;
    if (!summary || !summary.ok) {
      readiness.dataset.state = "idle";
      label.textContent = "Select a repository";
      return;
    }
    const card = health?.persistence?.resume_card;
    const startupFresh = card?.freshness_status === "fresh" && card?.validation_status === "valid";
    const trust = shell.trustValue || (startupFresh ? { fresh: true, user_trust_label: "Fresh" } : null);
    if (!trust) scheduleTrustCheck();
    if (!trust) {
      readiness.dataset.state = "neutral";
      label.textContent = "Verifying memory";
      return;
    }
    const stale = trust && (trust.scan_stale || trust.fresh === false || trust.stale_status);
    readiness.dataset.state = stale ? "warning" : "ready";
    label.textContent = stale ? "Repository changed" : "Memory current";
  }

  async function renderMemoryLegacy() {
    const status = byId("memoryStatusStrip");
    const freshness = byId("memoryFreshnessLabel");
    const facts = byId("memoryFacts");
    const evidence = byId("memoryEvidence");
    const history = byId("memoryHistory");
    if (!status || !facts || !evidence || !history) return;

    status.innerHTML = `${statusPill("Checking", "neutral")} Reading signed local repository memory…`;
    const memoryRequests = await Promise.allSettled([
      api("/api/repositories/current/summary"),
      api("/api/history"),
      Promise.resolve(null),
      api("/api/health"),
    ]);
    const [summaryResult, historyResult, diagnosticsResult, healthResult] = memoryRequests;
    if (summaryResult.status === "rejected") {
      const timedOut = summaryResult.reason && summaryResult.reason.kind === "timeout";
      status.innerHTML = `${statusPill(timedOut ? "Timed out" : "Unavailable", "warning")} Repository memory could not be read from the local runtime.`;
      freshness.textContent = timedOut ? "Timed out" : "Unavailable";
      freshness.dataset.state = "warning";
      facts.innerHTML = factRows([["Repository", "Endpoint unavailable"], ["Persistence", "Stored locally"]]);
      evidence.innerHTML = emptyState("Repository evidence is temporarily unavailable. Retry Memory.");
      history.innerHTML = emptyState("Memory history is temporarily unavailable.");
      return;
    }
    const summary = summaryResult.value;
    const historyData = historyResult.status === "fulfilled" ? historyResult.value : null;
    const diagnostics = diagnosticsResult.status === "fulfilled" ? diagnosticsResult.value : null;
    const healthPayload = healthResult.status === "fulfilled" ? healthResult.value : null;

    if (!summary || !summary.ok) {
      status.innerHTML = `${statusPill("No repository", "warning")} Scan or resume a repository to create project memory.`;
      freshness.textContent = "Unavailable";
      freshness.dataset.state = "warning";
      facts.innerHTML = factRows([["Repository", "Not selected"], ["Persistence", "Local only"]]);
      evidence.innerHTML = emptyState("Evidence will appear after the first successful scan.");
      history.innerHTML = emptyState("No repository history is available yet.");
      return;
    }

    const card = healthPayload?.persistence?.resume_card;
    const startupFresh = card?.freshness_status === "fresh" && card?.validation_status === "valid";
    const trust = shell.trustValue || (startupFresh ? { fresh: true, user_trust_label: "Fresh" } : null);
    scheduleTrustCheck();

    const isStale = !!(trust && (trust.scan_stale || trust.fresh === false || trust.stale_status));
    const trustLabel = trust ? text(trust.user_trust_label || trust.label, isStale ? "Needs refresh" : "Fresh") : "Verifying";
    const persistence = diagnostics && diagnostics.trust_integrity && diagnostics.trust_integrity.memory_persistence_status;
    const restored = !!(healthPayload && healthPayload.persistence && healthPayload.persistence.ok && healthPayload.persistence.restored);
    status.innerHTML = `${statusPill(trustLabel, trust ? (isStale ? "warning" : "ready") : "neutral")} ${trust ? (isStale ? "Repository files changed after the stored scan. Refresh before relying on downstream analysis." : "Repository memory matches the last verified scan and is ready for analysis.") : "Live repository freshness is still being checked."}`;
    freshness.textContent = trustLabel;
    freshness.dataset.state = trust ? (isStale ? "warning" : "ready") : "neutral";

    const coverage = summary.evidence_coverage || {};
    const health = summary.graph_health || {};
    facts.innerHTML = factRows([
      ["Repository", summary.repo_name],
      ["Indexed files", number(summary.file_count)],
      ["Modules", number(summary.module_count)],
      ["Dependencies", number(summary.dependency_edges)],
      ["Indexed symbols", number(coverage.symbol_count)],
      ["Files with symbol evidence", number(coverage.files_with_symbols)],
      ["Graph reliability", health.label || summary.graph_quality || "Unknown"],
      ["Signed persistence", restored ? "Restored and verified" : (persistence === "ok" ? "Verified locally" : (persistence || "Not reported"))],
    ]);

    const evidenceItems = [];
    list(summary.subsystems).slice(0, 8).forEach((item) => {
      const isName = typeof item === "string";
      evidenceItems.push({
        title: isName ? item : (item.name || item.label || item.subsystem || "Subsystem"),
        meta: isName ? "Indexed architectural subsystem" : `${number(item.module_count || item.modules || item.file_count || item.production_files)} indexed modules or files`,
      });
    });
    list(summary.top_boundaries).slice(0, 6).forEach((item) => evidenceItems.push({
      title: item.label || item.name || item.path || item.source || "Dependency boundary",
      meta: item.reason || item.explanation || item.target || "High-value architectural boundary",
    }));
    evidence.innerHTML = evidenceItems.length
      ? evidenceItems.map((item) => `<article class="technical-row"><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.meta)}</span></article>`).join("")
      : `<article class="technical-row"><strong>${number(coverage.symbol_count)} symbols indexed</strong><span>${escapeHtml(health.notice || "Atlas has structural repository evidence available.")}</span></article>`;

    const items = list(historyData && historyData.items);
    history.innerHTML = items.length
      ? items.slice(0, 12).map((item) => `<article class="technical-row"><strong>${escapeHtml(item.title || item.request_text || item.workflow_type || "Analysis")}</strong><span>${escapeHtml(item.created_at || item.updated_at || "Saved locally")}</span></article>`).join("")
      : emptyState("No saved investigations or plans for this repository yet.");
  }

  function memoryRepositoryKey(summary = window.STATE && STATE.summary) {
    return text(summary && (summary.repo_id || summary.repo_path || summary.repo_name), "");
  }

  function memoryViewIsActive() {
    const active = document.querySelector(".view.active");
    return !active || active.id === "view-memory";
  }

  function memoryRequestIsCurrent(generation, repositoryKey) {
    if (generation !== shell.memory.generation || !memoryViewIsActive()) return false;
    const currentKey = memoryRepositoryKey();
    return !repositoryKey || !currentKey || currentKey === repositoryKey;
  }

  function setMemoryState(state, generation, detail = {}) {
    if (generation !== shell.memory.generation) return false;
    shell.memory.state = state;
    shell.memory.lastError = detail.error || null;
    const host = byId("memoryStatusStrip");
    if (host) host.dataset.memoryState = state;
    try { document.dispatchEvent(new CustomEvent("atlas:memory-state", { detail: { state, generation, ...detail } })); } catch (_error) {}
    return true;
  }

  function cancelMemoryRender(reason = "navigation", reset = false) {
    if (shell.memory.controller) shell.memory.controller.abort(reason);
    shell.memory.controller = null;
    shell.memory.generation += 1;
    if (reset) {
      shell.memory.state = "idle";
      shell.memory.repositoryKey = "";
      shell.memory.data = null;
      shell.memory.lastError = null;
    }
  }

  function paintMemorySnapshot(summary, historyData, healthPayload, liveTrust, generation) {
    const status = byId("memoryStatusStrip");
    const freshness = byId("memoryFreshnessLabel");
    const facts = byId("memoryFacts");
    const evidence = byId("memoryEvidence");
    const history = byId("memoryHistory");
    if (!status || !freshness || !facts || !evidence || !history || !summary || !summary.ok) return null;
    const card = healthPayload?.persistence?.resume_card;
    const startupFresh = card?.freshness_status === "fresh" && card?.validation_status === "valid";
    const trust = liveTrust || shell.trustValue || (startupFresh ? { fresh: true, user_trust_label: "Fresh" } : null);
    const isStale = !!(trust && (trust.scan_stale || trust.fresh === false || trust.stale_status || trust.trust_status?.fresh === false));
    const trustLabel = trust ? text(trust.user_trust_label || trust.label, isStale ? "Needs refresh" : "Fresh") : "Verifying";
    const restored = !!(healthPayload?.persistence?.ok && healthPayload?.persistence?.restored);
    const stableState = trust ? (isStale ? "loaded_review_needed" : "loaded_fresh") : "partial";
    setMemoryState(stableState, generation);
    status.innerHTML = `${statusPill(trustLabel, trust ? (isStale ? "warning" : "ready") : "neutral")} ${trust ? (isStale ? "Repository files changed after the stored scan. Refresh before relying on downstream analysis." : "Repository memory matches the last verified scan and is ready for analysis.") : "Signed facts are loaded. Live freshness can be retried without blocking Memory."}`;
    freshness.textContent = trustLabel;
    freshness.dataset.state = trust ? (isStale ? "warning" : "ready") : "neutral";

    const coverage = summary.evidence_coverage || {};
    const graphHealth = summary.graph_health || {};
    facts.innerHTML = factRows([
      ["Repository", summary.repo_name],
      ["Indexed files", number(summary.file_count)],
      ["Modules", number(summary.module_count)],
      ["Dependencies", number(summary.dependency_edges)],
      ["Indexed symbols", number(coverage.symbol_count)],
      ["Files with symbol evidence", number(coverage.files_with_symbols)],
      ["Graph reliability", graphHealth.label || summary.graph_quality || "Unknown"],
      ["Signed persistence", restored ? "Restored and verified" : "Verified locally"],
    ]);

    const evidenceItems = [];
    list(summary.subsystems).slice(0, 8).forEach((item) => {
      const isName = typeof item === "string";
      evidenceItems.push({
        title: isName ? item : (item.name || item.label || item.subsystem || "Subsystem"),
        meta: isName ? "Indexed architectural subsystem" : `${number(item.module_count || item.modules || item.file_count || item.production_files)} indexed modules or files`,
      });
    });
    list(summary.top_boundaries).slice(0, 6).forEach((item) => evidenceItems.push({
      title: item.label || item.name || item.path || item.source || "Dependency boundary",
      meta: item.reason || item.explanation || item.target || "High-value architectural boundary",
    }));
    evidence.innerHTML = evidenceItems.length
      ? evidenceItems.map((item) => `<article class="technical-row"><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.meta)}</span></article>`).join("")
      : `<article class="technical-row"><strong>${number(coverage.symbol_count)} symbols indexed</strong><span>${escapeHtml(graphHealth.notice || "Atlas has structural repository evidence available.")}</span></article>`;
    const items = list(historyData && historyData.items);
    history.innerHTML = items.length
      ? items.slice(0, 12).map((item) => `<article class="technical-row"><strong>${escapeHtml(item.title || item.request_text || item.workflow_type || "Analysis")}</strong><span>${escapeHtml(item.created_at || item.updated_at || "Saved locally")}</span></article>`).join("")
      : emptyState("No saved investigations or plans for this repository yet.");
    return stableState;
  }

  async function renderMemory(options = {}) {
    const status = byId("memoryStatusStrip");
    const freshness = byId("memoryFreshnessLabel");
    const facts = byId("memoryFacts");
    const evidence = byId("memoryEvidence");
    const history = byId("memoryHistory");
    if (!status || !freshness || !facts || !evidence || !history) return null;

    if (shell.memory.controller) shell.memory.controller.abort("superseded");
    const controller = typeof window.AbortController === "function"
      ? new window.AbortController()
      : { signal: undefined, abort() {} };
    const generation = ++shell.memory.generation;
    const initialKey = memoryRepositoryKey();
    shell.memory.controller = controller;
    const retained = shell.memory.data && shell.memory.repositoryKey === initialKey ? shell.memory.data : null;
    if (!retained) {
      setMemoryState("loading", generation);
      status.innerHTML = `${statusPill("Checking", "neutral")} Reading signed local repository memory...`;
    }

    const requestOptions = { signal: controller.signal, force: options.force === true };
    const optionalOptions = { ...requestOptions, optional: true };
    const summaryRequest = api("/api/repositories/current/summary", "GET", undefined, requestOptions);
    const historyRequest = api("/api/history", "GET", undefined, optionalOptions);
    const healthRequest = api("/api/health", "GET", undefined, optionalOptions);
    const trustRequest = typeof window.requestAtlasTrustStatus === "function"
      ? window.requestAtlasTrustStatus(optionalOptions)
      : api("/api/repositories/current/trust-status", "GET", undefined, optionalOptions);
    const optionalSettled = Promise.allSettled([historyRequest, healthRequest, trustRequest]);

    let summary;
    try {
      summary = await summaryRequest;
    } catch (error) {
      if (error && (error.kind === "cancelled" || error.name === "AbortError")) return null;
      if (!memoryRequestIsCurrent(generation, initialKey)) return null;
      if (retained) return paintMemorySnapshot(retained.summary, retained.history, retained.health, retained.trust, generation);
      const timedOut = error && error.kind === "timeout";
      setMemoryState("failed", generation, { error: error && error.message });
      status.innerHTML = `${statusPill(timedOut ? "Timed out" : "Unavailable", "warning")} Repository memory could not be read. <button class="btn small ghost" type="button" onclick="atlasDesktopShell.renderMemory({force:true})">Retry</button>`;
      freshness.textContent = timedOut ? "Timed out" : "Unavailable";
      freshness.dataset.state = "warning";
      facts.innerHTML = factRows([["Repository", "Endpoint unavailable"], ["Persistence", "Stored locally"]]);
      evidence.innerHTML = emptyState("Repository evidence is temporarily unavailable.");
      history.innerHTML = emptyState("Memory history is temporarily unavailable.");
      return "failed";
    }

    if (!memoryRequestIsCurrent(generation, initialKey)) return null;
    if (!summary || !summary.ok) {
      setMemoryState("idle", generation);
      status.innerHTML = `${statusPill("No repository", "warning")} Scan or resume a repository to create project memory.`;
      freshness.textContent = "Unavailable";
      freshness.dataset.state = "warning";
      facts.innerHTML = factRows([["Repository", "Not selected"], ["Persistence", "Local only"]]);
      evidence.innerHTML = emptyState("Evidence will appear after the first successful scan.");
      history.innerHTML = emptyState("No repository history is available yet.");
      return "idle";
    }

    const repositoryKey = memoryRepositoryKey(summary);
    if (window.STATE) window.STATE.summary = summary;
    shell.memory.repositoryKey = repositoryKey;
    shell.memory.data = {
      summary,
      history: retained && retained.history,
      health: retained && retained.health,
      trust: retained && retained.trust,
    };
    paintMemorySnapshot(summary, shell.memory.data.history, shell.memory.data.health, shell.memory.data.trust, generation);
    const settled = await optionalSettled;
    if (!memoryRequestIsCurrent(generation, repositoryKey)) return null;
    const historyData = settled[0].status === "fulfilled" ? settled[0].value : (retained && retained.history);
    const healthPayload = settled[1].status === "fulfilled" ? settled[1].value : (retained && retained.health);
    const liveTrust = settled[2].status === "fulfilled" && settled[2].value && settled[2].value.ok ? settled[2].value : null;
    if (liveTrust) shell.trustValue = liveTrust;
    const trust = liveTrust || shell.trustValue || (retained && retained.trust);
    shell.memory.data = { summary, history: historyData, health: healthPayload, trust };
    const state = paintMemorySnapshot(summary, historyData, healthPayload, trust, generation);
    shell.memory.controller = null;
    if (window.atlasWorkbench && typeof window.atlasWorkbench.renderMemoryWorkbench === "function") {
      window.atlasWorkbench.renderMemoryWorkbench({ summary, history: historyData, health: healthPayload, trust, generation }).catch(() => null);
    }
    return state;
  }

  function fileRow(node) {
    const path = node.path || node.name || node.label || node.id || "Unknown module";
    const relationships = Number(node.fan_in || node.importers_count || 0) + Number(node.fan_out || node.imported_modules_count || 0);
    const risk = Number(node.risk_score || 0);
    return `<tr>
      <td><strong>${escapeHtml(node.label || path)}</strong><span class="table-path">${escapeHtml(path)}</span></td>
      <td>${number(relationships)} <span class="muted">(${number(node.fan_in || 0)} in / ${number(node.fan_out || 0)} out)</span></td>
      <td>${statusPill(risk ? risk.toFixed(1) : "Low", risk >= 10 ? "warning" : risk >= 6 ? "attention" : "ready")}</td>
      <td><button class="btn ghost small inspect-file" type="button" data-target="${escapeHtml(path)}">Inspect</button></td>
    </tr>`;
  }

  function bindFileRows() {
    document.querySelectorAll(".inspect-file[data-target]").forEach((button) => {
      button.addEventListener("click", () => inspectFile(button.dataset.target || ""));
    });
  }

  function filterFiles() {
    const body = byId("filesTableBody");
    const count = byId("filesCount");
    const input = byId("filesSearch");
    if (!body) return;
    const query = (input && input.value || "").trim().toLowerCase();
    const filtered = shell.files.filter((node) => {
      const haystack = [node.path, node.name, node.label, node.id, node.subsystem].join(" ").toLowerCase();
      return !query || haystack.includes(query);
    });
    body.innerHTML = filtered.length ? filtered.map(fileRow).join("") : `<tr><td colspan="4">${emptyState("No indexed files match this filter.")}</td></tr>`;
    if (count) count.textContent = `${number(filtered.length)} of ${number(shell.files.length)}`;
    bindFileRows();
  }

  async function renderFiles() {
    const body = byId("filesTableBody");
    if (!body) return;
    body.innerHTML = `<tr><td colspan="4">${emptyState("Loading the repository index…")}</td></tr>`;
    const graph = await api("/api/repositories/current/graph?view=module");
    if (!graph || !graph.ok) {
      shell.files = [];
      body.innerHTML = `<tr><td colspan="4">${emptyState("Scan or resume a repository to browse files and symbols.")}</td></tr>`;
      const count = byId("filesCount");
      if (count) count.textContent = "No index";
      return;
    }
    shell.files = list(graph.nodes).slice().sort((a, b) => String(a.path || a.label || "").localeCompare(String(b.path || b.label || "")));
    filterFiles();
  }

  async function inspectFile(target) {
    const inspector = byId("filesInspector");
    if (!inspector || !target) return;
    inspector.innerHTML = `<h2 id="filesInspectorTitle">Inspector</h2><p class="muted">Loading ${escapeHtml(target)}…</p>`;
    const info = await api(`/api/repositories/current/module?target=${encodeURIComponent(target)}`);
    if (!info || !info.ok) {
      const node = shell.files.find((item) => (item.path || item.name || item.label || item.id) === target) || {};
      inspector.innerHTML = `<h2 id="filesInspectorTitle">${escapeHtml(node.label || target)}</h2>
        <p class="table-path">${escapeHtml(target)}</p>
        <dl class="fact-table compact">${factRows([
          ["Subsystem", node.subsystem], ["Incoming", number(node.fan_in)], ["Outgoing", number(node.fan_out)], ["Risk score", node.risk_score],
        ])}</dl>
        <p class="muted">Detailed symbol evidence is not available for this graph node, but dependency evidence remains available.</p>
        <div class="title-actions"><button class="btn primary" type="button" id="inspectImpactBtn">Trace impact</button><button class="btn ghost" type="button" id="inspectGraphBtn">Show in graph</button></div>`;
    } else {
      const module = info.module || info;
      const symbols = list(info.symbols || module.symbols);
      const importers = list(info.importers || module.importers);
      const imports = list(info.imports || info.dependencies || module.imports);
      inspector.innerHTML = `<h2 id="filesInspectorTitle">${escapeHtml(module.label || module.name || target)}</h2>
        <p class="table-path">${escapeHtml(module.path || target)}</p>
        <dl class="fact-table compact">${factRows([
          ["Subsystem", module.subsystem], ["Incoming", number(module.fan_in || importers.length)], ["Outgoing", number(module.fan_out || imports.length)], ["Symbols", number(symbols.length)], ["Risk score", module.risk_score],
        ])}</dl>
        <div class="section-heading"><h3>Indexed symbols</h3></div>
        <div class="technical-list">${symbols.length ? symbols.slice(0, 18).map((symbol) => `<article class="technical-row"><strong>${escapeHtml(symbol.name || symbol.label || symbol)}</strong><span>${escapeHtml(symbol.kind || symbol.type || "Symbol evidence")}</span></article>`).join("") : emptyState("No symbol records reported for this module.")}</div>
        <div class="title-actions"><button class="btn primary" type="button" id="inspectImpactBtn">Trace impact</button><button class="btn ghost" type="button" id="inspectGraphBtn">Show in graph</button></div>`;
    }
    byId("inspectImpactBtn")?.addEventListener("click", () => {
      go("impact");
      const input = byId("impactTarget");
      if (input) input.value = target;
    });
    byId("inspectGraphBtn")?.addEventListener("click", () => go("center"));
  }

  function renderDiagnosticCard(title, ok, details) {
    return `<article class="diagnostic-card" data-state="${ok ? "ready" : "warning"}">
      <div class="diagnostic-card-head"><h2>${escapeHtml(title)}</h2>${statusPill(ok ? "Pass" : "Review", ok ? "ready" : "warning")}</div>
      <p>${escapeHtml(text(details, ok ? "Available" : "Not available"))}</p>
    </article>`;
  }

  async function refreshDiagnostics(options = { force: true }) {
    const summary = byId("diagnosticsSummary");
    const grid = byId("diagnosticsGrid");
    const report = byId("diagnosticsReport");
    if (!summary || !grid || !report) return;
    summary.innerHTML = `${statusPill("Running", "neutral")} Checking local services and persisted state…`;
    const diagnosticRequests = await Promise.allSettled([
      api("/api/health"),
      api("/api/system/diagnostics", "GET", undefined, { force: options.force === true }),
      api("/api/system/startup-status"),
      api("/api/system/self-test"),
      api("/api/integrations/mcp/status"),
    ]);
    const [health, diagnostics, startup, selfTest, mcp] = diagnosticRequests.map((request) => request.status === "fulfilled" ? request.value : null);
    const requestFailures = diagnosticRequests.filter((request) => request.status === "rejected");
    const memory = diagnostics && diagnostics.trust_integrity || {};
    const scan = diagnostics && diagnostics.scan_statistics || {};
    const agents = connectedAgents(mcp);
    const memoryVerified = memory.memory_persistence_status === "ok" || !!(health && health.persistence && health.persistence.ok && health.persistence.restored);
    const startupReady = !!(startup && startup.ok && startup.startup && startup.startup.ready);
    const installerReady = !!(selfTest && selfTest.ok && selfTest.ready);
    const repositoryReady = !!(diagnostics && diagnostics.ok && !memory.scan_stale);
    const allOk = requestFailures.length === 0 && !!(health && health.ok) && startupReady && installerReady && repositoryReady && memoryVerified && !!(mcp && mcp.ok);
    summary.innerHTML = `${statusPill(allOk ? "Operational" : "Review needed", allOk ? "ready" : "warning")} ${allOk ? "The local backend, storage, index, and integration checks responded successfully." : "One or more local checks need attention. Review the report before recovery actions."}`;
    grid.innerHTML = [
      renderDiagnosticCard("Local backend", !!(health && health.ok), health && (health.version ? `Atlas ${health.version}` : health.status)),
      renderDiagnosticCard("Startup readiness", startupReady, startup && startup.startup && `${list(startup.startup.checks).filter((item) => item.ok).length} startup checks passed`),
      renderDiagnosticCard("Repository index", repositoryReady, scan.module_count !== undefined ? `${number(scan.module_count)} modules · ${number(scan.dependency_edges)} dependencies` : "No repository is currently indexed"),
      renderDiagnosticCard("Signed memory", memoryVerified, memoryVerified ? "Persisted repository state restored and verified" : memory.memory_persistence_error),
      renderDiagnosticCard("Installer runtime", installerReady, selfTest && `${list(selfTest.checks).filter((item) => item.ok).length} runtime checks passed`),
      renderDiagnosticCard("Agent configuration", !!(mcp && mcp.ok), agents.length ? `${agents.map((name) => name === "claude" ? "Claude" : name === "codex" ? "Codex" : "Cursor").join(", ")} configured` : "MCP configuration available; no agent reported configured"),
    ].join("");
    shell.diagnostics = { generated_at: new Date().toISOString(), request_failures: requestFailures.map((request) => text(request.reason && request.reason.message, "Request failed")), health, diagnostics, startup, self_test: selfTest, mcp: {
      ok: !!(mcp && mcp.ok), executable_exists: !!(mcp && mcp.executable_exists), configured_agents: agents,
    } };
    report.textContent = JSON.stringify(shell.diagnostics, null, 2);
    updateGlobalStatus();
  }

  async function renderAgents() {
    const host = byId("agentsHost");
    const setup = byId("mcpSetupSection");
    const status = byId("agentsStatusSummary");
    if (host && setup && setup.parentElement !== host) host.appendChild(setup);
    if (!status) return;
    status.innerHTML = `${statusPill("Checking", "neutral")} Reading local MCP configuration…`;
    const result = await atlasMcpSetup.loadStatus(true);
    const agents = connectedAgents(result);
    const repository = window.STATE && STATE.summary;
    const contextReady = !!(repository && repository.ok);
    status.innerHTML = result && result.ok
      ? `${statusPill(agents.length ? (contextReady ? "Connected" : "Configured — select a repository") : "Ready to connect", agents.length && contextReady ? "ready" : "neutral")} ${agents.length ? `${agents.length} coding agent${agents.length === 1 ? " is" : "s are"} configured to use Atlas MCP${contextReady ? ` with ${escapeHtml(repository.repo_name || "repository")} context.` : "; repository context is not active yet."}` : "Choose an agent below. Atlas will preserve its existing configuration and ask before writing."}`
      : `${statusPill("Unavailable", "warning")} MCP status could not be read. Open Diagnostics for details.`;
    if (result && result.ok && agents.length && contextReady) {
      status.innerHTML = status.innerHTML.replace(">Connected<", ">Configured<").replace(" context.", " context is ready.");
    }
  }

  async function renderSettings() {
    const account = byId("settingsAccountState");
    const facts = byId("settingsStorageFacts");
    if (!account || !facts) return;
    const [health, product] = await Promise.all([
      api("/api/health", "GET", undefined, { optional: true }),
      api("/api/product/config", "GET", undefined, { optional: true }),
    ]);
    let accountLabel = "Local mode";
    if (window.atlasAccounts) {
      if (atlasAccounts.isSignedIn && atlasAccounts.isSignedIn()) accountLabel = "Signed in";
      else if (atlasAccounts.isGuest && atlasAccounts.isGuest()) accountLabel = "Local guest session";
    }
    account.textContent = `${accountLabel}. Repository scans and memory remain available locally.`;
    const persistence = health && health.persistence || {};
    const dataDir = persistence.data_dir || persistence.storage || {};
    const trust = shell.trustValue || {};
    facts.innerHTML = factRows([
      ["Data directory", dataDir.path || persistence.path || "Managed local storage"],
      ["Environment override", yesNo(dataDir.override_env)],
      ["Memory persistence", persistence.ok ? "Verified" : "Available locally"],
      ["Repository changed", yesNo(trust.scan_stale || trust.fresh === false)],
      ["Version", product && product.version],
      ["Build commit", product && product.build_commit],
    ]);
  }

  function copyDiagnosticReport() {
    const report = byId("diagnosticsReport");
    if (!report) return;
    if (typeof window.copyText === "function") {
      window.copyText(report.textContent || "");
      if (typeof window.toast === "function") window.toast("Diagnostic report copied", "success");
      return;
    }
    navigator.clipboard?.writeText(report.textContent || "");
  }

  function enablePseudoControlKeyboard() {
    document.addEventListener("keydown", (event) => {
      const target = event.target && event.target.closest && event.target.closest('[role="button"]');
      if (!target || target.matches("button, a, input, select, textarea")) return;
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        target.click();
      }
    });
  }

  function syncDialogAccessibility() {
    const dialogs = Array.from(document.querySelectorAll('[role="dialog"]'));
    const appShell = byId("app-shell");
    const observer = new MutationObserver(() => {
      const visible = dialogs.find((dialog) => getComputedStyle(dialog).display !== "none" && !dialog.hidden);
      if (appShell) {
        if (visible) appShell.setAttribute("aria-hidden", "true");
        else appShell.removeAttribute("aria-hidden");
      }
    });
    dialogs.forEach((dialog) => observer.observe(dialog, { attributes: true, attributeFilter: ["style", "class", "hidden"] }));
  }

  function onViewChange(view) {
    if (view === "memory") renderMemory();
    else cancelMemoryRender("navigation");
    if (view === "files") renderFiles();
    if (view === "agents") renderAgents();
    if (view === "diagnostics") refreshDiagnostics({ force: false });
    if (view === "settings") renderSettings();
    updateGlobalStatus();
  }

  function init() {
    if (shell.initialized) return;
    shell.initialized = true;
    enablePseudoControlKeyboard();
    syncDialogAccessibility();
    const setup = byId("mcpSetupSection");
    const host = byId("agentsHost");
    if (setup && host) host.appendChild(setup);
    window.focusHomeAgentConnections = () => {
      go("agents");
      setTimeout(() => byId("mcpSetupTitle")?.focus(), 60);
    };
    document.addEventListener("atlas:viewchange", (event) => onViewChange(event.detail && event.detail.view));
    document.addEventListener("atlas:authenticated", updateGlobalStatus);
    document.addEventListener("atlas:repository-invalidated", () => {
      shell.trustValue = null;
      cancelMemoryRender("repository_switch", true);
    });
    document.addEventListener("atlas:trust-status", (event) => {
      const value = event.detail;
      if (!value || !value.ok) return;
      shell.trustValue = value;
      if (memoryViewIsActive() && shell.memory.data) {
        shell.memory.data.trust = value;
        paintMemorySnapshot(shell.memory.data.summary, shell.memory.data.history, shell.memory.data.health, value, shell.memory.generation);
      }
    });
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) updateGlobalStatus();
    });
    let wasAuthMode = document.body.classList.contains("auth-mode");
    new MutationObserver(() => {
      const isAuthMode = document.body.classList.contains("auth-mode");
      if (isAuthMode && !wasAuthMode) requestAnimationFrame(() => window.scrollTo(0, 0));
      wasAuthMode = isAuthMode;
    }).observe(document.body, { attributes: true, attributeFilter: ["class"] });
    updateGlobalStatus();
    shell.readinessTimer = window.setInterval(() => {
      if (!document.hidden) updateGlobalStatus();
    }, 30000);
    document.documentElement?.setAttribute("data-atlas-readiness-intervals", "1");
  }

  window.atlasDesktopShell = Object.assign(shell, {
    init,
    updateGlobalStatus,
    renderMemory,
    cancelMemoryRender,
    renderFiles,
    filterFiles,
    inspectFile,
    renderAgents,
    refreshDiagnostics,
    renderSettings,
    copyDiagnosticReport,
  });

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
