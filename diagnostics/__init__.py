"""Read-only cross-source diagnostics."""

from diagnostics.engine import (
    analyze_current_screen,
    diagnose_dashboard,
    diagnose_recent_errors,
    diagnose_trading_loop,
    explain_last_failure,
    run_diagnostics,
    suggest_next_steps,
)

__all__ = [
    "run_diagnostics",
    "diagnose_dashboard",
    "diagnose_trading_loop",
    "diagnose_recent_errors",
    "analyze_current_screen",
    "explain_last_failure",
    "suggest_next_steps",
]
