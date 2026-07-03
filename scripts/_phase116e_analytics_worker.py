"""Worker for phase116e_analytics_write_probe.py."""

from __future__ import annotations

import sys
import traceback

from atlas_desktop import analytics


def main() -> int:
    worker = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    for i in range(50):
        try:
            analytics.track_event("phase116e_subproc", worker=worker, i=i)
        except Exception as exc:
            print(f"FAIL worker={worker} i={i} {type(exc).__name__}: {exc}")
            traceback.print_exc()
            return 1
    print(f"ok worker={worker}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
