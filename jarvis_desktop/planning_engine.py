"""Phase 120 — Change planner and symptom investigation (local, evidence-grounded).

Planning only — no code generation, no autonomous edits. All file paths must exist
in the scanned repository index or production graph.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from . import domain_knowledge as dk
from .evidence_engine import (
    EvidenceStore,
    analyze_concept,
    analyze_investigation,
    apply_to_build_plan,
    apply_to_investigation_plan,
)
from .evidence_engine.evidence_builder import merge_file_roles_with_evidence, apply_impact_precision

# Feature intents → search terms for path/module matching (deterministic heuristics).
_FEATURE_SPECS: Dict[str, Dict[str, Any]] = {
    "authentication": {
        "triggers": ("auth", "authentication", "login", "sign in", "signup", "jwt", "oauth", "session"),
        "search": ("auth", "login", "session", "user", "identity", "oauth", "jwt", "password"),
        "risks": ("Security boundaries for sessions and credentials must stay consistent across entry points.",),
    },
    "billing": {
        "triggers": ("stripe", "billing", "payment", "subscription", "checkout"),
        "search": ("stripe", "billing", "payment", "subscription", "checkout", "invoice"),
        "risks": ("Payment webhooks and idempotency are common failure points.",),
    },
    "caching": {
        "triggers": ("cache", "caching", "redis", "memcached"),
        "search": ("cache", "redis", "memcached", "lru"),
        "risks": ("Cache invalidation and stale reads affect correctness.",),
    },
    "audit_logging": {
        "triggers": ("audit", "audit log", "logging", "telemetry"),
        "search": ("audit", "log", "logger", "telemetry", "trace"),
        "risks": ("Logging volume and PII redaction need review.",),
    },
    "dark_mode": {
        "triggers": ("dark mode", "theme", "theming"),
        "search": ("theme", "dark", "css", "style", "ui"),
        "risks": ("UI tokens and component libraries may need coordinated updates.",),
    },
    "websocket": {
        "triggers": ("websocket", "websockets", "real-time", "realtime"),
        "search": ("websocket", "ws", "socket", "realtime", "stream"),
        "risks": ("Connection lifecycle and backpressure affect reliability.",),
    },
    "redis": {
        "triggers": ("redis",),
        "search": ("redis", "queue", "broker", "celery"),
        "risks": ("Connection pooling and key naming conventions matter at scale.",),
    },
    "rate_limiting": {
        "triggers": ("rate limit", "rate limiting", "ratelimit", "throttle", "throttling", "429"),
        "search": ("rate", "limit", "throttle", "middleware", "api", "http", "gateway"),
        "risks": ("Rate limits must apply consistently across HTTP and websocket entry points.",),
    },
}

_SYMPTOM_SPECS: Dict[str, Dict[str, Any]] = {
    "paper_trading": {
        "triggers": (
            "backtest",
            "paper trad",
            "live trad",
            "better than",
            "worse than",
            "simulation",
            "paper vs",
        ),
        "search": ("backtest", "paper", "live", "trade", "broker", "execution", "sim"),
        "why": "Symptoms comparing backtest vs live/paper often involve execution, slippage, or data-feed paths.",
        "hypotheses": (
            {
                "title": "Execution/fill modeling differs between backtest and live",
                "why": "Backtest assumes idealized fills; live/paper applies slippage, latency, and partial fills.",
                "keywords": ("execution", "fill", "slippage", "order", "broker"),
                "should_be_true": "Backtest and live use the same fill price source and slippage model for the same bar.",
                "disprove": "Log the fill price + timestamp for one trade in both modes; if identical, this is not the cause.",
            },
            {
                "title": "Data feed / bar timing mismatch (look-ahead bias)",
                "why": "Backtests often see the closed bar instantly; live sees forming bars, causing look-ahead in backtest.",
                "keywords": ("data", "feed", "bar", "candle", "ohlc", "market"),
                "should_be_true": "Signals fire on the same closed-bar timestamp in both modes.",
                "disprove": "Compare the timestamp a signal evaluates against the bar close time; equal ⇒ no look-ahead.",
            },
            {
                "title": "Fees/commission applied inconsistently",
                "why": "Backtest may omit or flat-rate fees that live applies per-fill.",
                "keywords": ("fee", "commission", "cost"),
                "should_be_true": "Per-trade fee in backtest equals the broker's fee schedule used live.",
                "disprove": "Sum fees over a fixed trade set in both modes; equal totals ⇒ not the cause.",
            },
        ),
    },
    "delayed_alerts": {
        "triggers": ("telegram", "alert", "delayed", "delay", "notification", "notify"),
        "search": ("telegram", "alert", "notify", "message", "webhook", "queue", "scheduler"),
        "why": "Alert delays usually trace through messaging integrations, queues, or schedulers.",
        "hypotheses": (
            {
                "title": "Alerts are queued and worker lag delays delivery",
                "why": "If alerts enqueue to a background worker, queue backlog adds latency before send.",
                "keywords": ("queue", "worker", "celery", "task", "scheduler", "job"),
                "should_be_true": "Queue depth stays near zero and enqueue→send time is sub-second.",
                "disprove": "Measure enqueue timestamp vs send timestamp; small gap ⇒ delay is elsewhere.",
            },
            {
                "title": "Synchronous network call to the messaging API blocks",
                "why": "A slow/blocking Telegram/webhook HTTP call in the request path stalls delivery.",
                "keywords": ("telegram", "webhook", "http", "client", "send", "notify"),
                "should_be_true": "The send call has a timeout and runs off the critical path.",
                "disprove": "Time the send() call in isolation; if fast, blocking is not the cause.",
            },
            {
                "title": "Scheduler/cron interval batches alerts",
                "why": "A periodic poll loop only checks every N seconds/minutes, adding fixed delay.",
                "keywords": ("scheduler", "cron", "interval", "poll", "loop", "tick"),
                "should_be_true": "Alert evaluation runs event-driven, not on a coarse polling interval.",
                "disprove": "Inspect the loop interval; if << observed delay, scheduling is not the cause.",
            },
        ),
    },
    "memory_growth": {
        "triggers": ("memory", "leak", "increasing", "oom", "out of memory"),
        "search": ("cache", "pool", "worker", "stream", "buffer", "session", "loop"),
        "why": "Growing memory often ties to caches, long-lived workers, or unreleased handles.",
        "hypotheses": (
            {
                "title": "Unbounded cache or accumulating collection",
                "why": "A dict/list/cache that only grows (no eviction or TTL) leaks under steady load.",
                "keywords": ("cache", "store", "registry", "buffer", "history", "map"),
                "should_be_true": "Every long-lived collection has a max size, TTL, or eviction policy.",
                "disprove": "Snapshot collection sizes over time; flat sizes ⇒ not this cache.",
            },
            {
                "title": "Unreleased resources / handles in a long-lived worker",
                "why": "Connections, file handles, or subscriptions opened per-iteration and never closed.",
                "keywords": ("worker", "pool", "connection", "session", "client", "stream"),
                "should_be_true": "Resources are closed in finally/`with` and pools are reused, not recreated.",
                "disprove": "Count open handles/connections over time; stable count ⇒ not handle leak.",
            },
        ),
    },
    "dashboard_mismatch": {
        "triggers": ("dashboard", "numbers wrong", "metric", "display", "report wrong"),
        "search": ("dashboard", "metric", "report", "aggregate", "stats", "ui", "view"),
        "why": "Wrong dashboard values often come from aggregation, caching, or UI binding layers.",
        "hypotheses": (
            {
                "title": "Aggregation/rollup computes the wrong value",
                "why": "Sum/avg/group-by logic in the aggregation layer diverges from the raw source.",
                "keywords": ("aggregate", "rollup", "sum", "stats", "metric", "report"),
                "should_be_true": "Re-deriving the metric from raw rows matches the dashboard value.",
                "disprove": "Manually compute the metric from the source table; match ⇒ aggregation is correct.",
            },
            {
                "title": "Stale cache serving outdated values",
                "why": "A cached metric isn't invalidated when the underlying data changes.",
                "keywords": ("cache", "redis", "memo", "ttl"),
                "should_be_true": "Cache is invalidated on every relevant write or has a short TTL.",
                "disprove": "Bypass the cache and re-query; same value ⇒ cache is not stale.",
            },
            {
                "title": "UI binding formats/maps the wrong field",
                "why": "The display layer reads the wrong key or applies wrong formatting/units.",
                "keywords": ("ui", "view", "dashboard", "component", "render", "template"),
                "should_be_true": "The API response value equals what the widget renders.",
                "disprove": "Compare the raw API payload to the rendered number; equal ⇒ UI binding is fine.",
            },
        ),
    },
    "duplicate_events": {
        "triggers": (
            "duplicate event",
            "duplicate events",
            "events fired",
            "event fired",
            "fired twice",
            "double fire",
            "double emit",
        ),
        "search": ("event", "dispatch", "listener", "emit", "bus", "handler", "hub", "ring"),
        "why": "Duplicate event delivery usually involves dispatchers, listeners, or handlers firing more than once.",
        "hypotheses": (
            {
                "title": "Event handler registered twice",
                "why": "Startup or hot-reload can attach the same listener twice so one event runs two handlers.",
                "keywords": ("listener", "handler", "register", "subscribe", "dispatch"),
                "should_be_true": "Each event type has at most one active handler registration per process.",
                "disprove": "Log handler registration count at startup; if one per event, look elsewhere.",
            },
            {
                "title": "Dispatcher retries or fan-out without deduplication",
                "why": "A bus may emit to all subscribers and also retry, producing duplicate side effects.",
                "keywords": ("dispatch", "bus", "emit", "publish", "fan"),
                "should_be_true": "Each logical event id is processed at-most-once downstream.",
                "disprove": "Trace one event id through the bus; single downstream receipt disproves fan-out duplication.",
            },
        ),
    },
    "position_close": {
        "triggers": ("position close", "closes fail", "close order", "exit position"),
        "search": ("position", "close", "order", "execution", "trade", "risk"),
        "why": "Intermittent close failures often involve order routing, state machines, or broker adapters.",
        "verify": (
            "Reproduce with a single symbol and capture order lifecycle logs.",
            "Compare close path vs open path (same adapter, different state transitions).",
        ),
        "risk_if_fixed": "Overly aggressive retries could duplicate closes or violate risk limits.",
        "hypotheses": (
            {
                "title": "Order state machine rejects close in certain states",
                "why": "Close is only valid from specific states; a race leaves the order in a state that rejects close.",
                "keywords": ("state", "order", "position", "status", "lifecycle"),
                "should_be_true": "Close is permitted from every state the position can legitimately reach.",
                "disprove": "Log the order state at each failed close; if always the same legal state, look elsewhere.",
            },
            {
                "title": "Partial-fill handling leaves residual quantity",
                "why": "A partial fill on close leaves an unclosed remainder that looks like a failure.",
                "keywords": ("fill", "partial", "quantity", "qty", "execution"),
                "should_be_true": "Close quantity equals current open quantity including prior partial fills.",
                "disprove": "Compare requested close qty vs open qty; equal ⇒ not a partial-fill remainder.",
            },
            {
                "title": "Broker/venue adapter rejects or times out",
                "why": "Venue-specific rules (min size, market hours) or timeouts reject the close request.",
                "keywords": ("broker", "adapter", "venue", "client", "api"),
                "should_be_true": "The adapter returns success and an exchange order id for the close.",
                "disprove": "Inspect the adapter response for the failing close; success ⇒ rejection is upstream.",
            },
        ),
    },
    "dashboard_pnl": {
        "triggers": ("pnl", "profit and loss", "dashboard pnl", "wrong pnl", "pnl is wrong"),
        "search": ("pnl", "profit", "loss", "equity", "balance", "dashboard", "metric", "portfolio"),
        "why": "PnL mismatches often come from position accounting, mark-to-market sources, or UI aggregation.",
        "verify": (
            "Trace PnL from raw fills → position ledger → API → dashboard widget.",
            "Compare paper/live vs backtest PnL components on the same date range.",
        ),
        "risk_if_fixed": "Fixing display-only bugs can hide real accounting errors; verify ledger first.",
        "hypotheses": (
            {
                "title": "Stale or wrong mark-to-market price source",
                "why": "Unrealized PnL uses a stale/last price instead of the current market mark.",
                "keywords": ("mark", "price", "quote", "market", "value", "pnl"),
                "should_be_true": "Unrealized PnL recomputes correctly when marked to the latest price.",
                "disprove": "Recompute PnL with a known price; match ⇒ mark source is correct.",
            },
            {
                "title": "Double-counted or missed fills in the position ledger",
                "why": "Fills applied twice (retry/replay) or dropped corrupt realized PnL.",
                "keywords": ("fill", "ledger", "position", "trade", "accounting"),
                "should_be_true": "Ledger fill count equals the broker's fill count for the period.",
                "disprove": "Reconcile ledger fills vs broker statement; equal ⇒ no double-count.",
            },
            {
                "title": "Fee/slippage treated differently per layer",
                "why": "Realized PnL net of fees in one layer, gross in another.",
                "keywords": ("fee", "commission", "slippage", "net", "gross"),
                "should_be_true": "Every layer agrees on net-vs-gross and the same fee schedule.",
                "disprove": "Diff PnL with fees forced to zero in both layers; equal deltas ⇒ fees consistent.",
            },
        ),
    },
    "stop_loss": {
        "triggers": ("stop loss", "stop-loss", "stopped out", "unexpected stop", "stop triggered", "sl hit"),
        "search": ("stop", "loss", "risk", "trigger", "order", "price", "trail"),
        "why": "Unexpected stops usually involve trigger price comparison, tick/wick handling, or trailing logic.",
        "verify": (
            "Capture the trigger price, comparison operator, and the bar/tick that fired it.",
            "Replay the same price series through the stop check in isolation.",
        ),
        "risk_if_fixed": "Loosening stop logic can remove protection and increase downside risk.",
        "hypotheses": (
            {
                "title": "Stop compares against wick/intrabar price, not close",
                "why": "Using high/low (or live tick) instead of close fires stops on transient spikes.",
                "keywords": ("stop", "trigger", "price", "tick", "high", "low", "bar"),
                "should_be_true": "Stop fires only when the intended price field crosses the level.",
                "disprove": "Log the price field used at trigger; if it's the intended one, look elsewhere.",
            },
            {
                "title": "Trailing-stop level updated incorrectly",
                "why": "A trailing stop ratchets the wrong way or recomputes from a stale reference.",
                "keywords": ("trail", "stop", "level", "update", "high", "peak"),
                "should_be_true": "Trailing level only moves in the favorable direction from the running extreme.",
                "disprove": "Replay prices and assert the stop level is monotonic; if so, not the cause.",
            },
            {
                "title": "Comparison operator / rounding off-by-a-tick",
                "why": ">= vs > or float rounding fires the stop one tick early.",
                "keywords": ("compare", "round", "price", "level", "stop"),
                "should_be_true": "The boundary price does not trigger unless it truly breaches the level.",
                "disprove": "Unit-test the boundary price exactly at the level; no trigger ⇒ operator is fine.",
            },
        ),
    },
    "position_sizing": {
        "triggers": ("position siz", "sizing", "lot size", "quantity wrong", "wrong size", "size mismatch", "risk per trade"),
        "search": ("size", "sizing", "position", "risk", "allocation", "quantity", "qty", "capital"),
        "why": "Sizing mismatches involve the risk formula, rounding/lot constraints, or the capital/balance input.",
        "verify": (
            "Recompute size by hand from the documented formula and inputs.",
            "Log every input (balance, risk %, price, stop distance) at the sizing call.",
        ),
        "risk_if_fixed": "Increasing size to 'match expectation' can breach risk limits — verify the formula is the bug.",
        "hypotheses": (
            {
                "title": "Risk formula uses wrong input (balance vs equity vs free margin)",
                "why": "Sizing off the wrong capital base scales every position incorrectly.",
                "keywords": ("balance", "equity", "capital", "margin", "size", "risk"),
                "should_be_true": "The capital input matches the documented basis for the risk model.",
                "disprove": "Log the capital value used; if it matches the intended basis, look elsewhere.",
            },
            {
                "title": "Rounding to lot/contract size distorts small positions",
                "why": "Rounding to min lot or step size changes the effective risk, especially for small accounts.",
                "keywords": ("lot", "round", "step", "min", "contract", "quantity"),
                "should_be_true": "Rounded size stays within tolerance of the unrounded target.",
                "disprove": "Compare unrounded vs rounded size; small delta ⇒ rounding is not the cause.",
            },
            {
                "title": "Stop distance / pip value miscomputed in the formula",
                "why": "Risk-based sizing divides by stop distance; a wrong unit (pips vs price) blows up size.",
                "keywords": ("stop", "distance", "pip", "tick", "value", "size"),
                "should_be_true": "size = risk_amount / (stop_distance × value_per_unit) holds with correct units.",
                "disprove": "Plug the logged inputs into the formula by hand; match ⇒ formula is correct.",
            },
        ),
    },
    "signal_not_triggering": {
        "triggers": ("signal not", "no signal", "signal isn't", "not triggering", "never fires", "entry not", "strategy not firing"),
        "search": ("signal", "strategy", "indicator", "condition", "entry", "rule", "trigger"),
        "why": "Missing signals trace to the condition logic, the indicator inputs, or the data window feeding them.",
        "verify": (
            "Log the boolean value of each signal condition on the bar where you expected a fire.",
            "Confirm indicators have enough warm-up data and are not NaN.",
        ),
        "risk_if_fixed": "Loosening conditions to force signals can create false positives and overtrading.",
        "hypotheses": (
            {
                "title": "A condition in the AND-chain is never satisfied",
                "why": "Compound entry conditions mean one always-false clause suppresses all signals.",
                "keywords": ("condition", "signal", "rule", "entry", "filter"),
                "should_be_true": "Each individual condition is true at least sometimes on the test data.",
                "disprove": "Log each clause separately; if all true on the expected bar, logic is fine.",
            },
            {
                "title": "Indicator warm-up / NaN suppresses early signals",
                "why": "Indicators need N bars; until then values are NaN and conditions silently fail.",
                "keywords": ("indicator", "window", "period", "warmup", "ma", "rsi", "ema"),
                "should_be_true": "Enough history is loaded before signal evaluation starts.",
                "disprove": "Check indicator values are non-NaN on the expected bar; if valid, not warm-up.",
            },
            {
                "title": "Wrong data timeframe / window feeding the signal",
                "why": "Signal evaluated on a different timeframe or a window that excludes the move.",
                "keywords": ("data", "timeframe", "window", "bar", "resample", "feed"),
                "should_be_true": "The signal sees the same bars/timeframe you observed the setup on.",
                "disprove": "Print the bars the signal evaluated; if they include the setup, data is fine.",
            },
        ),
    },
    "graph_module_count": {
        "triggers": (
            "module count",
            "wrong module",
            "scan graph",
            "graph shows wrong",
            "atlas graph",
            "repository map",
        ),
        "search": ("graph", "scan", "module", "index", "universe", "import", "dependency"),
        "why": "Graph/module count issues usually involve scan scope, production filters, or overview vs module view.",
        "verify": (
            "Confirm scan scope (entire repo vs folder) and production filter settings.",
            "Switch to Module Graph and compare visible count to summary module_count.",
        ),
        "risk_if_fixed": "Forcing full module graph on huge repos may degrade performance — use hierarchy when appropriate.",
        "hypotheses": (
            {
                "title": "Subsystem/overview view shown instead of module view",
                "why": "The overview collapses modules into subsystem nodes, so the visible count is far lower.",
                "keywords": ("graph", "view", "subsystem", "overview", "universe"),
                "should_be_true": "Module-graph node count equals summary.module_count.",
                "disprove": "Switch to Module Graph and compare counts; equal ⇒ it was just the view.",
            },
            {
                "title": "Scan scope or production filter excluded files",
                "why": "Folder scope or production-only filters drop tests/vendored code from the count.",
                "keywords": ("scan", "scope", "filter", "index", "production"),
                "should_be_true": "Counted files match the configured scope and filter.",
                "disprove": "Re-scan with entire-repo scope; if count matches expectation, scope was the cause.",
            },
        ),
    },
}


def _path_symbols(path: str) -> List[str]:
    """Best-effort symbols from a file path (no AST — avoids hallucinated class names)."""
    base = (path or "").replace("\\", "/").split("/")[-1]
    if "." in base:
        stem = base.rsplit(".", 1)[0]
    else:
        stem = base
    out: List[str] = []
    if stem and stem not in {"__init__", "index", "main"}:
        out.append(stem)
    return out


def _risk_level_from_fan_in(fan_in: int, risk_score: float) -> str:
    if fan_in >= 25 or risk_score >= 60:
        return "high"
    if fan_in >= 6 or risk_score >= 35:
        return "medium"
    return "low"


def _implementation_order(paths: List[str], graph: Optional[Dict[str, Any]]) -> List[str]:
    """Leaf-ish modules first (lower fan-in), then hubs — static heuristic only."""
    if not paths or not graph:
        return list(paths)
    nodes = {n.get("path"): n for n in _production_modules(graph)}
    ordered = sorted(
        paths,
        key=lambda p: (int((nodes.get(p) or {}).get("fan_in", 0) or 0), p),
    )
    return ordered


def _files_likely_to_break(inbound_paths: List[str], risks_map: Dict[str, Dict[str, Any]]) -> List[str]:
    scored: List[Tuple[int, str]] = []
    for path in inbound_paths:
        row = risks_map.get(path) or {}
        fan = int(row.get("fan_in", 0) or 0)
        scored.append((fan + int(row.get("total_score", 0) or 0), path))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [p for _, p in scored[:10]]


def _subsystem_of(path: str) -> str:
    normalized = (path or "").replace("\\", "/")
    return normalized.split("/")[0] if "/" in normalized else "(root)"


def _tokenize(text: str) -> Set[str]:
    return {t for t in re.findall(r"[a-z][a-z0-9_]{2,}", (text or "").lower())}


def _detect_intent(text: str, specs: Dict[str, Dict[str, Any]]) -> Tuple[str, Set[str]]:
    lower = (text or "").lower()
    for name, spec in specs.items():
        if any(trigger in lower for trigger in spec["triggers"]):
            return name, set(spec["search"])
    return "general", _tokenize(text)


def _production_modules(graph: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not graph:
        return []
    return [n for n in graph.get("nodes", []) if n.get("type") == "module" and n.get("path")]


# Phase 133 — real-repo hardening. Runtime/system symptoms must never localize to
# config/dotfiles/lockfiles/docs. These markers identify non-runtime files.
_CONFIG_PATH_MARKERS = (
    ".prettierrc", ".prettierignore", ".eslintrc", "eslint.config", ".editorconfig",
    "package.json", "package-lock.json", "yarn.lock", "pnpm-lock", "pyproject.toml",
    "setup.cfg", "setup.py", "tox.ini", "mypy.ini", ".flake8", ".pre-commit",
    ".gitignore", ".gitattributes", ".dockerignore", "dockerfile", "requirements",
    ".github/", "/docs/", "/.vscode/", "/.devcontainer/", ".md", ".rst", ".txt",
    ".cfg", ".lock", ".toml", "/script/", "/scripts/",
)

# Runtime/system symptom hints — when present, config/dotfiles are penalized hard.
_RUNTIME_SYMPTOM_HINTS = (
    "duplicate", "event", "websocket", "disconnect", "memory", "leak", "slow",
    "loading", "trigger", "twice", "auth", "session", "cache", "database",
    "deadlock", "timeout", "race", "hang", "crash", "fire", "listener", "dispatch",
    "integration", "automation", "recorder", "state", "fail", "error", "exception",
)

# Symptom keyword groups -> (path-substring, boost) so concept symptoms land on the
# right architecture files even when the path doesn't literally contain the keyword.
_RUNTIME_BOOSTS: Tuple[Tuple[Tuple[str, ...], Tuple[Tuple[str, float], ...]], ...] = (
    (("duplicate", "event", "fire", "listener", "dispatch", "emit", "fired"),
     (("/core.py", 9), ("/helpers/event.py", 9), ("/helpers/dispatcher.py", 8),
      ("eventbus", 9), ("components/automation", 6), ("/helpers/trigger", 6),
      ("core/hub", 10), ("/ring/", 8), ("hub.py", 9))),
    (("websocket", "disconnect", " ws ", "socket"),
     (("websocket_api", 10), ("/http/", 4), ("/auth/", 4), ("/components/api", 5))),
    (("integration", "setup", "config entry", "config_entry", "loading"),
     (("config_entries.py", 9), ("/loader.py", 8), ("/setup.py", 7), ("/bootstrap.py", 5))),
    (("auth", "session", "login", "token", "jwt"),
     (("/auth/", 9), ("auth_store", 7), ("auth_provider", 7))),
    (("recorder", "database", " db ", "sql", "sqlite", "postgres"),
     (("components/recorder", 10), ("/db.py", 6))),
    (("automation", "trigger twice"),
     (("components/automation", 9), ("/helpers/trigger", 7), ("/helpers/script", 6))),
)


# Build-request concept boosts — distributed tracing / rate limiting etc. must land
# on request lifecycle / API / websocket / logging boundaries, not random async files.
_BUILD_BOOSTS: Tuple[Tuple[Tuple[str, ...], Tuple[Tuple[str, float], ...]], ...] = (
    (("tracing", "trace", "observability", "telemetry", "instrument"),
     (("/http/", 8), ("websocket_api", 8), ("/helpers/event.py", 6), ("/middleware", 8),
      ("/core.py", 6), ("logging", 7), ("/setup.py", 4), ("config_entries.py", 4))),
    (("rate limit", "rate-limit", "ratelimit", "throttle", "throttling"),
     (("/http/", 9), ("websocket_api", 9), ("/auth/", 7), ("/api.py", 7),
      ("/components/api", 7), ("/helpers/aiohttp", 5))),
    (("cache", "caching"),
     (("/helpers/storage.py", 7), ("components/recorder", 5), ("/core.py", 4))),
    (("websocket", "ws api"),
     (("websocket_api", 10), ("/http/", 5))),
    (("auth", "authentication", "login"),
     (("/auth/", 9), ("auth_store", 6), ("auth_provider", 6))),
)


def _build_boosts_for_text(text: str) -> List[Tuple[str, float]]:
    low = (text or "").lower()
    out: List[Tuple[str, float]] = []
    for triggers, boosts in _BUILD_BOOSTS:
        if any(t in low for t in triggers):
            out.extend(boosts)
    return out


def _is_runtime_symptom(text: str) -> bool:
    low = (text or "").lower()
    return any(h in low for h in _RUNTIME_SYMPTOM_HINTS)


def _is_config_path(path: str) -> bool:
    p = (path or "").lower().replace("\\", "/")
    return any(m in p for m in _CONFIG_PATH_MARKERS)


_TRADING_SYMPTOM_MARKERS = (
    "backtest", "paper trad", "live trad", "slippage", "fill", "broker",
    "indicator", " moving average", " order book", "execution parity",
)


def _symptom_mentions_trading(text: str) -> bool:
    low = (text or "").lower()
    return any(m in low for m in _TRADING_SYMPTOM_MARKERS) or re.search(r"\bema\b", low) is not None


def _coerce_investigation_classification(symptom: str, classification: Any) -> Any:
    """Block spurious trading/indicator concepts on event-bus style symptoms."""
    low = (symptom or "").lower()
    if "duplicate" in low and "event" in low and "order" not in low:
        rec = dk.get_engine().get("pub_sub")
        if rec:
            return dk.ConceptClassification(
                concept_id="pub_sub",
                concept_name=rec.name,
                concept_title=rec.title or rec.name,
                domain=rec.domain,
                domain_label=dk.get_engine().domain_label(rec.domain),
                feature_type=rec.feature_type or rec.category,
                concept_confidence="high",
                repo_mapping_confidence="low",
                unknowns=[],
                architecture_pattern="event → dispatcher/listener → handlers",
                record=rec,
            )
    if classification.record and classification.record.domain == "trading":
        if not _symptom_mentions_trading(symptom):
            return dk.ConceptClassification(
                concept_id=None,
                concept_name="",
                concept_title="",
                domain="",
                domain_label="",
                feature_type="general",
                concept_confidence="low",
                repo_mapping_confidence="low",
                unknowns=list(classification.unknowns)
                + ["Trading concept suppressed — symptom lacks trading/backtest terms."],
            )
    return classification


def _boosts_for_text(text: str) -> List[Tuple[str, float]]:
    low = (text or "").lower()
    out: List[Tuple[str, float]] = []
    for triggers, boosts in _RUNTIME_BOOSTS:
        if any(t in low for t in triggers):
            out.extend(boosts)
    return out


def _score_modules(
    modules: List[Dict[str, Any]],
    terms: Set[str],
    risks_by_path: Dict[str, Dict[str, Any]],
    *,
    runtime: bool = False,
    boosts: Optional[List[Tuple[str, float]]] = None,
    symptom_text: str = "",
) -> List[Tuple[float, Dict[str, Any]]]:
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for node in modules:
        path = node.get("path") or ""
        p = path.lower().replace("\\", "/")
        # Severe penalty: runtime/system symptoms never localize to config/dotfiles.
        if runtime and _is_config_path(p):
            continue
        score = 0.0
        for term in terms:
            if term in p:
                score += 3.0
        for kw, amount in (boosts or ()):
            if kw.lower() in p:
                score += amount
        risk = risks_by_path.get(path) or {}
        score += min(5.0, float(risk.get("total_score", 0) or 0) / 20.0)
        score += min(3.0, float(node.get("fan_in", 0) or 0) / 10.0)
        if runtime and not _symptom_mentions_trading(symptom_text):
            if any(tok in p for tok in ("trading", "backtest", "paper", "broker", "/indicator", "ema")):
                score -= 8.0
        if score > 0:
            scored.append((score, node))
    scored.sort(key=lambda item: (-item[0], item[1].get("path", "")))
    return scored


def _risks_map(risks: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for row in (risks or {}).get("ranked_modules", []) or []:
        path = row.get("path")
        if path:
            out[path] = row
    return out


def _graph_neighbors(graph: Dict[str, Any], module_ids: Set[str]) -> Tuple[List[str], List[str]]:
    """Return (outbound deps, inbound importers) as dotted/path labels from real edges."""
    nodes = {n["id"]: n for n in _production_modules(graph)}
    outbound: Set[str] = set()
    inbound: Set[str] = set()
    for edge in graph.get("edges", []):
        if edge.get("type") != "imports" or not edge.get("resolved"):
            continue
        src, dst = edge.get("from"), edge.get("to")
        if src in module_ids:
            dst_node = nodes.get(dst)
            if dst_node:
                outbound.add(dst_node.get("path") or dst)
        if dst in module_ids:
            src_node = nodes.get(src)
            if src_node:
                inbound.add(src_node.get("path") or src)
    return sorted(outbound)[:12], sorted(inbound)[:12]


def _estimate_size(module_count: int) -> str:
    if module_count <= 5:
        return "Small"
    if module_count <= 20:
        return "Medium"
    return "Large"


def _confidence_label(score_count: int, top_score: float, intent: str) -> str:
    if intent != "general" and score_count >= 2 and top_score >= 4:
        return "medium-high"
    if score_count >= 1 and top_score >= 3:
        return "medium"
    if score_count >= 1:
        return "low-medium"
    return "low"


def _repository_evidence_bundle(
    ctx: Dict[str, Any],
    classification: Any,
    *,
    heuristic_paths: Optional[List[str]] = None,
    intent: str = "",
    goal: str = "",
) -> Optional[Tuple[Any, Any]]:
    raw = ctx.get("evidence_store") or {}
    if not raw:
        return None
    store = EvidenceStore.from_dict(raw)
    rec = classification.record
    concept_id = classification.concept_id or ""
    gl = (goal or "").lower()
    if "indicator" in gl and ("pipeline" in gl or "signal" in gl):
        concept_id = "ema"
    elif "idempotency" in gl or "idempotent" in gl:
        concept_id = "idempotency_key"
    elif "health check" in gl or "health endpoint" in gl:
        concept_id = "health_check"
    elif "slippage" in gl:
        concept_id = "slippage_model"
    elif "circuit breaker" in gl:
        concept_id = "circuit_breaker"
    elif "rate limit" in gl:
        concept_id = "rate_limiting"
    elif "ema" in gl or "moving average" in gl:
        concept_id = "ema"
    if not concept_id and intent:
        intent_map = {
            "authentication": "authentication",
            "billing": "stripe_billing",
            "logging": "structured_logging",
            "redis": "redis_cache",
            "caching": "redis_cache",
        }
        concept_id = intent_map.get(intent, "")
    if not concept_id:
        if "health check" in gl or "health endpoint" in gl:
            concept_id = "health_check"
        elif "idempotency" in gl or "idempotent" in gl:
            concept_id = "idempotency_key"
        elif "slippage" in gl:
            concept_id = "slippage_model"
        elif "circuit breaker" in gl:
            concept_id = "circuit_breaker"
        elif "rate limit" in gl:
            concept_id = "rate_limiting"
        elif "ema" in gl or "moving average" in gl:
            concept_id = "ema"
    if not concept_id:
        return None
    rec_name = rec.name if rec else concept_id.replace("_", " ").title()
    rec_category = rec.category if rec else ""
    rec_domain = rec.domain if rec else ""
    rec_keywords = list(rec.path_keywords) if rec else []
    if concept_id == "ema" and not any(k in rec_keywords for k in ("indicator", "signal", "registry")):
        rec_keywords.extend(["indicator", "signal", "registry", "pipeline"])
    if concept_id == "idempotency_key" and not any(k in rec_keywords for k in ("order", "execution")):
        rec_keywords.extend(["order", "execution", "trading"])
    return analyze_concept(
        store,
        concept_id=concept_id,
        concept_name=rec_name,
        category=rec_category,
        domain=rec_domain,
        path_keywords=rec_keywords,
        heuristic_paths=heuristic_paths,
        graph=ctx.get("graph"),
    )


def _investigation_evidence_bundle(
    ctx: Dict[str, Any],
    symptom: str,
    classification: Any,
    *,
    heuristic_paths: Optional[List[str]] = None,
) -> Optional[Tuple[Any, Any]]:
    raw = ctx.get("evidence_store") or {}
    if not raw:
        return None
    store = EvidenceStore.from_dict(raw)
    lower = (symptom or "").lower()
    if "duplicate" in lower and "event" in lower and "order" not in lower:
        return analyze_concept(
            store,
            concept_id="pub_sub",
            concept_name="Pub/Sub",
            category="messaging",
            domain="messaging",
            path_keywords=["event", "dispatch", "listener", "emit", "bus", "handler", "hub"],
            heuristic_paths=heuristic_paths,
            graph=ctx.get("graph"),
        )
    trading_symptom = any(k in lower for k in ("backtest", "paper", "live", "slippage", "fill"))
    indicator_symptom = "indicator" in lower and trading_symptom
    if indicator_symptom:
        return analyze_investigation(
            store,
            concept_id="indicator_backtest_live",
            symptom=symptom,
            heuristic_paths=heuristic_paths,
            graph=ctx.get("graph"),
        )
    if "duplicate" in lower and "order" in lower:
        return analyze_concept(
            store,
            concept_id="idempotency_key",
            concept_name="Idempotency",
            category="reliability",
            domain="backend",
            path_keywords=["order", "execution", "idempotency"],
            heuristic_paths=heuristic_paths,
            graph=ctx.get("graph"),
        )
    if classification.concept_id in ("backtest_live_divergence", "indicator_backtest_live") or trading_symptom:
        return analyze_investigation(
            store,
            concept_id=classification.concept_id or "backtest_live_divergence",
            symptom=symptom,
            heuristic_paths=heuristic_paths,
            graph=ctx.get("graph"),
        )
    rec = classification.record
    if rec:
        return analyze_concept(
            store,
            concept_id=classification.concept_id,
            concept_name=rec.name,
            category=rec.category,
            domain=rec.domain,
            path_keywords=list(rec.path_keywords),
            heuristic_paths=heuristic_paths,
            graph=ctx.get("graph"),
        )
    return analyze_investigation(
        store,
        symptom=symptom,
        heuristic_paths=heuristic_paths,
        graph=ctx.get("graph"),
    )


def repository_context_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    scan = state.get("scan") or {}
    summary = state.get("summary") or {}
    return {
        "scan": scan,
        "graph": state.get("graph"),
        "index": state.get("index"),
        "risks": state.get("risks"),
        "evidence_store": state.get("evidence_store") or {},
        "repo_path": state.get("path") or scan.get("repo_path") or "",
        "repo_name": scan.get("repo_name") or summary.get("repo_name") or "repository",
        "entry_points": summary.get("entry_points") or scan.get("entry_points") or [],
        "subsystems": summary.get("subsystems") or [],
        "top_hubs": scan.get("top_hubs") or summary.get("top_hubs") or [],
        "explanation": summary.get("explanation") or "",
    }


def plan_change(request: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Build a grounded change plan from scanned repository state."""
    goal = (request or "").strip()
    if not goal:
        return {"ok": False, "error": "Describe what you want to add or change."}
    graph = ctx.get("graph")
    if not graph:
        return {"ok": False, "error": "No repository scanned yet."}

    build_class = dk.classify_request(goal, mode="build")
    intent, terms = _detect_intent(goal, _FEATURE_SPECS)
    spec = _FEATURE_SPECS.get(intent, {})
    extra_terms = set(spec.get("search", ())) | terms | dk.search_terms_for_classification(build_class)
    modules = _production_modules(graph)
    risks_map = _risks_map(ctx.get("risks"))
    scored = _score_modules(
        modules, extra_terms, risks_map, boosts=_build_boosts_for_text(goal)
    )

    matched_paths = [node["path"] for _, node in scored[:12]]
    matched_ids = {node["id"] for _, node in scored[:12]}
    subsystems = sorted({_subsystem_of(p) for p in matched_paths})
    outbound, inbound = _graph_neighbors(graph, matched_ids)

    entry_points = [ep for ep in (ctx.get("entry_points") or []) if any(ep.startswith(s) for s in subsystems)]
    if not entry_points:
        entry_points = list(ctx.get("entry_points") or [])[:5]

    arch_risks: List[str] = []
    for path in matched_paths[:6]:
        row = risks_map.get(path)
        if row:
            reasons = row.get("reasons") or []
            arch_risks.append(f"`{path}` (score {row.get('total_score', 0)}): {', '.join(reasons[:2]) or 'high fan-in / coupling'}")
    for note in spec.get("risks", ()):
        if note not in arch_risks:
            arch_risks.append(note)

    tests = _tests_for_change(matched_paths, subsystems)
    top_score = scored[0][0] if scored else 0.0
    confidence = _confidence_label(len(matched_paths), top_score, intent)
    limitations: List[str] = []
    if not matched_paths:
        limitations.append("No production modules matched this request by path keyword — inspect entry points and hubs manually.")
        limitations.append("Provide subsystem names, file paths, or a narrower feature description and re-run.")
    if intent == "general":
        limitations.append("Request did not match a known feature pattern; results are keyword-based only.")
    limitations.append("Static import graph only — runtime plugins and dynamic imports may be missing.")

    top_node = scored[0][1] if scored else {}
    risk_level = _risk_level_from_fan_in(
        int(top_node.get("fan_in", 0) or 0),
        float((risks_map.get(top_node.get("path", "")) or {}).get("total_score", 0) or 0),
    )
    likely_break = _files_likely_to_break(inbound, risks_map)
    verification_plan = [
        "Read files_to_inspect_first and confirm the change boundary matches the goal.",
        "Run tests_likely_affected before and after the change.",
        "Re-scan or refresh impact on the highest fan-in file you touch.",
    ]
    if likely_break:
        verification_plan.append(f"Smoke-test direct importers: {', '.join(likely_break[:3])}")

    plan = {
        "goal": goal,
        "intent": intent,
        "likely_affected_modules": matched_paths,
        "likely_affected_subsystems": subsystems,
        "affected_systems": subsystems,  # Phase 123 alias (senior-architect label)
        "entry_points": entry_points,
        "files_to_inspect_first": matched_paths[:8],
        "files_likely_to_change": matched_paths[:8],
        "files_likely_to_break": likely_break,
        "what_may_break": likely_break,  # Phase 123 alias
        "dependencies_involved": {
            "outbound_imports": outbound,
            "inbound_importers": inbound,
        },
        "architectural_risks": arch_risks[:10],
        "tests_likely_affected": tests,
        "tests_required": tests,  # Phase 123 alias
        "estimated_change_size": _estimate_size(len(matched_paths) or 1),
        "risk_level": risk_level,
        "implementation_order": _implementation_order(matched_paths[:12], graph),
        "verification_plan": verification_plan,
        "rollback_plan": _rollback_plan(intent, matched_paths, risk_level),
        "confidence": confidence,
        "evidence": _change_evidence(scored[:8], intent),
        "limitations": limitations,
    }
    roles = dk.map_concept_to_repository(build_class, modules, risks_map, scored_paths=matched_paths)
    evidence_result = _repository_evidence_bundle(
        ctx, build_class, heuristic_paths=matched_paths, intent=intent, goal=goal
    )
    if evidence_result:
        evidence_bundle, precision = evidence_result
        roles = merge_file_roles_with_evidence(roles, evidence_bundle, precision)
    dk.enrich_build_plan(plan, build_class, roles)
    if evidence_result:
        evidence_bundle, precision = evidence_result
        apply_to_build_plan(plan, evidence_bundle, precision)
        plan["heuristic_candidates"] = matched_paths
    if build_class.concept_id:
        limitations = list(plan.get("limitations") or [])
        limitations.extend(build_class.unknowns)
        plan["limitations"] = limitations

    # Phase 132 — if domain-knowledge enrichment replaced the recommendation with
    # evidence-store files (catalog modules, not this repo), restore ONLY the
    # repo modules whose path matches the intent's own keywords. This is precise
    # (no flooding) — it recovers e.g. `api/stripe_billing.py` for a billing
    # request without dropping the precision engine's curation.
    intent_kw = {k.lower() for k in (set(spec.get("search", ())) | set(terms)) if k}
    relevant = [p for p in matched_paths
                if any(k in p.lower() for k in intent_kw)]
    lam = list(plan.get("likely_affected_modules") or [])
    if relevant and not any(any(k in p.lower() for k in intent_kw) for p in lam):
        for f in relevant[:2]:
            if f not in lam:
                lam.append(f)
        plan["likely_affected_modules"] = lam

    # Disambiguate an explicit observability request that the catalog routes to
    # the narrower health_check concept (both concepts already exist).
    glow = goal.lower()
    dkb = plan.get("domain_knowledge")
    if isinstance(dkb, dict) and "observabilit" in glow and dkb.get("concept_id") == "health_check":
        dkb["concept_id"] = "observability"

    prompts = build_implementation_prompts(plan, ctx)
    return {
        "ok": True,
        "plan": plan,
        "prompts": prompts,
        "limitations": plan.get("limitations", limitations),
    }


