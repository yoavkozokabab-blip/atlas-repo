"use strict";
/* zero-friction first user experience.
 *
 * Adds (UI only — no new intelligence, no backend changes):
 *  - clean boot loading screen teardown
 *  - "Send this to your AI coding tool" panel for Change Plan / Debug / What breaks?
 *  - rich, safe-to-implement prompts for Claude / Cursor / Codex built from existing plan data
 *  - "You're ready." success recognition after the first Change Plan
 *  - broad-folder confirmation before scanning an obviously-too-large folder
 */

const ZF_READY_KEY = "atlas_ready_state_shown_v155";

/* ---------------- boot loading screen ---------------- */
function hideBootSplash() {
  const el = document.getElementById("bootSplash");
  if (!el) return;
  el.classList.add("done");
  setTimeout(() => { el.style.display = "none"; }, 480);
}

/* ---------------- helpers ---------------- */
function zfRepoName() {
  return (window.STATE && STATE.summary && STATE.summary.repo_name) || "this repository";
}

function zfList(arr, limit) {
  return (arr || []).slice(0, limit || 12).filter(Boolean);
}

function zfBullets(arr, limit) {
  const items = zfList(arr, limit);
  return items.length ? items.map(x => `- ${x}`).join("\n") : "- (none identified)";
}

const ZF_TOOL_LABEL = { claude: "Claude", cursor: "Cursor", codex: "Codex" };
const ZF_FULL_EXPORT = "FULL_EXPORT";
const ZF_MINIMAL_EXPORT = "MINIMAL_EXPORT";

function zfExportMode() {
  return (window.STATE && STATE.exportMode) || ZF_MINIMAL_EXPORT;
}

function zfWorkflowResult(kind) {
  if (!window.STATE) return {};
  if (kind === "investigate") return STATE.investigateResult || {};
  if (kind === "impact") return STATE.impactResult || {};
  return STATE.buildResult || {};
}

function zfServerExportText(kind) {
  const r = zfWorkflowResult(kind);
  const mode = zfExportMode();
  const block = mode === ZF_FULL_EXPORT ? r.export_full : (r.export || r.export_minimal);
  return (block && block.text) ? block.text : "";
}

const ZF_CLIPBOARD_METADATA_RE = /^(scan_id|scan_signature|memory_ref|generated_at|replay_warning|freshness_status|ref):/i;

