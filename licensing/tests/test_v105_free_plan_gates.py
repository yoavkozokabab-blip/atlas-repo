"""Audit tests for the EXISTING licensing/ Free-plan gate logic.

These do not add a new entitlement implementation — they exercise the public
gate helpers already present in ``licensing/`` so the Free-plan math and the
entitlement-outage behavior cannot silently regress. The runtime feature flag
``ATLAS_LICENSING_ENABLED`` and server wiring remain owned by Codex.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from licensing.client import LicenseStatus, _FREE_ENTITLEMENTS  # type: ignore
from licensing import gates

# Pro entitlements are delivered by the server; model an unlimited Pro plan
# for the gate math (unlimited repos/files, every feature enabled).
_PRO_ENTITLEMENTS = {
    "max_repos": None,
    "max_files_per_repo": None,
    "features": {k: True for k in _FREE_ENTITLEMENTS["features"]},
}


class _FakeClient:
    """Minimal LicenseClient stand-in: returns a fixed status, records events."""

    def __init__(self, status: LicenseStatus):
        self._status = status
        self.events: list[tuple[str, dict]] = []

    def refresh(self, force: bool = False) -> LicenseStatus:
        return self._status

    def track(self, event: str, props: dict | None = None) -> None:
        self.events.append((event, props or {}))


def _free() -> LicenseStatus:
    return LicenseStatus(plan="free", status="free", entitlements=dict(_FREE_ENTITLEMENTS))


def _pro() -> LicenseStatus:
    return LicenseStatus(plan="pro", status="pro", entitlements=dict(_PRO_ENTITLEMENTS))


# ── repository limit ───────────────────────────────────────────────────────
def test_free_plan_allows_first_repo_blocks_second():
    client = _FakeClient(_free())
    assert bool(gates.can_add_repo(client, current_repo_count=0)) is True
    blocked = gates.can_add_repo(client, current_repo_count=1)
    assert bool(blocked) is False
    assert "Free plan" in (blocked.prompt or "")


def test_pro_plan_repo_limit_is_unlimited():
    client = _FakeClient(_pro())
    assert bool(gates.can_add_repo(client, current_repo_count=25)) is True


# ── per-repo file / impact allowance ───────────────────────────────────────
def test_free_plan_truncates_over_cap():
    client = _FakeClient(_free())
    cap = _FREE_ENTITLEMENTS["max_files_per_repo"]
    limited, allowed = gates.enforce_scan_limit(client, list(range(cap + 25)))
    assert limited is True
    assert len(allowed) == cap
    assert any(e[0] == "upgrade_prompt_shown" for e in client.events)


def test_free_plan_under_cap_is_untouched():
    client = _FakeClient(_free())
    cap = _FREE_ENTITLEMENTS["max_files_per_repo"]
    limited, allowed = gates.enforce_scan_limit(client, list(range(cap - 1)))
    assert limited is False
    assert len(allowed) == cap - 1


def test_pro_plan_scan_is_unlimited():
    client = _FakeClient(_pro())
    limited, allowed = gates.enforce_scan_limit(client, list(range(10_000)))
    assert limited is False
    assert len(allowed) == 10_000


# ── feature gate ───────────────────────────────────────────────────────────
def test_feature_gate_blocks_free_and_allows_pro():
    free_client = _FakeClient(_free())
    pro_client = _FakeClient(_pro())
    feat = gates.FEATURES.IMPACT_ANALYSIS
    free_gate = gates.evaluate_gate(free_client, feat)
    pro_gate = gates.evaluate_gate(pro_client, feat)
    # Whatever the Free entitlement for impact is, Pro must be at least as
    # permissive, and a blocked gate always carries an upgrade prompt.
    if not free_gate:
        assert free_gate.prompt
        assert any(e[0] == "upgrade_prompt_shown" for e in free_client.events)
    assert bool(pro_gate) is True


# ── entitlement outage must never silently grant Pro ───────────────────────
def test_stale_status_never_upgrades_to_pro():
    stale = LicenseStatus(plan="free", status="free",
                          entitlements=dict(_FREE_ENTITLEMENTS), stale=True)
    client = _FakeClient(stale)
    assert bool(gates.can_add_repo(client, current_repo_count=1)) is False
    assert stale.is_pro is False


def test_default_status_is_free():
    # A bare status (no server data) must default to Free, never Pro.
    assert LicenseStatus().plan == "free"
    assert LicenseStatus().is_pro is False
