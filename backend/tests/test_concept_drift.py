"""Tests for Concept Drift Detection (Phase 12): chunk-level, embedding
nearest-neighbor comparison classified by bidirectional NLI entailment.
"""

import asyncio

from app.modules.evolution.concept_drift_detector import (
    ChunkPairDrift,
    detect_concept_drift,
)
from app.modules.verification.nli_verifier import CrossEncoderNliVerifier, NliScore

# ---- Deterministic matching / thresholding (fake embedder + verifier) ----


def _fixed_embed(vectors_by_text: dict[str, list[float]]):
    async def embed(texts: list[str]) -> list[list[float]]:
        return [vectors_by_text[t] for t in texts]

    return embed


class _StubVerifier:
    """Deterministic verifier: returns whatever NliScore was registered
    for a (premise, hypothesis) pair, defaulting to strong neutral."""

    model_name = "stub"

    def __init__(self, table: dict[tuple[str, str], NliScore] | None = None) -> None:
        self._table = table or {}

    async def score(self, premise: str, hypothesis: str) -> NliScore:
        return self._table.get(
            (premise, hypothesis), NliScore(contradiction=0.0, entailment=0.0, neutral=1.0, verdict="neutral")
        )


def test_no_old_chunks_no_drift() -> None:
    async def scenario() -> None:
        result = await detect_concept_drift(
            _fixed_embed({}), _StubVerifier(), [], [("n1", "New content.")], threshold=0.15
        )
        assert result.drift_score == 0.0
        assert result.drift_type == "none"
        assert result.changed_chunks == []

    asyncio.run(scenario())


def test_identical_chunks_no_drift_flagged() -> None:
    async def scenario() -> None:
        vec = {"Same content.": [1.0, 0.0]}
        result = await detect_concept_drift(
            _fixed_embed(vec), _StubVerifier(),
            [("o1", "Same content.")], [("n1", "Same content.")],
            threshold=0.15,
        )
        assert result.changed_chunks == []
        assert result.drift_score == 0.0
        assert result.drift_type == "none"

    asyncio.run(scenario())


def test_low_drift_rewording_not_flagged() -> None:
    """Low cosine distance *and* NLI agreeing it's a mutual paraphrase ->
    not flagged. (Cosine distance alone isn't used as the gate — see the
    module docstring for why: it can't reliably tell a rewording from a
    narrow factual change.)"""

    async def scenario() -> None:
        import math

        angle = 0.1  # cosine similarity ~0.99 -> drift ~0.01
        vec = {
            "Old wording.": [1.0, 0.0],
            "New wording.": [math.cos(angle), math.sin(angle)],
        }
        verifier = _StubVerifier(
            {
                ("Old wording.", "New wording."): NliScore(0.01, 0.95, 0.04, "entailment"),
                ("New wording.", "Old wording."): NliScore(0.01, 0.95, 0.04, "entailment"),
            }
        )
        result = await detect_concept_drift(
            _fixed_embed(vec), verifier,
            [("o1", "Old wording.")], [("n1", "New wording.")],
            threshold=0.15,
        )
        assert result.changed_chunks == []
        assert result.drift_type == "none"
        assert result.drift_score < 0.15

    asyncio.run(scenario())


def test_orthogonal_matched_pair_flagged_and_classified() -> None:
    async def scenario() -> None:
        vec = {"Old.": [1.0, 0.0], "New.": [0.0, 1.0]}
        verifier = _StubVerifier(
            {
                ("Old.", "New."): NliScore(0.9, 0.05, 0.05, "contradiction"),
                ("New.", "Old."): NliScore(0.9, 0.05, 0.05, "contradiction"),
            }
        )
        result = await detect_concept_drift(
            _fixed_embed(vec), verifier, [("o1", "Old.")], [("n1", "New.")], threshold=0.15
        )
        assert len(result.changed_chunks) == 1
        pair = result.changed_chunks[0]
        assert pair.old_chunk_id == "o1"
        assert pair.new_chunk_id == "n1"
        assert pair.drift_type == "contradiction"
        assert pair.drift_score == 1.0  # cosine similarity 0 -> drift 1
        assert result.drift_type == "contradiction"

    asyncio.run(scenario())


def test_unmatched_old_chunk_is_removed() -> None:
    async def scenario() -> None:
        # Old chunk's nearest new-chunk neighbor doesn't reciprocate
        # (that new chunk's own best match is a different old chunk).
        vec = {
            "Old A.": [1.0, 0.0, 0.0],
            "Old B.": [0.0, 1.0, 0.0],
            "New B.": [0.0, 0.9, 0.1],
        }
        result = await detect_concept_drift(
            _fixed_embed(vec), _StubVerifier(),
            [("oA", "Old A."), ("oB", "Old B.")], [("nB", "New B.")],
            threshold=0.15,
        )
        types = {c.old_chunk_id: c.drift_type for c in result.changed_chunks if c.old_chunk_id}
        assert types.get("oA") == "removed"
        removed = next(c for c in result.changed_chunks if c.drift_type == "removed")
        assert removed.new_chunk_id is None
        assert removed.new_content is None
        assert removed.drift_score == 1.0

    asyncio.run(scenario())


