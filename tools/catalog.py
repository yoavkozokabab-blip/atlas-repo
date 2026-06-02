"""Phase 78 — the first 40 tools (mostly READ_ONLY, 0 FORBIDDEN).

Every tool maps to an already-implemented, committed intent and is dispatched
through the existing ActionRegistry path. No tool maps to a mock-success handler
(enforced centrally in tools/registry.py). LLM routing is NOT wired here.
"""

from __future__ import annotations

from tools.registry import ToolRegistry, get_tool_registry
from tools.spec import (
    AuthKind,
    CostHint,
    LatencyHint,
    SafetyClass,
    SideEffect,
    ToolSpec,
    Verification,
)

RO = SafetyClass.READ_ONLY
REV = SafetyClass.REVERSIBLE
S = Verification.RESULT_SUCCESS
NES = Verification.NON_EMPTY_SUMMARY
PR = Verification.PROVIDER_REAL


def _t(name, intent, *, sc=RO, se=SideEffect.NONE, verify=(S,), desc="",
       args=None, required=None, raw="", cost=CostHint.CHEAP, lat=LatencyHint.FAST,
       tags=(), auth=AuthKind.NONE) -> ToolSpec:
    props = {a: {"type": "string"} for a in (args or [])}
    return ToolSpec(
        name=name, version=1, description=desc or name,
        input_schema={"properties": props, "required": list(required or [])},
        output_schema={},
        safety_class=sc, side_effects=se, idempotent=True,
        verification=tuple(verify), maps_to_intent=intent,
        arg_map={}, raw_text_template=raw, auth=auth,
        cost_hint=cost, latency_hint=lat, tags=tuple(tags),
    )


