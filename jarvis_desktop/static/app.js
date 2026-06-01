"use strict";
const STATE = {
  repo: null, summary: null, graph: null, graphView: "module", graphPerf: null,
  exportTarget: "claude", exportPacket: "compact", graph3d: null, hoverNodeId: null,
  selectedNode: null, copilotResult: null, showEdges: true, riskPercentiles: null,
  demoMode: false,
};
const RECENT_KEY = "jarvis_recent_repos";
const ONBOARDING_KEY = "jarvis_onboarding_done_v1";

async function api(path, method = "GET", body) {
  const opt = { method, headers: { "Content-Type": "application/json" } };
  if (body) opt.body = JSON.stringify(body);
  const r = await fetch(path, opt);
  return r.json();
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

async function loadDemoMode() {
  dismissOnboarding(true);
  go("scan");
  showScanPanel("running");
  $("scanPath").textContent = "Loading JARVIS Demo Sample…";
  renderScanSkeleton();
  setBar(30);
  const scan = await api("/api/demo/load", "POST", {});
  setBar(100);
  if (!scan.ok) { showScanFailed(scan.error, scan.code); toast("✗ Demo load failed", "error"); return; }
  STATE.summary = await api("/api/repositories/current/summary");
  finishScanSession(scan, null);
  toast("Demo Mode loaded ✓", "success");
}

function go(view) {
  document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
  const el = $("view-" + view); if (el) el.classList.add("active");
  document.querySelectorAll("#nav button").forEach(b => b.classList.toggle("active", b.dataset.view === view));
  window.scrollTo({ top: 0, behavior: "smooth" });
  if (view === "center") setTimeout(renderCenter, 60);
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
  let stage = 0; setStage(0, "run"); setBar(4);
  const timer = setInterval(() => { if (stage < STAGES.length - 1) { setStage(stage, "done"); stage++; setStage(stage, "run"); setBar(8 + stage * 12); } }, 850);

  const scan = await api("/api/repositories/scan", "POST", { path });
  clearInterval(timer);
  STAGES.forEach((_, i) => setStage(i, "done")); setBar(100); $("scanPct").textContent = "100%";
  if (!scan.ok) {
    showScanFailed(scan.error || "Scan failed", scan.code);
    toast("✗ Scan failed", "error");
    return;
  }
  $("scanMetrics").innerHTML = metricGrid(scan);
  STATE.summary = await api("/api/repositories/current/summary");
  finishScanSession(scan, sel.path);
  toast("Scan complete ✓", "success");
}
function setStage(i, cls) { const el = $("st" + i); if (el) el.className = "stage " + cls; }
function setBar(pct) { $("scanBar").style.width = pct + "%"; $("scanPct").textContent = Math.round(pct) + "%"; }
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
  return api(`/api/repositories/current/graph?view=${encodeURIComponent(view)}`);
}

function setGraphView(view) {
  STATE.graphView = view;
  STATE.graph = null;
  document.querySelectorAll('input[name="graphView"]').forEach(el => {
    el.checked = el.value === view;
  });
  renderCenter();
}

function updateGraphMeta(data, perf) {
  const sum = STATE.summary || {};
  const perfText = perf && perf.loadMs != null ? ` · loaded ${perf.loadMs}ms` : "";
  const capText = data.total_modules > data.node_count
    ? ` · showing ${data.node_count}/${data.total_modules} modules`
    : "";
  $("graphMeta").textContent =
    `${data.view || STATE.graphView} · ${data.node_count} nodes · ${data.link_count} edges · ${sum.graph_scope || data.graph_scope || ""}${capText}${perfText}`;
}

