"use strict";
const STATE = {
  repo: null, summary: null, graph: null, graphView: "module", graphPerf: null,
  exportTarget: "claude", exportPacket: "compact", graph3d: null, hoverNodeId: null,
  selectedNode: null, copilotResult: null, showEdges: true, riskPercentiles: null,
  demoMode: false, tourStops: null, screenshotMode: false, demoPack: "small", productTourActive: false,
  massiveMode: false, lastEstimate: null, hierarchy: { level: "subsystem", subsystem: "", package: "", module: "" },
};
const RECENT_KEY = "jarvis_recent_repos";
const ONBOARDING_KEY = "jarvis_onboarding_done_v1";
const DEMO_PACK_KEY = "jarvis_demo_pack_v1";

function sleep(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }

async function trackAnalytics(event, props) {
  try {
    await api("/api/analytics/event", "POST", { event, ...(props || {}) });
  } catch (e) { /* local-only, never block UX */ }
}

async function api(path, method = "GET", body) {
  const raw = String(path || "");
  const splitAt = raw.indexOf("?");
  const pathPart = splitAt >= 0 ? raw.slice(0, splitAt) : raw;
  const queryPart = splitAt >= 0 ? raw.slice(splitAt + 1) : "";
  const normalizedPath = pathPart.replace(/\/+$/, "") || "/api";
  const normalized = queryPart ? `${normalizedPath}?${queryPart}` : normalizedPath;
  const opt = { method, headers: { "Content-Type": "application/json" } };
  if (body) opt.body = JSON.stringify(body);
  const r = await fetch(normalized, opt);
  let payload = {};
  try { payload = await r.json(); } catch (e) { payload = { ok: false, error: "Invalid server response" }; }
  if (!payload.ok && String(payload.error || "").startsWith("Unknown endpoint")) {
    console.error("JARVIS API route missing:", method, normalized, payload.error);
  }
  return payload;
}
function $(id) { return document.getElementById(id); }
function toast(msg, kind) {
  const t = $("toast");
  t.textContent = msg;
  t.className = "toast show" + (kind === "success" ? " toast-success" : kind === "error" ? " toast-error" : "");
  setTimeout(() => { t.classList.remove("show"); t.className = "toast"; }, 2400);
}
async function copyText(text, label) {
  try { await navigator.clipboard.writeText(text); toast((label || "Copied") + " ✓", "success"); }
  catch (e) { const ta = document.createElement("textarea"); ta.value = text; document.body.appendChild(ta); ta.select(); document.execCommand("copy"); ta.remove(); toast((label || "Copied") + " ✓", "success"); }
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
  localStorage.setItem(ONBOARDING_KEY, "1");
  $("onboarding").style.display = "none";
  if (!skipDemo) go("home");
}

function maybeShowOnboarding() {
  try {
    if (localStorage.getItem(ONBOARDING_KEY) === "1") return;
  } catch (e) {}
  $("onboarding").style.display = "grid";
}

function showScanPanel(which) {
  $("scanRunning").style.display = which === "running" ? "block" : "none";
  $("scanSuccess").style.display = which === "success" ? "block" : "none";
  $("scanFailed").style.display = which === "failed" ? "block" : "none";
}

function renderScanSkeleton() {
  $("scanSkeleton").innerHTML = Array.from({ length: 8 }, () => '<div class="skeleton"></div>').join("");
}

function showScanFailed(message, code) {
  showScanPanel("failed");
  $("scanFailedMsg").textContent = message || "Scan failed.";
  const hints = {
    empty_path: ["Enter the full path to your project folder.", "Example: C:\\dev\\my-app"],
    not_found: ["Check spelling and drive letter.", "Use Validate before scanning."],
    no_code_files: ["Choose a folder that contains source files.", "Try Demo Mode to explore without a repo."],
    permission_denied: ["Run JARVIS Desktop with read access to the folder.", "Avoid system-protected directories."],
  };
  $("scanFailedHints").innerHTML = (hints[code] || ["Try Demo Mode or pick a different folder."]).map(h => `<li>${h}</li>`).join("");
}

