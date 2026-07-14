import crypto from "node:crypto";
import { ENV } from "./config";
import {
  AnalyticsEventName,
  AnalyticsSource,
  analyticsEnvironment,
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
  internal?: boolean;
  userId?: string | null;
};

export type AnalyticsRow = {
  id: string;
  user_id: string | null;
  anonymous_id: string | null;
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
  is_internal: boolean;
  metadata: Record<string, string | number | boolean>;
};

export function buildAnalyticsRow(input: EventInput): AnalyticsRow {
  const environment = analyticsEnvironment();
  const anonymousId = sanitizeIdentifier(input.anonymousId);
  const sessionId = sanitizeIdentifier(input.sessionId);
  const route = sanitizeRoute(input.route);
  const clientKey = sanitizeIdentifier(input.deduplicationKey) || "event";
  const identity = input.userId || anonymousId || "anonymous";
  const material = [environment, input.source, input.eventName, identity, sessionId, route, clientKey].join("|");
  return {
    id: crypto.randomUUID(),
    user_id: input.userId || null,
    anonymous_id: anonymousId,
    session_id: sessionId,
    event_name: input.eventName,
    source: input.source,
    environment,
    route,
    app_version: ENV.appVersion,
    build_commit: process.env.VERCEL_GIT_COMMIT_SHA?.slice(0, 40) || null,
    platform: input.source === "website" ? "web" : "windows",
    event_version: 1,
    deduplication_key: crypto.createHash("sha256").update(material).digest("hex"),
    is_internal: environment !== "production" || input.internal === true,
    metadata: sanitizeProperties(input.properties),
  };
}
