#!/usr/bin/env python3
"""Bootstrap benchmark reference repos and atlas_benchmark_suite_v1.json (Phase 130)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPOS = ROOT / "repos"


def _w(rel: str, text: str) -> None:
    path = REPOS / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def bootstrap_atlas_reference() -> None:
    repo = "atlas_reference"
    _w(
        f"{repo}/indicators/sma.py",
        """
class SMAIndicator:
    def compute(self, bars):
        return bars
""",
    )
    _w(
        f"{repo}/indicators/indicator_registry.py",
        """
class IndicatorRegistry:
    def register_indicator(self, name, cls):
        self._registry[name] = cls
""",
    )
    _w(
        f"{repo}/registry/signal_registry.py",
        """
from indicators.indicator_registry import IndicatorRegistry

class SignalRegistry(IndicatorRegistry):
    def register_signal(self, name, fn):
        return fn
""",
    )
    _w(
        f"{repo}/signals/pipeline.py",
        """
from registry.signal_registry import SignalRegistry

registry = SignalRegistry()

def run_signals(bars):
    return registry
""",
    )
    _w(
        f"{repo}/trading/backtest_engine.py",
        """
from trading.backtest_config import SLIPPAGE, FILL_MODEL

def run_backtest(strategy):
    return {"slippage": SLIPPAGE, "fill": FILL_MODEL}
""",
    )
    _w(
        f"{repo}/trading/paper_trading.py",
        """
from trading.paper_config import SLIPPAGE, FILL_MODEL
from trading.backtest_engine import run_backtest

def run_paper(strategy):
    return {"slippage": SLIPPAGE, "fill": FILL_MODEL}
""",
    )
    _w(
        f"{repo}/trading/backtest_config.py",
        "SLIPPAGE = 0.001\nFILL_MODEL = 'ideal'\nEXECUTION_TIMING = 'close'\n",
    )
    _w(
        f"{repo}/trading/paper_config.py",
        "SLIPPAGE = 0.01\nFILL_MODEL = 'broker'\nEXECUTION_TIMING = 'live'\n",
    )
    _w(
        f"{repo}/trading/execution.py",
        """
def execute_order(order):
    return order
""",
    )
    _w(
        f"{repo}/trading/order_service.py",
        """
from trading.execution import execute_order

def place_order(order):
    return execute_order(order)
""",
    )
    _w(
        f"{repo}/auth/middleware.py",
        """
def authenticate_jwt(token):
    return token is not None

def auth_middleware(request, next_handler):
    authenticate_jwt(request.headers.get("Authorization"))
    return next_handler(request)
""",
    )
    _w(
        f"{repo}/auth/login.py",
        """
from auth.session import create_session

def login(user, password):
    return create_session(user)
""",
    )
    _w(
        f"{repo}/auth/session.py",
        """
def create_session(user):
    return {"user": user}
""",
    )
    _w(
        f"{repo}/billing/stripe_billing.py",
        """
def charge_customer(customer_id, amount):
    return amount
""",
    )
    _w(
        f"{repo}/billing/stripe_webhooks.py",
        """
def verify_webhook_signature(payload, signature):
    return signature is not None

def handle_stripe_webhook(event):
    return verify_webhook_signature(event, event.get("sig"))
""",
    )
    _w(
        f"{repo}/api/rate_limit.py",
        """
def rate_limit_middleware(request):
    return request
""",
    )
    _w(
        f"{repo}/api/routes.py",
        """
from auth.middleware import auth_middleware
from api.rate_limit import rate_limit_middleware

def register_routes(app):
    app.use(auth_middleware)
    app.use(rate_limit_middleware)
""",
    )
    _w(
        f"{repo}/middleware/tracing.py",
        """
def trace_middleware(request, next_handler):
    return next_handler(request)
""",
    )
    _w(
        f"{repo}/middleware/request_logging.py",
        """
def request_id_middleware(environ, start_response):
    request_id = environ.get("HTTP_X_REQUEST_ID", "local")
    return start_response("200 OK", [("X-Request-ID", request_id)])
""",
    )
    _w(
        f"{repo}/services/http_client.py",
        """
