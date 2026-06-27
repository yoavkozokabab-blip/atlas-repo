"use strict";
/* trust signals, output detail level, and SmartScreen guidance.
 *
 * UI-only. No changes to intelligence, semantic resolver, benchmarks, billing,
 * or the marketing site. Every Change Plan / Debug / What-breaks result
 * gets a consistent "Why Atlas believes this" block (evidence + confidence +
 * reason), and the user can switch between Simple and Full detail output.
 */

const OUTPUT_MODE_KEY = "atlas_output_mode_v157";
const UNSIGNED_APP_KEY = "atlas_unsigned_app_ack_v157";

/* ---------------- Beginner / Advanced output mode ---------------- */
function getOutputMode() {
  try {
    const m = localStorage.getItem(OUTPUT_MODE_KEY);
    if (m === "beginner" || m === "advanced") return m;
  } catch (e) {}
  return "beginner";
}

function applyOutputMode(mode) {
  document.body.classList.remove("mode-beginner", "mode-advanced");
  document.body.classList.add(mode === "advanced" ? "mode-advanced" : "mode-beginner");
  document.querySelectorAll("#modeToggle button").forEach(function (b) {
    b.classList.toggle("active", b.dataset.mode === mode);
  });
}

function setOutputMode(mode) {
  const next = mode === "advanced" ? "advanced" : "beginner";
  try { localStorage.setItem(OUTPUT_MODE_KEY, next); } catch (e) {}
  applyOutputMode(next);
  if (typeof toast === "function") {
    toast(next === "advanced" ? "Full detail view" : "Simple view", "success");
  }
}

/* ---------------- Confidence ---------------- */
function tzNormalizeConfidence(raw) {
  const s = String(raw || "").toLowerCase();
  if (s.includes("high")) return "high";
  if (s.includes("low")) return "low";
  return "medium";
}

function tzConfidence(kind) {
  if (!window.STATE) return "medium";
  if (kind === "build") return tzNormalizeConfidence((STATE.buildResult || {}).plan && STATE.buildResult.plan.confidence);
  if (kind === "investigate") return tzNormalizeConfidence((STATE.investigateResult || {}).plan && STATE.investigateResult.plan.confidence);
  if (kind === "impact") return tzNormalizeConfidence((STATE.impactResult || {}).confidence);
  return "medium";
}

/* ---------------- Evidence (files / symbols / references) ---------------- */
function _uniq(arr) {
  return [...new Set((arr || []).filter(Boolean))];
}

function _evidenceSymbols(rev) {
  if (!rev || !rev.file_evidences) return [];
  const out = [];
  rev.file_evidences.forEach(function (f) {
    (f.matching_symbols || []).forEach(function (s) { out.push(s); });
  });
  return out;
}

function tzEvidence(kind) {
  const S = window.STATE || {};
  if (kind === "build") {
    const p = (S.buildResult || {}).plan || {};
    const rev = p.repository_evidence || (p.domain_knowledge || {}).repository_evidence || {};
    return {
      files: _uniq(p.files_to_inspect_first || p.files_likely_to_modify || (rev.file_evidences || []).map(function (f) { return f.path; })),
      symbols: _uniq(_evidenceSymbols(rev)),
      references: _uniq(p.what_may_break || p.affected_systems || p.likely_affected_subsystems),
    };
  }
  if (kind === "investigate") {
    const p = (S.investigateResult || {}).plan || {};
    const rev = p.repository_evidence || (p.domain_knowledge || {}).repository_evidence || {};
    const files = [];
    (p.hypotheses || []).forEach(function (h) { (h.files_involved || []).forEach(function (f) { files.push(f); }); });
    const refs = [];
    (p.hypotheses || []).forEach(function (h) { (h.evidence || []).forEach(function (e) { refs.push(e); }); });
    return {
      files: _uniq(files.length ? files : (rev.file_evidences || []).map(function (f) { return f.path; })),
      symbols: _uniq(_evidenceSymbols(rev)),
      references: _uniq(refs).slice(0, 6),
    };
  }
  if (kind === "impact") {
    const r = S.impactResult || {};
    const syms = (r.resolved_symbols || []).map(function (s) { return typeof s === "string" ? s : (s.qualname || s.name); });
    return {
      files: _uniq(r.resolved_modules && r.resolved_modules.length ? r.resolved_modules : r.direct_impact),
      symbols: _uniq(syms),
      references: _uniq(r.direct_impact),
    };
  }
  return { files: [], symbols: [], references: [] };
}

