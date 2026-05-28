# Execution Cleanup Patch Preview
Generated: 2026-05-26T17:55:43.537117+00:00
## Problem
- ExecutionDisabledAdapter + stop_loss_hit close rejections leave stale open_positions.
- Engine open count exceeds adapter positions; risk cap blocks new signals.
## State
- adapter: ExecutionDisabledAdapter health_ok=False
- kill_switch_enabled: False
- alpaca keys missing: True
- engine_open_positions: 9
- adapter_positions: 4
- primary blocker: stale open positions after stop loss hit
## Risk Simulation
- risk before: 0.1125
- risk after (simulated P1): 0.0
- open_risk_fraction_daily before/after: 0.1125 -> 0.0
- eligible signals before/after: 5 -> 5
## Stale Positions
- POS1 unknown reason=engine_open_without_adapter_positions stop_hit=True evidence=combined evidence
- POS2 unknown reason=engine_open_without_adapter_positions stop_hit=True evidence=combined evidence
- POS3 unknown reason=engine_open_without_adapter_positions stop_hit=True evidence=combined evidence
- POS4 unknown reason=engine_open_without_adapter_positions stop_hit=True evidence=combined evidence
- POS5 unknown reason=engine_open_without_adapter_positions stop_hit=True evidence=combined evidence
- POS6 unknown reason=engine_open_without_adapter_positions stop_hit=True evidence=combined evidence
- POS7 unknown reason=engine_open_without_adapter_positions stop_hit=True evidence=combined evidence
- POS8 unknown reason=engine_open_without_adapter_positions stop_hit=True evidence=combined evidence
- POS9 unknown reason=engine_open_without_adapter_positions stop_hit=True evidence=combined evidence
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