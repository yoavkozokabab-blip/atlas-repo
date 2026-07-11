"""Token accounting helpers.

Exact token counts should be recorded from the agent UI/API when available.
The fallback here is intentionally labeled as an estimate.
"""

from __future__ import annotations

import re
from typing import Any

_TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    # A conservative approximation for reporting only. It is not a model tokenizer.
    return len(_TOKEN_RE.findall(text))


def token_metric(value: int | None, status: str) -> dict[str, Any]:
    return {"value": value, "status": status}


def unavailable_token_metric() -> dict[str, Any]:
    return token_metric(None, "unavailable")


def estimated_token_metric(text: str) -> dict[str, Any]:
    return token_metric(estimate_tokens(text), "estimated")
