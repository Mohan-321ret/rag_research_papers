"""Tests for the knowledge evolution detectors (Module 3): Change
Detector, Diff Detector, Drift Detector, Conflict Detector, and the
temporal as-of cutoff resolver retrieval depends on.
"""

import asyncio
from datetime import UTC, datetime

from app.modules.evolution.change_detector import detect_change
from app.modules.evolution.conflict_detector import detect_conflicts
from app.modules.evolution.diff_detector import ReplacedPair, compute_diff
from app.modules.evolution.drift_detector import classify_magnitude, detect_drift
from app.modules.retrieval.temporal import resolve_as_of_cutoff
from app.modules.verification.nli_verifier import CrossEncoderNliVerifier

# ---- Change Detector ------------------------------------------------------


def test_change_detector_new_document_has_no_previous_hash() -> None:
    result = detect_change(None, "abc123")
    assert result.is_new_document is True
    assert result.previous_hash is None
    assert result.new_hash == "abc123"


def test_change_detector_revision_has_previous_hash() -> None:
    result = detect_change("old_hash", "new_hash")
    assert result.is_new_document is False


# ---- Diff Detector ----------------------------------------------------


def test_diff_detector_new_document_everything_added() -> None:
    diff = compute_diff(None, "First sentence. Second sentence.")
    assert diff.added == ["First sentence.", "Second sentence."]
    assert diff.removed == []
    assert diff.replaced_pairs == []
    assert diff.similarity_ratio == 0.0


def test_diff_detector_identical_text_no_changes() -> None:
    text = "Employees receive 25 days of annual leave."
    diff = compute_diff(text, text)
    assert diff.added == []
    assert diff.removed == []
    assert diff.unchanged_count == 1
    assert diff.similarity_ratio == 1.0


def test_diff_detector_aligns_replaced_sentence() -> None:
    old = "Employees receive 20 days of annual leave."
    new = "Employees receive 25 days of annual leave."
    diff = compute_diff(old, new)
    assert diff.replaced_pairs == [ReplacedPair(old, new)]
    assert diff.added == []
    assert diff.removed == []


def test_diff_detector_pure_insertion() -> None:
    old = "Policy A applies."
    new = "Policy A applies. Policy B also applies."
    diff = compute_diff(old, new)
    assert diff.added == ["Policy B also applies."]
    assert diff.removed == []
    assert diff.unchanged_count == 1


def test_diff_detector_pure_deletion() -> None:
    old = "Policy A applies. Policy B also applies."
    new = "Policy A applies."
    diff = compute_diff(old, new)
    assert diff.removed == ["Policy B also applies."]
    assert diff.added == []


def test_diff_detector_empty_new_text() -> None:
    diff = compute_diff("Some old content.", "")
    assert diff.removed == ["Some old content."]
    assert diff.added == []


# ---- Drift Detector -----------------------------------------------------


def test_classify_magnitude_buckets() -> None:
    assert classify_magnitude(0.0) == "none"
    assert classify_magnitude(0.10) == "minor"
    assert classify_magnitude(0.20) == "moderate"
    assert classify_magnitude(0.50) == "major"


def test_drift_detector_no_prior_content_is_major() -> None:
    async def scenario() -> None:
        async def embed(texts: list[str]) -> list[list[float]]:
            raise AssertionError("must not embed when there's nothing prior")

        result = await detect_drift(embed, [], ["Brand new content."])
        assert result.score == 1.0
        assert result.magnitude == "major"

    asyncio.run(scenario())


def test_drift_detector_identical_centroids_zero_drift() -> None:
    async def scenario() -> None:
        async def embed(texts: list[str]) -> list[list[float]]:
            # Same fixed vector regardless of text -> identical centroids.
            return [[1.0, 0.0, 0.0] for _ in texts]

        result = await detect_drift(embed, ["old chunk"], ["new chunk"])
        assert result.score == 0.0
        assert result.magnitude == "none"

    asyncio.run(scenario())


def test_drift_detector_orthogonal_centroids_maximal_drift() -> None:
    async def scenario() -> None:
        async def embed(texts: list[str]) -> list[list[float]]:
            return [[1.0, 0.0] if "old" in t else [0.0, 1.0] for t in texts]

        result = await detect_drift(embed, ["old chunk"], ["new chunk"])
        assert result.score == 1.0
        assert result.magnitude == "major"

    asyncio.run(scenario())


