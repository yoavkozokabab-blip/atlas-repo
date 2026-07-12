"use strict";
/**
 * Launch UX: command palette (Ctrl/Cmd+K), shortcuts modal (?), local-only
 * activity feed, and the guided sample-repo demo tour.
 *
 * Privacy: the activity feed stores fixed event labels + timestamps in
 * localStorage only. It never records prompts, file paths, or repo contents.
 */

/* ------------------------------------------------------------------ *
 * Activity feed (local-only labels)
 * ------------------------------------------------------------------ */
const atlasActivity = (() => {
  const KEY = "atlas_activity_v1";
  const MAX = 30;

  function read() {
    try { return JSON.parse(localStorage.getItem(KEY) || "[]"); } catch (e) { return []; }
  }

  function write(list) {
    try { localStorage.setItem(KEY, JSON.stringify(list.slice(0, MAX))); } catch (e) {}
  }

  function when(ts) {
    const d = Date.now() - ts;
    if (d < 60000) return "just now";
    if (d < 3600000) return `${Math.round(d / 60000)}m ago`;
    if (d < 86400000) return `${Math.round(d / 3600000)}h ago`;
    return new Date(ts).toLocaleDateString();
  }

  function render() {
    const host = document.getElementById("activityList");
    if (!host) return;
    const list = read();
    if (!list.length) {
      host.innerHTML = '<p class="muted tiny" style="margin:0">No activity yet. Load the sample repository or scan a repo — useful events show up here.</p>';
      return;
    }
    host.innerHTML = list
      .map((e) => `<div class="activity-row"><span>${e.label}</span><span class="muted tiny">${when(e.ts)}</span></div>`)
      .join("");
  }

  function add(label) {
    if (!label) return;
    const list = read();
    list.unshift({ label: String(label).slice(0, 80), ts: Date.now() });
    write(list);
    render();
  }

  function clear() {
    write([]);
    render();
  }

  document.addEventListener("DOMContentLoaded", render);
  return { add, render, clear };
})();
window.atlasActivity = atlasActivity;

/* ------------------------------------------------------------------ *
 * Guided demo tour (sample repo → analysis → impact → failure → plan)
 * ------------------------------------------------------------------ */
const atlasDemoTour = (() => {
  // Example inputs match the "medium" sample pack the HN demo loads.
  const STEPS = [
    {
      id: "ask",
      title: "Repository Analysis",
      body: "Run the prepared investigation to produce a cited engineering report.",
      cta: "Run analysis",
      run() { if (typeof sendCopilotQuestion === "function") sendCopilotQuestion(); },
    },
    {
      id: "impact",
      title: "Change Impact",
      body: "Trace likely breakage before editing a heavily imported file.",
      cta: "Analyze api/handlers.py",
      run() {
        go("impact");
        const t = document.getElementById("impactTarget");
        if (t) t.value = "api/handlers.py";
        if (typeof runImpact === "function") runImpact();
      },
    },
    {
      id: "investigate",
      title: "Failure Investigation",
      body: "Start from an observed symptom. Atlas ranks likely causes against repository evidence.",
      cta: "Investigate a failure",
      run() {
        go("investigate");
        const t = document.getElementById("investigateSymptom");
        if (t) t.value = "API requests fail intermittently under load";
        if (typeof runInvestigationPlan === "function") runInvestigationPlan();
      },
    },
    {
      id: "build",
      title: "Implementation Plan",
      body: "Define a change and inspect affected files, sequencing, and risk.",
      cta: "Build an implementation plan",
      run() {
        go("build");
        const t = document.getElementById("buildRequest");
        if (t) t.value = "Add structured logging to API handlers";
        if (typeof runChangePlan === "function") runChangePlan();
      },
    },
    {
      id: "connect",
      title: "Use it from your agent",
      body: "Connect Claude, Cursor, or Codex so they can read this repo memory.",
      cta: "Open connections",
      run() {
        go("home");
        setTimeout(() => document.getElementById("mcpSetupSection")?.scrollIntoView({ block: "start" }), 150);
      },
    },
  ];

  let idx = -1;

  function bar() { return document.getElementById("demoTour"); }

  function renderStep() {
    const el = bar();
    if (!el) return;
    if (idx < 0 || idx >= STEPS.length) { el.style.display = "none"; return; }
    const s = STEPS[idx];
    el.style.display = "flex";
    el.querySelector(".dt-step").textContent = `Demo ${idx + 1}/${STEPS.length}`;
    el.querySelector(".dt-title").textContent = s.title;
    el.querySelector(".dt-body").textContent = s.body;
    const cta = el.querySelector(".dt-cta");
    cta.textContent = s.cta;
    cta.onclick = () => { s.run(); next(); };
  }

  function start() {
    idx = 0;
    renderStep();
  }

  function next() {
    idx += 1;
    if (idx >= STEPS.length) return end();
    renderStep();
  }

  function end() {
    idx = -1;
    const el = bar();
    if (el) el.style.display = "none";
  }

  return { start, next, end, active: () => idx >= 0 };
})();
window.atlasDemoTour = atlasDemoTour;

