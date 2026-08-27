"""Service-level tests for cross-document conflict detection (Phase 13):
corpus-wide candidate search -> NLI contradiction check -> authority
resolution -> persistence.

Uses controlled fixed-vector/fixed-verdict fakes (not the real embedder
or NLI model — those are already validated in test_evolution_detectors.py
and test_concept_drift.py) so the *orchestration* — thresholds, exclusion
of the document's own chunks, wiring into the authority resolver — is
tested deterministically. Runs directly against its own isolated SQLite
DB per test (not the suite's shared session-scoped one): the vector
store's integer ids restart from 1 each time it's reset, and a shared DB
would let one test's leftover chunk rows collide, by embedding_ref, with
another test's freshly-allocated ids.
"""

import asyncio
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.models import Base
from app.models.document import Document, DocumentChunk, DocumentStatus, DocumentVersion
from app.models.user import User, UserRole
from app.modules.repository.vector_store import get_vector_store, reset_vector_store
from app.modules.verification.nli_verifier import NliScore
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.conflict_repository import ConflictRepository
from app.repositories.document_repository import DocumentRepository
from app.services.conflict_service import ConflictService

LEAVE_20 = "Employees get 20 days leave."
LEAVE_25 = "Employees get 25 days leave."


@pytest.fixture
def db_session_factory(tmp_path: Path):
    db_path = tmp_path / "conflict_test.sqlite3"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", poolclass=NullPool)

    async def _create_schema() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_create_schema())
    yield async_sessionmaker(engine, expire_on_commit=False)
    asyncio.run(engine.dispose())


class _FixedEmbedder:
    model_name = "fixed-test-embedder"
    dimension = 4

    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self._vectors = vectors

    async def embed_texts(self, texts):
        return [self._vectors[t] for t in texts]


class _FixedVerifier:
    model_name = "fixed-test-verifier"

    def __init__(self, contradictions: set[tuple[str, str]]) -> None:
        self._contradictions = contradictions

    async def score(self, premise: str, hypothesis: str) -> NliScore:
        if (premise, hypothesis) in self._contradictions:
            return NliScore(contradiction=0.95, entailment=0.02, neutral=0.03, verdict="contradiction")
        return NliScore(contradiction=0.01, entailment=0.1, neutral=0.89, verdict="neutral")


async def _seed_document(session, embedder, store, *, title, content, priority, created_at):
    user = User(email=f"u-{uuid.uuid4().hex}@example.com", hashed_password="x", role=UserRole.USER)
    session.add(user)
    await session.flush()

    document = Document(
        title=title, source_uri=f"{title}.txt", source_type="upload",
        status=DocumentStatus.READY, created_by_id=user.id,
        doc_metadata={"priority": priority, "department": None},
    )
    session.add(document)
    await session.flush()

    version = DocumentVersion(
        document_id=document.id, version_number=1, content_hash=uuid.uuid4().hex,
        content=content, is_current=True, created_at=created_at,
    )
    session.add(version)
    await session.flush()

    [vector] = await embedder.embed_texts([content])
    [vector_id] = await store.add([vector])

    chunk = DocumentChunk(
        version_id=version.id, document_id=document.id, chunk_index=0,
        content=content, embedding_ref=str(vector_id),
    )
    session.add(chunk)
    await session.commit()
    return document, chunk


def test_detects_conflict_and_prefers_higher_priority_document(
    tmp_path, db_session_factory
) -> None:
    async def scenario() -> None:
        settings = Settings(
            vector_index_dir=str(tmp_path / "vectors"),
            conflict_detection_enabled=True,
            conflict_similarity_threshold=0.5,
            conflict_contradiction_threshold=0.5,
        )
        reset_vector_store()
        embedder = _FixedEmbedder({
            LEAVE_20: [1.0, 0.0, 0.0, 0.0],
            LEAVE_25: [0.9, 0.1, 0.0, 0.0],  # same topic: high cosine similarity
        })
        verifier = _FixedVerifier({(LEAVE_25, LEAVE_20)})
        try:
            async with db_session_factory() as session:
                store = await get_vector_store(
                    settings.vector_index_dir, embedder.dimension, embedder.model_name
                )
                doc_a, chunk_a = await _seed_document(
                    session, embedder, store,
                    title="HR Handbook", content=LEAVE_20, priority=1,
                    created_at=datetime(2024, 1, 1, tzinfo=UTC),
                )
                doc_b, chunk_b = await _seed_document(
                    session, embedder, store,
                    title="Legal Policy", content=LEAVE_25, priority=5,
                    created_at=datetime(2024, 6, 1, tzinfo=UTC),
                )

                service = ConflictService(
                    settings, ConflictRepository(session), DocumentRepository(session),
                    ChunkRepository(session), embedder, verifier,
                )
                detected = await service.detect_for_document(
                    doc_b.id, [(chunk_b.id, chunk_b.content)]
                )

                assert len(detected) == 1
                conflict = detected[0]
                assert conflict.claim_a_chunk_id == chunk_b.id
                assert conflict.claim_b_chunk_id == chunk_a.id
                assert conflict.resolved is True
                assert conflict.preferred_chunk_id == chunk_b.id  # Legal Policy: priority 5 > 1
                assert "priority" in conflict.resolution_reason.lower()
                assert conflict.contradiction_score > 0.9
        finally:
            reset_vector_store()

    asyncio.run(scenario())


