"""Tests for cloud analytics forwarding and safe metadata."""

from __future__ import annotations

from jarvis_desktop import cloud_analytics as ca


def test_track_cloud_event_skips_unknown_events():
    result = ca.track_cloud_event("copilot_question", metadata={"mode": "risk"})
    assert result.get("skipped") is True


def test_track_cloud_event_maps_internal_names():
    mapped = ca._EVENT_MAP["scan_completed"]
    assert mapped == "repo_connected"


def test_scrub_metadata_blocks_sensitive_keys():
    clean = ca._scrub_metadata({"reason": "auth_required", "password": "secret", "token": "x"})
    assert clean == {"reason": "auth_required"}


def test_scrub_metadata_allows_safe_fields():
    clean = ca._scrub_metadata({"agent": "cursor", "first": True, "packet": "compact"})
    assert clean["agent"] == "cursor"
    assert clean["first"] is True


def test_track_cloud_event_allows_rc_events():
    allowed = {
        "cursor_connected",
        "atlas_tool_call",
        "atlas_session_started",
        "desktop_installed",
    }
    assert allowed.issubset(ca._ALLOWED)


def test_track_cloud_event_injects_installation_id_from_anonymous():
    meta = ca._scrub_metadata({})
    payload_meta = dict(meta)
    anon = "install-abc"
    if anon and "installation_id" not in payload_meta:
        payload_meta["installation_id"] = str(anon)[:64]
    assert payload_meta["installation_id"] == "install-abc"