/** True when a repository (or the demo) is loaded. STATE is a top-level const
 * in app.js — visible to other classic scripts, but NOT a window property. */
function atlasHasRepo() {
  try { return !!(STATE && (STATE.summary?.ok || STATE.demoMode || STATE.repo)); } catch (e) { return false; }
}

/* ------------------------------------------------------------------ *
 * Command palette (Ctrl/Cmd+K)
 * ------------------------------------------------------------------ */
const atlasPalette = (() => {
  const ACTIONS = [
    { label: "Load sample repository", hint: "Index the bundled demo repo", run: () => loadDemoMode("medium") },
    { label: "Scan local repository", hint: "Point Atlas at a folder", run: () => go("scan") },
    { label: "Repository Analysis", hint: "Investigate with cited repository evidence", run: () => go("ask"), needsRepo: true },
    { label: "Change Impact", hint: "Trace direct and transitive consequences", run: () => go("impact"), needsRepo: true },
    { label: "Failure Investigation", hint: "Rank causes and verification steps", run: () => go("investigate"), needsRepo: true },
    { label: "Implementation Plan", hint: "Files, order, tests, and delivery risks", run: () => go("build"), needsRepo: true },
    { label: "Architecture Map", hint: "Inspect repository dependencies and risk", run: () => go("center"), needsRepo: true },
    { label: "Connect Claude", hint: "Write Claude Desktop MCP config", run: () => atlasMcpSetup.connectClaude() },
    { label: "Connect Cursor", hint: "Write Cursor MCP config", run: () => atlasMcpSetup.connectCursor() },
    { label: "Connect Codex", hint: "Write Codex MCP config", run: () => atlasMcpSetup.connectCodex() },
    { label: "Open Docs", hint: "In-app documentation", run: () => window.open("docs.html", "_blank") },
    { label: "Keyboard shortcuts", hint: "Show the shortcut list", run: () => atlasShortcuts.open() },
    { label: "Report bug / Suggest feature", hint: "Email the Atlas team", run: () => { window.location.href = "mailto:yoavkozokabab@gmail.com?subject=Atlas%20feedback"; } },
  ];

  let selected = 0;
  let visible = [];

  function overlay() { return document.getElementById("cmdPalette"); }
  function input() { return document.getElementById("cmdPaletteInput"); }
  function list() { return document.getElementById("cmdPaletteList"); }

  function available() {
    return ACTIONS.filter((a) => !a.needsRepo || atlasHasRepo());
  }

  function renderList(filter) {
    const q = (filter || "").trim().toLowerCase();
    visible = available().filter((a) => !q || a.label.toLowerCase().includes(q) || a.hint.toLowerCase().includes(q));
    if (selected >= visible.length) selected = Math.max(0, visible.length - 1);
    list().innerHTML = visible.length
      ? visible.map((a, i) =>
          `<div class="cp-item${i === selected ? " sel" : ""}" data-i="${i}"><span>${a.label}</span><span class="muted tiny">${a.hint}</span></div>`
        ).join("")
      : '<div class="cp-item muted">No matching action</div>';
    list().querySelectorAll(".cp-item[data-i]").forEach((el) => {
      el.onclick = () => { selected = Number(el.dataset.i); confirm(); };
    });
  }

  function open() {
    selected = 0;
    overlay().style.display = "grid";
    input().value = "";
    renderList("");
    setTimeout(() => input().focus(), 30);
  }

  function close() { overlay().style.display = "none"; }
  function isOpen() { return overlay() && overlay().style.display !== "none" && overlay().style.display !== ""; }

  function confirm() {
    const action = visible[selected];
    if (!action) return;
    close();
    action.run();
  }

  function onKey(e) {
    if (e.key === "Escape") { close(); return; }
    if (e.key === "ArrowDown") { e.preventDefault(); selected = Math.min(selected + 1, visible.length - 1); renderList(input().value); return; }
    if (e.key === "ArrowUp") { e.preventDefault(); selected = Math.max(selected - 1, 0); renderList(input().value); return; }
    if (e.key === "Enter") { e.preventDefault(); confirm(); return; }
  }

  document.addEventListener("DOMContentLoaded", () => {
    const inp = input();
    if (!inp) return;
    inp.addEventListener("input", () => { selected = 0; renderList(inp.value); });
    inp.addEventListener("keydown", onKey);
    overlay().addEventListener("mousedown", (e) => { if (e.target === overlay()) close(); });
  });

  return { open, close, isOpen };
})();
window.atlasPalette = atlasPalette;

