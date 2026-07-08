/** Pure TTFV math — testable without DB. */

export type MilestoneTimestamps = {
  installed_at?: string | null;
  opened_at?: string | null;
  login_success_at?: string | null;
  repo_connected_at?: string | null;
  first_context_at?: string | null;
};

export type TtfvSeconds = {
  install_to_open_sec: number | null;
  open_to_login_sec: number | null;
  login_to_repo_sec: number | null;
  repo_to_first_context_sec: number | null;
  total_ttfv_sec: number | null;
};

function diffSec(a?: string | null, b?: string | null): number | null {
  if (!a || !b) return null;
  const ms = new Date(b).getTime() - new Date(a).getTime();
  if (!Number.isFinite(ms) || ms < 0) return null;
  return Math.round(ms / 1000);
}

export function computeTtfvSeconds(m: MilestoneTimestamps): TtfvSeconds {
  return {
    install_to_open_sec: diffSec(m.installed_at, m.opened_at),
    open_to_login_sec: diffSec(m.opened_at, m.login_success_at),
    login_to_repo_sec: diffSec(m.login_success_at, m.repo_connected_at),
    repo_to_first_context_sec: diffSec(m.repo_connected_at, m.first_context_at),
    total_ttfv_sec: diffSec(m.installed_at, m.first_context_at),
  };
}

export function averageTtfv(rows: TtfvSeconds[]): Partial<TtfvSeconds> {
  const keys = [
    "install_to_open_sec",
    "open_to_login_sec",
    "login_to_repo_sec",
    "repo_to_first_context_sec",
    "total_ttfv_sec",
  ] as const;
  const out: Partial<TtfvSeconds> = {};
  for (const key of keys) {
    const vals = rows.map((r) => r[key]).filter((v): v is number => typeof v === "number");
    out[key] = vals.length ? Math.round(vals.reduce((a, b) => a + b, 0) / vals.length) : null;
  }
  return out;
}
