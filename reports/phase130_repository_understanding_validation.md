# Phase 130 — Repository Understanding Validation

Generated: 2026-06-03 10:02:21

## Executive summary

- **Scenarios run:** 50 (reference repo `atlas_reference`, optional external repos excluded)
- **Executed successfully:** 50
- **Mean Atlas score:** 86.3/100

## Category breakdown

| Category | Count | Mean Atlas score | File precision | File recall |
|----------|-------|------------------|----------------|-------------|
| feature_addition | 20 | 82.8 | 0.804 | 0.95 |
| bug_investigation | 20 | 86.0 | 0.301 | 0.975 |
| impact_analysis | 10 | 94.0 | 0.883 | 0.967 |

## Score dimensions (averages over successful runs)

- **Repository Understanding:** 85.8/100
- **Knowledge Understanding:** 94.0/100
- **Evidence Quality:** 56.0/100
- **Investigation Quality:** 96.1/100
- **Impact Analysis Quality:** 89.2/100

## Sample scenario results

### feat_001_ema — `atlas_reference`

**Prompt:** add EMA indicator with configurable period

**Atlas score:** 94.3/100
**File precision / recall:** 0.75 / 1.00
**Insertion correct:** Yes
**Concept:** ema (expected `ema`)

### feat_002_feature_flags — `atlas_reference`

**Prompt:** add feature flags for gradual rollout

**Atlas score:** 97.5/100
**File precision / recall:** 1.00 / 1.00
**Insertion correct:** Yes
**Concept:** feature_flags (expected `feature_flags`)

### feat_003_stripe_billing — `atlas_reference`

**Prompt:** Add Stripe billing and subscriptions

**Atlas score:** 70.7/100
**File precision / recall:** 1.00 / 0.50
**Insertion correct:** No
**Concept:** stripe_billing (expected `stripe_billing`)

### feat_004_circuit_breaker — `atlas_reference`

**Prompt:** Add circuit breaker for outbound HTTP calls

**Atlas score:** 85.7/100
**File precision / recall:** 1.00 / 1.00
**Insertion correct:** Yes
**Concept:** circuit_breaker (expected `circuit_breaker`)

### feat_005_distributed_tracing — `atlas_reference`

**Prompt:** add distributed tracing with span propagation

**Atlas score:** 92.2/100
**File precision / recall:** 1.00 / 1.00
**Insertion correct:** Yes
**Concept:** distributed_tracing (expected `distributed_tracing`)

### feat_006_rate_limiting — `atlas_reference`

**Prompt:** add API rate limiting middleware

**Atlas score:** 73.1/100
**File precision / recall:** 1.00 / 1.00
**Insertion correct:** No
**Concept:** rate_limiting (expected `rate_limiting`)

### feat_007_jwt — `atlas_reference`

**Prompt:** configure JWT bearer authentication

**Atlas score:** 68.5/100
**File precision / recall:** 0.67 / 1.00
**Insertion correct:** Yes
**Concept:** authentication (expected `jwt`)

### feat_008_oauth2 — `atlas_reference`

**Prompt:** Add OAuth2 authorization code flow with PKCE

**Atlas score:** 86.8/100
**File precision / recall:** 0.67 / 1.00
**Insertion correct:** Yes
**Concept:** oauth2 (expected `oauth2`)

## Repository evidence audit

- `feat_003_stripe_billing` — **incorrect_insertion_point**: got `billing/stripe_webhooks.py` expected one of ['billing/stripe_billing.py']
- `feat_006_rate_limiting` — **incorrect_insertion_point**: got `api/routes.py` expected one of ['api/rate_limit.py']
- `feat_011_db_migration` — **incorrect_insertion_point**: got `db/postgres.py` expected one of ['db/migrations/001_initial.py']
- `feat_013_structured_logging` — **incorrect_insertion_point**: got `auth/login.py` expected one of ['middleware/request_logging.py']
- `feat_019_paper_trading` — **incorrect_insertion_point**: got `registry/signal_registry.py` expected one of ['trading/paper_trading.py']
- `inv_004_stale_cache` — **incorrect_insertion_point**: got `cache/redis_client.py` expected one of ['cache/cache_layer.py']
- `inv_008_rate_limit_429` — **incorrect_insertion_point**: got `api/routes.py` expected one of ['api/rate_limit.py']
- `inv_010_session_expired` — **incorrect_insertion_point**: got `auth/middleware.py` expected one of ['auth/session.py']
- `inv_014_missing_traces` — **incorrect_insertion_point**: got `middleware/request_logging.py` expected one of ['middleware/tracing.py']
- `inv_017_order_fill_delay` — **incorrect_insertion_point**: got `trading/backtest_config.py` expected one of ['trading/execution.py']
- `inv_018_cache_invalidation` — **incorrect_insertion_point**: got `cache/redis_client.py` expected one of ['cache/cache_layer.py']
- `inv_019_migration_failure` — **incorrect_insertion_point**: got `db/postgres.py` expected one of ['db/migrations/001_initial.py']

## Failure analysis (sample)

### feat_003_stripe_billing
- **Why:** Incorrect insertion point
- **Evidence used:** hand
- **Expected:** n/a
- **Missing:** n/a

### feat_006_rate_limiting
- **Why:** Incorrect insertion point
- **Evidence used:** rate
- **Expected:** n/a
- **Missing:** Limi

### feat_007_jwt
- **Why:** Wrong concept identified
- **Evidence used:** auth
- **Expected:** jwt
- **Missing:** jwt

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

### feat_019_paper_trading
- **Why:** Incorrect insertion point
- **Evidence used:** SMAI
- **Expected:** n/a
- **Missing:** Ema,

### inv_002_duplicate_orders
- **Why:** Wrong concept identified
- **Evidence used:** ema
- **Expected:** retr
- **Missing:** retr

### inv_004_stale_cache
- **Why:** Incorrect insertion point
- **Evidence used:** cach
- **Expected:** cach
- **Missing:** n/a

### inv_008_rate_limit_429
- **Why:** Incorrect insertion point
- **Evidence used:** rate
- **Expected:** rate
- **Missing:** Limi

### inv_010_session_expired
- **Why:** Incorrect insertion point
- **Evidence used:** auth
- **Expected:** sess
- **Missing:** Pass

### inv_014_missing_traces
- **Why:** Incorrect insertion point
- **Evidence used:** requ
- **Expected:** trac
- **Missing:** Corr

### inv_017_order_fill_delay
- **Why:** Incorrect insertion point
- **Evidence used:** Slip
- **Expected:** fill
- **Missing:** Side

## Competitive evaluation (manual)

Use `benchmarks/competitive/manual_comparison_template.md` to score Atlas vs Claude Code vs Cursor.
No API integration — paste assistant outputs and score file recall, insertion, and evidence quality manually.

## Driving future phases

Prioritize fixes for categories with lowest mean Atlas score and repeated failure reasons above.
