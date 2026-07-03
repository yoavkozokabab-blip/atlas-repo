"""Phase 199 — desktop proxies for launch readiness dashboard."""
from __future__ import annotations

import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from atlas_desktop import accounts_routes


def test_accounts_routes_include_phase199_endpoints():
    paths = {path for method, path in accounts_routes.ACCOUNTS_ROUTES}
    assert "/api/accounts/admin/launch-readiness" in paths
    assert "/api/accounts/admin/feedback" in paths
    assert "/api/accounts/admin/invites" in paths
    assert "/api/accounts/acquisition/event" in paths
    assert "/api/accounts/validate-invite" in paths


def test_static_launch_readiness_markers():
    static = os.path.join(os.path.dirname(__file__), "..", "static")
    with open(os.path.join(static, "atlas_admin.js"), encoding="utf-8") as f:
        admin_js = f.read()
    with open(os.path.join(static, "index.html"), encoding="utf-8") as f:
        html = f.read()
    assert "loadLaunch" in admin_js
    assert "Do users actually want Atlas?" in admin_js
    assert 'data-tab="launch"' in html
    assert "atlas_acquisition.js" in html
