"""Phase 66: run measured real-world validation (350 scenarios)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    import config as cfg

    cfg.MEMORY_ENABLED = True
    cfg.SCREEN_UNDERSTANDING_ENABLED = True
    cfg.DESKTOP_OPERATOR_ENABLED = True

    from validation.run_all import main as run_validation

    report = run_validation()
    total = report.count("| Voice Conversation |")  # sanity
    print("Phase 66 real-world validation complete.")
    print(f"Report: {ROOT / 'reports' / 'real_world_validation_report.md'}")
    print(f"Raw JSON: {ROOT / 'reports' / 'phase66_validation_raw.json'}")
    # Print measured summary lines only
    for line in report.splitlines():
        if line.startswith("| ") and "Category" not in line and "---" not in line:
            print(line)


if __name__ == "__main__":
    main()
