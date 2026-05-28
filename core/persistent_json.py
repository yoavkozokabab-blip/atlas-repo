"""Atomic JSON persistence with corruption recovery (Phase 53)."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar

from core.logger import setup_logger

logger = setup_logger("jarvis.persistent_json")

T = TypeVar("T")


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def atomic_write_json(path: Path, payload: Any, *, indent: int = 2) -> None:
    """Write JSON via temp file + replace to avoid partial/corrupt files."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_dir = path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.stat().st_size > 0:
        try:
            shutil.copy2(path, backup_dir / f"{path.stem}_{_timestamp()}.json")
        except OSError as exc:
            logger.debug("Backup skipped for %s: %s", path, exc)
    fd, tmp_name = tempfile.mkstemp(
        suffix=".json",
        prefix=f"{path.stem}_",
        dir=str(path.parent),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=indent, ensure_ascii=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except OSError:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def load_json(
    path: Path,
    *,
    default: T,
    validator: Callable[[Any], T | None] | None = None,
) -> T:
    """Load JSON with backup recovery on corruption."""
    path = Path(path)
    if not path.is_file():
        return default
    raw_text = ""
    try:
        raw_text = path.read_text(encoding="utf-8")
        if not raw_text.strip():
            raise json.JSONDecodeError("empty file", raw_text, 0)
        data = json.loads(raw_text)
        if validator is not None:
            validated = validator(data)
            if validated is not None:
                return validated
        return data  # type: ignore[return-value]
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
        logger.warning("Corrupt JSON at %s: %s — attempting recovery", path, exc)
        backup_dir = path.parent / "backups"
        if backup_dir.is_dir():
            backups = sorted(
                backup_dir.glob(f"{path.stem}_*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            for backup in backups[:5]:
                try:
                    data = json.loads(backup.read_text(encoding="utf-8"))
                    if validator is not None:
                        validated = validator(data)
                        if validated is None:
                            continue
                        data = validated
                    atomic_write_json(path, data)
                    logger.info("Recovered %s from backup %s", path.name, backup.name)
                    return data  # type: ignore[return-value]
                except (OSError, json.JSONDecodeError, ValueError, TypeError):
                    continue
        if path.is_file():
            corrupt = path.with_suffix(path.suffix + ".corrupt")
            try:
                shutil.move(path, corrupt)
            except OSError:
                pass
        return default
