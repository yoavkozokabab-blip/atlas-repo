import { test, expect } from "playwright/test";
import { buildHnFunnel, launchHealth } from "../app/_lib/hn-funnel";
import type { FunnelRow } from "../app/_lib/store";

/**
 * The dashboard's job is to be right, not to look busy. These tests pin the
 * arithmetic that the launch decisions will rest on: unique-installation
 * counting, the website/desktop boundary, sample sizes, and the refusal to
 * invent a number from an empty set.
 */

const T0 = Date.parse("2026-08-10T12:00:00.000Z");

function row(over: Partial<FunnelRow> & { event_name: string }): FunnelRow {
  return {
    installation_id: null,
    anonymous_id: null,
    session_id: null,
    created_at: new Date(T0).toISOString(),
    app_version: "1.0.6-beta.2",
    metadata: {},
    ...over,
  };
}

function build(rows: FunnelRow[]) {
  return buildHnFunnel(rows, { since: new Date(T0).toISOString(), windowLabel: "test", truncated: false });
}

test("an empty window yields zeros and nulls, never invented ratios", () => {
  const f = build([]);
  expect(f.acquisition.hnSessions).toBe(0);
  expect(f.acquisition.hnShare).toBeNull();
  expect(f.mcp.activationRate).toBeNull();
  expect(f.reliability.scanSuccessRate).toBeNull();
  expect(f.timeToValue.launchToValueMedianMs).toBeNull();
  expect(f.timeToValue.valueSampleSize).toBe(0);
  for (const stage of f.stages) expect(stage.count).toBe(0);
});

test("HN sessions are counted from acquisition_channel, not lumped into social", () => {
  const f = build([
    row({ event_name: "page_view", session_id: "s1", metadata: { acquisition_channel: "hacker_news" } }),
    row({ event_name: "page_view", session_id: "s2", metadata: { acquisition_channel: "hacker_news" } }),
    row({ event_name: "page_view", session_id: "s3", metadata: { acquisition_channel: "social" } }),
    row({ event_name: "page_view", session_id: "s4", metadata: {} }),
  ]);
  expect(f.acquisition.hnSessions).toBe(2);
  expect(f.acquisition.totalSessions).toBe(4);
  expect(f.acquisition.hnShare).toBeCloseTo(0.5);
});

test("a session that reloads ten times is one session", () => {
  const rows = Array.from({ length: 10 }, () =>
    row({ event_name: "page_view", session_id: "s1", metadata: { acquisition_channel: "hacker_news" } }));
  expect(build(rows).acquisition.hnSessions).toBe(1);
});

test("desktop stages count unique installations, not events", () => {
  const rows = [
    row({ event_name: "desktop_launched", installation_id: "i1" }),
    row({ event_name: "desktop_launched", installation_id: "i1" }),
    row({ event_name: "desktop_launched", installation_id: "i2" }),
    row({ event_name: "scan_started", installation_id: "i1" }),
    row({ event_name: "scan_started", installation_id: "i1" }),
  ];
  const f = build(rows);
  expect(f.stages.find((s) => s.key === "first_launch")!.count).toBe(2);
  expect(f.stages.find((s) => s.key === "scan_started")!.count).toBe(1);
});

test("redirect to first launch is labelled an aggregate proxy", () => {
  const f = build([]);
  const stage = f.stages.find((s) => s.key === "first_launch")!;
  expect(stage.aggregateProxy).toBe(true);
  // No other stage may claim per-user attribution it does not have.
  const proxies = f.stages.filter((s) => s.aggregateProxy).map((s) => s.key);
  expect(proxies).toEqual(["first_launch"]);
});

test("activation is first value over first launch, by installation", () => {
  const f = build([
    row({ event_name: "desktop_launched", installation_id: "i1" }),
    row({ event_name: "desktop_launched", installation_id: "i2" }),
    row({ event_name: "desktop_launched", installation_id: "i3" }),
    row({ event_name: "desktop_launched", installation_id: "i4" }),
    row({ event_name: "first_value_reached", installation_id: "i1", metadata: { agent: "claude" } }),
  ]);
  expect(f.mcp.activationRate).toBeCloseTo(0.25);
  expect(f.mcp.firstValueInstallations).toBe(1);
});

test("time to value is measured per installation and reports its sample size", () => {
  const f = build([
    row({ event_name: "desktop_launched", installation_id: "i1", created_at: new Date(T0).toISOString() }),
    row({ event_name: "first_value_reached", installation_id: "i1", created_at: new Date(T0 + 60_000).toISOString() }),
    row({ event_name: "desktop_launched", installation_id: "i2", created_at: new Date(T0).toISOString() }),
    row({ event_name: "first_value_reached", installation_id: "i2", created_at: new Date(T0 + 180_000).toISOString() }),
  ]);
  expect(f.timeToValue.valueSampleSize).toBe(2);
  expect(f.timeToValue.launchToValueMedianMs).toBe(60_000);
  expect(f.timeToValue.launchToValueP90Ms).toBe(180_000);
});

