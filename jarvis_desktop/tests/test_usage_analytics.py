"""Tests for RC usage analytics helpers."""

from __future__ import annotations

from jarvis_desktop import cloud_analytics as ca
from jarvis_desktop import usage_analytics as ua


def test_track_agent_connected_queues_cursor(monkeypatch):
    sent = []

    def fake_track(event_name, **kwargs):
        sent.append((event_name, kwargs.get("metadata") or {}))
        return {"ok": True}

    monkeypatch.setattr(ca, "track_cloud_event", fake_track)
    monkeypatch.setattr(ua, "_installation_meta", lambda: {"installation_id": "abc"})

    ua.track_agent_connected("cursor")
    names = [e[0] for e in sent]
    assert "cursor_connected" in names
    assert "agent_context_injected" in names


def test_track_tool_call_first_and_repeat(monkeypatch):
    sent = []

    def fake_track(event_name, **kwargs):
        sent.append(event_name)
        return {"ok": True}

    monkeypatch.setattr(ca, "track_cloud_event", fake_track)
    monkeypatch.setattr(ua, "_installation_meta", lambda: {"installation_id": "abc"})
    ua._first_tool_call_sent = False
    ua._session_started_sent = False

    ua.track_tool_call("atlas_repo_health")
    ua.track_tool_call("atlas_repo_health")

    assert sent.count("atlas_session_started") == 1
    assert sent.count("atlas_first_tool_call") == 1
    assert sent.count("atlas_tool_call") == 2


def test_track_context_used_maps_agent(monkeypatch):
    sent = []

    def fake_track(event_name, **kwargs):
        sent.append(event_name)
        return {"ok": True}

    monkeypatch.setattr(ca, "track_cloud_event", fake_track)
    monkeypatch.setattr(ua, "_installation_meta", lambda: {"installation_id": "abc"})
    ua._session_started_sent = False

    ua.track_context_used("codex")
    assert "atlas_context_used" in sent
    assert "codex_used" in sent
