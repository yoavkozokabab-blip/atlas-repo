"use strict";
/* Atlas Demo Studio — one-click cinematic recording mode.
   Loads a bundled demo repo, then runs a hands-free ~70s scripted tour over a
   maximized auto-orbiting 3D graph. No debug noise, clean branding. */

const S = { G: null, data: null, summary: null, risks: null, orbit: null, running: false, hl: "base", pack: "small" };

async function jget(p) { return (await fetch(p)).json(); }
async function jpost(p, b) { return (await fetch(p, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b || {}) })).json(); }
const wait = ms => new Promise(r => setTimeout(r, ms));

/* ---- scene overlay ---- */
function scene(kicker, title, sub) {
  const el = document.getElementById("scene");
  el.classList.remove("show");
  setTimeout(() => {
    document.getElementById("sceneKicker").textContent = kicker || "";
    document.getElementById("sceneTitle").textContent = title || "";
    document.getElementById("sceneSub").textContent = sub || "";
    el.classList.add("show");
  }, 350);
}
function hideScene() { document.getElementById("scene").classList.remove("show"); }
function datacard(head, rowsHtml) {
  document.getElementById("dcHead").textContent = head;
  document.getElementById("dcBody").innerHTML = rowsHtml;
  document.getElementById("datacard").classList.add("show");
}
function hideCard() { document.getElementById("datacard").classList.remove("show"); }
function setDots(active, total) {
  const d = document.getElementById("dots");
  d.classList.add("show");
  d.innerHTML = Array.from({ length: total }, (_, i) => `<span class="d ${i <= active ? "on" : ""}"></span>`).join("");
}

/* ---- 3D graph ---- */
function riskColor(s) { return s >= 50 ? "#ff5c7a" : s >= 25 ? "#ffbe5c" : s >= 12 ? "#9a8bff" : "#6bd5ff"; }
function buildGraph() {
  const host = document.getElementById("graph");
  if (typeof ForceGraph3D === "undefined" || !S.data || !(S.data.nodes || []).length) {
    host.innerHTML = '<div style="position:absolute;inset:0;background:radial-gradient(900px 500px at 50% 45%,rgba(120,110,255,.18),#05050a 70%)"></div>';
    return;
  }
  const nodeColor = n => {
    if (S.hl === "risk") return riskColor(n.risk_score || 0);
    if (S.hl === "impact") return n._imp ? "#6bd5ff" : (n._hub ? "#ff6bd0" : "rgba(150,150,180,.35)");
    return n.in_cycle ? "#9a8bff" : (n.fan_in >= 6 ? "#6bd5ff" : "#7b7ca8");
  };
  S.G = ForceGraph3D()(host)
    .graphData({ nodes: S.data.nodes.map(n => ({ ...n })), links: S.data.links.map(l => ({ ...l })) })
    .backgroundColor("#05050a")
    .showNavInfo(false)
    .nodeLabel(() => "")
    .nodeVal(n => 4 + Math.min(20, (n.fan_in || 0) * 1.4))
    .nodeColor(nodeColor).nodeOpacity(0.95)
    .linkColor(() => "rgba(140,150,255,0.16)").linkWidth(0.5)
    .width(host.clientWidth).height(host.clientHeight);
  try { S.G.cameraPosition({ x: 0, y: 30, z: 430 }, { x: 0, y: 0, z: 0 }, 0); } catch (e) {}
}
function recolor() { if (S.G) S.G.nodeColor(S.G.nodeColor()); }   // re-trigger accessor
function startOrbit() {
  if (!S.G) return;
  let t = 0; const R = 430;
  S.orbit = setInterval(() => {
    t += 0.0055;
    try { S.G.cameraPosition({ x: R * Math.sin(t), y: 60 + 40 * Math.sin(t * 0.4), z: R * Math.cos(t) }, { x: 0, y: 0, z: 0 }, 120); } catch (e) {}
  }, 60);
}
function stopOrbit() { if (S.orbit) { clearInterval(S.orbit); S.orbit = null; } }

/* ---- highlight helpers ---- */
function markImpact(hubPath) {
  const nodes = S.data.nodes;
  const hub = nodes.find(n => n.path === hubPath) || nodes.slice().sort((a, b) => b.fan_in - a.fan_in)[0];
  if (!hub) return null;
  const importers = new Set(S.data.links.filter(l => (l.target.id || l.target) === hub.id).map(l => (l.source.id || l.source)));
  nodes.forEach(n => { n._hub = (n.id === hub.id); n._imp = importers.has(n.id); });
  return { hub, count: importers.size };
}

