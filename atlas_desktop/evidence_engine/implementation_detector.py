"""Concept-specific implementation detectors using AST symbol evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .call_graph import CallGraph
from .evidence_models import FileEvidence, ImplementationStatus, SymbolRecord
from .symbol_index import SymbolIndex

DetectorFn = Callable[[SymbolIndex, CallGraph, List[str]], "DetectionResult"]


@dataclass
class DetectionResult:
    concept_id: str
    status: str = ImplementationStatus.NOT_FOUND.value
    found_labels: List[str] = field(default_factory=list)
    missing_labels: List[str] = field(default_factory=list)
    matched_symbols: List[SymbolRecord] = field(default_factory=list)
    search_patterns: List[str] = field(default_factory=list)
    insertion_patterns: Tuple[str, ...] = ()
    usage_patterns: List[str] = field(default_factory=list)


def _sym_label(sym: SymbolRecord) -> str:
    if sym.qualname and sym.qualname != sym.name:
        return f"{sym.qualname}() in `{sym.file_path}`"
    return f"{sym.name} in `{sym.file_path}`"


def _score_file(path: str, symbols: List[SymbolRecord], patterns: List[str]) -> FileEvidence:
    sym_names = [_sym_label(s) for s in symbols]
    patterns_hit = [p for p in patterns if any(p.lower() in n.lower() for n in sym_names + [path])]
    impl_boost = 0.0
    for s in symbols:
        if s.kind in ("registry", "factory", "middleware", "interface", "protocol"):
            impl_boost += 8.0
        if "register" in s.name.lower():
            impl_boost += 6.0
    score = min(100.0, 20.0 + len(symbols) * 12.0 + len(patterns_hit) * 8.0 + impl_boost)
    return FileEvidence(
        path=path,
        evidence_score=score,
        matching_symbols=sym_names[:8],
        matching_concepts=patterns_hit[:6],
        usage_patterns=[f"{s.name} used {s.usage_count}x" for s in symbols if s.usage_count][:4],
        reason_selected=f"AST definitions/references match: {', '.join(patterns_hit[:3]) or 'symbol overlap'}",
        symbol_details=[s.to_dict() for s in symbols[:6]],
    )


def _detect(
    concept_id: str,
    index: SymbolIndex,
    call_graph: CallGraph,
    *,
    found_patterns: List[str],
    missing_patterns: List[str],
    target_patterns: List[str],
    insertion_patterns: Tuple[str, ...] = ("registry", "service", "middleware", "client"),
    status_if_partial: bool = True,
) -> DetectionResult:
    matched = index.find_in_source(found_patterns + target_patterns)
    found_labels: List[str] = []
    missing_labels: List[str] = []
    seen_found: Set[str] = set()

    for pat in found_patterns:
        hits = [s for s in matched if pat.lower() in (s.name + s.qualname).lower()]
        if hits:
            label = _sym_label(hits[0])
            if label not in seen_found:
                seen_found.add(label)
                found_labels.append(label)
        else:
            missing_labels.append(pat.replace("_", " ").title())

    target_hits = [s for s in matched if any(t.lower() in (s.name + s.qualname).lower() for t in target_patterns)]
    has_target = bool(target_hits)

    if has_target:
        status = ImplementationStatus.IMPLEMENTED.value
    elif found_labels and status_if_partial:
        status = ImplementationStatus.PARTIAL.value
        for pat in missing_patterns:
            if not any(pat.lower() in f.lower() for f in found_labels):
                missing_labels.append(pat.replace("_", " ").title())
    else:
        status = ImplementationStatus.NOT_FOUND.value
        missing_labels.extend(m.replace("_", " ").title() for m in missing_patterns)

    return DetectionResult(
        concept_id=concept_id,
        status=status,
        found_labels=found_labels,
        missing_labels=sorted(set(missing_labels)),
        matched_symbols=matched,
        search_patterns=found_patterns + target_patterns,
        insertion_patterns=insertion_patterns,
        usage_patterns=[f"calls {c}" for c in call_graph.who_calls(target_patterns[0])[:3]] if target_patterns else [],
    )


def detect_ema(index: SymbolIndex, cg: CallGraph, _kw: List[str]) -> DetectionResult:
    result = _detect(
        "ema",
        index,
        cg,
        found_patterns=["sma", "moving_average", "moving average", "indicator", "signal", "register_indicator", "registry"],
        missing_patterns=["ema", "exponential moving average"],
        target_patterns=["emaindicator", "ema_indicator"],
        insertion_patterns=("registry", "indicator", "signal", "strategy"),
    )
    impl = [
        s
        for s in result.matched_symbols
        if s.kind in ("class", "function", "method")
        and "ema" in s.name.lower()
        and "feature" not in s.name.lower()
    ]
    if not impl:
        result.status = ImplementationStatus.PARTIAL.value
        for label in ("EMA", "Exponential moving average"):
            if label not in result.missing_labels:
                result.missing_labels.append(label)
    return result


def detect_circuit_breaker(index: SymbolIndex, cg: CallGraph, _kw: List[str]) -> DetectionResult:
    return _detect(
        "circuit_breaker",
        index,
        cg,
        found_patterns=["http", "client", "retry", "requests", "httpx", "aiohttp", "fetch"],
        missing_patterns=["circuit_breaker", "breaker", "half_open", "open_state"],
        target_patterns=["circuit", "breaker"],
        insertion_patterns=("client", "http", "service", "wrapper"),
    )


def detect_distributed_tracing(index: SymbolIndex, cg: CallGraph, _kw: List[str]) -> DetectionResult:
    return _detect(
        "distributed_tracing",
        index,
        cg,
        found_patterns=["request_id", "correlation", "middleware", "logging", "logger", "structlog"],
        missing_patterns=["trace", "span", "opentelemetry", "propagat"],
        target_patterns=["trace", "span", "otel"],
        insertion_patterns=("middleware", "logging", "request", "http"),
    )


def detect_retry(index: SymbolIndex, cg: CallGraph, _kw: List[str]) -> DetectionResult:
    result = _detect(
        "retry_backoff",
        index,
        cg,
        found_patterns=["retry", "backoff", "sleep", "attempt", "tenacity", "fetch", "range"],
        missing_patterns=["exponential backoff", "jitter"],
        target_patterns=["retry", "backoff"],
        insertion_patterns=("client", "http", "service", "queue"),
    )
    if not result.found_labels:
        for path, scan in index.files.items():
            callees = {c[1].lower() for c in scan.calls}
            if "sleep" in callees and any(c[0] for c in scan.calls):
                result.found_labels.append(f"Retry loop (sleep/backoff) in `{path}`")
                result.status = ImplementationStatus.PARTIAL.value
    return result


def detect_feature_flags(index: SymbolIndex, cg: CallGraph, _kw: List[str]) -> DetectionResult:
    return _detect(
        "feature_flags",
        index,
        cg,
        found_patterns=["feature_flag", "feature flag", "feature", "toggle", "launchdarkly", "settings", "config"],
        missing_patterns=["flag evaluation", "rollout"],
        target_patterns=["feature", "flag", "toggle"],
        insertion_patterns=("config", "settings", "feature"),
    )


def detect_authentication(index: SymbolIndex, cg: CallGraph, _kw: List[str]) -> DetectionResult:
    return _detect(
        "authentication",
        index,
        cg,
        found_patterns=["auth", "login", "session", "middleware", "authenticate", "password"],
        missing_patterns=["token validation", "session store"],
        target_patterns=["authenticate", "login", "auth"],
        insertion_patterns=("auth", "middleware", "session", "login"),
    )


def detect_jwt(index: SymbolIndex, cg: CallGraph, _kw: List[str]) -> DetectionResult:
    return _detect(
        "jwt",
        index,
        cg,
        found_patterns=["jwt", "bearer", "decode", "encode", "middleware", "auth"],
        missing_patterns=["jwt validation", "algorithm allow-list"],
        target_patterns=["jwt", "bearer"],
        insertion_patterns=("auth", "middleware", "security"),
    )


def detect_oauth2(index: SymbolIndex, cg: CallGraph, _kw: List[str]) -> DetectionResult:
    return _detect(
        "oauth2",
        index,
        cg,
        found_patterns=["oauth", "authorize", "token", "pkce", "client_id", "login", "session"],
        missing_patterns=["authorization code flow", "token refresh"],
        target_patterns=["oauth", "authorize", "login"],
        insertion_patterns=("auth", "oauth", "login", "security"),
    )


def detect_idempotency_key(index: SymbolIndex, cg: CallGraph, _kw: List[str]) -> DetectionResult:
    return _detect(
        "idempotency_key",
        index,
        cg,
        found_patterns=["idempotency", "idempotent", "order", "execution", "place_order", "execute_order"],
        missing_patterns=["idempotency key store", "dedupe token"],
        target_patterns=["idempotency", "idempotent", "order"],
        insertion_patterns=("order", "execution", "service", "trading"),
    )


def detect_rate_limiting(index: SymbolIndex, cg: CallGraph, _kw: List[str]) -> DetectionResult:
    return _detect(
        "rate_limiting",
        index,
        cg,
        found_patterns=["rate_limit", "throttle", "limiter", "middleware", "redis"],
        missing_patterns=["rate limit headers", "429 response"],
        target_patterns=["rate", "throttle", "limiter"],
        insertion_patterns=("middleware", "api", "gateway"),
    )


def detect_logging(index: SymbolIndex, cg: CallGraph, _kw: List[str]) -> DetectionResult:
    return _detect(
        "structured_logging",
        index,
        cg,
        found_patterns=["logger", "logging", "structlog", "json", "log"],
        missing_patterns=["structured fields", "correlation id"],
        target_patterns=["structlog", "json", "logger"],
        insertion_patterns=("logging", "middleware", "audit"),
    )


def detect_webhooks(index: SymbolIndex, cg: CallGraph, _kw: List[str]) -> DetectionResult:
    return _detect(
        "webhook_receiver",
        index,
        cg,
        found_patterns=["webhook", "stripe", "signature", "verify", "endpoint"],
        missing_patterns=["webhook signature verification"],
        target_patterns=["webhook"],
        insertion_patterns=("webhook", "api", "billing"),
    )


def detect_database(index: SymbolIndex, cg: CallGraph, _kw: List[str]) -> DetectionResult:
    return _detect(
        "postgresql",
        index,
        cg,
        found_patterns=["sqlalchemy", "postgres", "session", "engine", "migrate", "alembic"],
        missing_patterns=["connection pool", "migration"],
        target_patterns=["session", "engine", "postgres"],
        insertion_patterns=("db", "database", "models", "repository"),
    )


def detect_queues(index: SymbolIndex, cg: CallGraph, _kw: List[str]) -> DetectionResult:
    return _detect(
        "retry_queue",
        index,
        cg,
        found_patterns=["queue", "celery", "kafka", "consumer", "worker", "publish"],
        missing_patterns=["dead letter", "retry queue"],
        target_patterns=["queue", "consumer", "worker"],
        insertion_patterns=("queue", "worker", "messaging"),
    )


def detect_indicator_backtest_live(index: SymbolIndex, cg: CallGraph, _kw: List[str]) -> DetectionResult:
    """Investigation detector — indicator computation differs between backtest and live."""
    indicator_syms = index.find_in_source(
        ["sma", "indicator", "moving_average", "compute", "warmup", "lookahead"]
    )
    pipeline_syms = index.find_in_source(["pipeline", "signal", "run_signals"])
    found: List[str] = []
    missing: List[str] = []

    sma = [s for s in indicator_syms if "sma" in (s.name + s.qualname).lower() or "indicator" in s.kind]
    if sma:
        found.append(f"Indicator implementation: {_sym_label(sma[0])}")
    else:
        missing.append("Indicator module (SMA/EMA)")

    pipe = [s for s in pipeline_syms if "pipeline" in s.file_path.lower() or "run_signal" in s.name.lower()]
    if pipe:
        found.append(f"Signal pipeline: {_sym_label(pipe[0])}")
    else:
        missing.append("Signal pipeline wiring")

    warmup = [s for s in indicator_syms if "warmup" in (s.name + s.qualname).lower()]
    if warmup:
        found.append(f"Warmup handling: {_sym_label(warmup[0])}")
    else:
        missing.append("Warmup / bar alignment check")

    status = ImplementationStatus.PARTIAL.value if found else ImplementationStatus.NOT_FOUND.value
    if len(found) >= 2:
        status = ImplementationStatus.IMPLEMENTED.value

    return DetectionResult(
        concept_id="indicator_backtest_live",
        status=status,
        found_labels=found,
        missing_labels=missing or ["Compare indicator compute path backtest vs live"],
        matched_symbols=indicator_syms + pipeline_syms,
        search_patterns=["indicator", "sma", "pipeline", "signal", "warmup"],
        insertion_patterns=("indicator", "signal", "pipeline", "sma"),
    )


def detect_backtest_divergence(index: SymbolIndex, cg: CallGraph, _kw: List[str]) -> DetectionResult:
    """Investigation detector — compare execution config symbols across backtest/paper."""
    backtest_syms = index.find_in_source(["backtest", "slippage", "fill_model", "fill model"])
    paper_syms = index.find_in_source(["paper", "live", "broker", "execution"])
    found: List[str] = []
    missing: List[str] = []

    slippage_bt = [s for s in backtest_syms if "slippage" in (s.name + s.qualname).lower()]
    slippage_live = [s for s in paper_syms if "slippage" in (s.name + s.qualname).lower()]
    if slippage_bt and slippage_live:
        bt_vals = {_sym_label(s) for s in slippage_bt}
        live_vals = {_sym_label(s) for s in slippage_live}
        if bt_vals != live_vals:
            found.append(f"Slippage mismatch: backtest {list(bt_vals)[:2]} vs live {list(live_vals)[:2]}")
        else:
            found.append(f"Slippage symbols aligned: {list(bt_vals)[:2]}")
    elif slippage_bt and not slippage_live:
        found.append(f"Slippage defined in backtest only: {_sym_label(slippage_bt[0])}")
        missing.append("Live/paper slippage configuration")
    elif slippage_live and not slippage_bt:
        found.append(f"Slippage defined in live/paper only: {_sym_label(slippage_live[0])}")
        missing.append("Backtest slippage configuration")

    fill_bt = [s for s in backtest_syms if "fill" in (s.name + s.qualname).lower()]
    fill_live = [s for s in paper_syms if "fill" in (s.name + s.qualname).lower()]
    if fill_bt and fill_live and {_sym_label(s) for s in fill_bt} != {_sym_label(s) for s in fill_live}:
        found.append("Different fill model symbols between backtest and live paths")

    timing = index.find_in_source(["bar_timing", "lookahead", "execution_timing", "timing"])
    if timing:
        found.append(f"Execution timing config: {_sym_label(timing[0])}")

    status = ImplementationStatus.PARTIAL.value if found else ImplementationStatus.NOT_FOUND.value
    if len(found) >= 2:
        status = ImplementationStatus.IMPLEMENTED.value

    return DetectionResult(
        concept_id="backtest_live_divergence",
        status=status,
        found_labels=found,
        missing_labels=missing or ["Side-by-side slippage/fill comparison"],
        matched_symbols=backtest_syms + paper_syms,
        search_patterns=["backtest", "paper", "slippage", "fill"],
        insertion_patterns=("backtest", "paper", "execution", "config"),
    )


def detect_slippage_model(index: SymbolIndex, cg: CallGraph, _kw: List[str]) -> DetectionResult:
    return _detect(
        "slippage_model",
        index,
        cg,
        found_patterns=["slippage", "fill_model", "fill model", "backtest_config", "paper_config"],
        missing_patterns=["configurable slippage"],
        target_patterns=["slippage"],
        insertion_patterns=("backtest", "paper", "config", "trading"),
    )


def detect_health_check(index: SymbolIndex, cg: CallGraph, _kw: List[str]) -> DetectionResult:
    return _detect(
        "health_check",
        index,
        cg,
        found_patterns=["health", "routes", "endpoint", "status"],
        missing_patterns=["health check endpoint"],
        target_patterns=["health"],
        insertion_patterns=("routes", "api", "health"),
    )


DETECTORS: Dict[str, DetectorFn] = {
    "ema": detect_ema,
    "circuit_breaker": detect_circuit_breaker,
    "distributed_tracing": detect_distributed_tracing,
    "retry_backoff": detect_retry,
    "feature_flags": detect_feature_flags,
    "authentication": detect_authentication,
    "jwt": detect_jwt,
    "oauth2": detect_oauth2,
    "idempotency_key": detect_idempotency_key,
    "rate_limiting": detect_rate_limiting,
    "structured_logging": detect_logging,
    "webhook_receiver": detect_webhooks,
    "postgresql": detect_database,
    "database_migration": detect_database,
    "retry_queue": detect_queues,
    "backtest_live_divergence": detect_backtest_divergence,
    "indicator_backtest_live": detect_indicator_backtest_live,
    "slippage_model": detect_slippage_model,
    "health_check": detect_health_check,
}


def resolve_detector(concept_id: str, category: str = "", domain: str = "") -> Optional[DetectorFn]:
    if concept_id in DETECTORS:
        return DETECTORS[concept_id]
    if category == "indicator" or domain == "trading":
        return detect_ema
    if category in ("auth", "authentication") or domain == "security":
        return detect_authentication
    if domain == "observability":
        return detect_logging
    return None


def file_evidences_from_detection(
    detection: DetectionResult,
    index: SymbolIndex,
) -> List[FileEvidence]:
    by_file: Dict[str, List[SymbolRecord]] = {}
    for sym in detection.matched_symbols:
        by_file.setdefault(sym.file_path, []).append(sym)
    evidences = [
        _score_file(path, syms, detection.search_patterns)
        for path, syms in by_file.items()
    ]
    evidences.sort(key=lambda fe: (-fe.evidence_score, fe.path))
    return evidences


def pick_insertion_point(
    detection: DetectionResult,
    file_evidences: List[FileEvidence],
    index: SymbolIndex,
    *,
    concept_id: str = "",
) -> Tuple[str, str]:
    if not file_evidences:
        candidates = index.files_with_pattern(detection.insertion_patterns)
        if candidates:
            return candidates[0], "No direct symbol match — nearest structural pattern in repo"
        return "", "No AST evidence for insertion point"

    ranked: List[Tuple[float, str]] = []
    for fe in file_evidences:
        score = fe.evidence_score
        pl = fe.path.lower()
        for pat in detection.insertion_patterns:
            if pat in pl:
                score += 18.0
        if concept_id in ("stripe_billing",) and "webhook" in pl and "billing" not in pl:
            score -= 25.0
        if concept_id in ("circuit_breaker", "retry_backoff") and ("client" in pl or "http" in pl):
            score += 15.0
        if concept_id in ("rate_limiting",) and "rate" in pl:
            score += 20.0
        if concept_id in ("distributed_tracing", "structured_logging") and "middleware" in pl:
            score += 15.0
        if concept_id in ("ema",) and ("registry" in pl or "indicator" in pl):
            score += 12.0
        if concept_id in ("slippage_model", "backtest_live_divergence") and (
            "_config" in pl or pl.endswith("config.py")
        ):
            score += 28.0
        if concept_id in ("slippage_model", "backtest_live_divergence") and (
            "engine" in pl or pl.endswith("paper_trading.py")
        ):
            score -= 22.0
        if concept_id == "indicator_backtest_live" and ("indicators/" in pl or "/sma" in pl):
            score += 40.0
        if concept_id == "indicator_backtest_live" and ("signal" in pl or "pipeline" in pl):
            score += 22.0
        if concept_id == "indicator_backtest_live" and "registry/signal" in pl:
            score -= 25.0
        if concept_id == "health_check" and ("routes" in pl or "/api/" in pl):
            score += 30.0
        if concept_id == "retry_backoff" and ("http_client" in pl or "client" in pl):
            score += 25.0
        if concept_id in ("oauth2", "authentication", "jwt") and pl.startswith("auth/"):
            score += 30.0
        if concept_id == "idempotency_key" and ("order" in pl or "execution" in pl):
            score += 22.0
        ranked.append((score, fe.path))
    ranked.sort(key=lambda x: (-x[0], x[1]))
    top = ranked[0]
    fe = next(f for f in file_evidences if f.path == top[1])
    return top[1], f"Evidence score {top[0]:.0f}/100 — {fe.reason_selected}"
