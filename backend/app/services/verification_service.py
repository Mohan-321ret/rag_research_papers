"""Evidence verification service (Module 9).

Generated answer -> Claim Extraction -> for each claim: Evidence
Retrieval (the offered SOURCE block it cited, plus an independent
corpus-wide vector search) -> Fact Verification (NLI claim<->evidence
comparison) -> Support Score -> Citation Verification -> aggregate
Confidence Scoring + Hallucination Detection -> Response Refinement ->
Verified Answer.

Evidence retrieval deliberately checks the whole current-version corpus,
not just the chunks Module 7 already offered to the LLM: a claim can be
unsupported by every offered source yet still be true (evidence exists
but wasn't retrieved), or worse, be actively contradicted by something
the model was never shown. Checking the full corpus catches both.
"""

import uuid

from app.core.config import Settings
from app.core.logging import get_logger
from app.modules.context_fusion.types import EvidenceChunk
from app.modules.processing.embedding import SentenceTransformerEmbedder
from app.modules.repository.vector_store import get_vector_store
from app.modules.verification.claim_extraction import Claim, extract_claims
from app.modules.verification.nli_verifier import NliVerifier, nli_available
from app.modules.verification.refinement import refine_response
from app.modules.verification.types import ClaimVerification, VerificationOutcome
from app.repositories.chunk_repository import ChunkRepository

logger = get_logger(__name__)

_NO_EVIDENCE_VERDICT = "no_evidence"


def _to_evidence(retrievable, score: float) -> EvidenceChunk:
    return EvidenceChunk(
        chunk_id=retrievable.chunk.id,
        document_id=retrievable.chunk.document_id,
        document_title=retrievable.document_title,
        version_number=retrievable.version_number,
        page_number=retrievable.chunk.page_number,
        section=retrievable.chunk.section,
        content=retrievable.chunk.content,
        retrieval_score=score,
        retrievers=["vector"],
    )


class VerificationService:
    def __init__(
        self,
        settings: Settings,
        chunk_repository: ChunkRepository,
        embedder: SentenceTransformerEmbedder,
        verifier: NliVerifier,
    ) -> None:
        self._settings = settings
        self._chunks = chunk_repository
        self._embedder = embedder
        self._verifier = verifier

    def _active(self) -> bool:
        return self._settings.verification_enabled and nli_available()

    async def verify(
        self, answer_text: str, offered: list[EvidenceChunk]
    ) -> VerificationOutcome:
        if not self._active():
            return VerificationOutcome(
                enabled=False,
                refined_answer=answer_text,
                confidence=None,
                hallucination_detected=None,
            )

        if not offered:
            # No context was offered to the generator at all (the
            # NO_CONTEXT_ANSWER path) — an honest "I don't know" isn't a
            # hallucination, and there's no evidence pool to check it
            # against.
            return VerificationOutcome(
                enabled=True,
                refined_answer=answer_text,
                confidence=1.0,
                hallucination_detected=False,
                model_name=self._verifier.model_name,
            )

        claims = extract_claims(answer_text)
        if not claims:
            return VerificationOutcome(
                enabled=True,
                refined_answer=answer_text,
                confidence=1.0,
                hallucination_detected=False,
                model_name=self._verifier.model_name,
            )

        verifications = [await self._verify_claim(claim, offered) for claim in claims]

        confidence = round(
            sum(v.support_score for v in verifications) / len(verifications), 4
        )
        hallucination_detected = any(not v.supported for v in verifications)
        refined = refine_response(answer_text, claims, verifications)

        logger.info(
            "answer_verified",
            claims=len(verifications),
            confidence=confidence,
            hallucination_detected=hallucination_detected,
            model=self._verifier.model_name,
        )
        return VerificationOutcome(
            enabled=True,
            refined_answer=refined,
            confidence=confidence,
            hallucination_detected=hallucination_detected,
            claim_verifications=verifications,
            model_name=self._verifier.model_name,
        )

    async def _verify_claim(
        self, claim: Claim, offered: list[EvidenceChunk]
    ) -> ClaimVerification:
        cited_evidence = [
            offered[marker - 1] for marker in claim.markers if 1 <= marker <= len(offered)
        ]
        retrieved_evidence = await self._retrieve_evidence(claim.text)

        candidates = list(cited_evidence)
        if retrieved_evidence is not None:
            candidates.append(retrieved_evidence)

        if not candidates:
            return ClaimVerification(
                claim=claim.text,
                support_score=0.0,
                supported=False,
                verdict=_NO_EVIDENCE_VERDICT,
                source_document=None,
                source_version=None,
                source_page=None,
                source_chunk_id=None,
                cited_markers=claim.markers,
                citation_verified=None,
            )

        scored = [
            (evidence, await self._verifier.score(evidence.content, claim.text))
            for evidence in candidates
        ]
        best_evidence, best = max(scored, key=lambda row: row[1].entailment)
        threshold = self._settings.verification_support_threshold
        supported = best.verdict == "entailment" and best.entailment >= threshold

        citation_verified = None
        if cited_evidence:
            cited_scores = scored[: len(cited_evidence)]
            citation_verified = any(
                score.verdict == "entailment" and score.entailment >= threshold
                for _, score in cited_scores
            )

        return ClaimVerification(
            claim=claim.text,
            support_score=round(best.entailment, 4),
            supported=supported,
            verdict=best.verdict,
            source_document=best_evidence.document_title,
            source_version=best_evidence.version_number,
            source_page=best_evidence.page_number,
            source_chunk_id=best_evidence.chunk_id,
            cited_markers=claim.markers,
            citation_verified=citation_verified,
        )

    async def _retrieve_evidence(self, claim_text: str) -> EvidenceChunk | None:
        """Independent, corpus-wide top-1 vector search for this claim."""
        [vector] = await self._embedder.embed_texts([claim_text])
        store = await get_vector_store(
            self._settings.vector_index_dir,
            self._embedder.dimension,
            self._embedder.model_name,
        )
        hits = await store.search(vector, k=5)
        qualifying = [h for h in hits if h.score >= self._settings.verification_min_evidence_score]
        if not qualifying:
            return None

        by_ref = await self._chunks.get_current_by_embedding_refs(
            [hit.chunk_id for hit in qualifying]
        )
        for hit in qualifying:
            retrievable = by_ref.get(hit.chunk_id)
            if retrievable is not None:
                return _to_evidence(retrievable, hit.score)
        return None
