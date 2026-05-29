"""Phase 71 — Real Tool-Use Foundation: data contracts.

These dataclasses make the safety guarantees explicit and inspectable:

- An ``ActionPlan`` is always a *dry run* — building it never touches the world.
- Every ``PlanStep`` carries an explicit ``RiskLevel`` and ``requires_approval``.
- ``RiskLevel.IRREVERSIBLE`` steps are forbidden in this phase (payments,
  orders, bookings, submits, logins, downloads, deletes, sends).  The planner
  refuses to emit them and the executor refuses to run them (defense in depth).
- A run only reaches ``RunStatus.SUCCESS`` when every step executed against a
  REAL provider and passed verification.  There is no mock success path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class StepKind(str, Enum):
    """The discrete, bounded actions this phase supports (read-only browsing)."""

    OPEN_SESSION = "open_session"   # launch a real browser
    SEARCH = "search"               # query a search engine
    OPEN_RESULT = "open_result"     # navigate to a chosen result
    OBSERVE = "observe"             # read current page structure (no fetch)
    SUMMARIZE = "summarize"         # summarize current page (no fetch)


class RiskLevel(str, Enum):
    READ_ONLY = "read_only"        # observation/summary of already-loaded page
    EXTERNAL = "external"          # fetches/navigates — reversible, needs approval
    IRREVERSIBLE = "irreversible"  # payments/orders/etc — FORBIDDEN this phase


# Goal / action text containing any of these is rejected outright this phase.
FORBIDDEN_KEYWORDS: frozenset[str] = frozenset({
    "pay", "payment", "purchase", "buy", "order", "checkout",
    "book", "booking", "reserve", "submit", "log in", "login",
    "sign in", "sign-in", "download", "delete", "send", "transfer",
    "subscribe", "add to cart", "place order", "confirm order",
})


class ForbiddenGoalError(ValueError):
    """Raised when a goal/step requests an irreversible or out-of-scope action."""


def scan_forbidden(text: str) -> str | None:
    """Return the first forbidden keyword found in *text*, else None."""
    low = (text or "").lower()
    for kw in FORBIDDEN_KEYWORDS:
        if kw in low:
            return kw
    return None


@dataclass(frozen=True)
class PlanStep:
    index: int
    kind: StepKind
    description: str
    risk: RiskLevel
    requires_approval: bool
    target: str = ""
    success_criteria: tuple[str, ...] = ()

    @property
    def is_external(self) -> bool:
        return self.risk in (RiskLevel.EXTERNAL, RiskLevel.IRREVERSIBLE)

    def preview(self) -> str:
        """Human-facing approval preview shown before the step runs."""
        lines = [
            f"Step {self.index}: {self.kind.value} [{self.risk.value}]",
            f"  what: {self.description}",
        ]
        if self.target:
            lines.append(f"  target: {self.target}")
        if self.success_criteria:
            lines.append("  success_when:")
            lines.extend(f"    - {c}" for c in self.success_criteria)
        return "\n".join(lines)


@dataclass(frozen=True)
class ActionPlan:
    goal: str
    steps: tuple[PlanStep, ...]

    @property
    def is_dry_run(self) -> bool:
        # Building/holding a plan never executes anything.
        return True

    @property
    def external_steps(self) -> tuple[PlanStep, ...]:
        return tuple(s for s in self.steps if s.is_external)

    def format(self) -> str:
        lines = [
            "Tool-use action plan (DRY RUN — nothing executed yet):",
            f"  goal: {self.goal}",
            f"  steps: {len(self.steps)}  (external/approval-gated: {len(self.external_steps)})",
            "",
        ]
        for step in self.steps:
            lines.append(step.preview())
            lines.append(f"  approval_required: {step.requires_approval}")
            lines.append("")
        return "\n".join(lines).rstrip()


@dataclass
class Observation:
    """Structured snapshot of the current UI (DOM-based for browser)."""

    real: bool
    provider: str
    url: str = ""
    title: str = ""
    headings: list[str] = field(default_factory=list)
    links: list[dict[str, str]] = field(default_factory=list)
    buttons: list[str] = field(default_factory=list)
    visible_text: str = ""
    screenshot_path: str = ""
    error: str = ""

    def short(self) -> str:
        return (
            f"real={self.real} provider={self.provider} "
            f"url={self.url or 'n/a'} title={self.title or 'n/a'} "
            f"links={len(self.links)} text_len={len(self.visible_text)}"
        )


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    reason: str


@dataclass(frozen=True)
class StepOutcome:
    """What the provider reports immediately after attempting a step."""

    ok: bool
    detail: str = ""
    data: dict[str, object] = field(default_factory=dict)


class StepStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED_UNAVAILABLE = "blocked_unavailable"  # no real provider — NOT success
    APPROVAL_DENIED = "approval_denied"
    FORBIDDEN = "forbidden"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    step: PlanStep
    status: StepStatus
    detail: str = ""
    verification: VerificationResult | None = None
    recovery_attempts: int = 0
    observation: Observation | None = None

    @property
    def ok(self) -> bool:
        return self.status == StepStatus.SUCCESS


class RunStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED_UNAVAILABLE = "blocked_unavailable"
    APPROVAL_DENIED = "approval_denied"
    FORBIDDEN = "forbidden"


@dataclass
class TaskRun:
    goal: str
    status: RunStatus
    steps: list[StepResult] = field(default_factory=list)
    summary: str = ""

    @property
    def ok(self) -> bool:
        return self.status == RunStatus.SUCCESS

    def format(self) -> str:
        lines = [
            "Tool-use task run:",
            f"  goal: {self.goal}",
            f"  status: {self.status.value}",
            "  steps:",
        ]
        for r in self.steps:
            v = ""
            if r.verification is not None:
                v = f" verify={'ok' if r.verification.ok else 'fail'}({r.verification.reason})"
            rc = f" recovery={r.recovery_attempts}" if r.recovery_attempts else ""
            lines.append(f"    [{r.status.value}] {r.step.kind.value}{v}{rc} — {r.detail[:160]}")
        if self.summary:
            lines.extend(["", "  summary:", *(f"    {ln}" for ln in self.summary.splitlines())])
        return "\n".join(lines)
