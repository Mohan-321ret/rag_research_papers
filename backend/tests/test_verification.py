"""Tests for evidence verification (Module 9): Claim Extraction -> Evidence
Retrieval -> Fact Verification -> Confidence Scoring -> Hallucination
Detection -> Response Refinement -> Citation Verification.
"""

import asyncio
import uuid

from app.core.config import Settings
from app.modules.context_fusion.types import EvidenceChunk
from app.modules.verification.claim_extraction import extract_claims
from app.modules.verification.nli_verifier import CrossEncoderNliVerifier
from app.modules.verification.refinement import refine_response
from app.modules.verification.types import ClaimVerification
from app.services.verification_service import VerificationService

# ---- Claim Extraction ----------------------------------------------------


def test_extract_claims_splits_sentences_and_strips_markers() -> None:
    claims = extract_claims("Leave is 25 days [1]. Remote work needs approval [2].")
    assert [c.text for c in claims] == ["Leave is 25 days.", "Remote work needs approval."]
    assert claims[0].markers == [1]
    assert claims[1].markers == [2]


def test_extract_claims_spans_match_original_text() -> None:
    text = "Leave is 25 days [1]. Sick leave is 10 days [2]."
    claims = extract_claims(text)
    assert text[claims[0].start : claims[0].end] == "Leave is 25 days [1]."
    assert text[claims[1].start : claims[1].end] == "Sick leave is 10 days [2]."


def test_extract_claims_skips_marker_only_fragment() -> None:
    claims = extract_claims("Real claim here [1]. [2]")
    assert len(claims) == 1
    assert claims[0].text == "Real claim here."


def test_extract_claims_handles_trailing_fragment_without_terminal_punctuation() -> None:
    claims = extract_claims("First sentence. Trailing fragment with no period")
    assert len(claims) == 2
    assert claims[1].text == "Trailing fragment with no period"


def test_extract_claims_empty_answer() -> None:
    assert extract_claims("") == []


def test_extract_claims_multiple_markers_on_one_claim() -> None:
    claims = extract_claims("Both sources agree on 25 days [1][2].")
    assert len(claims) == 1
    assert claims[0].markers == [1, 2]


# ---- Response Refinement --------------------------------------------------


def _verification(claim: str, *, supported: bool, verdict: str = "entailment") -> ClaimVerification:
    return ClaimVerification(
        claim=claim,
        support_score=0.9 if supported else 0.1,
        supported=supported,
        verdict=verdict,
        source_document="Employee_Handbook.pdf",
        source_version=1,
        source_page=23,
        source_chunk_id=uuid.uuid4(),
        cited_markers=[1],
        citation_verified=supported,
    )


def test_refine_response_leaves_supported_claims_untouched() -> None:
    text = "Leave is 25 days [1]."
    claims = extract_claims(text)
    verifications = [_verification(claims[0].text, supported=True)]
    assert refine_response(text, claims, verifications) == text


def test_refine_response_tags_contradicted_claim() -> None:
    text = "Leave is 20 days [1]."
    claims = extract_claims(text)
    verifications = [_verification(claims[0].text, supported=False, verdict="contradiction")]
    refined = refine_response(text, claims, verifications)
    assert refined == "Leave is 20 days [1]. [⚠ contradicted by source]"


def test_refine_response_tags_unsupported_neutral_claim() -> None:
    text = "The office is closed on holidays [1]."
    claims = extract_claims(text)
    verifications = [_verification(claims[0].text, supported=False, verdict="neutral")]
    refined = refine_response(text, claims, verifications)
    assert refined == "The office is closed on holidays [1]. [⚠ unverified]"


def test_refine_response_multi_claim_insertion_preserves_earlier_spans() -> None:
    text = "First claim is true [1]. Second claim is false [2]. Third claim is true [3]."
    claims = extract_claims(text)
    verifications = [
        _verification(claims[0].text, supported=True),
        _verification(claims[1].text, supported=False, verdict="contradiction"),
        _verification(claims[2].text, supported=True),
    ]
    refined = refine_response(text, claims, verifications)
    assert refined == (
        "First claim is true [1]. Second claim is false [2]. "
        "[⚠ contradicted by source] Third claim is true [3]."
    )


# ---- NLI verifier: real model (locks in the Phase-10 design decision) ----


def test_nli_verifier_entails_true_claim_against_evidence() -> None:
    async def scenario() -> None:
        verifier = CrossEncoderNliVerifier("cross-encoder/nli-deberta-v3-xsmall")
        result = await verifier.score(
            "Employees receive 25 days of paid annual leave per year.",
            "Employees receive 25 days of annual leave.",
        )
        assert result.verdict == "entailment"
        assert result.entailment > 0.9

    asyncio.run(scenario())


def test_nli_verifier_catches_wrong_number_hallucination() -> None:
    """The exact class of hallucination a relevance-only reranker would
    miss: same topic, contradicting fact (the spec's own 20-vs-25 example)."""

    async def scenario() -> None:
        verifier = CrossEncoderNliVerifier("cross-encoder/nli-deberta-v3-xsmall")
        result = await verifier.score(
            "Employees receive 25 days of paid annual leave per year.",
            "Employees receive 20 days of annual leave.",
        )
        assert result.verdict == "contradiction"
        assert result.entailment < 0.1  # entailment probability stays near zero
        assert result.contradiction > 0.9

    asyncio.run(scenario())


# ---- VerificationService: aggregation, hallucination detection ----------


class _EmptyChunkRepository:
    async def get_current_by_embedding_refs(self, refs):
        return {}


