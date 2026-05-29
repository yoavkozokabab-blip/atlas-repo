"""Thread-safe, size-bounded JSONL writer with numbered rotation.

Rotation scheme (e.g. max_bytes=10 MB, backup_count=3):
    command_history.jsonl        — active log
    command_history.jsonl.1      — previous
    command_history.jsonl.2      — older
    command_history.jsonl.3      — oldest kept; .4 would be deleted

All methods are thread-safe via an internal Lock.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path


class RotatingJSONLWriter:
    """Append JSONL records to a file; rotate when the file exceeds max_bytes."""

    def __init__(
        self,
        path: Path,
        *,
        max_bytes: int = 10_000_000,
        backup_count: int = 3,
    ) -> None:
        self._path = Path(path)
        self._max_bytes = max(1024, int(max_bytes))
        self._backup_count = max(1, int(backup_count))
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write(self, record: dict) -> None:
        """Serialise *record* as a JSON line and append."""
        line = json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
        self._write_raw(line)

    def write_line(self, line: str) -> None:
        """Append a pre-formatted line (caller is responsible for JSON encoding)."""
        if not line.endswith("\n"):
            line += "\n"
        self._write_raw(line)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _write_raw(self, line: str) -> None:
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            try:
                if self._path.is_file() and self._path.stat().st_size >= self._max_bytes:
                    self._rotate()
            except OSError:
                pass  # size check failed; just append
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(line)

    def _rotate(self) -> None:
        """Shift .N-1 → .N (oldest first), then move current → .1."""
        path = self._path
        # Shift existing rotations away from .1
        for i in range(self._backup_count - 1, 0, -1):
            src = Path(f"{path}.{i}")
            dst = Path(f"{path}.{i + 1}")
            if src.is_file():
                try:
                    src.replace(dst)
                except OSError:
                    pass
        # Move current active file → .1
        one = Path(f"{path}.1")
        try:
            path.replace(one)
        except OSError:
            pass
        # Delete any overflow beyond backup_count
        overflow = Path(f"{path}.{self._backup_count + 1}")
        if overflow.is_file():
            try:
                overflow.unlink(missing_ok=True)
            except OSError:
                pass
