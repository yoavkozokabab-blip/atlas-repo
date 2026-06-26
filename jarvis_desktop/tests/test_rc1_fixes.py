"""RC-1 regression tests.

Locks in two fixes verified by dogfooding before RC-1:
  1. MCP `_sanitize` must NOT redact token-accounting metrics (they contain the
     substring "token" but are not secrets), while STILL redacting real secrets.
  2. `change_impact_simulation` must never list a subsystem as
     "probably won't break" when one of its files is reported as impacted.
"""
from __future__ import annotations


def test_token_metrics_are_not_redacted_but_secrets_still_are():
    from jarvis_desktop.mcp_server import runtime

    out = runtime._sanitize({
        "token_reduction_pct": 88.9,
        "file_level_tokens": 1000,
        "symbol_level_tokens": 110,
        "token_estimate": 1845,
        # genuine secret-shaped keys must still be redacted:
        "access_token": "sk-abcdefgh12345678",
        "authorization": "Bearer abc.def.ghi",
    })

    assert out["token_reduction_pct"] == 88.9
    assert out["file_level_tokens"] == 1000
    assert out["symbol_level_tokens"] == 110
    assert out["token_estimate"] == 1845
    assert out["access_token"] == "[REDACTED]"
    assert out["authorization"] == "[REDACTED]"


def test_wont_break_excludes_impacted_subsystems():
    from jarvis_desktop import api

    res = {
        "direct_impact": ["billing/models.py", "agent.py"],
        "indirect_impact": [],
        "affected_files": ["billing/models.py", "agent.py"],
        "what_probably_wont_break": [
            "`billing` subsystem (no resolved import path to `x.py`)",
            "`demo` subsystem (no resolved import path to `x.py`)",
        ],
        "simulation": {
            "what_probably_wont_break": [
                "`billing` subsystem (no resolved import path to `x.py`)",
                "`demo` subsystem (no resolved import path to `x.py`)",
            ]
        },
    }
    api._reconcile_wont_break(res)

    top = " ".join(res["what_probably_wont_break"])
    sim = " ".join(res["simulation"]["what_probably_wont_break"])
    assert "billing" not in top   # impacted -> removed (no contradiction)
    assert "demo" in top          # genuinely untouched -> kept
    assert "billing" not in sim   # the mirrored simulation copy is reconciled too
