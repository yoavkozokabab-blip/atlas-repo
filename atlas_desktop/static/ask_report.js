/* =============================================================================
   Atlas — Ask Atlas report renderer  (presentation only)
   -----------------------------------------------------------------------------
   Scoped entirely to the Ask Atlas view. Overrides the Ask-specific globals
   (`renderCopilotAnswer`, plus a staged-loading and empty-state enhancement)
   defined in app.js by reassigning them AFTER app.js has loaded. It consumes the
   existing /api/copilot/ask response shape verbatim — no backend, routing,
   scanning, or shared-renderer changes. If anything is missing or malformed it
   degrades to the plain answer, never throwing.

   Response shape consumed (all optional / defensively read):
     res: { ok, mode, answer, evidence:[str], files:[str], risk_level,
            confidence, suggested_action, limitations:[str], graph_highlight,
            comparison:{concept_a,concept_b,shared_modules,only_a,only_b},
            semantic_label, architectural_blast_radius, direct_impact:[],
            indirect_impact:[], risky_areas:[], safe_areas:[], report:{…} }
     res.report: { executive_summary, direction:{title,items:[{label,value}]},
            confidence:{level,evidence_strength,reason}, evidence:[{signal,
            why_it_matters}], ranked_files:[{path,why,risk,action}],
            cannot_conclude:[str], next_action, reasoning }
   ============================================================================ */