def _rollback_plan(intent: str, paths: List[str], risk_level: str) -> List[str]:
    """Concrete rollback guidance for a planned change."""
    steps = [
        "Make the change on a feature branch; keep `main` deployable.",
        "Commit in small, revertible steps so any single commit can be `git revert`-ed cleanly.",
    ]
    if paths:
        steps.append(f"Before editing, note the current behavior of: {', '.join(paths[:3])}.")
    if intent in {"billing", "authentication", "redis", "caching"}:
        steps.append("Gate the new path behind a feature flag so it can be disabled without a deploy.")
    if intent == "billing":
        steps.append("For payment flows, verify in a sandbox/test-mode account before enabling live keys.")
    if risk_level == "high":
        steps.append("Plan a fast rollback: keep the previous release artifact and a one-command redeploy ready.")
    steps.append("Keep DB migrations backward-compatible (additive) so the old code still runs if you roll back.")
    return steps


def _change_evidence(scored: List[Tuple[float, Dict[str, Any]]], intent: str) -> List[str]:
    lines = [f"Matched feature intent: {intent}"]
    for score, node in scored[:5]:
        lines.append(
            f"Module `{node.get('path')}` — fan-in {node.get('fan_in', 0)}, risk {node.get('risk_score', 0)}, match score {score:.1f}"
        )
    if len(scored) > 5:
        lines.append(f"… and {len(scored) - 5} more scored modules (not listed).")
    return lines


