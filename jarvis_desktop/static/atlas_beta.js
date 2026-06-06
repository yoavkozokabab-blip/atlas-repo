"use strict";
/* Phase 141 — private beta launch: feedback, exports, walkthrough, diagnostics, about */

const WF_FEEDBACK_KEY = "atlas_workflow_feedback";
const WELCOME_KEY = "atlas_welcome_v141_done";
const GUIDED_TOUR_KEY = "atlas_guided_walkthrough_v141_done";

function listWorkflowFeedback() {
  try { return JSON.parse(localStorage.getItem(WF_FEEDBACK_KEY) || "[]"); } catch (e) { return []; }
}

function saveWorkflowFeedback(workflow, vote, meta) {
  const entry = {
    workflow,
    vote,
    meta: meta || {},
    repo: (STATE.summary && STATE.summary.repo_name) || "",
    ts: new Date().toISOString(),
  };
  const list = listWorkflowFeedback();
  list.push(entry);
  try { localStorage.setItem(WF_FEEDBACK_KEY, JSON.stringify(list.slice(-200))); } catch (e) {}
  return list.length;
}

function workflowFeedbackHtml(workflow) {
  const id = `wfFb_${workflow}`;
  return `<div class="workflow-feedback" id="${id}" data-workflow="${workflow}">
    <span class="muted tiny">Was this helpful?</span>
    <button type="button" class="btn small ghost wf-up" title="Helpful" onclick="voteWorkflowFeedback('${workflow}', 'up')">👍</button>
    <button type="button" class="btn small ghost wf-down" title="Not helpful" onclick="voteWorkflowFeedback('${workflow}', 'down')">👎</button>
    <span class="wf-thanks muted tiny" style="display:none">Thanks — saved locally.</span>
  </div>`;
}

function voteWorkflowFeedback(workflow, vote) {
  const meta = {};
  if (workflow === "build" && STATE.buildResult) meta.request = ($("buildRequest") && $("buildRequest").value) || "";
  if (workflow === "investigate" && STATE.investigateResult) meta.symptom = ($("investigateSymptom") && $("investigateSymptom").value) || "";
  if (workflow === "impact" && STATE.impactResult) meta.target = STATE.impactResult.target || "";
  saveWorkflowFeedback(workflow, vote, meta);
  const host = document.querySelector(`.workflow-feedback[data-workflow="${workflow}"]`);
  if (host) {
    host.querySelectorAll("button").forEach(b => { b.disabled = true; });
    const thanks = host.querySelector(".wf-thanks");
    if (thanks) thanks.style.display = "inline";
  }
  if (typeof toast === "function") toast("Feedback saved locally", "success");
}

function impactResultMarkdown(r) {
  if (!r || !r.ok) return "";
  const lines = [
    `# Impact: ${r.target || ""}`,
    "",
    `- Risk: ${r.risk_level || "unknown"}`,
    `- Confidence: ${r.confidence || "medium"}`,
    r.semantic_label ? `- Semantic target: ${r.semantic_label}` : "",
    "",
    "## Direct impact",
    ...((r.direct_impact || []).map(f => `- ${f}`)),
    "",
    "## Indirect impact",
    ...((r.indirect_impact || []).map(f => `- ${f}`)),
    "",
    "## Tests to run",
    ...((r.tests_likely_affected || []).map(t => `- ${t}`)),
    "",
    "## Verification",
    ...((r.recommended_verification || []).map(v => `- ${v}`)),
  ];
  return lines.filter((l, i, a) => !(l === "" && a[i + 1] === "")).join("\n");
}

function buildWorkflowMarkdownBundle() {
  const parts = [
    "# Atlas workflow export",
    "",
    `Generated: ${new Date().toISOString()}`,
    `Repository: ${(STATE.summary && STATE.summary.repo_name) || "—"}`,
    "",
  ];
  if (STATE.buildResult && STATE.buildResult.ok) {
    parts.push("---", "", "## Build Plan", "", STATE.buildResult.formatted || "(no markdown body)", "");
  } else {
    parts.push("## Build Plan", "", "_Not generated in this session._", "");
  }
  if (STATE.investigateResult && STATE.investigateResult.ok) {
    parts.push("---", "", "## Investigation", "", STATE.investigateResult.formatted || "(no markdown body)", "");
  } else {
    parts.push("## Investigation", "", "_Not generated in this session._", "");
  }
  if (STATE.impactResult && STATE.impactResult.ok) {
    parts.push("---", "", impactResultMarkdown(STATE.impactResult), "");
  } else {
    parts.push("## Impact", "", "_Not generated in this session._", "");
  }
  return parts.join("\n");
}

