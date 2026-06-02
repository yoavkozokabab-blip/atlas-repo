"use strict";
const STATE = {
  repo: null, summary: null, graph: null, graphView: "module", graphPerf: null,
  exportTarget: "claude", exportPacket: "compact", graph3d: null, hoverNodeId: null,
  selectedNode: null, copilotResult: null, showEdges: true, riskPercentiles: null,
  demoMode: false, tourStops: null, screenshotMode: false, demoPack: "small", productTourActive: false,
  massiveMode: false, lastEstimate: null, hierarchy: { level: "subsystem", subsystem: "", package: "", module: "" },
};
const RECENT_KEY = "atlas_recent_repos";
const LEGACY_RECENT_KEY = "jarvis_recent_repos";
const ONBOARDING_KEY = "atlas_onboarding_done_v1";
const DEMO_PACK_KEY = "atlas_demo_pack_v1";
const GRAPH_HIERARCHY_THRESHOLD = 1000;
const ATLAS_SHOW_GRAPH_DEBUG = false;
const NAV_ALIASES = { intel: "center", bug: "investigate", map: "center", "command-center": "center" };

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
  if (r.manual) return "Manually enabled for this scan";
  if (r.modules) return "Module count exceeds threshold";
  if (r.files) return "File count exceeds threshold";
  if (r.size) return "Repository size exceeds threshold";
  return "Repository exceeds massive-mode limits";
}

