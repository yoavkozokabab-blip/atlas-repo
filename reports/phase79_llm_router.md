# Phase 79 Stage 1 — Shadow LLM Tool Router

**Date:** 2026-05-29  
**Status:** Shipped (shadow only; default flags OFF)

## Summary

Adds an LLM tool router that runs **only on classifier misses** when both `LLM_TOOL_ROUTER_ENABLED` and `LLM_TOOL_ROUTER_SHADOW` are true. It retrieves candidate tools from the Phase 78 registry, asks the LLM for a structured decision, validates the response, and writes `data/llm_router_audit.jsonl`. It **never** invokes tools or changes `CommandRequest` / `CommandRouter` routing.

## Flags (defaults)

| Variable | Default | Effect |
|----------|---------|--------|
| `LLM_TOOL_ROUTER_ENABLED` | false | Master switch |
| `LLM_TOOL_ROUTER_SHADOW` | false | Log-only shadow (Stage 1) |
| `LLM_TOOL_ROUTER_READONLY_ONLY` | true | REVERSIBLE tools blocked at validation (Stage 2+) |

## Files

| File | Role |
|------|------|
| `brain/llm_tool_router.py` | `route_miss`, shadow hook, circuit breaker |
| `brain/tool_router_prompt.py` | Prompt + strict JSON parser |
| `brain/tool_router_audit.py` | `llm_router_audit.jsonl` writer |
| `brain/router.py` | `_maybe_shadow_llm_tool_route` hook after classify (no routing change) |
| `tools/flags.py` | Shadow + readonly-only flags |

## Verification

```text
py -3 -m pytest tests/test_phase79_llm_tool_router.py -q
py -3 scripts/smoke_phase79_llm_router_shadow.py
py -3 scripts/smoke_phase79_llm_router_safety.py
py -3 -m pytest tests/test_phase79_llm_tool_router.py tests/test_phase78_tool_registry.py tests/test_router.py tests/test_intent_registry_consistency.py -q
```

**Results (2026-05-29):** 9 phase79 tests passed; both smokes PASS; 45-test regression bundle PASS.

## Rollback

Set `LLM_TOOL_ROUTER_ENABLED=false` (or unset) — classifier-only behavior, zero audit/router calls.
