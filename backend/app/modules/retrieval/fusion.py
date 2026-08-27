"""Reciprocal Rank Fusion — the ranker merging retriever result lists.

RRF combines rankings whose raw scores are incomparable (BM25 term
weights, cosine similarities, graph match counts) by position:

    fused(d) = sum over lists containing d of 1 / (k + rank_d)

with the standard k = 60. Documents found by multiple retrievers rise.
"""

from dataclasses import dataclass, field

_RRF_K = 60


@dataclass(frozen=True, slots=True)
class FusedHit:
    key: str
    score: float
    retrievers: list[str] = field(default_factory=list)


def reciprocal_rank_fusion(
    ranked_lists: dict[str, list[str]], *, k: int = _RRF_K
) -> list[FusedHit]:
    """Fuse per-retriever ranked id lists into one ranking.

    ``ranked_lists`` maps retriever name -> ids ordered best-first.
    """
    scores: dict[str, float] = {}
    contributors: dict[str, list[str]] = {}

    for retriever, ids in ranked_lists.items():
        for rank, key in enumerate(ids, start=1):
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            contributors.setdefault(key, []).append(retriever)

    return [
        FusedHit(key=key, score=round(score, 6), retrievers=contributors[key])
        for key, score in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    ]