/* ------------------------------------------------------------------ *
 * Shortcuts modal (?)
 * ------------------------------------------------------------------ */
const atlasShortcuts = (() => {
  function modal() { return document.getElementById("shortcutsModal"); }
  function open() { if (modal()) modal().style.display = "grid"; }
  function close() { if (modal()) modal().style.display = "none"; }
  function isOpen() { return modal() && modal().style.display === "grid"; }
  document.addEventListener("DOMContentLoaded", () => {
    const m = modal();
    if (m) m.addEventListener("mousedown", (e) => { if (e.target === m) close(); });
  });
  return { open, close, isOpen };
})();
window.atlasShortcuts = atlasShortcuts;

/* ------------------------------------------------------------------ *
 * Global key handling
 * ------------------------------------------------------------------ */
document.addEventListener("keydown", (e) => {
  const inField = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName || "") ||
    document.activeElement?.isContentEditable;

  // Ctrl/Cmd+K — command palette (works everywhere).
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    atlasPalette.isOpen() ? atlasPalette.close() : atlasPalette.open();
    return;
  }

  // Esc — close whichever overlay is open.
  if (e.key === "Escape") {
    if (atlasPalette.isOpen()) { atlasPalette.close(); return; }
    if (atlasShortcuts.isOpen()) { atlasShortcuts.close(); return; }
    const manual = document.getElementById("mcpManualModal");
    if (manual && manual.style.display === "grid") { manual.style.display = "none"; return; }
    return;
  }

  if (inField) return;

  // ? — shortcuts modal.
  if (e.key === "?") {
    e.preventDefault();
    atlasShortcuts.isOpen() ? atlasShortcuts.close() : atlasShortcuts.open();
    return;
  }

  // Plain navigation keys when not typing.
  if (!e.ctrlKey && !e.metaKey && !e.altKey) {
    if (e.key === "h") { go("home"); return; }
    if (e.key === "s") { go("scan"); return; }
    if (e.key === "a") {
      if (atlasHasRepo()) go("ask");
      return;
    }
  }
});