function renderScanSuccess(scan) {
  showScanPanel("success");
  const demo = scan.demo_mode ? " · Demo Mode" : "";
  $("scanSuccessSub").textContent = `${scan.repo_name || "Repository"} indexed in ${scan.scan_duration_seconds || "?"}s${demo}`;
  $("scanSuccessMetrics").innerHTML = [
    ["Files indexed", scan.file_count],
    ["Modules", scan.module_count],
    ["Edges", scan.dependency_edges],
    ["Subsystems", scan.subsystem_count],
  ].map(([l, v]) => `<div class="metric"><div class="mv">${v ?? "—"}</div><div class="ml">${l}</div></div>`).join("");
  const risk = scan.top_risks?.[0];
  $("scanSuccessRisk").innerHTML = risk
    ? `<b style="color:${riskColor(risk.score)}">Top risk:</b> ${risk.module || risk.path} (score ${risk.score})`
    : `<span class="muted">No architectural risk ranking available.</span>`;
  $("scanSuccessActions").innerHTML = (scan.suggested_next_actions || []).map(a => `<li>${a}</li>`).join("");
}

async function validateRepoPath(showToast) {
  const path = ($("repoPath").value || "").trim();
  $("pathError").style.display = "none";
  $("pathOk").style.display = "none";
  if (!path) {
    $("pathError").style.display = "block";
    $("pathError").textContent = "Enter a folder path first.";
    if (showToast) toast("Enter a folder path", "error");
    return null;
  }
  const res = await api("/api/repositories/validate", "POST", { path });
  if (!res.ok) {
    $("pathError").style.display = "block";
    $("pathError").textContent = res.error || "Invalid path";
    if (showToast) toast("✗ " + (res.error || "Invalid path"), "error");
    return null;
  }
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

function focusCopilot() { go("center"); setTimeout(() => $("askInput")?.focus(), 120); }

function finishScanSession(scan, pathLabel) {
  if (pathLabel && !scan.demo_mode) pushRecent(pathLabel);
  STATE.summary = null;
  STATE.graph = null;
  STATE.graph3d = null;
  STATE.graphPerf = null;
  updateRepoChip(scan.repo_name, scan.demo_mode);
  unlockNav();
  renderScanSuccess(scan);
}

async function loadDemoMode(pack) {
  dismissOnboarding(true);
  const packId = pack || STATE.demoPack || "small";
  go("scan");
  showScanPanel("running");
  $("scanPath").textContent = `Loading JARVIS demo (${packId})…`;
  renderScanSkeleton();
  setBar(30);
  const scan = await api("/api/demo/load", "POST", { pack: packId });
  setBar(100);
  if (!scan.ok) { showScanFailed(scan.error, scan.code); toast("✗ Demo load failed", "error"); return; }
  STATE.demoPack = scan.demo_pack || packId;
  try { localStorage.setItem(DEMO_PACK_KEY, STATE.demoPack); } catch (e) {}
  STATE.summary = await api("/api/repositories/current/summary");
  finishScanSession(scan, null);
  toast("Demo loaded ✓", "success");
}

async function renderDemoPackPicker() {
  const host = $("demoPackList");
  if (!host) return;
  const res = await api("/api/demo/packs");
  if (!res.ok || !(res.packs || []).length) {
    host.innerHTML = `<span class="muted tiny">Demo packs unavailable.</span>`;
    return;
  }
  let selected = STATE.demoPack || "small";
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

function go(view) {
  document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
  const el = $("view-" + view); if (el) el.classList.add("active");
  document.querySelectorAll("#nav button").forEach(b => b.classList.toggle("active", b.dataset.view === view));
  window.scrollTo({ top: 0, behavior: "smooth" });
  if (view === "center") {
    trackAnalytics("graph_opened");
    setTimeout(renderCenter, 60);
  }
  if (view === "home") renderDemoPackPicker();
  if (view === "intel") renderIntel();
  if (view === "export") refreshExport();
}
function unlockNav() { document.querySelectorAll('#nav button[data-lock="1"]').forEach(b => b.removeAttribute("data-lock")); }

function selectRecentPath(p) {
  $("repoPath").value = p;
  validateRepoPath(false);
}

/* ---------------- Recent repos ---------------- */
function loadRecent() {
  let list = []; try { list = JSON.parse(localStorage.getItem(RECENT_KEY) || "[]"); } catch (e) {}
  const box = $("recentList");
  if (!list.length) { box.innerHTML = '<span class="muted">None yet — scan a repo to populate this.</span>'; return; }
  box.innerHTML = list.map(p => `<span class="rr" title="${p}" onclick="selectRecentPath(${JSON.stringify(p)})">${p.split(/[\\/]/).pop() || p}</span>`).join("");
}
function pushRecent(p) {
  let list = []; try { list = JSON.parse(localStorage.getItem(RECENT_KEY) || "[]"); } catch (e) {}
  list = [p, ...list.filter(x => x !== p)].slice(0, 6);
  localStorage.setItem(RECENT_KEY, JSON.stringify(list)); loadRecent();
}

/* ---------------- Scan flow ---------------- */
const STAGES = ["Indexing repository", "Building dependency graph", "Extracting architecture",
  "Detecting architectural risks", "Extracting contracts", "Generating verification evidence", "Building AI context packets"];

const STAGE_LABEL_INDEX = {};
STAGES.forEach((label, i) => { STAGE_LABEL_INDEX[label] = i; });

function applyScanStatus(status) {
  if (!status || !status.ok) return;
  const label = status.stage_label || "";
  const pct = status.progress_pct || 0;
  setBar(pct);
  let idx = STAGE_LABEL_INDEX[label];
  if (idx === undefined) {
    const partial = STAGES.findIndex(s => label.startsWith(s));
    idx = partial >= 0 ? partial : 0;
  }
  STAGES.forEach((_, i) => {
    if (i < idx) setStage(i, "done");
    else if (i === idx) setStage(i, "run");
    else setStage(i, "todo");
  });
  const lbl = $("st" + idx)?.querySelector(".lbl");
  if (lbl && label && label !== STAGES[idx]) lbl.textContent = label;
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
  const validation = await validateRepoPath(true);
  if (!validation) return;
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
    showScanFailed(scan.error || "Scan failed", scan.code);
    toast("✗ Scan failed", "error");
    return;
  }
  updateMassiveBadge(!!scan.massive_mode);
  if (scan.full_graph_pending) {
    $("scanModeInfo").style.display = "block";
    $("scanModeInfo").textContent = "Import-level graph ready (~" + (scan.module_count || 0) + " modules). Full module graph can be built on demand from Command Center.";
  } else if (scan.massive_mode) {
    $("scanModeInfo").style.display = "block";
    $("scanModeInfo").textContent = "Massive Repository Mode enabled. Starting with architecture overview is recommended.";
  } else if (scan.degraded) {
    $("scanModeInfo").style.display = "block";
    $("scanModeInfo").textContent = "Graph built in degraded/partial mode — some edges may be missing.";
  } else {
    $("scanModeInfo").style.display = "none";
  }
  $("scanMetrics").innerHTML = metricGrid(scan);
  STATE.summary = await api("/api/repositories/current/summary");
  finishScanSession(scan, sel.path);
  toast("Scan complete ✓", "success");
}
function setStage(i, cls) { const el = $("st" + i); if (el) el.className = "stage " + cls; }
function setBar(pct) { $("scanBar").style.width = pct + "%"; $("scanPct").textContent = Math.round(pct) + "%"; }
async function cancelCurrentScan() {
  const res = await api("/api/repositories/current/cancel-scan", "POST", {});
  if (res.ok) toast("Cancel requested", "success");
}
function metricGrid(s) {
  const M = [
    ["files discovered", s.files_discovered], ["modules indexed", s.module_count],
    ["subsystems", s.subsystem_count], ["dependency edges", s.dependency_edges],
    ["unresolved imports", s.unresolved_imports], ["import cycles", s.import_cycle_count],
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
      return api(`/api/repositories/current/hierarchy-graph?level=package&parent=${encodeURIComponent(h.subsystem || "")}`);
    }
    if (h.level === "module") {
      return api(`/api/repositories/current/hierarchy-graph?level=module&parent=${encodeURIComponent(h.package || h.subsystem || "")}`);
    }
    return api("/api/repositories/current/hierarchy-graph?level=subsystem");
  }
  return api(`/api/repositories/current/graph?view=${encodeURIComponent(view)}`);
}

