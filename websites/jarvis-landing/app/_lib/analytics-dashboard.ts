import type { IdentityRow } from "./analytics-dashboard-types";
import { averageTtfv, computeTtfvSeconds } from "./analytics-ttfv";

export type { IdentityRow };

export type FunnelStep = {
  key: string;
  label: string;
  count: number;
  conversionFromPrev: number | null;
};

const FUNNEL_STEPS: { key: string; label: string }[] = [
  { key: "site_visit", label: "Visitors" },
  { key: "download_clicked", label: "Downloads" },
  { key: "desktop_opened", label: "Desktop Opens" },
  { key: "signup_success", label: "Signups" },
  { key: "desktop_login_success", label: "Logins" },
  { key: "repo_connected", label: "Repositories Connected" },
  { key: "first_context_generated", label: "First Context Generated" },
  { key: "cursor_connected", label: "Cursor Connected" },
  { key: "claude_connected", label: "Claude Connected" },
  { key: "codex_connected", label: "Codex Connected" },
];

export function countEventsByName(events: { event_name: string }[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (const row of events) {
    const k = row.event_name || "unknown";
    out[k] = (out[k] || 0) + 1;
  }
  return out;
}

export function buildFunnel(byName: Record<string, number>): FunnelStep[] {
  let prev: number | null = null;
  return FUNNEL_STEPS.map((step) => {
    const count = byName[step.key] || 0;
    const conversionFromPrev =
      prev == null ? null : prev > 0 ? Math.round((count / prev) * 1000) / 10 : 0;
    prev = count;
    return { ...step, count, conversionFromPrev };
  });
}

export function findDropOff(funnel: FunnelStep[]): { from: string; to: string; dropPct: number } | null {
  let worst: { from: string; to: string; dropPct: number } | null = null;
  for (let i = 0; i < funnel.length - 1; i += 1) {
    const a = funnel[i];
    const b = funnel[i + 1];
    if (a.count <= 0) continue;
    const dropPct = Math.round(((a.count - b.count) / a.count) * 1000) / 10;
    if (!worst || dropPct > worst.dropPct) {
      worst = { from: a.label, to: b.label, dropPct };
    }
  }
  return worst;
}

export function mostUsedAgent(byName: Record<string, number>, identities: IdentityRow[]): string {
  const used = {
    cursor: (byName.cursor_used || 0) + sumField(identities, "cursor_used_count"),
    claude: (byName.claude_used || 0) + sumField(identities, "claude_used_count"),
    codex: (byName.codex_used || 0) + sumField(identities, "codex_used_count"),
  };
  const entries = Object.entries(used).sort((a, b) => b[1] - a[1]);
  return entries[0]?.[1] ? entries[0][0] : "none";
}

function sumField(rows: IdentityRow[], key: string): number {
  return rows.reduce((acc, row) => acc + Number(row[key] || 0), 0);
}

export function activeUsersToday(identities: IdentityRow[], now = new Date()): number {
  const day = now.toISOString().slice(0, 10);
  return identities.filter((r) => String(r.last_seen || "").slice(0, 10) === day).length;
}

export function returningUsers(identities: IdentityRow[]): number {
  return identities.filter((r) => Number(r.sessions_count || 0) > 1 || Number(r.days_active || 0) > 1).length;
}

export function averageTtfvFromIdentities(identities: IdentityRow[]) {
  const rows = identities
    .filter((r) => r.installed_at && r.first_context_at)
    .map((r) =>
      computeTtfvSeconds({
        installed_at: String(r.installed_at),
        opened_at: r.opened_at ? String(r.opened_at) : null,
        login_success_at: r.login_success_at ? String(r.login_success_at) : null,
        repo_connected_at: r.repo_connected_at ? String(r.repo_connected_at) : null,
        first_context_at: String(r.first_context_at),
      })
    );
  return averageTtfv(rows);
}
