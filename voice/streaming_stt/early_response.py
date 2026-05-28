"""Prepare early-response hints from prefetch (display/ack only)."""

from __future__ import annotations

from dataclasses import dataclass

from voice.streaming_stt.intent_prefetch import PrefetchResult


@dataclass(frozen=True)
class EarlyResponseHint:
    ack_text: str
    intent: str
    confidence: float


def prepare_early_response(prefetch: PrefetchResult | None) -> EarlyResponseHint | None:
    if prefetch is None or not prefetch.ready:
        return None
    try:
        from conversation.latency_hints import build_fast_ack
        from core.types import CommandRequest, Intent

        req = CommandRequest(
            raw_text=prefetch.canonical_text,
            intent=Intent(prefetch.intent),
            confidence=prefetch.confidence,
        )
        ack = build_fast_ack(req)
        if not ack:
            ack = f"Got it — {prefetch.intent.replace('_', ' ')}"
        return EarlyResponseHint(
            ack_text=ack[:160],
            intent=prefetch.intent,
            confidence=prefetch.confidence,
        )
    except Exception:
        return EarlyResponseHint(
            ack_text=f"Preparing {prefetch.intent.replace('_', ' ')}",
            intent=prefetch.intent,
            confidence=prefetch.confidence,
        )
