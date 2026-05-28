"""Parse parameters and resolve session follow-ups."""

from __future__ import annotations

import re
import unicodedata

from core.session import SessionState
from core.types import CommandRequest, Intent


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).strip().lower()
    return re.sub(r"\s+", " ", text)


_FOLLOW_UP_SUMMARIZE = frozenset(
    {"summarize it", "summarize this", "תסכם את זה", "תסכם את הלוג", "סכם את זה"}
)
_FOLLOW_UP_ERRORS = frozenset(
    {
        "show errors from that",
        "errors from that",
        "תראה שגיאות משם",
        "שגיאות משם",
        "תראה שגיאות מזה",
    }
)
_FOLLOW_UP_OPEN = frozenset(
    {
        "open that file",
        "open it",
        "פתח את הקובץ הזה",
        "פתח את זה",
        "פתחי את זה",
    }
)


def resolve_follow_up(text: str, session: SessionState) -> CommandRequest | None:
    """Map follow-up phrases to intents using safe session fields."""
    norm = _normalize(text)
    if norm in _FOLLOW_UP_SUMMARIZE:
        path = session.safe_path("last_opened_log") or session.safe_path("last_report_path")
        return CommandRequest(
            raw_text=text,
            intent=Intent.SUMMARIZE_LATEST_LOG,
            confidence=0.92,
            params={"path": str(path)} if path else {},
        )
    if norm in _FOLLOW_UP_ERRORS:
        path = session.safe_path("last_opened_log") or session.safe_path("last_report_path")
        return CommandRequest(
            raw_text=text,
            intent=Intent.SHOW_LAST_ERRORS,
            confidence=0.92,
            params={"path": str(path)} if path else {},
        )
    if norm in _FOLLOW_UP_OPEN:
        path = (
            session.safe_path("last_opened_file")
            or session.safe_path("last_opened_log")
            or session.safe_path("last_report_path")
        )
        if path is None:
            return CommandRequest(
                raw_text=text,
                intent=Intent.CLARIFY,
                confidence=0.5,
            )
        if path.is_dir():
            return CommandRequest(
                raw_text=text,
                intent=Intent.OPEN_PROJECT_FOLDER,
                confidence=0.9,
            )
        return CommandRequest(
            raw_text=text,
            intent=Intent.OPEN_LATEST_LOG,
            confidence=0.9,
            params={"path": str(path)},
        )
    return None


def _extract_after(prefixes: list[str], text: str) -> str:
    lower = text.lower()
    for prefix in prefixes:
        if lower.startswith(prefix):
            return text[len(prefix) :].strip()
        idx = lower.find(prefix)
        if idx >= 0:
            return text[idx + len(prefix) :].strip()
    return ""


def enrich_request(request: CommandRequest) -> CommandRequest:
    """Extract structured params from natural language."""
    text = request.raw_text
    intent = request.intent
    params = dict(request.params)

    if intent == Intent.SEARCH_PROJECT_FILE_BY_NAME:
        q = _extract_after(
            ["search file", "find file", "חפש קובץ", "חפש את הקובץ", "search_project_file"],
            text,
        )
        if q:
            params["query"] = q

    elif intent == Intent.SEARCH_CODE_TEXT:
        q = _extract_after(
            ["search code", "חפש בקוד", "search in code", "find in code"],
            text,
        )
        if q:
            params["query"] = q

    elif intent == Intent.FIND_FUNCTION:
        q = _extract_after(
            ["find function", "חפש פונקציה", "function ", "פונקציה "],
            text,
        )
        if q:
            params["name"] = q.split()[-1] if q.split() else q

    elif intent == Intent.FIND_CLASS:
        q = _extract_after(["find class", "חפש מחלקה", "class "], text)
        if q:
            params["name"] = q.split()[-1] if q.split() else q

    elif intent in (Intent.FIND_CONFIG_KEY,):
        q = _extract_after(
            ["find config", "config key", "איפה מוגדר", "where is"],
            text,
        )
        if q:
            params["key"] = q.split()[-1] if q.split() else q

    elif intent == Intent.SEARCH_TRADING_LOGS:
        q = _extract_after(
            ["search logs", "חפש בלוגים", "search trading logs", "in logs"],
            text,
        )
        if q:
            params["query"] = q
        elif "חפש בלוגים" in text:
            params["query"] = text.split("חפש בלוגים", 1)[-1].strip()

    elif intent == Intent.FIND_RISK_USAGE:
        for token in ("risk_per_trade", "max_total_open_risk", "exposure_limit"):
            if token in text:
                params["key"] = token

    elif intent == Intent.EXPLAIN_SKILL:
        for key in ("trading", "logs", "code", "files", "system", "assistant", "מסחר", "לוגים"):
            if key in text.lower():
                params["skill"] = "trading" if key == "מסחר" else (
                    "logs" if key == "לוגים" else key
                )
                break

    elif intent == Intent.HELP_FOR_COMMAND:
        q = _extract_after(
            ["help for", "help ", "תן עזרה על", "איך אני מריץ"],
            text,
        )
        if q:
            params["query"] = q

    elif intent in (Intent.REMEMBER_PREFERENCE, Intent.REMEMBER_FACT, Intent.SET_PREFERENCE):
        if "עברית" in text or "hebrew" in text.lower():
            params.setdefault("key", "language")
            params.setdefault("value", "hebrew")
        if "FINAL_ALGO" in text or "פרויקט" in text:
            params.setdefault("key", "project_root")
            m = re.search(r"[A-Z]:\\[^\s]+", text)
            if m:
                params.setdefault("value", m.group(0))

    elif intent == Intent.SEARCH_MEMORY:
        q = _extract_after(["חפש בזיכרון", "search memory", "what do you remember about"], text)
        if q:
            params["query"] = q

    elif intent == Intent.SEARCH_WEB_FOR:
        q = _extract_after(["search web for"], text)
        if q:
            params["query"] = q

    elif intent == Intent.FIND_INFORMATION_ABOUT:
        q = _extract_after(["find information about"], text)
        if q:
            params["query"] = q

    elif intent == Intent.CLICK_BUTTON_THAT_SAYS:
        from desktop.control_runtime import extract_button_label

        label = extract_button_label(text)
        if label:
            params["label"] = label

    elif intent == Intent.TYPE_THIS:
        from desktop.control_runtime import extract_type_text

        typed = extract_type_text(text)
        if typed:
            params["text"] = typed

    elif intent == Intent.OPEN_WEBSITE:
        from browser.url_parser import extract_first_url

        raw = extract_first_url(text)
        if raw:
            params["url"] = raw

    elif intent in (Intent.SET_ALIAS, Intent.DELETE_ALIAS):
        m = re.search(r"alias[:\s]+(.+?)\s*=\s*([\w_]+)", text, re.I)
        if m:
            params["alias"] = m.group(1).strip()
            params["intent"] = m.group(2).strip()

    elif intent == Intent.FORGET_MEMORY:
        m = re.search(r"שכח(?:\s+alias)?\s+(.+)|forget\s+(.+)", text, re.I)
        if m:
            params["key"] = (m.group(1) or m.group(2) or "").strip()

    if params != request.params:
        return request.model_copy(update={"params": params})
    return request
