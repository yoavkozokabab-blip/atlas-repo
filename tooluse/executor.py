"""Phase 71 — the observe → (plan) → approve → act → verify → recover loop.

The executor is the single place where the safety contract is enforced:

1. FORBIDDEN guard (defense in depth): an irreversible step aborts the run.
2. APPROVAL gate: every external step must be approved by the injected
   ``approver`` callback before it runs; denial aborts the run.
3. REAL provider required: an external step on a non-real provider returns
   BLOCKED_UNAVAILABLE — there is no mock success.
4. VERIFY after each step against observed state.
5. RECOVER (bounded) when verification fails; if recovery cannot restore the
   expected state, the step FAILS and the run aborts.

The executor never plans or executes anything on its own — it is handed a
pre-built dry-run :class:`ActionPlan` and an explicit human ``approver``.
"""

from __future__ import annotations

from typing import Callable

from core.logger import setup_logger
from tooluse.contracts import (
    ActionPlan,
    Observation,
    PlanStep,
    RiskLevel,
    StepKind,
    StepResult,
    StepStatus,
    RunStatus,
    TaskRun,
)
from tooluse.provider import ToolProvider
from tooluse.recovery import plan_recovery
from tooluse.verifier import build_summary, verify_step

logger = setup_logger("jarvis.tooluse.executor")

# An approver receives a step and returns True to allow it, False to deny.
Approver = Callable[[PlanStep], bool]


def deny_all(_step: PlanStep) -> bool:
    """Default approver: deny everything (safe default)."""
    return False


class ToolUseExecutor:
    def __init__(
        self,
        provider: ToolProvider,
        approver: Approver = deny_all,
        *,
        max_recovery: int = 2,
    ) -> None:
        self.provider = provider
        self.approver = approver
        self.max_recovery = max_recovery

    def run(self, plan: ActionPlan) -> TaskRun:
        run = TaskRun(goal=plan.goal, status=RunStatus.SUCCESS, steps=[])

        for step in plan.steps:
            # 1. Defense in depth — irreversible actions are never executed.
            if step.risk == RiskLevel.IRREVERSIBLE:
                run.steps.append(StepResult(step, StepStatus.FORBIDDEN,
                                            "irreversible action refused by executor"))
                run.status = RunStatus.FORBIDDEN
                return self._finish(run)

            # 2. Human approval before every external action.
            if step.requires_approval:
                approved = False
                try:
                    approved = bool(self.approver(step))
                except Exception as exc:
                    logger.warning("approver raised: %s", exc)
                    approved = False
                if not approved:
                    run.steps.append(StepResult(step, StepStatus.APPROVAL_DENIED,
                                                "human approval not granted"))
                    run.status = RunStatus.APPROVAL_DENIED
                    return self._finish(run)
                logger.info("approved step %d (%s)", step.index, step.kind.value)

            # 3. External steps require a REAL provider — no mock success.
            if step.is_external and not self.provider.is_real():
                run.steps.append(StepResult(step, StepStatus.BLOCKED_UNAVAILABLE,
                                            "no real tool provider available (mock not accepted)"))
                run.status = RunStatus.BLOCKED_UNAVAILABLE
                return self._finish(run)

            # 4. Act, observe, verify (with bounded recovery).
            # _execute_with_verification only ever returns SUCCESS or FAILED.
            result = self._execute_with_verification(step)
            run.steps.append(result)
            if not result.ok:
                run.status = RunStatus.FAILED
                return self._finish(run)

            # Carry the summary from the SUMMARIZE step into the run output.
            if step.kind == StepKind.SUMMARIZE and result.observation is not None:
                run.summary = build_summary(result.observation)

        return self._finish(run)

    def _execute_with_verification(self, step: PlanStep) -> StepResult:
        before = self.provider.observe()
        outcome = self.provider.execute(step)
        after = self.provider.observe()
        verification = verify_step(step, before, after)
        attempts = 0

        while not verification.ok and attempts < self.max_recovery:
            decision = plan_recovery(step, verification, after, attempts,
                                     max_attempts=self.max_recovery)
            if not decision.should_retry:
                break
            logger.info("recovery for step %d: %s (%s)", step.index, decision.kind.value, decision.reason)
            try:
                self.provider.apply_recovery(decision, step)
            except Exception as exc:
                logger.warning("recovery action raised: %s", exc)
                break
            after = self.provider.observe()
            verification = verify_step(step, before, after)
            attempts += 1

        if verification.ok:
            return StepResult(step, StepStatus.SUCCESS, outcome.detail,
                              verification=verification, recovery_attempts=attempts,
                              observation=after)
        return StepResult(step, StepStatus.FAILED,
                          outcome.detail or "verification failed",
                          verification=verification, recovery_attempts=attempts,
                          observation=after)

    def _finish(self, run: TaskRun) -> TaskRun:
        try:
            self.provider.close()
        except Exception:
            pass
        return run


# ---------------------------------------------------------------------------
# Approver helpers
# ---------------------------------------------------------------------------

def approve_all(_step: PlanStep) -> bool:
    """Explicit opt-in approver (the operator running the task approves all)."""
    return True


def console_approver(printer: Callable[[str], None] = print) -> Approver:
    """
    Approver that prints each step preview.  Returns an approver that approves
    only when the operator has pre-authorized via this factory (used by the
    smoke with an explicit --approve flag).  Without pre-authorization the gate
    denies, so the approval requirement is always real.
    """
    def _approver(step: PlanStep) -> bool:
        printer(f"[APPROVAL REQUIRED]\n{step.preview()}")
        return False
    return _approver
