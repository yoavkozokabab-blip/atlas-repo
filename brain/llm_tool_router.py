"""Phase 79 Stage 1 — Shadow LLM tool router (decide + log only; never execute)."""

from __future__ import annotations

import concurrent.futures
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
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

STAGE1_SHADOW_ONLY = True

_DEFAULT_K = 10
_CIRCUIT_BREAKER_THRESHOLD = 3
_DEFAULT_LLM_TIMEOUT_S = 4.0

_lock = threading.Lock()
_consecutive_errors = 0
_circuit_open = False
_invoke_count = 0
_injected_llm_fn: LlmFn | None = None
_injection_allowed = False
_test_registry_override: Any | None = None
_registry_initialized = False


class ShadowOnlyViolation(RuntimeError):
    """Raised if Stage 1 shadow routing attempts execution."""


class TestInjectionForbidden(RuntimeError):
    """Raised when test-only hooks are used outside allowed contexts."""


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


def allow_llm_fn_injection_for_tests() -> None:
    """Enable test/smoke-only LLM and registry injection hooks."""
    global _injection_allowed
    _injection_allowed = True


def is_test_injection_allowed() -> bool:
    return _injection_allowed


def reset_llm_tool_router_for_tests() -> None:
    global _consecutive_errors, _circuit_open, _invoke_count, _injected_llm_fn
    global _injection_allowed, _test_registry_override, _registry_initialized
    with _lock:
        _consecutive_errors = 0
        _circuit_open = False
        _invoke_count = 0
        _injected_llm_fn = None
        _injection_allowed = False
        _test_registry_override = None
        _registry_initialized = False
    tool_router_audit.reset_for_tests()


def set_llm_fn_for_tests(fn: LlmFn | None) -> None:
    """Inject deterministic LLM for tests/smoke (blocked in production)."""
    if not _injection_allowed:
        raise TestInjectionForbidden(
            "set_llm_fn_for_tests is only allowed in tests/smokes with allow_llm_fn_injection_for_tests()"
        )
    global _injected_llm_fn
    _injected_llm_fn = fn


def set_tool_registry_for_tests(registry: Any | None) -> None:
    """Inject ToolRegistry for tests/smoke (blocked in production)."""
    if not _injection_allowed:
        raise TestInjectionForbidden(
            "set_tool_registry_for_tests is only allowed in tests/smokes with allow_llm_fn_injection_for_tests()"
        )
    global _test_registry_override
    _test_registry_override = registry


def _resolve_llm_fn(llm_fn: LlmFn | None) -> LlmFn | None:
    if llm_fn is not None:
        if not _injection_allowed:
            raise TestInjectionForbidden(
                "Explicit llm_fn is only allowed in tests/smokes with allow_llm_fn_injection_for_tests()"
            )
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


def _llm_call_timeout_s() -> float:
    raw = os.getenv("LLM_TOOL_ROUTER_TIMEOUT_S", str(_DEFAULT_LLM_TIMEOUT_S))
    try:
        return max(0.05, float(raw))
    except (TypeError, ValueError):
        return _DEFAULT_LLM_TIMEOUT_S


def _call_llm_with_timeout(fn: LlmFn, system: str, user: str, *, timeout_s: float) -> str:
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = pool.submit(fn, system, user)
    try:
        return str(future.result(timeout=timeout_s))
    except concurrent.futures.TimeoutError as exc:
        future.cancel()
        raise TimeoutError("llm_timeout") from exc
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def _enforce_stage1_shadow_invariant(decision: RouterDecision) -> RouterDecision:
    if not STAGE1_SHADOW_ONLY:
        return decision
    if decision.executed:
        raise ShadowOnlyViolation("Phase 79 Stage 1 is shadow-only; execution is forbidden")
    if decision.shadow and not decision.executed:
        return decision
    return replace(decision, shadow=True, executed=False)


def _finalize_decision(decision: RouterDecision) -> RouterDecision:
    return _enforce_stage1_shadow_invariant(decision)


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


def _resolve_registry() -> Any:
    global _registry_initialized
    if _test_registry_override is not None:
        return _test_registry_override
    from tools.catalog import build_default_tool_registry
    from tools.registry import get_tool_registry

    registry = get_tool_registry()
    if not _registry_initialized:
        build_default_tool_registry()
        _registry_initialized = True
    return registry


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
        return None, f"invalid_args:{type(exc).__name__}"
    return spec, ""


