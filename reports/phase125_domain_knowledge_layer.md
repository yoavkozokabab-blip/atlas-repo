# Phase 125 — Domain Knowledge Layer

**Version:** `phase125-domain-knowledge-layer`  
**Approach:** Deterministic local registry — no external APIs, no LLM, no model training.

## Concepts added

| ID | Domain | Feature type |
|----|--------|--------------|
| `ema` | Trading | indicator |
| `rsi` | Trading | indicator |
| `atr_stop_loss` | Trading | risk |
| `authentication` | Web backend | auth |
| `stripe_billing` | Web backend | billing |
| `rate_limiting` | Web backend | infra |
| `logging` | Infra | observability |
| `retry_queue` | Infra | queue |
| `observability` | Infra | observability |
| `backtest_live_divergence` | Trading | symptom (investigate) |
| `indicator_backtest_live` | Trading | symptom (investigate) |

## Before / after — “add EMA indicator”

**Before:** Keyword path match only; no warmup/lookahead/backtest-live guidance.

**After:** Concept **EMA**, knowledge risks, implementation steps, file roles, domain-aware Claude prompt.

## Before / after — “backtest better than paper”

**Before:** Generic `paper_trading` intent.

**After:** `backtest_live_divergence` failure modes (fills, timing, slippage, fees) in checklist and prompts.

## Limitations

- Curated concepts only; no semantic search beyond aliases
- Path-based repo mapping (no AST)
- Minimal repos may have empty file roles with honest integration note

## Next concepts

MACD, migrations, feature flags, CI/CD, data pipelines.

## Tests

`test_phase125_domain_knowledge.py`
