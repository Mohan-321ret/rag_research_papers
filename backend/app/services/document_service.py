"""Document ingestion service.

Orchestrates the upload flow: validation -> type detection -> extraction
(-> OCR fallback) -> metadata assembly -> persistence (document +
immutable version) -> raw-file storage. Chunking/embedding (the
processing pipeline) attaches to READY versions in Phase 3.
"""

import hashlib
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import (
    BadRequestError,
    ForbiddenError,
    NotFoundError,
    PayloadTooLargeError,
)
from app.core.logging import get_logger
from app.models.document import Document, DocumentStatus
from app.models.user import User, UserRole
from app.modules.ingestion.detection import FileType, detect_file_type
from app.modules.ingestion.extractors import ExtractionResult, build_extractor_registry
from app.modules.ingestion.ocr import TesseractOcrEngine
from app.modules.processing.embedding import embedding_stack_available
from app.repositories.audit_repository import AuditRepository
from app.repositories.document_repository import DocumentRepository
from app.services.processing_service import ProcessingService
from app.schemas.document import (
    DocumentListResponse,
    DocumentRead,
    DocumentVersionRead,
    UploadResponse,
)

logger = get_logger(__name__)


class DocumentService:
    def __init__(
        self,
        settings: Settings,
        session: AsyncSession,
        document_repository: DocumentRepository,
        audit_repository: AuditRepository,
        processing_service: ProcessingService,
    ) -> None:
        self._settings = settings
        self._session = session
        self._documents = document_repository
        self._audit = audit_repository
        self._processing = processing_service

        ocr_engine = TesseractOcrEngine()
        self._extractors = build_extractor_registry(
            ocr_engine if settings.ocr_enabled and ocr_engine.is_available() else None
        )

    # ---- upload -----------------------------------------------------------

    async def upload(
        self,
        *,
        user: User,
        filename: str | None,
        content: bytes,
        title: str | None,
        author: str | None,
        department: str | None,
        access_level: str | None,
        priority: int | None = None,
    ) -> UploadResponse:
        filename = self._validate_upload(filename, content)
        file_type = detect_file_type(filename, content)
        extraction = self._extract(file_type, content)
        content_hash = hashlib.sha256(extraction.text.encode("utf-8")).hexdigest()

        metadata = self._build_metadata(
            filename=filename,
            file_type=file_type,
            extraction=extraction,
            title=title,
            author=author,
            department=department,
            access_level=access_level,
            priority=priority,
        )

        document = await self._documents.get_by_filename(
            created_by_id=user.id, filename=filename
        )
        deduplicated = False
        new_version_created = False

        if document is None:
            document = await self._documents.create_document(
                title=metadata["title"],
                source_uri=filename,
                source_type="upload",
                metadata=metadata,
                created_by_id=user.id,
            )
            version = await self._documents.add_version(
                document_id=document.id,
                version_number=1,
                content_hash=content_hash,
                content=extraction.text,
            )
            new_version_created = True
        else:
            versions = await self._documents.get_versions(document.id)
            current = next((v for v in versions if v.is_current), None)
            if current is not None and current.content_hash == content_hash:
                deduplicated = True
                version = current
            else:
                version = await self._documents.add_version(
                    document_id=document.id,
                    version_number=(versions[-1].version_number + 1) if versions else 1,
                    content_hash=content_hash,
                    content=extraction.text,
                )
                new_version_created = True
            document.title = metadata["title"]
            document.doc_metadata = metadata

        # PENDING = extracted, awaiting chunking/embedding; the processing
        # pipeline promotes it to READY (or FAILED).
        if new_version_created:
            document.status = DocumentStatus.PENDING
            self._store_raw_file(document.id, version.version_number, filename, content)

        await self._audit.record(
            action="document.upload",
            user_id=user.id,
            resource_type="document",
            resource_id=str(document.id),
            details={
                "filename": filename,
                "file_type": file_type.value,
                "version": version.version_number,
                "deduplicated": deduplicated,
                "used_ocr": extraction.used_ocr,
            },
        )
        await self._session.commit()
        logger.info(
            "document_ingested",
            document_id=str(document.id),
            file_type=file_type.value,
            version=version.version_number,
            characters=len(extraction.text),
            used_ocr=extraction.used_ocr,
            deduplicated=deduplicated,
        )

        if new_version_created and self._settings.auto_process_on_upload:
            if embedding_stack_available():
                try:
                    await self._processing.process_document(document.id)
                except Exception:
                    # Status/metadata already record the failure; the upload
                    # itself succeeded.
                    logger.warning(
                        "auto_processing_failed", document_id=str(document.id)
                    )
            else:
                document.doc_metadata = {
                    **document.doc_metadata,
                    "processing": "deferred: embedding stack not installed",
                }
                await self._session.commit()

        # The UPDATE expires server-maintained columns (updated_at); reload
        # them explicitly — lazy loading is unavailable in async context.
        await self._session.refresh(document)
        versions = await self._documents.get_versions(document.id)
        read = self._to_read(document, versions)
        return UploadResponse(
            **read.model_dump(),
            new_version_created=new_version_created,
            deduplicated=deduplicated,
        )

    # ---- queries ----------------------------------------------------------

    async def list_documents(
        self, *, limit: int, offset: int, search: str | None
    ) -> DocumentListResponse:
        documents, total = await self._documents.list_documents(
            limit=limit, offset=offset, search=search
        )
        items = [self._to_read(doc, doc.versions) for doc in documents]
        return DocumentListResponse(items=items, total=total, limit=limit, offset=offset)

    async def get_document(self, document_id: uuid.UUID) -> DocumentRead:
        document = await self._get_or_404(document_id)
        return self._to_read(document, document.versions)

    async def get_versions(self, document_id: uuid.UUID) -> list[DocumentVersionRead]:
        document = await self._get_or_404(document_id)
        return [DocumentVersionRead.model_validate(v) for v in document.versions]

    async def delete_document(self, *, document_id: uuid.UUID, user: User) -> None:
        document = await self._get_or_404(document_id)
        if document.created_by_id != user.id and user.role != UserRole.ADMIN:
            raise ForbiddenError("Only the document owner or an admin can delete it")

        await self._processing.remove_document_vectors(document_id)
        await self._processing.remove_document_from_graph(document_id)
        await self._documents.delete(document)
        await self._audit.record(
            action="document.delete",
            user_id=user.id,
            resource_type="document",
            resource_id=str(document_id),
        )
        await self._session.commit()

        storage_dir = Path(self._settings.upload_dir) / str(document_id)
        shutil.rmtree(storage_dir, ignore_errors=True)
        logger.info("document_deleted", document_id=str(document_id))

    # ---- internals --------------------------------------------------------

    def _validate_upload(self, filename: str | None, content: bytes) -> str:
        if not filename or not filename.strip():
            raise BadRequestError("Uploaded file must have a filename")
        if not content:
            raise BadRequestError("Uploaded file is empty")
        max_bytes = self._settings.max_upload_size_mb * 1024 * 1024
        if len(content) > max_bytes:
            raise PayloadTooLargeError(
                f"File exceeds the {self._settings.max_upload_size_mb} MB upload limit"
            )
        # Normalize away any client-provided path components.
        return Path(filename).name

    def _extract(self, file_type: FileType, content: bytes) -> ExtractionResult:
        extraction = self._extractors[file_type].extract(content)
        if not extraction.text:
            extraction.warnings.append("No text could be extracted from this file")
        return extraction

    def _build_metadata(
        self,
        *,
        filename: str,
        file_type: FileType,
        extraction: ExtractionResult,
        title: str | None,
        author: str | None,
        department: str | None,
        access_level: str | None,
        priority: int | None,
    ) -> dict[str, object]:
        native = extraction.native_metadata
        metadata: dict[str, object] = {
            "title": title or native.get("title") or Path(filename).stem,
            "filename": filename,
            "file_type": file_type.value,
            "source": "upload",
            "author": author or native.get("author"),
            "department": department,
            # Authority rank for Phase 13 cross-document conflict
            # resolution — higher wins when two documents contradict.
            "priority": priority or 0,
            "created_at": datetime.now(UTC).isoformat(),
            "access_level": access_level or "internal",
            "characters": len(extraction.text),
            "used_ocr": extraction.used_ocr,
        }
        if extraction.page_count is not None:
            metadata["page_count"] = extraction.page_count
        if extraction.warnings:
            metadata["warnings"] = extraction.warnings
        return metadata

    def _store_raw_file(
        self, document_id: uuid.UUID, version_number: int, filename: str, content: bytes
    ) -> None:
        suffix = Path(filename).suffix
        target_dir = Path(self._settings.upload_dir) / str(document_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / f"v{version_number}{suffix}").write_bytes(content)

    async def _get_or_404(self, document_id: uuid.UUID) -> Document:
        document = await self._documents.get(document_id)
        if document is None:
            raise NotFoundError("Document not found")
        return document

    @staticmethod
    def _to_read(document: Document, versions: list) -> DocumentRead:
        current = next((v for v in versions if v.is_current), None)
        return DocumentRead(
            id=document.id,
            title=document.title,
            source_uri=document.source_uri,
            source_type=document.source_type,
            status=document.status,
            metadata=document.doc_metadata,
            created_by_id=document.created_by_id,
            created_at=document.created_at,
            updated_at=document.updated_at,
            current_version=current.version_number if current else None,
            version_count=len(versions),
        )
