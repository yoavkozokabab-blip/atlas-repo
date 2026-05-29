"""Phase 78 — the additive Tool Registry.

Central authority for registering and invoking tools. It enforces every safety
invariant at registration and gates execution by safety_class at invocation.
It does NOT replace ActionRegistry or the classifier — invocation dispatches
through the existing ActionRegistry path. LLM routing is a later phase and stays
disabled here.
"""

from __future__ import annotations

import re
import threading
import time

from core.logger import setup_logger
from tools import adapters, audit, verification
from tools.spec import SafetyClass, SideEffect, ToolResult, ToolSpec, ToolStatus

logger = setup_logger("jarvis.tools.registry")

_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")

# Legacy handlers that historically counted MOCK output as success — a tool may
# never map to these (no-mock-success guarantee at the catalog level).
MOCK_SUCCESS_DENYLIST: frozenset[str] = frozenset({
    "find_information_about",
    "extract_key_facts_from_this_page",
})

# Default: only read-only tools may run unless the caller explicitly opts in.
_READ_ONLY_ONLY = frozenset({SafetyClass.READ_ONLY})


class ToolRegistrationError(ValueError):
    """Raised when a ToolSpec violates a registration invariant."""


class ToolRegistry:
    def __init__(self, *, action_registry=None) -> None:
        self._tools: dict[str, ToolSpec] = {}
        self._lock = threading.Lock()
        self._action_registry = action_registry  # injected; lazily built if None

    # -- registration ----------------------------------------------------
    def register(self, spec: ToolSpec) -> None:
        self._validate(spec)
        with self._lock:
            if spec.name in self._tools:
                raise ToolRegistrationError(f"duplicate tool name: {spec.name}")
            self._tools[spec.name] = spec
        logger.debug("ToolRegistry: registered %s (%s)", spec.name, spec.safety_class.value)

    def _validate(self, spec: ToolSpec) -> None:
        if not _NAME_RE.match(spec.name):
            raise ToolRegistrationError(f"malformed tool name: {spec.name!r}")
        if spec.safety_class == SafetyClass.IRREVERSIBLE_FORBIDDEN:
            raise ToolRegistrationError(f"FORBIDDEN tools may not be registered: {spec.name}")
        if spec.side_effects == SideEffect.EXTERNAL_IRREVERSIBLE:
            raise ToolRegistrationError(f"irreversible external side effect forbidden: {spec.name}")
        if spec.maps_to_intent in MOCK_SUCCESS_DENYLIST:
            raise ToolRegistrationError(
                f"tool {spec.name} maps to denylisted mock-success handler "
                f"'{spec.maps_to_intent}'"
            )
        # Mapped intent must be implemented AND have a registered handler.
        try:
            from config import IMPLEMENTED_INTENTS
        except Exception:
            IMPLEMENTED_INTENTS = frozenset()
        if spec.maps_to_intent not in IMPLEMENTED_INTENTS:
            raise ToolRegistrationError(
                f"tool {spec.name} maps to unimplemented intent '{spec.maps_to_intent}'"
            )
        reg = self._get_action_registry()
        if not reg.has(spec.maps_to_intent):
            raise ToolRegistrationError(
                f"tool {spec.name} maps to intent '{spec.maps_to_intent}' with no handler"
            )

    # -- lookup ----------------------------------------------------------
    def get(self, name: str) -> ToolSpec | None:
        with self._lock:
            return self._tools.get(name)

    def all(self) -> list[ToolSpec]:
        with self._lock:
            return list(self._tools.values())

    def names(self) -> list[str]:
        with self._lock:
            return sorted(self._tools)

    def by_safety_class(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for spec in self.all():
            counts[spec.safety_class.value] = counts.get(spec.safety_class.value, 0) + 1
        return counts

    def select(self, query: str, k: int = 10) -> list[ToolSpec]:
        """v1 retrieval stub: rank by query-token overlap with name/description/tags.

        (Embedding-based retrieval arrives with Phase 79; this keeps the API stable.)
        """
        q = {t for t in re.split(r"\W+", (query or "").lower()) if len(t) > 2}
        if not q:
            return self.all()[:k]

        def score(s: ToolSpec) -> int:
            hay = f"{s.name} {s.description} {' '.join(s.tags)}".lower()
            toks = {t for t in re.split(r"\W+", hay) if len(t) > 2}
            return len(q & toks)

        return sorted(self.all(), key=score, reverse=True)[:k]

    # -- invocation ------------------------------------------------------
    def _get_action_registry(self):
        if self._action_registry is None:
            from actions.registry import ActionRegistry

            self._action_registry = ActionRegistry()
        return self._action_registry

    def invoke(
        self,
        name: str,
        args: dict | None = None,
        *,
        allowed_classes: frozenset[SafetyClass] = _READ_ONLY_ONLY,
        approved: bool = False,
    ) -> ToolResult:
        args = args or {}
        spec = self.get(name)
        if spec is None or not spec.enabled:
            res = ToolResult(name, ToolStatus.ERROR, reason="unknown_or_disabled_tool",
                             summary=f"No such tool: {name}")
            audit.record_invocation(name, args, res)
            return res

        # Central safety gate.
        if spec.safety_class not in allowed_classes:
            res = ToolResult(name, ToolStatus.BLOCKED, reason="safety_class_not_allowed",
                             summary=f"{spec.safety_class.value} not permitted this turn")
            audit.record_invocation(name, args, res)
            return res
        if spec.requires_approval and not approved:
            res = ToolResult(name, ToolStatus.NEEDS_APPROVAL, reason="approval_required",
                             summary=f"{name} requires explicit approval before running")
            audit.record_invocation(name, args, res)
            return res

        # Schema validation (never execute on bad args).
        try:
            adapters.validate_args(spec, args)
        except adapters.SchemaValidationError as exc:
            res = ToolResult(name, ToolStatus.ERROR, reason="invalid_args", summary=str(exc))
            audit.record_invocation(name, args, res)
            return res

        # Execute through the existing ActionRegistry path.
        started = time.perf_counter()
        request = adapters.build_request(spec, args)
        command_result = self._get_action_registry().execute(request)
        result = adapters.map_result(spec, command_result)

        # Verify (no fake success: verification fails on any non-success result).
        ok, reason = verification.verify(spec, result)
        result.verified = ok
        result.verification_reason = reason

        latency_ms = int((time.perf_counter() - started) * 1000)
        audit.record_invocation(name, args, result, latency_ms=latency_ms)
        return result


# ---------------------------------------------------------------------------
# Process-wide singleton (built lazily / at startup by tools.catalog)
# ---------------------------------------------------------------------------

_registry: ToolRegistry | None = None
_registry_lock = threading.Lock()


def get_tool_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = ToolRegistry()
    return _registry


def reset_for_tests() -> None:
    global _registry
    with _registry_lock:
        _registry = None