def test_similar_but_not_contradicting_is_not_flagged(tmp_path, db_session_factory) -> None:
    async def scenario() -> None:
        settings = Settings(
            vector_index_dir=str(tmp_path / "vectors"),
            conflict_detection_enabled=True,
            conflict_similarity_threshold=0.5,
            conflict_contradiction_threshold=0.5,
        )
        reset_vector_store()
        embedder = _FixedEmbedder({
            LEAVE_20: [1.0, 0.0, 0.0, 0.0],
            LEAVE_25: [0.9, 0.1, 0.0, 0.0],
        })
        verifier = _FixedVerifier(set())  # nothing registered as a contradiction
        try:
            async with db_session_factory() as session:
                store = await get_vector_store(
                    settings.vector_index_dir, embedder.dimension, embedder.model_name
                )
                doc_a, chunk_a = await _seed_document(
                    session, embedder, store,
                    title="HR Handbook", content=LEAVE_20, priority=1,
                    created_at=datetime(2024, 1, 1, tzinfo=UTC),
                )
                doc_b, chunk_b = await _seed_document(
                    session, embedder, store,
                    title="Legal Policy", content=LEAVE_25, priority=5,
                    created_at=datetime(2024, 6, 1, tzinfo=UTC),
                )

                service = ConflictService(
                    settings, ConflictRepository(session), DocumentRepository(session),
                    ChunkRepository(session), embedder, verifier,
                )
                detected = await service.detect_for_document(
                    doc_b.id, [(chunk_b.id, chunk_b.content)]
                )
                assert detected == []
        finally:
            reset_vector_store()

    asyncio.run(scenario())


def test_below_similarity_threshold_never_reaches_nli(tmp_path, db_session_factory) -> None:
    async def scenario() -> None:
        settings = Settings(
            vector_index_dir=str(tmp_path / "vectors"),
            conflict_detection_enabled=True,
            conflict_similarity_threshold=0.9,  # strict: needs near-identical topic
            conflict_contradiction_threshold=0.5,
        )
        reset_vector_store()
        embedder = _FixedEmbedder({
            LEAVE_20: [1.0, 0.0, 0.0, 0.0],
            "Unrelated content about parking permits.": [0.0, 1.0, 0.0, 0.0],
        })

        class _ExplodingVerifier:
            model_name = "should-not-be-called"

            async def score(self, premise, hypothesis):
                raise AssertionError("NLI must not run below the similarity threshold")

        try:
            async with db_session_factory() as session:
                store = await get_vector_store(
                    settings.vector_index_dir, embedder.dimension, embedder.model_name
                )
                doc_a, chunk_a = await _seed_document(
                    session, embedder, store,
                    title="HR Handbook", content=LEAVE_20, priority=1,
                    created_at=datetime(2024, 1, 1, tzinfo=UTC),
                )
                doc_b, chunk_b = await _seed_document(
                    session, embedder, store,
                    title="Facilities Memo", content="Unrelated content about parking permits.",
                    priority=5, created_at=datetime(2024, 6, 1, tzinfo=UTC),
                )

                service = ConflictService(
                    settings, ConflictRepository(session), DocumentRepository(session),
                    ChunkRepository(session), embedder, _ExplodingVerifier(),
                )
                detected = await service.detect_for_document(
                    doc_b.id, [(chunk_b.id, chunk_b.content)]
                )
                assert detected == []
        finally:
            reset_vector_store()

    asyncio.run(scenario())
