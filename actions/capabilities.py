"""Read-only capability discovery actions (skill registry)."""

from __future__ import annotations

import re

from actions.base import BaseAction
from config import CONFIRMATION_REQUIRED_INTENTS, IMPLEMENTED_INTENTS, LLM_CLASSIFIER_ENABLED
from core.results import result_failed, result_success
from core.types import CommandRequest, CommandResult, Intent
from skills.registry import get_skill_registry

from brain.intent_classifier import classify_rules

_FEATURE_GROUPS = [
    (
        "Voice / TTS",
        [
            "Push-to-talk STT: python main.py --voice",
            "Optional TTS summary: --speak or TTS_ENABLED=true",
        ],
    ),
    (
        "LLM classifier",
        [
            f"Optional Ollama intent assist: {'enabled' if LLM_CLASSIFIER_ENABLED else 'disabled'}",
            "Classification JSON only — never executes commands",
        ],
    ),
    (
        "Vision",
        [
            "Read-only screen capture + OCR (VISION_ENABLED=true)",
            "No mouse/keyboard control; no external screenshot upload by default",
        ],
    ),
    (
        "Diagnostics",
        [
            "Cross-source read-only analysis: dashboard, logs, screen, runtime",
            "Suggests safe next commands only — no auto-fix or shell execution",
        ],
    ),
    (
        "Workflows",
        [
            "Predefined multi-step sequences (code-only, no LLM planning)",
            "Each step uses router path; confirm-required steps pause the workflow",
        ],
    ),
    (
        "Services",
        [
            "Windows Startup autostart via scripts/run_jarvis_tray.ps1 (confirm to enable/disable)",
            "Tray watchdog: read-only health, data/watchdog_status.json, notify on critical only",
        ],
    ),
    (
        "Computer control",
        [
            "Predefined window/clipboard only (COMPUTER_CONTROL_ENABLED=true)",
            "No click/type/hotkeys; confirm required for focus/minimize/maximize/copy/clear",
        ],
    ),
    (
        "Website launcher",
        [
            "Built-in https sites only (ChatGPT, YouTube, Gmail, …)",
            "webbrowser.open() — no Selenium/Playwright, no arbitrary URLs",
            "User-approved sites persist in data/approved_websites.json",
        ],
    ),
]


def _format_action_line(act) -> str:
    confirm = (
        " [confirm]"
        if act.permission_level.value == "confirm_required"
        else ""
    )
    blocked = " [not implemented]" if act.permission_level.value == "blocked" else ""
    return f"  - {act.name}{confirm}{blocked}: {act.description}"


class ShowCapabilitiesAction(BaseAction):
    intent = Intent.SHOW_CAPABILITIES.value

    def execute(self, request: CommandRequest) -> CommandResult:
        reg = get_skill_registry()
        lines = ["JARVIS capabilities (all execution via router + security + registry):\n"]

        for category, metas in sorted(reg.grouped_by_category().items()):
            lines.append(f"## {category}")
            for meta in metas:
                lines.append(f"Skill: {meta.name} — {meta.description}")
                for act in meta.actions[:6]:
                    lines.append(_format_action_line(act))
                if len(meta.actions) > 6:
                    lines.append(f"  ... +{len(meta.actions) - 6} more")
            lines.append("")

        for title, items in _FEATURE_GROUPS:
            lines.append(f"## {title}")
            for item in items:
                lines.append(f"  - {item}")
            lines.append("")

        summary = "\n".join(lines).strip()
        return result_success(
            Intent.SHOW_CAPABILITIES,
            summary,
            data={"skill_count": len(reg.list_skills())},
        )


class ListSkillsAction(BaseAction):
    intent = Intent.LIST_SKILLS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        reg = get_skill_registry()
        lines = ["Registered skills:"]
        for meta in reg.list_skills():
            lines.append(f"  - {meta.name} ({meta.category}): {len(meta.actions)} actions")
        return result_success(Intent.LIST_SKILLS, "\n".join(lines))


