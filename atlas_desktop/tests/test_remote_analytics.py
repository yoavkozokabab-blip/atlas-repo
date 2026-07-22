"""v1.0.5 desktop analytics delivery stays local-first and privacy-safe."""

from __future__ import annotations

import json
import re

import pytest

from atlas_desktop import analytics_remote, operations


def test_remote_event_allowlist_is_frozen_analytics_only():
    assert analytics_remote._ALLOWED_EVENTS == {
        "desktop_launched", "sample_scan_completed", "real_repo_scan_completed", "scan_failed",
        "graph_opened", "impact_completed", "mcp_connected", "analytics_opted_out",
    }


def test_new_installation_identity_is_a_random_uuid(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(tmp_path))
    first = operations.get_installation_identity(data_dir=str(tmp_path))
    second = operations.get_installation_identity(data_dir=str(tmp_path))
    assert re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", first["installation_id"])
    assert second["installation_id"] == first["installation_id"]


def test_corrupt_installation_identity_is_replaced_with_uuidv4(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(tmp_path))
    path = tmp_path / "operations" / "installation.json"
    path.parent.mkdir(parents=True)
    path.write_text('{"installation_id":"ATLAS_REPOSITORY_NAME_MARKER"}', encoding="utf-8")
    identity = operations.get_installation_identity(data_dir=str(tmp_path))
    assert re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", identity["installation_id"])


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
        properties={"surface": "desktop", "duration_active_ms": 123, "message": "ordinary unknown field"},
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
    }) == {}


@pytest.mark.parametrize("marker", [
    r"C:\Users\ATLAS_WINDOWS_USERNAME_MARKER\ATLAS_REPOSITORY_FOLDER_MARKER",
    "ATLAS_REPOSITORY_NAME_MARKER", "ATLAS_FILE_PATH_MARKER", "ATLAS_FILE_NAME_MARKER",
    "ATLAS_SOURCE_CODE_MARKER", "ATLAS_PROMPT_MARKER", "ATLAS_SYMBOL_NAME_MARKER",
    "ATLAS_GRAPH_CONTENT_MARKER", "ATLAS_IMPACT_RESULT_MARKER", "ATLAS_TERMINAL_OUTPUT_MARKER",
    "unique-atlas-email-marker@example.test", "Bearer ATLAS_ACCESS_TOKEN_MARKER",
    "ATLAS_PASSWORD_MARKER", r"ATLAS_STACK_TRACE_MARKER C:\Users\private\repo\file.py:9",
])
def test_remote_analytics_rejects_forbidden_categories_recursively(tmp_path, monkeypatch, marker):
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(tmp_path))
    monkeypatch.setattr(analytics_remote, "_schedule_flush", lambda: None)
    analytics_remote.track_pipeline_event(
        "graph_opened", installation_id="installation-12345678", app_version="1.0.6", build_commit="e" * 40,
        properties={"surface": "graph", "nested": [{"status": marker}]},
    )
    assert analytics_remote._load_queue() == []


def test_legacy_account_and_install_events_never_enqueue(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(tmp_path))
    monkeypatch.setattr(analytics_remote, "_schedule_flush", lambda: None)
    for event in ("account_create_started", "account_login_completed", "account_deleted", "app_first_run"):
        analytics_remote.track_pipeline_event(
            event, installation_id="installation-12345678", app_version="1.0.6", build_commit="f" * 40,
            properties={},
        )
    assert analytics_remote._load_queue() == []


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
