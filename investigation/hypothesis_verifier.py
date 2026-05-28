"""Hypothesis verification scoring using deterministic replay artifacts."""

from __future__ import annotations

from investigation.replay_diff import diff_live_backtest
from investigation.replay_engine import replay_symbol
from investigation.replay_models import HypothesisVerification
from phase45_investigation import rank_live_backtest_hypotheses


def verify_hypothesis(title: str | None = None, *, symbol: str = "AAPL") -> HypothesisVerification:
    hypotheses = rank_live_backtest_hypotheses()
    selected = next((h for h in hypotheses if title and title.lower() in h.title.lower()), hypotheses[0])
    replay = replay_symbol(symbol)
    diff = diff_live_backtest(symbol)
    title_lower = selected.title.lower()
    replay_confirmed = False
    contradictions: list[str] = []
    if "bar" in title_lower:
        replay_confirmed = bool(diff.divergence_reasons)
    elif "execution" in title_lower:
        replay_confirmed = replay.execution_attempts == 0
    elif "universe" in title_lower:
        replay_confirmed = bool(replay.universe_hash)
    elif "risk" in title_lower or "positions" in title_lower:
        replay_confirmed = replay.portfolio_before.get("positions", 0) >= replay.portfolio_before.get("max_open_positions", 99)
    else:
        replay_confirmed = bool(selected.evidence)
    if not replay_confirmed:
        contradictions.append("Replay did not reproduce this hypothesis directly; keep as hypothesis.")
    evidence_paths = sorted(set([ev.path for ev in selected.evidence] + replay.evidence_paths + diff.evidence_paths))
    reproducibility = 1.0 if replay.replay_hash == replay_symbol(symbol).replay_hash else 0.0
    before = selected.confidence
    after = min(0.99, before + 0.08) if replay_confirmed and reproducibility == 1.0 else max(0.20, before - 0.15)
    status = "VERIFIED" if replay_confirmed and reproducibility == 1.0 else "HYPOTHESIS"
    return HypothesisVerification(
        title=selected.title,
        status=status,
        evidence_count=len(evidence_paths),
        replay_confirmation=replay_confirmed,
        contradictory_evidence=contradictions,
        reproducibility_score=reproducibility,
        confidence_before=before,
        confidence_after=after,
        evidence_paths=evidence_paths[:20],
        rationale=(
            "Replay reproduced mismatch and deterministic hash matched."
            if status == "VERIFIED"
            else "Evidence exists but replay did not fully confirm the hypothesis."
        ),
    )


def verify_all_hypotheses(*, symbol: str = "AAPL") -> list[HypothesisVerification]:
    return [verify_hypothesis(h.title, symbol=symbol) for h in rank_live_backtest_hypotheses()]


def format_verifications(items: list[HypothesisVerification]) -> str:
    lines = ["Hypothesis verification report"]
    for i, item in enumerate(items, 1):
        lines.append(f"{i}. {item.status} - {item.title}")
        lines.append(f"  evidence_count: {item.evidence_count}")
        lines.append(f"  replay_confirmation: {item.replay_confirmation}")
        lines.append(f"  reproducibility_score: {item.reproducibility_score:.2f}")
        lines.append(f"  confidence: {item.confidence_before:.2f} -> {item.confidence_after:.2f}")
        lines.append(f"  rationale: {item.rationale}")
        if item.contradictory_evidence:
            lines.append(f"  contradictory evidence: {'; '.join(item.contradictory_evidence)}")
        for path in item.evidence_paths[:5]:
            lines.append(f"  evidence: {path}")
    return "\n".join(lines)
