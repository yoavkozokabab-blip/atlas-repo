"""Deterministic token estimator for the offline benchmark harness (Phase 104A)."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

CHARS_PER_TOKEN = 4.0
INSTRUMENTATION_VERSION = "phase104a-v1"


@dataclass(frozen=True)
class TokenEstimate:
    estimated_tokens: int
    source: str
    note: str = "Estimated token count; not a tokenizer measurement."

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class TokenBreakdown:
    """Labeled token estimates for one benchmark prompt/answer package."""

    raw_prompt: TokenEstimate
    atlas_context: TokenEstimate
    final_prompt_package: TokenEstimate
    answer_text: Optional[TokenEstimate] = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "instrumentation_version": INSTRUMENTATION_VERSION,
            "estimator": "chars_per_4_estimate",
            "raw_prompt": self.raw_prompt.to_dict(),
            "atlas_context": self.atlas_context.to_dict(),
            "final_prompt_package": self.final_prompt_package.to_dict(),
        }
        if self.answer_text is not None:
            payload["answer_text"] = self.answer_text.to_dict()
        return payload

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TokenBreakdown":
        answer = data.get("answer_text")
        return cls(
            raw_prompt=TokenEstimate(**data["raw_prompt"]),
            atlas_context=TokenEstimate(**data["atlas_context"]),
            final_prompt_package=TokenEstimate(**data["final_prompt_package"]),
            answer_text=TokenEstimate(**answer) if isinstance(answer, dict) else None,
        )


def estimate_tokens(text: Optional[str], *, manual_override: Optional[int] = None) -> TokenEstimate:
    """Estimate text tokens with chars/4 or preserve a human-provided override."""
    if manual_override is not None:
        if manual_override < 0:
            raise ValueError("manual_override must be non-negative")
        return TokenEstimate(int(manual_override), "manual_override")
    return TokenEstimate(math.ceil(len(text or "") / CHARS_PER_TOKEN), "chars_per_4_estimate")


def estimated_count(text: Optional[str], *, manual_override: Optional[int] = None) -> int:
    return estimate_tokens(text, manual_override=manual_override).estimated_tokens


def build_token_breakdown(
    *,
    raw_prompt: str,
    atlas_context: str,
    final_prompt_package: str,
    answer_text: Optional[str] = None,
    answer_override: Optional[int] = None,
) -> TokenBreakdown:
    """Build a structured breakdown for benchmark run packages."""
    return TokenBreakdown(
        raw_prompt=estimate_tokens(raw_prompt),
        atlas_context=estimate_tokens(atlas_context),
        final_prompt_package=estimate_tokens(final_prompt_package),
        answer_text=estimate_tokens(answer_text, manual_override=answer_override)
        if answer_text is not None or answer_override is not None
        else None,
    )


def prompt_metadata_comment(breakdown: TokenBreakdown) -> str:
    """HTML comment block embedded at the top of generated prompt files."""
    parts = breakdown.to_dict()
    lines = [
        "<!-- token_estimate metadata (Phase 104A; not a tokenizer measurement)",
        f"instrumentation_version: {parts['instrumentation_version']}",
        f"raw_prompt_tokens: {breakdown.raw_prompt.estimated_tokens}",
        f"atlas_context_tokens: {breakdown.atlas_context.estimated_tokens}",
        f"final_prompt_package_tokens: {breakdown.final_prompt_package.estimated_tokens}",
    ]
    if breakdown.answer_text is not None:
        lines.append(f"answer_text_tokens: {breakdown.answer_text.estimated_tokens}")
    lines.append("-->")
    return "\n".join(lines) + "\n\n"


def attach_answer_to_breakdown(
    breakdown: Dict[str, Any],
    answer_text: str,
    *,
    manual_override: Optional[int] = None,
) -> Dict[str, Any]:
    """Return a copy of a breakdown dict with answer_text estimates filled in."""
    updated = dict(breakdown)
    updated["answer_text"] = estimate_tokens(
        answer_text, manual_override=manual_override
    ).to_dict()
    return updated
