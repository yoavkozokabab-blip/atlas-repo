"use strict";

function $(id) { return document.getElementById(id); }

function toast(msg, kind) {
  const t = $("toast");
  if (!t) return;
  t.textContent = msg;
  t.className = "toast show" + (kind === "success" ? " toast-success" : kind === "error" ? " toast-error" : "");
  setTimeout(() => { t.className = "toast"; }, 2600);
}

async function api(path, method, body) {
  const opt = { method: method || "GET", headers: { "Content-Type": "application/json" } };
  if (body) opt.body = JSON.stringify(body);
  const r = await fetch(path, opt);
  try { return await r.json(); } catch (e) { return { ok: false, error: "Invalid response" }; }
}

function esc(s) {
  return String(s || "").replace(/</g, "&lt;");
}

function renderChecks(startup) {
  const host = $("envChecks");
  if (!host) return;
  const checks = (startup && startup.checks) || [];
  if (!checks.length) {
    host.innerHTML = '<p class="muted tiny">No checks returned.</p>';
    return;
  }
  let html = checks.map(c => {
    const cls = c.ok ? "ok" : (c.id === "optional" ? "warn" : "fail");
    return `<div class="support-check ${cls}">
      <span class="support-check-label">${esc(c.label)}</span>
      <span class="support-check-detail">${esc(c.detail)}</span>
      ${c.hint && !c.ok ? `<p class="support-hint">${esc(c.hint)}</p>` : ""}
    </div>`;
  }).join("");
  if (startup && startup.data_dir) {
    const fb = startup.data_dir_info && startup.data_dir_info.fallback;
    html += `<div class="support-check ok">
      <span class="support-check-label">Data directory</span>
      <span class="support-check-detail">${esc(startup.data_dir)}${fb ? " (fallback: " + esc(fb) + ")" : ""}</span>
    </div>`;
  }
  host.innerHTML = html;
}

function renderScanHealth(health) {
  const host = $("scanHealth");
  if (!host) return;
  if (!health || !health.ok) {
    host.innerHTML = '<p>No repository scanned yet. <a href="index.html">Open Atlas</a> and load a sample or scan a folder.</p>';
    return;
  }
  host.innerHTML = `
    <p><b>${esc(health.repo_name || "Repository")}</b></p>
    <ul class="clean tiny">
      <li>Modules: ${health.modules ?? "—"}</li>
      <li>Edges: ${health.edges ?? "—"}</li>
      <li>Graph quality: ${esc(health.graph_quality || "—")}</li>
      <li>Scan duration: ${health.scan_duration_seconds != null ? health.scan_duration_seconds + "s" : "—"}</li>
    </ul>`;
}

function renderSelfTest(result) {
  const host = $("selfTestResults");
  if (!host) return;
  if (!result || !result.ok) {
    host.innerHTML = `<p class="muted tiny">Self-test unavailable.</p>`;
    return;
  }
  const head = result.ready
    ? `<p class="support-check ok"><span class="support-check-label">Install looks healthy</span></p>`
    : `<p class="support-check fail"><span class="support-check-label">Some checks need attention</span></p>`;
  const rows = (result.checks || []).map(c => {
    const cls = c.ok ? "ok" : (c.optional ? "warn" : "fail");
    return `<div class="support-check ${cls}">
      <span class="support-check-label">${esc(c.label)}</span>
      <span class="support-check-detail">${esc(c.detail)}</span>
      ${c.hint && !c.ok ? `<p class="support-hint">${esc(c.hint)}</p>` : ""}
    </div>`;
  }).join("");
  host.innerHTML = head + rows;
}

async function supportRunSelfTest() {
  const host = $("selfTestResults");
  if (host) host.innerHTML = '<p class="muted tiny">Running…</p>';
  const result = await api("/api/system/self-test");
  renderSelfTest(result);
}

async function loadSupportStatus() {
  const env = await api("/api/system/startup-status");
  if (!env.ok) {
    $("envChecks").innerHTML = `<p class="muted">${esc(env.error || "Failed to load status")}</p>`;
    return;
  }
  $("atlasVersion").textContent = env.version || "—";
  if ($("atlasBuildCommit")) $("atlasBuildCommit").textContent = env.build_commit || "—";
  if ($("atlasBuildDate")) $("atlasBuildDate").textContent = env.build_date || "—";
  const trustEl = $("trustStatusLabel");
  if (trustEl) {
    const label = (env.scan_health && env.scan_health.user_trust_label) || "Fresh";
    trustEl.textContent = label;
    trustEl.className = "support-trust-label trust-" + String(label).toLowerCase().replace(/\s+/g, "-");
  }
  renderChecks(env.startup);
  renderScanHealth(env.scan_health);
  supportRunSelfTest();
}

function setActionMsg(msg) {
  const el = $("supportActionMsg");
  if (el) el.textContent = msg || "";
}

async function supportClearCache() {
  const r = await api("/api/system/clear-cache", "POST", {});
  setActionMsg(r.message || (r.ok ? "Cache cleared." : r.error));
  toast(r.ok ? "Cache cleared" : (r.error || "Failed"), r.ok ? "success" : "error");
  loadSupportStatus();
}

async function supportRebuildIndex() {
  setActionMsg("Rebuilding…");
  const r = await api("/api/system/rebuild-index", "POST", { rescan: true });
  setActionMsg(r.message || (r.ok ? "Rebuild complete." : r.error));
  toast(r.ok ? "Index rebuilt" : (r.error || "Failed"), r.ok ? "success" : "error");
  loadSupportStatus();
}

function supportResetOnboarding() {
  const keys = [
    "atlas_welcome_v141_done",
    "atlas_onboarding_v2_done",
    "atlas_guided_walkthrough_v141_done",
    "atlas_workflow_examples_seen",
  ];
  keys.forEach(k => { try { localStorage.removeItem(k); } catch (e) {} });
  setActionMsg("Onboarding and welcome screens reset. Reload Atlas home to see them again.");
  toast("Onboarding reset", "success");
}

async function supportCopyDiagnostics() {
  const d = await api("/api/system/diagnostics");
  const text = JSON.stringify(d, null, 2);
  try {
    await navigator.clipboard.writeText(text);
    toast("Diagnostics copied", "success");
  } catch (e) {
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
    toast("Diagnostics copied", "success");
  }
}

async function supportDownloadBundle() {
  setActionMsg("Building support bundle…");
  const r = await api("/api/system/support-bundle", "POST", {});
  if (!r.ok) {
    setActionMsg(r.error || "Bundle failed");
    toast(r.error || "Failed", "error");
    return;
  }
  const binary = atob(r.content_base64 || "");
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  const blob = new Blob([bytes], { type: "application/zip" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = r.filename || "atlas_support_bundle.zip";
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 3000);
  setActionMsg("Support bundle saved to your Downloads folder: " + (r.filename || "bundle") + " (" + Math.round((r.size_bytes || 0) / 1024) + " KB). Attach it to your support message.");
  toast("Support bundle saved to Downloads", "success");
}

window.supportClearCache = supportClearCache;
window.supportRebuildIndex = supportRebuildIndex;
window.supportResetOnboarding = supportResetOnboarding;
window.supportCopyDiagnostics = supportCopyDiagnostics;
window.supportDownloadBundle = supportDownloadBundle;
window.supportRunSelfTest = supportRunSelfTest;

loadSupportStatus();
