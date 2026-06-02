"""Phase 116E probe — concurrent analytics writes from separate processes (investigation only)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "scripts" / "_phase116e_analytics_worker.py"


def main() -> int:
    procs = [
        subprocess.Popen([sys.executable, str(WORKER), str(i)], cwd=str(ROOT))
        for i in range(4)
    ]
    codes = [p.wait() for p in procs]
    print("exit codes:", codes)
    return 0 if all(c == 0 for c in codes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