class ExplainSkillAction(BaseAction):
    intent = Intent.EXPLAIN_SKILL.value

    def execute(self, request: CommandRequest) -> CommandResult:
        skill_key = (
            request.params.get("skill")
            or request.params.get("query")
            or ""
        ).strip()
        if not skill_key:
            skill_key = _extract_skill_from_text(request.raw_text)

        reg = get_skill_registry()
        meta = reg.get_skill(skill_key) if skill_key else None
        if meta is None:
            return result_failed(
                Intent.EXPLAIN_SKILL,
                f"Unknown skill '{skill_key}'. Try: trading, logs, code, files, system, assistant.",
            )

        lines = [
            f"Skill: {meta.name} ({meta.category})",
            meta.description,
            "",
            "Actions:",
        ]
        confirm_list: list[str] = []
        for act in meta.actions:
            lines.append(_format_action_line(act))
            if act.examples:
                lines.append(f"    e.g. {act.examples[0]}")
            if act.intent in CONFIRMATION_REQUIRED_INTENTS:
                confirm_list.append(act.intent)

        if confirm_list:
            lines.append("")
            lines.append("Requires confirmation: " + ", ".join(confirm_list))

        lines.append("")
        lines.append(
            "Safety: run the phrase as a normal command — router validates allowlist and confirmation."
        )
        return result_success(
            Intent.EXPLAIN_SKILL,
            "\n".join(lines),
            data={"skill": meta.name},
        )


class HelpForCommandAction(BaseAction):
    intent = Intent.HELP_FOR_COMMAND.value

    def execute(self, request: CommandRequest) -> CommandResult:
        query = (
            request.params.get("query")
            or request.params.get("intent")
            or request.raw_text
        ).strip()
        intent_name = _resolve_intent_from_query(query)
        reg = get_skill_registry()

        if not intent_name:
            return result_failed(
                Intent.HELP_FOR_COMMAND,
                "Could not match a command. Try naming the action, e.g. 'run live daily loop'.",
            )

        act = reg.get_action(intent_name)
        rule = classify_rules(query)

        lines = [f"Help for: {intent_name}"]
        if act:
            lines.append(f"Description: {act.description}")
            if act.examples:
                lines.append("Examples:")
                for ex in act.examples[:4]:
                    lines.append(f"  - {ex}")
        else:
            lines.append("No skill metadata entry (may still be allowlisted).")

        if intent_name in CONFIRMATION_REQUIRED_INTENTS:
            lines.append("")
            lines.append(
                "Confirmation required: reply yes / confirm / כן after the command."
            )
        elif intent_name not in IMPLEMENTED_INTENTS:
            lines.append("")
            lines.append("Status: allowlisted but not implemented in this build.")
        else:
            lines.append("")
            lines.append("Safety: read-only or allowlisted script only — no arbitrary shell.")

        if rule.intent.value == intent_name:
            lines.append(f"Rule classifier match confidence: {rule.confidence:.2f}")

        return result_success(
            Intent.HELP_FOR_COMMAND,
            "\n".join(lines),
            data={"intent": intent_name},
        )


def _extract_skill_from_text(text: str) -> str:
    lower = text.lower()
    aliases = {
        "מסחר": "trading",
        "trading": "trading",
        "לוגים": "logs",
        "לוג": "logs",
        "logs": "logs",
        "קוד": "code",
        "code": "code",
        "קבצים": "files",
        "files": "files",
        "מערכת": "system",
        "system": "system",
        "עזרה": "assistant",
        "assistant": "assistant",
    }
    for key, skill in aliases.items():
        if key in lower:
            return skill
    m = re.search(r"skill\s+(\w+)|סקיל\s+(\w+)", lower)
    if m:
        return (m.group(1) or m.group(2) or "").strip()
    return ""


def _resolve_intent_from_query(query: str) -> str:
    rule = classify_rules(query)
    if rule.intent not in (Intent.UNKNOWN, Intent.CLARIFY):
        return rule.intent.value

    q = query.lower()
    hints: list[tuple[list[str], str]] = [
        (["לופ יומי", "daily loop", "run live daily"], "run_live_daily_loop"),
        (["לופ שבועי", "weekly loop"], "run_live_weekly_loop"),
        (["שגיאות", "last errors"], "show_last_errors"),
        (["דאשבורד", "dashboard health"], "show_dashboard_health"),
        (["capabilities", "מה אתה יודע"], "show_capabilities"),
    ]
    for keys, intent in hints:
        if any(k in q for k in keys):
            return intent

    reg = get_skill_registry()
    for act in reg.list_actions():
        if act.name.replace("_", " ") in q or act.name in q:
            return act.name
    return ""