/* ---------------- Reason (why Atlas believes the result) ---------------- */
function tzReason(kind) {
  const ev = tzEvidence(kind);
  const conf = tzConfidence(kind);
  const nf = ev.files.length, ns = ev.symbols.length, nr = ev.references.length;
  if (kind === "build") {
    return `Atlas matched your request to ${nf} file(s)` +
      (ns ? ` and ${ns} symbol(s)` : "") +
      ` using file names, code roles, and the dependency graph, then ranked them by relevance. Confidence is ${conf} because ` +
      (conf === "high" ? "several independent signals agreed." : conf === "low" ? "few grounded signals matched — treat this as a lead." : "some signals matched but evidence is partial.");
  }
  if (kind === "investigate") {
    const nh = ((window.STATE || {}).investigateResult || {}).plan ? (STATE.investigateResult.plan.hypotheses || []).length : 0;
    return `Atlas ranked ${nh} hypothesis(es) from your symptom and grounded them in ${nf} file(s)` +
      (ns ? ` and ${ns} symbol(s)` : "") +
      `. Confidence is ${conf}; each hypothesis lists how to confirm or disprove it.`;
  }
  if (kind === "impact") {
    if (typeof window.impactArchSummary === "function" && (window.STATE || {}).impactResult) {
      return window.impactArchSummary(STATE.impactResult);
    }
    return `Atlas followed the dependency graph from your target to ${nr} direct importer(s) that may break. Confidence is ${conf}.`;
  }
  return "";
}

/* ---------------- The trust block ---------------- */
function _tagList(items, cls) {
  if (!items || !items.length) return '<span class="muted tiny">none</span>';
  return items.slice(0, 12).map(function (x) {
    return `<span class="tag ${cls || ""}">${String(x).replace(/</g, "&lt;")}</span>`;
  }).join("");
}

function trustBlock(kind) {
  const conf = tzConfidence(kind);
  const ev = tzEvidence(kind);
  const reason = tzReason(kind);
  return `<div class="trust-block glass" data-kind="${kind}">
    <div class="trust-head">
      <span class="trust-title">Why Atlas believes this</span>
      <span class="conf-badge conf-${conf}">${conf} confidence</span>
    </div>
    <p class="trust-reason">${String(reason).replace(/</g, "&lt;")}</p>
    <div class="trust-evidence advanced-only">
      <div class="trust-ev-row"><span class="trust-ev-label">Files</span><div class="taglist">${_tagList(ev.files)}</div></div>
      <div class="trust-ev-row"><span class="trust-ev-label">Symbols</span><div class="taglist">${_tagList(ev.symbols, "sym")}</div></div>
      <div class="trust-ev-row"><span class="trust-ev-label">References</span><div class="taglist">${_tagList(ev.references)}</div></div>
    </div>
    <p class="trust-ev-hint beginner-only muted tiny">Switch to <b>Full detail</b> (top bar) to see the exact files, symbols, and references behind this result.</p>
  </div>`;
}

/* ---------------- SmartScreen / unsigned first-launch notice ---------------- */
function _isWindows() {
  return /windows/i.test(navigator.userAgent || "") || /win/i.test(navigator.platform || "");
}

function showUnsignedAppNotice(force) {
  let acked = false;
  try { acked = localStorage.getItem(UNSIGNED_APP_KEY) === "1"; } catch (e) {}
  if (acked && !force) return;
  if (!_isWindows() && !force) { try { localStorage.setItem(UNSIGNED_APP_KEY, "1"); } catch (e) {} return; }
  let modal = document.getElementById("unsignedAppModal");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "unsignedAppModal";
    modal.className = "about-modal";
    document.body.appendChild(modal);
  }
  modal.innerHTML = `<div class="about-card glass" onclick="event.stopPropagation()">
    <p class="onboard-eyebrow">First launch</p>
    <h2>Atlas is an unsigned application</h2>
    <p class="muted">Atlas is not yet code-signed with a paid certificate, so Windows may show a
      blue <b>SmartScreen</b> warning the first time you run it. This is expected for new, unsigned software — it is
      not a sign that anything is wrong.</p>
    <h3>Why Windows shows this</h3>
    <ul class="clean about-list muted">
      <li>SmartScreen flags applications it has not seen from a known publisher.</li>
      <li>SmartScreen reputation improves as more people install and run the app.</li>
    </ul>
    <h3>How to continue safely</h3>
    <ul class="clean about-list">
      <li>Only run Atlas from a copy you downloaded yourself from the official source.</li>
      <li>If SmartScreen appears, click <b>More info</b> &rarr; <b>Run anyway</b>.</li>
      <li>Atlas runs entirely on your machine and does not upload your source code.</li>
    </ul>
    <div class="success-buttons">
      <button class="btn primary" type="button" id="unsignedAppAck">I understand — continue</button>
    </div>
  </div>`;
  modal.style.display = "grid";
  const close = function () {
    modal.style.display = "none";
    try { localStorage.setItem(UNSIGNED_APP_KEY, "1"); } catch (e) {}
  };
  modal.onclick = close;
  const btn = modal.querySelector("#unsignedAppAck");
  if (btn) btn.onclick = close;
}

window.setOutputMode = setOutputMode;
window.trustBlock = trustBlock;
window.tzConfidence = tzConfidence;
window.showUnsignedAppNotice = showUnsignedAppNotice;

(function trustBoot() {
  applyOutputMode(getOutputMode());
  // Show the unsigned-app notice once, after the welcome screen has had a chance
  // to render, so first-time Windows users understand the SmartScreen prompt.
  setTimeout(function () { showUnsignedAppNotice(false); }, 1200);
})();
