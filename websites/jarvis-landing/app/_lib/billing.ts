import { liveChargesEnabled } from "./config";
import { store, User } from "./store";

export const PLANS = {
  free: { id: "free", name: "Free", price: 0, interval: null as null | "month", trialDays: 0,
    blurb: "Local scanning, one repository, basic Change Plans." },
  pro: { id: "pro", name: "Pro", price: 29, interval: "month" as const, trialDays: 7,
    blurb: "Unlimited repositories, impact analysis, investigation, risk detection." },
  team: { id: "team", name: "Team", price: null as number | null, interval: "month" as const, trialDays: 0,
    blurb: "Seats, shared context and SSO for engineering teams." },
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
 * inert and falls through to the stub, which grants a local trial. Real Stripe
 * checkout must be added deliberately (SDK + env + explicit approval).
 */
export async function startCheckout(user: User, plan: PlanId): Promise<CheckoutResult> {
  if (plan === "team") return { mode: "stub", url: "/contact" };
  if (plan === "free") {
    await store.update(user.id, { plan: "free", planStatus: "none", trialEndsAt: null, renewsAt: null });
    return { mode: "stub", url: "/account" };
  }

  if (liveChargesEnabled()) {
    // Real Stripe Checkout session would be created here once billing is wired and
    // explicitly approved. Deliberately NOT active — fall through to stub so no
    // live charge can occur from this build.
  }

  // STUB: grant a local trial, no charge.
  const trialEnds = new Date(Date.now() + (PLANS[plan].trialDays || 7) * 86_400_000).toISOString();
  await store.update(user.id, {
    plan,
    planStatus: "trialing",
    trialEndsAt: trialEnds,
    renewsAt: trialEnds,
  });
  return { mode: "stub", url: `/billing/success?plan=${plan}&mode=stub` };
}

/** Billing portal. Stub returns the local billing page until Stripe is connected. */
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
