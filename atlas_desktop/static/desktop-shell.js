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
    return ["claude", "cursor", "codex"].filter((key) => status[key]?.connected || status.connections?.clients?.[key]?.connected);
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

  function renderGlobalReadinessActions(html) {
    const readiness = byId("globalReadiness");
    if (!readiness) return;
    let actions = byId("globalReadinessActions");
    if (!actions && typeof document.createElement === "function") {
      actions = document.createElement("div");
      actions.id = "globalReadinessActions";
      actions.className = "global-readiness-actions";
      readiness.appendChild(actions);
    }
    if (!actions) return;
    actions.innerHTML = html || "";
    if (typeof actions.querySelector === "function") {
      actions.querySelector("[data-global-retry]")?.addEventListener("click", () => updateGlobalStatus(), { once: true });
      actions.querySelector("[data-global-diagnostics]")?.addEventListener("click", () => go("diagnostics"), { once: true });
    }
  }

  async function updateGlobalStatus() {
    const readiness = byId("globalReadiness");
    const label = byId("globalReadinessLabel");
    if (!readiness || !label) return;

    let health = null;
    try {
      health = await api("/api/health", "GET", undefined, { optional: true });
    } catch (_error) {
      health = null;
    }

    const runtimeHealthy = !!(health && health.ok && health.product === "ATLAS");
    if (!runtimeHealthy) {
      readiness.dataset.state = "error";
      label.textContent = "Atlas stopped responding. Your repository was not changed.";
      renderGlobalReadinessActions(
        '<button type="button" class="btn ghost tiny" data-global-retry>Retry</button>'
        + '<button type="button" class="btn ghost tiny" data-global-diagnostics>Open diagnostics</button>'
      );
      return;
    }

    renderGlobalReadinessActions("");

    let summary = (window.STATE && STATE.summary && STATE.summary.ok) ? STATE.summary : null;
    if (!summary) {
      try {
        const fetched = await api("/api/repositories/current/summary", "GET", undefined, { optional: true });
        if (fetched && fetched.ok) summary = fetched;
      } catch (_error) {}
    }

    if (window.AtlasRepositoryState) {
      AtlasRepositoryState.publish({ summary, health, trust: shell.trustValue });
    }

    if (!summary || !summary.ok) {
      readiness.dataset.state = "idle";
      label.textContent = "No repository loaded";
      return;
    }

    const card = health?.persistence?.resume_card;
    const startupFresh = card?.freshness_status === "fresh" && card?.validation_status === "valid";
    const trust = shell.trustValue || (startupFresh ? { fresh: true, user_trust_label: "Fresh" } : null);
    if (!trust) scheduleTrustCheck();
    if (!trust) {
      readiness.dataset.state = "neutral";
      label.textContent = "Checking memory";
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
    return `<tr data-file-path="${escapeHtml(path)}" tabindex="0">
      <td><strong>${escapeHtml(node.label || path)}</strong><span class="table-path">${escapeHtml(path)}</span></td>
      <td>${number(relationships)} <span class="muted">(${number(node.fan_in || 0)} in / ${number(node.fan_out || 0)} out)</span></td>
      <td>${statusPill(risk ? risk.toFixed(1) : "Low", risk >= 10 ? "warning" : risk >= 6 ? "attention" : "ready")}</td>
      <td><button class="btn ghost small inspect-file inspect-inline" type="button" data-target="${escapeHtml(path)}" aria-label="Inspect ${escapeHtml(path)}">›</button></td>
    </tr>`;
  }

  function setFilesSelection(path) {
    const grid = document.querySelector("#view-files .files-workbench-grid");
    document.querySelectorAll("#filesTableBody tr[data-file-path]").forEach((row) => {
      row.classList.toggle("is-selected", row.dataset.filePath === path);
    });
    if (grid) grid.classList.toggle("has-selection", !!path);
  }

  function bindFileRows() {
    document.querySelectorAll("#filesTableBody tr[data-file-path]").forEach((row) => {
      const open = () => inspectFile(row.dataset.filePath || "");
      row.addEventListener("click", (event) => {
        if (event.target.closest("button")) return;
        open();
      });
      row.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          open();
        }
      });
    });
    document.querySelectorAll(".inspect-file[data-target]").forEach((button) => {
      button.addEventListener("click", (event) => {
        event.stopPropagation();
        inspectFile(button.dataset.target || "");
      });
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
    setFilesSelection(target);
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

  function renderDiagnosticCard(title, state, label, details) {
    const visual = state === "ready" ? "ready" : (state === "error" ? "warning" : (state === "neutral" ? "neutral" : "warning"));
    return `<article class="diagnostic-card" data-state="${visual}" data-component-state="${escapeHtml(state)}">
      <div class="diagnostic-card-head"><h2>${escapeHtml(title)}</h2>${statusPill(label, visual)}</div>
      <p>${escapeHtml(text(details))}</p>
    </article>`;
  }

  function activeRepositorySummary() {
    const stateSummary = window.STATE && STATE.summary;
    if (stateSummary && stateSummary.ok) return stateSummary;
    return null;
  }

  async function refreshDiagnostics(options = { force: true }) {
    const summaryHost = byId("diagnosticsSummary");
    const grid = byId("diagnosticsGrid");
    const report = byId("diagnosticsReport");
    if (!summaryHost || !grid || !report) return;
    summaryHost.innerHTML = `${statusPill("Running", "neutral")} Checking local services and persisted state…`;

    const fetchOptional = async (path, extra) => {
      try { return await api(path, "GET", undefined, Object.assign({ optional: true }, extra || {})); }
      catch (_error) { return null; }
    };

    const [health, diagnostics, startup, selfTest, mcp] = await Promise.all([
      fetchOptional("/api/health"),
      fetchOptional("/api/system/diagnostics", { force: options.force === true }),
      fetchOptional("/api/system/startup-status"),
      fetchOptional("/api/system/self-test"),
      fetchOptional("/api/integrations/mcp/status"),
    ]);

    const repoSummary = activeRepositorySummary();
    const memory = (diagnostics && diagnostics.trust_integrity) || {};
    const scan = (diagnostics && diagnostics.scan_statistics) || {};
    const moduleCount = Number(repoSummary?.module_count ?? scan.module_count ?? 0);
    const edgeCount = Number(repoSummary?.dependency_edges ?? scan.dependency_edges ?? 0);
    const fileCount = Number(repoSummary?.file_count ?? scan.file_count ?? 0);
    const hasRepo = !!(repoSummary && repoSummary.ok);
    const scanStale = !!(memory.scan_stale || shell.trustValue?.scan_stale || shell.trustValue?.fresh === false);
    const scanInProgress = document.body.classList.contains("atlas-scan-active");

    const runtimeHealthy = !!(health && health.ok && health.product === "ATLAS");
    const runtimeDegraded = runtimeHealthy && !!(startup && startup.ok && startup.startup && !startup.startup.ready);
    const runtimeState = runtimeHealthy ? (runtimeDegraded ? "warning" : "ready") : "warning";
    const runtimeLabel = runtimeHealthy ? (runtimeDegraded ? "Degraded" : "Healthy") : "Unavailable";
    const runtimeDetails = runtimeHealthy
      ? (health.version ? `Atlas ${health.version}` : "Local runtime responding")
      : "Start Atlas or retry the local runtime";

    let indexState = "warning";
    let indexLabel = "Unavailable";
    let indexDetails = "Load or scan a repository";
    if (hasRepo) {
      if (scanInProgress) {
        indexState = "neutral";
        indexLabel = "Scanning";
        indexDetails = "Repository scan in progress";
      } else if (scanStale) {
        indexState = "warning";
        indexLabel = "Stale";
        indexDetails = `${number(moduleCount)} modules · ${number(edgeCount)} dependencies · rescan recommended`;
      } else {
        indexState = "ready";
        indexLabel = "Ready";
        indexDetails = `${number(moduleCount)} modules · ${number(edgeCount)} dependencies · ${number(fileCount)} files`;
      }
    }

    const memoryRestored = !!(health && health.persistence && health.persistence.ok && health.persistence.restored);
    const memoryVerified = memory.memory_persistence_status === "ok" || memoryRestored;
    let memoryState = "warning";
    let memoryLabel = "Unavailable";
    let memoryDetails = "No signed memory for the active repository";
    if (hasRepo) {
      if (memoryVerified && !scanStale) {
        memoryState = "ready";
        memoryLabel = "Ready";
        memoryDetails = memoryRestored ? "Restored from local storage" : "Signed memory available";
      } else if (scanStale) {
        memoryState = "warning";
        memoryLabel = "Stale";
        memoryDetails = "Repository changed since the last scan";
      } else if (memoryVerified) {
        memoryState = "ready";
        memoryLabel = "Ready";
        memoryDetails = "Signed memory available";
      }
    }

    const installerReady = !!(selfTest && selfTest.ok && selfTest.ready);
    const installerChecks = list(selfTest?.checks);
    const installerPassed = installerChecks.filter((item) => item.ok).length;
    const installerState = installerReady ? "ready" : (selfTest ? "warning" : "neutral");
    const installerLabel = installerReady ? "Verified" : (selfTest ? "Warning" : "Unknown");
    const installerDetails = selfTest
      ? `${installerPassed}/${Math.max(installerChecks.length, 1)} runtime checks passed`
      : "Runtime integrity not checked yet";

    const agents = connectedAgents(mcp);
    let agentState = "neutral";
    let agentLabel = "Not connected";
    let agentDetails = "No coding agent currently has an active Atlas MCP session";
    if (mcp && mcp.ok) {
      if (agents.length === 3) {
        agentState = "ready";
        agentLabel = "Connected";
        agentDetails = "Claude, Cursor, and Codex are actively connected";
      } else if (agents.length > 0) {
        agentState = "neutral";
        agentLabel = "Partially connected";
        agentDetails = `${agents.length} of 3 agents currently connected`;
      } else {
        agentState = "neutral";
        agentLabel = "Not connected";
        agentDetails = "Configure and restart Claude, Cursor, or Codex to connect";
      }
    } else if (mcp) {
      agentState = "warning";
      agentLabel = "Error";
      agentDetails = "MCP status could not be read";
    }

    const components = [
      { title: "Local runtime", state: runtimeState, label: runtimeLabel, details: runtimeDetails, degraded: runtimeState !== "ready" },
      { title: "Repository index", state: indexState, label: indexLabel, details: indexDetails, degraded: indexState === "warning" },
      { title: "Persistent memory", state: memoryState, label: memoryLabel, details: memoryDetails, degraded: memoryState === "warning" },
      { title: "Installer runtime integrity", state: installerState, label: installerLabel, details: installerDetails, degraded: installerState === "warning" },
      { title: "Agent configuration", state: agentState, label: agentLabel, details: agentDetails, degraded: agentState === "warning" },
    ];
    const degradedCount = components.filter((item) => item.degraded).length;
    const unavailable = !runtimeHealthy;

    if (unavailable) {
      summaryHost.innerHTML = `${statusPill("Unavailable", "warning")} Atlas runtime is unavailable.`;
    } else if (degradedCount === 0) {
      summaryHost.innerHTML = `${statusPill("Ready", "ready")} Atlas is ready.`;
    } else {
      summaryHost.innerHTML = `${statusPill("Attention", "warning")} Atlas needs attention. ${degradedCount} component${degradedCount === 1 ? " is" : "s are"} degraded.`;
    }

    grid.innerHTML = components.map((item) => renderDiagnosticCard(item.title, item.state, item.label, item.details)).join("");
    shell.diagnostics = {
      generated_at: new Date().toISOString(),
      health,
      diagnostics,
      startup,
      self_test: selfTest,
      mcp: { ok: !!(mcp && mcp.ok), executable_exists: !!(mcp && mcp.executable_exists), configured_agents: agents },
      repository_summary: repoSummary,
      degraded_count: degradedCount,
    };
    report.textContent = JSON.stringify(shell.diagnostics, null, 2);
    updateGlobalStatus();
  }

  function agentVerificationState(key, data) {
    if (data?.connected || data?.connection?.connected) return "connected";
    if (data?.atlas_configured) return "configured";
    return "not_configured";
  }

  async function renderAgents() {
    const host = byId("agentsHost");
    const setup = byId("mcpSetupSection");
    const status = byId("agentsStatusSummary");
    if (host && setup && setup.parentElement !== host) host.appendChild(setup);
    if (!status) return;
    status.innerHTML = `${statusPill("Checking", "neutral")} Reading local MCP configuration…`;
    const result = await atlasMcpSetup.loadStatus(true);
    const connected = connectedAgents(result);
    const configured = ["claude", "cursor", "codex"].filter((key) => agentVerificationState(key, result && result[key]) !== "not_configured");
    const repository = window.STATE && STATE.summary;
    const contextReady = !!(repository && repository.ok);
    // Lead with the live connection state; configuration count is secondary.
    status.innerHTML = result && result.ok
      ? `${statusPill(connected.length ? "Connected" : "Not connected", connected.length ? "ready" : "neutral")} Connected clients: ${connected.length}. Configured clients: ${configured.length}. Available MCP tools: 18. Transport: Local stdio.${
          contextReady ? ` Repository context: ${escapeHtml(repository.repo_name || "active")}.` : " Load a repository for MCP context."
        }`
      : `${statusPill("Error", "warning")} MCP status could not be read. Open Diagnostics for details.`;
  }

  async function renderSettings() {
    const account = byId("settingsAccountState");
    const facts = byId("settingsStorageFacts");
    const advanced = byId("settingsAdvancedFacts");
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
    ]);
    if (advanced) {
      const commit = product && product.build_commit;
      advanced.innerHTML = factRows([
        ["Build commit", commit && commit !== "unknown" ? commit : "Unavailable"],
        ["Build date", product && product.build_date],
      ]);
    }
    // Load the current analytics preference into the toggle from the backend.
    const toggle = byId("analyticsOptToggle");
    const stateEl = byId("analyticsToggleState");
    if (toggle) {
      try {
        const pref = await api("/api/analytics/preferences", "GET", undefined, { optional: true });
        const optedOut = !!(pref && pref.opted_out);
        toggle.checked = !optedOut;
        if (stateEl) stateEl.textContent = optedOut
          ? "Analytics is off. No usage events are shared from this installation."
          : "Sharing anonymous usage events. You can turn this off anytime.";
      } catch (e) { /* preference read must never break Settings */ }
    }
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
    document.addEventListener("atlas:repository-state-changed", () => {
      updateGlobalStatus();
      if (window.atlasWorkbench && typeof window.atlasWorkbench.syncSidebarFromState === "function") {
        window.atlasWorkbench.syncSidebarFromState();
      }
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
