# Strict Real World Validation Report (Phase 66.1)

Generated: 2026-05-29 09:42:59 UTC
Scenarios per category: 50

**Primary readiness score: real_success_rate only.**
Mock fallback, simulated routing, and degraded passes do not count as real product success.

## Summary

| Category | Real % | Mock % | Degraded % | Fail % | Crash % | Avg latency | Top blocker |
|----------|--------|--------|------------|--------|---------|-------------|-------------|
| Voice Conversation | 46.0 | 0.0 | 54.0 | 0.0 | 0.0 | 6145.06 | simulated_routing_only |
| Browser Task | 100.0 | 0.0 | 0.0 | 0.0 | 0.0 | 205.75 | none |
| Desktop Operator | 100.0 | 0.0 | 0.0 | 0.0 | 0.0 | 209.92 | none |
| Memory Recall | 100.0 | 0.0 | 0.0 | 0.0 | 0.0 | 120.12 | none |
| Coding Task | 96.0 | 0.0 | 4.0 | 0.0 | 0.0 | 155.37 | patch_target_weak |
| Integrations (Email/Calendar) | 40.0 | 60.0 | 0.0 | 0.0 | 0.0 | 0.13 | none |
| Recovery After Failures | 100.0 | 0.0 | 0.0 | 0.0 | 0.0 | 740.09 | none |
| Multi-Step Task Completion | 100.0 | 0.0 | 0.0 | 0.0 | 0.0 | 376.09 | none |

## Voice Conversation

- **real_success_rate (primary):** 46.0%
- **mock_success_rate:** 0.0%
- **degraded_success_rate:** 54.0%
- **failure_rate:** 0.0%
- **crash_rate:** 0.0%
- **average_latency:** 6145.06 ms

### Top real blockers
- (10) simulated_routing_only
- (10) config_probe_only
- (7) partial_voice_pipeline

### Recommended fixes
- Run live voice hardware tests separately (10).
- Address blocker: config_probe_only (10).
- Address blocker: partial_voice_pipeline (7).

## Browser Task

- **real_success_rate (primary):** 100.0%
- **mock_success_rate:** 0.0%
- **degraded_success_rate:** 0.0%
- **failure_rate:** 0.0%
- **crash_rate:** 0.0%
- **average_latency:** 205.75 ms

### Top real blockers
- none

### Recommended fixes
- none

## Desktop Operator

- **real_success_rate (primary):** 100.0%
- **mock_success_rate:** 0.0%
- **degraded_success_rate:** 0.0%
- **failure_rate:** 0.0%
- **crash_rate:** 0.0%
- **average_latency:** 209.92 ms

### Top real blockers
- none

### Recommended fixes
- none

## Memory Recall

- **real_success_rate (primary):** 100.0%
- **mock_success_rate:** 0.0%
- **degraded_success_rate:** 0.0%
- **failure_rate:** 0.0%
- **crash_rate:** 0.0%
- **average_latency:** 120.12 ms

### Top real blockers
- none

### Recommended fixes
- none

## Coding Task

- **real_success_rate (primary):** 96.0%
- **mock_success_rate:** 0.0%
- **degraded_success_rate:** 4.0%
- **failure_rate:** 0.0%
- **crash_rate:** 0.0%
- **average_latency:** 155.37 ms

### Top real blockers
- (2) patch_target_weak

### Recommended fixes
- Address blocker: patch_target_weak (2).

## Integrations (Email/Calendar)

- **real_success_rate (primary):** 40.0%
- **mock_success_rate:** 60.0%
- **degraded_success_rate:** 0.0%
- **failure_rate:** 0.0%
- **crash_rate:** 0.0%
- **average_latency:** 0.13 ms

### Top real blockers
- none

### Recommended fixes
- none

## Recovery After Failures

- **real_success_rate (primary):** 100.0%
- **mock_success_rate:** 0.0%
- **degraded_success_rate:** 0.0%
- **failure_rate:** 0.0%
- **crash_rate:** 0.0%
- **average_latency:** 740.09 ms

### Top real blockers
- none

### Recommended fixes
- none

## Multi-Step Task Completion

- **real_success_rate (primary):** 100.0%
- **mock_success_rate:** 0.0%
- **degraded_success_rate:** 0.0%
- **failure_rate:** 0.0%
- **crash_rate:** 0.0%
- **average_latency:** 376.09 ms

### Top real blockers
- none

### Recommended fixes
- none
