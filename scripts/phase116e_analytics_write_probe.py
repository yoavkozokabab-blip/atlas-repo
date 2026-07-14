"""Phase 116E probe — concurrent analytics writes from separate processes (investigation only)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from verification_isolation import activate_isolated_atlas_data

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "scripts" / "_phase116e_analytics_worker.py"


def main() -> int:
    activate_isolated_atlas_data("phase116e-analytics-write-probe")
    procs = [
        subprocess.Popen(
            [sys.executable, str(WORKER), str(i)],
            cwd=str(ROOT),
            env=dict(os.environ),
        )
        for i in range(4)
    ]
    codes = [p.wait() for p in procs]
    print("exit codes:", codes)
    return 0 if all(c == 0 for c in codes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
