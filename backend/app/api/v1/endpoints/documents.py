"""Document ingestion endpoints. All logic lives in DocumentService."""

import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, Query, UploadFile, status

from app.api.deps import (
    ConflictServiceDep,
    CurrentUserDep,
    DocumentServiceDep,
    EvolutionServiceDep,
    ProcessingServiceDep,
)
from app.schemas.conflict import ConflictListResponse, KnowledgeConflictRead
from app.schemas.document import (
    DocumentListResponse,
    DocumentRead,
    DocumentVersionRead,
    UploadResponse,
)
from app.schemas.evolution import (
    ConceptDriftHistoryResponse,
    ConceptDriftReportRead,
    EvolutionHistoryResponse,
    VersionComparisonRead,
)
from app.schemas.processing import ChunkListResponse, ProcessingResult

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document (PDF, DOCX, TXT, HTML, XLSX)",
)
async def upload_document(
    service: DocumentServiceDep,
    user: CurrentUserDep,
    file: Annotated[UploadFile, File()],
    title: Annotated[str | None, Form(max_length=500)] = None,
    author: Annotated[str | None, Form(max_length=200)] = None,
    department: Annotated[str | None, Form(max_length=200)] = None,
    access_level: Annotated[str | None, Form(max_length=50)] = None,
    priority: Annotated[
        int | None,
        Form(description="Authority rank for cross-document conflict resolution; higher wins"),
    ] = None,
) -> UploadResponse:
    content = await file.read()
    return await service.upload(
        user=user,
        filename=file.filename,
        content=content,
        title=title,
        author=author,
        department=department,
        access_level=access_level,
        priority=priority,
    )


@router.get("", response_model=DocumentListResponse, summary="List documents")
async def list_documents(
    service: DocumentServiceDep,
    _user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    search: Annotated[str | None, Query(max_length=200)] = None,
) -> DocumentListResponse:
    return await service.list_documents(limit=limit, offset=offset, search=search)


@router.get("/{document_id}", response_model=DocumentRead, summary="Get one document")
async def get_document(
    document_id: uuid.UUID, service: DocumentServiceDep, _user: CurrentUserDep
) -> DocumentRead:
    return await service.get_document(document_id)


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document (owner or admin)",
)
async def delete_document(
    document_id: uuid.UUID, service: DocumentServiceDep, user: CurrentUserDep
) -> None:
    await service.delete_document(document_id=document_id, user=user)


@router.post(
    "/{document_id}/process",
    response_model=ProcessingResult,
    summary="Run (or re-run) the processing pipeline on the current version",
)
async def process_document(
    document_id: uuid.UUID, service: ProcessingServiceDep, _user: CurrentUserDep
) -> ProcessingResult:
    return await service.process_document(document_id)


@router.get(
    "/{document_id}/chunks",
    response_model=ChunkListResponse,
    summary="Chunks of a document version (defaults to the current version)",
)
async def list_chunks(
    document_id: uuid.UUID,
    service: ProcessingServiceDep,
    _user: CurrentUserDep,
    version: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ChunkListResponse:
    return await service.list_chunks(
        document_id, version_number=version, limit=limit, offset=offset
    )


@router.get(
    "/{document_id}/versions",
    response_model=list[DocumentVersionRead],
    summary="Version history of a document",
)
async def get_document_versions(
    document_id: uuid.UUID, service: DocumentServiceDep, _user: CurrentUserDep
) -> list[DocumentVersionRead]:
    return await service.get_versions(document_id)


@router.get(
    "/{document_id}/evolution",
    response_model=EvolutionHistoryResponse,
    summary="Knowledge evolution timeline: change/diff/drift/conflict per version transition",
)
async def get_document_evolution(
    document_id: uuid.UUID, service: EvolutionServiceDep, _user: CurrentUserDep
) -> EvolutionHistoryResponse:
    comparisons = await service.history(document_id)
    return EvolutionHistoryResponse(
        document_id=document_id,
        comparisons=[VersionComparisonRead.model_validate(c) for c in comparisons],
    )


@router.get(
    "/{document_id}/concept-drift",
    response_model=ConceptDriftHistoryResponse,
    summary="Chunk-level concept drift: embedding nearest-neighbor pairing, "
    "classified as rewording/expansion/narrowing/contradiction/topic_shift",
)
async def get_document_concept_drift(
    document_id: uuid.UUID, service: EvolutionServiceDep, _user: CurrentUserDep
) -> ConceptDriftHistoryResponse:
    reports = await service.concept_drift_history(document_id)
    return ConceptDriftHistoryResponse(
        document_id=document_id,
        reports=[ConceptDriftReportRead.model_validate(r) for r in reports],
    )


@router.get(
    "/{document_id}/conflicts",
    response_model=ConflictListResponse,
    summary="Cross-document contradictions involving this document, with authority resolution",
)
async def get_document_conflicts(
    document_id: uuid.UUID, service: ConflictServiceDep, _user: CurrentUserDep
) -> ConflictListResponse:
    conflicts = await service.list_for_document(document_id)
    return ConflictListResponse(
        items=[KnowledgeConflictRead.model_validate(c) for c in conflicts],
        total=len(conflicts),
        limit=len(conflicts),
        offset=0,
    )
