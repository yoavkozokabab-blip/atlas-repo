"""Sprint 2 — unit tests for S2.1 through S2.7.

Covers:
  S2.1 — Memory per-entry size limit
  S2.2 — Default TTL for ephemeral categories
  S2.3 — ThreadRegistry liveness detection
  S2.4 — Startup intent coverage validation
  S2.5 — Config startup validation
  S2.6 — Overlay retry cap (headless fallback at > 3 crashes)
  S2.7 — Screenshot count-based pruning
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def memory_enabled(monkeypatch):
    monkeypatch.setattr("config.MEMORY_ENABLED", True)


@pytest.fixture()
def memory_store(tmp_path):
    """Isolated PersonalMemoryStore backed by a temp file."""
    from memory.store import PersonalMemoryStore
    return PersonalMemoryStore(path=tmp_path / "mem.json")


# ---------------------------------------------------------------------------
# S2.1 — per-entry size limit
# ---------------------------------------------------------------------------

class TestMemorySizeLimit:
    def test_large_entry_is_truncated(self, memory_store):
        big_text = "x" * 20_000
        entry = memory_store.remember(big_text, category="personal_note")
        assert len(entry.text.encode("utf-8")) <= 10_240

    def test_small_entry_is_not_truncated(self, memory_store):
        text = "hello world"
        entry = memory_store.remember(text, category="personal_note")
        assert entry.text == text

    def test_exactly_limit_passes(self, memory_store):
        text = "a" * 10_240
        entry = memory_store.remember(text, category="personal_note")
        assert len(entry.text.encode("utf-8")) <= 10_240


# ---------------------------------------------------------------------------
# S2.2 — default TTL for ephemeral categories
# ---------------------------------------------------------------------------

class TestDefaultTTL:
    @pytest.mark.parametrize("cat", ["session", "short_term", "temporary_fact"])
    def test_ephemeral_category_gets_default_ttl(self, memory_store, cat):
        entry = memory_store.remember("some fact", category=cat)
        assert entry.expires_at != "", (
            f"category '{cat}' should have a default TTL but expires_at is empty"
        )

    def test_non_ephemeral_category_no_default_ttl(self, memory_store):
        entry = memory_store.remember("permanent fact", category="personal_note")
        assert entry.expires_at == "", (
            "personal_note should not get a default TTL"
        )

    def test_explicit_ttl_overrides_default(self, memory_store):
        entry = memory_store.remember("session fact", category="session", ttl_seconds=60)
        # expires_at should reflect 60s, not 86400s
        from datetime import datetime, timezone
        exp = datetime.fromisoformat(entry.expires_at)
        now = datetime.now(timezone.utc)
        delta_seconds = (exp - now).total_seconds()
        assert 50 <= delta_seconds <= 70, f"Expected ~60s TTL, got {delta_seconds:.0f}s"

    def test_no_ttl_on_ephemeral_when_passed_none_explicitly(self, memory_store):
        # Passing ttl_seconds=None still uses the default.
        entry = memory_store.remember("temp", category="session", ttl_seconds=None)
        assert entry.expires_at != ""


# ---------------------------------------------------------------------------
# S2.3 — ThreadRegistry
# ---------------------------------------------------------------------------

class TestThreadRegistry:
    def setup_method(self):
        from core.thread_registry import ThreadRegistry
        self.reg = ThreadRegistry()

    def test_register_and_alive_thread(self):
        t = threading.Thread(target=lambda: time.sleep(5), daemon=True)
        t.start()
        self.reg.register("alive", t)
        dead = self.reg.heartbeat_check()
        assert "alive" not in dead
        t.join(timeout=0)  # don't wait — it's a daemon

    def test_detect_dead_thread(self):
        t = threading.Thread(target=lambda: None, daemon=True)
        t.start()
        t.join(timeout=2)
        assert not t.is_alive()
        self.reg.register("dead", t)
        dead = self.reg.heartbeat_check()
        assert "dead" in dead

    def test_register_fn_alive(self):
        self.reg.register_fn("svc", lambda: True)
        dead = self.reg.heartbeat_check()
        assert "svc" not in dead

    def test_register_fn_dead(self):
        self.reg.register_fn("dead_svc", lambda: False)
        dead = self.reg.heartbeat_check()
        assert "dead_svc" in dead

    def test_update_replaces_reference(self):
        t1 = threading.Thread(target=lambda: None, daemon=True)
        t1.start(); t1.join()
        self.reg.register("t", t1)
        t2 = threading.Thread(target=lambda: time.sleep(5), daemon=True)
        t2.start()
        self.reg.update("t", t2)
        dead = self.reg.heartbeat_check()
        assert "t" not in dead

    def test_deregister_removes_from_check(self):
        self.reg.register_fn("gone", lambda: False)
        self.reg.deregister("gone")
        dead = self.reg.heartbeat_check()
        assert "gone" not in dead

    def test_snapshot(self):
        self.reg.register_fn("up", lambda: True)
        self.reg.register_fn("down", lambda: False)
        snap = self.reg.snapshot()
        assert snap["up"] is True
        assert snap["down"] is False

    def test_heartbeat_does_not_raise_on_fn_exception(self):
        def bad_fn():
            raise RuntimeError("oops")
        self.reg.register_fn("err", bad_fn)
        # Should not raise; the thread is treated as dead
        dead = self.reg.heartbeat_check()
        assert "err" in dead


# ---------------------------------------------------------------------------
# S2.4 — Startup intent coverage
# ---------------------------------------------------------------------------

class TestIntentCoverage:
    def test_all_handlers_present(self):
        from core.startup_validation import validate_intent_coverage
        from actions.registry import ActionRegistry
        registry = ActionRegistry()
        missing = validate_intent_coverage(registry)
        assert missing == [], (
            f"Missing handlers for {len(missing)} intents: {missing[:5]}"
        )

    def test_detects_missing_handler(self):
        from core.startup_validation import validate_intent_coverage

        mock_registry = MagicMock()
        mock_registry.has.return_value = False  # claim no handlers exist

        with patch("config.IMPLEMENTED_INTENTS", new=frozenset({"fake_intent_xyz"})):
            missing = validate_intent_coverage(mock_registry)
        assert "fake_intent_xyz" in missing


# ---------------------------------------------------------------------------
# S2.5 — Config startup validation
# ---------------------------------------------------------------------------

class TestConfigValidation:
    def test_clean_config_passes(self, tmp_path):
        from core.startup_validation import validate_config
        with patch("core.startup_validation.Path") as mock_path_cls:
            # Use real logic but redirect DATA_DIR writes to tmp_path
            pass  # actual config is valid; just run it
        from core.startup_validation import ValidationSeverity

        issues = validate_config()
        # DATA_DIR should be writable on the test machine
        config_type_errors = [
            i for i in issues if "frozenset" in i.message or "empty" in i.message
        ]
        assert config_type_errors == [], f"Unexpected config errors: {issues}"

    def test_detects_non_frozenset_implemented(self):
        from core.startup_validation import ValidationSeverity, validate_config

        with patch("config.IMPLEMENTED_INTENTS", new=None):
            issues = validate_config()
        assert any("IMPLEMENTED_INTENTS" in i.message for i in issues)
        assert all(i.severity == ValidationSeverity.CRITICAL for i in issues)

    def test_detects_subset_violation(self):
        from core.startup_validation import validate_config

        with patch("config.IMPLEMENTED_INTENTS", new=frozenset({"intent_not_in_allowed"})):
            with patch("config.ALLOWED_INTENTS", new=frozenset({"other_intent"})):
                issues = validate_config()
        assert any("not in ALLOWED" in i.message for i in issues)


# ---------------------------------------------------------------------------
# S2.6 — Overlay retry cap
# ---------------------------------------------------------------------------

class TestOverlayRetryCap:
    def test_recover_disabled_after_max_crashes(self):
        """After _MAX_QT_RESTART_ATTEMPTS crashes, recover_if_crashed disables overlay."""
        from ui.overlay_app import OverlayController

        ctrl = OverlayController.__new__(OverlayController)
        # Minimal init — don't start any threads
        ctrl._enabled = True
        ctrl._qt_thread = None
        ctrl._qt_crash_count = OverlayController._MAX_QT_RESTART_ATTEMPTS
        ctrl._last_qt_exception = "fake crash"
        ctrl._last_recovery_monotonic = 0.0
        ctrl._window = None
        ctrl._app = None
        ctrl._stop_qt = threading.Event()
        ctrl._ready = threading.Event()
        ctrl._qt_start_count = 0

        with patch("ui.overlay_app.OVERLAY_QT_ENABLED", True), \
             patch("ui.overlay_app._runtime_overlay_enabled", return_value=True), \
             patch("ui.overlay_app.OVERLAY_RECOVERY_BACKOFF_SECONDS", 0.0), \
             patch("core.runtime_state.get_runtime_state") as mock_rt:
            mock_rt.return_value.set_overlay = MagicMock()
            result = ctrl.recover_if_crashed()

        assert result is False
        assert ctrl._enabled is False

    def test_recover_allowed_below_max_crashes(self):
        """recover_if_crashed returns True when crash count is below limit."""
        from ui.overlay_app import OverlayController

        ctrl = OverlayController.__new__(OverlayController)
        ctrl._enabled = True
        ctrl._qt_thread = None       # no thread yet — simulates a crashed state
        ctrl._qt_crash_count = 0
        ctrl._last_qt_exception = None
        ctrl._last_recovery_monotonic = 0.0
        ctrl._window = None
        ctrl._app = None
        ctrl._stop_qt = threading.Event()
        ctrl._ready = threading.Event()
        ctrl._qt_start_count = 0

        # ensure_started sets _qt_thread to a live thread as a side effect
        fake_thread = MagicMock()
        fake_thread.is_alive.return_value = True

        def _fake_ensure_started():
            ctrl._qt_thread = fake_thread

        with patch("ui.overlay_app.OVERLAY_QT_ENABLED", True), \
             patch("ui.overlay_app._runtime_overlay_enabled", return_value=True), \
             patch("ui.overlay_app.OVERLAY_RECOVERY_BACKOFF_SECONDS", 0.0), \
             patch.object(ctrl, "ensure_started", side_effect=_fake_ensure_started):
            result = ctrl.recover_if_crashed()

        assert result is True


# ---------------------------------------------------------------------------
# S2.7 — Screenshot count pruning
# ---------------------------------------------------------------------------

class TestScreenshotCountPruning:
    def test_prune_keeps_10_most_recent(self, tmp_path, monkeypatch):
        from vision.screen_capture import _prune_screenshot_count

        # Create 15 PNG files with distinct mtimes
        for i in range(15):
            f = tmp_path / f"shot_{i:03d}.png"
            f.write_bytes(b"\x89PNG")
            # Give each file a distinct mtime
            ts = 1_000_000 + i
            import os
            os.utime(f, (ts, ts))

        removed: list[str] = []

        def fake_remove(path):
            removed.append(path.name)
            return True

        monkeypatch.setattr("vision.screen_capture.remove_file_best_effort", fake_remove)
        _prune_screenshot_count(tmp_path)
        assert set(removed) == {f"shot_{i:03d}.png" for i in range(5)}

    def test_prune_no_op_when_under_limit(self, tmp_path):
        from vision.screen_capture import _prune_screenshot_count

        for i in range(5):
            (tmp_path / f"s{i}.png").write_bytes(b"\x89PNG")
        _prune_screenshot_count(tmp_path)
        assert len(list(tmp_path.glob("*.png"))) == 5

    def test_prune_handles_empty_dir(self, tmp_path):
        from vision.screen_capture import _prune_screenshot_count
        _prune_screenshot_count(tmp_path)  # must not raise