async function renderCenter() {
  const sum = STATE.summary || (STATE.summary = await api("/api/repositories/current/summary"));
  if (!sum.ok) {
    $("leftPanel").innerHTML = emptyStateHtml("No repository scanned", "Scan a folder or load Demo Mode to explore the dependency graph.", "Go to Home", "go('home')");
    $("graph3d").innerHTML = emptyStateHtml("Graph unavailable", "Complete a scan to render the dependency graph.", "Try Demo Mode", "loadDemoMode()");
    $("suggest").innerHTML = "";
    return;
  }
  const sav = sum.token_savings || {};
  $("leftPanel").innerHTML = `
    <h3>Overview</h3>
    <div class="stat"><span>Files</span><b>${sum.file_count}</b></div>
    <div class="stat"><span>Modules</span><b>${sum.module_count}</b></div>
    <div class="stat"><span>Subsystems</span><b>${sum.subsystem_count}</b></div>
    <div class="stat"><span>Dependency edges</span><b>${sum.dependency_edges}</b></div>
    <div class="stat"><span>Graph health</span><span class="pill ${sum.graph_health.label==='healthy'?'ok':'warn'}">${sum.graph_health.label}</span></div>
    <div class="gauge"><div class="muted" style="font-size:11px">Architectural risk score</div><div class="gv" style="color:${riskColor(sum.risk_score)}">${sum.risk_score}</div></div>
    <div class="gauge"><div class="muted" style="font-size:11px">Est. token savings vs broad reading</div><div class="gv" style="color:var(--green)">${sav.reduction_percent||0}%</div>
      <div class="muted tiny">${(sav.compact_packet_tokens||0)} tok packet vs ~${(sav.naive_read_estimate||0)} tok</div></div>
    <h3 style="margin-top:18px">Top risks</h3>
    ${(sum.top_risks||[]).slice(0,5).map(r=>`<div class="stat"><span title="${r.path||''}">${(r.module||'').split('.').pop()}</span><b style="color:${riskColor(r.score)}">${r.score}</b></div>`).join("")}`;
  $("suggest").innerHTML = renderCopilotSuggestions(sum);
  const graph = STATE.graph || (STATE.graph = await fetchGraphPayload());
  STATE.riskPercentiles = computeRiskPercentiles(graph.nodes || []);
  updateGraphMeta(graph, STATE.graphPerf);
  build3DGraph(graph);
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

function graphNodeColor(n, active) {
  if (n.in_cycle) return active ? "#c9b0ff" : "#9a7bff";
  const pct = STATE.riskPercentiles;
  if (pct?.top1?.has(n.id)) return active ? "#ff8aa0" : "#ff5c7a";
  if (pct?.top5?.has(n.id)) return active ? "#ffd36a" : "#ffc24b";
  return active ? "#7ea0ff" : "#5b76c8";
}

function graphLinkColor(link, active) {
  const opacity = active ? Math.min(0.95, (link.opacity || 0.18) + 0.35) : (link.opacity || 0.18);
  return `rgba(120,160,255,${opacity})`;
}

function resetGraphHighlight(fg) {
  if (!fg) return;
  if (STATE.selectedNode) {
    highlightGraphNeighborhood(fg, STATE.selectedNode);
    return;
  }
  const show = STATE.showEdges !== false;
  fg.linkVisibility(() => show)
    .nodeColor(n => graphNodeColor(n, false))
    .linkColor(l => graphLinkColor(l, false))
    .linkWidth(l => show ? 0.2 + (l.weight || 1) * 0.12 : 0);
}

function highlightGraphNeighborhood(fg, node) {
  if (!fg) return;
  const show = STATE.showEdges !== false;
  fg.linkVisibility(() => show);
  const focusNode = node || STATE.selectedNode;
  if (!focusNode) { resetGraphHighlight(fg); return; }
  const graph = fg.graphData();
  const focus = new Set([focusNode.id]);
  graph.links.forEach(link => {
    const sid = typeof link.source === "object" ? link.source.id : link.source;
    const tid = typeof link.target === "object" ? link.target.id : link.target;
    if (sid === focusNode.id) focus.add(tid);
    if (tid === focusNode.id) focus.add(sid);
  });
  fg.nodeColor(n => graphNodeColor(n, focus.has(n.id)))
    .linkColor(l => {
      if (!show) return "rgba(0,0,0,0)";
      const sid = typeof l.source === "object" ? l.source.id : l.source;
      const tid = typeof l.target === "object" ? l.target.id : l.target;
      const active = focus.has(sid) && focus.has(tid) && (sid === focusNode.id || tid === focusNode.id);
      return graphLinkColor(l, active);
    })
    .linkWidth(l => {
      if (!show) return 0;
      const sid = typeof l.source === "object" ? l.source.id : l.source;
      const tid = typeof l.target === "object" ? l.target.id : l.target;
      const active = sid === focusNode.id || tid === focusNode.id;
      return active ? 0.75 + (l.weight || 1) * 0.22 : 0.12 + (l.weight || 1) * 0.06;
    });
}

function toggleGraphEdges() {
  STATE.showEdges = $("showEdges").checked;
  highlightGraphNeighborhood(STATE.graph3d, STATE.hoverNodeId ? { id: STATE.hoverNodeId } : STATE.selectedNode);
}

function build3DGraph(data) {
  const host = $("graph3d");
  if (!data || !data.ok || !(data.nodes || []).length) {
    host.innerHTML = '<div style="display:grid;place-items:center;height:100%;color:var(--muted)">No graph data.</div>';
    return;
  }
  if (typeof ForceGraph3D === "undefined") {
    host.innerHTML = `<div style="padding:24px;color:var(--muted)">3D graph library unavailable offline. Top hubs:<br>${(STATE.summary.top_hubs||[]).map(h=>`• ${h.module} ← ${h.fan_in}`).join("<br>")}</div>`;
    return;
  }
  host.innerHTML = "";
  $("nodePop").style.display = "none";
  const nodes = data.nodes.map(n => ({ ...n }));
  const links = data.links.map(l => ({ ...l }));
  const t0 = performance.now();
  const fg = ForceGraph3D()(host)
    .graphData({ nodes: [], links: [] })
    .backgroundColor("rgba(0,0,0,0)")
    .showNavInfo(false)
    .nodeLabel("")
    .nodeVal(n => n.size || 4)
    .nodeColor(n => graphNodeColor(n, false))
    .nodeOpacity(0.92)
    .linkColor(l => graphLinkColor(l, false))
    .linkWidth(l => 0.2 + (l.weight || 1) * 0.12)
    .linkOpacity(0.75)
    .onNodeClick(n => showNode(n))
    .onNodeHover(n => {
      STATE.hoverNodeId = n ? n.id : null;
      highlightGraphNeighborhood(fg, n || STATE.selectedNode);
      fg.nodeLabel(node => node && n && node.id === n.id
        ? `${node.label}\nfan-in ${node.fan_in} · fan-out ${node.fan_out} · risk ${node.risk_score}`
        : "");
    })
    .onBackgroundClick(() => {
      $("nodePop").style.display = "none";
      STATE.selectedNode = null;
      $("selectedNodeCard").style.display = "none";
      if (STATE.summary) $("suggest").innerHTML = renderCopilotSuggestions(STATE.summary);
      highlightGraphNeighborhood(fg, null);
    })
    .width(host.clientWidth)
    .height(host.clientHeight);
  STATE.graph3d = fg;

  try {
    const charge = fg.d3Force("charge");
    if (charge && charge.strength) charge.strength(-90 - Math.min(180, nodes.length * 0.08));
    const linkForce = fg.d3Force("link");
    if (linkForce && linkForce.distance) linkForce.distance(l => 28 + (6 / Math.max(l.opacity || 0.15, 0.12)));
  } catch (e) { /* library-specific force hooks */ }

  const chunkSize = nodes.length > 1200 ? 180 : nodes.length;
  let loaded = 0;
  function loadChunk() {
    const slice = nodes.slice(loaded, loaded + chunkSize);
    loaded += slice.length;
    const current = fg.graphData();
    const mergedNodes = [...(current.nodes || []), ...slice];
    const ids = new Set(mergedNodes.map(n => n.id));
    const mergedLinks = links.filter(l => ids.has(l.source) && ids.has(l.target));
    fg.graphData({ nodes: mergedNodes, links: mergedLinks });
    if (loaded < nodes.length) {
      requestAnimationFrame(loadChunk);
    } else {
      STATE.graphPerf = { loadMs: Math.round(performance.now() - t0), nodes: mergedNodes.length, links: mergedLinks.length };
      updateGraphMeta(data, STATE.graphPerf);
      try {
        const dist = 160 + Math.sqrt(mergedNodes.length) * 14;
        fg.cameraPosition({ z: dist });
      } catch (e) {}
    }
  }
  requestAnimationFrame(loadChunk);

  if (!STATE._graphResizeBound) {
    STATE._graphResizeBound = true;
    window.addEventListener("resize", () => {
      if (!STATE.graph3d || !$("graph3d")) return;
      STATE.graph3d.width($("graph3d").clientWidth).height($("graph3d").clientHeight);
    });
  }
}

function showNode(n) {
  STATE.selectedNode = n;
  const sub = (n.subsystem || "").toString();
  const moduleLine = n.module_count != null ? `<div class="nr"><span>modules</span><b>${n.module_count}</b></div>` : "";
  $("nodePop").style.display = "block";
  $("nodePop").innerHTML = `<h4>${n.label}</h4>
    <div class="nr"><span>subsystem</span><b>${sub}</b></div>
    <div class="nr"><span>fan-in</span><b>${n.fan_in}</b></div>
    <div class="nr"><span>fan-out</span><b>${n.fan_out}</b></div>
    <div class="nr"><span>importers</span><b>${n.importers_count ?? n.fan_in}</b></div>
    <div class="nr"><span>imports</span><b>${n.imported_modules_count ?? n.fan_out}</b></div>
    <div class="nr"><span>LOC</span><b>${n.loc}</b></div>
    <div class="nr"><span>risk score</span><b style="color:${riskColor(n.risk_score)}">${n.risk_score}</b></div>
    <div class="nr"><span>risk rank</span><b>${n.risk_rank ?? "—"}</b></div>
    <div class="nr"><span>cycle member</span><b>${n.in_cycle ? "yes" : "no"}</b></div>
    ${moduleLine}
    <div style="margin-top:8px"><button class="btn small" onclick="impactFor(${JSON.stringify(n.path)})">Analyze impact →</button></div>`;
  $("selectedNodeCard").style.display = "block";
  $("selectedNodeCard").innerHTML = `<h4>Selected: ${n.label}</h4>
    <div class="muted tiny">${n.path || ""} · fan-in ${n.fan_in} · fan-out ${n.fan_out}</div>`;
  if (STATE.summary) $("suggest").innerHTML = renderCopilotSuggestions(STATE.summary);
  highlightGraphNeighborhood(STATE.graph3d, n);
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
  wireSeg("segTarget", "exportTarget"); wireSeg("segPacket", "exportPacket");
  $("askInput").addEventListener("keydown", e => { if (e.key === "Enter") sendCopilotQuestion(); });
  $("askSend").addEventListener("click", sendCopilotQuestion);
  $("repoPath").addEventListener("keydown", e => { if (e.key === "Enter") validateRepoPath(true); });
  try {
    const h = await api("/api/health");
    if (h.repository_open) {
      unlockNav();
      STATE.summary = await api("/api/repositories/current/summary");
      updateRepoChip(h.repo_name || STATE.summary?.repo_name, h.demo_mode);
    }
  } catch (e) {}
})();
