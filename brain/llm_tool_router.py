"""Phase 79 Stage 1 — Shadow LLM tool router (decide + log only; never execute)."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from config import CONFIDENCE_THRESHOLD
from core.logger import setup_logger
from core.types import CommandRequest, Intent
from tools.spec import SafetyClass, ToolSpec

from brain import tool_router_audit
from brain.tool_router_prompt import (
    CORE_TOOL_NAMES,
    build_system_prompt,
    build_user_prompt,
    parse_router_output,
    render_candidate_tools,
)
from tooluse.contracts import scan_forbidden

logger = setup_logger("jarvis.brain.llm_tool_router")

LlmFn = Callable[[str, str], str]

_DEFAULT_K = 10
_CIRCUIT_BREAKER_THRESHOLD = 3
_latency_budget_s = 4.0

_lock = threading.Lock()
_consecutive_errors = 0
_circuit_open = False
_invoke_count = 0
_injected_llm_fn: LlmFn | None = None


@dataclass(frozen=True)
class RouterDecision:
    outcome: str
    tool_name: str = ""
    tool_args: dict[str, Any] = field(default_factory=dict)
    mapped_intent: str = ""
    clarify_question: str = ""
    refuse_reason: str = ""
    candidate_tools: tuple[str, ...] = ()
    latency_ms: float = 0.0
    fallback_reason: str = ""
    shadow: bool = True
    executed: bool = False
    circuit_breaker_open: bool = False


def reset_llm_tool_router_for_tests() -> None:
    global _consecutive_errors, _circuit_open, _invoke_count, _injected_llm_fn
    with _lock:
        _consecutive_errors = 0
        _circuit_open = False
        _invoke_count = 0
        _injected_llm_fn = None
    tool_router_audit.reset_for_tests()


def set_llm_fn_for_tests(fn: LlmFn | None) -> None:
    """Inject deterministic LLM for tests/smoke (never used in production)."""
    global _injected_llm_fn
    _injected_llm_fn = fn


def _resolve_llm_fn(llm_fn: LlmFn | None) -> LlmFn | None:
    if llm_fn is not None:
        return llm_fn
    return _injected_llm_fn


def get_router_invoke_count() -> int:
    with _lock:
        return _invoke_count


def is_circuit_breaker_open() -> bool:
    with _lock:
        return _circuit_open


def is_classifier_miss(request: CommandRequest) -> bool:
    if request.intent in (Intent.UNKNOWN, Intent.CLARIFY):
        return True
    return float(request.confidence or 0.0) < float(CONFIDENCE_THRESHOLD)


def should_invoke_shadow_router() -> bool:
    from tools.flags import llm_tool_router_enabled, llm_tool_router_shadow

    return llm_tool_router_enabled() and llm_tool_router_shadow()


def _record_error() -> None:
    global _consecutive_errors, _circuit_open
    with _lock:
        _consecutive_errors += 1
        if _consecutive_errors >= _CIRCUIT_BREAKER_THRESHOLD:
            _circuit_open = True
            logger.warning(
                "LLM tool router circuit breaker open after %d errors",
                _consecutive_errors,
            )


def _record_success() -> None:
    global _consecutive_errors
    with _lock:
        _consecutive_errors = 0


def _allowed_safety_classes() -> tuple[SafetyClass, ...]:
    from tools.flags import llm_tool_router_readonly_only

    if llm_tool_router_readonly_only():
        return (SafetyClass.READ_ONLY,)
    return (SafetyClass.READ_ONLY, SafetyClass.REVERSIBLE)


def _retrieve_candidates(query: str, registry) -> list[ToolSpec]:
    allowed = set(_allowed_safety_classes())
    ranked = [s for s in registry.select(query, k=_DEFAULT_K) if s.safety_class in allowed]
    by_name = {s.name: s for s in ranked}
    for core in CORE_TOOL_NAMES:
        spec = registry.get(core)
        if spec is not None and spec.safety_class in allowed:
            by_name[core] = spec
    return list(by_name.values())


def _validate_tool_call(
    registry,
    name: str,
    args: dict[str, Any],
    *,
    candidate_names: frozenset[str],
) -> tuple[ToolSpec | None, str]:
    if name not in candidate_names:
        return None, "not_in_candidates"
    spec = registry.get(name)
    if spec is None:
        return None, "hallucinated_tool"
    allowed = set(_allowed_safety_classes())
    if spec.safety_class not in allowed:
        return None, "safety_class_blocked"
    try:
        from tools.adapters import validate_args

        validate_args(spec, args or {})
    except Exception as exc:
        return None, f"invalid_args:{exc}"
    return spec, ""


def _map_tool_to_request(spec: ToolSpec, args: dict[str, Any], *, user_text: str) -> CommandRequest:
    from tools.adapters import build_request

    req = build_request(spec, args or {})
    return req.model_copy(
        update={
            "raw_text": user_text,
            "classifier_source": "llm_tool_router_shadow",
        }
    )


def route_miss(
    text: str,
    *,
    rule_request: CommandRequest,
    session_context: object | None = None,
    llm_fn: LlmFn | None = None,
) -> RouterDecision:
    """
    Run retrieval → prompt → LLM → validate. Shadow stage never executes tools.
    """
    global _invoke_count
    t0 = time.perf_counter()
    with _lock:
        _invoke_count += 1
        breaker_open = _circuit_open

    candidates: list[str] = []
    if breaker_open:
        decision = RouterDecision(
            outcome="skipped",
            fallback_reason="circuit_breaker_open",
            circuit_breaker_open=True,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
        )
        _audit_shadow(text, rule_request, decision)
        return decision

    forbidden = scan_forbidden(text)
    if forbidden:
        decision = RouterDecision(
            outcome="refuse",
            refuse_reason=f"forbidden_action:{forbidden}",
            fallback_reason="user_forbidden_phrase",
            latency_ms=(time.perf_counter() - t0) * 1000.0,
        )
        _audit_shadow(text, rule_request, decision)
        _record_success()
        return decision

    try:
        from tools.catalog import build_default_tool_registry

        registry = build_default_tool_registry()
    except Exception as exc:
        _record_error()
        decision = RouterDecision(
            outcome="error",
            fallback_reason=f"registry_unavailable:{exc}",
            latency_ms=(time.perf_counter() - t0) * 1000.0,
        )
        _audit_shadow(text, rule_request, decision)
        return decision

    specs = _retrieve_candidates(text, registry)
    candidates = [s.name for s in specs]
    if not specs:
        decision = RouterDecision(
            outcome="no_tool",
            candidate_tools=tuple(candidates),
            fallback_reason="no_candidates",
            latency_ms=(time.perf_counter() - t0) * 1000.0,
        )
        _audit_shadow(text, rule_request, decision)
        _record_success()
        return decision

    system = build_system_prompt(allowed_classes=_allowed_safety_classes())
    user = build_user_prompt(
        user_text=text,
        candidates_block=render_candidate_tools(specs),
        context_snippet=_session_snippet(session_context),
    )

    raw = ""
    resolved = _resolve_llm_fn(llm_fn)
    try:
        if resolved is None:
            raise RuntimeError("no_llm_fn_configured")
        raw = resolved(system, user)
    except Exception as exc:
        _record_error()
        decision = RouterDecision(
            outcome="error",
            candidate_tools=tuple(candidates),
            fallback_reason=f"llm_error:{type(exc).__name__}",
            latency_ms=(time.perf_counter() - t0) * 1000.0,
        )
        _audit_shadow(text, rule_request, decision, parse_result=f"llm_error:{type(exc).__name__}")
        return decision

    kind, payload = parse_router_output(raw)
    parse_result = kind
    if kind == "malformed":
        retry_raw = ""
        try:
            if resolved is not None:
                retry_raw = resolved(
                    system,
                    user + "\n\nYour previous reply was invalid. Return one JSON object only.",
                )
                kind, payload = parse_router_output(retry_raw)
                parse_result = kind
        except Exception:
            pass
        if kind == "malformed":
            decision = RouterDecision(
                outcome="no_tool",
                candidate_tools=tuple(candidates),
                fallback_reason="malformed_llm_output",
                latency_ms=(time.perf_counter() - t0) * 1000.0,
            )
            _audit_shadow(
                text,
                rule_request,
                decision,
                parse_result=parse_result,
            )
            _record_success()
            return decision

    if kind == "clarify":
        decision = RouterDecision(
            outcome="clarify",
            clarify_question=str(payload.get("question") or ""),
            candidate_tools=tuple(candidates),
            latency_ms=(time.perf_counter() - t0) * 1000.0,
        )
        _audit_shadow(text, rule_request, decision, parse_result=parse_result)
        _record_success()
        return decision

    if kind == "refuse":
        decision = RouterDecision(
            outcome="refuse",
            refuse_reason=str(payload.get("reason") or ""),
            candidate_tools=tuple(candidates),
            latency_ms=(time.perf_counter() - t0) * 1000.0,
        )
        _audit_shadow(text, rule_request, decision, parse_result=parse_result)
        _record_success()
        return decision

    if kind == "no_tool":
        decision = RouterDecision(
            outcome="no_tool",
            candidate_tools=tuple(candidates),
            latency_ms=(time.perf_counter() - t0) * 1000.0,
        )
        _audit_shadow(text, rule_request, decision, parse_result=parse_result)
        _record_success()
        return decision

    if kind == "tool_call":
        name = str(payload.get("name") or "")
        args = dict(payload.get("args") or {})
        candidate_set = frozenset(candidates)
        spec, reject = _validate_tool_call(
            registry,
            name,
            args,
            candidate_names=candidate_set,
        )
        if spec is None:
            outcome = "no_tool" if reject in {"not_in_candidates", "hallucinated_tool"} else "clarify"
            decision = RouterDecision(
                outcome=outcome,
                clarify_question="Could you rephrase that?" if outcome == "clarify" else "",
                candidate_tools=tuple(candidates),
                fallback_reason=reject or "invalid_tool_call",
                latency_ms=(time.perf_counter() - t0) * 1000.0,
            )
            _audit_shadow(text, rule_request, decision, parse_result=parse_result)
            _record_success()
            return decision

        mapped = _map_tool_to_request(spec, args, user_text=text)
        would_execute = False  # Stage 1 shadow: never execute
        decision = RouterDecision(
            outcome="tool_call",
            tool_name=spec.name,
            tool_args=args,
            mapped_intent=mapped.intent.value,
            candidate_tools=tuple(candidates),
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            shadow=True,
            executed=False,
        )
        _audit_shadow(
            text,
            rule_request,
            decision,
            parse_result=parse_result,
            shadow_would_execute=would_execute,
        )
        _record_success()
        return decision

    decision = RouterDecision(
        outcome="no_tool",
        candidate_tools=tuple(candidates),
        fallback_reason="unknown_kind",
        latency_ms=(time.perf_counter() - t0) * 1000.0,
    )
    _audit_shadow(text, rule_request, decision, parse_result=parse_result)
    _record_success()
    return decision


def shadow_route_miss(
    text: str,
    *,
    rule_request: CommandRequest,
    session_context: object | None = None,
    llm_fn: LlmFn | None = None,
) -> RouterDecision:
    """Shadow entry: log decision only; production routing stays on rule_request."""
    if not should_invoke_shadow_router():
        return RouterDecision(outcome="skipped", fallback_reason="shadow_disabled")
    return route_miss(
        text,
        rule_request=rule_request,
        session_context=session_context,
        llm_fn=llm_fn,
    )


def maybe_shadow_route_on_miss(
    text: str,
    classifier_request: CommandRequest,
    *,
    session_context: object | None = None,
    llm_fn: LlmFn | None = None,
) -> None:
    """Invoke shadow router on classifier miss without changing routing."""
    if not should_invoke_shadow_router():
        return
    if not is_classifier_miss(classifier_request):
        return
    shadow_route_miss(
        text,
        rule_request=classifier_request,
        session_context=session_context,
        llm_fn=_resolve_llm_fn(llm_fn),
    )


def _session_snippet(session_context: object | None) -> str:
    if session_context is None:
        return ""
    try:
        last = getattr(session_context, "last_commands", None) or []
        lines = [str(x)[:80] for x in list(last)[-3:]]
        return "\n".join(lines)
    except Exception:
        return ""


def _audit_shadow(
    text: str,
    rule_request: CommandRequest,
    decision: RouterDecision,
    *,
    parse_result: str = "",
    shadow_would_execute: bool = False,
) -> None:
    tool_router_audit.record_shadow_decision(
        user_text=text,
        classifier_intent=rule_request.intent.value,
        classifier_confidence=float(rule_request.confidence or 0.0),
        classifier_source=rule_request.classifier_source,
        outcome=decision.outcome,
        candidate_tools=list(decision.candidate_tools),
        selected_tool=decision.tool_name,
        selected_args=decision.tool_args,
        mapped_intent=decision.mapped_intent,
        shadow_would_execute=shadow_would_execute,
        latency_ms=decision.latency_ms,
        fallback_reason=decision.fallback_reason,
        parse_result=parse_result,
        circuit_breaker_open=decision.circuit_breaker_open,
    )
