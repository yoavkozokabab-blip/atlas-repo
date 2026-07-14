"use strict";
/* Trust status, update banner, version display */

const TRUST_LABELS = {
  Fresh: "fresh",
  "Needs refresh": "refresh",
  "Full rescan required": "rescan",
  "Limited language support": "limited",
};

async function atlasFetchProductConfig() {
  try {
    if (typeof api === "function") return await api("/api/product/config");
  } catch (e) {}
  return { ok: false };
}

function atlasFormatVersionLine(cfg) {
  if (!cfg || !cfg.version) return "";
  const parts = [cfg.version];
  if (cfg.build_commit && cfg.build_commit !== "unknown") parts.push(cfg.build_commit);
  if (cfg.build_date) parts.push(cfg.build_date);
  return parts.join(" · ");
}

async function atlasRenderVersionTargets() {
  const cfg = await atlasFetchProductConfig();
  const line = atlasFormatVersionLine(cfg);
  document.querySelectorAll("[data-atlas-version]").forEach(el => {
    el.textContent = line || cfg.version || "—";
  });
  const email = (cfg && cfg.support_email) || "yoavkozokabab@gmail.com";
  document.querySelectorAll("[data-atlas-support-email]").forEach(el => {
    if (el.tagName === "A") {
      el.href = "mailto:" + email;
      el.textContent = email;
    } else {
      el.textContent = email;
    }
  });
}

function atlasTrustStatusClass(label) {
  return TRUST_LABELS[label] || "unknown";
}

function atlasRenderTrustBar(payload) {
  // Drive first-run gating: repo-dependent UI (advanced quick actions, recent
  // activity, output-detail toggle) is hidden via CSS until a repo is scanned.
  document.body.classList.toggle("atlas-no-repo", !(payload && payload.has_repo));
  const bar = document.getElementById("trustStatusBar");
  if (!bar) return;
  const label = (payload && payload.user_trust_label) || "Fresh";
  // No active repository → the staleness bar is meaningless. Hide it so a fresh
  // first run never shows a contradictory "Full rescan required".
  if (!payload || payload.has_repo === false || label === "Fresh") {
    bar.style.display = "none";
    bar.innerHTML = "";
    return;
  }
  const status = (payload.trust_status || {});
  const msg = status.message || "";
  const refresh = payload.targeted_refresh_available;
  bar.className = "trust-status-bar trust-" + atlasTrustStatusClass(label);
  bar.style.display = "flex";
  bar.innerHTML = `<span class="trust-status-label">${String(label).replace(/</g, "&lt;")}</span>`
    + (msg ? `<span class="trust-status-msg muted tiny">${String(msg).replace(/</g, "&lt;")}</span>` : "")
    + (refresh ? `<button class="btn small ghost" type="button" onclick="atlasRefreshChangedFiles()">Refresh changed files</button>` : "")
    + (label === "Full rescan required" ? `<button class="btn small ghost" type="button" onclick="go('home')">Rescan repository</button>` : "");
}

async function atlasPollTrustStatus() {
  if (typeof api !== "function") return null;
  if (window.atlasTrustRequest) {
    try {
      const current = await window.atlasTrustRequest;
      if (current && current.ok) atlasRenderTrustBar(current);
      return current;
    } catch (_error) {
      window.atlasTrustRequest = null;
      return null;
    }
  }
  if (window.atlasTrustPollTimer) return null;
  return new Promise((resolve) => {
    window.atlasTrustPollTimer = window.setTimeout(() => {
      window.atlasTrustPollTimer = null;
      const request = typeof window.requestAtlasTrustStatus === "function"
        ? window.requestAtlasTrustStatus()
        : api("/api/repositories/current/trust-status");
      window.atlasTrustRequest = request;
      request.then((data) => {
        if (data && data.ok) atlasRenderTrustBar(data);
        resolve(data || null);
      }).catch(() => resolve(null)).finally(() => {
        if (window.atlasTrustRequest === request) window.atlasTrustRequest = null;
      });
    }, 7000);
  });
}

async function atlasRefreshChangedFiles() {
  try {
    const r = await api("/api/repositories/current/refresh-changed-files", "POST", {});
    if (typeof toast === "function") toast(r.ok ? (r.message || "Refresh complete") : (r.error || "Refresh failed"), r.ok ? "success" : "error");
    atlasPollTrustStatus();
  } catch (e) {
    if (typeof toast === "function") toast("Refresh failed", "error");
  }
}

async function atlasCheckForUpdate() {
  const banner = document.getElementById("updateBanner");
  if (!banner) return;
  try {
    const data = typeof api === "function" ? await api("/api/product/update-check") : { configured: false };
    if (!data || !data.configured || !data.update_available) {
      banner.style.display = "none";
      return;
    }
    const latest = data.latest_version || "newer";
    banner.style.display = "flex";
    banner.innerHTML = `<span>Update available: <b>${String(latest).replace(/</g, "&lt;")}</b></span>`
      + (data.release_notes_url ? `<a class="btn small ghost" href="${String(data.release_notes_url).replace(/"/g, "")}" target="_blank" rel="noopener">Release notes</a>` : "")
      + `<button class="btn small ghost" type="button" onclick="this.parentElement.style.display='none'">Dismiss</button>`;
  } catch (e) {
    banner.style.display = "none";
  }
}

function atlasEnhanceAboutModal() {
  const modal = document.getElementById("aboutAtlasModal");
  if (!modal || modal.querySelector("[data-atlas-version]")) return;
  const card = modal.querySelector(".about-card");
  if (!card) return;
  const ver = document.createElement("p");
  ver.className = "muted tiny";
  ver.innerHTML = 'Version <span data-atlas-version>—</span> · <a data-atlas-support-email href="mailto:yoavkozokabab@gmail.com">yoavkozokabab@gmail.com</a>';
  const buttons = card.querySelector(".success-buttons");
  if (buttons) card.insertBefore(ver, buttons);
  else card.appendChild(ver);
}

(function atlasProductBoot() {
  function boot() {
    atlasEnhanceAboutModal();
    atlasRenderVersionTargets();
    atlasPollTrustStatus();
    atlasCheckForUpdate();
    setInterval(atlasPollTrustStatus, 45000);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();

window.atlasPollTrustStatus = atlasPollTrustStatus;
window.atlasRefreshChangedFiles = atlasRefreshChangedFiles;
window.atlasRenderVersionTargets = atlasRenderVersionTargets;