def test_drift_detector_real_embedder_rewrite_has_low_drift() -> None:
    """A pure rewording (same fact, different phrasing) should show much
    lower semantic drift than an actual policy change — proving drift
    measures *meaning*, not just how many words changed."""
    from app.modules.processing.embedding import SentenceTransformerEmbedder

    async def scenario() -> None:
        embedder = SentenceTransformerEmbedder("sentence-transformers/all-MiniLM-L6-v2")

        async def embed(texts: list[str]) -> list[list[float]]:
            return [list(v) for v in await embedder.embed_texts(texts)]

        rewrite = await detect_drift(
            embed,
            ["Employees receive 25 days of paid annual leave per year."],
            ["Staff are entitled to twenty-five days of paid annual leave annually."],
        )
        policy_change = await detect_drift(
            embed,
            ["Employees receive 25 days of paid annual leave per year."],
            ["Employees receive 10 days of paid annual leave per year."],
        )
        assert rewrite.score < policy_change.score

    asyncio.run(scenario())


# ---- Conflict Detector (real NLI model) ----------------------------------


def test_conflict_detector_flags_contradicting_replacement() -> None:
    async def scenario() -> None:
        verifier = CrossEncoderNliVerifier("cross-encoder/nli-deberta-v3-xsmall")
        pairs = [
            ReplacedPair(
                "Employees receive 25 days of paid annual leave per year.",
                "Employees receive 20 days of annual leave.",
            )
        ]
        conflicts = await detect_conflicts(verifier, pairs, threshold=0.5)
        assert len(conflicts) == 1
        assert conflicts[0].contradiction_score > 0.9

    asyncio.run(scenario())


def test_conflict_detector_ignores_consistent_rewrite() -> None:
    async def scenario() -> None:
        verifier = CrossEncoderNliVerifier("cross-encoder/nli-deberta-v3-xsmall")
        pairs = [
            ReplacedPair(
                "Employees receive 25 days of paid annual leave per year.",
                "Employees receive 25 days of annual leave.",
            )
        ]
        conflicts = await detect_conflicts(verifier, pairs, threshold=0.5)
        assert conflicts == []

    asyncio.run(scenario())


def test_conflict_detector_empty_pairs_no_model_call() -> None:
    async def scenario() -> None:
        class _ExplodingVerifier:
            model_name = "should-not-be-used"

            async def score(self, premise, hypothesis):
                raise AssertionError("must not score with no replaced pairs")

        conflicts = await detect_conflicts(_ExplodingVerifier(), [], threshold=0.5)
        assert conflicts == []

    asyncio.run(scenario())


# ---- Temporal as-of cutoff resolution -----------------------------------


def test_resolve_as_of_cutoff_before_year() -> None:
    assert resolve_as_of_cutoff("before", "2024") == datetime(2024, 1, 1, tzinfo=UTC)


def test_resolve_as_of_cutoff_before_month() -> None:
    assert resolve_as_of_cutoff("before", "2024-03") == datetime(2024, 3, 1, tzinfo=UTC)


def test_resolve_as_of_cutoff_at_year_is_start_of_next_year() -> None:
    assert resolve_as_of_cutoff("at", "2023") == datetime(2024, 1, 1, tzinfo=UTC)


def test_resolve_as_of_cutoff_at_december_rolls_over_to_next_year() -> None:
    assert resolve_as_of_cutoff("at", "2023-12") == datetime(2024, 1, 1, tzinfo=UTC)


def test_resolve_as_of_cutoff_at_mid_year_month() -> None:
    assert resolve_as_of_cutoff("at", "2023-06") == datetime(2023, 7, 1, tzinfo=UTC)


def test_resolve_as_of_cutoff_past_behaves_like_at() -> None:
    assert resolve_as_of_cutoff("past", "2023") == resolve_as_of_cutoff("at", "2023")


def test_resolve_as_of_cutoff_after_has_no_point_in_time_reading() -> None:
    assert resolve_as_of_cutoff("after", "2023") is None


def test_resolve_as_of_cutoff_current_has_no_cutoff() -> None:
    assert resolve_as_of_cutoff("current", None) is None


def test_resolve_as_of_cutoff_no_target_date_no_cutoff() -> None:
    assert resolve_as_of_cutoff("before", None) is None


def test_resolve_as_of_cutoff_not_temporal_no_cutoff() -> None:
    assert resolve_as_of_cutoff(None, None) is None
