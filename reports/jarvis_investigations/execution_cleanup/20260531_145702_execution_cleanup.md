# Execution Cleanup Patch Preview
Generated: 2026-05-31T14:57:02.755717+00:00
## Problem
- ExecutionDisabledAdapter + stop_loss_hit close rejections leave stale open_positions.
- Engine open count exceeds adapter positions; risk cap blocks new signals.
## State
- adapter: ExecutionDisabledAdapter health_ok=False
- kill_switch_enabled: False
- alpaca keys missing: True
- engine_open_positions: 1
- adapter_positions: 0
- primary blocker: stale open positions after stop_loss_hit
## Risk Simulation
- risk before: 0.0125
- risk after (simulated P1): 0.1
- open_risk_fraction_daily before/after: 0.1125 -> 0.1
- eligible signals before/after: 4 -> 4
## Stale Positions
- AAPL unknown reason=stop_loss_hit_adapter_disabled stop_hit=True evidence=C:\J.A.R.V.I.S\local_jarvis\tests_tmp\pytest_temp\pytest-of-babi2\pytest-346\test_apply_requires_validation0\trading\reports\live_paper\dual\state\open_positions.json
## Patch Preview
```diff
--- a/services/live_paper_engine.py
+++ b/services/live_paper_engine.py
@@
+if paper_mode and adapter_is_disabled and position.forced_exit_due:
+    record_event("close_order_paper_only", reason="paper_local_close_after_adapter_disabled")
+    close_local_open_position(position, broker_close_sent=False)
+    emit_warning("Broker close NOT sent; adapter disabled/missing keys")
+    return
```
## Tests

- ExecutionDisabledAdapter + stop hit closes local paper position only
- does not mark broker execution accepted
- risk fraction drops after local close
- telemetry primary blocker prefers exposure_limit_reached over scan noise
- execution summary includes kill switch + adapter status
- no live order call
## Rollback
Remove paper-local close branch; restore prior open_positions persistence behavior.
## Safety
- Preview only; no production apply without explicit approval.