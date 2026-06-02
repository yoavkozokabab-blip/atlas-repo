# Execution Investigation Report
Generated: 2026-05-29T14:06:35.110996+00:00
## Summary
- Files scanned: 175
- Signals generated: 4
- Signals eligible: 4
- Signals blocked: 4
- Execution attempts: 0
- Execution accepted: 0
- Adapter mode: AlpacaExecutionAdapter
- Dry run: true
- Execution disabled: yes
- Top blocker: overlap block
## Block Reasons
- [medium] overlap block count=25 evidence=C:\FINAL_ALGO_TRADER\reports\live_paper\live_summary_latest.json
- [high] max positions reached count=15 evidence=C:\FINAL_ALGO_TRADER\reports\live_paper_trials\alpaca_paper_30d\latest_snapshot.json
- [high] not relevant to last bar count=15 evidence=C:\FINAL_ALGO_TRADER\reports\live_paper_trials\alpaca_paper_clean_100k_20260516\live_output\execution_decision_summary.json
- [medium] already in position count=10 evidence=C:\FINAL_ALGO_TRADER\reports\live_paper_trials\alpaca_paper_30d\cumulative_summary.json
- [medium] market closed count=10 evidence=C:\FINAL_ALGO_TRADER\reports\live_paper_trials\alpaca_paper_clean_100k_20260516\live_output\live_summary_latest.json
- [medium] delayed entry failure count=7 evidence=C:\FINAL_ALGO_TRADER\reports\live_paper\live_summary_latest.json
- [medium] duplicate block count=5 evidence=C:\FINAL_ALGO_TRADER\reports\live_paper_trials\alpaca_paper_clean_100k_20260516\live_output\live_summary_latest.json
- [high] dry run mode count=3 evidence=C:\FINAL_ALGO_TRADER\reports\live_paper_trials\alpaca_paper_30d\daily_snapshots\2026-04-25.json
- [critical] execution disabled adapter count=2 evidence=C:\FINAL_ALGO_TRADER\reports\live_paper\dual\execution_order_events.csv
- [high] exposure limit count=2 evidence=C:\FINAL_ALGO_TRADER\reports\live_paper\dual\execution_order_events.csv
- [medium] processed count=1 evidence=C:\FINAL_ALGO_TRADER\reports\live_paper\live_summary_latest.json
## Evidence Paths
- C:\FINAL_ALGO_TRADER\reports\live_paper_trials\alpaca_paper_clean_100k_20260516\live_output\execution_order_events.csv
- C:\FINAL_ALGO_TRADER\reports\live_paper\dual\execution_order_events.csv
- C:\FINAL_ALGO_TRADER\reports\live_paper_trials\alpaca_paper_clean_100k_20260516\live_output\execution_decision_summary.json
- C:\FINAL_ALGO_TRADER\reports\live_paper\dual\execution_decision_summary.json
- C:\FINAL_ALGO_TRADER\reports\live_paper\dual\live_signals.csv
- C:\FINAL_ALGO_TRADER\reports\live_paper_trials\alpaca_paper_clean_100k_20260516\live_output\live_summary_latest.json
- C:\FINAL_ALGO_TRADER\reports\live_paper\dual\live_summary_latest.json
- C:\FINAL_ALGO_TRADER\reports\live_paper\live_summary_latest.json
- C:\FINAL_ALGO_TRADER\reports\live_paper\daily\live_summary_latest.json
- C:\FINAL_ALGO_TRADER\reports\live_paper\dual\state\jarvis_execution_telemetry.json
- C:\FINAL_ALGO_TRADER\reports\live_paper_trials\alpaca_paper_30d\audit\ranking_execution_audit_20260516T200255Z.md
- C:\FINAL_ALGO_TRADER\reports\live_paper_trials\alpaca_paper_30d\audit\ranking_execution_audit_20260516T200255Z.csv
- C:\FINAL_ALGO_TRADER\reports\live_paper_trials\alpaca_paper_30d\audit\ranking_execution_audit_20260516T200153Z.md
- C:\FINAL_ALGO_TRADER\reports\live_paper_trials\alpaca_paper_30d\audit\ranking_execution_audit_20260516T200153Z.csv
- C:\FINAL_ALGO_TRADER\reports\live_paper_trials\alpaca_paper_30d\audit\ranking_execution_audit_20260516T200110Z.md
- C:\FINAL_ALGO_TRADER\reports\live_paper_trials\alpaca_paper_30d\audit\ranking_execution_audit_20260516T200110Z.csv
- C:\FINAL_ALGO_TRADER\reports\live_paper_trials\alpaca_paper_30d\audit\ranking_execution_audit_20260516T200011Z.md
- C:\FINAL_ALGO_TRADER\reports\live_paper_trials\alpaca_paper_30d\audit\ranking_execution_audit_20260516T200011Z.csv
- C:\FINAL_ALGO_TRADER\reports\live_paper_trials\alpaca_paper_clean_100k_20260516\live_output\state\processed_signals.json
- C:\FINAL_ALGO_TRADER\reports\live_paper\dual\state\processed_signals.json
- C:\FINAL_ALGO_TRADER\reports\live_paper\state\processed_signals.json
- C:\FINAL_ALGO_TRADER\reports\live_paper\daily\state\processed_signals.json
- C:\FINAL_ALGO_TRADER\reports\live_paper_trials\alpaca_paper_30d\cumulative_summary.json
- C:\FINAL_ALGO_TRADER\reports\live_paper_trials\alpaca_paper_30d\latest_snapshot.json
- C:\FINAL_ALGO_TRADER\reports\live_paper_trials\alpaca_paper_30d\trial_manifest.json
## Recommended Verification
- Confirm execution adapter is enabled for paper/live mode (not ExecutionDisabledAdapter).
- Verify dry_run flag matches intended environment.
- Check signal_detection_mode vs eligible last-bar signals.
- Inspect entry_blocks and reason_if_no_attempt in execution_decision_summary.json.
- Compare live_signals.csv rows to execution_order_events.csv attempt events.