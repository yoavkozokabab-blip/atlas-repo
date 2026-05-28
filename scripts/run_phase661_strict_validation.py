#!/usr/bin/env python3
"""Phase 66.1 — strict real-world validation runner."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from validation.run_all_strict import main, run_all_strict_validations, verify_strict_acceptance


if __name__ == "__main__":
    measurements = run_all_strict_validations()
    body = main()
    print(body[:4000])
    if len(body) > 4000:
        print("\n... (truncated; see reports/strict_real_world_validation_report.md)")
    violations = verify_strict_acceptance(measurements)
    if violations:
        print("\nACCEPTANCE VIOLATIONS:")
        for v in violations:
            print(f"  - {v}")
        sys.exit(1)
    sys.exit(0)
