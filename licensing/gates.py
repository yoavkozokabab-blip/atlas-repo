"""Feature gates + scan limits, layered on top of LicenseClient.

A "gate" answers: may the current user use feature X right now? When the
answer is no, it carries an upgrade prompt and emits an `upgrade_prompt_shown`
analytics event so conversion can be measured. Call `gate.clicked()` if the
user acts on the prompt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional, TYPE_CHECKING

if TYPE_CHECKING:  # avoid a runtime import cycle
    from .client import LicenseClient


class FEATURES:
    """Canonical feature names (match the server entitlements + event names)."""

    DEPENDENCY_GRAPH = "dependency_graph"
    IMPACT_ANALYSIS = "impact_analysis"
    CONTEXT_COMPRESSION = "context_compression"
    INVESTIGATION = "investigation"
    RISK_DETECTION = "risk_detection"


# Human-readable names for upgrade prompts.
_LABELS = {
    FEATURES.DEPENDENCY_GRAPH: "Dependency Graph",
    FEATURES.IMPACT_ANALYSIS: "Impact Analysis",
    FEATURES.CONTEXT_COMPRESSION: "AI Context Compression",
    FEATURES.INVESTIGATION: "Investigation Mode",
    FEATURES.RISK_DETECTION: "Architecture Risk Detection",
}


@dataclass
class FeatureGate:
    """Result of evaluating a feature gate."""

    feature: str
    allowed: bool
    plan: str
    prompt: Optional[str] = None
    _client: Any = None  # LicenseClient (kept private; for .clicked())

    def clicked(self) -> None:
        """Record that the user clicked the upgrade prompt."""
        if self._client is not None:
            self._client.track("upgrade_prompt_clicked", {"feature_name": self.feature})

    def __bool__(self) -> bool:  # `if gate:` reads naturally
        return self.allowed


def _label(feature: str) -> str:
    return _LABELS.get(feature, feature.replace("_", " ").title())


def evaluate_gate(client: "LicenseClient", feature: str) -> FeatureGate:
    """Evaluate whether `feature` is allowed for the current user.

    Emits `feature_used` when allowed and `upgrade_prompt_shown` when blocked.
    """
    status = client.refresh()  # respects the 24h cache
    allowed = status.feature_enabled(feature)

    if allowed:
        client.track("feature_used", {"feature_name": feature})
        return FeatureGate(feature=feature, allowed=True, plan=status.plan, _client=client)

    prompt = (
        f"{_label(feature)} is a Pro feature. "
        "Start a free 7-day trial to unlock it — no credit card required."
    )
    client.track("upgrade_prompt_shown", {"feature_name": feature})
    return FeatureGate(feature=feature, allowed=False, plan=status.plan, prompt=prompt, _client=client)


def enforce_scan_limit(client: "LicenseClient", files: Iterable[Any]):
    """Apply the Free-tier per-repo file cap.

    Returns ``(limited, allowed_files)``:
      * ``limited``  — True if the list was truncated (Free tier hit the cap).
      * ``allowed_files`` — the files that may be scanned (truncated on Free).

    Pro / Trial users are unlimited and get the input back unchanged.
    """
    files = list(files)
    status = client.refresh()
    cap = status.max_files_per_repo  # None == unlimited
    if cap is None or len(files) <= cap:
        return False, files

    # Free tier over the cap → truncate and surface an upgrade prompt.
    client.track("upgrade_prompt_shown", {"feature_name": "file_limit", "found": len(files), "cap": cap})
    return True, files[:cap]


def can_add_repo(client: "LicenseClient", current_repo_count: int) -> FeatureGate:
    """Whether the user may add another repository under their plan."""
    status = client.refresh()
    cap = status.max_repos  # None == unlimited
    if cap is None or current_repo_count < cap:
        return FeatureGate(feature="repo_slot", allowed=True, plan=status.plan, _client=client)
    prompt = (
        f"The Free plan includes {cap} repository. "
        "Upgrade to Pro for unlimited repositories — start a free 7-day trial."
    )
    client.track("upgrade_prompt_shown", {"feature_name": "repo_limit", "cap": cap})
    return FeatureGate(feature="repo_slot", allowed=False, plan=status.plan, prompt=prompt, _client=client)
