"""The unit of result flowing out of the verification pipeline.

Kept generic (plain dataclasses, no dependency on the API schema layer)
so the pipeline stages stay pure and independently testable; the service
layer converts these into the API response shape.
"""

import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ClaimVerification:
    """Fact Verification + Confidence Scoring + Citation Verification for
    one extracted claim."""

    claim: str
    support_score: float
    supported: bool
    verdict: str  # "entailment" | "contradiction" | "neutral" | "no_evidence"
    source_document: str | None
    source_version: int | None
    source_page: int | None
    source_chunk_id: uuid.UUID | None
    cited_markers: list[int]
    citation_verified: bool | None  # None when the claim had no [n] markers to check


@dataclass(frozen=True, slots=True)
class VerificationOutcome:
    """Overall Evidence Verification result for one generated answer."""

    enabled: bool
    refined_answer: str
    confidence: float | None
    hallucination_detected: bool | None
    claim_verifications: list[ClaimVerification] = field(default_factory=list)
    model_name: str = "none"
