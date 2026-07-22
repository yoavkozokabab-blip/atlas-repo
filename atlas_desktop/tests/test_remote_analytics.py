"""v1.0.5 desktop analytics delivery stays local-first and privacy-safe."""

from __future__ import annotations

import json

from atlas_desktop import analytics_remote, operations


def test_remote_analytics_is_offline_by_default_for_source_runs(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(tmp_path))
    monkeypatch.delenv("ATLAS_ANALYTICS_ENDPOINT", raising=False)
    assert analytics_remote.analytics_endpoint() == ""
    analytics_remote.track_pipeline_event(
        "scan_completed", installation_id="installation-12345678", app_version="1.0.5", build_commit="a" * 40,
        properties={"surface": "desktop"},
    )
    assert (tmp_path / "operations" / "analytics-outbox.json").is_file()


def test_remote_analytics_allowlists_and_flushes_without_private_data(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(tmp_path))
    monkeypatch.setenv("ATLAS_ANALYTICS_ENDPOINT", "https://collector.example.test/api/analytics/desktop-events")
    sent = []

    class Response:
        status = 202
        def __enter__(self): return self
        def __exit__(self, *_args): return False

    def fake_urlopen(request, timeout):
        sent.append(json.loads(request.data.decode("utf-8")))
        assert timeout == 2.0
        return Response()

    monkeypatch.setattr(analytics_remote.urllib.request, "urlopen", fake_urlopen)
    analytics_remote.track_pipeline_event(
        "scan_completed", installation_id="installation-12345678", app_version="1.0.5", build_commit="b" * 40,
        properties={"surface": "desktop", "duration_active_ms": 123, "message": "C:\\Users\\private\\repo", "path": "nope"},
    )
    # A direct flush makes this deterministic; the daemon may already have sent it.
    analytics_remote.flush()
    assert sent
    event = sent[0]["events"][0]
    assert event["eventName"] == "real_repo_scan_completed"
    assert event["properties"] == {"surface": "desktop", "duration_active_ms": 123}
    serialized = json.dumps(event).lower()
    assert "c:\\users\\private" not in serialized
    assert '"path"' not in serialized
    assert '"message"' not in serialized


def test_remote_analytics_opt_out_blocks_delivery(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(tmp_path))
    monkeypatch.setenv("ATLAS_ANALYTICS_ENDPOINT", "https://collector.example.test/api/analytics/desktop-events")
    assert analytics_remote.set_analytics_opt_out(True)["opted_out"] is True
    analytics_remote.track_pipeline_event(
        "app_started", installation_id="installation-12345678", app_version="1.0.5", build_commit="c" * 40, properties={},
    )
    assert not (tmp_path / "operations" / "analytics-outbox.json").exists()


def test_remote_analytics_rejects_ui_heartbeats_and_nested_private_data(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(tmp_path))
    monkeypatch.delenv("ATLAS_ANALYTICS_ENDPOINT", raising=False)
    analytics_remote.track_pipeline_event(
        "screen_active_ended", installation_id="installation-12345678", app_version="1.0.5", build_commit="d" * 40,
        properties={"screen": "graph", "duration_active_ms": 2400, "duration_elapsed_ms": 3000, "path": "C:\\Users\\private\\repo"},
    )
    assert not (tmp_path / "operations" / "analytics-outbox.json").exists()
    assert analytics_remote._safe_properties({
        "surface": {"path": "C:\\Users\\private\\repo"},
        "workflow": "scan",
    }) == {"workflow": "scan"}


def test_remote_analytics_retries_are_bounded_and_diagnostics_are_safe(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(tmp_path))
    monkeypatch.setenv("ATLAS_ANALYTICS_ENDPOINT", "https://collector.example.test/api/analytics/desktop-events")
    monkeypatch.setattr(analytics_remote, "_schedule_flush", lambda: None)

    def rejected(_request, timeout):
        raise analytics_remote.urllib.error.HTTPError("https://collector.example.test", 400, "Bad Request", {}, None)

    monkeypatch.setattr(analytics_remote.urllib.request, "urlopen", rejected)
    analytics_remote.track_pipeline_event(
        "scan_completed", installation_id="installation-12345678", app_version="1.0.5", build_commit="d" * 40,
        properties={"workflow": "scan"},
    )
    assert analytics_remote.flush() is False
    assert analytics_remote.flush() is False
    assert analytics_remote.flush() is False
    assert analytics_remote._load_queue() == []
    assert analytics_remote.diagnostics()["last_status_class"] == "http_4xx"
    assert analytics_remote.diagnostics()["rejected"] == 1


def test_pipeline_stays_functional_when_remote_delivery_is_unavailable(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(tmp_path))
    monkeypatch.setattr(analytics_remote, "track_pipeline_event", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("offline")))
    result = operations.pipeline_track_event("scan_completed", modules=3)
    assert result["ok"] is True
