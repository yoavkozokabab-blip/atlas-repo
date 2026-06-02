"""Phase 37a — redacted conversational turn log (read-only for classify, no execution)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import (
    CONVERSATION_CLASSIFY_CONTEXT_TURNS,
    CONVERSATION_CONTEXT_PATH,
    CONVERSATION_ENABLED,
    CONVERSATION_MAX_RAW_CHARS,
    CONVERSATION_MAX_SUMMARY_CHARS,
    CONVERSATION_MAX_TURNS,
)
from core.logger import setup_logger
from vision.screen_redaction import redact_screen_text

logger = setup_logger("jarvis.conversation.context")


@dataclass
class ConversationTurn:
    timestamp: str
    intent: str
    status: str
    summary_excerpt: str = ""
    raw_text_excerpt: str = ""
    input_mode: str = "text"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConversationStore:
    turns: list[ConversationTurn] = field(default_factory=list)
    version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "turns": [t.to_dict() for t in self.turns],
        }


def _redact_excerpt(text: str, *, max_len: int) -> str:
    if not text:
        return ""
    out = redact_screen_text(str(text), max_len=max_len)
    return out.strip()


def _load_store() -> ConversationStore:
    path = Path(CONVERSATION_CONTEXT_PATH)
    if not path.is_file():
        return ConversationStore()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return ConversationStore()
        turns_raw = raw.get("turns") or []
        turns: list[ConversationTurn] = []
        for item in turns_raw[-CONVERSATION_MAX_TURNS :]:
            if not isinstance(item, dict):
                continue
            try:
                turns.append(
                    ConversationTurn(
                        timestamp=str(item.get("timestamp", "")),
                        intent=str(item.get("intent", "")),
                        status=str(item.get("status", "")),
                        summary_excerpt=str(item.get("summary_excerpt", "")),
                        raw_text_excerpt=str(item.get("raw_text_excerpt", "")),
                        input_mode=str(item.get("input_mode", "text")),
                    )
                )
            except (TypeError, ValueError):
                continue
        return ConversationStore(turns=turns, version=int(raw.get("version", 1)))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("Conversation context load degraded: %s", exc)
        return ConversationStore()


def _save_store(store: ConversationStore) -> None:
    path = Path(CONVERSATION_CONTEXT_PATH)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        trimmed = store.turns[-CONVERSATION_MAX_TURNS :]
        payload = {"version": store.version, "turns": [t.to_dict() for t in trimmed]}
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.warning("Conversation context save failed: %s", exc)


def append_turn(
    *,
    raw_text: str,
    intent: str,
    status: str,
    summary: str,
    input_mode: str = "text",
) -> None:
    """Append one command turn (redacted). Failures must not affect routing."""
    if not CONVERSATION_ENABLED:
        return
    try:
        store = _load_store()
        turn = ConversationTurn(
            timestamp=datetime.now(timezone.utc).isoformat(),
            intent=intent or "unknown",
            status=status or "unknown",
            summary_excerpt=_redact_excerpt(
                summary, max_len=CONVERSATION_MAX_SUMMARY_CHARS
            ),
            raw_text_excerpt=_redact_excerpt(
                raw_text, max_len=CONVERSATION_MAX_RAW_CHARS
            ),
            input_mode=input_mode or "text",
        )
        store.turns.append(turn)
        store.turns = store.turns[-CONVERSATION_MAX_TURNS :]
        _save_store(store)
    except Exception as exc:
        logger.debug("append_turn skipped: %s", exc)


def get_recent_turns(*, limit: int | None = None) -> list[ConversationTurn]:
    if not CONVERSATION_ENABLED:
        return []
    try:
        default_cap = min(CONVERSATION_CLASSIFY_CONTEXT_TURNS, CONVERSATION_MAX_TURNS)
        cap = limit if limit is not None else default_cap
        return _load_store().turns[-cap:]
    except Exception:
        return []


def get_classify_context() -> dict[str, Any]:
    """Bounded context for LLM/rule classify (no secrets, no full bodies)."""
    if not CONVERSATION_ENABLED:
        return {}
    try:
        turns = get_recent_turns(limit=CONVERSATION_CLASSIFY_CONTEXT_TURNS)
        if not turns:
            return {}
        lines: list[str] = []
        for i, t in enumerate(turns, start=1):
            line = f"turn{i}: {t.intent} ({t.status})"
            if t.raw_text_excerpt:
                line += f" user={t.raw_text_excerpt[:60]}"
            if t.summary_excerpt:
                line += f" assistant={t.summary_excerpt[:80]}"
            lines.append(line)
        return {
            "recent_turns": lines,
            "last_intent": turns[-1].intent,
            "last_status": turns[-1].status,
            "turn_count": len(turns),
            "max_turns": CONVERSATION_MAX_TURNS,
        }
    except Exception as exc:
        logger.debug("get_classify_context degraded: %s", exc)
        return {}


def reset_conversation_store() -> None:
    """Test helper — clear conversation log."""
    path = Path(CONVERSATION_CONTEXT_PATH)
    if path.is_file():
        try:
            path.unlink()
        except OSError:
            try:
                path.write_text(
                    json.dumps({"version": 1, "turns": []}, indent=2),
                    encoding="utf-8",
                )
            except OSError:
                pass