def default_specs() -> list[ToolSpec]:
    return [
        # --- assistant / discoverability ---
        _t("assistant.capabilities", "show_capabilities", desc="List what JARVIS can do.", tags=("assistant",)),
        _t("assistant.help", "help_for_command", desc="Explain how to use a command.",
           args=["topic"], raw="help for {topic}", tags=("assistant",)),
        _t("assistant.list_skills", "list_skills", desc="List available skills.", tags=("assistant",)),
        # --- memory ---
        _t("memory.recall", "search_memory", verify=(S, NES), desc="Recall remembered facts matching a query.",
           args=["query"], required=["query"], raw="search memory {query}", tags=("memory",)),
        _t("memory.remember", "remember_fact", se=SideEffect.LOCAL_WRITE, desc="Remember a fact (local, reversible).",
           args=["text"], required=["text"], raw="remember that {text}", tags=("memory",)),
        _t("memory.show", "show_memory", desc="Show stored memory.", tags=("memory",)),
        _t("memory.list", "list_memory", desc="List memory entries.", tags=("memory",)),
        _t("memory.set_preference", "set_preference", se=SideEffect.LOCAL_WRITE, desc="Set a user preference.",
           args=["text"], required=["text"], raw="set preference {text}", tags=("memory",)),
        _t("memory.list_preferences", "list_preferences", desc="List user preferences.", tags=("memory",)),
        _t("memory.set_alias", "set_alias", se=SideEffect.LOCAL_WRITE, desc="Set a command alias.",
           args=["text"], required=["text"], raw="set alias {text}", tags=("memory",)),
        _t("memory.list_aliases", "list_aliases", desc="List command aliases.", tags=("memory",)),
        _t("session.summarize", "summarize_session", verify=(S, NES), desc="Summarize this session.", tags=("session",)),
        _t("session.recall", "what_were_we_doing", desc="Recall what we were doing.", tags=("session",)),
        # --- code intelligence ---
        _t("code.find_function", "find_function", desc="Find a function in the project.",
           args=["name"], required=["name"], raw="find function {name}", tags=("code",)),
        _t("code.find_class", "find_class", desc="Find a class in the project.",
           args=["name"], required=["name"], raw="find class {name}", tags=("code",)),
        _t("code.search_text", "search_code_text", desc="Search code text.",
           args=["query"], required=["query"], raw="search code {query}", tags=("code",)),
        _t("code.search_file", "search_project_file_by_name", desc="Find a project file by name.",
           args=["name"], required=["name"], raw="search file {name}", tags=("code",)),
        _t("code.inspect_project", "inspect_project", verify=(S, NES), desc="Inspect the current project.", tags=("code",)),
        # --- system / health ---
        _t("system.status", "show_system_status", desc="Show CPU/RAM/system status.", tags=("system",)),
        _t("system.disk", "show_disk_usage", desc="Show disk usage.", tags=("system",)),
        _t("system.network", "show_network_status", desc="Show network status.", tags=("system",)),
        _t("system.health", "show_system_health", desc="Show overall system health.", tags=("system",)),
        _t("system.jarvis_health", "run_jarvis_health_check", desc="Run the JARVIS health check.", tags=("system",)),
        _t("system.watchdog_status", "show_watchdog_status", desc="Show watchdog status.", tags=("system",)),
        _t("system.runtime_status", "show_runtime_status", desc="Show runtime status.", tags=("system",)),
        # --- screen (read-only) ---
        _t("screen.describe", "describe_screen", se=SideEffect.EXTERNAL_READ, verify=(S, NES),
           desc="Describe what is on screen.", cost=CostHint.NETWORK, tags=("screen",)),
        _t("screen.read_text", "read_screen_text", se=SideEffect.EXTERNAL_READ, verify=(S, NES),
           desc="Read text visible on screen.", tags=("screen",)),
        _t("screen.active_window", "get_active_window", se=SideEffect.EXTERNAL_READ,
           desc="Get the active window info.", tags=("screen",)),
        _t("screen.list_windows", "list_visible_windows", se=SideEffect.EXTERNAL_READ,
           desc="List visible windows.", tags=("screen",)),
        # --- diagnostics ---
        _t("diagnostics.run", "run_diagnostics", desc="Run read-only diagnostics.", tags=("diagnostics",)),
        _t("diagnostics.explain_last_failure", "explain_last_failure", desc="Explain the last failure.", tags=("diagnostics",)),
        _t("diagnostics.recent_commands", "show_recent_commands", desc="Show recent commands.", tags=("diagnostics",)),
        # --- trading (read-only) ---
        _t("trading.dashboard_health", "show_dashboard_health", se=SideEffect.EXTERNAL_READ,
           desc="Show trading dashboard health.", tags=("trading",)),
        _t("trading.open_positions", "show_open_positions", se=SideEffect.EXTERNAL_READ,
           desc="Show open trading positions.", tags=("trading",)),
        _t("trading.last_errors", "show_last_errors", desc="Show last trading errors.", tags=("trading",)),
        _t("trading.latest_report", "show_latest_live_report", desc="Show the latest live report.", tags=("trading",)),
        _t("trading.search_logs", "search_trading_logs", desc="Search trading logs.",
           args=["query"], required=["query"], raw="search trading logs {query}", tags=("trading",)),
        # --- research (Phase 71/72 no-mock path; preview is RO, run is approval-gated) ---
        _t("research.plan", "plan_tool_task", desc="Preview a bounded read-only web research plan (no execution).",
           args=["goal"], required=["goal"], raw="plan tool task {goal}", tags=("research", "web")),
        _t("research.run", "run_tool_task", sc=REV, se=SideEffect.EXTERNAL_REVERSIBLE, verify=(PR,),
           desc="Run a bounded read-only web research task (search, open, summarize). Approval-gated.",
           args=["goal"], required=["goal"], raw="run tool task {goal}",
           cost=CostHint.NETWORK, lat=LatencyHint.SLOW, tags=("research", "web")),
        _t("research.show_last", "show_last_tool_run", desc="Show the last web research run (read-only).", tags=("research", "web")),
        # --- project intelligence (Phase 79+) ---
        _t(
            "project.answer_question",
            "answer_project_question",
            sc=RO,
            se=SideEffect.NONE,
            verify=(S, NES),
            desc=(
                "Answer a free-form question about the JARVIS project: phase history, "
                "architecture decisions, risks, roadmap, codebase state, or what to build next. "
                "Reads reports/, README files, key module files, and git log. "
                "Read-only. Never executes code or opens browsers."
            ),
            args=["query"],
            required=["query"],
            raw="answer project question about {query}",
            lat=LatencyHint.SLOW,
            tags=("project", "intelligence", "architecture", "builder"),
        ),
    ]


def build_default_tool_registry(*, action_registry=None) -> ToolRegistry:
    """Register the default catalog into the process-wide registry and return it."""
    reg = get_tool_registry()
    if action_registry is not None:
        reg._action_registry = action_registry  # injected (tests / shared instance)
    for spec in default_specs():
        if reg.get(spec.name) is None:
            reg.register(spec)
    return reg
