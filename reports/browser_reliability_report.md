# Browser Reliability Report

- current_score: 95.0%
- target_score: 85.0%
- gap: 0.0%
- pass_rate: 100.0% (6/6)

## Acceptance Results
- [PASS] runtime_state (0.01 ms) — provider=mock
- [PASS] open_browser (877.91 ms) — REAL VISIBLE BROWSER
Browser session active.
  browser_visible: True
  url: about:blank
  tab: 1/1
- [PASS] navigation_recovery (901.08 ms) — REAL VISIBLE BROWSER
Browser session active.
  browser_visible: True
  url: https://example.com/
  tab: 1/1
- [PASS] crash_recovery (816.65 ms) — REAL VISIBLE BROWSER
Browser session recovered.
- [PASS] summarize_page (167.52 ms) — REAL VISIBLE BROWSER
Summary for about:blank
  title: n/a
  key_points: n/a
- [PASS] active_page_status (2.08 ms) — Active tab:
  index: 1/1
  title: n/a
  url: about:blank