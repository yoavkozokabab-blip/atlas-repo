# Phase 167 — Break-Even Analysis

Formula: `scan_time / (claude_avg_question_time - atlas_cached_avg_question_time)`

| Repo | Scan (s) | Claude avg/Q (s) | Atlas cached avg/Q (s) | Break-even Q | Threshold | Meets? |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| FastAPI | 2.58 | 24.0 | 4.1 | 0.1 | 5 | YES |
| Django | 17.52 | 34.0 | 4.2 | 0.6 | 5 | YES |
| VS Code | 26.95 | 54.0 | 4.1 | 0.5 | 10 | YES |
| Home Assistant | 334.05 | 94.0 | 4.9 | 3.8 | 30 | YES |