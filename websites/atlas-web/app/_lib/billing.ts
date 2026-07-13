import crypto from "node:crypto";
import { ENV, liveChargesEnabled, paddleCheckoutConfigured, paddleWebhookConfigured } from "./config";
import { store, User, newId, PlanStatus } from "./store";

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
export function isPlanId(p: string): p is PlanId {
  return p === "free" || p === "pro" || p === "team";
}

export interface CheckoutResult {
  mode: "local" | "paddle";
  url: string;
}

export interface BillingUnavailable {
  code: "billing_not_configured" | "team_not_billed";
  message: string;
}

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
  return paddleCheckoutConfigured();
}

export async function startCheckout(user: User, plan: PlanId): Promise<CheckoutResult> {
  if (plan === "team") throw unavailable("team_not_billed");
  if (plan === "free") {
    await store.update(user.id, { plan: "free", planStatus: "none", trialEndsAt: null, renewsAt: null });
    return { mode: "local", url: "/account" };
  }

  if (!paddleCheckoutConfigured()) throw unavailable("billing_not_configured");

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

export function billingPortal(_user: User): CheckoutResult {
  return { mode: "local", url: "/account/billing" };
}

export async function cancelSubscription(user: User): Promise<void> {
  await store.update(user.id, { planStatus: "canceled" });
}

export async function renewSubscription(user: User): Promise<void> {
  if (!user.paddleSubscriptionId) throw unavailable("billing_not_configured");
  await store.update(user.id, { planStatus: "active" });
}

function unavailable(code: BillingUnavailable["code"]): Error & BillingUnavailable {
  const message =
    code === "team_not_billed"
      ? "Team billing is not available yet. Contact Atlas for team access."
      : "Pro checkout is not configured yet. Set PADDLE_API_KEY, PADDLE_PRO_PRICE_ID, and PADDLE_WEBHOOK_SECRET.";
  return Object.assign(new Error(message), { code, message });
}

function timingSafeEqual(a: string, b: string): boolean {
  const ab = Buffer.from(a, "hex");
  const bb = Buffer.from(b, "hex");
  return ab.length === bb.length && crypto.timingSafeEqual(ab, bb);
}

export function verifyPaddleSignature(rawBody: string, header: string | null): boolean {
  if (!paddleWebhookConfigured() || !header) return false;
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

type PaddleEvent = {
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
