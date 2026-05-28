"""Persist approved apps for safe launch."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import APPROVED_APPS_PATH, BACKUPS_DIR, DATA_DIR
from core.logger import setup_logger

logger = setup_logger("jarvis.apps.registry")


@dataclass(frozen=True)
class ApprovedApp:
    app_id: str
    display_name: str
    shortcut_path: Path
    target_path: Path | None = None
    approved_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "app_id": self.app_id,
            "display_name": self.display_name,
            "shortcut_path": str(self.shortcut_path),
            "target_path": str(self.target_path) if self.target_path else None,
            "approved_at": self.approved_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ApprovedApp | None:
        try:
            sid = str(data.get("app_id", "")).strip()
            shortcut = Path(str(data.get("shortcut_path", "")))
            if not sid or not shortcut:
                return None
            target_raw = data.get("target_path")
            target = Path(str(target_raw)) if target_raw else None
            return cls(
                app_id=sid,
                display_name=str(data.get("display_name", sid)),
                shortcut_path=shortcut,
                target_path=target,
                approved_at=str(data.get("approved_at", "")),
            )
        except (TypeError, ValueError):
            return None


class AppRegistry:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or APPROVED_APPS_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        BACKUPS_DIR.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.path.is_file():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            apps = data.get("apps") if isinstance(data, dict) else data
            if isinstance(apps, dict):
                return apps
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not load approved apps: %s", exc)
        return {}

    def _save(self, apps: dict[str, dict[str, Any]]) -> None:
        if self.path.is_file():
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup = BACKUPS_DIR / f"approved_apps_{stamp}.json"
            try:
                shutil.copy2(self.path, backup)
            except OSError as exc:
                logger.debug("Approved apps backup skipped: %s", exc)
        payload = {"apps": apps, "updated_at": datetime.now(timezone.utc).isoformat()}
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list_approved(self) -> list[ApprovedApp]:
        out: list[ApprovedApp] = []
        for raw in self._load().values():
            app = ApprovedApp.from_dict(raw)
            if app is not None:
                out.append(app)
        return sorted(out, key=lambda a: a.display_name.lower())

    def get(self, app_id: str) -> ApprovedApp | None:
        raw = self._load().get(app_slug_key(app_id))
        if raw is None:
            return None
        return ApprovedApp.from_dict(raw)

    def approve(self, app: ApprovedApp) -> ApprovedApp:
        apps = self._load()
        entry = app.to_dict()
        entry["approved_at"] = datetime.now(timezone.utc).isoformat()
        apps[app.app_id] = entry
        self._save(apps)
        return ApprovedApp.from_dict(entry) or app

    def forget(self, app_id: str) -> bool:
        apps = self._load()
        key = app_slug_key(app_id)
        if key not in apps:
            return False
        del apps[key]
        self._save(apps)
        return True


def app_slug_key(app_id: str) -> str:
    from apps.discovery import app_slug

    return app_slug(app_id)
