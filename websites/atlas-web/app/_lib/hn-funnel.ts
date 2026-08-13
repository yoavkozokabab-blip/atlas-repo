import type { FunnelRow } from "./store";

/**
 * Show HN launch funnel.
 *
 * Two rules govern every number here.
 *
 * 1. Website and desktop identities are NOT correlated. A browser session and
 *    an installation are separate universes, so any ratio that crosses them is
 *    a ratio of two independent counters, not a per-user conversion. Those are
 *    marked `aggregateProxy` and the UI must say so.
 * 2. Sample size travels with every statistic. A median over three events is
 *    not a median, and hiding N is how a launch dashboard starts lying.
 */

export type Stage = {
  key: string;
  label: string;
  count: number;
  /** Conversion from the previous stage, null when the previous count is 0. */
  fromPrevious: number | null;
  /** Conversion from the top of the funnel. */
  fromTop: number | null;
  /** True when this stage's ratio crosses the website/desktop boundary. */
  aggregateProxy?: boolean;
  unit: "sessions" | "events" | "installations";
};

export type ToolUsage = {
  tool: string;
  uniqueInstallations: number;
  totalCalls: number;
  successRate: number | null;
};

export type HnFunnel = {
  since: string;
  windowLabel: string;
  truncated: boolean;
  rowsScanned: number;
  acquisition: {
    hnSessions: number;
    totalSessions: number;
    hnShare: number | null;
    downloadCtaClicks: number;
    hnDownloadCtaClicks: number;
    artifactRedirects: number;
    ctaConversion: number | null;
  };
  stages: Stage[];
  timeToValue: {
    launchToScanMedianMs: number | null;
    launchToScanP90Ms: number | null;
    launchToValueMedianMs: number | null;
    launchToValueP90Ms: number | null;
    scanSampleSize: number;
    valueSampleSize: number;
  };
  mcp: {
    configured: number;
    initialized: number;
    firstValueInstallations: number;
    activationRate: number | null;
    agents: { agent: string; installations: number }[];
  };
  tools: ToolUsage[];
  reliability: {
    scanStarts: number;
    scanCompletions: number;
    scanFailures: number;
    scanSuccessRate: number | null;
    toolCalls: number;
    toolFailures: number;
    toolFailureRate: number | null;
    topErrorCodes: { code: string; count: number }[];
    versions: { version: string; installations: number }[];
  };
  retention: {
    installationsToday: number;
    returningInstallations: number;
    d1: { returned: number; cohort: number } | null;
    d7: { returned: number; cohort: number } | null;
  };
  feedback: {
    opened: number;
    submitted: number;
    categories: { category: string; count: number }[];
  };
};

const SCAN_DONE = new Set(["real_repo_scan_completed", "sample_scan_completed"]);

function ratio(numerator: number, denominator: number): number | null {
  return denominator > 0 ? numerator / denominator : null;
}

function percentile(values: number[], p: number): number | null {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const index = Math.min(sorted.length - 1, Math.max(0, Math.ceil((p / 100) * sorted.length) - 1));
  return sorted[index];
}

function meta(row: FunnelRow, key: string): string | null {
  const value = row.metadata?.[key];
  return typeof value === "string" ? value : null;
}

/** First timestamp per installation for a set of event names. */
function firstAt(rows: FunnelRow[], names: Set<string>): Map<string, number> {
  const out = new Map<string, number>();
  for (const row of rows) {
    if (!row.installation_id || !names.has(row.event_name)) continue;
    const at = Date.parse(row.created_at);
    if (!Number.isFinite(at)) continue;
    const existing = out.get(row.installation_id);
    if (existing === undefined || at < existing) out.set(row.installation_id, at);
  }
  return out;
}

function uniqueInstalls(rows: FunnelRow[], name: string): Set<string> {
  const out = new Set<string>();
  for (const row of rows) {
    if (row.event_name === name && row.installation_id) out.add(row.installation_id);
  }
  return out;
}

function countBy(rows: FunnelRow[], name: string): number {
  return rows.reduce((total, row) => total + (row.event_name === name ? 1 : 0), 0);
}

