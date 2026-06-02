# Phase 130 — Repository Understanding Validation

Generated: 2026-06-03 00:55:29

## Executive summary

- **Scenarios run:** 50
- **Executed successfully:** 50
- **Mean Atlas score:** 63.8/100

## Category breakdown

| Category | Count | Mean Atlas score | File precision | File recall |
|----------|-------|------------------|----------------|-------------|
| feature_addition | 20 | 68.4 | 0.126 | 1.0 |
| bug_investigation | 20 | 63.1 | 0.106 | 0.9 |
| impact_analysis | 10 | 55.8 | 1.0 | 0.733 |

## Score dimensions (averages over successful runs)

- **Repository Understanding:** 65.4/100
- **Knowledge Understanding:** 84.0/100
- **Evidence Quality:** 56.3/100
- **Investigation Quality:** 83.7/100
- **Impact Analysis Quality:** 65.2/100

## Sample scenario results

### feat_001_ema — `atlas_reference`

**Prompt:** add EMA indicator with configurable period

**Atlas score:** 85.7/100
**File precision / recall:** 0.21 / 1.00
**Insertion correct:** Yes
**Concept:** ema (expected `ema`)

### feat_002_feature_flags — `atlas_reference`

**Prompt:** add feature flags for gradual rollout

**Atlas score:** 90.4/100
**File precision / recall:** 0.08 / 1.00
**Insertion correct:** Yes
**Concept:** feature_flags (expected `feature_flags`)

### feat_003_stripe_billing — `atlas_reference`

**Prompt:** Add Stripe billing and subscriptions

**Atlas score:** 69.3/100
**File precision / recall:** 0.15 / 1.00
**Insertion correct:** No
**Concept:** stripe_billing (expected `stripe_billing`)

### feat_004_circuit_breaker — `atlas_reference`

**Prompt:** Add circuit breaker for outbound HTTP calls

**Atlas score:** 68.1/100
**File precision / recall:** 0.07 / 1.00
**Insertion correct:** No
**Concept:** circuit_breaker (expected `circuit_breaker`)

### feat_005_distributed_tracing — `atlas_reference`

**Prompt:** add distributed tracing with span propagation

**Atlas score:** 84.1/100
**File precision / recall:** 0.14 / 1.00
**Insertion correct:** Yes
**Concept:** distributed_tracing (expected `distributed_tracing`)

### feat_006_rate_limiting — `atlas_reference`

**Prompt:** add API rate limiting middleware

**Atlas score:** 60.8/100
**File precision / recall:** 0.14 / 1.00
**Insertion correct:** No
**Concept:** rate_limiting (expected `rate_limiting`)

### feat_007_jwt — `atlas_reference`

**Prompt:** configure JWT bearer authentication

**Atlas score:** 45.8/100
**File precision / recall:** 0.12 / 1.00
**Insertion correct:** No
**Concept:** authentication (expected `jwt`)

### feat_008_oauth2 — `atlas_reference`

**Prompt:** Add OAuth2 authorization code flow with PKCE

**Atlas score:** 52.5/100
**File precision / recall:** 0.14 / 1.00
**Insertion correct:** No
**Concept:** oauth2 (expected `oauth2`)

## Repository evidence audit

- `feat_003_stripe_billing` — **incorrect_insertion_point**: got `billing/stripe_webhooks.py` expected one of ['billing/stripe_billing.py']
- `feat_004_circuit_breaker` — **incorrect_insertion_point**: got `cache/redis_client.py` expected one of ['services/http_client.py']
- `feat_006_rate_limiting` — **incorrect_insertion_point**: got `api/routes.py` expected one of ['api/rate_limit.py']
- `feat_007_jwt` — **incorrect_insertion_point**: got `auth/login.py` expected one of ['auth/middleware.py']
- `feat_008_oauth2` — **incorrect_insertion_point**: got `api/routes.py` expected one of ['auth/login.py']
- `feat_011_db_migration` — **incorrect_insertion_point**: got `db/postgres.py` expected one of ['db/migrations/001_initial.py']
- `feat_013_structured_logging` — **incorrect_insertion_point**: got `auth/login.py` expected one of ['middleware/request_logging.py']
- `feat_018_auth_sessions` — **incorrect_insertion_point**: got `auth/login.py` expected one of ['auth/middleware.py']
- `feat_019_paper_trading` — **incorrect_insertion_point**: got `registry/signal_registry.py` expected one of ['trading/paper_trading.py']
- `feat_020_slippage_model` — **incorrect_insertion_point**: got `registry/signal_registry.py` expected one of ['trading/backtest_config.py']
- `inv_001_backtest_paper` — **incorrect_insertion_point**: got `trading/paper_trading.py` expected one of ['trading/backtest_config.py']
- `inv_002_duplicate_orders` — **incorrect_insertion_point**: got `registry/signal_registry.py` expected one of ['trading/order_service.py']
- `inv_004_stale_cache` — **incorrect_insertion_point**: got `cache/redis_client.py` expected one of ['cache/cache_layer.py']
- `inv_005_auth_bypass` — **incorrect_insertion_point**: got `auth/login.py` expected one of ['auth/middleware.py']
- `inv_006_slippage_mismatch` — **incorrect_insertion_point**: got `trading/paper_trading.py` expected one of ['trading/backtest_config.py']

## Failure analysis (sample)

### feat_003_stripe_billing
- **Why:** Incorrect insertion point
- **Evidence used:** hand
- **Expected:** n/a
- **Missing:** n/a

### feat_004_circuit_breaker
- **Why:** Incorrect insertion point
- **Evidence used:** cach
- **Expected:** http
- **Missing:** Aioh

### feat_006_rate_limiting
- **Why:** Incorrect insertion point
- **Evidence used:** rate
- **Expected:** n/a
- **Missing:** Limi

### feat_007_jwt
- **Why:** Incorrect insertion point
- **Evidence used:** auth
- **Expected:** n/a
- **Missing:** Pass

### feat_007_jwt
- **Why:** Wrong concept identified
- **Evidence used:** auth
- **Expected:** jwt
- **Missing:** jwt

### feat_008_oauth2
- **Why:** Incorrect insertion point
- **Evidence used:** n/a
- **Expected:** n/a
- **Missing:** Auth

### feat_011_db_migration
- **Why:** Incorrect insertion point
- **Evidence used:** sqla
- **Expected:** n/a
- **Missing:** Alem

### feat_013_structured_logging
- **Why:** Incorrect insertion point
- **Evidence used:** logi
- **Expected:** requ
- **Missing:** Corr

### feat_016_signal_pipeline
- **Why:** Wrong concept identified
- **Evidence used:** ci_c
- **Expected:** ema
- **Missing:** ema

### feat_018_auth_sessions
- **Why:** Incorrect insertion point
- **Evidence used:** auth
- **Expected:** n/a
- **Missing:** Pass

### feat_019_paper_trading
- **Why:** Incorrect insertion point
- **Evidence used:** SMAI
- **Expected:** n/a
- **Missing:** Ema,

### feat_020_slippage_model
- **Why:** Incorrect insertion point
- **Evidence used:** SMAI
- **Expected:** slip
- **Missing:** Ema,

## Competitive evaluation (manual)

Use `benchmarks/competitive/manual_comparison_template.md` to score Atlas vs Claude Code vs Cursor.
No API integration — paste assistant outputs and score file recall, insertion, and evidence quality manually.

## Driving future phases

Prioritize fixes for categories with lowest mean Atlas score and repeated failure reasons above.
