import { requireAdmin } from "@/app/_lib/auth";
import { privateJson, unavailableJson } from "@/app/_lib/http";
import { analyticsSummary } from "@/app/_lib/store";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const ALLOWED_RANGES = new Set([1, 7, 30]);
const ALLOWED_ENVIRONMENTS = new Set(["production", "preview", "development", "test", "unknown"]);

export async function GET(req: Request) {
  try {
    const admin = await requireAdmin();
    if (!admin) return privateJson({ ok: false, error: "forbidden" }, { status: 403 });

    const url = new URL(req.url);
    const requestedDays = Number(url.searchParams.get("days") || "7");
    const days = ALLOWED_RANGES.has(requestedDays) ? requestedDays : 7;
    const requestedEnvironment = url.searchParams.get("environment") || "production";
    const environment = ALLOWED_ENVIRONMENTS.has(requestedEnvironment)
      ? requestedEnvironment
      : "production";
    const buildCommit = (url.searchParams.get("build") || "").trim();
    const includeInternal = url.searchParams.get("include_internal") === "true";
    const since = new Date(Date.now() - days * 86_400_000).toISOString();

    const summary = await analyticsSummary({
      since,
      environment,
      buildCommit: /^[a-f0-9]{7,40}$/i.test(buildCommit) ? buildCommit : null,
      includeInternal,
    });
    return privateJson({ ok: true, days, summary });
  } catch {
    return unavailableJson();
  }
}
