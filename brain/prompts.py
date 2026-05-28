"""LLM prompts for intent classification (no execution)."""

from __future__ import annotations

from config import IMPLEMENTED_INTENTS


def build_intent_classification_prompt(
    user_text: str,
    *,
    session_context: dict | None = None,
) -> str:
    """Build a tight classification-only prompt with allowlisted intents."""
    intents_sorted = ", ".join(sorted(IMPLEMENTED_INTENTS))
    session_block = ""
    if session_context:
        conv = session_context.get("conversation") or {}
        recent = conv.get("recent_turns") or []
        recent_block = ""
        if recent:
            recent_block = "- recent_turns:\n" + "\n".join(
                f"  * {line}" for line in recent[-5:]
            )
        session_block = (
            "\nSession context (for follow-up phrases only):\n"
            f"- last_intent: {session_context.get('last_intent', '')}\n"
            f"- last_opened_log: {session_context.get('last_opened_log', '')}\n"
            f"- last_report_path: {session_context.get('last_report_path', '')}\n"
            f"{recent_block}\n"
        )

    return f"""You are NOT an agent. You do NOT execute commands. You do NOT run shell, PowerShell, Python, or scripts.
You ONLY classify the user's message into ONE allowed intent and return JSON.

Allowed intents (exactly these — no others):
{intents_sorted}

If unsure, use intent "clarification_needed" with confidence below 0.5.

Return JSON ONLY with this shape:
{{
  "intent": "<allowed intent or clarification_needed>",
  "confidence": 0.0,
  "params": {{}},
  "reason": "short explanation"
}}

params may include: query, name, key (strings only). No paths to execute.

FORBIDDEN in JSON (never include): shell, command, powershell, python, code, script, execute, path_to_run

Examples:
- "מה מצב הדאשבורד" -> show_dashboard_health
- "איפה מוגדר risk per trade" -> find_risk_usage
- "תראה שגיאות מהלוגים" -> show_last_errors
- "פתח את התיקייה של הפרויקט" -> open_project_folder
- "תסכם את זה" -> summarize_latest_log (follow-up)
- "חפש בקוד max_positions_reached" -> search_code_text with params.query
- "מה אתה יודע לעשות" -> show_capabilities
- "איזה פקודות מסחר יש" -> explain_skill with params.skill=trading
- "תן עזרה על לופ יומי" -> help_for_command with params.query
- "מה אתה זוכר" -> list_memory
- "show memory graph" -> show_memory_graph
- "search memory graph router" -> search_memory_graph with params.query
- "זכור ש..." -> remember_fact or remember_preference
- "קבע alias" -> set_alias
- "מה יש במסך" -> describe_screen
- "קרא את הטקסט במסך" -> read_screen_text
- "יש שגיאה במסך" -> detect_screen_errors
- "איזה חלון פתוח" -> get_active_window
- "צלם מסך" -> take_screenshot
- "תראה חלונות פתוחים" -> list_visible_windows
- "הרץ אבחון" -> run_diagnostics
- "אבחן דאשבורד" -> diagnose_dashboard
- "אבחן לופ מסחר" -> diagnose_trading_loop
- "מה הצעדים הבאים" -> suggest_next_steps
- "תראה workflows" -> list_workflows
- "תריץ בדיקת מערכת מסחר" -> run_workflow with params.workflow=trading_health_check
- "תסביר workflow מסחר" -> explain_workflow with params.workflow=trading_health_check
- "תפעיל הפעלה אוטומטית" -> enable_autostart (confirmation required)
- "מצב הפעלה אוטומטית" -> show_autostart_status
- "בדוק את ג'רוויס" -> run_jarvis_health_check
- "איזה אפליקציה בפוקוס" -> get_focused_app
- "תעביר פוקוס לכרום" -> focus_window (confirmation)
- "open chatgpt" -> open_website with params.website=chatgpt
- "open youtube" -> open_website with params.website=youtube
- "list websites" -> list_websites
{session_block}
User message:
{user_text}
"""


INTENT_CLASSIFICATION_SYSTEM = (
    "You are a strict intent classifier for a local Windows assistant. "
    "Output valid JSON only. Never output executable code or commands."
)