test("tool ranking is led by unique installations so one power user cannot dominate", () => {
  const rows = [
    ...Array.from({ length: 50 }, () =>
      row({ event_name: "atlas_tool_called", installation_id: "power",
            metadata: { tool_name: "atlas_find_file", outcome: "success" } })),
    ...["a", "b", "c"].map((id) =>
      row({ event_name: "atlas_tool_called", installation_id: id,
            metadata: { tool_name: "atlas_what_breaks", outcome: "success" } })),
  ];
  const f = build(rows);
  expect(f.tools[0].tool).toBe("atlas_what_breaks");
  expect(f.tools[0].uniqueInstallations).toBe(3);
  // The raw call count is still shown, never hidden.
  expect(f.tools[1].totalCalls).toBe(50);
});

test("tool success rate reflects failures", () => {
  const f = build([
    row({ event_name: "atlas_tool_called", installation_id: "i1", metadata: { tool_name: "atlas_what_breaks", outcome: "success" } }),
    row({ event_name: "atlas_tool_called", installation_id: "i1", metadata: { tool_name: "atlas_what_breaks", outcome: "failure" } }),
  ]);
  expect(f.tools[0].successRate).toBeCloseTo(0.5);
  expect(f.reliability.toolFailureRate).toBeCloseTo(0.5);
});

test("scan success is completions over starts, and failures are grouped by safe code", () => {
  const f = build([
    row({ event_name: "scan_started", installation_id: "i1" }),
    row({ event_name: "scan_started", installation_id: "i2" }),
    row({ event_name: "real_repo_scan_completed", installation_id: "i1" }),
    row({ event_name: "scan_failed", installation_id: "i2", metadata: { error_code: "permission_denied" } }),
  ]);
  expect(f.reliability.scanSuccessRate).toBeCloseTo(0.5);
  expect(f.reliability.topErrorCodes).toEqual([{ code: "permission_denied", count: 1 }]);
});

test("feedback categories are counted without any message text", () => {
  const f = build([
    row({ event_name: "feedback_opened", installation_id: "i1" }),
    row({ event_name: "feedback_submitted", installation_id: "i1", metadata: { category: "bug" } }),
    row({ event_name: "feedback_submitted", installation_id: "i2", metadata: { category: "bug" } }),
  ]);
  expect(f.feedback.opened).toBe(1);
  expect(f.feedback.submitted).toBe(2);
  expect(f.feedback.categories).toEqual([{ category: "bug", count: 2 }]);
  expect(JSON.stringify(f)).not.toContain("message");
});

test("health stays green on small samples and never invents a threshold", () => {
  // Two failed scans out of two is alarming in principle but meaningless at N=2.
  const f = build([
    row({ event_name: "scan_started", installation_id: "i1" }),
    row({ event_name: "scan_started", installation_id: "i2" }),
    row({ event_name: "scan_failed", installation_id: "i1", metadata: { error_code: "parser_failure" } }),
    row({ event_name: "scan_failed", installation_id: "i2", metadata: { error_code: "parser_failure" } }),
  ]);
  expect(launchHealth(f, true, true).level).toBe("green");
});

test("health goes red when scans broadly fail at a readable sample size", () => {
  const rows = [
    ...Array.from({ length: 12 }, (_, i) => row({ event_name: "scan_started", installation_id: `i${i}` })),
    ...Array.from({ length: 11 }, (_, i) =>
      row({ event_name: "scan_failed", installation_id: `i${i}`, metadata: { error_code: "index_failure" } })),
  ];
  expect(launchHealth(build(rows), true, true).level).toBe("red");
});

test("health goes red when the download route is wrong, whatever the events say", () => {
  expect(launchHealth(build([]), false, true).level).toBe("red");
});

test("health goes amber when feedback storage is unavailable", () => {
  const f = build([row({ event_name: "feedback_opened", installation_id: "i1" })]);
  const health = launchHealth(f, true, false);
  expect(health.level).toBe("amber");
  expect(health.reasons.join(" ")).toContain("feedback");
});

test("a truncated read is never presented as a complete count", () => {
  const f = buildHnFunnel([], { since: new Date(T0).toISOString(), windowLabel: "test", truncated: true });
  expect(f.truncated).toBe(true);
  expect(launchHealth(f, true, true).reasons.join(" ")).toContain("lower bound");
});
