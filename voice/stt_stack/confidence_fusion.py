"""Fuse multiple STT backend hypotheses by confidence."""

from __future__ import annotations

from voice.stt_engines.base import SttHypothesis

try:
    from rapidfuzz import fuzz
except ImportError:
    fuzz = None  # type: ignore


def _similar(a: str, b: str) -> bool:
    if not a or not b:
        return False
    if fuzz is not None:
        return fuzz.token_sort_ratio(a.lower(), b.lower()) >= 82
    return a.lower().strip() == b.lower().strip()


def fuse_hypotheses(hypotheses: list[SttHypothesis]) -> SttHypothesis:
    """
    Weighted fusion: cluster similar transcripts, pick highest total confidence.
    """
    if not hypotheses:
        return SttHypothesis(text="", engine="none", confidence=0.0)
    if len(hypotheses) == 1:
        return hypotheses[0]

    clusters: list[list[SttHypothesis]] = []
    for h in hypotheses:
        placed = False
        for cluster in clusters:
            if _similar(h.text, cluster[0].text):
                cluster.append(h)
                placed = True
                break
        if not placed:
            clusters.append([h])

    best_cluster: list[SttHypothesis] = []
    best_score = -1.0
    for cluster in clusters:
        score = sum(h.confidence for h in cluster) + 0.05 * len(cluster)
        if score > best_score:
            best_score = score
            best_cluster = cluster

    winner = max(best_cluster, key=lambda h: h.confidence)
    engines = sorted({h.engine for h in best_cluster})
    fused_conf = min(0.99, sum(h.confidence for h in best_cluster) / len(best_cluster))
    return SttHypothesis(
        text=winner.text,
        engine="+".join(engines) if len(engines) > 1 else winner.engine,
        confidence=fused_conf,
        language=winner.language,
        avg_logprob=winner.avg_logprob,
        language_probability=winner.language_probability,
        metadata={"fused_from": engines, "cluster_size": len(best_cluster)},
    )
