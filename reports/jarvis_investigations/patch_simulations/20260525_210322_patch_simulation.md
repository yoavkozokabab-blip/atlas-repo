# Patch Simulation Report
Generated: 2026-05-25T21:03:22.423496+00:00
## Verified Root Cause
LIVE selected an incomplete bar while BACKTEST selected the prior completed bar.
Evidence: replay diff before simulation includes incomplete candle/index mismatch.
## Candidate Patches
Patch candidates for verified top hypothesis (preview only).
Candidate A: Force live replay/signal path to use last completed bar only
  affected files: C:\FINAL_ALGO_TRADER\services\live_paper_engine.py, C:\FINAL_ALGO_TRADER\services\live_dual_paper_cycle.py, C:\FINAL_ALGO_TRADER\algo_scanner\backtest\fib_quality.py, C:\FINAL_ALGO_TRADER\algo_scanner\strategy\real_algo.py
  expected effect: Live selected bar should align with backtest completed historical bar before signal detection.
  risk: MEDIUM - changes live signal timing; may skip signals that previously used incomplete bars.
  minimal diff preview:
```diff
--- a/services/live_paper_engine.py
+++ b/services/live_paper_engine.py
@@
-candidate_bar = bars.iloc[-1]
+candidate_bar = last_completed_bar(bars)
+decision.selected_bar_complete = True
```
  rollback plan: Restore prior bar selection expression in live signal path.
  verification commands:
    - py -3 -m py_compile services/live_paper_engine.py
    - py -3 -m pytest tests/test_bar_alignment.py -q
    - replay live vs backtest AAPL

Candidate B: Normalize live/backtest bar index alignment before signal detection
  affected files: C:\FINAL_ALGO_TRADER\services\live_paper_engine.py, C:\FINAL_ALGO_TRADER\services\live_dual_paper_cycle.py, C:\FINAL_ALGO_TRADER\algo_scanner\backtest\fib_quality.py, C:\FINAL_ALGO_TRADER\algo_scanner\strategy\real_algo.py
  expected effect: Both modes compute equivalent signal bar index from completed candle timestamps.
  risk: MEDIUM - requires careful timestamp/index handling across data providers.
  minimal diff preview:
```diff
--- a/algo_scanner/strategy/real_algo.py
+++ b/algo_scanner/strategy/real_algo.py
@@
+aligned_bar = align_signal_bar(mode, bars, require_complete=True)
+candidate_bar = aligned_bar
```
  rollback plan: Remove alignment helper call and revert to previous mode-specific bar selection.
  verification commands:
    - py -3 -m py_compile algo_scanner/strategy/real_algo.py
    - py -3 -m pytest tests/test_live_backtest_alignment.py -q

Candidate C: Reject incomplete candidate bars with explicit reason
  affected files: C:\FINAL_ALGO_TRADER\services\live_paper_engine.py, C:\FINAL_ALGO_TRADER\services\live_dual_paper_cycle.py, C:\FINAL_ALGO_TRADER\algo_scanner\backtest\fib_quality.py
  expected effect: No signal/entry can proceed from incomplete bars; reports expose incomplete_bar as rejection reason.
  risk: LOW - safest guard; may reduce live signals but avoids incomplete candle bias.
  minimal diff preview:
```diff
--- a/services/live_paper_engine.py
+++ b/services/live_paper_engine.py
@@
+if not candidate_bar.complete:
+    return reject_signal(reason="incomplete_bar")
```
  rollback plan: Remove incomplete_bar guard.
  verification commands:
    - py -3 -m py_compile services/live_paper_engine.py
    - py -3 -m pytest tests/test_incomplete_bar_guard.py -q
    - replay symbol AAPL

Candidate D: Add selected-bar diagnostics to live reports
  affected files: C:\FINAL_ALGO_TRADER\services\live_paper_engine.py, C:\FINAL_ALGO_TRADER\services\live_dual_paper_cycle.py, C:\FINAL_ALGO_TRADER\algo_scanner\backtest\fib_quality.py, C:\FINAL_ALGO_TRADER\algo_scanner\strategy\real_algo.py, C:\FINAL_ALGO_TRADER\run_live_paper_monitor.py, C:\FINAL_ALGO_TRADER\reports\live_paper\dual
  expected effect: Reports include selected_bar_index/timestamp/complete/close and optional backtest equivalent index.
  risk: LOW - reporting-only; does not alter trading behavior.
  minimal diff preview:
```diff
--- a/services/live_dual_paper_cycle.py
+++ b/services/live_dual_paper_cycle.py
@@
+execution_decision_summary["selected_bar_index"] = candidate_bar.index
+execution_decision_summary["selected_bar_timestamp"] = candidate_bar.timestamp
+execution_decision_summary["selected_bar_complete"] = candidate_bar.complete
+execution_decision_summary["selected_bar_close"] = candidate_bar.close
```
  rollback plan: Remove selected_bar_* diagnostic fields from report writer.
  verification commands:
    - py -3 -m py_compile services/live_dual_paper_cycle.py
    - inspect latest live report

