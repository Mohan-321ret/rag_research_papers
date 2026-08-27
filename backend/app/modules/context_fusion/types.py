"""The unit of evidence flowing through the context fusion pipeline.

Kept generic (plain fields, no dependency on repository/service types) so
the pipeline stages — dedup, rerank, compress, build — stay pure and
independently testable; the service layer is responsible for converting
retrieval results into this shape and back.
"""

import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EvidenceChunk:
    """One retrieved chunk, carrying everything the Context Builder needs."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    version_number: int
    page_number: int | None
    section: str | None
    content: str
    retrieval_score: float
    retrievers: list[str]
    rerank_score: float | None = None