function zfStripClipboardMetadata(text) {
  if (!text) return "";
  return String(text)
    .split("\n")
    .filter(function (line) { return !ZF_CLIPBOARD_METADATA_RE.test(line.trim()); })
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function zfSessionPrefix() {
  const se = window.STATE && STATE.sessionExport;
  if (!se || !se.text) return "";
  const text = zfStripClipboardMetadata(se.text.trim());
  return text ? text + "\n\n" : "";
}

function zfClipboardBody(kind) {
  const server = zfServerExportText(kind);
  if (!server) return zfLegacyFullPromptBody(kind);
  return zfStripClipboardMetadata(server);
}

function zfTrustBlock(result) {
  const r = result || {};
  const p = r.plan || {};
  const lines = ["## Trust & grounding"];
  const conf = r.confidence || p.confidence;
  if (conf) lines.push(`- Confidence: ${conf}`);
  const cap = r.confidence_cap_reason || p.confidence_cap_reason;
  if (cap) lines.push(`- Confidence note: ${cap}`);
  const ep = r.evidence_panel || p.evidence_panel || r.impact_evidence_panel;
  if (ep && ep.summary) {
    lines.push(`- Evidence: ${ep.summary}`);
  } else if (ep && (ep.items || []).length) {
    lines.push(`- Evidence: ${ep.items.length} grounded match(es) from symbol/path index`);
  } else if ((p.evidence || r.evidence || []).length) {
    lines.push(`- Evidence: ${(p.evidence || r.evidence).slice(0, 2).join("; ")}`);
  }
  const gh = r.graph_health || p.graph_health;
  if (gh && typeof gh === "string" && gh !== "healthy") {
    lines.push(`- Graph health: ${gh}`);
  } else if (gh && gh.notice) {
    lines.push(`- Graph health: ${gh.notice}`);
  }
  const status = r.status || p.status;
  if (status && /unknown|insufficient|unresolved|not_resolved/i.test(String(status))) {
    lines.push(`- Status: ${status}`);
  }
  const lims = (r.limitations || p.limitations || []).filter(l =>
    /insufficient|unknown|evidence|graph health/i.test(String(l)));
  if (lims.length) lines.push(`- Caveat: ${lims[0]}`);
  return lines.length > 1 ? lines.join("\n") : "";
}

function zfSafetyFooter() {
  return [
    "## How to work safely",
    "- Implement the steps in order; make one focused change at a time.",
    "- Do not change a module's public interface without updating every file that imports it (see \"What may break\").",
    "- Run the listed tests after each step. Add tests for new behavior.",
    "- Keep changes reversible: small commits, and follow the rollback notes if something regresses.",
    "- If the plan and the real code disagree, trust the code and tell me before proceeding.",
  ].join("\n");
}

/* ---------------- prompt builders (from existing plan data) ---------------- */
function zfChangePromptBody() {
  const r = (window.STATE && STATE.buildResult) || {};
  const p = r.plan || {};
  const repo = zfRepoName();
  const request = (document.getElementById("buildRequest") && document.getElementById("buildRequest").value.trim()) || p.intent || "the requested change";
  return [
    `# Change request for ${repo}`,
    "",
    `Goal: ${request}`,
    p.estimated_change_size ? `Estimated size: ${p.estimated_change_size} · Risk: ${p.risk_level || "unknown"}` : "",
    "",
    "## Repository context",
    `- Repository: ${repo}`,
    `- Affected systems: ${zfList(p.affected_systems || p.likely_affected_subsystems).join(", ") || "none listed"}`,
    `- Entry points: ${zfList(p.entry_points).join(", ") || "none listed"}`,
    "",
    "## Files to inspect first",
    zfBullets(p.files_to_inspect_first || p.files_likely_to_modify),
    "",
    "## Implementation order",
    zfBullets(p.implementation_order),
    "",
    "## What may break (check these importers)",
    zfBullets(p.what_may_break || p.files_likely_to_break),
    "",
    "## Tests to run / add",
    zfBullets(p.tests_required || p.tests_likely_affected),
    "",
    "## Rollback plan",
    zfBullets(p.rollback_plan),
    "",
    zfTrustBlock(r) || "",
    zfSafetyFooter(),
  ].filter(l => l !== "").join("\n");
}

function zfInvestigatePromptBody() {
  const r = (window.STATE && STATE.investigateResult) || {};
  const p = r.plan || {};
  const repo = zfRepoName();
  const hyps = (p.hypotheses || []).slice(0, 4).map((h, i) =>
    `${i + 1}. ${h.title || "hypothesis"} — ${h.why_it_fits || ""} (files: ${(h.files_involved || []).join(", ") || "n/a"})`);
  return [
    `# Bug investigation for ${repo}`,
    "",
    `Symptom: ${p.symptom_summary || p.symptom || "(see below)"}`,
    "",
    "## Most likely root cause",
    `- ${p.most_likely_root_cause || p.most_likely_source || "Not localizable from the symptom alone"}`,
    "",
    "## Ranked hypotheses",
    hyps.length ? hyps.join("\n") : "- (none grounded yet)",
    "",
    "## Verification checklist",
    zfBullets(p.verification_checklist),
    "",
    "## Minimal fix strategy",
    zfBullets(p.minimal_fix_strategy),
    "",
    zfTrustBlock(r) || "",
    zfSafetyFooter(),
  ].filter(l => l !== "").join("\n");
}

function zfImpactPromptBody() {
  const r = (window.STATE && STATE.impactResult) || {};
  const repo = zfRepoName();
  return [
    `# Impact of changing ${r.target || "this module"} in ${repo}`,
    "",
    `- Risk: ${r.risk_level || "unknown"} · Confidence: ${r.confidence || "medium"}`,
    r.semantic_label ? `- Semantic target: ${r.semantic_label}` : "",
    "",
    "## Direct importers (may break)",
    zfBullets(r.direct_impact),
    "",
    "## Transitive impact",
    zfBullets(r.indirect_impact),
    "",
    "## Tests to run",
    zfBullets(r.tests_likely_affected),
    "",
    "## Verification",
    zfBullets(r.recommended_verification),
    "",
    zfTrustBlock(r) || "",
    zfSafetyFooter(),
  ].filter(l => l !== "").join("\n");
}

function zfLegacyFullPromptBody(kind) {
  if (kind === "investigate") return zfInvestigatePromptBody();
  if (kind === "impact") return zfImpactPromptBody();
  return zfChangePromptBody();
}

function zfPromptBody(kind) {
  return zfClipboardBody(kind);
}

function zfHasResult(kind) {
  if (!window.STATE) return false;
  if (kind === "investigate") return !!(STATE.investigateResult && STATE.investigateResult.ok);
  if (kind === "impact") return !!(STATE.impactResult && STATE.impactResult.ok);
  return !!(STATE.buildResult && STATE.buildResult.ok);
}

function composeAiPrompt(tool, kind) {
  const intro = `You are ${ZF_TOOL_LABEL[tool] || "an AI coding assistant"} working in this repository. Implement the plan below carefully and safely.\n\n`;
  return intro + zfSessionPrefix() + zfPromptBody(kind);
}

/* ---------------- actions ---------------- */
function copyForAi(tool, kind) {
  if (!zfHasResult(kind)) {
    if (typeof toast === "function") toast("Generate a result first", "error");
    return;
  }
  const text = composeAiPrompt(tool, kind);
  if (typeof copyText === "function") {
    copyText(text, `Copied prompt for ${ZF_TOOL_LABEL[tool] || tool}`);
    if (typeof toast === "function") {
      toast("Paste into Claude and ask it to implement step by step", "success");
    }
  }
  if (typeof applyExportNavVisibility === "function") applyExportNavVisibility();
}

function downloadAiMarkdown(kind) {
  if (!zfHasResult(kind)) {
    if (typeof toast === "function") toast("Generate a result first", "error");
    return;
  }
  const body = zfSessionPrefix() + zfPromptBody(kind);
  const repo = (zfRepoName() || "atlas").replace(/[^\w.-]+/g, "_");
  const blob = new Blob([body], { type: "text/markdown" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `atlas_${kind}_${repo}.md`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 3000);
  if (typeof toast === "function") toast("Markdown downloaded", "success");
}

function _zfEsc(s) {
  return String(s || "").replace(/</g, "&lt;");
}

/* pinned CTA shown at top of every result regardless of mode */
function pinnedCopyForClaude(kind) {
  return `<div class="pinned-copy-cta" style="display:flex;align-items:center;gap:10px;padding:10px 14px;border-radius:14px;border:1px solid rgba(109,107,255,.45);background:linear-gradient(100deg,rgba(109,107,255,.14),rgba(160,107,255,.08));margin-bottom:12px">
    <button class="btn primary" style="flex:1" type="button" onclick="copyForAi('claude','${kind}')">Copy for Claude</button>
    <button class="btn ghost small" type="button" onclick="copyForAi('cursor','${kind}')">Cursor</button>
    <button class="btn ghost small" type="button" onclick="copyForAi('codex','${kind}')">Codex</button>
  </div>`;
}

function beginnerPlanHero(plan, kind) {
  if (typeof getOutputMode === "function" && getOutputMode() === "advanced") return pinnedCopyForClaude(kind);
  const p = plan || {};
  const goal = p.change_goal || p.goal || (document.getElementById("buildRequest") && document.getElementById("buildRequest").value) || "Your change";
  const files = zfList(
    p.files_to_inspect_first || p.files_likely_to_modify
      || (p.repository_evidence && p.repository_evidence.file_evidences || []).map(function (f) { return f.path; }),
    5
  );
  const order = zfList(p.implementation_order, 5);
  return `<div class="beginner-plan-card glass" data-kind="${kind}">
    <h3 class="beginner-plan-title">Your plan</h3>
    <div class="beginner-plan-section"><span class="report-label">Goal</span><p>${_zfEsc(goal)}</p></div>
    <div class="beginner-plan-section"><span class="report-label">Files</span><ul class="clean tiny">${files.length ? files.map(f => `<li>${_zfEsc(f)}</li>`).join("") : "<li class='muted'>No files matched — try a more specific request</li>"}</ul></div>
    <div class="beginner-plan-section"><span class="report-label">Order</span><ol class="clean tiny">${order.length ? order.map(s => `<li>${_zfEsc(s)}</li>`).join("") : "<li class='muted'>No specific order suggested</li>"}</ol></div>
    ${sendToAiPanel(kind, true)}
  </div>`;
}

function beginnerInvestigateHero(plan) {
  if (typeof getOutputMode === "function" && getOutputMode() === "advanced") return pinnedCopyForClaude("investigate");
  const p = plan || {};
  const goal = p.symptom_summary || p.symptom || (document.getElementById("investigateSymptom") && document.getElementById("investigateSymptom").value) || "Your symptom";
  const hyps = (p.hypotheses || []).slice(0, 3);
  const files = zfList(hyps.flatMap(function (h) { return h.files_involved || []; }), 5);
  const order = zfList(p.verification_checklist || p.minimal_fix_strategy, 5);
  return `<div class="beginner-plan-card glass" data-kind="investigate">
    <h3 class="beginner-plan-title">Debug result</h3>
    <div class="beginner-plan-section"><span class="report-label">Symptom</span><p>${_zfEsc(goal)}</p></div>
    <div class="beginner-plan-section"><span class="report-label">Files</span><ul class="clean tiny">${files.length ? files.map(f => `<li>${_zfEsc(f)}</li>`).join("") : "<li class='muted'>Add a file path or error message for better grounding</li>"}</ul></div>
    <div class="beginner-plan-section"><span class="report-label">How to confirm</span><ol class="clean tiny">${order.length ? order.map(s => `<li>${_zfEsc(s)}</li>`).join("") : "<li class='muted'>Switch to Full detail for ranked hypotheses</li>"}</ol></div>
    ${sendToAiPanel("investigate", true)}
  </div>`;
}

function beginnerImpactHero(result) {
  if (typeof getOutputMode === "function" && getOutputMode() === "advanced") return pinnedCopyForClaude("impact");
  const r = result || {};
  const goal = r.target || (document.getElementById("impactTarget") && document.getElementById("impactTarget").value) || "This module";
  const files = zfList(r.direct_impact, 5);
  const order = zfList(r.recommended_verification || r.tests_likely_affected, 5);
  return `<div class="beginner-plan-card glass" data-kind="impact">
    <h3 class="beginner-plan-title">Impact of changing ${_zfEsc(goal.split(/[/\\]/).pop())}</h3>
    <div class="beginner-plan-section"><span class="report-label">Files that may break</span><ul class="clean tiny">${files.length ? files.map(f => `<li>${_zfEsc(f)}</li>`).join("") : "<li class='muted'>No direct importers found — this module is likely safe to change</li>"}</ul></div>
    <div class="beginner-plan-section"><span class="report-label">Verification steps</span><ol class="clean tiny">${order.length ? order.map(s => `<li>${_zfEsc(s)}</li>`).join("") : "<li class='muted'>Run tests after any change</li>"}</ol></div>
    ${sendToAiPanel("impact", true)}
  </div>`;
}

/* ---------------- the panel ---------------- */
function sendToAiPanel(kind, insideBeginner) {
  const extra = insideBeginner ? "" : `<p class="muted tiny">Includes everything Claude needs. Paste once per new chat.</p>`;
  const memNote = `<p class="muted tiny memory-export-note">Sends a compact repository summary plus this plan — not your whole codebase.</p>`;
  return `<div class="send-to-ai glass" data-kind="${kind}">
    <h3 class="send-to-ai-title">${insideBeginner ? "Copy for Claude" : "Copy for your AI tool"}</h3>
    ${extra}
    ${memNote}
    <div class="copy-row copy-row-primary">
      <button class="btn primary${insideBeginner ? " big" : " small"}" type="button" onclick="copyForAi('claude','${kind}')">Copy for Claude</button>
      <button class="btn small" type="button" onclick="copyForAi('cursor','${kind}')">Copy for Cursor</button>
      <button class="btn small" type="button" onclick="copyForAi('codex','${kind}')">Copy for Codex</button>
      <button class="btn ghost small advanced-only" type="button" onclick="downloadAiMarkdown('${kind}')">Download Markdown</button>
    </div>
    <p class="muted tiny send-to-ai-next">Paste into Claude, Cursor, or Codex and ask it to implement step by step.</p>
  </div>`;
}

function applyExportNavVisibility() {
  const btn = document.querySelector('#nav button[data-view="export"]');
  if (!btn) return;
  let done = false;
  try { done = localStorage.getItem("atlas_first_build_plan_done") === "1"; } catch (e) {}
  btn.style.display = done ? "" : "none";
}

function showHomeScanFocus() {
  document.body.classList.add("home-scan-focus");
  const banner = document.getElementById("homeScanBanner");
  if (banner) banner.style.display = "block";
  if (typeof go === "function") go("home");
  const inp = document.getElementById("repoPath");
  if (inp) setTimeout(function () { inp.focus(); }, 120);
}

function hideHomeScanFocus() {
  document.body.classList.remove("home-scan-focus");
  const banner = document.getElementById("homeScanBanner");
  if (banner) banner.style.display = "none";
}

/* ---------------- success recognition ---------------- */
function afterChangePlanSuccess() {
  const host = document.getElementById("readyState");
  if (!host) return;
  let shown = false;
  try { shown = localStorage.getItem(ZF_READY_KEY) === "1"; } catch (e) {}
  if (shown) return;
  try { localStorage.setItem(ZF_READY_KEY, "1"); } catch (e) {}
  host.innerHTML = `<div class="ready-state glass">
    <h2 class="ready-title">You're ready.</h2>
    <p class="muted">Atlas turned a request into a grounded plan. Send it to your AI coding tool and start implementing.</p>
    <div class="copy-row">
      <button class="btn primary big" type="button" onclick="copyForAi('claude','build')">Copy for Claude</button>
      <button class="btn small" type="button" onclick="copyForAi('cursor','build')">Copy for Cursor</button>
      <button class="btn small" type="button" onclick="copyForAi('codex','build')">Copy for Codex</button>
      <button class="btn ghost small" type="button" onclick="go('home')">Try on your own repository</button>
    </div>
  </div>`;
  host.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

/* ---------------- broad-folder confirmation ---------------- */
function atlasShowBroadFolderModal(warnings, onContinue) {
  let modal = document.getElementById("broadFolderModal");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "broadFolderModal";
    modal.className = "about-modal";
    document.body.appendChild(modal);
  }
  const items = (warnings || []).map(w => `<li>${String(w).replace(/</g, "&lt;")}</li>`).join("");
  modal.innerHTML = `<div class="about-card glass" onclick="event.stopPropagation()">
    <h2>That folder looks broad</h2>
    <p class="muted">Scanning a very large or mixed folder can be slow and noisy. Atlas noticed:</p>
    <ul class="clean about-list">${items}</ul>
    <p class="muted tiny">Tip: choose your project root — the folder that holds your source code.</p>
    <div class="success-buttons">
      <button class="btn ghost" type="button" id="broadFolderChoose">Choose a smaller folder</button>
      <button class="btn primary" type="button" id="broadFolderContinue">Continue anyway</button>
    </div>
  </div>`;
  modal.style.display = "grid";
  const close = () => { modal.style.display = "none"; };
  modal.onclick = close;
  modal.querySelector("#broadFolderChoose").onclick = () => { close(); if (typeof go === "function") go("home"); };
  modal.querySelector("#broadFolderContinue").onclick = () => { close(); if (typeof onContinue === "function") onContinue(); };
}

window.hideBootSplash = hideBootSplash;
window.copyForAi = copyForAi;
window.downloadAiMarkdown = downloadAiMarkdown;
window.sendToAiPanel = sendToAiPanel;
window.beginnerPlanHero = beginnerPlanHero;
window.beginnerInvestigateHero = beginnerInvestigateHero;
window.beginnerImpactHero = beginnerImpactHero;
window.zfStripClipboardMetadata = zfStripClipboardMetadata;
window.afterChangePlanSuccess = afterChangePlanSuccess;
window.atlasShowBroadFolderModal = atlasShowBroadFolderModal;
window.applyExportNavVisibility = applyExportNavVisibility;
window.showHomeScanFocus = showHomeScanFocus;
window.hideHomeScanFocus = hideHomeScanFocus;

(function zfBoot() {
  applyExportNavVisibility();
  if (document.readyState === "complete") {
    setTimeout(hideBootSplash, 200);
  } else {
    window.addEventListener("load", () => setTimeout(hideBootSplash, 200));
  }
  // Safety net: never let the splash trap the user.
  setTimeout(hideBootSplash, 4000);
})();