class _StubEmbedder:
    model_name = "stub-embedder"
    dimension = 16

    async def embed_texts(self, texts):
        return [[0.0] * self.dimension for _ in texts]


class _EmptyVectorStore:
    async def search(self, vector, k):
        return []


# Shared across tests in this module: the NLI cross-encoder is only ever
# loaded once (lazily, on first .score() call) instead of once per test.
_SHARED_NLI_VERIFIER = CrossEncoderNliVerifier("cross-encoder/nli-deberta-v3-xsmall")


def _service(settings: Settings | None = None) -> VerificationService:
    settings = settings or Settings(
        verification_enabled=True,
        verification_support_threshold=0.5,
    )
    return VerificationService(
        settings, _EmptyChunkRepository(), _StubEmbedder(), _SHARED_NLI_VERIFIER
    )


def _patch_empty_vector_store(monkeypatch) -> None:
    """Independent corpus search finds nothing — isolates these tests to
    the cited-evidence path, which is enough to prove the hallucination
    detection contract without standing up a real vector index."""

    async def _get_empty_store(*args, **kwargs):
        return _EmptyVectorStore()

    monkeypatch.setattr(
        "app.services.verification_service.get_vector_store", _get_empty_store
    )


def _evidence(content: str, **overrides) -> EvidenceChunk:
    defaults = dict(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_title="Employee_Handbook.pdf",
        version_number=1,
        page_number=23,
        section=None,
        content=content,
        retrieval_score=0.9,
        retrievers=["vector"],
    )
    defaults.update(overrides)
    return EvidenceChunk(**defaults)


def test_verification_service_disabled_short_circuits() -> None:
    async def scenario() -> None:
        settings = Settings(verification_enabled=False)
        service = _service(settings)
        outcome = await service.verify("Leave is 25 days [1].", [_evidence("...")])
        assert outcome.enabled is False
        assert outcome.confidence is None
        assert outcome.hallucination_detected is None
        assert outcome.refined_answer == "Leave is 25 days [1]."

    asyncio.run(scenario())


def test_verification_service_no_context_offered_is_not_a_hallucination() -> None:
    from app.modules.llm.generator import NO_CONTEXT_ANSWER

    async def scenario() -> None:
        service = _service()
        outcome = await service.verify(NO_CONTEXT_ANSWER, [])
        assert outcome.enabled is True
        assert outcome.confidence == 1.0
        assert outcome.hallucination_detected is False

    asyncio.run(scenario())


def test_verification_service_supports_true_claim_against_cited_evidence(monkeypatch) -> None:
    async def scenario() -> None:
        _patch_empty_vector_store(monkeypatch)
        service = _service()
        offered = [_evidence("Employees receive 25 days of paid annual leave per year.")]
        outcome = await service.verify("Employees receive 25 days of annual leave [1].", offered)

        assert outcome.hallucination_detected is False
        assert outcome.confidence > 0.9
        [claim] = outcome.claim_verifications
        assert claim.supported is True
        assert claim.verdict == "entailment"
        assert claim.source_document == "Employee_Handbook.pdf"
        assert claim.source_page == 23
        assert claim.citation_verified is True
        assert "⚠" not in outcome.refined_answer

    asyncio.run(scenario())


def test_verification_service_detects_hallucinated_number_against_cited_evidence(
    monkeypatch,
) -> None:
    """The core Module 9 proof: the spec's own example — real evidence says
    25 days, the generated claim says 20 — is caught as a contradiction,
    not waved through as merely "on topic"."""

    async def scenario() -> None:
        _patch_empty_vector_store(monkeypatch)
        service = _service()
        offered = [_evidence("Employees receive 25 days of paid annual leave per year.")]
        outcome = await service.verify("Employees receive 20 days of annual leave [1].", offered)

        assert outcome.hallucination_detected is True
        assert outcome.confidence < 0.1
        [claim] = outcome.claim_verifications
        assert claim.supported is False
        assert claim.verdict == "contradiction"
        assert claim.citation_verified is False
        assert "[⚠ contradicted by source]" in outcome.refined_answer

    asyncio.run(scenario())


def test_verification_service_no_evidence_at_all_is_unsupported(monkeypatch) -> None:
    async def scenario() -> None:
        _patch_empty_vector_store(monkeypatch)
        service = _service()
        # An offered-but-uncited source, so the claim has no [n] markers
        # and the (empty) independent search finds nothing either.
        offered = [_evidence("Unrelated content about parking permits.")]
        outcome = await service.verify("Employees receive 25 days of annual leave.", offered)
        [claim] = outcome.claim_verifications
        assert claim.cited_markers == []
        assert claim.citation_verified is None  # nothing was cited to check
        assert outcome.hallucination_detected is True

    asyncio.run(scenario())


def test_verification_service_confidence_is_mean_of_claim_scores(monkeypatch) -> None:
    async def scenario() -> None:
        _patch_empty_vector_store(monkeypatch)
        service = _service()
        offered = [
            _evidence("Employees receive 25 days of paid annual leave per year.", chunk_id=uuid.uuid4()),
        ]
        text = (
            "Employees receive 25 days of annual leave [1]. "
            "Employees receive 20 days of annual leave [1]."
        )
        outcome = await service.verify(text, offered)
        assert len(outcome.claim_verifications) == 2
        scores = [c.support_score for c in outcome.claim_verifications]
        assert abs(outcome.confidence - (sum(scores) / 2)) < 1e-3

    asyncio.run(scenario())
