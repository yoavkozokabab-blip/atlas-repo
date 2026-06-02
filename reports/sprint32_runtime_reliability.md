# Sprint 3.2 Runtime Reliability Report

Date: 2026-05-29

Scope: remaining fixes only for B02, B04, and B07. No architecture redesign.

## Fixes

| ID | Issue | Result |
| --- | --- | --- |
| B02 | Watchdog not guaranteed in CLI/voice startup | `core.runtime_bootstrap.ensure_jarvis_runtime_bootstrapped()` now starts the process watchdog once. `JarvisApp` startup inherits this path, `main.py --safe-mode` opts out, and tray mode reattaches to the same watchdog. |
| B04 | Config validation needs structured severity/degraded runtime | Existing `StartupValidationIssue`/`ValidationSeverity` path now has coverage for an unwritable `DATA_DIR` style failure marking runtime degraded without hard exit. |
| B07 | Startup dependency validation coverage | Existing Playwright, Tesseract, and Win32 checks now have explicit startup-validation coverage; missing optional deps are warnings that degrade runtime, not fatal exits. |

## Verification-Only Stabilization

The requested verification bundle exposed two non-B02/B04/B07 blockers:

- Screenshot count pruning stopped after cleanup errors on Windows. The pruning path now attempts each old screenshot independently via `remove_file_best_effort()`.
- `test_health_monitor_storage_checks_return_items` used `tempfile.TemporaryDirectory()` in the system temp area, which this sandbox could not clean up. The test now uses pytest `tmp_path`.

## Files Changed

- `core/app.py`
- `core/runtime_bootstrap.py`
- `core/test_runtime.py`
- `main.py`
- `vision/screen_capture.py`
- `tests/test_sprint2.py`
- `tests/test_sprint3_agents.py`
- `tests/test_sprint32_runtime_reliability.py`
- `reports/sprint32_runtime_reliability.md`

## Test Results

```text
py -3 -m pytest tests\test_sprint32_runtime_reliability.py -q
11 passed, 1 warning

py -3 -m pytest tests\test_sprint2.py tests\test_sprint3_agents.py tests\test_runtime_stability_phase41_5.py -q
62 passed, 1 warning

py -3 scripts\smoke_phase70_agent_architecture.py
SMOKE PASS phase70_agent_architecture

py -3 scripts\smoke_phase65_product_hardening.py
SMOKE PASS phase65_product_hardening
```

Warnings observed:

- Pytest cache writes are denied in `.pytest_cache` by the sandbox.
- Smoke Phase 70 reports session-state write permission warnings but passes.
- Smoke Phase 65 reports BitBlt and Playwright subprocess permission warnings in this sandbox but passes.

## Remaining Blockers

No remaining B02/B04/B07 blocker found after targeted verification.
