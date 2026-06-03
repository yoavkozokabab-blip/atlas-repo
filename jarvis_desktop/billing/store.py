"""Phase 137A — local persistence for usage/billing (JSONL + JSON, no DB, no cloud).

Mirrors the analytics store: append-only event log, env-overridable directory,
never raises to callers (degrades quietly). Absolutely no external calls.
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Dict, List, Optional

from .models import (
    User, Workspace, RepositoryScan, UsageEvent, BillingAccount, new_id,
)

_LOCK = threading.Lock()


def billing_data_dir() -> str:
    override = os.environ.get("ATLAS_BILLING_DATA_DIR", "").strip()
    if override:
        return os.path.abspath(override)
    base = os.environ.get("JARVIS_DESKTOP_DATA", "").strip()
    if base:
        return os.path.join(os.path.abspath(base), "billing")
    return os.path.join(os.path.expanduser("~"), ".jarvis_desktop", "billing")


class Store:
    """File-backed store. Usage events + scans are append-only JSONL; accounts /
    users / workspaces are small JSON documents."""

    def __init__(self, directory: Optional[str] = None) -> None:
        self.dir = directory or billing_data_dir()

    # -- paths ----------------------------------------------------------------
    @property
    def events_path(self) -> str:
        return os.path.join(self.dir, "usage_events.jsonl")

    @property
    def scans_path(self) -> str:
        return os.path.join(self.dir, "repository_scans.jsonl")

    @property
    def accounts_path(self) -> str:
        return os.path.join(self.dir, "accounts.json")

    # -- low-level ------------------------------------------------------------
    def _append(self, path: str, row: Dict[str, Any]) -> bool:
        try:
            with _LOCK:
                os.makedirs(self.dir, exist_ok=True)
                with open(path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            return True
        except OSError:
            return False  # never break the product over telemetry

    def _read_jsonl(self, path: str) -> List[Dict[str, Any]]:
        if not os.path.isfile(path):
            return []
        rows: List[Dict[str, Any]] = []
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        try:
                            rows.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except OSError:
            return []
        return rows

    def _read_json(self, path: str, default: Any) -> Any:
        if not os.path.isfile(path):
            return default
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError):
            return default

    def _write_json(self, path: str, doc: Any) -> bool:
        try:
            with _LOCK:
                os.makedirs(self.dir, exist_ok=True)
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(doc, fh, ensure_ascii=False, indent=2)
            return True
        except OSError:
            return False

    # -- usage events ---------------------------------------------------------
    def record_event(self, event: UsageEvent) -> bool:
        return self._append(self.events_path, event.to_dict())

    def all_events(self) -> List[UsageEvent]:
        return [UsageEvent.from_dict(r) for r in self._read_jsonl(self.events_path)]

    # -- repository scans -----------------------------------------------------
    def record_scan(self, scan: RepositoryScan) -> bool:
        return self._append(self.scans_path, scan.to_dict())

    def all_scans(self) -> List[RepositoryScan]:
        return [RepositoryScan.from_dict(r) for r in self._read_jsonl(self.scans_path)]

    # -- accounts / users / workspaces ---------------------------------------
    def _accounts_doc(self) -> Dict[str, Any]:
        return self._read_json(self.accounts_path, {"users": {}, "workspaces": {}, "accounts": {}})

    def upsert_user(self, user: User) -> User:
        doc = self._accounts_doc()
        doc["users"][user.id] = user.to_dict()
        self._write_json(self.accounts_path, doc)
        return user

    def get_user(self, user_id: str) -> Optional[User]:
        doc = self._accounts_doc()
        raw = doc["users"].get(user_id)
        return User.from_dict(raw) if raw else None

    def all_users(self) -> List[User]:
        return [User.from_dict(u) for u in self._accounts_doc().get("users", {}).values()]

    def upsert_workspace(self, ws: Workspace) -> Workspace:
        doc = self._accounts_doc()
        doc["workspaces"][ws.id] = ws.to_dict()
        self._write_json(self.accounts_path, doc)
        return ws

    def all_workspaces(self) -> List[Workspace]:
        return [Workspace.from_dict(w) for w in self._accounts_doc().get("workspaces", {}).values()]

    def upsert_account(self, account: BillingAccount) -> BillingAccount:
        doc = self._accounts_doc()
        doc["accounts"][account.user_id] = account.to_dict()
        self._write_json(self.accounts_path, doc)
        return account

    def get_account(self, user_id: str) -> Optional[BillingAccount]:
        doc = self._accounts_doc()
        raw = doc["accounts"].get(user_id)
        return BillingAccount.from_dict(raw) if raw else None

    # -- default local context -----------------------------------------------
    def ensure_default_context(self) -> Dict[str, Any]:
        """Ensure a local owner user + default workspace + account exist.

        The local desktop owner is treated as an admin so the admin dashboard is
        usable on a single-user install. No network, no real identity.
        """
        doc = self._accounts_doc()
        changed = False
        if "user_local_owner" not in doc["users"]:
            owner = User(id="user_local_owner", email="owner@localhost",
                         name="Local Owner", role="admin", plan_id="free",
                         workspace_ids=["ws_default"])
            doc["users"][owner.id] = owner.to_dict()
            changed = True
        if "ws_default" not in doc["workspaces"]:
            ws = Workspace(id="ws_default", name="Default Workspace",
                           owner_user_id="user_local_owner",
                           member_user_ids=["user_local_owner"])
            doc["workspaces"][ws.id] = ws.to_dict()
            changed = True
        if "user_local_owner" not in doc["accounts"]:
            acct = BillingAccount(id=new_id("acct"), user_id="user_local_owner",
                                  workspace_id="ws_default", plan_id="free")
            doc["accounts"][acct.user_id] = acct.to_dict()
            changed = True
        if changed:
            self._write_json(self.accounts_path, doc)
        return {"user_id": "user_local_owner", "workspace_id": "ws_default"}

    # -- test helpers ---------------------------------------------------------
    def reset(self) -> None:
        for p in (self.events_path, self.scans_path, self.accounts_path):
            if os.path.isfile(p):
                try:
                    os.remove(p)
                except OSError:
                    pass


def default_store() -> Store:
    """Fresh Store bound to the current env-configured directory (cheap; reads on
    demand) so tests that set ``ATLAS_BILLING_DATA_DIR`` / ``JARVIS_DESKTOP_DATA``
    are isolated."""
    return Store(billing_data_dir())