function rank(counts: Map<string, number>, limit = 8): { code: string; count: number }[] {
  return [...counts.entries()]
    .map(([code, count]) => ({ code, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, limit);
}

export function buildHnFunnel(
  rows: FunnelRow[],
  options: { since: string; windowLabel: string; truncated: boolean },
): HnFunnel {
  // --- acquisition (browser sessions) ------------------------------------
  const sessionsAll = new Set<string>();
  const sessionsHn = new Set<string>();
  const ctaSessions = new Set<string>();
  const ctaHnSessions = new Set<string>();
  for (const row of rows) {
    if (!row.session_id) continue;
    const hn = meta(row, "acquisition_channel") === "hacker_news";
    if (row.event_name === "page_view" || row.event_name === "site_visit") {
      sessionsAll.add(row.session_id);
      if (hn) sessionsHn.add(row.session_id);
    }
    if (row.event_name === "download_clicked") {
      ctaSessions.add(row.session_id);
      if (hn) ctaHnSessions.add(row.session_id);
    }
  }
  const artifactRedirects = countBy(rows, "installer_download_started");

  // --- desktop stages (installations) ------------------------------------
  const firstLaunch = uniqueInstalls(rows, "desktop_launched");
  const localMode = uniqueInstalls(rows, "onboarding_local_mode_selected");
  const repoSelected = uniqueInstalls(rows, "repository_selected");
  const scanStarted = uniqueInstalls(rows, "scan_started");
  const scanCompleted = new Set<string>();
  for (const row of rows) {
    if (SCAN_DONE.has(row.event_name) && row.installation_id) scanCompleted.add(row.installation_id);
  }
  const mcpConfigured = uniqueInstalls(rows, "mcp_configured");
  const mcpInitialized = uniqueInstalls(rows, "mcp_initialize_success");
  const firstValue = uniqueInstalls(rows, "first_value_reached");

  const top = sessionsHn.size;
  const stage = (
    key: string, label: string, count: number,
    previous: number, unit: Stage["unit"], aggregateProxy = false,
  ): Stage => ({
    key, label, count,
    fromPrevious: ratio(count, previous),
    fromTop: ratio(count, top),
    unit,
    ...(aggregateProxy ? { aggregateProxy: true } : {}),
  });

  const stages: Stage[] = [
    stage("hn_sessions", "HN sessions", sessionsHn.size, sessionsHn.size, "sessions"),
    stage("download_cta", "Download CTA", ctaHnSessions.size, sessionsHn.size, "sessions"),
    stage("artifact_redirect", "Artifact redirect", artifactRedirects, ctaSessions.size, "events"),
    stage("first_launch", "First launch", firstLaunch.size, artifactRedirects, "installations", true),
    stage("local_mode", "Local mode", localMode.size, firstLaunch.size, "installations"),
    stage("repository_selected", "Repository selected", repoSelected.size, localMode.size, "installations"),
    stage("scan_started", "Scan started", scanStarted.size, repoSelected.size, "installations"),
    stage("scan_completed", "Scan completed", scanCompleted.size, scanStarted.size, "installations"),
    stage("mcp_configured", "MCP configured", mcpConfigured.size, scanCompleted.size, "installations"),
    stage("mcp_initialized", "MCP initialized", mcpInitialized.size, mcpConfigured.size, "installations"),
    stage("first_value", "First value", firstValue.size, mcpInitialized.size, "installations"),
  ];

  // --- time to value ------------------------------------------------------
  const launchAt = firstAt(rows, new Set(["desktop_launched"]));
  const scanAt = firstAt(rows, SCAN_DONE);
  const valueAt = firstAt(rows, new Set(["first_value_reached"]));
  const scanDeltas: number[] = [];
  const valueDeltas: number[] = [];
  for (const [install, launched] of launchAt) {
    const scan = scanAt.get(install);
    if (scan !== undefined && scan >= launched) scanDeltas.push(scan - launched);
    const value = valueAt.get(install);
    if (value !== undefined && value >= launched) valueDeltas.push(value - launched);
  }

  // --- MCP ----------------------------------------------------------------
  const agentInstalls = new Map<string, Set<string>>();
  for (const row of rows) {
    if (row.event_name !== "mcp_configured" && row.event_name !== "mcp_initialize_success") continue;
    const agent = meta(row, "agent");
    if (!agent || !row.installation_id) continue;
    if (!agentInstalls.has(agent)) agentInstalls.set(agent, new Set());
    agentInstalls.get(agent)!.add(row.installation_id);
  }

  // --- tools --------------------------------------------------------------
  const toolInstalls = new Map<string, Set<string>>();
  const toolCalls = new Map<string, number>();
  const toolOk = new Map<string, number>();
  let totalToolCalls = 0;
  let totalToolFailures = 0;
  for (const row of rows) {
    if (row.event_name !== "atlas_tool_called") continue;
    totalToolCalls += 1;
    const success = meta(row, "outcome") === "success";
    if (!success) totalToolFailures += 1;
    const tool = meta(row, "tool_name");
    if (!tool) continue;
    toolCalls.set(tool, (toolCalls.get(tool) || 0) + 1);
    if (success) toolOk.set(tool, (toolOk.get(tool) || 0) + 1);
    if (row.installation_id) {
      if (!toolInstalls.has(tool)) toolInstalls.set(tool, new Set());
      toolInstalls.get(tool)!.add(row.installation_id);
    }
  }
  // Sorted by unique installations first so one power user cannot dominate.
  const tools: ToolUsage[] = [...toolCalls.keys()]
    .map((tool) => ({
      tool,
      uniqueInstallations: toolInstalls.get(tool)?.size || 0,
      totalCalls: toolCalls.get(tool) || 0,
      successRate: ratio(toolOk.get(tool) || 0, toolCalls.get(tool) || 0),
    }))
    .sort((a, b) => b.uniqueInstallations - a.uniqueInstallations || b.totalCalls - a.totalCalls);

  // --- reliability --------------------------------------------------------
  const errorCodes = new Map<string, number>();
  for (const row of rows) {
    if (row.event_name !== "scan_failed") continue;
    const code = meta(row, "error_code") || "unreported";
    errorCodes.set(code, (errorCodes.get(code) || 0) + 1);
  }
  const versionInstalls = new Map<string, Set<string>>();
  for (const row of rows) {
    if (!row.app_version || !row.installation_id) continue;
    if (!versionInstalls.has(row.app_version)) versionInstalls.set(row.app_version, new Set());
    versionInstalls.get(row.app_version)!.add(row.installation_id);
  }

  // --- retention ----------------------------------------------------------
  const dayOf = (ms: number) => Math.floor(ms / 86_400_000);
  const launchDays = new Map<string, Set<number>>();
  for (const row of rows) {
    if (row.event_name !== "desktop_launched" || !row.installation_id) continue;
    const at = Date.parse(row.created_at);
    if (!Number.isFinite(at)) continue;
    if (!launchDays.has(row.installation_id)) launchDays.set(row.installation_id, new Set());
    launchDays.get(row.installation_id)!.add(dayOf(at));
  }
  let returning = 0;
  let d1Cohort = 0, d1Returned = 0, d7Cohort = 0, d7Returned = 0;
  const today = dayOf(Date.now());
  const installationsToday = new Set<string>();
  for (const [install, days] of launchDays) {
    if (days.size > 1) returning += 1;
    if (days.has(today)) installationsToday.add(install);
    const first = Math.min(...days);
    if (today - first >= 1) {
      d1Cohort += 1;
      if (days.has(first + 1)) d1Returned += 1;
    }
    if (today - first >= 7) {
      d7Cohort += 1;
      if ([...days].some((d) => d > first && d - first <= 7)) d7Returned += 1;
    }
  }

  // --- feedback -----------------------------------------------------------
  const categories = new Map<string, number>();
  for (const row of rows) {
    if (row.event_name !== "feedback_submitted") continue;
    const category = meta(row, "category") || "general";
    categories.set(category, (categories.get(category) || 0) + 1);
  }

  return {
    since: options.since,
    windowLabel: options.windowLabel,
    truncated: options.truncated,
    rowsScanned: rows.length,
    acquisition: {
      hnSessions: sessionsHn.size,
      totalSessions: sessionsAll.size,
      hnShare: ratio(sessionsHn.size, sessionsAll.size),
      downloadCtaClicks: ctaSessions.size,
      hnDownloadCtaClicks: ctaHnSessions.size,
      artifactRedirects,
      ctaConversion: ratio(ctaSessions.size, sessionsAll.size),
    },
    stages,
    timeToValue: {
      launchToScanMedianMs: percentile(scanDeltas, 50),
      launchToScanP90Ms: percentile(scanDeltas, 90),
      launchToValueMedianMs: percentile(valueDeltas, 50),
      launchToValueP90Ms: percentile(valueDeltas, 90),
      scanSampleSize: scanDeltas.length,
      valueSampleSize: valueDeltas.length,
    },
    mcp: {
      configured: mcpConfigured.size,
      initialized: mcpInitialized.size,
      firstValueInstallations: firstValue.size,
      activationRate: ratio(firstValue.size, firstLaunch.size),
      agents: [...agentInstalls.entries()]
        .map(([agent, set]) => ({ agent, installations: set.size }))
        .sort((a, b) => b.installations - a.installations),
    },
    tools,
    reliability: {
      scanStarts: scanStarted.size,
      scanCompletions: scanCompleted.size,
      scanFailures: countBy(rows, "scan_failed"),
      scanSuccessRate: ratio(scanCompleted.size, scanStarted.size),
      toolCalls: totalToolCalls,
      toolFailures: totalToolFailures,
      toolFailureRate: ratio(totalToolFailures, totalToolCalls),
      topErrorCodes: rank(errorCodes),
      versions: [...versionInstalls.entries()]
        .map(([version, set]) => ({ version, installations: set.size }))
        .sort((a, b) => b.installations - a.installations),
    },
    retention: {
      installationsToday: installationsToday.size,
      returningInstallations: returning,
      d1: d1Cohort > 0 ? { returned: d1Returned, cohort: d1Cohort } : null,
      d7: d7Cohort > 0 ? { returned: d7Returned, cohort: d7Cohort } : null,
    },
    feedback: {
      opened: countBy(rows, "feedback_opened"),
      submitted: countBy(rows, "feedback_submitted"),
      categories: [...categories.entries()]
        .map(([category, count]) => ({ category, count }))
        .sort((a, b) => b.count - a.count),
    },
  };
}

/**
 * Launch health.
 *
 * Deliberately coarse and operational. There is no baseline to derive
 * statistical thresholds from on launch day, so these are availability
 * statements plus one obvious-failure check, and the raw numbers are always
 * shown next to the colour.
 */
export function launchHealth(funnel: HnFunnel, downloadOk: boolean, feedbackOk: boolean): {
  level: "green" | "amber" | "red";
  reasons: string[];
} {
  const reasons: string[] = [];
  let level: "green" | "amber" | "red" = "green";

  if (!downloadOk) {
    reasons.push("download route is not serving the expected artifact");
    level = "red";
  }
  const { scanStarts, scanCompletions, scanSuccessRate, toolFailureRate, toolCalls } = funnel.reliability;
  if (scanStarts >= 10 && scanSuccessRate !== null && scanSuccessRate < 0.5) {
    reasons.push(`scan success ${scanCompletions}/${scanStarts}`);
    level = "red";
  }
  if (toolCalls >= 10 && toolFailureRate !== null && toolFailureRate > 0.5) {
    reasons.push(`MCP tool failures ${Math.round(toolFailureRate * 100)}% of ${toolCalls}`);
    level = "red";
  }
  if (level !== "red") {
    if (!feedbackOk) {
      reasons.push("feedback endpoint unavailable");
      level = "amber";
    }
    if (scanStarts >= 10 && scanSuccessRate !== null && scanSuccessRate < 0.8) {
      reasons.push(`scan success below 80% (${scanCompletions}/${scanStarts})`);
      level = "amber";
    }
    if (funnel.truncated) {
      reasons.push("row cap reached - counts are a lower bound");
      level = "amber";
    }
  }
  if (!reasons.length) reasons.push("site, download and ingestion healthy");
  return { level, reasons };
}