def _call_llm_resolved(resolved: LlmFn, system: str, user: str) -> str:
    return _call_llm_with_timeout(resolved, system, user, timeout_s=_llm_call_timeout_s())


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

    def _done(decision: RouterDecision, *, parse_result: str = "") -> RouterDecision:
        decision = replace(decision, latency_ms=(time.perf_counter() - t0) * 1000.0)
        _audit_shadow(text, rule_request, decision, parse_result=parse_result)
        return _finalize_decision(decision)

    candidates: list[str] = []
    if breaker_open:
        return _done(
            RouterDecision(
                outcome="skipped",
                fallback_reason="circuit_breaker_open",
                circuit_breaker_open=True,
            )
        )

    forbidden = scan_forbidden(text)
    if forbidden:
        _record_success()
        return _done(
            RouterDecision(
                outcome="refuse",
                refuse_reason=f"forbidden_action:{forbidden}",
                fallback_reason="user_forbidden_phrase",
            )
        )

    try:
        registry = _resolve_registry()
    except Exception as exc:
        _record_error()
        return _done(
            RouterDecision(
                outcome="error",
                fallback_reason=f"registry_unavailable:{type(exc).__name__}",
            ),
            parse_result=f"registry_error:{type(exc).__name__}",
        )

    def _route_metadata_only() -> RouterDecision:
        """Select and validate a shadow decision without invoking any tool."""
        specs = _retrieve_candidates(text, registry)
        candidates = [s.name for s in specs]
        if not specs:
            _record_success()
            return _done(
                RouterDecision(
                    outcome="no_tool",
                    candidate_tools=tuple(candidates),
                    fallback_reason="no_candidates",
                )
            )

        system = build_system_prompt(allowed_classes=_allowed_safety_classes())
        user = build_user_prompt(
            user_text=text,
            candidates_block=render_candidate_tools(specs),
            context_snippet=_session_snippet(session_context),
        )

        resolved = _resolve_llm_fn(llm_fn)
        try:
            if resolved is None:
                raise RuntimeError("no_llm_fn_configured")
            raw = _call_llm_resolved(resolved, system, user)
        except TimeoutError:
            _record_error()
            return _done(
                RouterDecision(
                    outcome="error",
                    candidate_tools=tuple(candidates),
                    fallback_reason="llm_timeout",
                ),
                parse_result="llm_timeout",
            )
        except Exception as exc:
            _record_error()
            return _done(
                RouterDecision(
                    outcome="error",
                    candidate_tools=tuple(candidates),
                    fallback_reason=f"llm_error:{type(exc).__name__}",
                ),
                parse_result=f"llm_error:{type(exc).__name__}",
            )

        kind, payload = parse_router_output(raw)
        parse_result = kind
        if kind == "malformed":
            try:
                if resolved is not None:
                    retry_raw = _call_llm_resolved(
                        resolved,
                        system,
                        user + "\n\nYour previous reply was invalid. Return one JSON object only.",
                    )
                    kind, payload = parse_router_output(retry_raw)
                    parse_result = kind
            except TimeoutError:
                parse_result = "llm_timeout"
            except Exception:
                pass
            if kind == "malformed":
                _record_success()
                return _done(
                    RouterDecision(
                        outcome="no_tool",
                        candidate_tools=tuple(candidates),
                        fallback_reason="malformed_llm_output",
                    ),
                    parse_result=parse_result,
                )

        if kind == "clarify":
            _record_success()
            return _done(
                RouterDecision(
                    outcome="clarify",
                    clarify_question=str(payload.get("question") or ""),
                    candidate_tools=tuple(candidates),
                ),
                parse_result=parse_result,
            )

        if kind == "refuse":
            _record_success()
            return _done(
                RouterDecision(
                    outcome="refuse",
                    refuse_reason=str(payload.get("reason") or ""),
                    candidate_tools=tuple(candidates),
                ),
                parse_result=parse_result,
            )

        if kind == "no_tool":
            _record_success()
            return _done(
                RouterDecision(
                    outcome="no_tool",
                    candidate_tools=tuple(candidates),
                ),
                parse_result=parse_result,
            )

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
                _record_success()
                return _done(
                    RouterDecision(
                        outcome=outcome,
                        clarify_question="Could you rephrase that?" if outcome == "clarify" else "",
                        candidate_tools=tuple(candidates),
                        fallback_reason=reject or "invalid_tool_call",
                    ),
                    parse_result=parse_result,
                )

            _record_success()
            return _done(
                RouterDecision(
                    outcome="tool_call",
                    tool_name=spec.name,
                    tool_args=args,
                    mapped_intent=spec.maps_to_intent,
                    candidate_tools=tuple(candidates),
                    shadow=True,
                    executed=False,
                ),
                parse_result=parse_result,
            )

        _record_success()
        return _done(
            RouterDecision(
                outcome="no_tool",
                candidate_tools=tuple(candidates),
                fallback_reason="unknown_kind",
            ),
            parse_result=parse_result,
        )

    return _route_metadata_only()


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
        llm_fn=llm_fn,
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
