"""Run Phase 66 validation — delegates to strict Phase 66.1 (legacy entrypoint)."""

from __future__ import annotations

from validation.run_all_strict import main as strict_main
from validation.run_all_strict import run_all_strict_validations
# Backward-compatible alias
run_all_validations = run_all_strict_validations


def main() -> str:
    return strict_main()