function downloadWorkflowMarkdownBundle() {
  const text = buildWorkflowMarkdownBundle();
  const repo = ((STATE.summary && STATE.summary.repo_name) || "atlas").replace(/[^\w.-]+/g, "_");
  const blob = new Blob([text], { type: "text/markdown" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `atlas_workflows_${repo}_${new Date().toISOString().slice(0, 10)}.md`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 3000);
  if (typeof toast === "function") toast("Markdown bundle downloaded", "success");
}

async function copyBetaDiagnostics() {
  const diag = await api("/api/system/diagnostics");
  const text = JSON.stringify(diag, null, 2);
  if (typeof copyText === "function") {
    await copyText(text, "Diagnostics copied");
  } else {
    try { await navigator.clipboard.writeText(text); } catch (e) {}
    if (typeof toast === "function") toast("Diagnostics copied", "success");
  }
}

function showAboutAtlas() {
  let modal = $("aboutAtlasModal");
  if (!modal) return;
  modal.style.display = "grid";
}

function closeAboutAtlas() {
  const modal = $("aboutAtlasModal");
  if (modal) modal.style.display = "none";
}

async function openReportIssue() {
  const ctx = await collectIssueContext();
  if (window.JarvisFeedback && typeof JarvisFeedback.openReportIssue === "function") {
    JarvisFeedback.openReportIssue(ctx);
    return;
  }
  if (window.JarvisFeedback && typeof JarvisFeedback.open === "function") {
    JarvisFeedback.open("bug");
    return;
  }
  if (typeof toast === "function") toast("Report Issue unavailable — reload the app", "error");
}

async function collectIssueContext() {
  let diag = {};
  try { diag = await api("/api/system/diagnostics"); } catch (e) { diag = { ok: false }; }
  return {
    view: (document.querySelector(".view.active") || {}).id || "",
    repo: (STATE.summary && STATE.summary.repo_name) || "",
    diagnostics: diag,
  };
}

function dismissWelcomeScreen(goHome) {
  try {
    localStorage.setItem(WELCOME_KEY, "1");
    localStorage.setItem("atlas_onboarding_v2_done", "1");
  } catch (e) {}
  const w = $("welcomeScreen");
  if (w) w.style.display = "none";
  const ob = $("onboarding");
  if (ob) ob.style.display = "none";
  if (goHome !== false && typeof go === "function") go("home");
}

function welcomeScanMyRepo() {
  dismissWelcomeScreen(false);
  if (typeof showHomeScanFocus === "function") showHomeScanFocus();
  else if (typeof go === "function") go("home");
}

function welcomeLoadSample() {
  dismissWelcomeScreen(false);
  if (typeof onboardingLoadSample === "function") onboardingLoadSample();
  else if (typeof loadDemoMode === "function") loadDemoMode("small");
}

function welcomeStartWalkthrough() {
  dismissWelcomeScreen(false);
  startGuidedWalkthrough();
}

function maybeShowWelcomeScreen() {
  try {
    if (localStorage.getItem(WELCOME_KEY) === "1") return;
  } catch (e) {}
  const w = $("welcomeScreen");
  if (w) w.style.display = "grid";
}

const GUIDED_STEPS = [
  { title: "Welcome", text: "Atlas prepares grounded Build Plans for your AI tools. It maps code locally and does not write patches for you.", action: null },
  { title: "Sample repository", text: "We'll load a small bundled codebase so you can explore without cloning anything.", action: "load_sample" },
  { title: "Repository Map", text: "The 3D map shows modules, dependencies, and architectural risk. Click nodes to inspect them.", view: "center", action: "wait_map" },
  { title: "Your first Build Plan", text: "We will load a sample repo and generate a plan — affected files, order, and tests. You implement the change (or paste the export into Claude/Cursor).", view: "build", action: "build_example" },
  { title: "Investigate", text: "Paste a symptom or traceback. Atlas ranks hypotheses and verification steps.", view: "investigate", action: "investigate_example" },
  { title: "Impact", text: "Enter a file or module to see blast radius before you edit.", view: "impact", action: "impact_example" },
  { title: "Export", text: "Download Build, Investigation, and Impact as one markdown file, or copy AI context packets.", view: "export", action: null },
  { title: "You're ready", text: "Scan your own repository from Home, or keep exploring the sample. Use Report Issue if something breaks.", action: "done" },
];

let _guidedIndex = 0;
let _guidedActive = false;

function setGuidedStep(i) {
  const step = GUIDED_STEPS[i];
  if (!step) return;
  $("guidedTourStep").textContent = `Step ${i + 1} / ${GUIDED_STEPS.length}`;
  $("guidedTourTitle").textContent = step.title;
  $("guidedTourText").textContent = step.text;
  const panel = $("guidedWalkthroughPanel");
  if (panel) panel.style.display = "block";
}

function stopGuidedWalkthrough() {
  _guidedActive = false;
  const panel = $("guidedWalkthroughPanel");
  if (panel) panel.style.display = "none";
  try { localStorage.setItem(GUIDED_TOUR_KEY, "1"); } catch (e) {}
}

async function runGuidedAction(action) {
  if (action === "load_sample") {
    if (typeof loadDemoMode === "function") await loadDemoMode("small");
    return;
  }
  if (action === "wait_map") {
    if (typeof go === "function") go("center");
    if (typeof renderCenter === "function") await renderCenter();
    return;
  }
  if (action === "build_example") {
    if (typeof go === "function") go("build");
    const field = $("buildRequest");
    if (field) field.value = "Add structured logging to API handlers";
    if (typeof runChangePlan === "function") await runChangePlan();
    return;
  }
  if (action === "investigate_example") {
    if (typeof go === "function") go("investigate");
    const field = $("investigateSymptom");
    if (field) field.value = "API requests fail intermittently under load";
    if (typeof runInvestigationPlan === "function") await runInvestigationPlan();
    return;
  }
  if (action === "impact_example") {
    const hub = (STATE.summary && STATE.summary.top_hubs && STATE.summary.top_hubs[0]) || {};
    const target = hub.path || hub.module || "core/hub.py";
    if (typeof go === "function") go("impact");
    const field = $("impactTarget");
    if (field) field.value = target;
    if (typeof runImpact === "function") await runImpact();
    return;
  }
}

async function guidedWalkthroughNext() {
  if (!_guidedActive) return;
  const step = GUIDED_STEPS[_guidedIndex];
  if (step && step.view && typeof go === "function") go(step.view);
  if (step && step.action) await runGuidedAction(step.action);
  _guidedIndex += 1;
  if (_guidedIndex >= GUIDED_STEPS.length) {
    stopGuidedWalkthrough();
    if (typeof toast === "function") toast("Guided walkthrough complete", "success");
    return;
  }
  setGuidedStep(_guidedIndex);
}

function startGuidedWalkthrough() {
  if (_guidedActive) return;
  _guidedActive = true;
  _guidedIndex = 0;
  dismissWelcomeScreen(false);
  if (typeof dismissOnboarding === "function") dismissOnboarding(true);
  setGuidedStep(0);
}

window.voteWorkflowFeedback = voteWorkflowFeedback;
window.downloadWorkflowMarkdownBundle = downloadWorkflowMarkdownBundle;
window.copyBetaDiagnostics = copyBetaDiagnostics;
window.showAboutAtlas = showAboutAtlas;
window.closeAboutAtlas = closeAboutAtlas;
window.openReportIssue = openReportIssue;
window.dismissWelcomeScreen = dismissWelcomeScreen;
window.welcomeLoadSample = welcomeLoadSample;
window.welcomeStartWalkthrough = welcomeStartWalkthrough;
window.welcomeScanMyRepo = welcomeScanMyRepo;
window.startGuidedWalkthrough = startGuidedWalkthrough;
window.stopGuidedWalkthrough = stopGuidedWalkthrough;
window.guidedWalkthroughNext = guidedWalkthroughNext;
window.maybeShowWelcomeScreen = maybeShowWelcomeScreen;

(function phase141Boot() {
  try {
    if (localStorage.getItem(WELCOME_KEY) !== "1") {
      maybeShowWelcomeScreen();
    }
  } catch (e) {
    maybeShowWelcomeScreen();
  }
})();