import time

def fetch(url):
    for attempt in range(3):
        try:
            return url
        except Exception:
            time.sleep(2 ** attempt)
""",
    )
    _w(
        f"{repo}/cache/redis_client.py",
        """
class RedisClient:
    def get(self, key):
        return None

    def set(self, key, value, ttl=60):
        return True
""",
    )
    _w(
        f"{repo}/cache/cache_layer.py",
        """
from cache.redis_client import RedisClient

cache = RedisClient()

def get_cached(key):
    return cache.get(key)
""",
    )
    _w(
        f"{repo}/db/postgres.py",
        """
from sqlalchemy import create_engine

engine = create_engine("postgresql://localhost/app")

def get_session():
    return engine.connect()
""",
    )
    _w(
        f"{repo}/db/migrations/001_initial.py",
        """
def upgrade():
    pass

def downgrade():
    pass
""",
    )
    _w(
        f"{repo}/config/feature_flags.py",
        "FEATURE_EMA = False\nFEATURE_TRACING = True\nFEATURE_STRIPE = True\n",
    )
    _w(
        f"{repo}/tests/test_indicators.py",
        """
def test_sma():
    from indicators.sma import SMAIndicator
    assert SMAIndicator().compute([]) == []
""",
    )
    _w(
        f"{repo}/tests/test_auth.py",
        """
def test_auth():
    from auth.middleware import authenticate_jwt
    assert authenticate_jwt("token")
