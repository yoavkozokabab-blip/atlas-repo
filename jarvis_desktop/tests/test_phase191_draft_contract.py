"""Phase 191 — registration proxy validation contract."""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from jarvis_desktop import accounts_routes


def test_register_validation_before_service_call():
    out = accounts_routes.accounts_register({"email": "bad", "password": "x"}, {})
    assert out["ok"] is False
    assert out["code"] == "validation_error"
    assert out["submitted"] is False
