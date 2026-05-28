"""Small, bounded cleanup helpers for temporary local files."""

from __future__ import annotations

import gc
import time
from pathlib import Path


def remove_file_best_effort(
    path: Path | str | None,
    *,
    attempts: int = 5,
    delay_seconds: float = 0.025,
) -> bool:
    """
    Remove one file and report whether it is actually gone.

    Windows can briefly deny deletion while antivirus, image/audio libraries, or
    shell metadata readers still hold a handle. This helper is intentionally
    bounded and cleanup-only: it never escalates, never removes directories, and
    never claims success while the file remains visible.
    """
    if path is None:
        return True

    target = Path(path)
    tries = max(1, attempts)
    for attempt in range(tries):
        try:
            if not target.exists():
                return True
            if not target.is_file():
                return False
            target.unlink()
        except FileNotFoundError:
            return True
        except OSError:
            pass

        try:
            if not target.exists():
                return True
        except OSError:
            return False

        if attempt < tries - 1:
            gc.collect()
            time.sleep(delay_seconds * (attempt + 1))

    try:
        return not target.exists()
    except OSError:
        return False
