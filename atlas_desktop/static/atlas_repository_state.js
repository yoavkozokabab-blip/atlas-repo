(function (global) {
  "use strict";

  const STATES = Object.freeze({
    NO_REPOSITORY: "NO_REPOSITORY",
    LOADING_REPOSITORY: "LOADING_REPOSITORY",
    REPOSITORY_READY: "REPOSITORY_READY",
    REPOSITORY_STALE: "REPOSITORY_STALE",
    REPOSITORY_ERROR: "REPOSITORY_ERROR",
  });

  const listeners = new Set();

  function summaryFromState() {
    const summary = global.STATE && global.STATE.summary;
    return summary && summary.ok ? summary : null;
  }

  function trustLabel(trust) {
    if (!trust) return "";
    return String(trust.user_trust_label || trust.label || "").trim();
  }

  function isFresh(trust, health) {
    if (trust) {
      if (trust.fresh === true || trust.trust_status?.fresh === true) return true;
      if (trustLabel(trust) === "Fresh") return true;
    }
    const card = health && health.persistence && health.persistence.resume_card;
    return !!(card && card.freshness_status === "fresh" && card.validation_status === "valid");
  }

  function isStale(trust) {
    if (!trust) return false;
    return !!(trust.scan_stale || trust.fresh === false || trust.stale_status);
  }

  function compute(options) {
    const opts = options || {};
    if (opts.loading) {
      return {
        state: STATES.LOADING_REPOSITORY,
        hasRepo: false,
        name: "",
        fileCount: 0,
        moduleCount: 0,
        dependencyCount: 0,
        memoryStatus: "loading",
        memoryLabel: "Loading",
        scanState: "loading",
      };
    }

    const summary = opts.summary !== undefined
      ? (opts.summary && opts.summary.ok ? opts.summary : null)
      : summaryFromState();
    const health = opts.health || null;
    const trust = opts.trust || null;

    if (!summary) {
      return {
        state: STATES.NO_REPOSITORY,
        hasRepo: false,
        name: "",
        fileCount: 0,
        moduleCount: 0,
        dependencyCount: 0,
        memoryStatus: "offline",
        memoryLabel: "No repository",
        scanState: "none",
      };
    }

    const stale = isStale(trust);
    const fresh = isFresh(trust, health);
    return {
      state: stale ? STATES.REPOSITORY_STALE : STATES.REPOSITORY_READY,
      hasRepo: true,
      name: String(summary.repo_name || "Repository"),
      repoId: summary.repo_id || summary.id || "",
      fileCount: Number(summary.file_count || 0),
      moduleCount: Number(summary.module_count || 0),
      dependencyCount: Number(summary.dependency_edges || 0),
      memoryStatus: fresh ? "ready" : (stale ? "stale" : "review"),
      memoryLabel: fresh ? "Memory current" : (stale ? "Memory stale" : "Review memory"),
      scanState: stale ? "stale" : "ready",
      demoMode: !!summary.demo_mode,
    };
  }

  function publish(detail) {
    const snapshot = detail || compute();
    listeners.forEach((listener) => {
      try { listener(snapshot); } catch (_error) {}
    });
    try {
      global.document && global.document.dispatchEvent(new CustomEvent("atlas:repository-state", { detail: snapshot }));
    } catch (_error) {}
    return snapshot;
  }

  function subscribe(listener) {
    if (typeof listener !== "function") return () => {};
    listeners.add(listener);
    return () => listeners.delete(listener);
  }

  global.AtlasRepositoryState = Object.freeze({
    STATES,
    compute,
    publish,
    subscribe,
    current: () => compute(),
  });
})(window);
