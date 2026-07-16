/** Provider-neutral entitlement state machine. Client redirects and local UI
 * mutations are intentionally absent: only a verified provider event or a
 * server-side reconciliation can change a paid entitlement. */
export type EntitlementState =
  | "free" | "trialing" | "active" | "past_due" | "paused"
  | "cancel_scheduled" | "canceled" | "expired" | "unknown";

export type EntitlementRecord = { state: EntitlementState; revision: number; observedAt: string | null };
export type EntitlementTransition =
  | { kind: "provider_observed"; state: EntitlementState; observedAt: string }
  | { kind: "schedule_cancellation"; observedAt: string }
  | { kind: "cancel_immediately"; observedAt: string }
  | { kind: "remove_scheduled_cancellation"; observedAt: string };

export function hasPaidAccess(state: EntitlementState): boolean {
  return state === "trialing" || state === "active" || state === "cancel_scheduled";
}

export function transitionEntitlement(
  current: EntitlementRecord,
  event: EntitlementTransition,
): EntitlementRecord {
  // Delayed provider messages cannot overwrite newer observed state.
  if (current.observedAt && event.observedAt < current.observedAt) return current;
  let state = current.state;
  if (event.kind === "provider_observed") {
    state = event.state;
  } else if (event.kind === "schedule_cancellation") {
    if (state === "active" || state === "trialing" || state === "past_due") state = "cancel_scheduled";
  } else if (event.kind === "cancel_immediately") {
    state = "canceled";
  } else if (event.kind === "remove_scheduled_cancellation" && state === "cancel_scheduled") {
    // This is a provider-confirmed server operation; it cannot resurrect an
    // already canceled entitlement.
    state = "active";
  }
  return { state, revision: current.revision + (state === current.state ? 0 : 1), observedAt: event.observedAt };
}