function setGraphView(view) {
  STATE.graphView = view;
  if (view === "hierarchy") {
    STATE.hierarchy = { level: "subsystem", subsystem: "", package: "", module: "" };
  }
  STATE.graph = null;
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
  STATE.graph = null;
  renderCenter();
}

function backToOverview() {
  setGraphView("subsystem");
}

function updateGraphMeta(data, perf) {
  const sum = STATE.summary || {};
  const perfText = perf && perf.loadMs != null ? ` · loaded ${perf.loadMs}ms` : "";
  const capText = data.total_modules > data.node_count
    ? ` · showing ${data.node_count}/${data.total_modules} modules`
    : "";
  const clusterText = data.cluster_count ? ` · ${data.cluster_count} galaxies · ${data.bridge_link_count || 0} bridges` : "";
  const cacheText = (STATE.summary?.cache?.hit || STATE.graph?.cache?.hit) ? " · cache hit" : "";
  $("graphMeta").textContent =
    `${data.view || STATE.graphView} · ${data.node_count} nodes · ${data.link_count} edges · ${sum.graph_scope || data.graph_scope || ""}${clusterText}${capText}${cacheText}${perfText}`;
}

async function renderCenter() {
  const sum = STATE.summary || (STATE.summary = await api("/api/repositories/current/summary"));
  if (!sum.ok) {
    $("leftPanel").innerHTML = emptyStateHtml("No repository scanned", "Scan a folder or load Demo Mode to explore the dependency graph.", "Go to Home", "go('home')");
    $("graph3d").innerHTML = emptyStateHtml("Graph unavailable", "Complete a scan to render the dependency graph.", "Try Demo Mode", "loadDemoMode()");
    $("suggest").innerHTML = "";
    $("moduleInspector").innerHTML = `<h3>Module Inspector</h3><p class="muted tiny">Scan a repository first.</p>`;
    JARVIS_UNIVERSE.renderTimeline($("timelinePanel"), null);
    return;
  }
  renderHealthCockpit(sum);
  $("suggest").innerHTML = renderCopilotSuggestions(sum);
  const graph = STATE.graph || (STATE.graph = await fetchGraphPayload());
  if (STATE.graphView === "hierarchy") {
    renderHierarchyBreadcrumb();
    updateHierarchyCounts(graph);
  } else {
    $("hierarchyBreadcrumb").textContent = "Repository";
    $("hierarchyCounts").textContent = "";
  }
  if (graph.render_warning) {
    $("graphWarning").style.display = "block";
    $("graphWarning").textContent = graph.render_warning;
  } else {
    $("graphWarning").style.display = "none";
  }
  STATE.tourStops = graph.tour_stops || [];
  STATE.riskPercentiles = computeRiskPercentiles(graph.nodes || []);
  updateGraphMeta(graph, STATE.graphPerf);
  const timeline = await api("/api/repositories/current/timeline");
  JARVIS_UNIVERSE.renderTimeline($("timelinePanel"), timeline);
  renderModuleInspectorPlaceholder();
  build3DGraph(graph);
}

