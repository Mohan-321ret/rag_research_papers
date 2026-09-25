"""External paper source endpoints: arXiv, PubMed, Semantic Scholar."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUserDep, DocumentServiceDep, SettingsDep
from app.services.external_sources_service import ExternalSourcesService, PaperMetadata

router = APIRouter(prefix="/external", tags=["external-sources"])


# ── Response schemas (inline, no DB persistence needed) ──────────────────────

from pydantic import BaseModel  # noqa: E402


class PaperMetadataResponse(BaseModel):
    title: str
    authors: str
    abstract: str
    source: str
    external_id: str
    url: str
    published: str | None = None
    doi: str | None = None
    pdf_url: str | None = None

    @classmethod
    def from_metadata(cls, m: PaperMetadata) -> "PaperMetadataResponse":
        return cls(
            title=m.title,
            authors=m.authors,
            abstract=m.abstract,
            source=m.source,
            external_id=m.external_id,
            url=m.url,
            published=m.published,
            doi=m.doi,
            pdf_url=m.pdf_url,
        )


class ExternalSearchResponse(BaseModel):
    query: str
    sources: list[str]
    total: int
    papers: list[PaperMetadataResponse]


class IngestRequest(BaseModel):
    title: str
    authors: str
    abstract: str
    source: str
    external_id: str
    url: str
    published: str | None = None
    doi: str | None = None
    pdf_url: str | None = None


class IngestResponse(BaseModel):
    message: str
    document_id: uuid.UUID
    title: str
    new_version_created: bool
    deduplicated: bool


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_service(settings: SettingsDep, doc_service: DocumentServiceDep) -> ExternalSourcesService:
    return ExternalSourcesService(settings, doc_service)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/search",
    response_model=ExternalSearchResponse,
    summary="Search arXiv, PubMed, Semantic Scholar, CORE and optionally auto-ingest into RAG",
)
async def search_external(
    settings: SettingsDep,
    doc_service: DocumentServiceDep,
    user: CurrentUserDep,
    query: Annotated[str, Query(min_length=2, max_length=500)],
    sources: Annotated[
        str,
        Query(description="Comma-separated: arxiv,pubmed,semantic_scholar,core"),
    ] = "arxiv,pubmed,semantic_scholar",
    max_per_source: Annotated[int, Query(ge=1, le=25)] = 10,
    auto_ingest: Annotated[bool, Query(description="Automatically ingest found papers into RAG corpus")] = False,
) -> ExternalSearchResponse:
    source_list = [s.strip() for s in sources.split(",") if s.strip()]
    svc = _get_service(settings, doc_service)
    papers = await svc.search(query, source_list, max_per_source)
    if auto_ingest and papers:
        for paper in papers:
            try:
                await svc.ingest(paper, user)
            except Exception:
                pass
    return ExternalSearchResponse(
        query=query,
        sources=source_list,
        total=len(papers),
        papers=[PaperMetadataResponse.from_metadata(p) for p in papers],
    )


@router.post(
    "/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a paper from an external source into the RAG knowledge base",
)
async def ingest_external_paper(
    settings: SettingsDep,
    doc_service: DocumentServiceDep,
    user: CurrentUserDep,
    payload: IngestRequest,
) -> IngestResponse:
    from app.services.external_sources_service import PaperMetadata as _PM

    paper = _PM(
        title=payload.title,
        authors=payload.authors,
        abstract=payload.abstract,
        source=payload.source,
        external_id=payload.external_id,
        url=payload.url,
        published=payload.published,
        doi=payload.doi,
        pdf_url=payload.pdf_url,
    )
    svc = _get_service(settings, doc_service)
    result = await svc.ingest(paper, user)
    return IngestResponse(
        message="Paper ingested successfully",
        document_id=result.id,
        title=result.title,
        new_version_created=result.new_version_created,
        deduplicated=result.deduplicated,
    )