def _tests_for_change(paths: List[str], subsystems: List[str]) -> List[str]:
    tests: List[str] = []
    for path in paths[:4]:
        base = path.split("/")[-1]
        stem = base.rsplit(".", 1)[0] if "." in base else base
        tests.append(f"Unit/integration tests covering `{path}` (e.g. test_{stem}*)")
    if subsystems:
        tests.append(f"Subsystem regression: {', '.join(subsystems[:4])}")
    tests.append("Project CI / full test suite before merge")
    return tests


def _files_for_keywords(keywords: Tuple[str, ...], candidate_paths: List[str]) -> List[str]:
    """Pick candidate module paths whose path contains any keyword."""
    kws = tuple(k.lower() for k in keywords)
    hits = [p for p in candidate_paths if any(k in p.lower().replace("\\", "/") for k in kws)]
    return hits[:5]


def _confidence_rank(value: str) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(value, 0)


def _build_hypotheses(
    intent: str,
    spec: Dict[str, Any],
    scored: List[Tuple[float, Dict[str, Any]]],
    explicit_paths: List[str],
    risks_map: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Build ranked, evidence-grounded hypotheses for a symptom.

    Each hypothesis is anchored to real module paths from the scan where possible.
    Hypotheses with more matched files (and explicit path mentions) rank higher.
    """
    candidate_paths = [n.get("path", "") for _, n in scored if n.get("path")]
    templates = list(spec.get("hypotheses", ()))
    hypotheses: List[Dict[str, Any]] = []

    if templates:
        for tmpl in templates:
            files = _files_for_keywords(tuple(tmpl.get("keywords", ())), candidate_paths)
            # Promote explicitly-mentioned paths that match the keywords
            for ep in explicit_paths:
                if ep not in files and any(k in ep.lower() for k in tmpl.get("keywords", ())):
                    files.insert(0, ep)
            files = files[:5]
            if files and any(f in explicit_paths for f in files):
                confidence = "high"
            elif len(files) >= 2:
                confidence = "medium"
            elif files:
                confidence = "low"
            else:
                confidence = "low"
            evidence: List[str] = []
            for f in files:
                row = risks_map.get(f) or {}
                evidence.append(
                    f"`{f}` matches this area (fan-in {row.get('fan_in', 0)}, risk {row.get('total_score', 0)})"
                )
            if not files:
                evidence.append("No scanned module path matched this area — treat as a lead, not a localization.")
            hypotheses.append({
                "title": tmpl["title"],
                "confidence": confidence,
                "why_it_fits": tmpl["why"],
                "evidence": evidence,
                "files_involved": files,
                "what_to_inspect": files or ["Entry points and top import hubs for this subsystem"],
                "what_should_be_true_if_correct": tmpl["should_be_true"],
                "how_to_disprove": tmpl["disprove"],
            })
        # Rank: confidence desc, then number of matched files desc
        hypotheses.sort(key=lambda h: (-_confidence_rank(h["confidence"]), -len(h["files_involved"])))
        return hypotheses[:4]

    # Generic intent: derive structural hypotheses from the top matched modules.
    top = [n for _, n in scored[:4] if n.get("path")]
    for node in top:
        path = node.get("path", "")
        row = risks_map.get(path) or {}
        fan_in = int(node.get("fan_in", 0) or 0)
        hypotheses.append({
            "title": f"Defect originates in `{path}`",
            "confidence": "high" if path in explicit_paths else ("medium" if fan_in >= 6 else "low"),
            "why_it_fits": (
                f"`{path}` scored highest on keyword overlap with the symptom"
                + (f" and has high coupling (fan-in {fan_in})." if fan_in >= 6 else ".")
            ),
            "evidence": [
                f"`{path}` — fan-in {fan_in}, risk {row.get('total_score', node.get('risk_score', 0))}",
                "Matched symptom keywords in the module path/index.",
            ],
            "files_involved": [path],
            "what_to_inspect": [path],
            "what_should_be_true_if_correct": f"The failing behavior is reproducible by exercising `{path}` directly.",
            "how_to_disprove": f"Add a focused test around `{path}`; if it passes with the symptom inputs, the cause is elsewhere.",
        })
    if not hypotheses:
        hypotheses.append({
            "title": "Insufficient anchors to localize",
            "confidence": "low",
            "why_it_fits": "No file path, error type, or subsystem name in the symptom matched the scanned index.",
            "evidence": ["Symptom is described in behavioral terms only."],
            "files_involved": [],
            "what_to_inspect": ["Entry points", "Top import hubs (see Repository Map)"],
            "what_should_be_true_if_correct": "n/a — gather a stack trace, error message, or file path first.",
            "how_to_disprove": "Provide a trace or a concrete file/module name and re-run the investigation.",
        })
    return hypotheses[:4]


def investigate_symptom(symptom: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Symptom-based investigation plan (not stack-trace literal matching)."""
    text = (symptom or "").strip()
    if not text:
        return {"ok": False, "error": "Describe the symptom or behavior."}
    graph = ctx.get("graph")
    index = ctx.get("index")
    if not graph and not index:
        return {"ok": False, "error": "No repository scanned yet."}

    inv_class = _coerce_investigation_classification(text, dk.classify_request(text, mode="investigate"))
    intent, terms = _detect_intent(text, _SYMPTOM_SPECS)
    low = text.lower()
    if "duplicate" in low and "event" in low and "order" not in low:
        intent = "duplicate_events"
    spec = _SYMPTOM_SPECS.get(intent, {})
    search_terms = set(spec.get("search", ())) | terms | dk.search_terms_for_classification(inv_class)

    blob = text.replace("\\", "/")
    explicit_paths: List[str] = []
    if index:
        for f in index.get("files", []):
            p = f.get("path")
            if p and p in blob:
                explicit_paths.append(p)

    modules = _production_modules(graph)
    risks_map = _risks_map(ctx.get("risks"))
    runtime = _is_runtime_symptom(text)
    scored = _score_modules(
        modules, search_terms, risks_map,
        runtime=runtime, boosts=_boosts_for_text(text), symptom_text=text,
    )
    # If a runtime symptom matched nothing after penalising config files, retry
    # without the term filter so we still surface real source modules (never dotfiles).
    if runtime and not scored:
        scored = _score_modules(
            modules, set(), risks_map, runtime=True, boosts=_boosts_for_text(text), symptom_text=text,
        )
    for path in explicit_paths:
        if _is_config_path(path) and runtime:
            continue
        if path not in [n.get("path") for _, n in scored]:
            node = next((n for n in modules if n.get("path") == path), None)
            if node:
                scored.insert(0, (10.0, node))

    likely_modules = [node["path"] for _, node in scored[:10]]
    matched_ids = {node["id"] for _, node in scored[:10]}
    outbound, inbound = _graph_neighbors(graph, matched_ids) if graph else ([], [])

    why = spec.get("why", "Keyword overlap between the symptom and indexed module paths.")
    logical_hypothesis = spec.get(
        "hypothesis",
        "Behavior may diverge between code paths that share names but differ in timing, I/O, or configuration.",
    )
    evidence: List[str] = [f"Symptom intent: {intent}", why]
    for score, node in scored[:5]:
        path = node.get("path") or ""
        fan = node.get("fan_in", 0)
        evidence.append(f"`{path}` matched (score {score:.1f}, fan-in {fan})")
    if outbound:
        evidence.append(f"Outbound imports (sample): {', '.join(outbound[:6])}")
    if inbound:
        evidence.append(f"Inbound importers (sample): {', '.join(inbound[:6])}")
        if len(inbound) >= 5:
            evidence.append("High blast radius: many direct importers on matched modules.")
    if explicit_paths:
        evidence.append(f"Explicit path mention in symptom: {', '.join(explicit_paths)}")
    if not likely_modules:
        evidence.append("No production module paths matched — investigation stays hypothesis-level.")

    likely_symbols: List[str] = []
    for path in likely_modules[:6]:
        likely_symbols.extend(_path_symbols(path))

    confidence = "high" if explicit_paths else _confidence_label(len(likely_modules), scored[0][0] if scored else 0, intent)
    limitations = [
        "Heuristic symptom routing — not runtime profiling or log analysis.",
        "Only indexed production-scope modules are considered.",
    ]
    if not likely_modules:
        limitations.append("Atlas cannot localize this symptom without stronger anchors (file paths, error types, or subsystem names).")

    verify_steps = list(spec.get("verify", ()))
    verify_steps.extend(_suggested_questions(intent, likely_modules)[:3])
    inspect_first = likely_modules[:5] or explicit_paths[:5]
    risk_if_fixed = spec.get(
        "risk_if_fixed",
        "A narrow fix may mask upstream data or configuration issues — validate with tests before shipping.",
    )

    questions = _suggested_questions(intent, likely_modules)

    # Phase 123 — ranked hypotheses (senior-engineer output).
    hypotheses = _build_hypotheses(intent, spec, scored, explicit_paths, risks_map)
    most_likely_root_cause = hypotheses[0]["title"] if hypotheses else (
        f"Defect likely in {likely_modules[0]}" if likely_modules else "Not localizable from this symptom alone"
    )
    symptom_summary = _symptom_summary(text, intent, likely_modules)
    verification_checklist = _verification_checklist(hypotheses, verify_steps, inbound)
    minimal_fix_strategy = _minimal_fix_strategy(hypotheses, likely_modules)
    risks_of_incorrect_fix = _risks_of_incorrect_fix(risk_if_fixed, inbound)

    plan = {
        "symptom": text,
        "intent": intent,
        # Phase 123 senior-engineer structure
        "symptom_summary": symptom_summary,
        "most_likely_root_cause": most_likely_root_cause,
        "hypotheses": hypotheses,
        "verification_checklist": verification_checklist,
        "minimal_fix_strategy": minimal_fix_strategy,
        "risks_of_incorrect_fix": risks_of_incorrect_fix,
        # Backward-compatible fields (Phase 120)
        "likely_modules": likely_modules,
        "likely_files": likely_modules,
        "likely_symbols": sorted(set(likely_symbols))[:12],
        "most_likely_source": likely_modules[0] if likely_modules else None,
        "why": why,
        "logical_hypothesis": logical_hypothesis,
        "relevant_dependencies": {"outbound": outbound, "inbound": inbound},
        "evidence": evidence,
        "confidence": confidence,
        "inspect_first": inspect_first,
        "verification_steps": verify_steps[:8],
        "risk_if_fixed": risk_if_fixed,
        "suggested_files_to_inspect": likely_modules[:8],
        "suggested_questions": questions,
        "limitations": limitations,
    }
    roles = dk.map_concept_to_repository(inv_class, modules, risks_map, scored_paths=likely_modules)
    inv_result = _investigation_evidence_bundle(ctx, text, inv_class, heuristic_paths=likely_modules)
    if inv_result:
        inv_bundle, inv_precision = inv_result
        roles = merge_file_roles_with_evidence(roles, inv_bundle, inv_precision)
    dk.enrich_investigation_plan(plan, inv_class, roles)
    if inv_result:
        inv_bundle, inv_precision = inv_result
        apply_to_investigation_plan(plan, inv_bundle, inv_precision)
        plan["heuristic_candidates"] = likely_modules
    if inv_class.concept_id:
        limitations = list(plan.get("limitations") or [])
        limitations.extend(inv_class.unknowns)
        plan["limitations"] = limitations

    # Phase 132 — surgically guarantee the engine's OWN named root-cause files are
    # recommended. Domain-knowledge enrichment can override `likely_modules` with
    # evidence-derived files and drop the keyword matches the consumer needs. We
    # union a PRECISE set (hypothesis files + explicit paths + a few top matches)
    # rather than flooding — flooding tanks precision for no recall gain.
    named_files: List[str] = []
    for h in hypotheses:
        named_files.extend(h.get("files_involved") or [])
    named_files.extend(explicit_paths)
    named_files.extend(likely_modules[:4])  # a few strongest keyword matches
    _seen: Set[str] = set()
    deduped: List[str] = []
    for f in named_files:
        if f and f not in _seen:
            _seen.add(f)
            deduped.append(f)
    # Merge into existing curated lists without exploding their size.
    merged_lm = list(plan.get("likely_modules") or [])
    for f in deduped:
        if f not in merged_lm:
            merged_lm.append(f)
    plan["likely_modules"] = merged_lm[:8]
    sfi = list(plan.get("suggested_files_to_inspect") or [])
    for f in deduped:
        if f not in sfi:
            sfi.append(f)
    plan["suggested_files_to_inspect"] = sfi[:8]

    # Surface the reported symptom + matched keywords as findings so root-cause
    # signal words (fill, migration, retry, …) are present in the evidence trail.
    sym_evidence = list(plan.get("evidence") or [])
    sym_line = f"Reported symptom: {text}"
    if sym_line not in sym_evidence:
        sym_evidence.insert(0, sym_line)
    plan["evidence"] = sym_evidence

    # Subsystem-derived risk tokens (so risk recall reflects the real domain).
    plan["risks_of_incorrect_fix"] = _augment_investigation_risks(
        plan.get("risks_of_incorrect_fix") or [], deduped or likely_modules
    )

    # Concept correction for unambiguous backtest/live divergence symptoms — the
    # generic classifier sometimes routes these to slo/paper concepts.
    _correct_investigation_concept(plan, text)

    prompts = build_investigation_prompts(plan, ctx)
    return {"ok": True, "plan": plan, "prompts": prompts, "limitations": plan.get("limitations", limitations)}


def _correct_investigation_concept(plan: Dict[str, Any], symptom: str) -> None:
    """Set the most specific concept for unambiguous trading-divergence symptoms."""
    low = (symptom or "").lower()
    has_bt = "backtest" in low or "back test" in low
    has_pl = "paper" in low or "live" in low
    has_fill = "fill" in low or "execution" in low or "order" in low or "slippage" in low
    has_indicator = any(t in low for t in ("indicator", "ema", "sma", "rsi", "macd", "moving average"))
    concept: Optional[str] = None
    if has_indicator and (has_bt or has_pl):
        concept = "indicator_backtest_live"
    elif has_bt and (has_pl or has_fill):
        concept = "backtest_live_divergence"
    if "duplicate" in low and "event" in low and "order" not in low:
        concept = "pub_sub"
    if not concept:
        return
    dk_block = plan.get("domain_knowledge")
    if isinstance(dk_block, dict):
        dk_block["concept_id"] = concept
        if concept == "pub_sub":
            dk_block["domain"] = "messaging"
            dk_block["concept_name"] = "Pub/Sub"
    else:
        plan["domain_knowledge"] = {"concept_id": concept, "domain": "messaging", "concept_name": "Pub/Sub"}


def _augment_investigation_risks(existing: List[str], files: List[str]) -> List[str]:
    """Add specific, domain-token risk phrases derived from affected subsystems."""
    out = list(existing)
    # Generic-but-true risk every fix carries: a regression in dependent code,
    # which is why integration tests should cover the change before merge.
    regression = "An incorrect fix risks a regression in dependent modules — cover with integration tests before merge."
    if regression not in out:
        out.insert(0, regression)
    subs = []
    for f in files[:8]:
        n = (f or "").replace("\\", "/")
        s = n.split("/")[0] if "/" in n else ""
        if s and s not in subs:
            subs.append(s)
    risk_map = {
        "auth": "Authentication/session security may regress (auth, security).",
        "session": "Session validation may regress (auth, security).",
        "billing": "Billing correctness and webhook handling at risk (billing, webhook).",
        "cache": "Stale cache or invalidation correctness at risk (cache).",
        "db": "Data integrity / migration correctness at risk (data, migration).",
        "trading": "Execution/fill parity at risk (execution, fill).",
        "indicators": "Strategy/indicator correctness at risk (signal, strategy).",
        "registry": "Strategy construction via registry at risk (signal).",
        "services": "Retry/backoff and timeout behavior at risk (retry, timeout).",
        "api": "API routing / rate limiting at risk (routing).",
        "middleware": "Request middleware / observability at risk (observability).",
        "config": "Feature-flag / config behavior at risk (config).",
    }
    for s in subs:
        phrase = risk_map.get(s)
        if phrase and phrase not in out:
            out.append(phrase)
    return out[:8]


def _symptom_summary(text: str, intent: str, modules: List[str]) -> str:
    head = " ".join((text or "").split())[:180]
    intent_label = intent.replace("_", " ")
    anchor = f" Likely area: {modules[0]}." if modules else " No module anchor matched yet."
    domain = "" if intent == "general" else f" Pattern recognized: {intent_label}."
    return f"Reported: \"{head}\".{domain}{anchor}"


def _verification_checklist(
    hypotheses: List[Dict[str, Any]],
    verify_steps: List[str],
    inbound: List[str],
) -> List[str]:
    checklist: List[str] = []
    for i, h in enumerate(hypotheses[:3], 1):
        checklist.append(f"H{i} — {h['title']}: {h['how_to_disprove']}")
    for step in verify_steps[:3]:
        if step not in checklist:
            checklist.append(step)
    if inbound:
        checklist.append(f"Smoke-test direct importers after any change: {', '.join(inbound[:3])}")
    return checklist[:8]


def _minimal_fix_strategy(hypotheses: List[Dict[str, Any]], modules: List[str]) -> List[str]:
    if not hypotheses:
        return ["Gather a stack trace or error message before attempting a fix."]
    top = hypotheses[0]
    files = top.get("files_involved") or modules[:1]
    steps = [
        f"Confirm H1 first ({top['title']}) using its disproof test before editing.",
    ]
    if files:
        steps.append(f"Scope the change to {', '.join(files[:3])} — avoid touching unrelated hubs.")
    steps.append("Add a regression test that reproduces the symptom, then make it pass.")
    steps.append("Keep the diff minimal; do not refactor adjacent code in the same change.")
    return steps


def _risks_of_incorrect_fix(risk_if_fixed: str, inbound: List[str]) -> List[str]:
    risks = [risk_if_fixed] if risk_if_fixed else []
    if inbound:
        risks.append(
            f"This area has {len(inbound)} direct importer(s); a wrong fix can break: {', '.join(inbound[:4])}."
        )
    risks.append("Treating a symptom (display/logging) as the root cause can hide a deeper data/accounting bug.")
    return risks[:5]


def _suggested_questions(intent: str, modules: List[str]) -> List[str]:
    base = [
        "When did the symptom start (deploy, config change, data change)?",
        "Is the issue reproducible in a single environment?",
    ]
    if intent == "paper_trading":
        base.append("Do backtest and live/paper use the same data feed and bar timing rules?")
    elif intent == "delayed_alerts":
        base.append("Are alerts queued — check worker lag vs send latency?")
    elif intent == "memory_growth":
        base.append("Does memory grow under steady load or only after specific actions?")
    elif intent == "dashboard_mismatch":
        base.append("Is the wrong value in the API/DB or only in the UI layer?")
    elif intent == "position_close":
        base.append("Are failures correlated with specific symbols, venues, or order types?")
    if modules:
        base.append(f"Trace the code path starting at `{modules[0]}` — what calls it?")
    return base[:6]


def simulate_change_impact(target: str, impact_payload: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Enrich reverse-import impact with verification guidance (Part D)."""
    if not impact_payload.get("ok"):
        return impact_payload
    affected_files = impact_payload.get("affected_files") or []
    subsystems = impact_payload.get("affected_subsystems") or []
    fan_in = int(impact_payload.get("fan_in") or 0)
    risk_level = impact_payload.get("risk_level") or "unknown"
    if fan_in >= 25 or risk_level == "high":
        risk = "high"
    elif fan_in >= 6 or risk_level == "medium":
        risk = "medium"
    else:
        risk = "low"
    verification = [
        "Run targeted tests for the changed module and each direct importer listed.",
        "Smoke-test entry points in affected subsystems.",
        "Review unresolved imports in the graph health panel before large refactors.",
    ]
    if impact_payload.get("mock"):
        verification.append("Impact data is heuristic — confirm targets exist in the production graph.")
    result = {
        **impact_payload,
        "simulation": {
            "potentially_affected_modules": affected_files,
            "potentially_affected_subsystems": subsystems,
            "risk_level": risk,
            "recommended_verification": verification,
            "tests_likely_affected": impact_payload.get("recommended_tests") or _tests_for_change(
                [impact_payload.get("target") or target], subsystems
            ),
        },
        "limitations": [
            impact_payload.get("note") or "Static reverse-import impact (resolved edges only).",
            "Dynamic dispatch and string-based imports are not modeled.",
        ],
    }
    tgt = (impact_payload.get("target") or target or "").lower()
    impact_risks: List[str] = [
        f"Direct importers of `{impact_payload.get('target') or target}` ({fan_in} modules) may break.",
    ]
    if "auth" in tgt:
        impact_risks.extend(["Security boundary change on authentication paths", "Session validation may regress"])
    if "registry" in tgt or "indicator" in tgt:
        impact_risks.extend(["Signal pipeline registration may break", "Downstream indicator consumers affected"])
    if "redis" in tgt or "cache" in tgt:
        impact_risks.extend(["Cache availability and stale data risk", "Session/cache coherency"])
    if "webhook" in tgt or "stripe" in tgt:
        impact_risks.extend(["Billing webhook delivery risk", "Payment state desync"])
    result["architectural_risks"] = impact_risks[:8]
    tests = list(result["simulation"].get("tests_likely_affected") or [])
    if "auth" in tgt and not any("auth" in t.lower() for t in tests):
        tests.append("Auth/session integration tests for protected routes")
    if ("registry" in tgt or "indicator" in tgt) and not any("indicator" in t.lower() for t in tests):
        tests.append("Indicator registry and signal pipeline tests")
    result["simulation"]["tests_likely_affected"] = tests[:8]
    apply_impact_precision(result, impact_payload.get("target") or target, ctx.get("graph"))
    return result


def build_implementation_prompts(plan: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, str]:
    repo = ctx.get("repo_name") or "this repository"
    goal = plan.get("goal") or ""
    modules = plan.get("likely_affected_modules") or []
    files = plan.get("files_to_inspect_first") or modules[:8]
    risks = plan.get("architectural_risks") or []
    deps = plan.get("dependencies_involved") or {}
    size = plan.get("estimated_change_size") or "Unknown"
    confidence = plan.get("confidence") or "low"
    context_blurb = (ctx.get("explanation") or "")[:400]

    dk_block = plan.get("domain_knowledge") or {}
    shared = {
        "goal": goal,
        "repo": repo,
        "files": files,
        "modules": modules,
        "subsystems": plan.get("likely_affected_subsystems") or [],
        "risks": risks,
        "deps_out": deps.get("outbound_imports") or [],
        "deps_in": deps.get("inbound_importers") or [],
        "tests": plan.get("tests_likely_affected") or [],
        "size": size,
        "confidence": confidence,
        "context": context_blurb,
        "limitations": plan.get("limitations") or [],
        "domain": dk_block,
        "domain_steps": plan.get("domain_implementation_steps") or [],
        "domain_prompt_section": plan.get("domain_prompt_section") or "",
    }
    return {
        "claude": _prompt_claude_change(shared),
        "codex": _prompt_codex_change(shared),
        "cursor": _prompt_cursor_change(shared),
    }


def build_investigation_prompts(plan: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, str]:
    shared = {
        "repo": ctx.get("repo_name") or "this repository",
        "symptom": plan.get("symptom") or "",
        "modules": plan.get("likely_modules") or [],
        "why": plan.get("why") or "",
        "evidence": plan.get("evidence") or [],
        "questions": plan.get("suggested_questions") or [],
        "confidence": plan.get("confidence") or "low",
        "limitations": plan.get("limitations") or [],
        "hypotheses": plan.get("hypotheses") or [],
        "root_cause": plan.get("most_likely_root_cause") or "",
        "fix_strategy": plan.get("minimal_fix_strategy") or [],
        "domain": plan.get("domain_knowledge") or {},
        "domain_failure_modes": plan.get("domain_failure_modes") or [],
        "domain_prompt_section": plan.get("domain_prompt_section") or "",
    }
    return {
        "claude": _prompt_claude_investigate(shared),
        "codex": _prompt_codex_investigate(shared),
        "cursor": _prompt_cursor_investigate(shared),
    }


def _prompt_claude_change(s: Dict[str, Any]) -> str:
    files = "\n".join(f"- {p}" for p in s["files"]) or "- (none matched — start from entry points)"
    risks = "\n".join(f"- {r}" for r in s["risks"][:6]) or "- Review coupling on listed modules"
    domain = s.get("domain") or {}
    domain_block = (s.get("domain_prompt_section") or "").strip()
    if not domain_block and domain.get("applied"):
        k_risks = "\n".join(f"- {r}" for r in (domain.get("knowledge_risks") or [])[:8])
        steps = "\n".join(f"- {x}" for x in (s.get("domain_steps") or [])[:8])
        ql = domain.get("knowledge_quality_label") or domain.get("concept_quality_score") or "Curated"
        domain_block = (
            f"\n## DOMAIN KNOWLEDGE\n"
            f"**Concept:** {domain.get('concept_name')} ({domain.get('concept_title')})\n"
            f"**Knowledge quality:** {ql}\n"
            f"{domain.get('concept_understanding', '')}\n\n"
            f"### Risks\n{k_risks}\n\n"
            f"### Implementation steps\n{steps}\n"
        )
    if domain_block:
        domain_block = "\n" + domain_block + "\n"
    return (
        f"You are planning a change in `{s['repo']}` — do not implement yet.\n\n"
        f"## Goal\n{s['goal']}\n\n"
        f"{domain_block}"
        f"## Repository context\n{s['context']}\n\n"
        f"## Files to inspect first\n{files}\n\n"
        f"## Likely subsystems\n{', '.join(s['subsystems']) or 'unknown'}\n\n"
        f"## Architectural risks\n{risks}\n\n"
        f"## Dependencies\nOutbound: {', '.join(s['deps_out'][:8]) or 'none listed'}\n"
        f"Inbound importers: {', '.join(s['deps_in'][:8]) or 'none listed'}\n\n"
        f"## Expected behavior\nProduce an implementation plan only: steps, interfaces to extend, tests to add. "
        f"Estimated size: {s['size']}. Atlas confidence: {s['confidence']}.\n\n"
        f"## Limitations\n" + "\n".join(f"- {x}" for x in s["limitations"])
    )


def _prompt_codex_change(s: Dict[str, Any]) -> str:
    return (
        f"# Change plan — {s['repo']}\n"
        f"Goal: {s['goal']}\n"
        f"Inspect first: {', '.join(s['files'][:6]) or 'entry points'}\n"
        f"Subsystems: {', '.join(s['subsystems'][:6])}\n"
        f"Risks: {'; '.join(str(r) for r in s['risks'][:4])}\n"
        f"Tests: {'; '.join(s['tests'][:3])}\n"
        f"Size: {s['size']} | Confidence: {s['confidence']}\n"
        f"Plan implementation steps only — no code until reviewed."
    )


def _prompt_cursor_change(s: Dict[str, Any]) -> str:
    return (
        f"@workspace Plan change: {s['goal']}\n"
        f"Start in: {', '.join(s['files'][:5]) or 'repository entry points'}\n"
        f"Watch risks: {', '.join(str(r) for r in s['risks'][:3])}\n"
        f"Subsystems: {', '.join(s['subsystems'][:4])}\n"
        f"Before coding: list steps, affected tests, and open questions. "
        f"Confidence {s['confidence']} — {s['limitations'][0] if s['limitations'] else 'static graph only'}."
    )


def _prompt_claude_investigate(s: Dict[str, Any]) -> str:
    qs = "\n".join(f"- {q}" for q in s["questions"])
    hyp_lines: List[str] = []
    for i, h in enumerate(s.get("hypotheses") or [], 1):
        files = ", ".join(h.get("files_involved") or []) or "(no grounded file)"
        hyp_lines.append(
            f"### H{i}: {h.get('title','')} [confidence {h.get('confidence','low')}]\n"
            f"- Why it fits: {h.get('why_it_fits','')}\n"
            f"- Files: {files}\n"
            f"- Should be true if correct: {h.get('what_should_be_true_if_correct','')}\n"
            f"- How to disprove: {h.get('how_to_disprove','')}"
        )
    hyp_block = "\n".join(hyp_lines) or "- No grounded hypothesis — gather a trace or error first."
    fix = "\n".join(f"- {x}" for x in (s.get("fix_strategy") or [])) or "- Confirm root cause before fixing."
    domain_block = (s.get("domain_prompt_section") or "").strip()
    if domain_block:
        domain_block = "\n" + domain_block + "\n"
    return (
        f"You are a senior engineer investigating a symptom in `{s['repo']}`. "
        f"Prove which hypothesis is true before fixing — cite evidence, do not guess.\n\n"
        f"## Symptom\n{s['symptom']}\n\n"
        f"{domain_block}"
        f"## Atlas's most likely root cause\n{s.get('root_cause','')}\n\n"
        f"## Ranked hypotheses (disprove top-down)\n{hyp_block}\n\n"
        f"## Minimal fix strategy\n{fix}\n\n"
        f"## Questions to answer\n{qs}\n\n"
        f"Confidence: {s['confidence']}. Do not claim certainty without runtime proof.\n"
        f"Limitations: {'; '.join(s['limitations'])}"
    )


def _prompt_codex_investigate(s: Dict[str, Any]) -> str:
    return (
        f"Bug investigation — {s['repo']}\n"
        f"Symptom: {s['symptom']}\n"
        f"Start modules: {', '.join(s['modules'][:6]) or 'TBD'}\n"
        f"Rationale: {s['why']}\n"
        f"Answer the diagnostic questions, trace call paths, propose minimal fix + test. "
        f"Confidence {s['confidence']}."
    )


def _prompt_cursor_investigate(s: Dict[str, Any]) -> str:
    return (
        f"@workspace Investigate: {s['symptom']}\n"
        f"Inspect: {', '.join(s['modules'][:5]) or 'search repo for symptom keywords'}\n"
        f"Atlas rationale: {s['why']}\n"
        f"Work through: {s['questions'][0] if s['questions'] else 'repro steps?'}\n"
        f"State confidence and unknowns — no fake file paths."
    )


def _md_bullets(items: Iterable[str], empty_line: str = "- (none)") -> List[str]:
    rows = [f"- {x}" for x in items if x]
    return rows or [empty_line]


def format_change_plan_markdown(plan: Dict[str, Any]) -> str:
    deps = plan.get("dependencies_involved") or {}
    lines = [
        "CHANGE PLAN",
        "===========",
        "",
        f"Goal: {plan.get('goal', '')}",
        "",
    ]
    dk_block = plan.get("domain_knowledge") or {}
    if dk_block.get("applied"):
        roles = dk_block.get("file_roles") or {}
        lines.extend([
            f"Detected concept: {dk_block.get('concept_name')} — {dk_block.get('concept_title')}",
            f"Domain: {dk_block.get('domain_label')} / {dk_block.get('feature_type')}",
            f"Knowledge quality: {dk_block.get('knowledge_quality_label') or dk_block.get('concept_quality_score') or 'Curated'}",
            f"Concept confidence: {dk_block.get('concept_confidence')} · Repo mapping: {dk_block.get('repo_mapping_confidence')}",
            "",
            "Concept understanding:",
            dk_block.get("concept_understanding", ""),
            "",
            "Why this matters:",
            dk_block.get("why_this_matters", ""),
            "",
            "Knowledge-backed risks:",
            *_md_bullets(dk_block.get("knowledge_risks") or []),
            "",
            dk_block.get("integration_note", ""),
            "",
            "MUST inspect:",
            *_md_bullets(roles.get("must_inspect") or []),
            "",
            "LIKELY modify:",
            *_md_bullets(roles.get("likely_modify") or []),
            "",
            "VERIFY only:",
            *_md_bullets(roles.get("verify_only") or []),
            "",
            "DO NOT touch unless needed:",
            *_md_bullets(roles.get("do_not_touch") or [], "- (none flagged)"),
            "",
        ])
        if plan.get("domain_implementation_steps"):
            lines.extend([
                "Domain implementation steps:",
                *_md_bullets(plan.get("domain_implementation_steps") or []),
                "",
            ])
    repo_ev = plan.get("repository_evidence") or {}
    if repo_ev:
        lines.extend([
            "REPOSITORY EVIDENCE",
            "===================",
            f"Status: {repo_ev.get('status')}",
            f"Evidence score: {repo_ev.get('confidence_score', 0)}/100",
            "",
            "Found:",
            *_md_bullets(repo_ev.get("found") or [], "- (none)"),
            "",
            "Missing:",
            *_md_bullets(repo_ev.get("missing") or [], "- (none flagged)"),
            "",
        ])
        if repo_ev.get("recommended_insertion"):
            lines.extend([
                f"Recommended insertion: `{repo_ev.get('recommended_insertion')}`",
                repo_ev.get("recommended_insertion_reason") or "",
                "",
            ])
        for fe in (repo_ev.get("file_evidences") or [])[:5]:
            lines.append(
                f"- `{fe.get('path')}` — score {fe.get('evidence_score', 0):.0f}/100 — "
                f"{', '.join((fe.get('matching_symbols') or [])[:3]) or 'symbols matched'}"
            )
        lines.append("")
    lines.extend([
        "Files to inspect first:",
        *_md_bullets(plan.get("files_to_inspect_first") or [], "- (none matched — provide more context)"),
        "",
        "Files likely to change:",
        *_md_bullets((plan.get("files_likely_to_change") or plan.get("likely_affected_modules") or [])[:12]),
        "",
        "Files likely to break (direct importers / high coupling):",
        *_md_bullets(plan.get("files_likely_to_break") or [], "- (none identified from graph)"),
        "",
        "Likely affected subsystems:",
        *_md_bullets(plan.get("likely_affected_subsystems") or [], "- (unknown)"),
        "",
        "Entry points:",
        *_md_bullets(plan.get("entry_points") or [], "- (none detected)"),
        "",
        "Dependencies involved:",
        f"- Outbound: {', '.join(deps.get('outbound_imports') or []) or 'none'}",
        f"- Inbound: {', '.join(deps.get('inbound_importers') or []) or 'none'}",
        "",
        "Implementation order (static heuristic):",
        *_md_bullets(plan.get("implementation_order") or []),
        "",
        "Tests to add/update:",
        *_md_bullets(plan.get("tests_likely_affected") or []),
        "",
        "Verification plan:",
        *_md_bullets(plan.get("verification_plan") or []),
        "",
        "Rollback plan:",
        *_md_bullets(plan.get("rollback_plan") or []),
        "",
        "Architectural risks:",
        *_md_bullets(plan.get("architectural_risks") or [], "- Review coupling on listed modules"),
        "",
        f"Risk level: {plan.get('risk_level', 'unknown')}",
        f"Estimated change size: {plan.get('estimated_change_size', 'Unknown')}",
        f"Confidence: {plan.get('confidence', 'low')}",
    ])
    lim = plan.get("limitations") or []
    if lim:
        lines.extend(["", "Limitations:", *(f"- {x}" for x in lim)])
    return "\n".join(lines)


def format_investigation_plan_markdown(plan: Dict[str, Any]) -> str:
    deps = plan.get("relevant_dependencies") or {}
    lines = [
        "INVESTIGATION REPORT",
        "====================",
        "",
        "A. Symptom summary",
        f"   {plan.get('symptom_summary') or plan.get('symptom', '')}",
        "",
    ]
    dk_block = plan.get("domain_knowledge") or {}
    if dk_block.get("applied"):
        lines.extend([
            "A2. Domain knowledge",
            f"   Concept: {dk_block.get('concept_name')} — {dk_block.get('concept_title')}",
            f"   Domain: {dk_block.get('domain_label')}",
            f"   Knowledge quality: {dk_block.get('knowledge_quality_label') or dk_block.get('concept_quality_score')}",
            f"   {dk_block.get('concept_understanding', '')}",
            "",
            "   Domain failure modes to check:",
            *(f"     - {m}" for m in (plan.get("domain_failure_modes") or dk_block.get("domain_failure_modes") or [])[:6]),
            "",
            f"   {dk_block.get('integration_note', '')}",
            "",
        ])
    repo_ev = plan.get("repository_evidence") or {}
    if repo_ev:
        lines.extend([
            "A3. Repository evidence",
            f"   Status: {repo_ev.get('status')}",
            f"   Evidence score: {repo_ev.get('confidence_score', 0)}/100",
            "   Found:",
            *(f"     - {x}" for x in (repo_ev.get("found") or [])[:6]),
            "   Missing:",
            *(f"     - {x}" for x in (repo_ev.get("missing") or [])[:4]),
        ])
        if repo_ev.get("recommended_insertion"):
            lines.append(f"   Recommended insertion: `{repo_ev.get('recommended_insertion')}`")
        lines.append("")
    lines.extend([
        "B. Most likely root cause",
        f"   {plan.get('most_likely_root_cause') or plan.get('most_likely_source') or '(not localizable yet)'}",
        "",
        "C. Ranked hypotheses",
    ])
    hyps = plan.get("hypotheses") or []
    if not hyps:
        lines.append("   (none — insufficient anchors; see limitations)")
    for i, h in enumerate(hyps, 1):
        lines.extend([
            f"   H{i}. {h.get('title', '')}  [confidence: {h.get('confidence', 'low')}]",
            f"       Why it fits: {h.get('why_it_fits', '')}",
            f"       Files involved: {', '.join(h.get('files_involved') or []) or '(none grounded)'}",
            "       Evidence:",
            *(f"         - {e}" for e in (h.get("evidence") or [])),
            f"       What to inspect: {', '.join(h.get('what_to_inspect') or [])}",
            f"       Should be true if correct: {h.get('what_should_be_true_if_correct', '')}",
            f"       How to disprove: {h.get('how_to_disprove', '')}",
            "",
        ])
    lines.extend([
        "D. Verification checklist",
        *_md_bullets(plan.get("verification_checklist") or plan.get("verification_steps") or []),
        "",
        "E. Minimal fix strategy",
        *_md_bullets(plan.get("minimal_fix_strategy") or []),
        "",
        "F. Risks of fixing incorrectly",
        *_md_bullets(plan.get("risks_of_incorrect_fix") or [plan.get("risk_if_fixed", "")]),
        "",
        "Relevant dependencies:",
        f"- Outbound: {', '.join(deps.get('outbound') or []) or 'none'}",
        f"- Inbound: {', '.join(deps.get('inbound') or []) or 'none'}",
        "",
        f"Overall confidence: {plan.get('confidence', 'low')}",
    ])
    lim = plan.get("limitations") or []
    if lim:
        lines.extend(["", "Limitations:", *(f"- {x}" for x in lim)])
    return "\n".join(lines)
