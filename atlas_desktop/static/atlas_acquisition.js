"use strict";
/* Acquisition funnel events (privacy-safe, best-effort). */
(function () {
  function post(stage, metadata) {
    const body = { stage: stage, source: "desktop" };
    if (metadata) body.metadata = metadata;
    fetch("/api/accounts/acquisition/event", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).catch(function () {});
  }

  try {
    if (!sessionStorage.getItem("atlas_acq_installed")) {
      sessionStorage.setItem("atlas_acq_installed", "1");
      post("app_installed");
    }
  } catch (e) {}

  window.atlasAcquisition = { track: post };
})();
