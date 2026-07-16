import crypto from "node:crypto";
import { ENV } from "./config";
import {
  AnalyticsEventName,
  AnalyticsSource,
  analyticsEnvironment,
  classifyBrowser,
  classifyDevice,
  classifyReferrer,
  sanitizeIdentifier,
  sanitizeProperties,
  sanitizeRoute,
} from "./analytics-contract";

type EventInput = {
  eventName: AnalyticsEventName;
  source: AnalyticsSource;
  anonymousId?: unknown;
  sessionId?: unknown;
  route?: unknown;
  properties?: unknown;
  deduplicationKey?: unknown;
  installationId?: unknown;
  appVersion?: unknown;
  buildCommit?: unknown;
  request?: Pick<Request, "headers">;
  internal?: boolean;
  userId?: string | null;
};

export type AnalyticsRow = {
  id: string;
  user_id: string | null;
  anonymous_id: string | null;
  installation_id: string | null;
  session_id: string | null;
  event_name: AnalyticsEventName;
  source: AnalyticsSource;
  environment: string;
  route: string | null;
  app_version: string;
  build_commit: string | null;
  platform: string;
  event_version: number;
  deduplication_key: string;
  duration_active_ms: number | null;
  duration_elapsed_ms: number | null;
  is_internal: boolean;
  metadata: Record<string, string | number | boolean>;
};

export function buildAnalyticsRow(input: EventInput): AnalyticsRow {
  const environment = analyticsEnvironment();
  const anonymousId = sanitizeIdentifier(input.anonymousId);
  const sessionId = sanitizeIdentifier(input.sessionId);
  const route = sanitizeRoute(input.route);
  const installationId = sanitizeIdentifier(input.installationId);
  const clientKey = sanitizeIdentifier(input.deduplicationKey) || "event";
  const identity = input.userId || installationId || anonymousId || "anonymous";
  const material = [environment, input.source, input.eventName, identity, sessionId, route, clientKey].join("|");
  return {
    id: crypto.randomUUID(),
    user_id: input.userId || null,
    anonymous_id: anonymousId,
    installation_id: installationId,
    session_id: sessionId,
    event_name: input.eventName,
    source: input.source,
    environment,
    route,
    app_version: sanitizeIdentifier(input.appVersion)?.slice(0, 80) || ENV.appVersion,
    build_commit: sanitizeIdentifier(input.buildCommit)?.slice(0, 40) || process.env.VERCEL_GIT_COMMIT_SHA?.slice(0, 40) || null,
    platform: input.source === "website" ? "web" : "windows",
    event_version: 1,
    deduplication_key: crypto.createHash("sha256").update(material).digest("hex"),
    duration_active_ms: typeof sanitizeProperties(input.properties).duration_active_ms === "number"
      ? Number(sanitizeProperties(input.properties).duration_active_ms) : null,
    duration_elapsed_ms: typeof sanitizeProperties(input.properties).duration_elapsed_ms === "number"
      ? Number(sanitizeProperties(input.properties).duration_elapsed_ms) : null,
    is_internal: environment !== "production" || input.internal === true,
    metadata: {
      ...sanitizeProperties(input.properties),
      ...(input.request ? {
        referrer_category: classifyReferrer(input.request.headers.get("referer")),
        device_category: classifyDevice(input.request.headers.get("user-agent")),
        browser_category: classifyBrowser(input.request.headers.get("user-agent")),
      } : {}),
    },
  };
}