function renderHealthCockpit(sum) {
  const sav = sum.token_savings || {};
  const gh = sum.graph_health || {};
  $("leftPanel").innerHTML = `
    <h3>Health Cockpit</h3>
    <div class="cockpit-grid">
      <div class="cockpit-card risk"><div class="cc-label">Risk score</div><div class="cc-val" id="ccRisk">${sum.risk_score}</div></div>
      <div class="cockpit-card"><div class="cc-label">Graph health</div><div class="cc-val" id="ccHealth" style="font-size:16px;color:${gh.label === 'healthy' ? 'var(--green)' : 'var(--amber)'}">${gh.label || "—"}</div></div>
      <div class="cockpit-card warn"><div class="cc-label">Import cycles</div><div class="cc-val" id="ccCycles">${gh.import_cycles ?? 0}</div></div>
      <div class="cockpit-card"><div class="cc-label">Token savings</div><div class="cc-val" id="ccSavings">${sav.reduction_percent || 0}%</div></div>
    </div>
    <div class="cockpit-card"><div class="cc-label">Blast radius hub</div><div class="cc-val" style="font-size:14px;color:#eaf0ff">${(sum.top_hubs?.[0]?.module || "—").split(".").pop()}</div>
      <div class="muted tiny">${sum.top_hubs?.[0]?.fan_in ?? 0} direct importers</div></div>
    <div class="cockpit-card"><div class="cc-label">Repository modules</div><div class="cc-val" id="ccModules">${sum.module_count}</div></div>
    <h3 style="margin-top:14px">Top risks</h3>
    <ul class="clean cockpit-hubs">${(sum.top_risks || []).slice(0, 5).map(r => `<li><b style="color:${riskColor(r.score)}">${(r.module || "").split(".").pop()}</b> <span class="muted">${r.score}</span></li>`).join("")}</ul>
    <h3 style="margin-top:14px">Top hubs</h3>
    <ul class="clean cockpit-hubs">${(sum.top_hubs || []).slice(0, 5).map(h => `<li>${h.module} <span class="muted">← ${h.fan_in}</span></li>`).join("")}</ul>`;
  JARVIS_UNIVERSE.animateCounter($("ccRisk"), sum.risk_score, 800);
  JARVIS_UNIVERSE.animateCounter($("ccModules"), sum.module_count, 900);
  JARVIS_UNIVERSE.animateCounter($("ccCycles"), gh.import_cycles ?? 0, 700);
  JARVIS_UNIVERSE.animateCounter($("ccSavings"), sav.reduction_percent || 0, 900);
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

function defaultCopilotQuestions(summary) {
  const qs = [
    "What does this repository do?",
    "Where should I start?",
    "What are the top architectural risks?",
  ];
  if (summary?.top_hubs?.[0]?.path) qs.push(`What breaks if I change ${summary.top_hubs[0].path}?`);
  if ((summary?.graph_health?.import_cycles || 0) > 0) qs.push("Show import cycles.");
  qs.push("Generate a Claude prompt for this repo.");
  return qs;
}

function nodeCopilotQuestions(node) {
  const path = node.path || node.label || "this module";
  return [
    `Explain module ${path}`,
    `What breaks if I change ${path}?`,
    `Who imports ${path}?`,
    `Generate a Claude prompt for ${path}`,
  ];
}

function renderCopilotSuggestions(summary) {
  const qs = STATE.selectedNode ? nodeCopilotQuestions(STATE.selectedNode) : defaultCopilotQuestions(summary);
  return qs.map(q => `<div class="sg" onclick="askQuestion(${JSON.stringify(q)})">${q}</div>`).join("");
}

async function askQuestion(q) {
  $("askInput").value = q;
  await sendCopilotQuestion();
}

async function sendCopilotQuestion() {
  const question = ($("askInput").value || "").trim();
  if (!question) { toast("Enter a question"); return; }
  $("copilotLoading").style.display = "block";
  $("copilotCard").style.display = "none";
  const body = { question, target: "none", packet: "compact" };
  if (STATE.selectedNode) body.node_context = STATE.selectedNode;
  const res = await api("/api/copilot/ask", "POST", body);
  $("copilotLoading").style.display = "none";
  if (!res.ok) { toast("✗ " + (res.error || "Copilot failed")); return; }
  STATE.copilotResult = res;
  renderCopilotAnswer(res);
}

function renderCopilotAnswer(res) {
  $("copilotCard").style.display = "block";
  $("copilotMode").textContent = res.mode || "unknown";
  $("copilotRisk").textContent = `${res.risk_level || "unknown"} risk`;
  $("copilotRisk").className = `lvl ${res.risk_level || "unknown"}`;
  $("copilotAnswer").textContent = res.answer || "";
  const evidence = res.evidence || [];
  $("copilotEvidenceWrap").style.display = evidence.length ? "block" : "none";
  $("copilotEvidence").innerHTML = evidence.map(item => `<li>${item}</li>`).join("");
  const files = res.files || [];
  $("copilotFilesWrap").style.display = files.length ? "block" : "none";
  $("copilotFiles").innerHTML = files.map(f => `<span class="tag">${f}</span>`).join("");
  $("copilotActionWrap").style.display = res.suggested_action ? "block" : "none";
  $("copilotAction").textContent = res.suggested_action || "";
  const limits = (res.limitations || []).filter(Boolean);
  $("copilotOut").innerHTML = limits.length
    ? `<span class="muted">Limitations: ${limits.join(" · ")}</span>`
    : `<span class="muted">Confidence: ${res.confidence || "medium"}</span>`;
  if (res.graph_highlight) JARVIS_UNIVERSE.highlightBlastRadius(res.graph_highlight);
}

function copyCopilotAnswer() {
  if (!STATE.copilotResult?.answer) { toast("Nothing to copy"); return; }
  copyText(STATE.copilotResult.answer, "Answer copied");
}
function copyCopilotTarget(target) {
  const text = STATE.copilotResult?.copy_targets?.[target] || STATE.copilotResult?.suggested_prompt;
  if (!text) { toast("Nothing to copy"); return; }
  copyText(text, `${target} prompt copied`);
}

function toggleGraphEdges() {
  STATE.showEdges = $("showEdges").checked;
  JARVIS_UNIVERSE.setShowEdges(STATE.showEdges);
  JARVIS_UNIVERSE.refreshHighlight(STATE.hoverNodeId ? { id: STATE.hoverNodeId } : STATE.selectedNode);
}

function build3DGraph(data) {
  JARVIS_UNIVERSE.destroyGraph?.();
  STATE.graph3d = JARVIS_UNIVERSE.buildGraph($("graph3d"), data, {
    onNodeClick: n => {
      if (STATE.graphView === "hierarchy") {
        handleHierarchyClick(n);
        return;
      }
      showNode(n);
    },
    onNodeHover: n => { STATE.hoverNodeId = n ? n.id : null; },
    onBackgroundClick: () => {
      STATE.selectedNode = null;
      $("selectedNodeCard").style.display = "none";
      renderModuleInspectorPlaceholder();
      if (STATE.summary) $("suggest").innerHTML = renderCopilotSuggestions(STATE.summary);
    },
    getSelectedNode: () => STATE.selectedNode,
    onLoaded: perf => {
      STATE.graphPerf = perf;
      updateGraphMeta(data, perf);
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
      <div class="nr"><span>fan-in / fan-out</span><b>${info.fan_in} / ${info.fan_out}</b></div>
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
  $("moduleInspector").innerHTML = `
    <h3>Module Inspector 2.0</h3>
    <p class="muted tiny">Click a node in the universe graph to inspect path, subsystem, risk, imports, cycles, and evidence.</p>`;
}

function showNode(n) {
  STATE.selectedNode = n;
  $("selectedNodeCard").style.display = "block";
  $("selectedNodeCard").innerHTML = `<h4>Selected: ${n.label}</h4>
    <div class="muted tiny">${n.path || ""} · ${n.subsystem || ""} · fan-in ${n.fan_in}</div>`;
  if (STATE.summary) $("suggest").innerHTML = renderCopilotSuggestions(STATE.summary);
  renderModuleInspector(n);
  JARVIS_UNIVERSE.refreshHighlight(n);
  JARVIS_UNIVERSE.flyToNode(n, 1100);
}

function startRepositoryTour() {
  const stops = STATE.tourStops || STATE.graph?.tour_stops || [];
  if (!stops.length) { toast("Tour unavailable — scan a repository first"); return; }
  $("tourPanel").style.display = "block";
  JARVIS_UNIVERSE.startTour(stops, ({ stop, index, total, done }) => {
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
  JARVIS_UNIVERSE.stopTour();
  $("tourPanel").style.display = "none";
}

function exportGraphPNG() {
  const url = JARVIS_UNIVERSE.exportPNG(2);
  if (!url) { toast("Export failed"); return; }
  JARVIS_UNIVERSE.downloadDataUrl(url, `jarvis-universe-${Date.now()}.png`);
  toast("PNG exported ✓", "success");
}

function exportGraphSVG() {
  const svg = JARVIS_UNIVERSE.exportSVG();
  if (!svg) { toast("SVG export failed"); return; }
  JARVIS_UNIVERSE.downloadText(svg, `jarvis-universe-${Date.now()}.svg`, "image/svg+xml");
  toast("SVG exported ✓", "success");
}

function toggleScreenshotMode() {
  STATE.screenshotMode = !STATE.screenshotMode;
  JARVIS_UNIVERSE.toggleScreenshotMode(STATE.screenshotMode);
  $("screenshotBtn").textContent = STATE.screenshotMode ? "Exit screenshot" : "Screenshot";
  if ($("presentationBadge")) $("presentationBadge").style.display = STATE.screenshotMode ? "block" : "none";
  if (STATE.graph3d || JARVIS_UNIVERSE.fg) {
    const host = $("graph3d");
    JARVIS_UNIVERSE.fg?.width(host.clientWidth).height(host.clientHeight);
  }
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
  a.download = res.filename || "jarvis_demo_bundle.zip";
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 3000);
  toast("Demo bundle exported ✓", "success");
}

let _productTourTimer = null;
function stopProductTour() {
  STATE.productTourActive = false;
  if (_productTourTimer) clearTimeout(_productTourTimer);
  JARVIS_UNIVERSE.stopTour?.();
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
  STATE.productTourActive = true;
  trackAnalytics("product_tour_started");
  dismissOnboarding(true);
  setProductTourStep("Loading demo", "Scanning bundled repository for a screen-recording friendly walkthrough…");
  await loadDemoMode("small");
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
    setProductTourStep("Impact analysis", `Simulating blast radius if you change ${hub}.`);
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
  setProductTourStep("Tour complete", "Export Demo Bundle for marketing assets, or scan your own repository.");
  STATE.productTourActive = false;
  toast("Product tour complete ✓", "success");
}
function impactFor(path) { $("impactTarget").value = path; go("impact"); runImpact(); }

async function copyContext(target) {
  const res = await api("/api/copilot/ask", "POST", { question: `Generate a ${target} prompt for this repo`, target, packet: "compact" });
  if (!res.ok) { toast("✗ Scan a repo first"); return; }
  const text = res.copy_targets?.[target] || res.suggested_prompt || "";
  copyText(text, `Copied ${target} context`);
}

/* ---------------- Project Intelligence ---------------- */
async function renderIntel() {
  const sum = STATE.summary || (STATE.summary = await api("/api/repositories/current/summary"));
  const body = $("intelBody");
  if (!sum.ok) {
    body.innerHTML = emptyStateHtml("Scan required", "Project Intelligence needs a scanned repository or Demo Mode.", "Try Demo Mode", "loadDemoMode()");
    return;
  }
  const flow = ["entry point", "→", "subsystems", "→", "core hubs", "→", "actions"].map(x => x === "→" ? '<span class="ar">→</span>' : `<span class="fn">${x}</span>`).join("");
  body.innerHTML = `
    <div class="glass ib full"><h3>Plain-English explanation</h3><p>${sum.explanation}</p></div>
    <div class="glass ib"><h3>Subsystem map</h3><div class="taglist">${sum.subsystems.map(s=>`<span class="tag" title="${(s.dependencies||[]).join(', ')}">${s.name} · ${s.production_files}</span>`).join("")}</div></div>
    <div class="glass ib"><h3>Entry points</h3><div class="taglist">${(sum.entry_points||[]).map(e=>`<span class="tag">${e}</span>`).join("") || '<span class="muted">none detected</span>'}</div></div>
    <div class="glass ib full"><h3>Runtime flow (high level)</h3><div class="flow">${flow}</div><p class="muted tiny" style="margin-top:10px">Derived from subsystem dependencies; exact runtime branches are configuration-dependent.</p></div>
    <div class="glass ib"><h3>Major modules (import hubs)</h3><ul class="clean">${sum.top_hubs.map(h=>`<li>${h.module} <span class="muted">← ${h.fan_in} importers</span></li>`).join("")}</ul></div>
    <div class="glass ib"><h3>Architecture risks</h3><ul class="clean">${sum.top_risks.map(r=>`<li><b style="color:${riskColor(r.score)}">${(r.module||'').split('.').pop()}</b> <span class="muted">(${r.score}) — ${(r.reasons||[]).slice(0,2).join(', ')}</span></li>`).join("")}</ul></div>
    <div class="glass ib full"><h3>Recommended next questions</h3><ul class="clean">${(sum.recommended_questions||[]).map(q=>`<li>${q}</li>`).join("")}</ul></div>`;
}

/* ---------------- Impact ---------------- */
async function runImpact() {
  const target = $("impactTarget").value.trim();
  if (!target) { toast("Enter a file or module"); return; }
  const r = await api("/api/impact", "POST", { target });
  const out = $("impactOut");
  if (!r.ok) { out.innerHTML = `<div class="glass ocard muted">${r.error||'No result'}</div>`; return; }
  if (r.target_node_id) {
    JARVIS_UNIVERSE.highlightBlastRadius({
      target_node_id: r.target_node_id,
      affected_node_ids: r.affected_node_ids || [],
    });
    go("center");
  }
  const mockTag = r.mock ? `<span class="pill warn">heuristic / TODO</span>` : "";
  out.innerHTML = `
    <div class="glass ocard">
      <div style="display:flex;justify-content:space-between;align-items:center"><h3 style="margin:0">Impact of changing <span style="color:var(--cyan)">${r.target}</span></h3><span class="lvl ${r.risk_level}">${r.risk_level} risk</span></div>
      <p class="muted tiny" style="margin:8px 0 14px">${r.note || ""} ${mockTag}</p>
      <div class="stat"><span>Affected files</span><b>${r.affected_file_count||0}</b></div>
      <div class="taglist" style="margin:10px 0">${(r.affected_files||[]).slice(0,24).map(f=>`<span class="tag">${f}</span>`).join("") || '<span class="muted">none resolved</span>'}</div>
      <h3 style="font-size:13px;color:var(--cyan)">Affected subsystems</h3>
      <div class="taglist">${(r.affected_subsystems||[]).map(s=>`<span class="tag">${s}</span>`).join("") || '<span class="muted">none</span>'}</div>
      <h3 style="font-size:13px;color:var(--cyan);margin-top:16px">Recommended tests</h3>
      <ul class="clean">${(r.recommended_tests||[]).map(t=>`<li>${t}</li>`).join("")}</ul>
      <h3 style="font-size:13px;color:var(--cyan);margin-top:16px">Recommended Claude/Codex prompt</h3>
      <pre class="code">${(r.recommended_prompt||"").replace(/</g,"&lt;")}</pre>
      <button class="btn small" onclick="copyText(${JSON.stringify(r.recommended_prompt||"")}, 'Prompt copied')">Copy prompt</button>
    </div>`;
}

/* ---------------- Bug investigation ---------------- */
async function runBug() {
  const text = $("bugText").value.trim();
  if (!text) { toast("Paste a trace or describe the bug"); return; }
  const r = await api("/api/bug-investigation", "POST", { text });
  const out = $("bugOut");
  if (!r.ok) { out.innerHTML = `<div class="glass ocard muted">${r.error||''}</div>`; return; }
  const conf = r.confidence || "low";
  out.innerHTML = `
    <div class="glass ocard">
      <div style="display:flex;justify-content:space-between;align-items:center"><h3 style="margin:0">Likely source modules</h3><span class="lvl ${conf==='high'?'low':conf==='medium'?'medium':'unknown'}">confidence: ${conf}</span></div>
      ${r.mock?'<p class="muted tiny" style="margin-top:6px"><span class="pill warn">heuristic / TODO</span> Semantic localization + verification wiring is future work.</p>':''}
      <div class="taglist" style="margin:12px 0">${(r.likely_modules||[]).map(m=>`<span class="tag">${m}</span>`).join("") || '<span class="muted">no match — add a file path or module name</span>'}</div>
      <h3 style="font-size:13px;color:var(--cyan)">Evidence</h3>
      <ul class="clean">${(r.evidence||[]).map(e=>`<li>${e}</li>`).join("")}</ul>
      <h3 style="font-size:13px;color:var(--cyan);margin-top:14px">Suggested investigation prompt</h3>
      <pre class="code">${(r.suggested_prompt||"").replace(/</g,"&lt;")}</pre>
      <button class="btn small" onclick="copyText(${JSON.stringify(r.suggested_prompt||"")}, 'Prompt copied')">Copy prompt</button>
    </div>`;
}

/* ---------------- AI Context Export ---------------- */
function wireSeg(id, key) {
  $(id).querySelectorAll("button").forEach(b => b.onclick = () => {
    $(id).querySelectorAll("button").forEach(x => x.classList.remove("active"));
    b.classList.add("active"); STATE[key] = b.dataset.v; refreshExport();
  });
}
async function refreshExport() {
  const sum = STATE.summary || await api("/api/repositories/current/summary");
  if (!sum.ok) {
    $("exportPreview").innerHTML = emptyStateHtml("Export unavailable", "Scan a repository or load Demo Mode to build an AI context packet.", "Try Demo Mode", "loadDemoMode()");
    $("tokEst").textContent = "—";
    $("previewMeta").textContent = "Scan required";
    return;
  }
  const res = await api("/api/context/export", "POST", { target: STATE.exportTarget, packet: STATE.exportPacket });
  if (!res.ok) { $("exportPreview").textContent = "Scan a repository first."; $("tokEst").textContent = "—"; return; }
  $("exportPreview").textContent = res.text;
  $("tokEst").textContent = res.estimated_tokens;
  $("previewMeta").textContent = `${res.target} · ${res.packet} · ~${res.estimated_tokens} tokens`;
  STATE._exportText = res.text;
}
async function copyExport() { if (STATE._exportText) copyText(STATE._exportText, `Copied ${STATE.exportPacket} context for ${STATE.exportTarget}`); else toast("Nothing to copy"); }
function saveExport() {
  if (!STATE._exportText) { toast("Nothing to save"); return; }
  const blob = new Blob([STATE._exportText], { type: "text/plain" });
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
  a.download = `jarvis_context_${STATE.exportTarget}_${STATE.exportPacket}.txt`; a.click(); toast("Prompt saved ✓");
}

/* ---------------- Boot ---------------- */
(async function boot() {
  loadRecent();
  maybeShowOnboarding();
  renderDemoPackPicker();
  wireSeg("segTarget", "exportTarget"); wireSeg("segPacket", "exportPacket");
  $("askInput").addEventListener("keydown", e => { if (e.key === "Enter") sendCopilotQuestion(); });
  $("askSend").addEventListener("click", sendCopilotQuestion);
  $("repoPath").addEventListener("keydown", e => { if (e.key === "Enter") validateRepoPath(true); });
  ["scopeMode", "scopeFolder", "scopeInclude", "scopeExclude", "manualMassiveMode"].forEach(id => {
    const el = $(id);
    if (!el) return;
    el.addEventListener("change", () => validateRepoPath(false));
  });
  try {
    const h = await api("/api/health");
    if (h.repository_open) {
      unlockNav();
      STATE.summary = await api("/api/repositories/current/summary");
      updateRepoChip(h.repo_name || STATE.summary?.repo_name, h.demo_mode);
      updateMassiveBadge(!!STATE.summary?.massive_mode);
    }
  } catch (e) {}
})();
