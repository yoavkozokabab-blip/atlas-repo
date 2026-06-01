"""Small deterministic token estimator used by the offline benchmark harness."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Optional

CHARS_PER_TOKEN = 4.0


@dataclass(frozen=True)
class TokenEstimate:
    estimated_tokens: int
    source: str
    note: str = "Estimated token count; not a tokenizer measurement."

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def estimate_tokens(text: Optional[str], *, manual_override: Optional[int] = None) -> TokenEstimate:
    """Estimate text tokens with chars/4 or preserve a human-provided override."""
    if manual_override is not None:
        if manual_override < 0:
            raise ValueError("manual_override must be non-negative")
        return TokenEstimate(int(manual_override), "manual_override")
    return TokenEstimate(math.ceil(len(text or "") / CHARS_PER_TOKEN), "chars_per_4_estimate")


def estimated_count(text: Optional[str], *, manual_override: Optional[int] = None) -> int:
    return estimate_tokens(text, manual_override=manual_override).estimated_tokens
