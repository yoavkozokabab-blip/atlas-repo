Trading operations dashboard:
  generated: 2026-05-26T17:46:24.601859+00:00

## Execution blockers
Execution blockers:
  signals blocked: 4
  top blocker: overlap block
- [medium] overlap block count=24
  evidence path: C:\FINAL_ALGO_TRADER\reports\live_paper\live_summary_latest.json
  snippet: "signal_flow_debug_text": "\nDEBUG SIGNAL FLOW:\n  total_symbols=22\n  pre_setups=10248\n  passed_filters=708\n  failed_entry=518\n  reject_reasons={'RR_TOO_LOW': 383, 'VOLUME_TOO_LOW': 5954, 'TREND_FILTER_FAIL': 2613, 'DEEP_RETRACE': 332, 'SETUP_EXPIRED': 60}
- [high] max positions reached count=16
  evidence path: C:\FINAL_ALGO_TRADER\reports\live_paper_trials\alpaca_paper_30d\cumulative_summary.js

## Stale positions
Stale open positions (read-only scan):
  engine_open_position_count=9
  adapter_position_count=4
  adapter=AlpacaExecutionAdapter disabled=True
- BRBR entry=2026-04-17 reason=stop_loss_hit_adapter_disabled
  stop_hit=True close_rejected=False
  evidence: C:\FINAL_ALGO_TRADER\reports\live_paper\dual\state\open_positions.json
  snippet: "symbol": "BRBR",
      "combo_label": "real_algo_config_produc

## Runtime health
Runtime health: HEALTHY
  checked: 2026-05-26T17:46:26.019385+00:00
  [OK] runtime: running=True
  [OK] overlay: phase=OverlayPhase.EXECUTING
  [OK] wake_listener: alive=True
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
  primary blocker: stale open positions after stop_loss_hit

## Live engine
Live engine status:
  engine file: present
  cycle file: present
  open positions: 0
Execution adapter inspection:
  adapter mode: AlpacaExecutionAdapter
  dry run status: true
  execution disabled: yes
  attempts: 0
  accepted: 0
Adapter evidence:
  - C:\FINAL_ALGO_TRADER\reports\live_paper_trials\alpaca_paper_clean_100k_20260516\live_output\execution_order_events.csv: timestamp,ts,event_type,adapter,symbol,side,engine,interval,position_id,qty,qty_local,qty_broker,order_type,entry_price,entry,s

## Recent investigations
Recent investigations:
  - Phase 50 — Computer Control + Context Memory
  desktop: open/focus apps, reports, screenshots (allowlisted)
  context: w
  - Phase 49 — Autonomous Operational Healing
  runtime health: healthy
  recovery attempts (1h): 0
  max recoveries/hour: 6
  - Phase 45 status
  Mode: Elite Code + Trading Investigation Engine
  Runtime: console + HUD first; TTS optional/deferred
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