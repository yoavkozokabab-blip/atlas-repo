"""Phase 71 — verification-driven failure recovery.

When a step fails verification (the UI did not change as expected — a stale
page, a results layout shift, a dropped session), ``plan_recovery`` decides a
bounded, safe recovery action.  Recovery never escalates risk: it only
re-observes, retries the same read/navigation, advances to the next candidate
result, or restarts the (reversible) session.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from tooluse.contracts import Observation, PlanStep, StepKind, VerificationResult


class RecoveryKind(str, Enum):
    NONE = "none"                 # not recoverable — give up
    REOBSERVE = "reobserve"       # observe again and re-verify (transient/timing)
    RETRY_STEP = "retry_step"     # re-run the same action
    NEXT_CANDIDATE = "next_candidate"  # OPEN_RESULT: try the next-best result
    RESTART_SESSION = "restart_session"  # session dropped — relaunch browser


@dataclass(frozen=True)
class RecoveryDecision:
    kind: RecoveryKind
    should_retry: bool
    reason: str


def plan_recovery(
    step: PlanStep,
    verification: VerificationResult,
    after: Observation,
    attempt: int,
    *,
    max_attempts: int = 2,
) -> RecoveryDecision:
    """Decide how (or whether) to recover from a failed step verification."""
    if attempt >= max_attempts:
        return RecoveryDecision(RecoveryKind.NONE, False, "max recovery attempts reached")

    # A dead/disconnected session is the clearest recoverable failure.
    if step.is_external and not after.real:
        return RecoveryDecision(RecoveryKind.RESTART_SESSION, True, "provider not connected; relaunch")

    if step.kind == StepKind.SEARCH:
        # Results page may not have rendered yet, or layout shifted.
        return RecoveryDecision(RecoveryKind.RETRY_STEP, True, "no results extracted; retry search")

    if step.kind == StepKind.OPEN_RESULT:
        # Either the click/navigation didn't take, or the chosen result is bad.
        return RecoveryDecision(RecoveryKind.NEXT_CANDIDATE, True, "navigation failed; try next result")

    if step.kind in (StepKind.OBSERVE, StepKind.SUMMARIZE):
        # Page may still be loading; observe again before giving up.
        return RecoveryDecision(RecoveryKind.REOBSERVE, True, "no text yet; re-observe")

    if step.kind == StepKind.OPEN_SESSION:
        return RecoveryDecision(RecoveryKind.RESTART_SESSION, True, "session launch failed; retry")

    return RecoveryDecision(RecoveryKind.NONE, False, "no recovery strategy for step")