function renderGraphModeMetrics(sum, graph) {
  const view = STATE.graphView || "module";
  const totals = graphUnderlyingTotals(sum, graph);
  const vis = graphVisibleCounts(graph);
  const badge = $("graphModeBadge");
  if (badge) badge.style.display = "none";  // Phase 124 — no floating center badge
  const host = $("graphScaleHeader");
  if (host) {
    const gh = sum?.graph_health || {};
    const risk = sum?.risk_score ?? 0;
    const cycles = gh.import_cycles ?? 0;
    const coverage = gh.label || "—";
    if (view === "module") {
      host.innerHTML = `
        <div class="scale-row">
          <div class="scale-stat"><span class="scale-num">${vis.nodes.toLocaleString()}</span><span class="scale-lbl">modules</span></div>
          <div class="scale-stat"><span class="scale-num">${vis.links.toLocaleString()}</span><span class="scale-lbl">dependencies</span></div>
          <div class="scale-stat"><span class="scale-num">${risk}</span><span class="scale-lbl">risk</span></div>
          <div class="scale-stat"><span class="scale-num">${cycles}</span><span class="scale-lbl">cycles</span></div>
          <div class="scale-stat"><span class="scale-num" style="font-size:13px;color:${coverage === 'healthy' ? 'var(--green)' : 'var(--amber)'}">${coverage}</span><span class="scale-lbl">coverage</span></div>
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
  const d = perf?.renderDiagnostics || JARVIS_UNIVERSE.getRenderDiagnostics?.();
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

const TELEMETRY_WARNING_TEXT = "Telemetry unavailable. Repository analysis unaffected.";

function updateTelemetryWarning(source) {
  const el = $("telemetryWarning");
  if (!el) return;
  const degraded = source && (source.analytics_status === "degraded" || source.telemetry_warning);
  if (degraded) {
    el.style.display = "block";
    el.textContent = source.telemetry_warning || TELEMETRY_WARNING_TEXT;
  } else {
    el.style.display = "none";
  }
}

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
    permission_denied: ["Run Atlas Desktop with read access to the folder.", "Avoid system-protected directories."],
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
    $("pathError").textContent = res.error || "Invalid path";
    if (showToast) toast("✗ " + (res.error || "Invalid path"), "error");
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

function focusCopilot() { go("center"); setTimeout(() => $("askInput")?.focus(), 120); }

function finishScanSession(scan, pathLabel) {
  if (pathLabel && !scan.demo_mode) pushRecent(pathLabel);
  STATE.summary = null;
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
  renderScanSuccess(scan);
}

async function loadDemoMode(pack) {
  dismissOnboarding(true);
  const packId = pack || STATE.demoPack || "small";
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
  view = NAV_ALIASES[view] || view;
  document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
  const el = $("view-" + view); if (el) el.classList.add("active");
  document.querySelectorAll("#nav button").forEach(b => {
    const target = NAV_ALIASES[b.dataset.view] || b.dataset.view;
    b.classList.toggle("active", target === view);
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
  if (view === "center") {
    trackAnalytics("graph_opened");
    setTimeout(renderCenter, 60);
  }
  if (view === "home") renderDemoPackPicker();
  if (view === "export") refreshExport();
}
function unlockNav() { document.querySelectorAll('#nav button[data-lock="1"]').forEach(b => b.removeAttribute("data-lock")); }

function selectRecentPath(p) {
  $("repoPath").value = p;
  validateRepoPath(false);
}

/* ---------------- Recent repos ---------------- */
function loadRecent() {
  let list = [];
  try { list = JSON.parse(localStorage.getItem(RECENT_KEY) || "[]"); } catch (e) {}
  // Migrate from legacy key on first load
  if (!list.length) {
    try {
      const legacy = JSON.parse(localStorage.getItem(LEGACY_RECENT_KEY) || "[]");
      if (legacy.length) { list = legacy; localStorage.setItem(RECENT_KEY, JSON.stringify(list)); }
    } catch (e) {}
  }
  const box = $("recentList");
  if (!list.length) { box.innerHTML = '<span class="muted">None yet — scan a repository to populate this.</span>'; return; }
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
    $("scanModeInfo").textContent = "Import-level graph ready (~" + (scan.module_count || 0) + " modules). Open Repository Map for the full module graph.";
  } else if (scan.massive_mode) {
    $("scanModeInfo").style.display = "block";
    $("scanModeInfo").textContent = "Massive Repository Mode enabled. Starting with architecture overview is recommended.";
  } else if (scan.degraded) {
    $("scanModeInfo").style.display = "block";
    $("scanModeInfo").textContent = "Graph built in degraded/partial mode — some edges may be missing.";
  } else if (!scan.module_count && (scan.code_files || scan.file_count || 0) > 0) {
    $("scanModeInfo").style.display = "block";
    $("scanModeInfo").textContent = "This repository uses languages not yet supported for dependency extraction.";
  } else {
    $("scanModeInfo").style.display = "none";
  }
  $("scanMetrics").innerHTML = metricGrid(scan);
  STATE.summary = await api("/api/repositories/current/summary");
  finishScanSession(scan, sel.path);
  toast("Scan complete ✓", "success");
  if ((scan.module_count || 0) < GRAPH_HIERARCHY_THRESHOLD) {
    toast(`Opening Module Graph (${(scan.module_count || 0).toLocaleString()} modules)`, "success");
  }
}
function setStage(i, cls) { const el = $("st" + i); if (el) el.className = "stage " + cls; }
function setBar(pct) { $("scanBar").style.width = pct + "%"; $("scanPct").textContent = Math.round(pct) + "%"; }
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
      return api(`/api/repositories/current/hierarchy-graph?level=package&parent=${encodeURIComponent(h.subsystem || "")}`);
    }
    if (h.level === "module") {
      return api(`/api/repositories/current/hierarchy-graph?level=module&parent=${encodeURIComponent(h.package || h.subsystem || "")}`);
    }
    return api("/api/repositories/current/hierarchy-graph?level=subsystem");
  }
  return api(`/api/repositories/current/graph?view=${encodeURIComponent(view)}`);
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
  renderMapHeader(sum);
  $("suggest").innerHTML = renderCopilotSuggestions(sum);
  const graph = STATE.graph || (STATE.graph = await fetchGraphPayload());
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
  JARVIS_UNIVERSE.renderTimeline($("timelinePanel"), timeline);
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
    const label = sum.graph_health?.label || "—";
    badge.textContent = label;
    badge.className = `map-health-badge ${label}`;
  }
}

// Concise warning + "Details" link (full explanation in a toast, not a wall of text).
function setMapWarning(graph, sum) {
  const el = $("graphWarning");
  if (!el) return;
  const full = [graph.render_warning, sum.graph_health?.notice].filter(Boolean).join(" ");
  if (!full) { el.style.display = "none"; return; }
  const partial = (sum.graph_health?.label || "") !== "healthy";
  const concise = partial
    ? "Graph coverage is partial. Most missing links are external or dynamic imports."
    : "Some dependencies could not be resolved.";
  el.style.display = "flex";
  el.innerHTML = `<span>${concise}</span><span class="map-warning-details" role="button" tabindex="0" onclick="toast(${JSON.stringify(full)})">Details</span>`;
}

function renderArchitectureSummary(sum) {
  const host = $("architectureSummary");
  if (!host || !sum?.ok) return;
  const subsystems = (sum.subsystems || []).slice(0, 8);
  host.innerHTML = `
    <h3 style="margin-top:16px">Architecture</h3>
    <p class="muted tiny" style="margin:4px 0 8px">${esc((sum.explanation || "").slice(0, 280))}${(sum.explanation || "").length > 280 ? "…" : ""}</p>
    <div class="taglist">${subsystems.map(s => `<span class="tag" title="${esc((s.dependencies || []).join(", "))}">${esc(s.name)} · ${s.production_files || 0}</span>`).join("") || '<span class="muted tiny">—</span>'}</div>
    <p class="muted tiny" style="margin-top:8px">Entry: ${esc((sum.entry_points || []).slice(0, 3).join(", ") || "none detected")}</p>`;
}

function renderModuleBrowsePanel(graph, sum) {
  const panel = $("moduleBrowsePanel");
  const list = $("moduleBrowseList");
  if (!panel || !list) return;
  const view = STATE.graphView || "module";
  const nodes = (graph?.nodes || []).filter(n => n.type === "module" && n.path);
  const showList = view === "module" && nodes.length > 0;
  panel.style.display = showList ? "block" : "none";
  if (!showList) return;
  const totals = graphUnderlyingTotals(sum, graph);
  const summary = $("moduleBrowseSummary");
  if (summary) summary.textContent = `Top hubs · ${nodes.length.toLocaleString()} visible of ${totals.modules.toLocaleString()} modules`;
  const ranked = [...nodes].sort((a, b) => (b.fan_in || 0) - (a.fan_in || 0) || (b.risk_score || 0) - (a.risk_score || 0));
  STATE.moduleBrowseNodes = ranked;
  filterModuleBrowseList();
}

function filterModuleBrowseList() {
  const list = $("moduleBrowseList");
  if (!list || !STATE.moduleBrowseNodes) return;
  const q = ($("moduleBrowseFilter")?.value || "").trim().toLowerCase();
  const items = STATE.moduleBrowseNodes.filter(n => !q || (n.path || "").toLowerCase().includes(q)).slice(0, 100);
  list.innerHTML = items.map(n => {
    const path = n.path || "";
    const fi = n.fan_in || 0, fo = n.fan_out || 0;
    const risk = n.risk_score || 0;
    const sub = n.subsystem || "";
    const rc = risk >= 60 ? "var(--red)" : risk >= 35 ? "var(--amber)" : risk >= 15 ? "var(--cyan)" : "var(--green)";
    return `<li><button type="button" class="mbp-item" onclick="selectModuleFromList(${JSON.stringify(path)})">
      <span class="mbp-path">${esc(path)}</span>
      <span class="mbp-meta"><b style="color:${rc}">risk ${risk}</b> · in ${fi} · out ${fo}${sub ? " · " + esc(sub) : ""}</span>
    </button></li>`;
  }).join("") || '<li class="muted tiny">No modules match filter</li>';
}

function selectModuleFromList(path) {
  if (!path || !STATE.graph) return;
  const node = (STATE.graph.nodes || []).find(n => n.path === path);
  if (node) showNode(node);
}

function renderHealthCockpit(sum) {
  updateTelemetryWarning(sum);
  const sav = sum.token_savings || {};
  const gh = sum.graph_health || {};
  const showTokenSavings = sav.show_in_cockpit === true && sav.verified === true;
  const ratioNote = gh.unresolved_ratio_note || "Internal unresolved ÷ (resolved + unresolved internal)";
  const graphNotice = gh.notice
    ? `<div class="cockpit-card wide"><div class="cc-label">Graph coverage</div><div class="cc-val" style="font-size:13px;color:var(--amber)">${gh.notice}</div></div>`
    : "";
  const tel = sum.analytics_status === "degraded"
    ? `<div class="cockpit-card wide"><div class="cc-label">Telemetry</div><div class="cc-val" style="font-size:13px;color:var(--amber)">${sum.telemetry_warning || TELEMETRY_WARNING_TEXT}</div></div>`
    : "";
  const tokenCard = showTokenSavings
    ? `<div class="cockpit-card"><div class="cc-label">Token savings (verified)</div><div class="cc-val" id="ccSavings">${sav.reduction_percent || 0}%</div></div>`
    : "";
  $("leftPanel").innerHTML = `
    <h3>Health Cockpit</h3>
    ${tel}
    ${graphNotice}
    <div id="architectureSummary"></div>
    <div class="cockpit-grid">
      <div class="cockpit-card risk"><div class="cc-label">Risk score</div><div class="cc-val" id="ccRisk">${sum.risk_score}</div></div>
      <div class="cockpit-card"><div class="cc-label">Graph health</div><div class="cc-val" id="ccHealth" style="font-size:16px;color:${gh.label === 'healthy' ? 'var(--green)' : 'var(--amber)'}">${gh.label || "—"}</div></div>
      <div class="cockpit-card warn"><div class="cc-label">Import cycles</div><div class="cc-val" id="ccCycles">${gh.import_cycles ?? 0}</div></div>
      ${tokenCard}
    </div>
    <div class="cockpit-grid">
      <div class="cockpit-card"><div class="cc-label">Resolved imports</div><div class="cc-val">${gh.resolved_imports ?? 0}</div></div>
      <div class="cockpit-card warn"><div class="cc-label">Unresolved imports</div><div class="cc-val" title="Internal imports only">${gh.unresolved_imports ?? 0}</div></div>
      <div class="cockpit-card"><div class="cc-label">External package imports</div><div class="cc-val" title="Not counted in unresolved ratio">${gh.external_package_imports ?? 0}</div></div>
      <div class="cockpit-card"><div class="cc-label">Unresolved ratio</div><div class="cc-val" title="${esc(ratioNote)}">${((gh.unresolved_ratio ?? 0) * 100).toFixed(1)}%</div></div>
    </div>
    <p class="muted tiny" style="margin:4px 0 10px">${esc(ratioNote)}</p>
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
  if (showTokenSavings && $("ccSavings")) JARVIS_UNIVERSE.animateCounter($("ccSavings"), sav.reduction_percent || 0, 900);
  renderArchitectureSummary(sum);
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
  const noMatch = (res.answer || "").toLowerCase().includes("no match") || (res.answer || "").length < 20;
  if (noMatch) {
    $("copilotOut").innerHTML = `<span class="muted">I need a more specific file, module, or symptom to answer precisely.</span>
      <div class="suggest" style="margin-top:8px">
        <div class="sg" onclick="askQuestion('What are the top architectural risks?')">Ask about top risks</div>
        <div class="sg" onclick="askQuestion('What breaks if I change the top hub module?')">Ask what breaks if a file changes</div>
        <div class="sg" onclick="askQuestion('Explain the main subsystems')">Explain a subsystem</div>
        <div class="sg" onclick="askQuestion('Generate a Claude prompt for this repo')">Generate AI context</div>
      </div>`;
  } else {
    $("copilotOut").innerHTML = limits.length
      ? `<span class="muted">Limitations: ${limits.join(" · ")}</span>`
      : `<span class="muted">Confidence: ${res.confidence || "medium"}</span>`;
  }
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
    <div class="muted tiny">${n.path || ""} · ${n.subsystem || ""} · fan-in ${n.fan_in}</div>`;
  if (STATE.summary) $("suggest").innerHTML = renderCopilotSuggestions(STATE.summary);
  if ($("inspectorQuick")) $("inspectorQuick").style.display = n.path ? "flex" : "none";
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
  JARVIS_UNIVERSE.downloadDataUrl(url, `atlas-universe-${Date.now()}.png`);
  toast("PNG exported ✓", "success");
}

function exportGraphSVG() {
  const svg = JARVIS_UNIVERSE.exportSVG();
  if (!svg) { toast("SVG export failed"); return; }
  JARVIS_UNIVERSE.downloadText(svg, `atlas-universe-${Date.now()}.svg`, "image/svg+xml");
  toast("SVG exported ✓", "success");
}

function toggleScreenshotMode() {
  STATE.screenshotMode = !STATE.screenshotMode;
  JARVIS_UNIVERSE.toggleScreenshotMode(STATE.screenshotMode);
  $("screenshotBtn").textContent = STATE.screenshotMode ? "Exit screenshot" : "Screenshot";
  if ($("screenshotExitBtn")) {
    $("screenshotExitBtn").style.display = STATE.screenshotMode ? "block" : "none";
    $("screenshotExitBtn").textContent = STATE.productTourActive ? "Stop tour" : "Exit screenshot";
  }
  if ($("presentationBadge")) $("presentationBadge").style.display = STATE.screenshotMode ? "block" : "none";
  if (STATE.graph3d || JARVIS_UNIVERSE.fg) {
    const host = $("graph3d");
    JARVIS_UNIVERSE.fg?.width(host.clientWidth).height(host.clientHeight);
  }
}

function exitPresentationMode() {
  if (STATE.productTourActive) { stopProductTour(); return; }
  if (STATE.screenshotMode) toggleScreenshotMode();
}

function resetGraphView() {
  if (typeof JARVIS_UNIVERSE?.resetGraphView === "function") {
    JARVIS_UNIVERSE.resetGraphView();
    return;
  }
  if (JARVIS_UNIVERSE?.fg) {
    JARVIS_UNIVERSE.fg.cameraPosition({ x: 0, y: 0, z: 600 }, { x: 0, y: 0, z: 0 }, 800);
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

/* ---------------- Build Plan ---------------- */
function esc(s) { return String(s || "").replace(/</g, "&lt;"); }

function renderLimitations(items) {
  const list = items || [];
  if (!list.length) return "";
  return `<h3 style="font-size:13px;color:var(--amber);margin-top:14px">Limitations</h3><ul class="clean">${list.map(x => `<li>${esc(x)}</li>`).join("")}</ul>`;
}

function renderDomainKnowledge(dk) {
  if (!dk || !dk.applied) return "";
  const roles = dk.file_roles || {};
  const risks = (dk.knowledge_risks || []).slice(0, 8);
  const tag = (p) => `<span class="tag" onclick="investigateFile(${JSON.stringify(p)})">${esc(p)}</span>`;
  return `
    <div class="domain-panel glass">
      <div class="domain-head">
        <span class="domain-concept">${esc(dk.concept_name)} — ${esc(dk.concept_title || "")}</span>
        <span class="pill">${esc(dk.domain_label || dk.domain)}</span>
      </div>
      <p class="muted tiny"><b>Concept confidence:</b> ${esc(dk.concept_confidence)} · <b>Repo mapping:</b> ${esc(dk.repo_mapping_confidence)}</p>
      <p class="domain-why">${esc(dk.why_this_matters || dk.concept_understanding || "")}</p>
      ${risks.length ? `<div class="report-section"><div class="report-label">Knowledge-backed risks</div><ul class="clean tiny">${risks.map(r => `<li>${esc(r)}</li>`).join("")}</ul></div>` : ""}
      <div class="report-section"><div class="report-label">File roles</div>
        <p class="muted tiny">Must inspect</p><div class="taglist">${(roles.must_inspect || []).map(tag).join("") || '<span class="muted tiny">—</span>'}</div>
        <p class="muted tiny">Likely modify</p><div class="taglist">${(roles.likely_modify || []).map(tag).join("") || '<span class="muted tiny">—</span>'}</div>
        <p class="muted tiny">Verify only</p><div class="taglist">${(roles.verify_only || []).map(tag).join("") || '<span class="muted tiny">—</span>'}</div>
      </div>
      ${dk.integration_note ? `<p class="muted tiny">${esc(dk.integration_note)}</p>` : ""}
    </div>`;
}

async function runChangePlan() {
  const request = $("buildRequest")?.value.trim();
  if (!request) { toast("Describe the change you want"); return; }
  const r = await api("/api/planning/change", "POST", { request });
  const out = $("buildOut");
  if (!r.ok) {
    out.innerHTML = `<div class="glass ocard muted">${esc(r.error || "Plan failed")}</div>`;
    return;
  }
  STATE.buildResult = r;
  const p = r.plan || {};
  const prompts = r.prompts || {};
  out.innerHTML = `
    <div class="glass ocard">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <h3 style="margin:0">Change Plan</h3>
        <span class="lvl ${p.confidence?.includes('high') ? 'low' : 'medium'}">confidence: ${esc(p.confidence)}</span>
      </div>
      <p class="muted tiny" style="margin:8px 0">Size: <b>${esc(p.estimated_change_size)}</b> · Risk: <b>${esc(p.risk_level)}</b> · Intent: ${esc(p.intent)}</p>
      ${renderDomainKnowledge(p.domain_knowledge)}
      <div class="plan-grid">
        <div class="report-section"><div class="report-label">Affected systems</div><div class="taglist">${(p.affected_systems || p.likely_affected_subsystems || []).map(s => `<span class="tag">${esc(s)}</span>`).join("") || '<span class="muted tiny">none matched</span>'}</div></div>
        <div class="report-section"><div class="report-label">Entry points</div><div class="taglist">${(p.entry_points || []).map(s => `<span class="tag">${esc(s)}</span>`).join("") || '<span class="muted tiny">none detected</span>'}</div></div>
      </div>
      <div class="report-section"><div class="report-label">Implementation order</div><ol class="clean">${(p.implementation_order || []).map(s => `<li>${esc(s)}</li>`).join("") || '<li class="muted">n/a</li>'}</ol></div>
      <div class="report-section"><div class="report-label">What may break (direct importers / high coupling)</div><div class="taglist">${(p.what_may_break || p.files_likely_to_break || []).map(s => `<span class="tag" onclick="investigateFile(${JSON.stringify(s)})">${esc(s)}</span>`).join("") || '<span class="muted tiny">nothing high-risk identified</span>'}</div></div>
      <div class="report-section"><div class="report-label">Tests required</div><ul class="clean">${(p.tests_required || p.tests_likely_affected || []).map(s => `<li>${esc(s)}</li>`).join("")}</ul></div>
      <div class="report-section"><div class="report-label">Rollback plan</div><ul class="clean">${(p.rollback_plan || []).map(s => `<li>${esc(s)}</li>`).join("")}</ul></div>
      <details style="margin-top:8px"><summary class="muted tiny">Full plan (markdown) + evidence</summary>
        <pre class="code" style="max-height:320px;overflow:auto">${esc(r.formatted || "")}</pre>
        <ul class="clean tiny">${(p.evidence || []).map(e => `<li>${esc(e)}</li>`).join("")}</ul>
      </details>
      ${renderLimitations(r.limitations)}
      <h3 style="font-size:13px;color:var(--cyan);margin-top:16px">Export implementation prompts</h3>
      <div class="copy-row">
        <button class="btn small" onclick="copyBuildPrompt('claude')">Copy Claude</button>
        <button class="btn small" onclick="copyBuildPrompt('codex')">Copy Codex</button>
        <button class="btn small" onclick="copyBuildPrompt('cursor')">Copy Cursor</button>
      </div>
      <details style="margin-top:12px"><summary class="muted tiny">Preview Claude prompt</summary>
        <pre class="code">${esc(prompts.claude || "")}</pre></details>
      <h3 style="font-size:13px;color:var(--cyan);margin-top:18px">Impact simulation (optional)</h3>
      <div class="pick-row">
        <input id="buildImpactTarget" type="text" placeholder="module path to simulate blast radius" value="${esc((p.files_to_inspect_first || [])[0] || "")}" />
        <button class="btn ghost" onclick="runBuildImpact()">Simulate</button>
      </div>
      <div id="buildImpactOut"></div>
    </div>`;
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
  const symptom = $("investigateSymptom")?.value.trim();
  if (!symptom) { toast("Describe the symptom"); return; }
  const r = await api("/api/planning/investigate", "POST", { symptom });
  const out = $("investigateOut");
  if (!r.ok) {
    out.innerHTML = `<div class="glass ocard muted">${esc(r.error || "Investigation failed")}</div>`;
    return;
  }
  STATE.investigateResult = r;
  const p = r.plan || {};
  const prompts = r.prompts || {};
  out.innerHTML = `
    <div class="glass ocard">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <h3 style="margin:0">Investigation Report</h3>
        <span class="lvl ${p.confidence === 'high' ? 'low' : p.confidence === 'low' ? 'unknown' : 'medium'}">confidence: ${esc(p.confidence)}</span>
      </div>
      <div class="report-section">
        <div class="report-label">Symptom summary</div>
        <p>${esc(p.symptom_summary || p.symptom || "")}</p>
      </div>
      ${renderDomainKnowledge(p.domain_knowledge)}
      ${(p.domain_failure_modes || []).length ? `<div class="report-section"><div class="report-label">Domain failure modes</div><ul class="clean">${p.domain_failure_modes.map(m => `<li>${esc(m)}</li>`).join("")}</ul></div>` : ""}
      <div class="report-section">
        <div class="report-label">Most likely root cause</div>
        <p class="root-cause">${esc(p.most_likely_root_cause || p.most_likely_source || "Not localizable from this symptom alone")}</p>
      </div>
      <div class="report-section">
        <div class="report-label">Ranked hypotheses</div>
        ${renderHypotheses(p.hypotheses || [])}
      </div>
      ${(p.verification_checklist || []).length ? `<div class="report-section"><div class="report-label">Verification checklist</div><ul class="clean">${p.verification_checklist.map(v => `<li>${esc(v)}</li>`).join("")}</ul></div>` : ""}
      ${(p.minimal_fix_strategy || []).length ? `<div class="report-section"><div class="report-label">Minimal fix strategy</div><ul class="clean">${p.minimal_fix_strategy.map(v => `<li>${esc(v)}</li>`).join("")}</ul></div>` : ""}
      ${(p.risks_of_incorrect_fix || []).length ? `<div class="report-section"><div class="report-label">Risks of fixing incorrectly</div><ul class="clean">${p.risks_of_incorrect_fix.map(v => `<li>${esc(v)}</li>`).join("")}</ul></div>` : ""}
      ${renderLimitations(r.limitations)}
      <h3 style="font-size:13px;color:var(--cyan);margin-top:16px">Export investigation prompt</h3>
      <div class="copy-row">
        <button class="btn small" onclick="copyInvestigatePrompt('claude')">Copy Claude</button>
        <button class="btn small" onclick="copyInvestigatePrompt('codex')">Copy Codex</button>
        <button class="btn small" onclick="copyInvestigatePrompt('cursor')">Copy Cursor</button>
      </div>
      <details style="margin-top:12px"><summary class="muted tiny">Preview full report (markdown)</summary>
        <pre class="code">${esc(r.formatted || "")}</pre></details>
    </div>`;
}

function renderHypotheses(hyps) {
  if (!hyps.length) {
    return `<p class="muted tiny">No grounded hypotheses — add a file path, error type, or subsystem name and re-run.</p>`;
  }
  return hyps.map((h, i) => {
    const conf = h.confidence === "high" ? "low" : h.confidence === "low" ? "unknown" : "medium";
    const files = (h.files_involved || []).map(f => `<span class="tag" onclick="investigateFile(${JSON.stringify(f)})" title="Open in impact">${esc(f)}</span>`).join("")
      || '<span class="muted tiny">no grounded file — lead only</span>';
    return `
    <div class="hyp-card">
      <div class="hyp-head">
        <span class="hyp-rank">H${i + 1}</span>
        <span class="hyp-title">${esc(h.title)}</span>
        <span class="lvl ${conf}">${esc(h.confidence)}</span>
      </div>
      <p class="hyp-why"><b>Why it fits:</b> ${esc(h.why_it_fits)}</p>
      <div class="hyp-files">${files}</div>
      ${(h.evidence || []).length ? `<ul class="clean tiny hyp-evidence">${h.evidence.map(e => `<li>${esc(e)}</li>`).join("")}</ul>` : ""}
      <p class="hyp-line"><b>If correct:</b> ${esc(h.what_should_be_true_if_correct || "")}</p>
      <p class="hyp-line disprove"><b>How to disprove:</b> ${esc(h.how_to_disprove || "")}</p>
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
  const mockTag = r.mock ? `<span class="pill warn">heuristic / target not in graph</span>` : "";
  const scopeTag = r.impact_scope === "direct_only"
    ? `<span class="pill">direct impact only</span>`
    : "";
  out.innerHTML = `
    <div class="glass ocard">
      <div style="display:flex;justify-content:space-between;align-items:center"><h3 style="margin:0">Impact of changing <span style="color:var(--cyan)">${esc(r.target)}</span></h3><span class="lvl ${r.risk_level}">${r.risk_level} risk</span></div>
      <p class="muted tiny" style="margin:8px 0 14px">${esc(r.note || "")} ${scopeTag} ${mockTag}</p>
      ${r.transitive_available === false ? '<p class="muted tiny">Transitive importers are not computed — only direct importers listed below.</p>' : ""}
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
  a.download = `atlas_context_${STATE.exportTarget}_${STATE.exportPacket}.txt`; a.click(); toast("Prompt saved ✓");
}

/* ---------------- Boot ---------------- */
(async function boot() {
  loadRecent();
  maybeShowOnboarding();
  renderDemoPackPicker();
  wireSeg("segTarget", "exportTarget"); wireSeg("segPacket", "exportPacket");
  $("askInput").addEventListener("keydown", e => { if (e.key === "Enter") sendCopilotQuestion(); });
  $("repoPath").addEventListener("keydown", e => { if (e.key === "Enter") validateRepoPath(true); });
  ["scopeMode", "scopeFolder", "scopeInclude", "scopeExclude", "manualMassiveMode"].forEach(id => {
    const el = $(id);
    if (!el) return;
    el.addEventListener("change", () => validateRepoPath(false));
  });
  try {
    const h = await api("/api/health");
    updateTelemetryWarning(h);
    if (h.repository_open) {
      unlockNav();
      updateScanBtnState(true);
      STATE.summary = await api("/api/repositories/current/summary");
      updateTelemetryWarning(STATE.summary);
      updateRepoChip(h.repo_name || STATE.summary?.repo_name, h.demo_mode);
      updateMassiveBadge(!!STATE.summary?.massive_mode);
    }
  } catch (e) {}
})();