""",
    )


def _s(
    sid: str,
    category: str,
    prompt: str,
    *,
    task_type: str = "build",
    impact_target: str = "",
    concept: str = "",
    files: list,
    insertion: list,
    findings: list | None = None,
    risks: list | None = None,
    tests: list | None = None,
) -> dict:
    return {
        "scenario_id": sid,
        "category": category,
        "repository": "atlas_reference",
        "prompt": prompt,
        "task_type": task_type,
        "impact_target": impact_target,
        "expected_concept_id": concept,
        "expected_findings": findings or [],
        "expected_files": files,
        "expected_insertion_points": insertion,
        "expected_risks": risks or [],
        "expected_tests": tests or [],
    }


def build_scenarios() -> list:
    scenarios = []

    # --- 20 feature additions ---
    scenarios.append(
        _s(
            "feat_001_ema",
            "feature_addition",
            "add EMA indicator with configurable period",
            concept="ema",
            files=["indicators/sma.py", "indicators/indicator_registry.py", "registry/signal_registry.py"],
            insertion=["indicators/indicator_registry.py", "registry/signal_registry.py"],
            findings=["SMA", "registry"],
            risks=["lookahead", "backtest"],
            tests=["indicator", "test_indicators"],
        )
    )
    scenarios.append(
        _s(
            "feat_002_feature_flags",
            "feature_addition",
            "add feature flags for gradual rollout",
            concept="feature_flags",
            files=["config/feature_flags.py"],
            insertion=["config/feature_flags.py"],
            findings=["feature", "flag"],
            tests=["feature"],
        )
    )
    scenarios.append(
        _s(
            "feat_003_stripe_billing",
            "feature_addition",
            "Add Stripe billing and subscriptions",
            concept="stripe_billing",
            files=["billing/stripe_billing.py", "billing/stripe_webhooks.py"],
            insertion=["billing/stripe_billing.py"],
            risks=["webhook", "payment"],
            tests=["billing", "stripe"],
        )
    )
    scenarios.append(
        _s(
            "feat_004_circuit_breaker",
            "feature_addition",
            "Add circuit breaker for outbound HTTP calls",
            concept="circuit_breaker",
            files=["services/http_client.py"],
            insertion=["services/http_client.py"],
            findings=["http", "retry"],
            risks=["cascading"],
            tests=["http", "client"],
        )
    )
    scenarios.append(
        _s(
            "feat_005_distributed_tracing",
            "feature_addition",
            "add distributed tracing with span propagation",
            concept="distributed_tracing",
            files=["middleware/request_logging.py", "middleware/tracing.py"],
            insertion=["middleware/tracing.py", "middleware/request_logging.py"],
            findings=["request", "middleware"],
            tests=["trace", "middleware"],
        )
    )
    scenarios.append(
        _s(
            "feat_006_rate_limiting",
            "feature_addition",
            "add API rate limiting middleware",
            concept="rate_limiting",
            files=["api/rate_limit.py", "api/routes.py"],
            insertion=["api/rate_limit.py"],
            risks=["429"],
            tests=["rate"],
        )
    )
    scenarios.append(
        _s(
            "feat_007_jwt",
            "feature_addition",
            "configure JWT bearer authentication",
            concept="jwt",
            files=["auth/middleware.py", "auth/login.py"],
            insertion=["auth/middleware.py"],
            risks=["token", "security"],
            tests=["auth", "test_auth"],
        )
    )
    scenarios.append(
        _s(
            "feat_008_oauth2",
            "feature_addition",
            "Add OAuth2 authorization code flow with PKCE",
            concept="oauth2",
            files=["auth/login.py", "auth/session.py"],
            insertion=["auth/login.py"],
            tests=["auth", "oauth"],
        )
    )
    scenarios.append(
        _s(
            "feat_009_webhooks",
            "feature_addition",
            "add Stripe webhook receiver with signature verification",
            concept="webhook_receiver",
            files=["billing/stripe_webhooks.py"],
            insertion=["billing/stripe_webhooks.py"],
            risks=["signature"],
            tests=["webhook"],
        )
    )
    scenarios.append(
        _s(
            "feat_010_redis_cache",
            "feature_addition",
            "add Redis caching layer",
            concept="redis_cache",
            files=["cache/redis_client.py", "cache/cache_layer.py"],
            insertion=["cache/redis_client.py"],
            tests=["cache", "redis"],
        )
    )
    scenarios.append(
        _s(
            "feat_011_db_migration",
            "feature_addition",
            "add database migration for new orders table",
            concept="database_migration",
            files=["db/postgres.py", "db/migrations/001_initial.py"],
            insertion=["db/migrations/001_initial.py"],
            risks=["migration", "lock"],
            tests=["migration"],
        )
    )
    scenarios.append(
        _s(
            "feat_012_retry",
            "feature_addition",
            "add retry with exponential backoff to HTTP client",
            concept="retry_backoff",
            files=["services/http_client.py"],
            insertion=["services/http_client.py"],
            findings=["retry", "sleep"],
            tests=["retry", "client"],
        )
    )
    scenarios.append(
        _s(
            "feat_013_structured_logging",
            "feature_addition",
            "add structured logging with correlation IDs",
            concept="structured_logging",
            files=["middleware/request_logging.py"],
            insertion=["middleware/request_logging.py"],
            findings=["request_id", "logging"],
            tests=["log"],
        )
    )
    scenarios.append(
        _s(
            "feat_014_idempotency",
            "feature_addition",
            "add idempotency keys for order placement",
            concept="idempotency_key",
            files=["trading/order_service.py", "trading/execution.py"],
            insertion=["trading/order_service.py"],
            tests=["order"],
        )
    )
    scenarios.append(
        _s(
            "feat_015_health_check",
            "feature_addition",
            "add health check endpoint for services",
            concept="health_check",
            files=["api/routes.py"],
            insertion=["api/routes.py"],
            tests=["health"],
        )
    )
    scenarios.append(
        _s(
            "feat_016_signal_pipeline",
            "feature_addition",
            "extend signal pipeline with new indicator hook",
            concept="ema",
            files=["signals/pipeline.py", "registry/signal_registry.py"],
            insertion=["registry/signal_registry.py", "signals/pipeline.py"],
            tests=["signal"],
        )
    )
    scenarios.append(
        _s(
            "feat_017_postgres",
            "feature_addition",
            "add PostgreSQL session factory",
            concept="postgresql",
            files=["db/postgres.py"],
            insertion=["db/postgres.py"],
            risks=["connection", "pool"],
            tests=["postgres", "db"],
        )
    )
    scenarios.append(
        _s(
            "feat_018_auth_sessions",
            "feature_addition",
            "Add user authentication with login sessions",
            concept="authentication",
            files=["auth/login.py", "auth/session.py", "auth/middleware.py"],
            insertion=["auth/middleware.py"],
            tests=["auth", "session"],
        )
    )
    scenarios.append(
        _s(
            "feat_019_paper_trading",
            "feature_addition",
            "add paper trading mode alongside backtest",
            concept="paper_trading",
            files=["trading/paper_trading.py", "trading/backtest_engine.py"],
            insertion=["trading/paper_trading.py"],
            risks=["backtest", "live"],
            tests=["paper", "backtest"],
        )
    )
    scenarios.append(
        _s(
            "feat_020_slippage_model",
            "feature_addition",
            "implement configurable slippage model",
            concept="slippage_model",
            files=["trading/backtest_config.py", "trading/paper_config.py"],
            insertion=["trading/backtest_config.py"],
            findings=["slippage"],
            tests=["slippage"],
        )
    )

    # --- 20 bug investigations ---
    inv_specs = [
        ("inv_001_backtest_paper", "backtest is much better than paper trading", "backtest_live_divergence", ["trading/backtest_config.py", "trading/paper_config.py"], ["slippage", "fill"]),
        ("inv_002_duplicate_orders", "duplicate orders placed twice in production", "retry_backoff", ["trading/order_service.py", "trading/execution.py"], ["duplicate", "order"]),
        ("inv_003_webhook_failures", "Stripe webhook signature verification failing", "webhook_receiver", ["billing/stripe_webhooks.py"], ["webhook", "signature"]),
        ("inv_004_stale_cache", "API returns stale cached data after update", "redis_cache", ["cache/cache_layer.py", "cache/redis_client.py"], ["cache", "stale"]),
        ("inv_005_auth_bypass", "unauthenticated requests reaching protected routes", "authentication", ["auth/middleware.py", "api/routes.py"], ["auth", "middleware"]),
        ("inv_006_slippage_mismatch", "slippage differs between backtest and live", "backtest_live_divergence", ["trading/backtest_config.py", "trading/paper_config.py"], ["slippage"]),
        ("inv_007_indicator_mismatch", "indicator values differ backtest vs live", "indicator_backtest_live", ["indicators/sma.py", "signals/pipeline.py"], ["indicator"]),
        ("inv_008_rate_limit_429", "users getting 429 too many requests", "rate_limiting", ["api/rate_limit.py"], ["rate", "429"]),
        ("inv_009_stripe_invalid_sig", "invalid stripe webhook signature errors", "webhook_receiver", ["billing/stripe_webhooks.py"], ["signature", "stripe"]),
        ("inv_010_session_expired", "login session expires immediately after login", "authentication", ["auth/session.py", "auth/login.py"], ["session"]),
        ("inv_011_redis_timeout", "redis connection timeout under load", "redis_cache", ["cache/redis_client.py"], ["redis", "timeout"]),
        ("inv_012_postgres_deadlock", "postgres deadlock on concurrent order updates", "postgresql", ["db/postgres.py"], ["postgres", "deadlock"]),
        ("inv_013_retry_storm", "retry storm amplifying outbound HTTP failures", "retry_backoff", ["services/http_client.py"], ["retry"]),
        ("inv_014_missing_traces", "requests missing trace spans across services", "distributed_tracing", ["middleware/tracing.py", "middleware/request_logging.py"], ["trace", "span"]),
        ("inv_015_flag_rollout", "feature flag rollout enabling wrong cohort", "feature_flags", ["config/feature_flags.py"], ["feature", "flag"]),
        ("inv_016_jwt_expired", "JWT tokens rejected as expired immediately", "jwt", ["auth/middleware.py"], ["jwt", "token"]),
        ("inv_017_order_fill_delay", "orders fill slowly in paper but not backtest", "backtest_live_divergence", ["trading/execution.py", "trading/paper_trading.py"], ["fill", "execution"]),
        ("inv_018_cache_invalidation", "cache invalidation not running after writes", "redis_cache", ["cache/cache_layer.py"], ["cache", "invalidation"]),
        ("inv_019_migration_failure", "database migration fails on deploy", "database_migration", ["db/migrations/001_initial.py"], ["migration"]),
        ("inv_020_execution_timing", "execution timing differs between sim and live", "backtest_live_divergence", ["trading/backtest_config.py", "trading/paper_config.py"], ["timing", "execution"]),
    ]
    for sid, prompt, concept, files, findings in inv_specs:
        scenarios.append(
            _s(
                sid,
                "bug_investigation",
                prompt,
                task_type="investigate",
                concept=concept,
                files=files,
                insertion=files[:1],
                findings=findings,
                risks=["regression"],
                tests=["integration"],
            )
        )

    # --- 10 impact analyses ---
    impact_specs = [
        ("imp_001_delete_auth_middleware", "auth/middleware.py", ["api/routes.py", "auth/login.py"], ["auth", "security"], ["test_auth"]),
        ("imp_002_replace_redis", "cache/redis_client.py", ["cache/cache_layer.py"], ["cache", "availability"], ["cache"]),
        ("imp_003_migrate_schema", "db/migrations/001_initial.py", ["db/postgres.py"], ["migration", "data"], ["migration"]),
        ("imp_004_remove_signal_registry", "registry/signal_registry.py", ["signals/pipeline.py", "indicators/indicator_registry.py"], ["signal", "breaking"], ["signal"]),
        ("imp_005_delete_webhooks", "billing/stripe_webhooks.py", ["billing/stripe_billing.py"], ["billing", "webhook"], ["stripe"]),
        ("imp_006_remove_tracing", "middleware/tracing.py", ["middleware/request_logging.py", "api/routes.py"], ["observability"], ["middleware"]),
        ("imp_007_delete_indicator_registry", "indicators/indicator_registry.py", ["registry/signal_registry.py", "signals/pipeline.py"], ["indicator"], ["test_indicators"]),
        ("imp_008_replace_http_client", "services/http_client.py", [], ["http", "retry"], ["client"]),
        ("imp_009_delete_rate_limit", "api/rate_limit.py", ["api/routes.py"], ["rate", "abuse"], ["rate"]),
        ("imp_010_remove_backtest", "trading/backtest_engine.py", ["trading/paper_trading.py"], ["backtest", "trading"], ["backtest"]),
    ]
    for sid, target, affected, risks, tests in impact_specs:
        scenarios.append(
            _s(
                sid,
                "impact_analysis",
                f"assess impact of changing `{target}`",
                task_type="impact",
                impact_target=target,
                files=[target] + affected,
                insertion=[target],
                risks=risks,
                tests=tests,
            )
        )

    # Optional external repo scenario (skipped when absent)
    scenarios.append(
        {
            "scenario_id": "opt_final_algo_ema",
            "category": "feature_addition",
            "repository": "FINAL_ALGO_TRADER",
            "prompt": "add ema indicator",
            "task_type": "build",
            "expected_concept_id": "ema",
            "expected_files": ["indicator", "signal"],
            "expected_insertion_points": ["indicator", "registry"],
            "expected_findings": ["EMA"],
            "expected_risks": ["lookahead"],
            "expected_tests": ["indicator"],
            "notes": "Optional — requires FINAL_ALGO_TRADER on disk",
        }
    )

    assert sum(1 for s in scenarios if s["category"] == "feature_addition") >= 20
    assert sum(1 for s in scenarios if s["category"] == "bug_investigation") >= 20
    assert sum(1 for s in scenarios if s["category"] == "impact_analysis") >= 10
    assert len(scenarios) >= 50
    return scenarios


def main() -> int:
    bootstrap_atlas_reference()
    scenarios = build_scenarios()
    payload = {
        "version": 1,
        "phase": 130,
        "total": len(scenarios),
        "categories": {
            "feature_addition": sum(1 for s in scenarios if s["category"] == "feature_addition"),
            "bug_investigation": sum(1 for s in scenarios if s["category"] == "bug_investigation"),
            "impact_analysis": sum(1 for s in scenarios if s["category"] == "impact_analysis"),
        },
        "scenarios": scenarios,
    }
    out = ROOT / "atlas_benchmark_suite_v1.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {len(scenarios)} scenarios to {out}")
    print("Categories:", payload["categories"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
