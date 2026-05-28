"""Persistent assistant notifications (Phase 52/53)."""

from __future__ import annotations

import hashlib
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from config import DATA_DIR, PROJECT_ROOT
from core.logger import setup_logger
from core.persistent_json import atomic_write_json, load_json
from services.notification_throttle import NotificationThrottle

logger = setup_logger("jarvis.assistant.notifications")

NOTIFICATIONS_PATH = DATA_DIR / "notifications.json"
NOTIFICATION_ARCHIVE_DIR = DATA_DIR / "notification_archive"
NOTIFICATION_REPORT_DIR = PROJECT_ROOT / "reports" / "notifications"
MAX_NOTIFICATIONS = 200
DEDUP_WINDOW_SECONDS = 300.0


class NotificationKind(str, Enum):
    INVESTIGATION_COMPLETED = "investigation_completed"
    RUNTIME_DEGRADED = "runtime_degraded"
    DASHBOARD_FAILED = "dashboard_failed"
    STALE_POSITIONS = "stale_positions"
    REPLAY_VALIDATION_PASSED = "replay_validation_passed"
    PATCH_WORKFLOW_COMPLETED = "patch_workflow_completed"
    HEALING_ACTION = "healing_action"
    TASK_COMPLETED = "task_completed"
    PROACTIVE = "proactive"
    GENERIC = "generic"


@dataclass
class Notification:
    id: int
    kind: str
    title: str
    message: str
    severity: str = "info"
    source: str = "assistant"
    created_at: str = ""
    read: bool = False
    archived: bool = False
    suggested_action: str = ""
    related_task_id: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Notification:
        return cls(
            id=int(data["id"]),
            kind=str(data.get("kind", NotificationKind.GENERIC.value)),
            title=str(data.get("title", "")),
            message=str(data.get("message", "")),
            severity=str(data.get("severity", "info")),
            source=str(data.get("source", "assistant")),
            created_at=str(data.get("created_at", "")),
            read=bool(data.get("read")),
            archived=bool(data.get("archived")),
            suggested_action=str(data.get("suggested_action", "")),
            related_task_id=data.get("related_task_id"),
            metadata=dict(data.get("metadata") or {}),
        )


class NotificationStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: list[Notification] = []
        self._next_id = 1
        self._recent_hashes: dict[str, float] = {}
        self._throttle = NotificationThrottle(max_per_minute=12, default_cooldown_seconds=20.0)
        self._load()

    def _load(self) -> None:
        def _validate(data: Any) -> dict[str, Any] | None:
            return data if isinstance(data, dict) else None

        payload = load_json(
            NOTIFICATIONS_PATH,
            default={"next_id": 1, "items": []},
            validator=_validate,
        )
        self._next_id = int(payload.get("next_id", 1) or 1)
        items = payload.get("items", [])
        if isinstance(items, list):
            for raw in items:
                if isinstance(raw, dict):
                    try:
                        self._items.append(Notification.from_dict(raw))
                    except (TypeError, ValueError, KeyError):
                        continue
        if self._next_id <= max((n.id for n in self._items), default=0):
            self._next_id = max((n.id for n in self._items), default=0) + 1

    def _save(self) -> None:
        with self._lock:
            payload = {
                "next_id": self._next_id,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "items": [n.to_dict() for n in self._items if not n.archived][-MAX_NOTIFICATIONS:],
            }
        atomic_write_json(NOTIFICATIONS_PATH, payload)

    def add(
        self,
        kind: NotificationKind | str,
        title: str,
        message: str,
        *,
        severity: str = "info",
        source: str = "assistant",
        suggested_action: str = "",
        task_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Notification:
        kind_name = kind.value if isinstance(kind, NotificationKind) else str(kind)
        try:
            from alpha.notifications_filter import should_suppress_notification

            if should_suppress_notification(
                kind_name,
                title=title,
                message=message,
                severity=severity,
            ):
                logger.debug("notification suppressed (alpha mode): %s", title[:80])
                with self._lock:
                    for item in reversed(self._items):
                        if item.kind == kind_name:
                            return item
                return Notification(
                    id=0,
                    kind=kind_name,
                    title=title[:120],
                    message="(suppressed in alpha mode)",
                    severity=severity,
                )
        except Exception:
            pass
        digest = hashlib.sha256(f"{kind}:{title}:{message[:120]}".encode()).hexdigest()
        now_mono = datetime.now(timezone.utc).timestamp()
        severity_norm = (severity or "info").lower()
        kind_name = kind.value if isinstance(kind, NotificationKind) else str(kind)
        throttle = self._throttle.should_emit(
            title=title,
            message=message,
            severity=severity_norm,
            group=kind_name,
        )
        if not throttle.allowed:
            logger.debug(
                "notification throttled kind=%s severity=%s reason=%s collapsed=%s",
                kind_name,
                severity_norm,
                throttle.reason,
                throttle.collapsed_count,
            )
            with self._lock:
                for item in reversed(self._items):
                    if item.kind == kind_name and item.title == title[:120]:
                        return item
        with self._lock:
            last = self._recent_hashes.get(digest, 0.0)
            if now_mono - last < DEDUP_WINDOW_SECONDS:
                for item in reversed(self._items):
                    if item.title == title[:120] and item.message[:120] == message[:120]:
                        return item
            self._recent_hashes[digest] = now_mono
            note = Notification(
                id=self._next_id,
                kind=kind_name,
                title=title[:120],
                message=(message + throttle.collapsed_suffix)[:500],
                severity=severity_norm,
                source=source[:80],
                created_at=datetime.now(timezone.utc).isoformat(),
                suggested_action=(suggested_action or "")[:300],
                related_task_id=task_id,
                metadata=dict(metadata or {}),
            )
            self._next_id += 1
            self._items.append(note)
            if len(self._items) > MAX_NOTIFICATIONS * 2:
                self._items = self._items[-MAX_NOTIFICATIONS:]
        print(f"[NOTIFY] {note.title}: {note.message[:120]}", flush=True)
        self._save()
        self._write_report(note)
        self._overlay_notify(note)
        return note

    def list_notifications(
        self,
        *,
        unread_only: bool = False,
        include_archived: bool = False,
        limit: int = 20,
    ) -> list[Notification]:
        with self._lock:
            items = [n for n in self._items if include_archived or not n.archived]
        if unread_only:
            items = [item for item in items if not item.read]
        items.sort(key=lambda n: n.created_at, reverse=True)
        return items[:limit]

    def get(self, notification_id: int) -> Notification | None:
        with self._lock:
            for item in self._items:
                if item.id == notification_id:
                    return Notification(**asdict(item))
        return None

    def clear(self) -> int:
        with self._lock:
            count = len([n for n in self._items if not n.archived])
            self._items = [n for n in self._items if n.archived]
        self._save()
        return count

    def archive(self, notification_id: int) -> tuple[bool, str]:
        with self._lock:
            for item in self._items:
                if item.id == notification_id:
                    item.archived = True
                    item.read = True
                    self._save()
                    return True, f"Archived notification {notification_id}."
        return False, f"No notification with id {notification_id}."

    def explain(self, notification_id: int) -> str:
        note = self.get(notification_id)
        if note is None:
            return f"No notification with id {notification_id}."
        lines = [
            f"Notification {note.id}: {note.title}",
            f"  kind: {note.kind}",
            f"  severity: {note.severity}",
            f"  source: {note.source}",
            f"  created: {note.created_at}",
            f"  message: {note.message}",
        ]
        if note.suggested_action:
            lines.append(f"  suggested action: {note.suggested_action}")
        if note.related_task_id is not None:
            lines.append(f"  related task: {note.related_task_id}")
        return "\n".join(lines)

    def format_list(self, *, unread_only: bool = False) -> str:
        items = self.list_notifications(unread_only=unread_only)
        if not items:
            label = "unread notifications" if unread_only else "notifications"
            return f"No {label}."
        lines = [f"Notifications ({len(items)}):"]
        for item in items:
            flag = "" if item.read else " [new]"
            action = f" -> {item.suggested_action[:60]}" if item.suggested_action else ""
            lines.append(
                f"  [{item.id}] {item.kind}{flag} ({item.severity}) "
                f"{item.title}: {item.message[:90]}{action}"
            )
        return "\n".join(lines)

    def latest_unread(self) -> Notification | None:
        items = self.list_notifications(unread_only=True, limit=1)
        return items[0] if items else None

    def _write_report(self, note: Notification) -> None:
        try:
            NOTIFICATION_REPORT_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            path = NOTIFICATION_REPORT_DIR / f"{ts}_notification_{note.id}.json"
            path.write_text(
                __import__("json").dumps(note.to_dict(), indent=2, ensure_ascii=True),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.debug("Notification report failed: %s", exc)

    def _overlay_notify(self, note: Notification) -> None:
        try:
            from ui.overlay_app import notify_overlay_notification

            notify_overlay_notification(note.title, note.message, severity=note.severity)
        except Exception:
            pass


_store: NotificationStore | None = None
_store_lock = threading.Lock()


def get_notification_store() -> NotificationStore:
    global _store
    with _store_lock:
        if _store is None:
            _store = NotificationStore()
        return _store


def reset_notification_store_for_tests() -> None:
    global _store
    with _store_lock:
        _store = None


def notify_investigation_completed(
    title: str,
    *,
    summary: str = "",
    task_id: int | None = None,
) -> Notification:
    return get_notification_store().add(
        NotificationKind.INVESTIGATION_COMPLETED,
        title,
        summary or "Investigation completed.",
        severity="success",
        suggested_action="Run explain last result or continue previous session.",
        task_id=task_id,
    )


def notify_runtime_degraded(message: str, *, task_id: int | None = None) -> Notification:
    return get_notification_store().add(
        NotificationKind.RUNTIME_DEGRADED,
        "Runtime degraded",
        message,
        severity="warning",
        suggested_action="Run show runtime health or validate runtime integrity.",
        task_id=task_id,
    )


def notify_dashboard_failed(message: str) -> Notification:
    return get_notification_store().add(
        NotificationKind.DASHBOARD_FAILED,
        "Dashboard failed",
        message,
        severity="error",
        suggested_action="Run restart dashboard or show dashboard health.",
    )


def notify_stale_positions_detected(message: str) -> Notification:
    return get_notification_store().add(
        NotificationKind.STALE_POSITIONS,
        "Stale positions detected",
        message,
        severity="warning",
        suggested_action="Run show stale open positions or propose execution cleanup patch.",
    )


def notify_replay_validation_passed(message: str, *, task_id: int | None = None) -> Notification:
    return get_notification_store().add(
        NotificationKind.REPLAY_VALIDATION_PASSED,
        "Replay validation passed",
        message,
        severity="success",
        task_id=task_id,
    )


def notify_patch_workflow_completed(message: str, *, task_id: int | None = None) -> Notification:
    return get_notification_store().add(
        NotificationKind.PATCH_WORKFLOW_COMPLETED,
        "Patch workflow completed",
        message,
        severity="success",
        task_id=task_id,
    )


def notify_healing_action(message: str) -> Notification:
    return get_notification_store().add(
        NotificationKind.HEALING_ACTION,
        "Healing action performed",
        message,
        severity="info",
    )


def notify_proactive(title: str, message: str, *, suggested_action: str = "") -> Notification:
    return get_notification_store().add(
        NotificationKind.PROACTIVE,
        title,
        message,
        severity="warning",
        source="proactive_monitor",
        suggested_action=suggested_action,
    )


def show_notifications(*, unread_only: bool = False) -> str:
    return get_notification_store().format_list(unread_only=unread_only)


def clear_notifications() -> str:
    count = get_notification_store().clear()
    return f"Cleared {count} notification(s)."


def archive_notification(notification_id: int) -> str:
    ok, msg = get_notification_store().archive(notification_id)
    return msg if ok else msg


def explain_notification(notification_id: int) -> str:
    return get_notification_store().explain(notification_id)
