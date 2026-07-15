(function () {
  "use strict";

  const workbench = {
    summary: null,
    trust: null,
    graph: null,
    history: [],
    agents: null,
    memoryConcepts: [],
    selectedConcept: 0,
    homeRenderToken: 0,
    memoryRenderToken: 0,
    scheduledViews: new Map(),
    initialized: false,
  };

  const byId = (id) => document.getElementById(id);
  const list = (value) => {
    if (Array.isArray(value)) return value;
    if (value && typeof value !== "string" && typeof value[Symbol.iterator] === "function") return Array.from(value);
    return [];
  };
  const num = (value) => Number(value || 0).toLocaleString();
  const clean = (value, fallback = "") => {
    const text = String(value == null ? "" : value).trim();
    return text || fallback;
  };
  const escapeHtml = (value) => clean(value).replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]);
  const apiSafe = async (path) => {
    try { return await window.api(path); } catch (_error) { return null; }
  };
  const get = (path) => typeof window.api === "function" ? apiSafe(path) : Promise.resolve(null);
  const getTrust = () => {
    if (typeof window.requestAtlasTrustStatus === "function") return window.requestAtlasTrustStatus().catch(() => null);
    if (window.atlasTrustRequest) return window.atlasTrustRequest;
    const request = get("/api/repositories/current/trust-status");
    window.atlasTrustRequest = request;
    request.then((value) => {
      if (!value && window.atlasTrustRequest === request) window.atlasTrustRequest = null;
    }).catch(() => {
      if (window.atlasTrustRequest === request) window.atlasTrustRequest = null;
    });
    return request;
  };

  function trustFromHealth(health) {
    const card = health?.persistence?.resume_card;
    const fresh = card?.freshness_status === "fresh" && card?.validation_status === "valid";
    return fresh ? { ok: true, fresh: true, user_trust_label: "Fresh", source: "startup_validation" } : null;
  }

  function toggleSidebar() {
    const compact = document.body.classList.toggle("sidebar-compact");
    try { localStorage.setItem("atlas.sidebar.compact", compact ? "1" : "0"); } catch (_error) {}
    const label = byId("sidebarCollapse")?.querySelector("span:last-child");
    if (label) label.textContent = compact ? "Expand sidebar" : "Compact sidebar";
    window.dispatchEvent(new Event("resize"));
  }

  function restoreSidebar() {
    let compact = false;
    try { compact = localStorage.getItem("atlas.sidebar.compact") === "1"; } catch (_error) {}
    document.body.classList.toggle("sidebar-compact", compact);
  }

  function agentNames(status) {
    const labels = { claude: "Claude Code", cursor: "Cursor", codex: "Codex" };
    return Object.keys(labels).filter((key) => status?.[key]?.atlas_configured).map((key) => labels[key]);
  }

  function branchLabel(summary) {
    return clean(summary?.branch || summary?.git?.branch || summary?.git_branch, "Current checkout");
  }

  function syncSidebar(summary, trust, agents) {
    const hasRepo = !!summary?.ok;
    const connected = agentNames(agents);
    if (byId("sidebarRepoName")) byId("sidebarRepoName").textContent = hasRepo ? clean(summary.repo_name, "Repository") : "No repository";
    if (byId("sidebarRepoBranch")) byId("sidebarRepoBranch").textContent = hasRepo ? branchLabel(summary) : "Select a local codebase";
    if (byId("sidebarAgentState")) byId("sidebarAgentState").textContent = `${connected.length} agent${connected.length === 1 ? "" : "s"}`;
    const memory = byId("sidebarMemoryState");
    if (memory) {
      const fresh = !!(hasRepo && trust && (trust.fresh === true || trust.trust_status?.fresh === true || trust.user_trust_label === "Fresh"));
      memory.dataset.state = fresh ? "ready" : (hasRepo ? "warning" : "idle");
      memory.textContent = fresh ? "Memory current" : (hasRepo ? "Review memory" : "Memory offline");
    }
  }

  function questionButtons(questions, limit = 3) {
    return list(questions).slice(0, limit).map((question) => `<button type="button" data-question="${escapeHtml(question)}">${escapeHtml(question)}</button>`).join("");
  }

  function bindQuestionButtons(host, destination = "home") {
    host?.querySelectorAll("button[data-question]").forEach((button) => button.addEventListener("click", () => {
      const question = button.dataset.question || "";
      const input = destination === "ask" ? byId("askInput") : byId("homeAskInput");
      if (input) input.value = question;
      if (destination === "ask") input?.focus();
      else if (typeof window.submitHomeAsk === "function") window.submitHomeAsk(new Event("submit"));
    }));
  }

  function renderArchitectureMap(graph, summary) {
    const host = byId("homeArchitectureMap");
    if (!host) return;
    const nodes = list(graph?.nodes).slice(0, 14);
    if (!nodes.length) {
      host.innerHTML = `<div class="map-loading">Architecture map will appear after graph resolution.</div>`;
      return;
    }
    const width = 760, height = 330, cx = width / 2, cy = height / 2;
    const maxImportance = Math.max(1, ...nodes.map((node) => Number(node.production_files || node.module_count || node.fan_in || 1)));
    const positions = new Map();
    nodes.forEach((node, index) => {
      const ring = index < 4 ? 92 : (index < 9 ? 142 : 185);
      const slot = index < 4 ? index : (index < 9 ? index - 4 : index - 9);
      const count = index < 4 ? 4 : (index < 9 ? 5 : Math.max(5, nodes.length - 9));
      const angle = -Math.PI / 2 + (slot / count) * Math.PI * 2 + (index >= 9 ? .25 : 0);
      positions.set(clean(node.id || node.name || node.path || index), { x: cx + Math.cos(angle) * ring, y: cy + Math.sin(angle) * ring });
    });
    const nodeIds = new Set(positions.keys());
    const links = list(graph?.links).filter((link) => {
      const source = clean(typeof link.source === "object" ? link.source.id : link.source);
      const target = clean(typeof link.target === "object" ? link.target.id : link.target);
      return nodeIds.has(source) && nodeIds.has(target);
    }).slice(0, 30);
    const lineSvg = links.map((link, index) => {
      const source = positions.get(clean(typeof link.source === "object" ? link.source.id : link.source));
      const target = positions.get(clean(typeof link.target === "object" ? link.target.id : link.target));
      return `<line class="${index < 8 ? "strong" : ""}" x1="${source.x}" y1="${source.y}" x2="${target.x}" y2="${target.y}" />`;
    }).join("");
    const nodeSvg = nodes.map((node, index) => {
      const id = clean(node.id || node.name || node.path || index);
      const point = positions.get(id);
      const importance = Number(node.production_files || node.module_count || node.fan_in || 1);
      const radius = 7 + Math.min(9, (importance / maxImportance) * 9);
      const risk = Number(node.risk_score || node.risk || 0);
      const tone = risk >= 8 ? "risk" : (index < 4 ? "core" : "service");
      const label = clean(node.label || node.name || node.subsystem || node.path || id).split(/[\\/]/).pop().slice(0, 20);
      return `<g class="map-node" data-tone="${tone}" data-node="${escapeHtml(id)}" transform="translate(${point.x} ${point.y})"><circle r="${radius}"/><text x="${radius + 6}" y="3">${escapeHtml(label)}</text></g>`;
    }).join("");
    host.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${nodes.length} architecture areas and ${links.length} visible relationships">${lineSvg}${nodeSvg}</svg>`;
    host.querySelectorAll(".map-node").forEach((node) => node.addEventListener("click", () => {
      if (typeof window.go === "function") window.go("center");
      setTimeout(() => { if (typeof window.selectModuleFromList === "function") window.selectModuleFromList(node.dataset.node || ""); }, 160);
    }));
    if (byId("homeArchitectureMeta")) byId("homeArchitectureMeta").textContent = `${nodes.length} areas · ${links.length} visible paths`;
    const health = summary?.graph_health || {};
    host.dataset.health = clean(health.label, "unknown").toLowerCase();
  }

  function findingRows(summary) {
    const rows = [];
    const health = summary?.graph_health || {};
    list(summary?.top_boundaries).slice(0, 2).forEach((item) => rows.push({
      tone: "core",
      title: clean(item.label || item.name || item.path || item.source, "Architecture boundary"),
      meta: clean(item.reason || item.explanation || item.target, "Cross-subsystem dependency boundary"),
      action: "Inspect",
    }));
    list(summary?.top_risks).slice(0, 2).forEach((item) => rows.push({
      tone: "risk",
      title: clean(item.label || item.name || item.path, "High-impact module"),
      meta: clean(item.reason || item.explanation, `Risk score ${clean(item.risk_score, "review")}`),
      action: "Trace",
    }));
    if (Number(health.unresolved_internal || 0) > 0) rows.push({ tone: "risk", title: `${num(health.unresolved_internal)} unresolved internal imports`, meta: "Dependency graph has missing internal edges", action: "Review" });
    else rows.push({ tone: "core", title: "Internal dependency graph is resolved", meta: `${num(summary?.dependency_edges)} verified dependency edges`, action: "Graph" });
    return rows.slice(0, 5);
  }

  function renderHomeActivity(history, recent, trust) {
    const host = byId("activityList");
    if (!host) return;
    const items = list(history).slice(0, 4).map((item) => ({
      title: clean(item.title || item.request_text || item.workflow_type, "Repository investigation"),
      when: clean(item.created_at || item.updated_at, "Saved locally"),
    }));
    if (!items.length && trust) items.push({ title: trust.user_trust_label === "Fresh" ? "Repository evidence verified" : "Repository changes require review", when: "Current scan state" });
    list(recent).slice(0, 2).forEach((item) => items.push({ title: `Scan baseline · ${clean(item.repo_name, "repository")}`, when: clean(item.last_scan_at, "Saved locally") }));
    host.innerHTML = items.length ? items.slice(0, 5).map((item) => `<article class="technical-row"><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.when)}</span></article>`).join("") : `<span class="muted tiny">No saved questions or scan changes yet.</span>`;
  }

  function renderHomeDetails(summary, trust, graph, history, recent, agents, health) {
    if (!summary?.ok) return;
    const dashboard = byId("homeDashboard");
    const connected = agentNames(agents);
    const graphHealth = summary.graph_health || {};
    const fresh = trust && (trust.fresh === true || trust.trust_status?.fresh === true || trust.user_trust_label === "Fresh");
    const restored = !!health?.persistence?.restored;
    const setText = (id, value) => { const el = byId(id); if (el) el.textContent = clean(value, "—"); };
    setText("homeBranch", branchLabel(summary));
    setText("homeMemoryState", restored ? "Memory restored" : (fresh ? "Memory verified" : "Memory needs review"));
    setText("homeMetricModules", num(summary.module_count));
    setText("homeMetricEdges", num(summary.dependency_edges));
    setText("homeMetricSubsystems", num(summary.subsystem_count));
    setText("homeMetricHealth", clean(graphHealth.label, "Unknown"));
    setText("homeConnectedAgents", connected.length ? connected.join(" · ") : "No agent configured");
    const questions = byId("homeRecommendedQuestions");
    if (questions) {
      questions.innerHTML = questionButtons(summary.recommended_questions, 4);
      bindQuestionButtons(questions, "home");
    }
    const next = byId("homeNextActions");
    if (next) next.innerHTML = [
      ["✦", "Explain the primary architecture", "Ask Atlas", "ask"],
      ["↳", "Trace change impact", "Select a file", "impact"],
      ["◎", fresh ? "Investigate a failure" : "Refresh stale evidence", fresh ? "Use evidence" : "Required", fresh ? "investigate" : "scan"],
    ].map(([icon, title, meta, view]) => `<button type="button" data-view="${view}"><i>${icon}</i><span>${title}</span><small>${meta}</small></button>`).join("");
    next?.querySelectorAll("button[data-view]").forEach((button) => button.addEventListener("click", () => window.go(button.dataset.view)));
    const memory = byId("homeMemorySummary");
    if (memory) memory.innerHTML = [
      ["Freshness", fresh ? "Current" : "Review needed"],
      ["Persistence", restored ? "Restored" : "Available locally"],
      ["Evidence", `${num(summary.evidence_coverage?.symbol_count)} symbols`],
      ["Configured agents", connected.length ? connected.join(", ") : "None"],
    ].map(([label, value]) => `<div class="memory-pulse-row"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("");
    const findings = byId("homeFindingsList");
    if (findings) {
      findings.innerHTML = findingRows(summary).map((item) => `<article class="finding-row" data-tone="${item.tone}"><i></i><div><strong>${escapeHtml(item.title)}</strong><small>${escapeHtml(item.meta)}</small></div><button type="button">${item.action} →</button></article>`).join("");
      findings.querySelectorAll(".finding-row").forEach((row) => row.addEventListener("click", () => window.go(row.dataset.tone === "risk" ? "impact" : "center")));
    }
    renderArchitectureMap(graph, summary);
    renderHomeActivity(history, recent, trust);
  }

  async function renderHomeWorkbench() {
    const token = ++workbench.homeRenderToken;
    const stateSummary = window.STATE?.summary?.ok ? window.STATE.summary : null;
    const mcpClient = typeof atlasMcpSetup !== "undefined" ? atlasMcpSetup : null;
    const [summary, graph, history, recent, agents, health] = await Promise.all([
      stateSummary || get("/api/repositories/current/summary"),
      get("/api/repositories/current/graph?view=subsystem"),
      get("/api/history"),
      get("/api/repositories/recent"),
      mcpClient?.loadStatus ? mcpClient.loadStatus(false).catch(() => null) : Promise.resolve(null),
      get("/api/health"),
    ]);
    if (token !== workbench.homeRenderToken) return;
    const trust = workbench.trust || trustFromHealth(health);
    workbench.summary = summary; workbench.trust = trust; workbench.graph = graph; workbench.history = list(history?.items); workbench.agents = agents;
    if (summary?.ok && window.STATE) window.STATE.summary = summary;
    if (typeof renderHomeExperience === "function") renderHomeExperience({ trustStatus: trust, recent: list(recent?.items), mcpStatus: agents });
    syncSidebar(summary, trust, agents);
    renderHomeDetails(summary, trust, graph, workbench.history, list(recent?.items), agents, health);
    const trustRequest = getTrust();
    trustRequest.then((liveTrust) => {
      if (!liveTrust || token !== workbench.homeRenderToken) return;
      workbench.trust = liveTrust;
      if (typeof renderHomeExperience === "function") renderHomeExperience({ trustStatus: liveTrust, recent: list(recent?.items), mcpStatus: agents });
      syncSidebar(summary, liveTrust, agents);
      renderHomeDetails(summary, liveTrust, graph, workbench.history, list(recent?.items), agents, health);
    });
  }

  function conceptFromSubsystem(item, index) {
    return {
      name: clean(typeof item === "string" ? item : item.name || item.label || item.subsystem, `Architecture area ${index + 1}`),
      count: Number(typeof item === "object" ? item.production_files || item.module_count || item.file_count || 0 : 0),
      description: clean(typeof item === "object" ? item.role || item.description : "", "Indexed architectural concept with persistent dependency evidence."),
      files: list(typeof item === "object" ? item.entry_files : []),
      dependencies: list(typeof item === "object" ? item.dependencies : []),
    };
  }

  function selectMemoryConcept(index) {
    workbench.selectedConcept = Number(index) || 0;
    const concept = workbench.memoryConcepts[workbench.selectedConcept];
    if (!concept) return;
    byId("memoryConceptList")?.querySelectorAll(".memory-concept-button").forEach((button, buttonIndex) => button.classList.toggle("active", buttonIndex === workbench.selectedConcept));
    const host = byId("memoryConceptInspector");
    const freshness = byId("memoryFreshnessLabel")?.outerHTML || "";
    if (host) host.innerHTML = `<span class="memory-focus-index">${String(workbench.selectedConcept + 1).padStart(2, "0")}</span><div><p>Selected concept</p><h2>${escapeHtml(concept.name)}</h2><p>${escapeHtml(concept.description)} ${concept.count ? `${num(concept.count)} production files are associated with this area.` : ""}</p></div>${freshness}`;
  }

  function filterMemory(query) {
    const needle = clean(query).toLowerCase();
    byId("memoryConceptList")?.querySelectorAll(".memory-concept-button").forEach((button) => { button.hidden = !!needle && !button.textContent.toLowerCase().includes(needle); });
  }

  function applyMemoryTrust(trust, summary, health) {
    const fresh = !!(trust && (trust.fresh === true || trust.trust_status?.fresh === true || trust.user_trust_label === "Fresh"));
    const known = !!trust;
    const restored = !!health?.persistence?.restored;
    const freshness = byId("memoryFreshnessLabel");
    if (freshness) {
      freshness.textContent = known ? (fresh ? "Fresh" : "Review") : "Verifying";
      freshness.dataset.state = known ? (fresh ? "ready" : "warning") : "neutral";
    }
    const status = byId("memoryStatusStrip");
    if (status) status.innerHTML = known
      ? `<span class="state-label" data-state="${fresh ? "ready" : "warning"}">${fresh ? "Fresh" : "Review"}</span> ${fresh ? "Signed repository memory matches the current checkout." : "Repository evidence changed after the stored scan."}`
      : `<span class="state-label" data-state="neutral">Verifying</span> Live repository freshness is still being checked.`;
    const facts = byId("memoryFacts");
    if (facts && summary?.ok) facts.innerHTML = [["Repository", summary.repo_name], ["Freshness", known ? (fresh ? "Current" : "Review") : "Verifying"], ["Persistence", restored ? "Restored" : "Local"], ["Concepts", workbench.memoryConcepts.length], ["Modules", summary.module_count], ["Graph", summary.graph_health?.label]].map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`).join("");
  }

  async function renderMemoryWorkbench(context = null) {
    if (!context && window.atlasDesktopShell && typeof window.atlasDesktopShell.renderMemory === "function") {
      return window.atlasDesktopShell.renderMemory();
    }
    const token = ++workbench.memoryRenderToken;
    const [summary, history, health, graph] = await Promise.all([
      context?.summary || get("/api/repositories/current/summary"),
      context?.history || get("/api/history"),
      context?.health || get("/api/health"),
      context?.graph || get("/api/repositories/current/graph?view=module"),
    ]);
    if (token !== workbench.memoryRenderToken) return null;
    const active = document.querySelector(".view.active");
    if (active && active.id !== "view-memory") return null;
    if (!summary?.ok) return;
    const trust = context?.trust || workbench.trust || trustFromHealth(health);
    const concepts = list(summary.subsystems).map(conceptFromSubsystem);
    if (!concepts.length) concepts.push({ name: "Repository structure", count: summary.module_count, description: summary.explanation || "Repository-wide structural model.", files: summary.entry_points || [], dependencies: [] });
    workbench.memoryConcepts = concepts;
    const conceptList = byId("memoryConceptList");
    if (conceptList) {
      conceptList.innerHTML = concepts.map((concept, index) => `<button class="memory-concept-button ${index === workbench.selectedConcept ? "active" : ""}" type="button" data-index="${index}"><i></i><span><strong>${escapeHtml(concept.name)}</strong><small>${concept.count ? `${num(concept.count)} production files` : "Structured concept"}</small></span><b>${String(index + 1).padStart(2, "0")}</b></button>`).join("");
      conceptList.querySelectorAll("button[data-index]").forEach((button) => button.addEventListener("click", () => selectMemoryConcept(button.dataset.index)));
    }
    selectMemoryConcept(Math.min(workbench.selectedConcept, concepts.length - 1));
    const areaHost = byId("memoryEvidence");
    if (areaHost) areaHost.innerHTML = concepts.slice(0, 8).map((concept, index) => `<article class="memory-area-card" data-index="${index}"><span>${String(index + 1).padStart(2, "0")}</span><strong>${escapeHtml(concept.name)}</strong><small>${escapeHtml(concept.dependencies.length ? `Depends on ${concept.dependencies.slice(0, 3).join(", ")}` : `${num(concept.count)} indexed files`)}</small><div class="memory-area-links"><i style="width:${Math.max(18,Math.min(82,concept.count * 2))}%"></i><i style="width:${Math.max(12,Math.min(48,concept.dependencies.length * 8))}%"></i></div></article>`).join("");
    areaHost?.querySelectorAll("[data-index]").forEach((area) => area.addEventListener("click", () => selectMemoryConcept(area.dataset.index)));
    const coverage = summary.evidence_coverage || {};
    const groupHost = byId("memoryEvidenceGroups");
    if (groupHost) groupHost.innerHTML = [["Symbols", num(coverage.symbol_count)], ["Files grounded", num(coverage.files_with_symbols)], ["Dependency edges", num(summary.dependency_edges)]].map(([label, value]) => `<article class="evidence-group"><strong>${label}</strong><span>${value} evidence records</span></article>`).join("");
    applyMemoryTrust(trust, summary, health);
    const nodes = list(graph?.nodes).slice().sort((a, b) => Number(b.risk_score || b.fan_in || 0) - Number(a.risk_score || a.fan_in || 0));
    const critical = byId("memoryCriticalFiles");
    if (critical) critical.innerHTML = nodes.slice(0, 6).map((node) => `<article class="critical-file"><strong>${escapeHtml(node.path || node.name || node.label || node.id)}</strong><span>${num(node.fan_in)} incoming · risk ${clean(node.risk_score, "low")}</span></article>`).join("") || `<p class="muted tiny">No critical files reported.</p>`;
    const timeline = byId("memoryHistory");
    if (timeline) timeline.innerHTML = list(history?.items).slice(0, 8).map((item) => `<article class="memory-timeline-item"><strong>${escapeHtml(item.title || item.request_text || item.workflow_type || "Repository analysis")}</strong><span>${escapeHtml(item.created_at || item.updated_at || "Saved locally")}</span></article>`).join("") || `<article class="memory-timeline-item"><strong>Repository memory created</strong><span>Current signed scan</span></article>`;
    const gaps = byId("memoryUnresolved");
    const unresolved = Number(summary.graph_health?.unresolved_internal || 0);
    if (gaps) gaps.innerHTML = unresolved ? `<div class="memory-gap">${num(unresolved)} internal imports need resolution</div>` : `<div class="memory-gap">No unresolved internal dependency knowledge</div>`;
    getTrust().then((liveTrust) => {
      if (!liveTrust) return;
      workbench.trust = liveTrust;
      applyMemoryTrust(liveTrust, summary, health);
    });
  }

  async function renderAskContext() {
    const [summary, history] = await Promise.all([get("/api/repositories/current/summary"), get("/api/history")]);
    const suggestions = byId("askContextSuggestions");
    if (suggestions) { suggestions.innerHTML = questionButtons(summary?.recommended_questions, 5); bindQuestionButtons(suggestions, "ask"); }
    const recent = byId("askQuestionHistory");
    const items = list(history?.items).filter((item) => item.request_text || item.title).slice(0, 8);
    if (recent) {
      recent.innerHTML = items.length ? items.map((item) => `<button type="button" data-question="${escapeHtml(item.request_text || item.title)}">${escapeHtml(item.request_text || item.title)}</button>`).join("") : `<p>No investigations yet.</p>`;
      bindQuestionButtons(recent, "ask");
    }
    syncAskEvidence();
  }

  function syncAskEvidence() {
    const card = byId("copilotCard");
    const visible = card && getComputedStyle(card).display !== "none";
    const answer = byId("copilotAnswer");
    const legacyEvidence = list(byId("copilotEvidence")?.querySelectorAll("li")).map((el) => clean(el.textContent));
    const reportEvidence = list(answer?.querySelectorAll(".axr-ev-card")).map((el) => {
      const file = clean(el.querySelector(".axr-ev-file")?.textContent);
      const reason = clean(el.querySelector(".axr-ev-why")?.textContent);
      return [file, reason].filter(Boolean).join(" — ");
    });
    const evidence = (reportEvidence.length ? reportEvidence : legacyEvidence).filter(Boolean);
    const legacyFiles = list(byId("copilotFiles")?.querySelectorAll(".tag,button,span")).map((el) => clean(el.textContent));
    const reportFiles = list(answer?.querySelectorAll(".axr-file-path,.axr-ev-file")).map((el) => clean(el.textContent));
    const files = [...new Set((reportFiles.length ? reportFiles : legacyFiles).filter(Boolean))].slice(0, 8);
    const confidenceText = clean(answer?.querySelector(".axr-verdict-pill.conf")?.textContent || byId("copilotRisk")?.textContent).toLowerCase();
    const confidence = !visible ? "idle" : confidenceText.includes("high") ? "high" : confidenceText.includes("low") ? "low" : "medium";
    const confidenceHost = byId("askConfidencePanel");
    const confidenceLabel = confidence === "high" ? "High" : confidence === "medium" ? "Moderate" : confidence === "low" ? "Low" : "Awaiting analysis";
    const confidenceShort = confidence === "high" ? "High" : confidence === "medium" ? "Med" : confidence === "low" ? "Low" : "—";
    if (confidenceHost) confidenceHost.innerHTML = `<div class="confidence-dial" data-confidence="${confidence}"><span>${confidenceShort}</span></div><div><strong>${confidence === "idle" ? confidenceLabel : `${confidenceLabel} confidence`}</strong><small>${visible ? `${evidence.length} cited evidence item${evidence.length === 1 ? "" : "s"}` : "Confidence appears with an answer"}</small></div>`;
    const fileHost = byId("askRelatedFiles");
    if (fileHost) fileHost.innerHTML = files.length ? `<div class="evidence-file-list">${files.map((file) => `<button type="button" data-file="${escapeHtml(file)}">${escapeHtml(file)}</button>`).join("")}</div>` : "No files selected";
    fileHost?.querySelectorAll("button[data-file]").forEach((button) => button.addEventListener("click", () => { window.go("files"); setTimeout(() => window.atlasDesktopShell?.inspectFile(button.dataset.file), 80); }));
    const symbolHost = byId("askRelatedSymbols");
    if (symbolHost) symbolHost.innerHTML = evidence.length ? `<div class="symbol-path-list">${evidence.slice(0, 5).map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>` : "No symbols selected";
    const follow = byId("askFollowUps");
    if (follow) {
      const prompts = visible ? ["Show the dependency path", "Which file is most risky to change?", "What evidence would increase confidence?"] : [];
      follow.innerHTML = prompts.length ? prompts.map((prompt) => `<button type="button" data-question="${escapeHtml(prompt)}">${prompt}</button>`).join("") : `<button type="button" disabled>Ask a question to continue</button>`;
      bindQuestionButtons(follow, "ask");
    }
  }

  function searchGraph(value) {
    const filter = byId("moduleBrowseFilter");
    if (!filter) return;
    filter.value = value;
    if (typeof window.filterModuleBrowseList === "function") window.filterModuleBrowseList();
    const panel = byId("moduleBrowsePanel");
    const toggle = byId("moduleBrowseToggle");
    if (clean(value) && panel?.classList.contains("is-collapsed") && typeof window.toggleModuleBrowsePanel === "function") window.toggleModuleBrowsePanel();
    if (toggle) toggle.setAttribute("aria-expanded", clean(value) ? "true" : toggle.getAttribute("aria-expanded"));
  }

  function decorateAgentCards(status, summary) {
    const connected = agentNames(status);
    if (byId("agentRepoContext")) byId("agentRepoContext").textContent = summary?.ok ? `${summary.repo_name} · ${num(summary.module_count)} modules` : "Select a repository";
    if (byId("agentConfiguredCount")) byId("agentConfiguredCount").textContent = `${connected.length} / 3`;
    const cards = [{ key: "claude", id: "mcpClaudeCard" }, { key: "cursor", id: "mcpCursorCard" }, { key: "codex", id: "mcpCodexCard" }];
    cards.forEach(({ key, id }) => {
      const card = byId(id); if (!card) return;
      const data = status?.[key] || {};
      const configured = !!data.atlas_configured;
      card.dataset.connected = configured ? "true" : "false";
      let meta = card.querySelector(".agent-runtime-meta");
      if (!meta) { meta = document.createElement("div"); meta.className = "agent-runtime-meta"; card.querySelector(".mcp-tool-card-top")?.after(meta); }
      meta.innerHTML = [
        ["Connection", configured ? (summary?.ok ? "Configured; repository context ready" : "Configured — select a repository") : "Not configured"],
        ["Last handshake", clean(data.last_handshake || data.last_tested_at, configured ? "Configuration verified" : "Never")],
        ["Repository context", summary?.ok ? summary.repo_name : "Select a repository"],
        ["Configuration", clean(data.config_status || data.status, configured ? "Atlas MCP present" : "Action required")],
      ].map(([label, value]) => `<div class="agent-meta-row"><span>${escapeHtml(label)}</span><b>${escapeHtml(value)}</b></div>`).join("") + `<div class="agent-tool-list"><span>health</span><span>scan</span><span>find files</span><span>ask</span><span>impact</span><span>debug</span><span>plan</span></div>`;
    });
  }

  async function renderAgentsWorkbench() {
    const mcpClient = typeof atlasMcpSetup !== "undefined" ? atlasMcpSetup : null;
    const [status, summary] = await Promise.all([mcpClient?.loadStatus ? mcpClient.loadStatus(true).catch(() => null) : Promise.resolve(null), get("/api/repositories/current/summary")]);
    workbench.agents = status; decorateAgentCards(status, summary); syncSidebar(summary, workbench.trust, status);
  }

  function decorateDiagnostics() {
    const grid = byId("diagnosticsGrid"); if (!grid) return;
    const cards = list(grid.querySelectorAll(".diagnostic-card"));
    if (!cards.length) return;
    const passing = cards.filter((card) => card.dataset.state === "ready").length;
    const score = Math.round((passing / cards.length) * 100);
    const scoreHost = byId("diagnosticScore");
    if (scoreHost) scoreHost.innerHTML = `<span>${score}</span><small>health</small>`;
    const title = byId("diagnosticOverallTitle");
    if (title) title.textContent = passing === cards.length ? "All Atlas systems operational" : `${cards.length - passing} component${cards.length - passing === 1 ? " needs" : "s need"} attention`;
    const issues = byId("diagnosticIssues");
    if (issues) issues.innerHTML = cards.map((card) => {
      const ok = card.dataset.state === "ready";
      return `<article class="diagnostic-issue" data-state="${ok ? "ready" : "warning"}"><i></i><div><strong>${escapeHtml(card.querySelector("h2")?.textContent)}</strong><small>${escapeHtml(card.querySelector("p")?.textContent)}</small></div><span>${ok ? "Healthy" : "Review"}</span></article>`;
    }).join("");
    const failed = cards.filter((card) => card.dataset.state !== "ready");
    const fixes = byId("diagnosticFixes");
    if (fixes) fixes.innerHTML = failed.length ? failed.map((card) => `<article class="diagnostic-fix"><i></i><div><strong>Recover ${escapeHtml(card.querySelector("h2")?.textContent)}</strong><small>Run the recommended local recovery sequence and verify again.</small></div><button type="button" onclick="location.href='support.html'">Repair →</button></article>`).join("") : `<article class="diagnostic-fix"><i style="background:var(--wb-green)"></i><div><strong>No recovery action required</strong><small>Backend, index, memory and integrations responded successfully.</small></div><button type="button" onclick="atlasDesktopShell.refreshDiagnostics()">Verify again</button></article>`;
    const primary = byId("diagnosticPrimaryAction");
    if (primary) primary.innerHTML = failed.length ? `<a class="btn primary" href="support.html">Open recovery center</a>` : `<button class="btn ghost" type="button" onclick="go('home')">Return to repository</button>`;
  }

  function installObservers() {
    const askCard = byId("copilotCard");
    if (askCard) new MutationObserver(() => window.setTimeout(syncAskEvidence, 30)).observe(askCard, { subtree: true, childList: true, attributes: true, characterData: true });
    const diagnosticGrid = byId("diagnosticsGrid");
    if (diagnosticGrid) new MutationObserver(() => window.setTimeout(decorateDiagnostics, 20)).observe(diagnosticGrid, { subtree: true, childList: true, attributes: true });
    const home = byId("homeDashboard");
    if (home) {
      let previousHomeState = home.dataset.homeState || "";
      new MutationObserver(() => {
        const nextHomeState = home.dataset.homeState || "";
        if (nextHomeState === previousHomeState) return;
        previousHomeState = nextHomeState;
        if (nextHomeState === "productive") scheduleView("home", renderHomeWorkbench, 30);
      }).observe(home, { attributes: true, attributeFilter: ["data-home-state"] });
    }
  }

  function scheduleView(view, renderer, delay = 0) {
    const pending = workbench.scheduledViews.get(view);
    if (pending) window.clearTimeout(pending);
    const timer = window.setTimeout(() => {
      workbench.scheduledViews.delete(view);
      const active = document.querySelector(".view.active");
      if (active && active.id !== `view-${view}`) return;
      renderer();
    }, delay);
    workbench.scheduledViews.set(view, timer);
  }

  function onView(view) {
    if (view === "home") scheduleView("home", renderHomeWorkbench, 20);
    if (view === "ask") scheduleView("ask", renderAskContext, 40);
    if (view === "agents") scheduleView("agents", renderAgentsWorkbench, 80);
    if (view === "diagnostics") scheduleView("diagnostics", decorateDiagnostics, 300);
  }

  function init() {
    if (workbench.initialized) return;
    workbench.initialized = true;
    restoreSidebar();
    installObservers();
    document.addEventListener("atlas:viewchange", (event) => onView(event.detail?.view));
    document.addEventListener("atlas:authenticated", () => {
      const active = document.querySelector(".view.active");
      onView(active?.id?.replace(/^view-/, "") || "home");
    });
    const active = document.querySelector(".view.active");
    onView(active?.id?.replace(/^view-/, "") || "home");
  }

  Object.assign(workbench, { toggleSidebar, renderHomeWorkbench, renderMemoryWorkbench, renderAskContext, renderAgentsWorkbench, decorateDiagnostics, selectMemoryConcept, filterMemory, searchGraph, syncAskEvidence });
  window.atlasWorkbench = workbench;
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
