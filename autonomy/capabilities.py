"""Autonomous Agent Stack v1 — capability model + safety classification.

Only READ-ONLY capabilities are allowed. Any goal whose text implies an
irreversible / account / commerce action is classified UNSAFE and refused
before a plan is ever built. Reuses the Phase 71 forbidden-keyword scanner.
"""

from __future__ import annotations

from enum import Enum

from tooluse.contracts import FORBIDDEN_KEYWORDS, scan_forbidden  # reuse, single source of truth


class Capability(str, Enum):
    # --- allowed (read-only) ---
    SEARCH = "search"
    OPEN_RESULT = "open_result"
    OPEN_URL = "open_url"               # only URLs surfaced by search / allowed_domains
    EXTRACT_FACTS = "extract_facts"
    EXTRACT_TITLE = "extract_title"
    EXTRACT_LINKS = "extract_links"
    SUMMARIZE = "summarize"
    COMPARE = "compare"
    FOLLOW_LINK = "follow_link"         # only non-dangerous http(s) links, counted vs limits
    SYNTHESIZE = "synthesize"


ALLOWED_CAPABILITIES: frozenset[Capability] = frozenset({
    Capability.SEARCH,
    Capability.OPEN_RESULT,
    Capability.OPEN_URL,
    Capability.EXTRACT_FACTS,
    Capability.EXTRACT_TITLE,
    Capability.EXTRACT_LINKS,
    Capability.SUMMARIZE,
    Capability.COMPARE,
    Capability.FOLLOW_LINK,
    Capability.SYNTHESIZE,
})

# Forbidden capability labels (never planned, never executed). These are the
# irreversible / account / commerce actions the sprint explicitly prohibits.
FORBIDDEN_CAPABILITIES: tuple[str, ...] = (
    "pay", "purchase", "buy", "order", "checkout", "book", "booking", "reserve",
    "login", "sign_in", "submit_form", "upload", "download", "delete", "send",
    "message", "email_send", "transfer", "subscribe", "account_change",
    "desktop_control", "click_arbitrary", "type_into_form",
)


class SafetyClass(str, Enum):
    READ_ONLY_RESEARCH = "read_only_research"  # allowed
    UNSAFE_FORBIDDEN = "unsafe_forbidden"      # refused


def detect_forbidden(goal: str) -> list[str]:
    """Return forbidden indicators found in the goal text (empty = clean)."""
    found: list[str] = []
    kw = scan_forbidden(goal)
    if kw is not None:
        found.append(kw)
    low = (goal or "").lower()
    # A few autonomy-specific phrasings not covered by the base keyword set.
    for extra in ("add to cart", "place order", "make a payment", "wire money",
                  "fill in", "fill out", "log into", "sign into", "check out"):
        if extra in low and extra not in found:
            found.append(extra)
    return found


def classify_goal(goal: str) -> tuple[SafetyClass, list[str]]:
    forbidden = detect_forbidden(goal)
    if forbidden:
        return SafetyClass.UNSAFE_FORBIDDEN, forbidden
    return SafetyClass.READ_ONLY_RESEARCH, []