(function () {
  "use strict";

  var g = window;
  function esc(s) {
    if (g.esc) return g.esc(s);
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function toast(m, k) { try { if (g.toast) g.toast(m, k); } catch (e) {} }
  function $(id) { return document.getElementById(id); }
  function lvl(v) { return String(v == null ? "" : v).trim().toLowerCase(); }
  function arr(v) { return Array.isArray(v) ? v : []; }
  function pad2(n) { return (n < 10 ? "0" : "") + n; }

  /* ---- quick-open: copy the path so it can be pasted into an editor/agent ----
     Atlas is a companion to coding agents; there is no OS file-open without a
     backend change, so "quick open" = copy the exact path (honest + useful). */
  g.askCopyPath = function (path, label) {
    if (!path) return;
    if (g.copyText) g.copyText(path, label || "Path copied — paste into your editor");
    else if (navigator.clipboard) navigator.clipboard.writeText(path).then(function () { toast("Path copied"); });
    else toast(path);
  };
  g.askCopyReport = function () {
    var r = g.STATE && g.STATE.copilotResult;
    var txt = (r && (r.formatted || (r.report && r.report.copy_prompt) || r.answer)) || "";
    if (!txt) { toast("Nothing to copy"); return; }
    if (g.copyText) g.copyText(txt, "Analysis copied for your agent");
    else if (navigator.clipboard) navigator.clipboard.writeText(txt).then(function () { toast("Analysis copied"); });
  };

  /* ---- evidence parsing: split "path.py: symA, symB" or `path` into parts ---- */
  function parseEvidence(signal) {
    var s = String(signal == null ? "" : signal).trim();
    var file = "", symbol = "", why = s;
    var m = s.match(/^`?([\w./\\@\-]+\.[A-Za-z]{1,6})`?\s*[:\-–]\s*(.+)$/);
    if (m) { file = m[1]; symbol = m[2].replace(/`/g, ""); why = symbol; return { file: file, symbol: symbol, why: why }; }
    var bt = s.match(/`([^`]+)`/);
    if (bt && /[\/.]/.test(bt[1]) && /\.[A-Za-z]{1,6}$/.test(bt[1])) {
      file = bt[1];
      why = s.replace(/`[^`]+`/, "").replace(/^[\s:–\-]+/, "").trim();
      symbol = "";
      return { file: file, symbol: symbol, why: why || s };
    }
    return { file: "", symbol: "", why: s };
  }
  function firstPath(res) {
    var f = arr(res.files)[0];
    if (typeof f === "string") return f;
    if (f && f.path) return f.path;
    return "";
  }

  /* -------------------------------------------------------------------------
     Section builders — each returns an HTML string ("" when not applicable).
     ---------------------------------------------------------------------- */

  // 1. Executive summary
  function execHtml(res, report) {
    var summary = (report && report.executive_summary) || res.answer || "";
    if (!summary) return "";
    return '<section class="axr-block axr-exec"><p class="axr-summary">' + esc(summary) + "</p></section>";
  }

  // 2. Verdict — confidence + risk, plainly stated
  function verdictHtml(res, report) {
    var conf = lvl((report && report.confidence && report.confidence.level) || res.confidence || "");
    var risk = lvl(res.risk_level || "");
    var strength = (report && report.confidence && report.confidence.evidence_strength) || "";
    var reason = (report && report.confidence && report.confidence.reason) || "";
    if (!conf && !risk) return "";
    var confClass = conf === "high" ? "is-high" : conf === "low" ? "is-low" : "is-med";
    var riskClass = risk === "high" ? "is-high" : risk === "medium" ? "is-med" : risk === "low" ? "is-low" : "is-unknown";
    var pills = "";
    if (conf) pills += '<span class="axr-verdict-pill conf ' + confClass + '"><span class="axr-dot"></span>' + esc(cap(conf)) + " confidence</span>";
    var showRisk = risk && (risk !== "unknown");
    if (showRisk || res.mode === "impact") {
      pills += '<span class="axr-verdict-pill risk ' + riskClass + '"><span class="axr-dot"></span>' + esc(cap(risk || "unknown")) + " risk</span>";
    }
    var meta = strength ? '<span class="axr-verdict-meta">' + esc(cap(strength)) + " evidence</span>" : "";
    var detail = reason ? '<details class="axr-reason"><summary>Why this verdict</summary><p>' + esc(reason) + "</p></details>" : "";
    return '<section class="axr-block axr-verdict-block"><div class="axr-verdict">' + pills + meta + "</div>" + detail + "</section>";
  }

  // 3. Key findings — 3–8 bullets from the structured direction items
  function findingsHtml(res, report) {
    if (res.mode === "comparison") return ""; // shown as shared/different below
    var items = (report && report.direction && arr(report.direction.items)) || [];
    var bullets = [];
    items.forEach(function (it) {
      var label = it && it.label ? String(it.label) : "";
      var value = it && it.value ? String(it.value) : (typeof it === "string" ? it : "");
      if (!value) return;
      if (label && label.toLowerCase() !== "finding") bullets.push("<strong>" + esc(label) + ".</strong> " + esc(value));
      else bullets.push(esc(value));
    });
    if (!bullets.length) return "";
    bullets = bullets.slice(0, 8);
    return section("Key findings",
      '<ul class="axr-findings">' + bullets.map(function (b) { return "<li>" + b + "</li>"; }).join("") + "</ul>");
  }

  // 4. Evidence — clickable cards (file · symbol · why · quick open)
  function evidenceHtml(res, report) {
    var raw = (report && arr(report.evidence)) || [];
    var list = raw.length ? raw.map(function (e) {
      if (typeof e === "string") { var p = parseEvidence(e); return { file: p.file, symbol: p.symbol, why: p.why, signal: e }; }
      var pe = parseEvidence(e.signal || "");
      return { file: pe.file, symbol: pe.symbol || "", why: (e.why_it_matters || pe.why || e.signal || ""), signal: e.signal || "" };
    }) : arr(res.evidence).map(function (s) { var p = parseEvidence(s); return { file: p.file, symbol: p.symbol, why: p.why, signal: s }; });
    list = list.filter(function (x) { return x.why || x.file || x.symbol; });
    if (!list.length) return "";
    var strong = list.slice(0, 3);
    var rest = list.slice(3, 8);
    function card(e) {
      var head = e.file
        ? '<span class="axr-ev-file mono">' + esc(e.file) + "</span>"
        : '<span class="axr-ev-file axr-ev-file--none">Signal</span>';
      var sym = e.symbol && e.symbol !== e.why ? '<span class="axr-ev-sym mono">' + esc(clip(e.symbol, 60)) + "</span>" : "";
      var open = e.file
        ? '<button type="button" class="axr-open" data-path="' + esc(e.file) + '" aria-label="Copy path ' + esc(e.file) + '">Copy path</button>'
        : "";
      return '<div class="axr-ev-card"><div class="axr-ev-head">' + head + sym + "</div>" +
        '<p class="axr-ev-why">' + esc(e.why) + "</p>" + open + "</div>";
    }
    var body = '<div class="axr-ev-grid">' + strong.map(card).join("") + "</div>";
    if (rest.length) {
      body += '<details class="axr-more"><summary>' + rest.length + " more evidence item" + (rest.length > 1 ? "s" : "") +
        '</summary><div class="axr-ev-grid axr-ev-grid--more">' + rest.map(card).join("") + "</div></details>";
    }
    return section("Evidence", body);
  }

  // 5. Relevant files — ranked cards (importance · reason · quick open)
  function filesHtml(res, report) {
    var ranked = (report && arr(report.ranked_files)) || [];
    if (!ranked.length) {
      ranked = arr(res.files).map(function (f) {
        return typeof f === "string" ? { path: f } : f;
      });
    }
    ranked = ranked.filter(function (f) { return f && f.path; });
    if (!ranked.length) return "";
    var top = ranked.slice(0, 4);
    var rest = ranked.slice(4, 12);
    function card(f, i) {
      var risk = lvl(f.risk);
      var tag = f.risk ? '<span class="axr-tag risk-' + (risk || "unknown") + '">' + esc(cap(f.risk)) + " risk</span>" : "";
      var why = f.why ? '<p class="axr-file-why">' + esc(f.why) + "</p>" : "";
      return '<li class="axr-file-card"><span class="axr-file-rank">' + pad2(i + 1) + "</span>" +
        '<div class="axr-file-body"><div class="axr-file-path mono">' + esc(f.path) + "</div>" + why +
        (tag ? '<div class="axr-file-meta">' + tag + "</div>" : "") + "</div>" +
        '<button type="button" class="axr-open axr-file-open" data-path="' + esc(f.path) + '" aria-label="Copy path ' + esc(f.path) + '">Copy</button></li>';
    }
    var body = '<ol class="axr-files">' + top.map(card).join("") + "</ol>";
    if (rest.length) {
      body += '<details class="axr-more"><summary>' + rest.length + " more file" + (rest.length > 1 ? "s" : "") +
        '</summary><ol class="axr-files" start="5">' + rest.map(function (f, i) { return card(f, i + 4); }).join("") + "</ol></details>";
    }
    return section("Relevant files", body);
  }

  // 6a. Comparison — shared / different / missing evidence
  function comparisonHtml(res, report) {
    if (res.mode !== "comparison") return "";
    var c = res.comparison || {};
    var a = c.concept_a || "A", b = c.concept_b || "B";
    var shared = arr(c.shared_modules);
    var onlyA = arr(c.only_a), onlyB = arr(c.only_b);
    var items = (report && report.direction && arr(report.direction.items)) || [];
    var sharedText = items.filter(function (x) { return (x.label || "").toLowerCase() === "shared"; }).map(function (x) { return x.value; });
    var diffText = items.filter(function (x) { return (x.label || "").toLowerCase() === "different"; }).map(function (x) { return x.value; });
    var missing = (report && arr(report.cannot_conclude)) || arr(res.limitations);
    function chips(list) { return list.length ? '<div class="axr-chips">' + list.map(function (m) { return '<span class="axr-chip mono">' + esc(m) + "</span>"; }).join("") + "</div>" : ""; }
    function notes(list) { return list.length ? '<ul class="axr-cmp-notes">' + list.map(function (t) { return "<li>" + esc(t) + "</li>"; }).join("") + "</ul>" : ""; }
    var col1 = '<div class="axr-cmp-col axr-cmp-shared"><div class="axr-cmp-h">Shared logic</div>' +
      (shared.length || sharedText.length ? notes(sharedText) + chips(shared) : '<p class="axr-cmp-empty">No shared modules resolved.</p>') + "</div>";
    var col2 = '<div class="axr-cmp-col axr-cmp-diff"><div class="axr-cmp-h">Different logic</div>' +
      notes(diffText) +
      (onlyA.length ? '<div class="axr-cmp-side"><span class="axr-cmp-side-l">' + esc(clip(a, 28)) + " only</span>" + chips(onlyA) + "</div>" : "") +
      (onlyB.length ? '<div class="axr-cmp-side"><span class="axr-cmp-side-l">' + esc(clip(b, 28)) + " only</span>" + chips(onlyB) + "</div>" : "") +
      (!diffText.length && !onlyA.length && !onlyB.length ? '<p class="axr-cmp-empty">No divergent modules resolved.</p>' : "") + "</div>";
    var col3 = '<div class="axr-cmp-col axr-cmp-missing"><div class="axr-cmp-h">Missing evidence</div>' +
      (missing.length ? notes(missing) : '<p class="axr-cmp-empty">Nothing flagged.</p>') + "</div>";
    return section("Dependency relationships", '<div class="axr-cmp">' + col1 + col2 + col3 + "</div>");
  }

  // 6b. Impact — a compact risk dashboard
  function riskDashboardHtml(res) {
    if (res.mode !== "impact") return "";
    var direct = arr(res.direct_impact).length;
    var indirect = arr(res.indirect_impact).length;
    var blast = res.architectural_blast_radius;
    if (blast == null) blast = direct + indirect;
    var risk = lvl(res.risk_level || "unknown");
    var conf = lvl(res.confidence || "medium");
    var mods = arr(res.files).slice(0, 12);
    var risky = arr(res.risky_areas).slice(0, 6);
    function tile(label, value, cls) {
      return '<div class="axr-stat ' + (cls || "") + '"><div class="axr-stat-v">' + esc(value) + '</div><div class="axr-stat-l">' + esc(label) + "</div></div>";
    }
    var grid = '<div class="axr-riskgrid">' +
      tile("Risk", cap(risk || "unknown"), "risk-" + (risk || "unknown")) +
      tile("Blast radius", String(blast) + " module" + (blast === 1 ? "" : "s"), "") +
      tile("Direct importers", String(direct), "") +
      tile("Confidence", cap(conf), "conf-" + (conf || "medium")) + "</div>";
    var modsHtml = mods.length
      ? '<div class="axr-risk-mods"><div class="axr-sub-l">Affected modules</div><div class="axr-chips">' +
        mods.map(function (m) { var p = typeof m === "string" ? m : (m.path || ""); return '<span class="axr-chip mono">' + esc(p) + "</span>"; }).join("") + "</div></div>"
      : "";
    var riskyHtml = risky.length
      ? '<div class="axr-risk-mods"><div class="axr-sub-l">Highest-risk areas</div><div class="axr-chips">' +
        risky.map(function (m) { return '<span class="axr-chip axr-chip--warn mono">' + esc(typeof m === "string" ? m : (m.path || m.name || "")) + "</span>"; }).join("") + "</div></div>"
      : "";
    return section("Blast radius", grid + modsHtml + riskyHtml);
  }

  // 7. Unknowns — explicit limits in the available repository evidence
  function unknownsHtml(res, report) {
    if (res.mode === "comparison") return ""; // surfaced in the comparison "missing" column
    var list = (report && arr(report.cannot_conclude)) || arr(res.limitations);
    list = list.filter(Boolean);
    if (!list.length) return "";
    return section("Unresolved evidence",
      '<ul class="axr-unknowns">' + list.map(function (c) { return "<li>" + esc(c) + "</li>"; }).join("") + "</ul>",
      "axr-unknowns-block");
  }

  // 8. Recommended next step — exactly ONE primary recommendation
  function nextStepHtml(res, report) {
    var next = (report && report.next_action) || res.suggested_action || "";
    if (!next && !(g.STATE && g.STATE.copilotResult)) return "";
    var text = next ? '<p class="axr-next-text">' + esc(next) + "</p>" : "";
    var cta = '<div class="axr-next-actions"><button type="button" class="btn primary axr-next-cta" onclick="askCopyReport()">Copy analysis for your agent</button></div>';
    return '<section class="axr-block axr-next"><div class="axr-h axr-h--next">Recommended next step</div>' + text + cta + "</section>";
  }

  /* ---- small utilities ---- */
  function section(title, inner, extraCls) {
    return '<section class="axr-block ' + (extraCls || "") + '"><div class="axr-h">' + esc(title) + "</div>" + inner + "</section>";
  }
  function cap(s) { s = String(s || ""); return s ? s.charAt(0).toUpperCase() + s.slice(1) : s; }
  function clip(s, n) { s = String(s || ""); return s.length > n ? s.slice(0, n - 1) + "…" : s; }

  /* -------------------------------------------------------------------------
     Assemble the full report and take over the Ask card.
     ---------------------------------------------------------------------- */
  function buildReport(res) {
    var report = res.report || null;
    var parts = [
      execHtml(res, report),
      verdictHtml(res, report),
      findingsHtml(res, report),
      evidenceHtml(res, report),
      filesHtml(res, report),
      comparisonHtml(res, report),
      riskDashboardHtml(res),
      unknownsHtml(res, report),
      nextStepHtml(res, report)
    ].filter(Boolean);
    return '<article class="axr">' + parts.join("") + "</article>";
  }

  function wireCards(root) {
    if (!root) return;
    root.querySelectorAll(".axr-open").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        g.askCopyPath(btn.getAttribute("data-path"));
        btn.classList.add("is-copied");
        var t = btn.textContent; btn.textContent = "Copied";
        setTimeout(function () { btn.textContent = t; btn.classList.remove("is-copied"); }, 1200);
      });
    });
  }

  g.renderCopilotAnswer = function (res) {
    try {
      if (!res) return;
      if (g.STATE) g.STATE.copilotResult = res;
      var card = $("copilotCard");
      if (!card) return;
      card.style.display = "block";
      card.classList.add("axr-card");
      // Hide the legacy chrome we now render ourselves.
      ["copilotImpactSummary", "copilotImpactHierarchy", "copilotEvidenceWrap", "copilotFilesWrap", "copilotActionWrap", "copilotOut"]
        .forEach(function (id) { var el = $(id); if (el) el.style.display = "none"; });
      var legacyOut = $("copilotOut");
      if (legacyOut) { legacyOut.innerHTML = ""; legacyOut.classList.remove("axr-empty-host"); }
      var head = card.querySelector(".copilot-card-head"); if (head) head.style.display = "none";
      var ans = $("copilotAnswer");
      if (ans) { ans.classList.add("axr-host"); ans.innerHTML = buildReport(res); wireCards(ans); }
      // Keep the existing refinement actions (Refine / Inspect / Map / Plan)
      // as a secondary toolbar; ask_report.css demotes them below our one primary.
      if (typeof g.renderCopilotPrimaryActions === "function") { try { g.renderCopilotPrimaryActions(res); } catch (e) {} }
      var suggest = $("suggest"); if (suggest) suggest.style.display = "none";
      // One primary CTA per screen: while a report is displayed, its recommended
      // next step is the primary; demote the send button to a quiet secondary.
      var send = $("askSend"); if (send) send.classList.remove("primary");
      if (res.graph_highlight && g.ATLAS_UNIVERSE) { try { g.ATLAS_UNIVERSE.highlightBlastRadius(res.graph_highlight); } catch (e) {} }
    } catch (err) {
      if (g.console && console.error) console.error("[ask_report] render failed, using plain answer:", err);
      var a = $("copilotAnswer"); if (a) a.textContent = (res && res.answer) || "";
    }
  };

  /* -------------------------------------------------------------------------
     PART 7 — Staged, premium loading. Observe #copilotLoading; when app.js
     shows it, cycle through explicit investigation phases. No wrapping of the
     async fetch — robust to early returns.
     ---------------------------------------------------------------------- */
  var STAGES = ["Scoping investigation", "Resolving repository evidence", "Assembling analysis report"];
  var _timer = null, _i = 0;
  function paintStages(el) {
    el.innerHTML = '<div class="axr-loading">' +
      STAGES.map(function (s, idx) {
        var st = idx < _i ? "done" : idx === _i ? "active" : "todo";
        var icon = st === "done" ? "✓" : st === "active" ? '<span class="axr-spinner"></span>' : "";
        return '<div class="axr-load-stage is-' + st + '"><span class="axr-load-ico">' + icon + "</span>" + esc(s) + "…</div>";
      }).join("") + "</div>";
  }
  function startStages(el) {
    _i = 0; paintStages(el);
    // A new analysis is starting: the send action becomes the primary again
    // until the next report takes over as the screen's one primary CTA.
    var send = $("askSend"); if (send) send.classList.add("primary");
    _timer = setInterval(function () { if (_i < STAGES.length - 1) { _i++; paintStages(el); } }, 650);
  }
  function stopStages() { if (_timer) { clearInterval(_timer); _timer = null; } }
  function initLoading() {
    var el = $("copilotLoading");
    if (!el || el._axrObserved) return;
    el._axrObserved = true;
    var obs = new MutationObserver(function () {
      var visible = getComputedStyle(el).display !== "none";
      if (visible && !_timer) startStages(el);
      else if (!visible && _timer) stopStages();
    });
    obs.observe(el, { attributes: true, attributeFilter: ["style", "class"] });
  }

  /* -------------------------------------------------------------------------
     PART 8 — Teaching empty state with 5 example prompts. Rendered into the
     pre-answer area (#copilotOut) whenever the Ask page shows with no result.
     ---------------------------------------------------------------------- */
  var EXAMPLES = [
    { icon: "◉", q: "What does this repository do?", h: "Get a grounded overview" },
    { icon: "⌘", q: "Where is authentication implemented?", h: "Locate a concept in code" },
    { icon: "⚠", q: "What breaks if I change the main entry file?", h: "See the blast radius" },
    { icon: "⇄", q: "How does the API layer differ from the CLI?", h: "Compare two areas" },
    { icon: "★", q: "Which files should I read first?", h: "Find the best entry points" }
  ];
  function emptyStateHtml(qs) {
    var cards = qs.map(function (item, i) {
      var q = typeof item === "string" ? item : item.q;
      var icon = typeof item === "string" ? "›" : item.icon;
      var hint = typeof item === "string" ? "" : item.h;
      return '<button type="button" class="axr-eg" data-q="' + esc(q) + '">' +
        '<span class="axr-eg-ico">' + esc(icon) + "</span>" +
        '<span class="axr-eg-body"><span class="axr-eg-q">' + esc(q) + "</span>" +
        (hint ? '<span class="axr-eg-h">' + esc(hint) + "</span>" : "") + "</span>" +
        '<span class="axr-eg-go">→</span></button>';
    }).join("");
    return '<div class="axr-empty">' +
      '<p class="axr-empty-lead">Define an engineering investigation. Atlas resolves repository evidence before producing an executive summary, ranked files, confidence, explicit unknowns, and one recommended action.</p>' +
      '<div class="axr-empty-caps"><span>Architecture</span><span>Location</span><span>Impact</span><span>Comparison</span><span>Risk</span></div>' +
      '<div class="axr-eg-grid">' + cards + "</div></div>";
  }
  function renderEmpty() {
    var panel = $("askPanel"); if (panel && getComputedStyle(panel).display === "none") return;
    var card = $("copilotCard"); if (card && getComputedStyle(card).display !== "none") return; // answer showing
    var out = $("copilotOut"); if (!out) return;
    // No report on screen: the send action is the screen's one primary CTA.
    var send = $("askSend"); if (send) send.classList.add("primary");
    var qs = EXAMPLES;
    try {
      if (typeof g.defaultCopilotQuestions === "function" && g.STATE && g.STATE.summary) {
        var dyn = g.defaultCopilotQuestions(g.STATE.summary);
        if (dyn && dyn.length) {
          // Keep our curated icons/hints but seed the first prompt with a repo-specific one.
          qs = EXAMPLES.slice();
          var hub = dyn.find(function (d) { return /what breaks/i.test(d); });
          if (hub) qs[2] = { icon: "⚠", q: hub, h: "See the blast radius" };
        }
      }
    } catch (e) {}
    out.style.display = "block";
    out.classList.add("axr-empty-host");
    out.innerHTML = emptyStateHtml(qs);
    out.querySelectorAll(".axr-eg").forEach(function (b) {
      b.addEventListener("click", function () { if (g.askQuestion) g.askQuestion(b.getAttribute("data-q")); });
    });
    var suggest = $("suggest"); if (suggest) suggest.style.display = "none";
  }
  function initEmptyState() {
    if (typeof g.renderAskPage !== "function" || g.renderAskPage._axrWrapped) return;
    var orig = g.renderAskPage;
    var wrapped = function () {
      var r = orig.apply(this, arguments);
      var run = function () { try { renderEmpty(); } catch (e) {} };
      if (r && typeof r.then === "function") r.then(run, run); else run();
      return r;
    };
    wrapped._axrWrapped = true;
    g.renderAskPage = wrapped;
  }

  /* ---- init after app.js globals exist ---- */
  function init() { initLoading(); initEmptyState(); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
  // Re-attempt shortly after in case app.js defines renderAskPage later.
  setTimeout(init, 400);
  setTimeout(init, 1200);
})();