/* ---- the cinematic sequence ---- */
async function runSequence() {
  S.running = true;
  document.getElementById("controls").classList.add("hide");
  document.getElementById("hint").style.opacity = "0";
  document.querySelector(".exitlink").classList.add("hide");
  const TOTAL = 6;

  // 1 — universe
  S.hl = "base"; recolor(); startOrbit(); setDots(0, TOTAL);
  scene("Repository intelligence", "Your code, as a universe", "Every module and connection — one living map, built locally in seconds.");
  await wait(11000);

  // 2 — risk
  S.hl = "risk"; recolor(); setDots(1, TOTAL);
  scene("Architectural risk", "The riskiest modules, ranked", "Dependency count, size, import cycles — with the evidence behind every score.");
  const rks = (S.risks.ranked_modules || []).slice(0, 4);
  datacard("Top architectural risk", rks.map(r => `<div class="drow"><span>${(r.label || "").split(".").pop()}</span><b style="color:${riskColor(r.total_score)}">${r.total_score}</b></div>`).join("") || '<div class="drow"><span>clean</span><b>0</b></div>');
  await wait(12500); hideCard();

  // 3 — impact
  const hub = (S.summary.top_hubs || [])[0];
  const imp = markImpact(hub && hub.path); S.hl = "impact"; recolor(); setDots(2, TOTAL);
  scene("What breaks?", "See the blast radius before you edit", "Atlas shows exactly what a change touches — and the tests to run.");
  if (imp) datacard("Impact of changing " + (hub ? hub.module : ""), `<div class="drow"><span>Affected modules</span><b>${imp.count}</b></div><div class="drow"><span>Risk level</span><b style="color:#ffbe5c">${imp.count >= 6 ? "high" : "medium"}</b></div><div class="pillbar" style="width:${Math.min(100, imp.count * 9)}%"></div>`);
  await wait(12000); hideCard();

  // 4 — copilot
  S.hl = "base"; recolor(); setDots(3, TOTAL);
  scene("AI copilot", "Ask anything about your code", "Grounded in real structure — not guesses.");
  const qs = (S.summary.recommended_questions || []).slice(0, 3);
  datacard("Suggested questions", qs.map(q => `<div class="drow" style="display:block;color:var(--ink-2)">“${q}”</div>`).join(""));
  await wait(11000); hideCard();

  // 5 — export
  setDots(4, TOTAL);
  const ex = await jpost("/api/context/export", { target: "claude", packet: "compact" });
  scene("AI context export", "AI-ready context in one click", "Compact packets for Claude, Codex and Cursor — token-cheap, evidence-rich.");
  datacard("Compact context packet", `<div class="drow"><span>Estimated tokens</span><b style="color:var(--accent)">${ex.estimated_tokens || "—"}</b></div><div class="drow"><span>Targets</span><b>Claude · Codex · Cursor</b></div><div class="drow"><span>Your code uploaded</span><b style="color:var(--good)">never</b></div>`);
  await wait(11000); hideCard();

  // 6 — outro
  stopOrbit(); setDots(5, TOTAL);
  try { S.G && S.G.cameraPosition({ x: 0, y: 20, z: 360 }, { x: 0, y: 0, z: 0 }, 2000); } catch (e) {}
  scene("Atlas", "Prepare your codebase for AI", "Stop making AI read your entire repository.");
  await wait(6000);

  // restore controls
  hideScene();
  document.getElementById("controls").classList.remove("hide");
  document.querySelector(".exitlink").classList.remove("hide");
  document.getElementById("hint").style.opacity = "";
  S.running = false;
  track("studio_demo_complete");
}

/* ---- start / restart ---- */
async function startDemo() {
  if (S.running) return;
  document.getElementById("titlecard").classList.add("hide");
  scene("", "Mapping your repository…", "");
  S.pack = document.getElementById("packSel").value || "small";
  await jpost("/api/demo/load", { pack: S.pack });
  S.data = await jget("/api/repositories/current/graph");
  S.summary = await jget("/api/repositories/current/summary");
  S.risks = await jget("/api/repositories/current/risks");
  buildGraph();
  await wait(900);
  runSequence();
}
function restartDemo() {
  stopOrbit(); S.running = false; hideScene(); hideCard();
  document.getElementById("titlecard").classList.remove("hide");
  document.getElementById("dots").classList.remove("show");
}

/* ---- boot ---- */
(async function () {
  try {
    const p = await jget("/api/demo/packs");
    const sel = document.getElementById("packSel");
    (p.packs || []).filter(x => x.available !== false).forEach(x => { const o = document.createElement("option"); o.value = x.id; o.textContent = x.label || x.id; sel.appendChild(o); });
  } catch (e) {}
  document.addEventListener("keydown", e => {
    if (e.code === "Space" || e.code === "Enter") { e.preventDefault(); if (!S.running) startDemo(); }
    else if (e.key === "r" || e.key === "R") restartDemo();
    else if (e.key === "Escape") location.href = "landing.html";
  });
  window.addEventListener("resize", () => { if (S.G) { const h = document.getElementById("graph"); S.G.width(h.clientWidth).height(h.clientHeight); } });
})();
