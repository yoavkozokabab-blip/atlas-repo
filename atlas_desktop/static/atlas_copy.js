"use strict";
/* User-facing label maps (UI copy only). */

const ATLAS_GRAPH_HEALTH_LABELS = {
  healthy: "Complete",
  watch: "Good",
  partial: "Limited",
  degraded: "Incomplete",
  unsupported: "Unsupported",
  empty: "Empty",
};

const ATLAS_RELIABILITY_LABELS = {
  ok: "Scan completed normally",
  partial_graph: "Some dependencies could not be linked",
  unresolved_explosion: "Many imports could not be resolved",
  zero_edge_graph: "Very few module links were found",
  zero_module_scan: "Almost no modules were indexed",
  timeout: "Scan timed out before finishing",
  memory_pressure: "Scan stopped early to save memory",
  scan_crash: "Scan stopped unexpectedly",
  scan_failed: "Scan could not finish",
  unsupported_language: "Limited language support for this repository",
  empty_repo: "No source files found",
};

const ATLAS_CONFIDENCE_LABELS = {
  high: "Strong",
  medium: "Moderate",
  low: "Limited",
  unknown: "Uncertain",
};

const ATLAS_TELEMETRY_UI = "Usage stats temporarily unavailable — scanning and plans still work.";

function atlasFriendlyGraphHealth(label) {
  const key = String(label || "").toLowerCase();
  return ATLAS_GRAPH_HEALTH_LABELS[key] || (key ? key.replace(/_/g, " ") : "—");
}

function atlasFriendlyReliability(category) {
  const key = String(category || "").toLowerCase();
  if (ATLAS_RELIABILITY_LABELS[key]) return ATLAS_RELIABILITY_LABELS[key];
  if (key.startsWith("scan category:")) {
    return atlasFriendlyReliability(key.replace(/^scan category:\s*/i, "").trim());
  }
  return key ? key.replace(/_/g, " ") : "Scan completed with limited coverage";
}

function atlasFriendlyTelemetry(msg) {
  const m = String(msg || "").trim();
  if (!m || /telemetry unavailable/i.test(m)) return ATLAS_TELEMETRY_UI;
  return m;
}

function atlasFriendlyConfidence(raw) {
  const s = String(raw || "").toLowerCase();
  if (s.includes("high")) return ATLAS_CONFIDENCE_LABELS.high;
  if (s.includes("low")) return ATLAS_CONFIDENCE_LABELS.low;
  if (s.includes("unknown")) return ATLAS_CONFIDENCE_LABELS.unknown;
  return ATLAS_CONFIDENCE_LABELS.medium;
}

window.atlasFriendlyGraphHealth = atlasFriendlyGraphHealth;
window.atlasFriendlyReliability = atlasFriendlyReliability;
window.atlasFriendlyTelemetry = atlasFriendlyTelemetry;
window.atlasFriendlyConfidence = atlasFriendlyConfidence;
