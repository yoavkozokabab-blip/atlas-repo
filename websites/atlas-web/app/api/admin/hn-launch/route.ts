import { requireAdmin } from "@/app/_lib/auth";
import { privateJson, unavailableJson } from "@/app/_lib/http";
import { funnelRows } from "@/app/_lib/store";
import { buildHnFunnel, launchHealth } from "@/app/_lib/hn-funnel";
import { CURRENT_WINDOWS_RELEASE } from "@/app/_config";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** Admin-only. Windows are short by design: this is a launch-day view. */
const WINDOWS: Record<string, { minutes: number; label: string }> = {
  "15m": { minutes: 15, label: "last 15 minutes" },
  "1h": { minutes: 60, label: "last hour" },
  "6h": { minutes: 360, label: "last 6 hours" },
  "24h": { minutes: 1_440, label: "launch day" },
  "7d": { minutes: 10_080, label: "last 7 days" },
  "30d": { minutes: 43_200, label: "all time (30d cap)" },
};

async function downloadHealthy(): Promise<boolean> {
  try {
    const res = await fetch(CURRENT_WINDOWS_RELEASE.downloadUrl, { method: "HEAD", redirect: "follow", cache: "no-store" });
    const length = Number(res.headers.get("content-length") || 0);
    return res.ok && length === CURRENT_WINDOWS_RELEASE.sizeBytes;
  } catch {
    return false;
  }
}

export async function GET(req: Request) {
  try {
    const admin = await requireAdmin();
    if (!admin) return privateJson({ ok: false, error: "forbidden" }, { status: 403 });

    const url = new URL(req.url);
    const key = url.searchParams.get("window") || "24h";
    const window = WINDOWS[key] || WINDOWS["24h"];
    const since = new Date(Date.now() - window.minutes * 60_000).toISOString();

    const { rows, truncated } = await funnelRows(since);
    const funnel = buildHnFunnel(rows, { since, windowLabel: window.label, truncated });

    // Feedback storage is the one dependency whose absence is invisible in the
    // event stream: no table means feedback_submitted can never appear, which
    // would otherwise read as "nobody sent feedback".
    const feedbackOk = funnel.feedback.submitted > 0 || funnel.feedback.opened === 0;
    const health = launchHealth(funnel, await downloadHealthy(), feedbackOk);

    return privateJson({
      ok: true,
      window: key,
      release: {
        version: CURRENT_WINDOWS_RELEASE.version,
        sha256: CURRENT_WINDOWS_RELEASE.sha256,
        sizeBytes: CURRENT_WINDOWS_RELEASE.sizeBytes,
      },
      health,
      funnel,
    });
  } catch (error) {
    console.error("[atlas] hn_launch_dashboard_failed", { name: (error as Error)?.name });
    return unavailableJson();
  }
}
