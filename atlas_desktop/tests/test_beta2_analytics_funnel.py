"""beta.2 launch instrumentation: privacy contract, enums, and exactly-once first value.

The funnel added in beta.2 touches the two places a leak would be worst: the
MCP tool dispatcher (which sees task text, file names and returned context) and
the scan failure path (whose exception strings routinely contain the repository
path). These tests exist so that a future edit which starts forwarding any of
that fails loudly instead of shipping.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

import pytest

from atlas_desktop import analytics_remote


# Values that must never survive into a queued analytics event, whichever
# property someone puts them in.
SENSITIVE_VALUES = [
    r"C:\Users\Yoav\secret_repo\auth.py",
    "/home/user/company/private.py",
    "atlas-private-monorepo",
    "billing_service.py",
    "https://github.com/acme/secret-repo",
    "def charge(card): return gateway.post(card)",
    "Refactor the auth module and explain the token flow",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIn0.abcdefghijklmnop",
    "ghp_ABCDEFghijklmnopqrstuvwxyz1234567",
    "sb_secret_livekey_abcdef123456",
    "yoav@example.com",
    'Traceback (most recent call last):\n  File "C:\\repo\\a.py", line 3',
]

NEW_EVENTS = [
    "onboarding_local_mode_selected",
    "repository_selected",
    "scan_started",
    "mcp_configured",
    "mcp_initialize_success",
    "atlas_tool_called",
    "first_value_reached",
    "feedback_opened",
    "feedback_submitted",
]


@pytest.fixture(autouse=True)
def _isolated() -> None:
    """conftest already gives each test its own data root; only reset the
    module-level opt-out latch so one test cannot silence the next."""
    analytics_remote._LOCAL_OPT_OUT = None
    analytics_remote._LOCAL_OPT_OUT_PATH = None


def _queue() -> List[Dict[str, Any]]:
    return analytics_remote._load_queue()


def _emit(event: str, **properties: Any) -> None:
    analytics_remote.track_pipeline_event(
        event,
        installation_id="11111111-2222-4333-8444-555555555555",
        app_version="1.0.6-beta.2",
        build_commit="0" * 40,
        properties=properties,
    )


# --- the event contract itself ---------------------------------------------

def test_every_new_event_is_allowlisted_on_the_desktop() -> None:
    for event in NEW_EVENTS:
        assert event in analytics_remote._ALLOWED_EVENTS, event


def test_an_event_outside_the_allowlist_is_never_queued() -> None:
    _emit("totally_new_event_someone_added", surface="x")
    assert _queue() == []


def test_new_properties_are_allowlisted() -> None:
    for prop in ("tool_name", "error_code", "repo_size_bucket", "category"):
        assert prop in analytics_remote._ALLOWED_PROPERTIES, prop


# --- privacy: the point of the whole exercise -------------------------------

@pytest.mark.parametrize("value", SENSITIVE_VALUES)
@pytest.mark.parametrize("event", NEW_EVENTS)
def test_sensitive_values_never_reach_a_queued_event(event: str, value: str) -> None:
    """Try every sensitive value through every allowlisted property of every new event."""
    for prop in ("tool_name", "error_code", "repo_size_bucket", "category",
                 "agent", "surface", "workflow", "outcome", "status"):
        _emit(event, **{prop: value})

    blob = json.dumps(_queue())
    for fragment in ("secret_repo", "auth.py", "private.py", "atlas-private-monorepo",
                     "billing_service", "github.com", "def charge", "Refactor the auth",
                     "eyJhbGci", "ghp_", "sb_secret_", "@example.com", "Traceback"):
        assert fragment not in blob, f"{fragment!r} leaked via {event}"


@pytest.mark.parametrize("value", SENSITIVE_VALUES)
def test_sensitive_values_never_reach_an_unknown_property(value: str) -> None:
    _emit("atlas_tool_called", repository_path=value, prompt=value, file_name=value)
    blob = json.dumps(_queue())
    assert "repository_path" not in blob and "prompt" not in blob and "file_name" not in blob


# --- closed enums -----------------------------------------------------------

def test_tool_name_outside_the_shipped_set_is_dropped() -> None:
    _emit("atlas_tool_called", tool_name="atlas_exfiltrate_everything", agent="claude")
    props = _queue()[0]["properties"]
    assert "tool_name" not in props
    assert props["agent"] == "claude"


def test_tool_name_inside_the_shipped_set_survives() -> None:
    _emit("atlas_tool_called", tool_name="atlas_what_breaks", agent="cursor", outcome="success")
    props = _queue()[0]["properties"]
    assert props["tool_name"] == "atlas_what_breaks"
    assert props["agent"] == "cursor"


def test_unknown_agent_becomes_other_rather_than_free_text() -> None:
    _emit("mcp_configured", agent="SomeUnreleasedEditor/2.1 (build 9)")
    assert _queue()[0]["properties"]["agent"] == "other"


def test_unknown_error_code_becomes_unknown_safe() -> None:
    _emit("scan_failed", error_code="SomeInternalParserExplosion")
    props = _queue()[0]["properties"]
    assert props["error_code"] == "unknown_safe"


def test_an_error_code_carrying_a_path_never_stores_the_path() -> None:
    """An exception string in error_code collapses to the sentinel, not a path."""
    _emit("scan_failed", error_code="OSError: [Errno 13] C:\\repo\\secret.py")
    blob = json.dumps(_queue())
    assert "C:\\\\repo" not in blob and "secret.py" not in blob and "Errno" not in blob
    if _queue():
        assert _queue()[0]["properties"].get("error_code") == "unknown_safe"


def test_every_documented_error_code_is_accepted() -> None:
    for code in ("permission_denied", "invalid_repository", "parser_failure",
                 "index_failure", "cancelled", "disk_failure", "unknown_safe"):
        analytics_remote._save_queue([])
        _emit("scan_failed", error_code=code)
        assert _queue()[0]["properties"]["error_code"] == code


def test_repo_size_bucket_is_a_bucket_not_a_count() -> None:
    analytics_remote._save_queue([])
    _emit("scan_started", repo_size_bucket="4821")
    assert "repo_size_bucket" not in _queue()[0]["properties"]
    analytics_remote._save_queue([])
    _emit("scan_started", repo_size_bucket="large")
    assert _queue()[0]["properties"]["repo_size_bucket"] == "large"


def test_feedback_category_is_a_closed_enum_and_never_the_message() -> None:
    _emit("feedback_submitted", category="Impact missed a dependent module in my project")
    blob = json.dumps(_queue())
    assert "dependent module" not in blob
    if _queue():
        assert _queue()[0]["properties"].get("category") in (None, "general")


def test_the_funnel_actually_queues_events_positive_control() -> None:
    """Guards the privacy tests above: they must not pass on an empty queue."""
    for event, props in (
        ("onboarding_local_mode_selected", {"surface": "first_run"}),
        ("repository_selected", {"surface": "workbench", "repo_size_bucket": "medium"}),
        ("scan_started", {"repo_size_bucket": "medium", "workflow": "scan"}),
        ("mcp_configured", {"agent": "claude", "outcome": "success"}),
        ("mcp_initialize_success", {"agent": "cursor", "outcome": "success"}),
        ("atlas_tool_called", {"tool_name": "atlas_what_breaks", "agent": "codex", "outcome": "success"}),
        ("first_value_reached", {"tool_name": "atlas_what_breaks", "agent": "claude"}),
        ("feedback_opened", {"surface": "support"}),
        ("feedback_submitted", {"category": "bug", "outcome": "success"}),
    ):
        analytics_remote._save_queue([])
        _emit(event, **props)
        queued = _queue()
        assert queued, f"{event} produced no event - the funnel would silently be empty"
        assert queued[0]["eventName"] == event
        for key, value in props.items():
            assert queued[0]["properties"].get(key) == value, (event, key)


# --- first value: exactly once ---------------------------------------------

def test_first_value_is_recorded_exactly_once_across_restarts() -> None:
    assert analytics_remote.first_value_reached() is False
    assert analytics_remote.mark_first_value(agent="claude", tool_name="atlas_what_breaks") is True
    assert analytics_remote.first_value_reached() is True

    # Second successful tool in the same process.
    assert analytics_remote.mark_first_value(agent="claude", tool_name="atlas_root_cause") is False

    # Simulated restart: module state is irrelevant, the marker file governs.
    analytics_remote._LOCAL_OPT_OUT = None
    assert analytics_remote.mark_first_value(agent="cursor", tool_name="atlas_plan_change") is False
    assert analytics_remote.first_value_reached() is True


def test_first_value_marker_holds_no_repository_information() -> None:
    analytics_remote.mark_first_value(agent="claude", tool_name="atlas_what_breaks")
    stored = json.loads((__import__("pathlib").Path(analytics_remote._first_value_path())).read_text(encoding="utf-8"))
    assert set(stored) <= {"reached", "at", "agent", "tool_name"}


def test_first_value_fails_closed_when_it_cannot_persist(monkeypatch: pytest.MonkeyPatch) -> None:
    """A disk problem must not turn one installation into a stream of first values."""
    monkeypatch.setattr(analytics_remote, "_write_json", lambda *_a, **_k: False)
    assert analytics_remote.mark_first_value(agent="claude", tool_name="atlas_what_breaks") is False


# --- opt-out still governs everything new -----------------------------------

def test_opt_out_blocks_every_new_event() -> None:
    analytics_remote.set_analytics_opt_out(True)
    for event in NEW_EVENTS:
        _emit(event, surface="x")
    assert _queue() == []
