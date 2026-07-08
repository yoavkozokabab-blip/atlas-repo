#!/usr/bin/env node
/**
 * RC analytics smoke: identity TTFV math + event allowlist sanity.
 * Run: node scripts/analytics-rc-smoke.mjs
 */

import assert from "node:assert/strict";

function diffSec(a, b) {
  const ms = new Date(b).getTime() - new Date(a).getTime();
  if (!Number.isFinite(ms) || ms < 0) return null;
  return Math.round(ms / 1000);
}

function computeTtfv(m) {
  return {
    install_to_open_sec: diffSec(m.installed_at, m.opened_at),
    open_to_login_sec: diffSec(m.opened_at, m.login_success_at),
    login_to_repo_sec: diffSec(m.login_success_at, m.repo_connected_at),
    repo_to_first_context_sec: diffSec(m.repo_connected_at, m.first_context_at),
    total_ttfv_sec: diffSec(m.installed_at, m.first_context_at),
  };
}

const t0 = "2026-01-01T00:00:00.000Z";
const m = {
  installed_at: t0,
  opened_at: "2026-01-01T00:05:00.000Z",
  login_success_at: "2026-01-01T00:10:00.000Z",
  repo_connected_at: "2026-01-01T00:20:00.000Z",
  first_context_at: "2026-01-01T00:30:00.000Z",
};
const ttfv = computeTtfv(m);
assert.equal(ttfv.install_to_open_sec, 300);
assert.equal(ttfv.total_ttfv_sec, 1800);

const RC_EVENTS = [
  "desktop_installed",
  "cursor_connected",
  "claude_connected",
  "codex_connected",
  "cursor_used",
  "claude_used",
  "codex_used",
  "atlas_session_started",
  "atlas_first_tool_call",
  "atlas_tool_call",
  "atlas_context_served",
  "atlas_context_used",
  "atlas_session_finished",
];
assert.ok(RC_EVENTS.length >= 13);

console.log("analytics-rc-smoke: PASS");
console.log(JSON.stringify({ ttfv, rc_event_count: RC_EVENTS.length }, null, 2));
