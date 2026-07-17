/** Authoritative Free plan policy. This module intentionally has no browser
 * state dependency: callers must supply the authenticated server identity. */
export const FREE_ACTIVE_REPOSITORIES = 1;
export const FREE_ACTIVE_MCP_CLIENTS = 1;
export const FREE_ADVANCED_IMPACT_LIMIT = 20;
export const FREE_IMPACT_WINDOW_HOURS = 24;

export type FreeFeature = "active_repository" | "mcp_client" | "advanced_impact";
export type UsageResult = { allowed: boolean; used: number; limit: number; resetAt: string };

export interface UsageMeter {
  consume(identity: string, feature: FreeFeature, limit: number, windowHours: number): UsageResult;
  usage(identity: string, feature: FreeFeature, limit: number, windowHours: number): UsageResult;
}

type Clock = () => number;
/** A process-local implementation used only when no database-backed meter is
 * configured. It is injected in tests and shared by all FeatureGate instances
 * in the process, so a second app instance cannot silently multiply quota. */
export class InMemoryUsageMeter implements UsageMeter {
  private readonly buckets = new Map<string, { used: number; resetAt: number }>();
  constructor(private readonly clock: Clock = () => Date.now()) {}
  private key(identity: string, feature: FreeFeature) { return `${identity}:${feature}`; }
  private result(identity: string, feature: FreeFeature, limit: number, windowHours: number, consume: boolean): UsageResult {
    const now = this.clock();
    const key = this.key(identity, feature);
    const windowMs = windowHours * 60 * 60 * 1000;
    const existing = this.buckets.get(key);
    const bucket = !existing || existing.resetAt <= now ? { used: 0, resetAt: now + windowMs } : existing;
    if (consume && bucket.used < limit) bucket.used += 1;
    this.buckets.set(key, bucket);
    return { allowed: bucket.used <= limit, used: bucket.used, limit, resetAt: new Date(bucket.resetAt).toISOString() };
  }
  consume(identity: string, feature: FreeFeature, limit: number, windowHours: number) { return this.result(identity, feature, limit, windowHours, true); }
  usage(identity: string, feature: FreeFeature, limit: number, windowHours: number) { return this.result(identity, feature, limit, windowHours, false); }
}

export interface EntitlementService {
  planFor(identity: string): Promise<"free" | "pro">;
}
/** Billing is disabled: entitlement lookup failure and legacy client claims
 * both fail closed to Free. A future server-only provider may replace this. */
export class FreeOnlyEntitlementService implements EntitlementService {
  async planFor(_identity: string): Promise<"free"> { return "free"; }
}

export class FeatureGate {
  constructor(private readonly entitlements: EntitlementService, private readonly meter: UsageMeter) {}
  async consume(identity: string, feature: FreeFeature, options: { demo?: boolean } = {}): Promise<UsageResult> {
    const plan = await this.entitlements.planFor(identity).catch(() => "free" as const);
    if (plan === "pro") return { allowed: true, used: 0, limit: Number.MAX_SAFE_INTEGER, resetAt: "" };
    if (feature === "active_repository" && options.demo) return { allowed: true, used: 0, limit: FREE_ACTIVE_REPOSITORIES, resetAt: "" };
    const [limit, windowHours] = feature === "advanced_impact"
      ? [FREE_ADVANCED_IMPACT_LIMIT, FREE_IMPACT_WINDOW_HOURS]
      : [feature === "mcp_client" ? FREE_ACTIVE_MCP_CLIENTS : FREE_ACTIVE_REPOSITORIES, FREE_IMPACT_WINDOW_HOURS];
    const before = this.meter.usage(identity, feature, limit, windowHours);
    if (before.used >= limit) return { ...before, allowed: false };
    return this.meter.consume(identity, feature, limit, windowHours);
  }
  usage(identity: string): Record<FreeFeature, UsageResult> {
    return {
      active_repository: this.meter.usage(identity, "active_repository", FREE_ACTIVE_REPOSITORIES, FREE_IMPACT_WINDOW_HOURS),
      mcp_client: this.meter.usage(identity, "mcp_client", FREE_ACTIVE_MCP_CLIENTS, FREE_IMPACT_WINDOW_HOURS),
      advanced_impact: this.meter.usage(identity, "advanced_impact", FREE_ADVANCED_IMPACT_LIMIT, FREE_IMPACT_WINDOW_HOURS),
    };
  }
}

const sharedMeter = new InMemoryUsageMeter();
const sharedGate = new FeatureGate(new FreeOnlyEntitlementService(), sharedMeter);
export function freeFeatureGate(): FeatureGate { return sharedGate; }