## Selected Candidate
C: Reject incomplete candidate bars with explicit reason
## Before Replay
{
  "symbol": "AAPL",
  "status": "different",
  "first_divergence": "index alignment mismatch live=2 backtest=1",
  "live_bar": {
    "index": 2,
    "timestamp": "2026-04-18T16:47:37",
    "open": 136.8,
    "high": 137.8,
    "low": 136.4,
    "close": 137.0,
    "volume": 1002.0,
    "complete": false
  },
  "backtest_bar": {
    "index": 1,
    "timestamp": "2026-04-18T16:47:37",
    "open": 136.3,
    "high": 137.3,
    "low": 135.9,
    "close": 136.5,
    "volume": 1001.0,
    "complete": true
  },
  "divergence_reasons": [
    "index alignment mismatch live=2 backtest=1",
    "incomplete candle usage in live replay",
    "price mismatch live_close=137.0 backtest_close=136.5"
  ],
  "evidence_paths": [
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\scheduled_logs\\live_weekly_20260523_162845.log",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\logs\\live_monitor.log",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\live_summary_latest.json",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\live_run_history.csv",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\execution_decision_summary.json",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\state\\sent_alerts.json",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\state\\processed_signals.json",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\state\\open_positions.json",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\execution_order_events.csv",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\weekly\\paper_live_log_weekly.txt",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\daily\\paper_live_log_daily.txt",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\combined\\paper_live_log_combined.txt",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\combined\\paper_positions_combined.json",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\weekly\\paper_positions_weekly.json",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\daily\\paper_positions_daily.json",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\combined\\paper_positions.json",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\state\\paper_safety_state.json",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\state\\paper_portfolio_state.json",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\review_summary.csv",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\review_summary.txt"
  ],
  "confidence": 0.88
}
## After Simulated Replay
{
  "symbol": "AAPL",
  "status": "same",
  "first_divergence": "no divergence detected",
  "live_bar": {
    "index": 1,
    "timestamp": "2026-04-18T16:47:37",
    "open": 136.3,
    "high": 137.3,
    "low": 135.9,
    "close": 136.5,
    "volume": 1001.0,
    "complete": true
  },
  "backtest_bar": {
    "index": 1,
    "timestamp": "2026-04-18T16:47:37",
    "open": 136.3,
    "high": 137.3,
    "low": 135.9,
    "close": 136.5,
    "volume": 1001.0,
    "complete": true
  },
  "divergence_reasons": [],
  "evidence_paths": [
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\scheduled_logs\\live_weekly_20260523_162845.log",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\logs\\live_monitor.log",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\live_summary_latest.json",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\live_run_history.csv",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\execution_decision_summary.json",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\state\\sent_alerts.json",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\state\\processed_signals.json",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\state\\open_positions.json",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\execution_order_events.csv",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\weekly\\paper_live_log_weekly.txt",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\daily\\paper_live_log_daily.txt",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\combined\\paper_live_log_combined.txt",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\combined\\paper_positions_combined.json",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\weekly\\paper_positions_weekly.json",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\daily\\paper_positions_daily.json",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\combined\\paper_positions.json",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\state\\paper_safety_state.json",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\state\\paper_portfolio_state.json",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\review_summary.csv",
    "C:\\FINAL_ALGO_TRADER\\reports\\live_paper\\dual\\review_summary.txt"
  ],
  "confidence": 0.96
}
## Impact Estimate
Patch impact estimate
  affected symbols: A, AA, AAL, AAON, AAP, AAPL, ABBV, ABCB, ABM, ABNB, ABT, ACAD, ACGL, ACHC, ACI, ACIW, ACLS, ACM, ACMR, ACN
  affected dates: 2026-04-17, 2026-04-18, 2026-04-19, 2026-04-20, 2026-04-21, 2026-04-23, 2026-04-24, 2026-04-25, 2026-04-26, 2026-04-27
  affected signals count: 352
  likely skipped trades: 124
  likely false trades: unknown
  unknowns: exact fill outcomes and future signals
  confidence: MEDIUM
  evidence:
    - C:\FINAL_ALGO_TRADER\reports\live_paper\dual\live_summary_latest.json
    - C:\FINAL_ALGO_TRADER\reports\live_paper\dual\live_run_history.csv
    - C:\FINAL_ALGO_TRADER\reports\live_paper\dual\execution_decision_summary.json
    - C:\FINAL_ALGO_TRADER\reports\live_paper\dual\state\processed_signals.json
    - C:\FINAL_ALGO_TRADER\reports\live_paper\dual\state\open_positions.json
    - C:\FINAL_ALGO_TRADER\reports\live_paper\dual\execution_order_events.csv
    - C:\FINAL_ALGO_TRADER\reports\live_paper\dual\combined\paper_live_log_combined.txt
    - C:\FINAL_ALGO_TRADER\reports\live_paper\dual\combined\paper_positions_combined.json
    - C:\FINAL_ALGO_TRADER\reports\live_paper\dual\daily\paper_positions_daily.json
    - C:\FINAL_ALGO_TRADER\reports\live_paper\dual\state\paper_safety_state.json
    - C:\FINAL_ALGO_TRADER\reports\live_paper\dual\review_summary.csv
    - C:\FINAL_ALGO_TRADER\reports\live_paper\dual\review_summary.txt
  note: estimate only; no financial guarantee.
## Risks
LOW - safest guard; may reduce live signals but avoids incomplete candle bias.
## Verification Plan
- py -3 -m py_compile services/live_paper_engine.py
- py -3 -m pytest tests/test_incomplete_bar_guard.py -q
- replay symbol AAPL
## Approval Status
pending_patch_simulation exists; patch apply disabled for Phase 46.2 preview.