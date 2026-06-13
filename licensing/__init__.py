"""Atlas desktop licensing.

Thin client + feature gates that talk to the Atlas website's `/api/license`
endpoint and enforce the Free / Trial / Pro entitlements locally.

Typical use at app launch::

    from licensing import licensing

    licensing.set_email(user_email)          # from sign-in / settings
    status = licensing.refresh()             # network check (cached 24h)
    if status.banner:
        ui.show_banner(status.banner)

Gating a Pro feature::

    from licensing import licensing, FEATURES

    gate = licensing.feature_gate(FEATURES.IMPACT_ANALYSIS)
    if not gate.allowed:
        ui.show_upgrade_prompt(gate.prompt)  # emits upgrade_prompt_shown
        return

Enforcing the Free scan limit::

    limited, allowed_files = licensing.enforce_scan_limit(found_files)
"""

from .client import LicenseClient, LicenseStatus
from .gates import FEATURES, FeatureGate

# Process-wide singleton — import this everywhere.
licensing = LicenseClient()

__all__ = ["licensing", "LicenseClient", "LicenseStatus", "FEATURES", "FeatureGate"]
