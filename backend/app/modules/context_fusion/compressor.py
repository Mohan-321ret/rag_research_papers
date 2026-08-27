"""Context compression — the third stage of context fusion.

Reranking produces a relevance-ordered list that may still be as large
as the retrieval candidate pool (up to ``retrieval_candidate_k``); this
step is the "don't blindly send 20 chunks to the LLM" cutoff, keeping
only the top few (5-8 by default) most relevant chunks.
"""

from app.modules.context_fusion.types import EvidenceChunk


def compress_to_top_k(items: list[EvidenceChunk], top_k: int) -> list[EvidenceChunk]:
    """Keep the top ``top_k`` items (already ranked best-first)."""
    return items[: max(top_k, 0)]
