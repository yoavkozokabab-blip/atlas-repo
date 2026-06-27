"use strict";
/* Product polish: first Change Plan funnel, copy, installer friction (no new intelligence). */

const FIRST_BUILD_KEY = "atlas_first_build_plan_done";
const FIRST_BUILD_PROMPT = "Add structured logging to API handlers";

function goToFirstBuildPlan() {
  if (typeof go === "function") go("build");
  const field = $("buildRequest");
  if (field && !field.value.trim()) field.value = FIRST_BUILD_PROMPT;
  if (typeof renderWorkflowQuickStarts === "function") renderWorkflowQuickStarts("build");
  setTimeout(function () {
    field && field.focus();
    if (typeof toast === "function") {
      toast("Describe your change, then click Create Change Plan", "success");
    }
  }, 200);
}

function markFirstBuildPlanDone() {
  try { localStorage.setItem(FIRST_BUILD_KEY, "1"); } catch (e) {}
  const banner = $("firstBuildBanner");
  if (banner) banner.style.display = "none";
}

function promptFirstBuildPlanAfterScan(scan) {
  if (!scan || !scan.ok) return;
  // do NOT auto-jump. Let the success screen land so the user
  // clearly sees what Atlas understood, then chooses "Generate your first
  // Change Plan" themselves.
  let done = false;
  try { done = localStorage.getItem(FIRST_BUILD_KEY) === "1"; } catch (e) {}
  if (done) return;
  if (typeof toast === "function") {
    toast("Next: click \u201cCreate your first Change Plan\u201d", "success");
  }
}

function renderScanReliabilityNotice(scan) {
  const host = $("scanReliabilityNotice");
  if (!host) return;
  const warnings = (scan && scan.health_warnings) || [];
  const rel = (scan && scan.reliability) || {};
  if (!warnings.length && !rel.degraded) {
    host.style.display = "none";
    host.innerHTML = "";
    return;
  }
  const relNote = rel.category && typeof atlasFriendlyReliability === "function"
    ? atlasFriendlyReliability(rel.category)
    : (rel.category ? String(rel.category).replace(/_/g, " ") : "Scan completed with limited coverage.");
  const items = warnings.length ? warnings : [relNote];
  host.style.display = "block";
  host.innerHTML = `<div class="product-notice warn">
    <b>Scan note</b>
    <ul class="clean tiny">${items.map(w => `<li>${escPolish(w)}</li>`).join("")}</ul>
    <p class="muted tiny">You can still run Change Plan and What breaks? — results may list fewer grounded files. Try a narrower scan scope if this is your own repo.</p>
  </div>`;
}

function friendlyValidateMessage(res) {
  const code = res && res.code;
  const map = {
    empty_path: "Enter the full path to your project folder (the root that contains your source code).",
    not_found: "That folder was not found. Check the drive letter and spelling, then click Validate.",
    not_directory: "That path is a file, not a folder. Choose the repository root directory.",
    permission_denied: "Atlas cannot read that folder. Try a path your user account owns, or run Atlas as a user with read access.",
    no_code_files: "No source files found here. Pick a folder with .py, .ts, .js, or similar — or load a sample repository first.",
    invalid: res && res.error ? String(res.error) : "That path could not be used.",
  };
  return map[code] || (res && res.error) || "That path could not be validated.";
}

function escPolish(s) {
  return String(s || "").replace(/</g, "&lt;");
}

window.goToFirstBuildPlan = goToFirstBuildPlan;
window.markFirstBuildPlanDone = markFirstBuildPlanDone;
window.promptFirstBuildPlanAfterScan = promptFirstBuildPlanAfterScan;
window.renderScanReliabilityNotice = renderScanReliabilityNotice;
window.friendlyValidateMessage = friendlyValidateMessage;
