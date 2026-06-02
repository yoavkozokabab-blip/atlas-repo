"""Phase 125 — Local domain knowledge for Build Plan and Investigate (deterministic, no LLM).

Maps user language to structured concepts, then grounds concepts on the scanned repository graph.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Domain labels (Part A)
# ---------------------------------------------------------------------------

DOMAINS: Dict[str, str] = {
    "trading": "Trading / Algo systems",
    "web_backend": "Web backend",
    "frontend": "Frontend / UI",
    "infra": "Infrastructure / DevOps",
    "data_analytics": "Data / Analytics",
}

# ---------------------------------------------------------------------------
# Concept registry
# ---------------------------------------------------------------------------

CONCEPTS: Dict[str, Dict[str, Any]] = {
    "ema": {
        "name": "EMA",
        "title": "Exponential Moving Average",
        "domain": "trading",
        "feature_type": "indicator",
        "aliases": (
            "ema",
            "exponential moving average",
            "exp moving average",
            "moving average ema",
            "trend filter ema",
        ),
        "meaning": (
            "A trend/price smoothing indicator calculated from a historical price series "
            "with exponential weighting on recent bars."
        ),
        "typical_locations": (
            "indicator calculation module",
            "strategy/signal generation",
            "config/parameters (period/span)",
            "backtest calculation path",
            "live/paper calculation path",
            "validation/tests",
        ),
        "path_keywords": (
            "indicator",
            "indicators",
            "ema",
            "moving",
            "average",
            "signal",
            "strategy",
            "ta",
            "technical",
        ),
        "required_inputs": ("price series (OHLCV)", "period/span configuration"),
        "required_outputs": ("EMA series aligned to bars", "signal-ready values after warmup"),
        "implementation_steps": (
            "Locate existing indicator/signal calculation path in the repo.",
            "Add EMA calculation (or extend the indicator registry) with configurable period/span.",
            "Integrate EMA into strategy entry/exit rules without changing unrelated logic.",
            "Ensure sufficient warmup bars before signals evaluate (period bars minimum).",
            "Ensure no lookahead: compute only from bars available at decision time.",
            "Wire the same calculation path (or provably equivalent logic) for backtest and live/paper.",
            "Add unit tests comparing output to a known reference (e.g. pandas ewm).",
        ),
        "implementation_risks": (
            "Lookahead bias (using future bars or incomplete bar close).",
            "Insufficient warmup bars (NaN or flat values suppress signals).",
            "Inconsistent backtest vs live/paper calculation path.",
            "Wrong price source (close vs open vs typical price).",
            "Period/span config drift between envs.",
            "NaN handling on initial bars.",
            "Recomputing from partial/forming bars in live mode.",
            "Performance on large universes (vectorize, avoid per-tick Python loops).",
        ),
        "common_bugs": (
            "EMA differs between backtest and paper because live uses forming bars.",
            "Warmup too short — signals fire before EMA is valid.",
            "Period mismatch between config and strategy code.",
        ),
        "verification": (
            "Compare EMA output against pandas/known fixture on a fixed price series.",
            "Test warmup: first valid index equals period-1 (or documented rule).",
            "Test no future bars used at signal timestamp.",
            "Test backtest/live calculation equivalence on identical bar stream.",
            "Test config period propagation from config → indicator → strategy.",
            "Run a small historical backtest before/after and diff signal timestamps.",
        ),
        "tests_to_run": (
            "Unit test EMA formula on fixture OHLCV.",
            "Integration test strategy signals with EMA filter enabled.",
            "Backtest vs paper parity test on same date range.",
        ),
        "related_concepts": ("rsi", "indicator_backtest_live", "backtest_live_divergence"),
    },
    "rsi": {
        "name": "RSI",
        "title": "Relative Strength Index",
        "domain": "trading",
        "feature_type": "indicator",
        "aliases": ("rsi", "relative strength index", "relative strength"),
        "meaning": "Momentum oscillator (0–100) from average gains vs losses over a lookback window.",
        "typical_locations": (
            "indicator module",
            "strategy/signal rules",
            "config (period, overbought/oversold thresholds)",
            "backtest and live paths",
        ),
        "path_keywords": ("rsi", "indicator", "signal", "strategy", "momentum", "oscillator"),
        "required_inputs": ("price series", "RSI period", "threshold levels"),
        "required_outputs": ("RSI series", "overbought/oversold signals"),
        "implementation_steps": (
            "Find indicator pipeline and strategy condition evaluation.",
            "Implement RSI with configurable period; document warmup length.",
            "Apply thresholds in strategy rules; avoid double-smoothing.",
            "Align backtest and live calculation; add fixture-based unit tests.",
        ),
        "implementation_risks": (
            "Warmup length off-by-one.",
            "Different smoothing (Wilder vs SMA) between backtest and live.",
            "Division by zero on flat markets.",
            "Lookahead on partial bars in live.",
        ),
        "common_bugs": (
            "RSI never reaches threshold because of wrong price field.",
            "Live RSI lags due to incomplete bar updates.",
        ),
        "verification": (
            "Compare to reference RSI on fixture data.",
            "Verify warmup bars before first signal.",
            "Backtest/live parity on same bars.",
        ),
        "tests_to_run": ("test_rsi_fixture", "strategy signal regression"),
        "related_concepts": ("ema", "indicator_backtest_live"),
    },
    "atr_stop_loss": {
        "name": "ATR stop loss",
        "title": "ATR-based stop loss",
        "domain": "trading",
        "feature_type": "risk",
        "aliases": (
            "atr stop",
            "atr stop loss",
            "atr trailing",
            "average true range stop",
            "atr based stop",
        ),
        "meaning": "Stop distance scaled by Average True Range volatility rather than fixed ticks.",
        "typical_locations": (
            "risk management",
            "order/execution",
            "position manager",
            "strategy exit rules",
        ),
        "path_keywords": ("atr", "stop", "risk", "trail", "exit", "position", "order"),
        "required_inputs": ("ATR period", "multiplier", "price series", "position state"),
        "required_outputs": ("stop price level", "trigger events"),
        "implementation_steps": (
            "Locate exit/stop evaluation and position lifecycle code.",
            "Compute ATR with correct true range formula and warmup.",
            "Set stop = entry ± multiplier × ATR; handle trailing updates.",
            "Ensure stop checks use intended bar field (close vs intrabar).",
            "Test stop triggers on historical replay.",
        ),
        "implementation_risks": (
            "Intrabar wick triggers vs close-only logic.",
            "Trailing stop ratchet direction wrong.",
            "ATR period mismatch across modes.",
            "Stop too tight after volatility spike.",
        ),
        "common_bugs": (
            "Stops fire on wicks in backtest but not live (or vice versa).",
            "ATR uses wrong timeframe.",
        ),
        "verification": (
            "Replay known bars and assert stop levels.",
            "Compare ATR to reference implementation.",
            "Paper trade one symbol with logged stop levels.",
        ),
        "tests_to_run": ("test_atr_formula", "test_stop_trigger_replay"),
        "related_concepts": ("ema", "backtest_live_divergence"),
    },
    "authentication": {
        "name": "Authentication",
        "title": "User authentication",
        "domain": "web_backend",
        "feature_type": "auth",
        "aliases": (
            "authentication",
            "auth",
            "login",
            "sign in",
            "signup",
            "jwt",
            "oauth",
            "session auth",
        ),
        "meaning": "Identity verification, sessions or tokens, and protected routes.",
        "typical_locations": (
            "user model",
            "auth routes/controllers",
            "session/token middleware",
            "password hashing",
            "permissions",
        ),
        "path_keywords": ("auth", "login", "session", "user", "identity", "jwt", "oauth", "password"),
        "required_inputs": ("credentials", "session store or JWT secret", "user persistence"),
        "required_outputs": ("authenticated session/token", "401/403 on protected routes"),
        "implementation_steps": (
            "Define user model and credential storage (hashed passwords).",
            "Add login/signup endpoints and session or JWT issuance.",
            "Protect routes with middleware/guards.",
            "Add permission checks on sensitive actions.",
            "Add tests for login, logout, and unauthorized access.",
        ),
        "implementation_risks": (
            "Session fixation",
            "Token leakage in logs",
            "Missing authorization on new endpoints",
            "Weak password policy",
        ),
        "common_bugs": ("Session expires unexpectedly", "Token not sent on API calls"),
        "verification": (
            "Test login/logout flows",
            "Test protected route without token returns 401",
            "Test role/permission boundaries",
        ),
        "tests_to_run": ("test_auth_login", "test_protected_route_401"),
        "related_concepts": ("rate_limiting", "stripe_billing"),
    },
    "stripe_billing": {
        "name": "Stripe billing",
        "title": "Stripe payments & subscriptions",
        "domain": "web_backend",
        "feature_type": "billing",
        "aliases": (
            "stripe",
            "billing",
            "subscription",
            "checkout",
            "payment",
            "stripe billing",
        ),
        "meaning": "Customer billing via Stripe Checkout, subscriptions, and webhooks.",
        "typical_locations": (
            "checkout/session creation",
            "webhook handler",
            "customer/subscription persistence",
            "billing portal",
        ),
        "path_keywords": ("stripe", "billing", "payment", "checkout", "subscription", "invoice", "webhook"),
        "required_inputs": ("Stripe API keys", "price IDs", "customer record", "webhook signing secret"),
        "required_outputs": ("checkout session", "subscription state", "idempotent webhook processing"),
        "implementation_steps": (
            "Model customer ↔ Stripe customer ID mapping.",
            "Create Checkout session or PaymentIntent flow.",
            "Implement webhook endpoint with signature verification.",
            "Update subscription state idempotently from events.",
            "Gate features by subscription status.",
        ),
        "implementation_risks": (
            "Webhook replay without idempotency",
            "Missing signature verification",
            "Race between checkout success and webhook",
            "Test vs live key mix-up",
        ),
        "common_bugs": ("Subscription active in Stripe but not in DB", "Double-charge on webhook retry"),
        "verification": (
            "Stripe CLI webhook replay in test mode",
            "Test checkout → webhook → entitlements",
            "Verify idempotency keys on events",
        ),
        "tests_to_run": ("test_webhook_signature", "test_subscription_state_sync"),
        "related_concepts": ("authentication"),
    },
    "rate_limiting": {
        "name": "Rate limiting",
        "title": "API rate limiting",
        "domain": "web_backend",
        "feature_type": "infra",
        "aliases": ("rate limit", "rate limiting", "throttle", "throttling", "429"),
        "meaning": "Cap request rates per client/IP/key to protect the service.",
        "typical_locations": ("middleware", "API gateway", "Redis counter", "reverse proxy config"),
        "path_keywords": ("rate", "limit", "throttle", "middleware", "redis", "api"),
        "required_inputs": ("limit policy", "identifier key", "window size"),
        "required_outputs": ("429 when exceeded", "headers indicating limit"),
        "implementation_steps": (
            "Choose limit scope (IP, user, API key).",
            "Implement counter (in-memory, Redis, or proxy).",
            "Apply middleware before handlers.",
            "Return consistent 429 + Retry-After.",
            "Load-test limits.",
        ),
        "implementation_risks": ("Shared NAT false positives", "Clock skew on windows", "Redis SPOF"),
        "common_bugs": ("Legitimate bursts blocked", "Limits not applied on all routes"),
        "verification": ("Burst test returns 429", "Limits reset after window"),
        "tests_to_run": ("test_rate_limit_middleware"),
        "related_concepts": ("authentication", "observability"),
    },
    "logging": {
        "name": "Structured logging",
        "title": "Logging / audit trail",
        "domain": "infra",
        "feature_type": "observability",
        "aliases": ("logging", "audit log", "structured log", "logger", "log aggregation"),
        "meaning": "Consistent structured logs for debugging, audit, and operations.",
        "typical_locations": ("logger setup", "middleware", "service modules", "log shipping"),
        "path_keywords": ("log", "logger", "audit", "trace", "telemetry"),
        "required_inputs": ("log level config", "correlation ID", "PII redaction rules"),
        "required_outputs": ("JSON/text logs", "request correlation"),
        "implementation_steps": (
            "Centralize logger configuration.",
            "Add correlation/request IDs in middleware.",
            "Redact secrets and PII.",
            "Define log levels per subsystem.",
        ),
        "implementation_risks": ("Log volume cost", "PII in logs", "Secret leakage"),
        "common_bugs": ("Missing context on errors", "Duplicate log lines"),
        "verification": ("Trigger error and verify trace ID in logs", "Scan sample logs for secrets"),
        "tests_to_run": ("test_logger_emits_structured_fields"),
        "related_concepts": ("observability", "retry_queue"),
    },
    "retry_queue": {
        "name": "Retry queue",
        "title": "Retry queue / async jobs",
        "domain": "infra",
        "feature_type": "queue",
        "aliases": ("retry queue", "dead letter", "celery", "task queue", "job queue", "worker queue"),
        "meaning": "Asynchronous work with retries, backoff, and dead-letter handling.",
        "typical_locations": ("worker", "broker", "task definitions", "scheduler"),
        "path_keywords": ("queue", "worker", "celery", "task", "job", "broker", "retry", "rabbit", "redis"),
        "required_inputs": ("broker URL", "retry policy", "idempotent handlers"),
        "required_outputs": ("enqueued jobs", "DLQ for failures"),
        "implementation_steps": (
            "Define task handlers as idempotent.",
            "Configure broker and retry/backoff.",
            "Add dead-letter or failed-job storage.",
            "Monitor queue depth and lag.",
        ),
        "implementation_risks": ("Non-idempotent retries duplicate side effects", "Poison messages"),
        "common_bugs": ("Tasks stuck in queue", "Retry storm overloads downstream"),
        "verification": ("Fail task twice — single side effect", "DLQ receives poison message"),
        "tests_to_run": ("test_task_retry_idempotent"),
        "related_concepts": ("logging", "observability"),
    },
    "observability": {
        "name": "Observability",
        "title": "Metrics, traces, and health checks",
        "domain": "infra",
        "feature_type": "observability",
        "aliases": ("observability", "metrics", "prometheus", "tracing", "health check", "monitoring"),
        "meaning": "Operational visibility: metrics, distributed traces, and health endpoints.",
        "typical_locations": ("metrics middleware", "trace instrumentation", "/health routes"),
        "path_keywords": ("metric", "prometheus", "trace", "health", "monitor", "otel", "statsd"),
        "required_inputs": ("metric names/labels", "trace exporter", "SLIs"),
        "required_outputs": ("scraped metrics", "trace spans", "200/503 health"),
        "implementation_steps": (
            "Add health/readiness endpoints.",
            "Instrument key paths with metrics.",
            "Add trace context propagation.",
            "Dashboard critical SLIs.",
        ),
        "implementation_risks": ("Cardinality explosion", "PII in traces", "Health check too shallow"),
        "common_bugs": ("Metrics missing on error paths", "Health green while dependencies down"),
        "verification": ("Scrape metrics in staging", "Break dependency — readiness fails"),
        "tests_to_run": ("test_health_endpoint", "test_metrics_increment"),
        "related_concepts": ("logging", "rate_limiting"),
    },
    "backtest_live_divergence": {
        "name": "Backtest vs live/paper divergence",
        "title": "Backtest/live behavioral mismatch",
        "domain": "trading",
        "feature_type": "symptom",
        "aliases": (
            "backtest better than paper",
            "backtest better than live",
            "better than paper trading",
            "better than paper",
            "better than live",
            "much better than paper",
            "much better than live",
            "paper worse than backtest",
            "live worse than backtest",
            "simulation better than live",
        ),
        "meaning": "Performance or behavior differs between simulation and live/paper execution.",
        "typical_locations": (
            "backtest engine",
            "paper/live execution engine",
            "data feed",
            "fill/slippage model",
            "signal timing",
        ),
        "path_keywords": ("backtest", "paper", "live", "sim", "execution", "broker", "fill", "slippage"),
        "required_inputs": ("comparable bar stream", "execution logs from both modes"),
        "required_outputs": ("identified divergence point"),
        "implementation_steps": (),  # investigate-only
        "implementation_risks": (),
        "common_bugs": (
            "Fill price mismatch (ideal next-bar vs latest quote).",
            "Signal timing mismatch (closed bar vs forming bar).",
            "Slippage/gap modeling only in one mode.",
            "Ranking/capacity constraints ignored in backtest.",
            "Stale price in live.",
            "Rejected orders not modeled in backtest.",
            "Session/timezone mismatch.",
            "Fees/commission applied inconsistently.",
        ),
        "verification": (
            "Log signal timestamp and fill price for one trade in both modes.",
            "Diff bar stream and indicator values at signal time.",
            "Compare fee/slippage assumptions side by side.",
        ),
        "tests_to_run": ("parity test on fixed bar stream"),
        "related_concepts": ("ema", "indicator_backtest_live"),
        "investigate_only": True,
    },
    "indicator_backtest_live": {
        "name": "Indicator backtest/live mismatch",
        "title": "Indicator works in backtest but not live/paper",
        "domain": "trading",
        "feature_type": "symptom",
        "aliases": (
            "works in backtest but not live",
            "works in backtest but not paper",
            "backtest but not paper",
            "backtest but not live",
            "indicator works in backtest",
            "ema works in backtest",
            "signal works in backtest",
        ),
        "meaning": "Indicator or signal logic passes backtest but fails or stays flat in live/paper.",
        "typical_locations": (
            "indicator calculation",
            "data feed / bar builder",
            "strategy signal evaluation",
            "config",
        ),
        "path_keywords": ("indicator", "signal", "backtest", "paper", "live", "ema", "rsi", "bar", "feed"),
        "required_inputs": ("indicator values at signal time in both modes"),
        "required_outputs": ("root cause of value/timing mismatch"),
        "implementation_steps": (),
        "implementation_risks": (),
        "common_bugs": (
            "Indicator calculation mismatch between paths.",
            "Partial/forming candle used in live but closed bar in backtest.",
            "Live price source mismatch (bid/ask vs last vs close).",
            "Warmup data length shorter in live.",
            "Config period mismatch.",
            "NaN handling suppresses live signals.",
        ),
        "verification": (
            "Dump indicator series for same symbol/date in both modes.",
            "Verify bar timestamps align at signal evaluation.",
            "Check warmup bar count before first live signal.",
        ),
        "tests_to_run": ("indicator parity fixture test"),
        "related_concepts": ("ema", "rsi", "backtest_live_divergence"),
        "investigate_only": True,
    },
}


@dataclass
class ConceptClassification:
    concept_id: Optional[str]
    concept_name: str
    concept_title: str
    domain: str
    domain_label: str
    feature_type: str
    concept_confidence: str
    repo_mapping_confidence: str
    unknowns: List[str] = field(default_factory=list)
    architecture_pattern: str = ""


@dataclass
class RepoFileRoles:
    must_inspect: List[str]
    likely_modify: List[str]
    verify_only: List[str]
    do_not_touch: List[str]
    dedicated_module_found: bool
    integration_note: str


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower().strip())


def _alias_score(text: str, aliases: Tuple[str, ...]) -> Tuple[float, List[str]]:
    """Score how well text matches concept aliases (longer phrases win)."""
    norm = _normalize(text)
    hits: List[str] = []
    score = 0.0
    for alias in sorted(aliases, key=len, reverse=True):
        a = alias.lower().strip()
        if not a:
            continue
        if a in norm:
            hits.append(a)
            score += 2.0 + min(len(a) / 10.0, 3.0)
        elif len(a) > 4 and re.search(rf"\b{re.escape(a)}\b", norm):
            hits.append(a)
            score += 1.5 + min(len(a) / 12.0, 2.0)
    return score, hits


def classify_request(text: str, *, mode: str = "build") -> ConceptClassification:
    """Part B — classify user text into domain + concept + feature type."""
    norm = _normalize(text)
    if not norm:
        return ConceptClassification(
            concept_id=None,
            concept_name="",
            concept_title="",
            domain="",
            domain_label="",
            feature_type="unknown",
            concept_confidence="low",
            repo_mapping_confidence="low",
            unknowns=["Empty request"],
        )

    best_id: Optional[str] = None
    best_score = 0.0
    best_hits: List[str] = []

    for cid, concept in CONCEPTS.items():
        if mode == "build" and concept.get("investigate_only"):
            continue
        score, hits = _alias_score(norm, tuple(concept.get("aliases", ())))
        if score > best_score:
            best_score = score
            best_id = cid
            best_hits = hits

    if not best_id or best_score < 1.5:
        unknowns = ["No domain concept matched — plan relies on path keywords only."]
        if mode == "investigate":
            unknowns.append("Add indicator name, subsystem, or file path for sharper routing.")
        return ConceptClassification(
            concept_id=None,
            concept_name="",
            concept_title="",
            domain="",
            domain_label="",
            feature_type="general",
            concept_confidence="low",
            repo_mapping_confidence="low",
            unknowns=unknowns,
        )

    concept = CONCEPTS[best_id]
    if best_score >= 5.0 or len(best_hits) >= 2:
        conf = "high"
    elif best_score >= 2.0:
        conf = "medium"
    else:
        conf = "low"

    domain = concept.get("domain", "")
    pattern = concept.get("feature_type", "feature")
    if domain == "trading" and pattern == "indicator":
        architecture_pattern = "price-series indicator → strategy signal → backtest/live paths"
    elif domain == "web_backend" and pattern == "auth":
        architecture_pattern = "identity → session/token → middleware → protected routes"
    elif domain == "web_backend" and pattern == "billing":
        architecture_pattern = "checkout → Stripe → webhook → subscription state"
    else:
        architecture_pattern = " → ".join(concept.get("typical_locations", ())[:4]) or "subsystem-specific"

    unknowns: List[str] = []
    if conf != "high":
        unknowns.append("Concept match is partial — confirm the request targets this concept.")
    if concept.get("investigate_only"):
        unknowns.append("This pattern is optimized for investigation, not greenfield implementation.")

    return ConceptClassification(
        concept_id=best_id,
        concept_name=concept.get("name", best_id),
        concept_title=concept.get("title", concept.get("name", "")),
        domain=domain,
        domain_label=DOMAINS.get(domain, domain),
        feature_type=pattern,
        concept_confidence=conf,
        repo_mapping_confidence="low",  # updated after mapping
        unknowns=unknowns,
        architecture_pattern=architecture_pattern,
    )


def search_terms_for_classification(classification: ConceptClassification) -> Set[str]:
    if not classification.concept_id:
        return set()
    concept = CONCEPTS[classification.concept_id]
    terms: Set[str] = set()
    for kw in concept.get("path_keywords", ()):
        terms.add(kw.lower())
    for alias in concept.get("aliases", ())[:3]:
        for tok in re.findall(r"[a-z][a-z0-9_]{2,}", alias.lower()):
            terms.add(tok)
    return terms


def map_concept_to_repository(
    classification: ConceptClassification,
    modules: List[Dict[str, Any]],
    risks_map: Dict[str, Dict[str, Any]],
    *,
    scored_paths: Optional[List[str]] = None,
) -> RepoFileRoles:
    """Part E — map concept to real module paths; never invent paths."""
    allowed = {n.get("path") for n in modules if n.get("path")}
    if not classification.concept_id or not allowed:
        return RepoFileRoles(
            must_inspect=list(scored_paths or [])[:5],
            likely_modify=[],
            verify_only=[],
            do_not_touch=[],
            dedicated_module_found=False,
            integration_note="No scanned modules available for concept mapping.",
        )

    concept = CONCEPTS[classification.concept_id]
    keywords = tuple(k.lower() for k in concept.get("path_keywords", ()))
    verify_kw = ("backtest", "paper", "live", "sim", "config", "settings", "test")
    modify_kw = ("indicator", "signal", "strategy", "ta", "technical", "ema", "rsi", "atr")
    if classification.feature_type in {"auth", "billing"}:
        modify_kw = ("auth", "login", "user", "stripe", "billing", "payment", "checkout", "webhook")
    elif classification.feature_type in {"observability", "queue"}:
        modify_kw = ("log", "metric", "trace", "queue", "worker", "task", "health")

    ranked: List[Tuple[float, str]] = []
    for node in modules:
        path = node.get("path") or ""
        if path not in allowed:
            continue
        p = path.lower().replace("\\", "/")
        score = 0.0
        for kw in keywords:
            if kw in p:
                score += 3.0
        if scored_paths and path in scored_paths[:15]:
            score += 2.0
        risk = risks_map.get(path) or {}
        score += min(2.0, float(risk.get("total_score", 0) or 0) / 30.0)
        if score > 0:
            ranked.append((score, path))
    ranked.sort(key=lambda x: (-x[0], x[1]))

    paths = [p for _, p in ranked]
    dedicated = any(
        any(m in p.lower() for m in ("indicator", "indicators", "ta_", "/ta/"))
        for p in paths[:8]
    ) if classification.feature_type == "indicator" else bool(paths)

    must = paths[:5]
    likely_modify = [p for p in paths if any(k in p.lower() for k in modify_kw)][:6]
    verify_only = [p for p in paths if any(k in p.lower() for k in verify_kw)][:6]
    if not likely_modify and must:
        likely_modify = must[:3]

    high_fan_in = []
    for p in paths:
        row = risks_map.get(p) or {}
        fan = int(row.get("fan_in", 0) or 0)
        if fan >= 20 and p not in must:
            high_fan_in.append(p)
    do_not_touch = high_fan_in[:5]

    if dedicated:
        note = f"Dedicated modules found for {classification.concept_name}."
    elif must:
        note = (
            f"No dedicated {classification.concept_name.lower()} module found. "
            f"Candidate integration points: {', '.join(must[:4])}."
        )
    else:
        note = (
            f"No production module matched {classification.concept_name} keywords. "
            "Inspect entry points and top import hubs in Repository Map."
        )

    mapping_conf = "high" if dedicated and len(must) >= 2 else ("medium" if must else "low")
    classification.repo_mapping_confidence = mapping_conf

    return RepoFileRoles(
        must_inspect=must,
        likely_modify=likely_modify,
        verify_only=verify_only,
        do_not_touch=do_not_touch,
        dedicated_module_found=dedicated,
        integration_note=note,
    )


def concept_understanding_text(classification: ConceptClassification) -> str:
    if not classification.concept_id:
        return ""
    concept = CONCEPTS[classification.concept_id]
    return concept.get("meaning", "")


def why_this_matters_text(classification: ConceptClassification) -> str:
    if not classification.concept_id:
        return ""
    concept = CONCEPTS[classification.concept_id]
    domain = classification.domain_label
    ft = classification.feature_type
    if classification.domain == "trading" and ft == "indicator":
        return (
            f"{concept['name']} is a price-series indicator — it must be computed consistently "
            "across backtest and live/paper paths, with correct warmup and no lookahead."
        )
    if classification.domain == "web_backend" and ft == "billing":
        return "Billing changes affect money movement — webhooks, idempotency, and entitlements must stay in sync."
    if classification.domain == "web_backend" and ft == "auth":
        return "Auth changes affect every protected route — sessions, tokens, and permissions must remain consistent."
    return f"Changes in {domain} affect {', '.join(concept.get('typical_locations', ())[:3])}."


def knowledge_risks(classification: ConceptClassification) -> List[str]:
    if not classification.concept_id:
        return []
    concept = CONCEPTS[classification.concept_id]
    risks = list(concept.get("implementation_risks", ()))
    if not risks:
        risks = list(concept.get("common_bugs", ()))
    return risks[:10]


def knowledge_verification(classification: ConceptClassification) -> List[str]:
    if not classification.concept_id:
        return []
    return list(CONCEPTS[classification.concept_id].get("verification", ()))[:10]


def knowledge_implementation_steps(classification: ConceptClassification) -> List[str]:
    if not classification.concept_id:
        return []
    steps = CONCEPTS[classification.concept_id].get("implementation_steps", ())
    return list(steps)[:12]


def domain_investigation_notes(classification: ConceptClassification) -> List[str]:
    """Failure modes and checks for investigate mode."""
    if not classification.concept_id:
        return []
    concept = CONCEPTS[classification.concept_id]
    notes = list(concept.get("common_bugs", ()))
    notes.extend(concept.get("verification", ())[:4])
    return notes[:10]


def enrich_build_plan(
    plan: Dict[str, Any],
    classification: ConceptClassification,
    roles: RepoFileRoles,
) -> None:
    """Mutate plan with domain knowledge fields (Part C)."""
    if not classification.concept_id:
        plan["domain_knowledge"] = {"applied": False}
        return

    concept = CONCEPTS[classification.concept_id]
    steps = knowledge_implementation_steps(classification)
    k_risks = knowledge_risks(classification)
    k_verify = knowledge_verification(classification)
    k_tests = list(concept.get("tests_to_run", ()))

    if roles.must_inspect:
        plan["files_to_inspect_first"] = roles.must_inspect[:8]
    if roles.likely_modify:
        plan["files_likely_to_change"] = roles.likely_modify[:8]
        plan["likely_affected_modules"] = list(
            dict.fromkeys(roles.likely_modify + (plan.get("likely_affected_modules") or []))
        )[:12]

    existing_risks = plan.get("architectural_risks") or []
    for r in k_risks:
        label = f"[domain] {r}"
        if label not in existing_risks:
            existing_risks.append(label)
    plan["architectural_risks"] = existing_risks[:14]

    vplan = list(plan.get("verification_plan") or [])
    for v in k_verify:
        if v not in vplan:
            vplan.append(v)
    plan["verification_plan"] = vplan[:12]

    tests = list(plan.get("tests_likely_affected") or [])
    for t in k_tests:
        if t not in tests:
            tests.append(t)
    plan["tests_likely_affected"] = tests
    plan["tests_required"] = tests

    if steps:
        impl = list(plan.get("implementation_order") or [])
        plan["domain_implementation_steps"] = steps
        if not impl:
            plan["implementation_order"] = [f"Step: {s}" for s in steps[:8]]

    plan["domain_knowledge"] = {
        "applied": True,
        "concept_id": classification.concept_id,
        "concept_name": classification.concept_name,
        "concept_title": classification.concept_title,
        "domain": classification.domain,
        "domain_label": classification.domain_label,
        "feature_type": classification.feature_type,
        "concept_confidence": classification.concept_confidence,
        "repo_mapping_confidence": classification.repo_mapping_confidence,
        "architecture_pattern": classification.architecture_pattern,
        "concept_understanding": concept_understanding_text(classification),
        "why_this_matters": why_this_matters_text(classification),
        "knowledge_risks": k_risks,
        "file_roles": {
            "must_inspect": roles.must_inspect,
            "likely_modify": roles.likely_modify,
            "verify_only": roles.verify_only,
            "do_not_touch": roles.do_not_touch,
        },
        "integration_note": roles.integration_note,
        "dedicated_module_found": roles.dedicated_module_found,
        "unknowns": classification.unknowns,
        "related_concepts": list(concept.get("related_concepts", ())),
    }


def enrich_investigation_plan(
    plan: Dict[str, Any],
    classification: ConceptClassification,
    roles: RepoFileRoles,
) -> None:
    """Mutate investigation plan with domain knowledge (Part D)."""
    if not classification.concept_id:
        plan["domain_knowledge"] = {"applied": False}
        return

    notes = domain_investigation_notes(classification)
    existing = plan.get("verification_checklist") or []
    for n in notes:
        if n not in existing:
            existing.append(n)
    plan["verification_checklist"] = existing[:12]

    if roles.must_inspect:
        plan["inspect_first"] = roles.must_inspect[:5]
        plan["suggested_files_to_inspect"] = roles.must_inspect[:8]
        plan["likely_modules"] = list(
            dict.fromkeys(roles.must_inspect + (plan.get("likely_modules") or []))
        )[:10]

    why = plan.get("why") or ""
    dk_why = why_this_matters_text(classification)
    if dk_why:
        plan["why"] = f"{why} {dk_why}".strip()

    concept = CONCEPTS[classification.concept_id]
    bugs = concept.get("common_bugs", ())
    if bugs:
        plan["logical_hypothesis"] = bugs[0]
        if len(bugs) > 1:
            plan["domain_failure_modes"] = list(bugs)

    plan["domain_knowledge"] = {
        "applied": True,
        "concept_id": classification.concept_id,
        "concept_name": classification.concept_name,
        "concept_title": classification.concept_title,
        "domain": classification.domain,
        "domain_label": classification.domain_label,
        "feature_type": classification.feature_type,
        "concept_confidence": classification.concept_confidence,
        "repo_mapping_confidence": classification.repo_mapping_confidence,
        "concept_understanding": concept_understanding_text(classification),
        "why_this_matters": why_this_matters_text(classification),
        "domain_failure_modes": list(bugs)[:8],
        "file_roles": {
            "must_inspect": roles.must_inspect,
            "likely_modify": roles.likely_modify,
            "verify_only": roles.verify_only,
        },
        "integration_note": roles.integration_note,
        "unknowns": classification.unknowns,
    }
