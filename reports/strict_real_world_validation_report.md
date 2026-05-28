# Strict Real World Validation Report (Phase 66.1)

Generated: 2026-05-28 20:58:55 UTC
Scenarios per category: 50

**Primary readiness score: real_success_rate only.**
Mock fallback, simulated routing, and degraded passes do not count as real product success.

## Summary

| Category | Real % | Mock % | Degraded % | Fail % | Crash % | Avg latency | Top blocker |
|----------|--------|--------|------------|--------|---------|-------------|-------------|
| Voice Conversation | 56.0 | 0.0 | 44.0 | 0.0 | 0.0 | 3748.21 | simulated_routing_only |
| Browser Task | 100.0 | 0.0 | 0.0 | 0.0 | 0.0 | 188.27 | none |
| Desktop Operator | 100.0 | 0.0 | 0.0 | 0.0 | 0.0 | 172.97 | none |
| Memory Recall | 100.0 | 0.0 | 0.0 | 0.0 | 0.0 | 92.77 | none |
| Coding Task | 96.0 | 0.0 | 4.0 | 0.0 | 0.0 | 119.22 | patch_target_weak |
| Integrations (Email/Calendar) | 40.0 | 60.0 | 0.0 | 0.0 | 0.0 | 0.11 | none |
| Recovery After Failures | 100.0 | 0.0 | 0.0 | 0.0 | 0.0 | 681.08 | none |
| Multi-Step Task Completion | 100.0 | 0.0 | 0.0 | 0.0 | 0.0 | 323.96 | none |

## Voice Conversation

- **real_success_rate (primary):** 56.0%
- **mock_success_rate:** 0.0%
- **degraded_success_rate:** 44.0%
- **failure_rate:** 0.0%
- **crash_rate:** 0.0%
- **average_latency:** 3748.21 ms

### Top real blockers
- (10) simulated_routing_only
- (10) config_probe_only
- (2) partial_voice_pipeline

### Recommended fixes
- Run live voice hardware tests separately (10).
- Address blocker: config_probe_only (10).
- Address blocker: partial_voice_pipeline (2).

## Browser Task

- **real_success_rate (primary):** 100.0%
- **mock_success_rate:** 0.0%
- **degraded_success_rate:** 0.0%
- **failure_rate:** 0.0%
- **crash_rate:** 0.0%
- **average_latency:** 188.27 ms

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
- **average_latency:** 172.97 ms

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
- **average_latency:** 92.77 ms

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
- **average_latency:** 119.22 ms

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
- **average_latency:** 0.11 ms

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
- **average_latency:** 681.08 ms

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
- **average_latency:** 323.96 ms

### Top real blockers
- none

### Recommended fixes
- none
