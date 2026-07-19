"use strict";
/* Release salvage (v1.0.5-final): Ask is disabled for launch.
 *
 * The not-found gate (not_found_confidence) reliably refuses most absent
 * concepts, but free-form "how does <absent concept> work" questions route to
 * the broad repository-understanding path and can still return a general
 * high-confidence summary. Rather than ship that hallucination path, the Ask
 * surface is removed from the desktop UI for launch. Graph, Impact, Debug,
 * Plan and repository understanding are unaffected.
 *
 * UI-only and self-contained: it hides the Ask entry, intercepts navigation to
 * Ask, and neutralises the Ask entry points, without touching the API,
 * intelligence, MCP, or any other workflow. Loaded last so it wins.
 */
(function () {
  var UNAVAILABLE_HTML =
    '<div class="ask-unavailable" role="status">' +
    '<h2>Repository Q&amp;A is temporarily unavailable</h2>' +
    '<p>Free-form questions are turned off for this release while we make the ' +
    'answers as trustworthy as the rest of Atlas. Everything the graph proves ' +
    'is available now:</p>' +
    '<div class="ask-unavailable-actions">' +
    '<button class="btn primary" type="button" onclick="go(\'impact\')">See change impact</button>' +
    '<button class="btn ghost" type="button" onclick="go(\'center\')">Open the dependency graph</button>' +
    '</div>' +
    '<p class="muted tiny">Impact, the graph, Debug and Plan all cite the exact ' +
    'files and dependencies behind every result.</p>' +
    '</div>';

  function neutraliseAsk() {
    // 1. Remove the Ask entry from the sidebar (all data-view="ask" controls).
    document.querySelectorAll('[data-view="ask"]').forEach(function (el) {
      el.setAttribute("hidden", "hidden");
      el.style.display = "none";
      el.setAttribute("aria-hidden", "true");
      el.tabIndex = -1;
    });
    // 2. Replace the Ask view body so any residual route lands on an honest state.
    var view = document.getElementById("view-ask");
    if (view && !view.dataset.askDisabled) {
      view.dataset.askDisabled = "1";
      view.innerHTML = UNAVAILABLE_HTML;
    }
  }

  // Intercept programmatic navigation: go('ask') shows the unavailable state,
  // it never renders the (removed) Ask workbench.
  function wrapGo() {
    if (typeof window.go !== "function" || window.go.__askGuarded) return;
    var original = window.go;
    window.go = function (view) {
      if (view === "ask") { neutraliseAsk(); return original.call(this, "ask"); }
      return original.apply(this, arguments);
    };
    window.go.__askGuarded = true;
  }

  // Neutralise the Ask entry points other surfaces call.
  function stubAskEntryPoints() {
    window.askQuestion = function () { if (typeof go === "function") go("ask"); };
    window.sendCopilotQuestion = function () { if (typeof go === "function") go("ask"); };
  }

  function run() { neutraliseAsk(); wrapGo(); stubAskEntryPoints(); }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }
  // Re-apply after late UI hydration (home cards, workbench re-render).
  setTimeout(run, 800);
  setTimeout(run, 2500);
})();
