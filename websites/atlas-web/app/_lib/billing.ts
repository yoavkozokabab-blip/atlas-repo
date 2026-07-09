import { liveChargesEnabled } from "./config";
import { store, User } from "./store";

export const PLANS = {
  free: { id: "free", name: "Free", price: 0, interval: null as null | "month", trialDays: 0,
    blurb: "Repository scanning, local dependency graph, MCP integration, Claude Code, Cursor, Codex, Ask Atlas, Debug, Impact analysis, change planning and dependency map." },
  pro: { id: "pro", name: "Pro", price: 19, interval: "month" as const, trialDays: 7,
    blurb: "Everything in Free plus unlimited repositories, unlimited indexing, cloud account sync, snapshot history, advanced search, priority indexing, early access features and priority support." },
  team: {
    id: "team",
    name: "Team",
    price: null as number | null,
    interval: null as null | "month",
    trialDays: 0,
    blurb: "Coming soon. Contact us.",
  },
} as const;

export type PlanId = keyof typeof PLANS;
export function isPlanId(p: string): p is PlanId {
  return p === "free" || p === "pro" || p === "team";
}

export interface CheckoutResult {
  mode: "stub" | "live";
  url: string;
}

/**
 * Start checkout for a plan.
 *
 * SAFETY: In this build no real money ever moves. The live branch is intentionally
 * inert and falls through to the stub, which grants a local Pro trial. Paddle is
 * the Merchant of Record for paid subscriptions; Atlas never stores payment
 * details. Team billing is intentionally not implemented.
 */
export async function startCheckout(user: User, plan: PlanId): Promise<CheckoutResult> {
  if (plan === "team") return { mode: "stub", url: "/contact" };
  if (plan === "free") {
    await store.update(user.id, { plan: "free", planStatus: "none", trialEndsAt: null, renewsAt: null });
    return { mode: "stub", url: "/account" };
  }

  if (liveChargesEnabled()) {
    // A real Paddle checkout session would be created here once Pro billing is
    // wired and explicitly enabled. Deliberately NOT active - fall through to the
    // stub so no live charge can occur from this build.
  }

  // STUB: grant a local Pro trial, no charge.
  const trialEnds = new Date(Date.now() + (PLANS[plan].trialDays || 7) * 86_400_000).toISOString();
  await store.update(user.id, {
    plan,
    planStatus: "trialing",
    trialEndsAt: trialEnds,
    renewsAt: trialEnds,
  });
  return { mode: "stub", url: `/billing/success?plan=${plan}&mode=stub` };
}

/** Billing portal. Stub returns the local billing page until Paddle is connected. */
export function billingPortal(_user: User): CheckoutResult {
  return { mode: "stub", url: "/account/billing" };
}

export async function cancelSubscription(user: User): Promise<void> {
  await store.update(user.id, { planStatus: "canceled" });
}
export async function renewSubscription(user: User): Promise<void> {
  const renews = new Date(Date.now() + 30 * 86_400_000).toISOString();
  await store.update(user.id, { planStatus: "active", renewsAt: renews });
}
