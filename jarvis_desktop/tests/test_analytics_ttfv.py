"""Tests for TTFV computation (mirrors analytics-ttfv.ts)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _diff_sec(a: str, b: str) -> int | None:
    ms = datetime.fromisoformat(b.replace("Z", "+00:00")).timestamp() - datetime.fromisoformat(
        a.replace("Z", "+00:00")
    ).timestamp()
    if ms < 0:
        return None
    return round(ms)


def compute_ttfv(m: dict) -> dict:
    def d(k1, k2):
        if not m.get(k1) or not m.get(k2):
            return None
        return _diff_sec(m[k1], m[k2])

    return {
        "install_to_open_sec": d("installed_at", "opened_at"),
        "open_to_login_sec": d("opened_at", "login_success_at"),
        "login_to_repo_sec": d("login_success_at", "repo_connected_at"),
        "repo_to_first_context_sec": d("repo_connected_at", "first_context_at"),
        "total_ttfv_sec": d("installed_at", "first_context_at"),
    }


def test_total_ttfv_chain():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    m = {
        "installed_at": t0.isoformat().replace("+00:00", "Z"),
        "opened_at": (t0 + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
        "login_success_at": (t0 + timedelta(minutes=10)).isoformat().replace("+00:00", "Z"),
        "repo_connected_at": (t0 + timedelta(minutes=20)).isoformat().replace("+00:00", "Z"),
        "first_context_at": (t0 + timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),
    }
    out = compute_ttfv(m)
    assert out["install_to_open_sec"] == 300
    assert out["total_ttfv_sec"] == 1800


def test_missing_milestone_returns_none():
    out = compute_ttfv({"installed_at": "2026-01-01T00:00:00Z"})
    assert out["total_ttfv_sec"] is None
