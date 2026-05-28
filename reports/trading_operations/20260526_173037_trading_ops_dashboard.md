Trading operations dashboard:
  generated: 2026-05-26T17:30:37.334178+00:00

## Execution blockers
Execution blockers:
  signals blocked: 5
  top blocker: execution disabled adapter
- [critical] execution disabled adapter count=29
  evidence path: C:\J.A.R.V.I.S\local_jarvis\reports\jarvis_investigations\execution_cleanup\20260526_170817_execution_cleanup.md
  snippet: - ExecutionDisabledAdapter + stop_loss_hit close rejections leave stale open_positions.
- [high] exposure limit count=26
  evidence path: C:\J.A.R.V.I.S\local_jarvis\reports\jarvis_investigations\execution_cleanup\20260526_170817_execution_cleanup.md
  snippet: - telemetry primary blocker prefers exposure_limit_reached over s

## Stale positions
Stale open positions (read-only scan):
  engine_open_position_count=9
  adapter_position_count=4
  adapter=ExecutionDisabledAdapter disabled=True
- POS1 entry=unknown reason=engine_open_without_adapter_positions
  stop_hit=True close_rejected=True
  evidence: combined evidence
  snippet: {}
# Execution Investigation Report
Generated: 2026-05-26T17:30:37.524146+00:00
## Summary
- Files scanned: 47


## Runtime health
Runtime health: DEGRADED
  checked: 2026-05-26T17:30:37.660659+00:00
  [OK] runtime: running=True
  [OK] overlay: phase=OverlayPhase.IDLE
  [OK] wake_listener: alive=False
  [OK] operator_console: queue=0
  [OK] dashboard: status=healthy detail=HTTP 200
  [OK] tts_worker: speaking=None
  [OK] runtime_monitor: issues=0

## Execution risk
Current execution risk:
  open risk fraction daily: 0.1125
  cap: 0.12
  kill switch: False
  adapter health: False
  execution enabled: False
  primary blocker: stale open positions after stop loss hit

## Live engine
Live engine status:
  engine file: present
  cycle file: present
  open positions: 0
Execution adapter inspection:
  adapter mode: ExecutionDisabledAdapter
  dry run status: unknown
  execution disabled: yes
  attempts: 0
  accepted: 0
Adapter evidence:
  - C:\J.A.R.V.I.S\local_jarvis\reports\jarvis_investigations\execution_cleanup\20260526_170817_execution_cleanup.md: - ExecutionDisabledAdapter + stop_loss_hit close rejections leave stale open_positions.
  - C:\J.A.R.V.I.S\local_jarvis\reports\

## Recent investigations
Recent investigations:
  - Phase 45 status
  Mode: Elite Code + Trading Investigation Engine
  Runtime: console + HUD first; TTS optional/deferred
  - Operational suggestions (explainable, not auto-applied):
  - dashboard degraded [low]
      evidence: <urlopen error [Wi
  - Resume hint: re-run related command for 'Ranked execution block reasons:
1. overlap block severity=medium count=25 evide
  -

## Patch workflow
Patch workflow status:
  safety validated: yes
  patch approved: yes
  patch applied: yes
  replay validated: PASSED (risk 0.1125->0.0; eligible 4->5; stale cleanup=0 symbols)
  rollback available: False
  backup id: 20260526_121610_95ec3bbe
  latest audit report: C:\J.A.R.V.I.S\local_jarvis\reports\jarvis_investigations\patch_apply\20260526_121628_rollback.md