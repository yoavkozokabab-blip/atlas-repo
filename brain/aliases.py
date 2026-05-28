"""Command aliases → allowlisted intents only."""

from __future__ import annotations

import json
import re
import shutil
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ALIASES_PATH, CONFIRMATION_REQUIRED_INTENTS, DATA_DIR, IMPLEMENTED_INTENTS
from brain.storage_safe import UnsafeStorageError, validate_safe_value
from core.logger import setup_logger
from core.types import CommandRequest, Intent

logger = setup_logger("jarvis.aliases")

BACKUPS_DIR = DATA_DIR / "backups"


def _normalize_alias(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).strip().lower()
    return re.sub(r"\s+", " ", text)


def validate_alias_target(intent: str, params: dict[str, Any] | None = None) -> None:
    if intent not in IMPLEMENTED_INTENTS:
        raise UnsafeStorageError(
            f"Alias target '{intent}' is not an implemented intent."
        )
    if params:
        blob = json.dumps(params, ensure_ascii=False)
        validate_safe_value("alias_params", blob)


class AliasStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or ALIASES_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        BACKUPS_DIR.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {"aliases": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "aliases" in data:
                return data
            if isinstance(data, dict):
                return {"aliases": data}
            return {"aliases": {}}
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not load aliases: %s", exc)
            return {"aliases": {}}

    def _backup(self) -> None:
        if not self.path.is_file():
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = BACKUPS_DIR / f"aliases_{stamp}.json"
        try:
            shutil.copy2(self.path, dest)
        except OSError as exc:
            logger.warning("Aliases backup failed: %s", exc)

    def _save(self, data: dict[str, Any]) -> None:
        self._backup()
        self.path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def add_alias(
        self,
        alias_text: str,
        target_intent: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        validate_alias_target(target_intent, params)
        norm = _normalize_alias(alias_text)
        validate_safe_value("alias", norm)
        data = self._load()
        aliases: dict[str, Any] = data.setdefault("aliases", {})
        aliases[norm] = {
            "intent": target_intent,
            "params": params or {},
            "alias_display": alias_text.strip(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save(data)

    def delete_alias(self, alias_text: str) -> bool:
        norm = _normalize_alias(alias_text)
        data = self._load()
        aliases: dict[str, Any] = data.get("aliases", {})
        if norm not in aliases:
            return False
        del aliases[norm]
        self._save(data)
        return True

    def list_aliases(self) -> list[dict[str, Any]]:
        aliases = self._load().get("aliases", {})
        return [
            {
                "alias": meta.get("alias_display", key),
                "normalized": key,
                "intent": meta.get("intent"),
                "params": meta.get("params", {}),
            }
            for key, meta in sorted(aliases.items())
        ]

    def resolve_alias(self, raw_text: str) -> CommandRequest | None:
        norm = _normalize_alias(raw_text)
        if not norm:
            return None
        meta = self._load().get("aliases", {}).get(norm)
        if not meta:
            return None
        intent_str = meta.get("intent", "")
        if intent_str not in IMPLEMENTED_INTENTS:
            return None
        try:
            intent = Intent(intent_str)
        except ValueError:
            return None
        return CommandRequest(
            raw_text=raw_text,
            intent=intent,
            confidence=1.0,
            params=dict(meta.get("params") or {}),
            classifier_source="alias",
        )


def resolve_alias(raw_text: str) -> CommandRequest | None:
    return get_aliases().resolve_alias(raw_text)


def alias_requires_confirmation(raw_text: str) -> bool:
    req = resolve_alias(raw_text)
    if req is None:
        return False
    return req.intent.value in CONFIRMATION_REQUIRED_INTENTS


_store: AliasStore | None = None


def get_aliases() -> AliasStore:
    global _store
    if _store is None:
        _store = AliasStore()
    return _store


def reset_alias_store() -> None:
    global _store
    _store = None