def test_unmatched_new_chunk_is_added() -> None:
    async def scenario() -> None:
        vec = {
            "Old A.": [1.0, 0.0, 0.0],
            "New A.": [0.95, 0.05, 0.0],
            "New C.": [0.0, 0.0, 1.0],
        }
        result = await detect_concept_drift(
            _fixed_embed(vec), _StubVerifier(),
            [("oA", "Old A.")], [("nA", "New A."), ("nC", "New C.")],
            threshold=0.15,
        )
        added = [c for c in result.changed_chunks if c.drift_type == "added"]
        assert len(added) == 1
        assert added[0].new_chunk_id == "nC"
        assert added[0].old_chunk_id is None
        assert added[0].old_content is None

    asyncio.run(scenario())


def test_dominant_type_prioritizes_contradiction_over_others() -> None:
    async def scenario() -> None:
        # Each pair has real (non-zero, non-tied) similarity to its own
        # partner and zero similarity to the other pair, so mutual
        # nearest-neighbor matching can't collide on an argmax tiebreak.
        vec = {
            "Old A.": [1.0, 0.0, 0.0, 0.0],
            "New A.": [0.6, 0.8, 0.0, 0.0],
            "Old B.": [0.0, 0.0, 1.0, 0.0],
            "New B.": [0.0, 0.0, 0.6, 0.8],
        }
        verifier = _StubVerifier(
            {
                ("Old A.", "New A."): NliScore(0.0, 0.0, 1.0, "neutral"),
                ("New A.", "Old A."): NliScore(0.0, 0.0, 1.0, "neutral"),
                ("Old B.", "New B."): NliScore(0.95, 0.02, 0.03, "contradiction"),
                ("New B.", "Old B."): NliScore(0.95, 0.02, 0.03, "contradiction"),
            }
        )
        result = await detect_concept_drift(
            _fixed_embed(vec), verifier,
            [("oA", "Old A."), ("oB", "Old B.")],
            [("nA", "New A."), ("nB", "New B.")],
            threshold=0.15,
        )
        assert result.drift_type == "contradiction"  # outranks topic_shift
        assert {c.drift_type for c in result.changed_chunks} == {"topic_shift", "contradiction"}

    asyncio.run(scenario())


def test_changed_chunk_pair_is_plain_dataclass_serializable() -> None:
    import dataclasses

    pair = ChunkPairDrift("o", "n", "old text", "new text", 0.5, "expansion")
    assert dataclasses.asdict(pair) == {
        "old_chunk_id": "o", "new_chunk_id": "n",
        "old_content": "old text", "new_content": "new text",
        "drift_score": 0.5, "drift_type": "expansion",
    }


# ---- Real model: the spec's own examples ---------------------------------


def test_real_model_catches_the_spec_confidential_info_expansion_example() -> None:
    """The exact motivating example from the spec: not a contradiction (an
    NLI contradiction check alone would score this near zero and miss it
    entirely) but a genuine broadening of scope, caught via bidirectional
    entailment: the new, broader statement entails the old, narrower one."""

    async def scenario() -> None:
        from app.modules.processing.embedding import SentenceTransformerEmbedder

        embedder = SentenceTransformerEmbedder("sentence-transformers/all-MiniLM-L6-v2")

        async def embed(texts: list[str]) -> list[list[float]]:
            return [list(v) for v in await embedder.embed_texts(texts)]

        verifier = CrossEncoderNliVerifier("cross-encoder/nli-deberta-v3-xsmall")
        old_text = "Confidential information includes customer records."
        new_text = "Confidential information includes customer and employee records."

        result = await detect_concept_drift(
            embed, verifier, [("o1", old_text)], [("n1", new_text)], threshold=0.05
        )
        assert len(result.changed_chunks) == 1
        pair = result.changed_chunks[0]
        assert pair.drift_type == "expansion"
        assert result.drift_type == "expansion"

    asyncio.run(scenario())


def test_real_model_catches_the_spec_remote_days_contradiction_example() -> None:
    """The spec's "obvious text difference" example — proving concept
    drift catches it too, uniformly with the semantic case above, not
    just the text-diff-obvious cases."""

    async def scenario() -> None:
        from app.modules.processing.embedding import SentenceTransformerEmbedder

        embedder = SentenceTransformerEmbedder("sentence-transformers/all-MiniLM-L6-v2")

        async def embed(texts: list[str]) -> list[list[float]]:
            return [list(v) for v in await embedder.embed_texts(texts)]

        verifier = CrossEncoderNliVerifier("cross-encoder/nli-deberta-v3-xsmall")
        old_text = "Employees can work remotely 2 days per week."
        new_text = "Employees can work remotely 3 days per week."

        result = await detect_concept_drift(
            embed, verifier, [("o1", old_text)], [("n1", new_text)], threshold=0.05
        )
        assert len(result.changed_chunks) == 1
        assert result.changed_chunks[0].drift_type == "contradiction"

    asyncio.run(scenario())
