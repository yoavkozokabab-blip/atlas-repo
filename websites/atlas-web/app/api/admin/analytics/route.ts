import { requireAdmin } from "@/app/_lib/auth";
import { privateJson, unavailableJson } from "@/app/_lib/http";
import { analyticsSummary } from "@/app/_lib/store";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const ALLOWED_RANGES = new Set([1, 7, 30]);
const ALLOWED_ENVIRONMENTS = new Set(["production", "preview", "development", "test", "unknown"]);

function dateRange(url: URL): { since: string; until: string | null; days: number | "custom" } {
  const from = url.searchParams.get("from");
  const to = url.searchParams.get("to");
  if (from || to) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(from || "") || !/^\d{4}-\d{2}-\d{2}$/.test(to || "")) throw new Error("invalid_range");
    const since = new Date(`${from}T00:00:00.000Z`);
    const endInclusive = new Date(`${to}T00:00:00.000Z`);
    if (Number.isNaN(since.valueOf()) || Number.isNaN(endInclusive.valueOf()) || endInclusive < since) throw new Error("invalid_range");
    const until = new Date(endInclusive.valueOf() + 86_400_000);
    if (until.valueOf() - since.valueOf() > 90 * 86_400_000) throw new Error("range_too_large");
    return { since: since.toISOString(), until: until.toISOString(), days: "custom" };
  }
  const requestedDays = Number(url.searchParams.get("days") || "7");
  const days = ALLOWED_RANGES.has(requestedDays) ? requestedDays : 7;
  return { since: new Date(Date.now() - days * 86_400_000).toISOString(), until: null, days };
}

export async function GET(req: Request) {
  try {
    const admin = await requireAdmin();
    if (!admin) return privateJson({ ok: false, error: "forbidden" }, { status: 403 });

    const url = new URL(req.url);
    const range = dateRange(url);
    const requestedEnvironment = url.searchParams.get("environment") || "production";
    const environment = ALLOWED_ENVIRONMENTS.has(requestedEnvironment)
      ? requestedEnvironment
      : "production";
    const buildCommit = (url.searchParams.get("build") || "").trim();
    const includeInternal = url.searchParams.get("include_internal") === "true";
    const summary = await analyticsSummary({
      since: range.since,
      until: range.until,
      environment,
      buildCommit: /^[a-f0-9]{7,40}$/i.test(buildCommit) ? buildCommit : null,
      includeInternal,
    });
    return privateJson({ ok: true, days: range.days, summary });
  } catch (error) {
    if (error instanceof Error && /range/.test(error.message)) return privateJson({ ok: false, error: error.message }, { status: 400 });
    return unavailableJson();
  }
}
