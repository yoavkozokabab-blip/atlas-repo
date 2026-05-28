"""Memory, preferences, and alias management actions (explicit user intent only)."""

from __future__ import annotations

import re

from actions.base import BaseAction
from brain.aliases import get_aliases
from config import MEMORY_ENABLED
from core import confirmation
from brain.memory import get_memory
from brain.preferences import get_preferences
from brain.storage_safe import UnsafeStorageError
from memory.redaction import UnsafeMemoryError as MemoryUnsafeError
from core.results import result_blocked, result_confirmation_required, result_failed, result_success
from core.types import CommandRequest, CommandResult, Intent


def _extract_remember_content(text: str) -> tuple[str, str]:
    """Parse 'remember that X is Y' / 'זכור ש...' into key-ish and value."""
    patterns = [
        r"זכור\s+ש(?:אני\s+)?(.+)",
        r"remember\s+(?:that\s+)?(.+)",
        r"זכור\s+(.+)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I | re.DOTALL)
        if m:
            content = m.group(1).strip()
            if "=" in content:
                key, val = content.split("=", 1)
                return key.strip(), val.strip()
            if " הוא " in content or " is " in content.lower():
                parts = re.split(r"\s+הוא\s+|\s+is\s+", content, maxsplit=1, flags=re.I)
                if len(parts) == 2:
                    return parts[0].strip(), parts[1].strip()
            return content[:60], content
    return "", text


class RememberPreferenceAction(BaseAction):
    intent = Intent.REMEMBER_PREFERENCE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        if request.confirmed:
            payload = request.params.get("remember_payload", {}) or {}
            request = request.model_copy(update={"params": payload, "confirmed": False})
        key = str(request.params.get("key") or "user_preference").strip()
        value = str(request.params.get("value") or "").strip()
        if not value:
            _, value = _extract_remember_content(request.raw_text)
        if not value:
            return result_failed(Intent.REMEMBER_PREFERENCE, "Nothing to remember. Specify a preference.")
        if _is_sensitive_memory_text(f"{key} {value} {request.raw_text}") and not request.confirmed:
            cid = confirmation.create_confirmation(
                "remember_sensitive_preference",
                {
                    "raw_text": request.raw_text,
                    "params": {"remember_payload": dict(request.params)},
                },
            )
            return result_confirmation_required(
                Intent.REMEMBER_PREFERENCE,
                f"This looks sensitive. Save preference anyway? Reply yes/confirm or no/cancel (id: {cid}).",
                cid,
                next_suggestions=[f"yes ({cid})", "no"],
            )
        try:
            get_preferences().set_preference(key, value)
            get_memory().remember(
                f"{key}: {value}",
                category="user_preference",
                tags=[key],
                source="user",
                importance=0.85,
                confidence=0.95,
                sensitive=_is_sensitive_memory_text(f"{key} {value}"),
            )
        except UnsafeStorageError as exc:
            return result_blocked(Intent.REMEMBER_PREFERENCE, str(exc), error=str(exc))
        return result_success(
            Intent.REMEMBER_PREFERENCE,
            f"Saved preference '{key}'.",
            data={"key": key},
        )


class RememberFactAction(BaseAction):
    intent = Intent.REMEMBER_FACT.value

    def execute(self, request: CommandRequest) -> CommandResult:
        if request.confirmed:
            payload = request.params.get("remember_payload", {}) or {}
            request = request.model_copy(update={"params": payload, "confirmed": False})
        key = str(request.params.get("key") or "").strip()
        value = str(request.params.get("value") or "").strip()
        if not key or not value:
            k, v = _extract_remember_content(request.raw_text)
            key = key or k or "fact"
            value = value or v
        is_sensitive = _is_sensitive_memory_text(f"{key} {value} {request.raw_text}")
        if is_sensitive and not request.confirmed:
            cid = confirmation.create_confirmation(
                "remember_sensitive_fact",
                {
                    "raw_text": request.raw_text,
                    "params": {"remember_payload": {"key": key, "value": value}},
                },
            )
            return result_confirmation_required(
                Intent.REMEMBER_FACT,
                f"This looks sensitive. Save fact anyway? Reply yes/confirm or no/cancel (id: {cid}).",
                cid,
                next_suggestions=[f"yes ({cid})", "no"],
            )
        try:
            category = _memory_category_from_text(request.raw_text, key=key)
            ttl_seconds = 24 * 3600 if category == "temporary_fact" else None
            get_memory().remember(
                f"{key}: {value}",
                category=category,
                tags=[key],
                source="user",
                importance=_importance_score(value=value, raw_text=request.raw_text),
                confidence=_confidence_score(raw_text=request.raw_text),
                ttl_seconds=ttl_seconds,
                sensitive=is_sensitive,
            )
        except UnsafeStorageError as exc:
            return result_blocked(Intent.REMEMBER_FACT, str(exc), error=str(exc))
        return result_success(
            Intent.REMEMBER_FACT,
            f"Remembered fact '{key}'.",
            data={"key": key},
        )


class ForgetMemoryAction(BaseAction):
    intent = Intent.FORGET_MEMORY.value

    def execute(self, request: CommandRequest) -> CommandResult:
        key = str(request.params.get("key") or request.params.get("query") or "").strip()
        if not key:
            key = str(request.params.get("value") or "").strip()
        if not key and "שכח" in request.raw_text:
            return result_failed(Intent.FORGET_MEMORY, "Specify what to forget (key).")
        mem = get_memory()
        if MEMORY_ENABLED:
            count = mem.forget(key)
            if count:
                return result_success(
                    Intent.FORGET_MEMORY,
                    f"Memory entry hidden (soft-delete): {count} match(es) for '{key}'.",
                )
        elif mem.delete_memory(key):
            return result_success(Intent.FORGET_MEMORY, f"Forgot memory entry '{key}'.")
        prefs = get_preferences()
        if prefs.delete_preference(key):
            return result_success(Intent.FORGET_MEMORY, f"Forgot preference '{key}'.")
        return result_failed(Intent.FORGET_MEMORY, f"No memory entry '{key}'.")


class ListMemoryAction(BaseAction):
    intent = Intent.LIST_MEMORY.value

    def execute(self, request: CommandRequest) -> CommandResult:
        mem = get_memory()
        raw = (request.raw_text or "").lower()
        if "show memory debug" in raw:
            items = mem.list_visible(limit=200) if hasattr(mem, "list_visible") else []
            body = [
                "Memory debug:",
                f"  entries_visible: {len(items)}",
            ]
            by_cat: dict[str, int] = {}
            for item in items:
                by_cat[item.category] = by_cat.get(item.category, 0) + 1
            for cat, count in sorted(by_cat.items()):
                body.append(f"  - {cat}: {count}")
            if items:
                avg_importance = sum(i.importance for i in items) / len(items)
                avg_confidence = sum(i.confidence for i in items) / len(items)
                temp_count = sum(1 for i in items if i.expires_at)
                body.append(f"  avg_importance: {avg_importance:.2f}")
                body.append(f"  avg_confidence: {avg_confidence:.2f}")
                body.append(f"  temporary_entries: {temp_count}")
            return result_success(Intent.LIST_MEMORY, "\n".join(body), data={"count": len(items), "debug": True})
        if MEMORY_ENABLED and hasattr(mem, "format_summary"):
            body = mem.format_summary()
            count = len(mem.list_visible()) if hasattr(mem, "list_visible") else 0
            return result_success(Intent.LIST_MEMORY, body, data={"count": count})
        items = mem.list_memory()
        if not items:
            return result_success(Intent.LIST_MEMORY, "No stored memory entries.")
        lines = ["Stored memory:"]
        for item in items:
            val = str(item.get("value", ""))[:100]
            lines.append(f"  - [{item.get('category', 'fact')}] {item['key']}: {val}")
        return result_success(Intent.LIST_MEMORY, "\n".join(lines), data={"count": len(items)})


class SearchMemoryAction(BaseAction):
    intent = Intent.SEARCH_MEMORY.value

    def execute(self, request: CommandRequest) -> CommandResult:
        query = str(request.params.get("query") or request.raw_text).strip()
        for prefix in ("חפש בזיכרון", "search memory", "חפש בזיכרון"):
            if query.lower().startswith(prefix):
                query = query[len(prefix) :].strip()
        category = (request.params.get("category") or "").strip() or None
        tag = (request.params.get("tag") or "").strip() or None
        if MEMORY_ENABLED:
            from memory.search import search_memory_entries

            hits = search_memory_entries(
                query,
                category=category,
                tag=tag or None,
            )
        else:
            hits = get_memory().search_memory(query)
        if not hits:
            return result_success(
                Intent.SEARCH_MEMORY,
                f"No memory matches for '{query}'.",
            )
        lines = [f"Memory search '{query}':"]
        for item in hits:
            cat = item.get("category", "")
            lines.append(
                f"  - [{cat}] {item['key']}: {str(item.get('value', ''))[:120]}"
            )
        return result_success(Intent.SEARCH_MEMORY, "\n".join(lines))


def _is_sensitive_memory_text(text: str) -> bool:
    lowered = (text or "").lower()
    return any(
        token in lowered
        for token in (
            "password",
            "token",
            "api key",
            "secret",
            "credit card",
            "ssn",
            "private key",
        )
    )


def _memory_category_from_text(raw_text: str, *, key: str) -> str:
    text = (raw_text or "").lower()
    k = (key or "").lower()
    if "temporary" in text or "for now" in text:
        return "temporary_fact"
    if "project" in text or "repo" in text:
        return "project_context"
    if "task" in text or "todo" in text:
        return "task_context"
    if "prefer" in text or "preference" in text:
        return "user_preference"
    if k in {"session", "context"}:
        return "short_term"
    return "short_term"


def _importance_score(*, value: str, raw_text: str) -> float:
    text = f"{raw_text} {value}".lower()
    score = 0.55
    if any(token in text for token in ("important", "urgent", "must", "critical")):
        score += 0.25
    if any(token in text for token in ("later", "maybe", "optional")):
        score -= 0.15
    return max(0.05, min(1.0, score))


def _confidence_score(*, raw_text: str) -> float:
    text = (raw_text or "").lower()
    if any(token in text for token in ("i think", "maybe", "probably", "not sure")):
        return 0.55
    return 0.9


class SetAliasAction(BaseAction):
    intent = Intent.SET_ALIAS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        alias = str(request.params.get("alias") or "").strip()
        intent_name = str(request.params.get("intent") or request.params.get("target") or "").strip()
        if not alias or not intent_name:
            m = re.search(
                r"alias[:\s]+(.+?)\s*=\s*(\w+)",
                request.raw_text,
                re.I,
            )
            if m:
                alias, intent_name = m.group(1).strip(), m.group(2).strip()
            else:
                m = re.search(
                    r"זכור\s+שכאשר\s+אני\s+אומר\s+(.+?)\s+אני\s+מתכוון\s+ל(.+)",
                    request.raw_text,
                    re.I,
                )
                if m:
                    alias = m.group(1).strip()
                    target = m.group(2).strip().lower()
                    intent_map = {
                        "פתוח דאשבורד": "open_trading_dashboard",
                        "פתח דאשבורד": "open_trading_dashboard",
                        "open dashboard": "open_trading_dashboard",
                    }
                    intent_name = intent_map.get(target, target.replace(" ", "_"))
        if not alias or not intent_name:
            return result_failed(
                Intent.SET_ALIAS,
                "Usage: set alias <phrase> = <intent>  e.g. פתח מסחר = open_trading_dashboard",
            )
        try:
            get_aliases().add_alias(alias, intent_name, request.params.get("params"))
        except UnsafeStorageError as exc:
            return result_blocked(Intent.SET_ALIAS, str(exc), error=str(exc))
        confirm_note = ""
        if intent_name in {"run_live_daily_loop", "shutdown_jarvis"}:
            confirm_note = " (confirmation still required when used)"
        return result_success(
            Intent.SET_ALIAS,
            f"Alias '{alias}' → {intent_name}{confirm_note}",
        )


class DeleteAliasAction(BaseAction):
    intent = Intent.DELETE_ALIAS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        alias = str(request.params.get("alias") or request.params.get("query") or "").strip()
        if not alias:
            m = re.search(r"שכח\s+alias\s+(.+)|delete\s+alias\s+(.+)", request.raw_text, re.I)
            if m:
                alias = (m.group(1) or m.group(2) or "").strip()
        if not alias:
            return result_failed(Intent.DELETE_ALIAS, "Specify alias to delete.")
        if get_aliases().delete_alias(alias):
            return result_success(Intent.DELETE_ALIAS, f"Deleted alias '{alias}'.")
        return result_failed(Intent.DELETE_ALIAS, f"Alias '{alias}' not found.")


class ListAliasesAction(BaseAction):
    intent = Intent.LIST_ALIASES.value

    def execute(self, request: CommandRequest) -> CommandResult:
        items = get_aliases().list_aliases()
        if not items:
            return result_success(Intent.LIST_ALIASES, "No aliases defined.")
        lines = ["Aliases (→ allowlisted intents only):"]
        for item in items:
            lines.append(f"  - '{item['alias']}' → {item['intent']}")
        return result_success(Intent.LIST_ALIASES, "\n".join(lines))


class SetPreferenceAction(BaseAction):
    intent = Intent.SET_PREFERENCE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        key = str(request.params.get("key") or "").strip()
        value = str(request.params.get("value") or "").strip()
        if not key or not value:
            return result_failed(Intent.SET_PREFERENCE, "Requires key and value in params.")
        try:
            get_preferences().set_preference(key, value)
        except UnsafeStorageError as exc:
            return result_blocked(Intent.SET_PREFERENCE, str(exc), error=str(exc))
        return result_success(Intent.SET_PREFERENCE, f"Preference '{key}' saved.")


class ListPreferencesAction(BaseAction):
    intent = Intent.LIST_PREFERENCES.value

    def execute(self, request: CommandRequest) -> CommandResult:
        data = get_preferences().list_preferences()
        if not data:
            return result_success(Intent.LIST_PREFERENCES, "No preferences stored.")
        lines = ["Preferences:"]
        for key, meta in sorted(data.items()):
            val = meta.get("value", meta) if isinstance(meta, dict) else meta
            lines.append(f"  - {key}: {str(val)[:100]}")
        return result_success(Intent.LIST_PREFERENCES, "\n".join(lines))


class ForgetPreferenceAction(BaseAction):
    intent = Intent.FORGET_PREFERENCE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        key = str(request.params.get("key") or "").strip()
        if not key:
            return result_failed(Intent.FORGET_PREFERENCE, "Specify preference key.")
        if get_preferences().delete_preference(key):
            return result_success(Intent.FORGET_PREFERENCE, f"Forgot preference '{key}'.")
        return result_failed(Intent.FORGET_PREFERENCE, f"Preference '{key}' not found.")
