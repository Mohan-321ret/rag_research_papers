"""Repository-level tests for as-of (temporal) chunk retrieval.

Deterministic and DB-only — no embedding model needed. Proves the core
new SQL (each document's version active as of a cutoff date) directly,
independent of the StubEmbedder's hash-based (non-semantic) vectors used
in the API test suite, which can't reliably prove real similarity.
"""

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.document import Document, DocumentChunk, DocumentStatus, DocumentVersion
from app.models.user import User, UserRole
from app.repositories.chunk_repository import ChunkRepository


@pytest.fixture
def db_session_factory(test_db_engine):
    return async_sessionmaker(test_db_engine, expire_on_commit=False)


async def _seed_two_versions(session):
    """Doc created in 2023 (v1: "20 days"), revised in 2026 (v2: "25 days")."""
    user = User(
        email=f"u-{uuid.uuid4().hex}@example.com",
        hashed_password="x",
        role=UserRole.USER,
    )
    session.add(user)
    await session.flush()

    document = Document(
        title="Leave Policy",
        source_uri="leave.txt",
        source_type="upload",
        status=DocumentStatus.READY,
        created_by_id=user.id,
    )
    session.add(document)
    await session.flush()

    v1 = DocumentVersion(
        document_id=document.id,
        version_number=1,
        content_hash="h1",
        content="Employees receive 20 days of annual leave.",
        is_current=False,
        created_at=datetime(2023, 6, 1, tzinfo=UTC),
    )
    v2 = DocumentVersion(
        document_id=document.id,
        version_number=2,
        content_hash="h2",
        content="Employees receive 25 days of annual leave.",
        is_current=True,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    session.add_all([v1, v2])
    await session.flush()

    c1 = DocumentChunk(
        version_id=v1.id, document_id=document.id, chunk_index=0,
        content=v1.content, embedding_ref="101",
    )
    c2 = DocumentChunk(
        version_id=v2.id, document_id=document.id, chunk_index=0,
        content=v2.content, embedding_ref="102",
    )
    session.add_all([c1, c2])
    await session.commit()
    return document, v1, v2, c1, c2


def test_as_of_before_revision_resolves_to_old_version(db_session_factory) -> None:
    async def scenario() -> None:
        async with db_session_factory() as session:
            document, v1, v2, c1, c2 = await _seed_two_versions(session)
            repo = ChunkRepository(session)

            as_of_2024 = await repo.get_as_of_by_embedding_refs(
                ["101", "102"], datetime(2024, 1, 1, tzinfo=UTC)
            )
            assert set(as_of_2024) == {"101"}
            assert as_of_2024["101"].chunk.content == "Employees receive 20 days of annual leave."
            assert as_of_2024["101"].version_number == 1

    asyncio.run(scenario())


def test_as_of_after_revision_resolves_to_new_version(db_session_factory) -> None:
    async def scenario() -> None:
        async with db_session_factory() as session:
            document, v1, v2, c1, c2 = await _seed_two_versions(session)
            repo = ChunkRepository(session)

            as_of_2027 = await repo.get_as_of_by_embedding_refs(
                ["101", "102"], datetime(2027, 1, 1, tzinfo=UTC)
            )
            assert set(as_of_2027) == {"102"}
            assert as_of_2027["102"].chunk.content == "Employees receive 25 days of annual leave."

    asyncio.run(scenario())


def test_as_of_before_document_existed_resolves_to_nothing(db_session_factory) -> None:
    async def scenario() -> None:
        async with db_session_factory() as session:
            document, v1, v2, c1, c2 = await _seed_two_versions(session)
            repo = ChunkRepository(session)

            as_of_2020 = await repo.get_as_of_by_embedding_refs(
                ["101", "102"], datetime(2020, 1, 1, tzinfo=UTC)
            )
            assert as_of_2020 == {}

    asyncio.run(scenario())


def test_current_ignores_as_of_and_always_returns_latest(db_session_factory) -> None:
    async def scenario() -> None:
        async with db_session_factory() as session:
            document, v1, v2, c1, c2 = await _seed_two_versions(session)
            repo = ChunkRepository(session)

            current = await repo.get_current_by_embedding_refs(["101", "102"])
            assert set(current) == {"102"}

    asyncio.run(scenario())


def test_as_of_by_ids_current_chunk_id_resolves_to_nothing_under_old_cutoff(
    db_session_factory,
) -> None:
    """A BM25/graph hit is always a *current*-version chunk id (those
    retrievers only ever index current content). Under an as-of cutoff
    that predates the current version, that id correctly resolves to
    nothing — it isn't valid as of that date — rather than silently
    returning today's content for a historical query."""

    async def scenario() -> None:
        async with db_session_factory() as session:
            document, v1, v2, c1, c2 = await _seed_two_versions(session)
            repo = ChunkRepository(session)

            resolved = await repo.get_as_of_by_ids([c2.id], datetime(2024, 1, 1, tzinfo=UTC))
            assert resolved == {}

            # But the OLD chunk's own id resolves fine under that cutoff.
            resolved_old = await repo.get_as_of_by_ids([c1.id], datetime(2024, 1, 1, tzinfo=UTC))
            assert set(resolved_old) == {c1.id}

    asyncio.run(scenario())
