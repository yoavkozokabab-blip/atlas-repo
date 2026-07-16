import crypto from "node:crypto";
import { ENV, liveChargesEnabled, paddleCheckoutConfigured, paddleWebhookConfigured } from "./config";
import { store, User, newId, PlanStatus } from "./store";
import { PAID_PLANS_ENABLED } from "@/app/_config";

export const PLANS = {
  free: {
    id: "free",
    name: "Free",
    price: 0,
    interval: null as null | "month",
    trialDays: 0,
    blurb: "Core local app, local scan, Ask Atlas, MCP, Impact, Debug, Plan Change and Map.",
  },
  pro: {
    id: "pro",
    name: "Pro",
    price: 19,
    interval: "month" as const,
    trialDays: 7,
    blurb: "Unlimited repositories and indexing, cloud sync, snapshot history, advanced search, priority indexing, new Pro capabilities and priority support.",
  },
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
export const BILLING_NOT_AVAILABLE = "BILLING_NOT_AVAILABLE" as const;
export function isPlanId(p: string): p is PlanId {
  return p === "free" || p === "pro" || p === "team";
}

export interface CheckoutResult {
  mode: "local" | "paddle";
  url: string;
}

export interface BillingUnavailable {
  code: typeof BILLING_NOT_AVAILABLE | "team_not_billed";
  message: string;
}

/** Provider-neutral billing contract. v1.0.5 always selects DisabledBillingProvider. */
export type PaddleEvent = {
  event_type?: string;
  data?: {
    id?: string;
    status?: string;
    customer_id?: string;
    subscription_id?: string;
    current_billing_period?: { ends_at?: string };
    next_billed_at?: string | null;
    custom_data?: { user_id?: string; plan?: string };
  };
};

export interface BillingProvider {
  createCheckout(user: User, plan: PlanId): Promise<CheckoutResult>;
  getSubscription(user: User): Promise<{ id: string | null; status: PlanStatus }>;
  reconcileSubscription(user: User): Promise<{ status: PlanStatus }>;
  scheduleCancellation(user: User): Promise<void>;
  cancelImmediately(user: User): Promise<void>;
  removeScheduledCancellation(user: User): Promise<void>;
  createCustomerPortalSession(user: User): Promise<CheckoutResult>;
  verifyWebhook(rawBody: string, header: string | null): boolean;
  processWebhookEvent(event: PaddleEvent): Promise<{ ok: boolean; action: string }>;
}

export class DisabledBillingProvider implements BillingProvider {
  private unavailable(): never { throw unavailable(BILLING_NOT_AVAILABLE); }
  async createCheckout(_user: User, _plan: PlanId): Promise<CheckoutResult> { return this.unavailable(); }
  async getSubscription(_user: User): Promise<{ id: string | null; status: PlanStatus }> { return this.unavailable(); }
  async reconcileSubscription(_user: User): Promise<{ status: PlanStatus }> { return this.unavailable(); }
  async scheduleCancellation(_user: User): Promise<void> { return this.unavailable(); }
  async cancelImmediately(_user: User): Promise<void> { return this.unavailable(); }
  async removeScheduledCancellation(_user: User): Promise<void> { return this.unavailable(); }
  async createCustomerPortalSession(_user: User): Promise<CheckoutResult> { return this.unavailable(); }
  verifyWebhook(_rawBody: string, _header: string | null): boolean { return false; }
  async processWebhookEvent(_event: PaddleEvent): Promise<{ ok: boolean; action: string }> {
    return { ok: true, action: "ignored_billing_disabled" };
  }
}

/**
 * Dormant Paddle adapter. It is dependency-injected so lifecycle behavior can
 * be exhaustively tested without live credentials. `activeProvider` below is
 * intentionally never this class in v1.0.5.
 */
export class PaddleBillingProvider implements BillingProvider {
  constructor(private readonly operations: BillingProvider) {}
  createCheckout(user: User, plan: PlanId) { return this.operations.createCheckout(user, plan); }
  getSubscription(user: User) { return this.operations.getSubscription(user); }
  reconcileSubscription(user: User) { return this.operations.reconcileSubscription(user); }
  scheduleCancellation(user: User) { return this.operations.scheduleCancellation(user); }
  cancelImmediately(user: User) { return this.operations.cancelImmediately(user); }
  removeScheduledCancellation(user: User) { return this.operations.removeScheduledCancellation(user); }
  createCustomerPortalSession(user: User) { return this.operations.createCustomerPortalSession(user); }
  verifyWebhook(rawBody: string, header: string | null) { return this.operations.verifyWebhook(rawBody, header); }
  processWebhookEvent(event: PaddleEvent) { return this.operations.processWebhookEvent(event); }
}

// Immutable by design: no environment value or client input can enable Paddle.
const activeProvider: BillingProvider = new DisabledBillingProvider();
export function billingProvider(): BillingProvider { return activeProvider; }

function paddleApiBase(): string {
  return ENV.paddleEnvironment === "production" ? "https://api.paddle.com" : "https://sandbox-api.paddle.com";
}

async function paddleRequest<T>(path: string, init: RequestInit): Promise<T> {
  const res = await fetch(`${paddleApiBase()}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      Authorization: `Bearer ${ENV.paddleApiKey}`,
      "Content-Type": "application/json",
      ...(init.headers || {}),
    },
  });
  const data = (await res.json().catch(() => ({}))) as T & { error?: { detail?: string } };
  if (!res.ok) {
    const detail = data?.error?.detail || `Paddle request failed with ${res.status}`;
    throw new Error(detail);
  }
  return data;
}

function checkoutUrlFromResponse(data: unknown): string | null {
  const root = data as { data?: { checkout?: { url?: string }; url?: string } };
  return root?.data?.checkout?.url || root?.data?.url || null;
}

export function proCheckoutReady(): boolean {
  return PAID_PLANS_ENABLED && paddleCheckoutConfigured();
}

export async function startCheckout(user: User, plan: PlanId): Promise<CheckoutResult> {
  if (!PAID_PLANS_ENABLED) return billingProvider().createCheckout(user, plan);
  if (plan === "team") throw unavailable("team_not_billed");
  if (plan === "free") {
    await store.update(user.id, { plan: "free", planStatus: "none", trialEndsAt: null, renewsAt: null });
    return { mode: "local", url: "/account" };
  }

  if (!paddleCheckoutConfigured()) throw unavailable(BILLING_NOT_AVAILABLE);

  const data = await paddleRequest<unknown>("/transactions", {
    method: "POST",
    body: JSON.stringify({
      items: [{ price_id: ENV.paddleProPriceId, quantity: 1 }],
      customer: { email: user.email, name: user.name || undefined },
      custom_data: { user_id: user.id, plan: "pro" },
      checkout: {
        success_url: `${ENV.appUrl}/billing/success?plan=pro`,
        cancel_url: `${ENV.appUrl}/billing/cancelled`,
      },
    }),
  });
  const url = checkoutUrlFromResponse(data);
  if (!url) throw new Error("Paddle did not return a checkout URL.");

  await store.audit({
    id: newId(),
    at: new Date().toISOString(),
    actorId: user.id,
    actorEmail: user.email,
    action: "paddle_checkout_started",
    meta: { plan, mode: ENV.paymentsMode, liveChargesEnabled: liveChargesEnabled() },
  });
  return { mode: "paddle", url };
}

export async function billingPortal(user: User): Promise<CheckoutResult> {
  if (!PAID_PLANS_ENABLED) return billingProvider().createCustomerPortalSession(user);
  return { mode: "local", url: "/account/billing" };
}

export async function cancelSubscription(user: User): Promise<void> {
  if (!PAID_PLANS_ENABLED) return billingProvider().cancelImmediately(user);
  await store.update(user.id, { planStatus: "canceled" });
}

export async function renewSubscription(user: User): Promise<void> {
  if (!PAID_PLANS_ENABLED) return billingProvider().removeScheduledCancellation(user);
  if (!user.paddleSubscriptionId) throw unavailable(BILLING_NOT_AVAILABLE);
  await store.update(user.id, { planStatus: "active" });
}

function unavailable(code: BillingUnavailable["code"]): Error & BillingUnavailable {
  const message =
    code === "team_not_billed"
      ? "Team billing is not available yet. Contact Atlas for team access."
      : "Billing is not available in this build.";
  return Object.assign(new Error(message), { code, message });
}

function timingSafeEqual(a: string, b: string): boolean {
  const ab = Buffer.from(a, "hex");
  const bb = Buffer.from(b, "hex");
  return ab.length === bb.length && crypto.timingSafeEqual(ab, bb);
}

export function verifyPaddleSignature(rawBody: string, header: string | null): boolean {
  if (!PAID_PLANS_ENABLED || !paddleWebhookConfigured() || !header) return false;
  const parts = Object.fromEntries(
    header.split(";").map((part) => {
      const [k, v] = part.split("=");
      return [k?.trim(), v?.trim()];
    })
  );
  const ts = parts.ts;
  const sig = parts.h1;
  if (!ts || !sig) return false;
  const expected = crypto.createHmac("sha256", ENV.paddleWebhookSecret).update(`${ts}:${rawBody}`).digest("hex");
  return timingSafeEqual(expected, sig);
}

function planStatusFromPaddle(status?: string): PlanStatus {
  if (status === "trialing") return "trialing";
  if (status === "active") return "active";
  if (status === "past_due") return "past_due";
  if (status === "canceled") return "canceled";
  return "active";
}

async function findWebhookUser(data: NonNullable<PaddleEvent["data"]>): Promise<User | undefined> {
  if (data.custom_data?.user_id) {
    const direct = await store.getById(data.custom_data.user_id);
    if (direct) return direct;
  }
  const users = await store.list();
  return users.find(
    (u) =>
      (!!data.customer_id && u.paddleCustomerId === data.customer_id) ||
      (!!data.subscription_id && u.paddleSubscriptionId === data.subscription_id) ||
      (!!data.id && u.paddleSubscriptionId === data.id)
  );
}

export async function handlePaddleEvent(event: PaddleEvent): Promise<{ ok: boolean; action: string }> {
  if (!PAID_PLANS_ENABLED) return billingProvider().processWebhookEvent(event);
  const eventType = event.event_type || "unknown";
  const data = event.data || {};
  const user = await findWebhookUser(data);
  if (!user) return { ok: true, action: "ignored_no_user" };

  if (eventType === "subscription.created" || eventType === "subscription.updated") {
    const subscriptionId = data.subscription_id || data.id || null;
    await store.update(user.id, {
      plan: "pro",
      planStatus: planStatusFromPaddle(data.status),
      paddleCustomerId: data.customer_id || user.paddleCustomerId || null,
      paddleSubscriptionId: subscriptionId,
      trialEndsAt: data.status === "trialing" ? data.next_billed_at || data.current_billing_period?.ends_at || null : user.trialEndsAt || null,
      renewsAt: data.next_billed_at || data.current_billing_period?.ends_at || null,
    });
  } else if (eventType === "subscription.canceled") {
    await store.update(user.id, { planStatus: "canceled", renewsAt: null });
  } else if (eventType === "transaction.paid" || eventType === "payment.succeeded") {
    await store.update(user.id, { plan: "pro", planStatus: "active", paddleCustomerId: data.customer_id || user.paddleCustomerId || null });
  } else if (eventType === "transaction.payment_failed" || eventType === "payment.failed") {
    await store.update(user.id, { planStatus: "past_due" });
  }

  await store.audit({
    id: newId(),
    at: new Date().toISOString(),
    actorId: user.id,
    actorEmail: user.email,
    action: "paddle_webhook",
    meta: { eventType, paddleId: data.id, customerId: data.customer_id },
  });
  return { ok: true, action: eventType };
}
